"""Append whole entity timelines, avoiding in-place closing of old periods."""

import json
import re
import sqlite3
from dataclasses import asdict
from typing import Iterable, Protocol

from ai_trade.data_access.models import IntegrityError, ValidationError, WriteResult
from ai_trade.data_access.validation import iso_date, text_field
from ai_trade.reference_data import validation
from ai_trade.reference_data.models import (
    ReferenceResult, SecurityAtDate, SecurityDataMissingError, SecurityNotActiveError,
    SecurityPeriod, SecuritySnapshot,
)
from ai_trade.reference_data.repository_support import envelope, insert_row, meta_from_row, write_batch
from ai_trade.storage.db import Database


class SecurityMaster(Protocol):
    def write_many(self, records: Iterable[SecuritySnapshot], *, run_id: str) -> WriteResult: ...

    def get(self, *, instrument_id: str, valid_on: str, as_of: str, mode: str) -> ReferenceResult[SecurityAtDate]: ...

    def resolve(self, *, symbol: str, valid_on: str, as_of: str, mode: str) -> ReferenceResult[SecurityAtDate]: ...


class SQLiteSecurityMaster:
    def __init__(self, database: Database):
        self.database = database

    @staticmethod
    def _insert(conn: sqlite3.Connection, record: SecuritySnapshot, run_id: str) -> None:
        anchor = conn.execute("SELECT symbol FROM instruments WHERE instrument_id=?", (record.instrument_id,)).fetchone()
        if anchor is None:
            conn.execute("INSERT INTO instruments VALUES (?,?)", (record.instrument_id, record.symbol))
        elif anchor["symbol"] != record.symbol:
            raise IntegrityError("stable listing identity already has another symbol; code changes unsupported")
        values = {key: getattr(record, key) for key in (
            "instrument_id", "symbol", "exchange", "security_type", "quality_status", "listing_date", "delisting_date")}
        values.update(asdict(record.provenance), periods_json=json.dumps(
            [asdict(period) for period in record.periods], ensure_ascii=False, separators=(",", ":")), run_id=run_id)
        insert_row(conn, "security_versions", dict(instrument_id=record.instrument_id,
                   record_version=record.provenance.record_version), values)

    def write_many(self, records: Iterable[SecuritySnapshot], *, run_id: str) -> WriteResult:
        return write_batch(self.database, records, run_id, validation.security, self._insert)

    @staticmethod
    def _result(row, valid_on: str, cutoff: str, mode: str) -> ReferenceResult[SecurityAtDate]:
        if row is None:
            raise SecurityDataMissingError("no visible master version; cannot reconstruct from current code lists")
        if valid_on < row["listing_date"] or (row["delisting_date"] is not None and valid_on >= row["delisting_date"]):
            raise SecurityNotActiveError("date is outside the listing lifetime in the visible version")
        periods = tuple(SecurityPeriod(**item) for item in json.loads(row["periods_json"]))
        period = next((period for period in periods if period.effective_from <= valid_on
                       and (period.effective_to is None or valid_on < period.effective_to)), None)
        if period is None:
            raise SecurityDataMissingError("listing lifetime known but effective name period is missing")
        snapshot = SecuritySnapshot(*(row[key] for key in (
            "instrument_id", "symbol", "exchange", "security_type", "listing_date", "delisting_date")),
            periods, meta_from_row(row), quality_status=row["quality_status"])
        return envelope(SecurityAtDate(snapshot, period), [row], cutoff, mode, "security",
                        dict(instrument_id=snapshot.instrument_id, valid_on=valid_on),
                        ("ST/risk history not implemented; unknown is not normal/non-ST",))

    def get(self, *, instrument_id: str, valid_on: str, as_of: str, mode: str) -> ReferenceResult[SecurityAtDate]:
        text_field(instrument_id, "instrument_id")
        iso_date(valid_on, "valid_on")
        cutoff = validation.query(as_of, mode)
        with self.database.connection() as conn:
            row = conn.execute("""SELECT * FROM security_versions WHERE instrument_id=?
                AND available_at<=? AND ingested_at<=?
                ORDER BY max(available_at,ingested_at) DESC LIMIT 1""", (instrument_id, cutoff, cutoff)).fetchone()
        return self._result(row, valid_on, cutoff, mode)

    def resolve(self, *, symbol: str, valid_on: str, as_of: str, mode: str) -> ReferenceResult[SecurityAtDate]:
        if not isinstance(symbol, str) or not re.fullmatch(r"[0-9]{6}\.(SH|SZ|BJ)", symbol):
            raise ValidationError(("symbol: explicit SH/SZ/BJ code required",))
        iso_date(valid_on, "valid_on")
        cutoff = validation.query(as_of, mode)
        with self.database.connection() as conn:
            rows = conn.execute("""WITH visible AS (
                SELECT *,row_number() OVER (PARTITION BY instrument_id ORDER BY max(available_at,ingested_at) DESC) r
                FROM security_versions WHERE symbol=? AND available_at<=? AND ingested_at<=?
            ) SELECT * FROM visible WHERE r=1 AND listing_date<=? AND (delisting_date IS NULL OR ?<delisting_date)""",
                                (symbol, cutoff, cutoff, valid_on, valid_on)).fetchall()
        if len(rows) > 1:
            raise IntegrityError("ambiguous symbol at business date and as_of; no identity selected")
        return self._result(rows[0] if rows else None, valid_on, cutoff, mode)

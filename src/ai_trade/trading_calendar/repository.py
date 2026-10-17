"""Point-in-time calendar queries distinguish closed, missing and source errors."""

import sqlite3
from dataclasses import asdict
from datetime import date, timedelta
from typing import Iterable, Protocol

from ai_trade.data_access.models import ValidationError, WriteResult
from ai_trade.data_access.validation import iso_date
from ai_trade.reference_data import validation
from ai_trade.reference_data.models import (
    CalendarDataMissingError, CalendarDay, CalendarSourceError, NoKnownTradingDayError, ReferenceResult,
)
from ai_trade.reference_data.repository_support import envelope, insert_row, meta_from_row, write_batch
from ai_trade.storage.db import Database


class TradingCalendar(Protocol):
    def write_many(self, records: Iterable[CalendarDay], *, run_id: str) -> WriteResult: ...

    def get_day(self, *, exchange: str, session_date: str, as_of: str, mode: str) -> ReferenceResult[CalendarDay]: ...

    def trading_days(self, *, exchange: str, start: str, end: str, as_of: str,
                     mode: str) -> ReferenceResult[tuple[CalendarDay, ...]]: ...

    def previous_known_trading_day(self, *, exchange: str, before: str, search_start: str,
                                   as_of: str, mode: str) -> ReferenceResult[CalendarDay]: ...


def _day(row: sqlite3.Row) -> CalendarDay:
    flag = row["is_trading_day"]
    return CalendarDay(row["exchange"], row["session_date"], None if flag is None else bool(flag),
                       meta_from_row(row), row["quality_status"], row["error_reason"])


class SQLiteTradingCalendar:
    def __init__(self, database: Database):
        self.database = database

    @staticmethod
    def _insert(conn: sqlite3.Connection, record: CalendarDay, run_id: str) -> None:
        values = dict(exchange=record.exchange, session_date=record.session_date,
                      is_trading_day=record.is_trading_day, quality_status=record.quality_status,
                      error_reason=record.error_reason, **asdict(record.provenance), run_id=run_id)
        insert_row(conn, "calendar_versions", dict(exchange=record.exchange, session_date=record.session_date,
                   record_version=record.provenance.record_version), values)

    def write_many(self, records: Iterable[CalendarDay], *, run_id: str) -> WriteResult:
        return write_batch(self.database, records, run_id, validation.calendar, self._insert)

    def get_day(self, *, exchange: str, session_date: str, as_of: str, mode: str) -> ReferenceResult[CalendarDay]:
        validation.exchange(exchange)
        iso_date(session_date, "session_date")
        cutoff = validation.query(as_of, mode)
        with self.database.connection() as conn:
            row = conn.execute("""SELECT * FROM calendar_versions WHERE exchange=? AND session_date=?
                AND available_at<=? AND ingested_at<=?
                ORDER BY max(available_at,ingested_at) DESC LIMIT 1""", (exchange, session_date, cutoff, cutoff)).fetchone()
        if row is None:
            raise CalendarDataMissingError(f"unknown calendar date: {exchange}/{session_date}")
        record = _day(row)
        if record.quality_status == "source_error":
            raise CalendarSourceError(f"calendar source error: {session_date}: {record.error_reason}")
        return envelope(record, [row], cutoff, mode, "calendar", dict(exchange=exchange, date=session_date))

    def trading_days(self, *, exchange: str, start: str, end: str, as_of: str,
                     mode: str) -> ReferenceResult[tuple[CalendarDay, ...]]:
        validation.exchange(exchange)
        iso_date(start, "start")
        iso_date(end, "end")
        cutoff = validation.query(as_of, mode)
        length = (date.fromisoformat(end) - date.fromisoformat(start)).days + 1
        if not 1 <= length <= 36600:
            raise ValidationError(("range: ordered inclusive range of at most 36600 dates required",))
        with self.database.connection() as conn:
            rows = conn.execute("""WITH visible AS (
                SELECT *,row_number() OVER (PARTITION BY session_date ORDER BY max(available_at,ingested_at) DESC) r
                FROM calendar_versions WHERE exchange=? AND session_date BETWEEN ? AND ?
                    AND available_at<=? AND ingested_at<=?
            ) SELECT * FROM visible WHERE r=1 ORDER BY session_date""", (exchange, start, end, cutoff, cutoff)).fetchall()
        present = {row["session_date"] for row in rows}
        beginning = date.fromisoformat(start)
        missing = tuple((beginning + timedelta(days=i)).isoformat() for i in range(length)
                        if (beginning + timedelta(days=i)).isoformat() not in present)
        errors = tuple(row["session_date"] for row in rows if row["quality_status"] == "source_error")
        if mode != "research":
            if errors:
                raise CalendarSourceError(f"source errors: {errors[:5]}; missing_count={len(missing)}")
            if missing:
                raise CalendarDataMissingError(f"calendar coverage missing: {missing[:5]}; count={len(missing)}")
        days = tuple(_day(row) for row in rows if row["quality_status"] == "accepted" and row["is_trading_day"])
        return envelope(days, rows, cutoff, mode, "calendar", dict(exchange=exchange, start=start, end=end),
                        missing=missing, errors=errors)

    def previous_known_trading_day(self, *, exchange: str, before: str, search_start: str,
                                   as_of: str, mode: str) -> ReferenceResult[CalendarDay]:
        iso_date(before, "before")
        iso_date(search_start, "search_start")
        if search_start >= before:
            raise ValidationError(("search_start: must precede exclusive before date",))
        end = (date.fromisoformat(before) - timedelta(days=1)).isoformat()
        result = self.trading_days(exchange=exchange, start=search_start, end=end, as_of=as_of, mode=mode)
        if not result.value:
            if result.source_error_dates:
                raise CalendarSourceError(f"no usable open day; source errors: {result.source_error_dates[:5]}")
            if result.missing_dates:
                raise CalendarDataMissingError(f"no known open day; missing dates: {result.missing_dates[:5]}")
            raise NoKnownTradingDayError("no known open day within explicit search interval; not proof of universal closure")
        return ReferenceResult(result.value[-1], result.as_of, result.mode, result.data_snapshot_id,
                               result.definitions_version, result.warnings, result.lineage_refs,
                               result.missing_dates, result.source_error_dates)

"""A minimal daily-bar port and its SQLite implementation.

This is not the complete multi-dataset DataAccess or a snapshot service.
Business consumers receive domain records, never sqlite3.Row objects.
"""

import hashlib
import json
import sqlite3
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Iterable, Protocol

from ai_trade.data_access.models import (
    DailyBar, DataUnavailableError, DuplicateRecordError, IntegrityError,
    ReadResult, ValidationError, WriteResult,
)
from ai_trade.data_access.validation import (
    ADJUSTMENTS, MODES, iso_date, text_field, timestamp, validate_bar,
)
from ai_trade.storage.db import Database


class MarketDataRepository(Protocol):
    """Portable boundary for daily observations and explicit point-in-time reads."""

    def write_many(self, bars: Iterable[DailyBar], *, run_id: str) -> WriteResult: ...

    def get_bar(self, *, instrument_id: str, trade_date: str, source: str,
                adjustment_method: str, as_of: str, mode: str) -> ReadResult: ...


class SQLiteMarketDataRepository:
    """Append-only storage with atomic batches and explicit revision chains."""

    def __init__(self, database: Database):
        self.database = database

    def write_many(self, bars: Iterable[DailyBar], *, run_id: str) -> WriteResult:
        """Reject all duplicates, including identical retries, without overwriting.

        The caller provides timestamps and provenance, not fabricated defaults.
        A failed batch leaves no run, instrument, bar or version behind.
        """
        text_field(run_id, "run_id")
        try:
            with self.database.transaction() as conn:
                if conn.execute("SELECT 1 FROM ingestion_runs WHERE run_id=?", (run_id,)).fetchone():
                    raise DuplicateRecordError(f"run_id already exists: {run_id}")
                conn.execute("INSERT INTO ingestion_runs VALUES (?, ?)", (
                    run_id, datetime.now(timezone.utc).isoformat(timespec="microseconds")))
                count = 0
                for index, raw in enumerate(bars):
                    try:
                        bar = validate_bar(raw)
                    except ValidationError as exc:
                        raise ValidationError(tuple(f"records[{index}].{issue}" for issue in exc.issues)) from exc
                    identity = conn.execute(
                        "SELECT symbol FROM instruments WHERE instrument_id=?", (bar.instrument_id,)
                    ).fetchone()
                    if identity is None:
                        conn.execute("INSERT INTO instruments VALUES (?, ?)", (bar.instrument_id, bar.symbol))
                    elif identity["symbol"] != bar.symbol:
                        raise IntegrityError(f"instrument_id has a different symbol: {bar.instrument_id}")
                    conn.execute("""INSERT INTO daily_bars (instrument_id, trade_date, adjustment_method)
                        VALUES (?, ?, ?) ON CONFLICT (instrument_id, trade_date, adjustment_method) DO NOTHING""",
                        (bar.instrument_id, bar.trade_date, bar.adjustment_method))
                    bar_id = conn.execute("""SELECT bar_id FROM daily_bars
                        WHERE instrument_id=? AND trade_date=? AND adjustment_method=?""",
                        (bar.instrument_id, bar.trade_date, bar.adjustment_method)).fetchone()[0]
                    if conn.execute("""SELECT 1 FROM daily_bar_versions
                            WHERE bar_id=? AND source=? AND source_version=?""",
                            (bar_id, bar.source, bar.source_version)).fetchone():
                        raise DuplicateRecordError(
                            f"records[{index}]: duplicate {bar.symbol}/{bar.trade_date}/"
                            f"{bar.adjustment_method}/{bar.source}/{bar.source_version}")
                    conn.execute("""INSERT INTO daily_bar_versions (
                        bar_id, source, source_version, open, high, low, close, volume, amount,
                        event_time, available_at, ingested_at, factor_version, quality_status,
                        supersedes_version, run_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""", (
                        bar_id, bar.source, bar.source_version, bar.open, bar.high, bar.low, bar.close,
                        bar.volume, bar.amount, bar.event_time, bar.available_at, bar.ingested_at,
                        bar.factor_version, bar.quality_status, bar.supersedes_version, run_id,
                    ))
                    count += 1
                if not count:
                    raise ValidationError(("records: batch cannot be empty",))
        except sqlite3.IntegrityError as exc:
            raise IntegrityError(f"batch rejected; no records committed: {exc}") from exc
        return WriteResult(run_id, count)

    def get_bar(self, *, instrument_id: str, trade_date: str, source: str,
                adjustment_method: str, as_of: str, mode: str) -> ReadResult:
        """Read one explicit source, never merge sources or backfill revisions.

        All modes enforce both availability and ingestion cutoffs. Research can
        expose structurally valid quarantined records with a warning. A newer
        visible quarantine blocks strict reads instead of reviving an older bar.
        """
        text_field(instrument_id, "instrument_id")
        text_field(source, "source")
        iso_date(trade_date)
        cutoff = timestamp(as_of, "as_of")
        if not isinstance(mode, str) or mode not in MODES:
            raise ValidationError(("mode: expected research, strict_backtest or paper_trade",))
        if not isinstance(adjustment_method, str) or adjustment_method not in ADJUSTMENTS:
            raise ValidationError(("adjustment_method: expected none, qfq or hfq",))
        with self.database.connection() as conn:
            row = conn.execute("""SELECT b.instrument_id, i.symbol, b.trade_date,
                    b.adjustment_method, v.* FROM daily_bars b
                JOIN instruments i ON i.instrument_id=b.instrument_id
                JOIN daily_bar_versions v ON v.bar_id=b.bar_id
                WHERE b.instrument_id=? AND b.trade_date=? AND b.adjustment_method=?
                    AND v.source=? AND v.available_at<=? AND v.ingested_at<=?
                ORDER BY max(v.available_at, v.ingested_at) DESC LIMIT 1""",
                (instrument_id, trade_date, adjustment_method, source, cutoff, cutoff)).fetchone()
        if row is None:
            raise DataUnavailableError("no visible daily bar for the explicit source and as_of")
        if mode != "research" and row["quality_status"] != "accepted":
            raise DataUnavailableError("latest visible version is quarantined")
        bar = DailyBar(**{name: row[name] for name in DailyBar.__dataclass_fields__})
        warnings: list[str] = []
        if mode == "research":
            warnings.append("research mode: not an audited backtest result")
        if bar.quality_status != "accepted":
            warnings.append("quarantined: not eligible for strict use")
        if bar.ingested_at > bar.available_at:
            warnings.append("ingestion delay: visibility constrained by ingested_at")
        digest = hashlib.sha256(json.dumps(asdict(bar), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return ReadResult(bar, cutoff, mode, f"observation:sha256:{digest}", "task-002-v1",
                          tuple(warnings), (f"run:{row['run_id']}", f"daily_bar_version:{row['version_id']}"))

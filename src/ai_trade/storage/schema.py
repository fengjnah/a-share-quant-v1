"""Ordered, append-only schema migrations executed inside a single transaction."""

import hashlib
import json
from dataclasses import dataclass

from ai_trade.storage.reference_schema import reference_statements


@dataclass(frozen=True)
class Migration:
    """Released migrations are immutable; changes require a new version."""

    version: int
    name: str
    statements: tuple[str, ...]

    @property
    def checksum(self) -> str:
        return hashlib.sha256(json.dumps(
            (self.version, self.name, self.statements), ensure_ascii=True
        ).encode()).hexdigest()


LEDGER_SQL = """
CREATE TABLE schema_migrations (
    version INTEGER PRIMARY KEY CHECK (version > 0),
    name TEXT NOT NULL,
    checksum TEXT NOT NULL,
    applied_at TEXT NOT NULL
)
"""

_IDENTITY = (
    """CREATE TABLE instruments (
        instrument_id TEXT PRIMARY KEY NOT NULL CHECK (length(trim(instrument_id)) > 0),
        symbol TEXT NOT NULL CHECK (
            length(symbol) = 9 AND substr(symbol, 1, 6) NOT GLOB '*[^0-9]*'
            AND substr(symbol, 7) IN ('.SH', '.SZ', '.BJ')),
        UNIQUE (instrument_id, symbol)
    )""",
    """CREATE TABLE ingestion_runs (
        run_id TEXT PRIMARY KEY NOT NULL CHECK (length(trim(run_id)) > 0),
        recorded_at TEXT NOT NULL
    )""",
    """CREATE TABLE daily_bars (
        bar_id INTEGER PRIMARY KEY,
        instrument_id TEXT NOT NULL REFERENCES instruments(instrument_id),
        trade_date TEXT NOT NULL CHECK (
            trade_date GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
            AND date(trade_date, '+0 days') IS NOT NULL
            AND date(trade_date, '+0 days') = trade_date),
        adjustment_method TEXT NOT NULL CHECK (adjustment_method IN ('none', 'qfq', 'hfq')),
        UNIQUE (instrument_id, trade_date, adjustment_method)
    )""",
)

_TIME_CHECK = """CHECK (
    length({field}) = 32 AND substr({field}, 11, 1) = 'T'
    AND substr({field}, 20, 1) = '.' AND substr({field}, 27) = '+00:00'
    AND julianday({field}) IS NOT NULL
)"""

_VERSIONS = (
    """CREATE TABLE daily_bar_versions (
        version_id INTEGER PRIMARY KEY,
        bar_id INTEGER NOT NULL REFERENCES daily_bars(bar_id),
        source TEXT NOT NULL CHECK (length(trim(source)) > 0 AND source GLOB '*:*:*'),
        source_version TEXT NOT NULL CHECK (length(trim(source_version)) > 0),
        open REAL NOT NULL CHECK (typeof(open) IN ('real','integer') AND open > 0 AND open <= 1.7976931348623157e308),
        high REAL NOT NULL CHECK (typeof(high) IN ('real','integer') AND high > 0 AND high <= 1.7976931348623157e308),
        low REAL NOT NULL CHECK (typeof(low) IN ('real','integer') AND low > 0 AND low <= 1.7976931348623157e308),
        close REAL NOT NULL CHECK (typeof(close) IN ('real','integer') AND close > 0 AND close <= 1.7976931348623157e308),
        volume INTEGER NOT NULL CHECK (typeof(volume) = 'integer' AND volume >= 0),
        amount REAL NOT NULL CHECK (typeof(amount) IN ('real','integer') AND amount >= 0 AND amount <= 1.7976931348623157e308),
        event_time TEXT NOT NULL {event_check},
        available_at TEXT NOT NULL {available_check},
        ingested_at TEXT NOT NULL {ingested_check},
        factor_version TEXT CHECK (factor_version IS NULL OR length(trim(factor_version)) > 0),
        quality_status TEXT NOT NULL CHECK (quality_status IN ('accepted','quarantined')),
        supersedes_version TEXT,
        run_id TEXT NOT NULL REFERENCES ingestion_runs(run_id),
        CHECK (low <= open AND open <= high AND low <= close AND close <= high),
        CHECK (event_time <= available_at AND event_time <= ingested_at),
        CHECK (supersedes_version IS NULL OR supersedes_version <> source_version),
        UNIQUE (bar_id, source, source_version),
        UNIQUE (bar_id, source, supersedes_version),
        FOREIGN KEY (bar_id, source, supersedes_version)
            REFERENCES daily_bar_versions(bar_id, source, source_version)
    )""".format(
        event_check=_TIME_CHECK.format(field="event_time"),
        available_check=_TIME_CHECK.format(field="available_at"),
        ingested_check=_TIME_CHECK.format(field="ingested_at"),
    ),
    """CREATE UNIQUE INDEX idx_one_version_root
        ON daily_bar_versions(bar_id, source) WHERE supersedes_version IS NULL""",
    """CREATE INDEX idx_bar_visibility
        ON daily_bar_versions(bar_id, source, available_at, ingested_at)""",
    "CREATE INDEX idx_version_run ON daily_bar_versions(run_id)",
    "CREATE INDEX idx_bars_date ON daily_bars(trade_date, instrument_id)",
    "CREATE INDEX idx_instruments_symbol ON instruments(symbol)",
    """CREATE TRIGGER validate_bar_version BEFORE INSERT ON daily_bar_versions
        BEGIN
            SELECT CASE WHEN (
                SELECT adjustment_method FROM daily_bars WHERE bar_id = NEW.bar_id
            ) = 'none' AND NEW.factor_version IS NOT NULL
                THEN RAISE(ABORT, 'unadjusted bar cannot have factor_version') END;
            SELECT CASE WHEN (
                SELECT adjustment_method FROM daily_bars WHERE bar_id = NEW.bar_id
            ) IN ('qfq','hfq') AND NEW.factor_version IS NULL
                THEN RAISE(ABORT, 'adjusted bar requires factor_version') END;
            SELECT CASE WHEN NEW.supersedes_version IS NOT NULL AND EXISTS (
                SELECT 1 FROM daily_bar_versions p
                WHERE p.bar_id = NEW.bar_id AND p.source = NEW.source
                    AND p.source_version = NEW.supersedes_version
                    AND (NEW.available_at < p.available_at OR NEW.ingested_at < p.ingested_at
                        OR max(NEW.available_at, NEW.ingested_at) <= max(p.available_at, p.ingested_at))
            ) THEN RAISE(ABORT, 'revision visibility must advance without backdating') END;
        END""",
)

_APPEND_ONLY = tuple(
    f"""CREATE TRIGGER immutable_{table}_{operation.lower()}
        BEFORE {operation} ON {table}
        BEGIN SELECT RAISE(ABORT, 'audit records are append-only'); END"""
    for table in ("instruments", "ingestion_runs", "daily_bars", "daily_bar_versions")
    for operation in ("UPDATE", "DELETE")
)

MIGRATIONS = (
    Migration(1, "daily_bar_foundation", _IDENTITY + _VERSIONS + _APPEND_ONLY),
    Migration(2, "security_master_and_calendar", reference_statements(_TIME_CHECK)),
)

"""Portable domain records and explicit data-layer failures."""

from dataclasses import dataclass


class ValidationError(ValueError):
    """One or more fields violate the data contract."""

    def __init__(self, issues: tuple[str, ...]):
        self.issues = issues
        super().__init__("; ".join(issues))


class IntegrityError(RuntimeError):
    """A version, identity or migration conflicts with existing facts."""


class DuplicateRecordError(IntegrityError):
    """An existing run or source version was submitted again."""


class DataUnavailableError(LookupError):
    """No accepted observation is visible at the requested as_of."""


@dataclass(frozen=True)
class DailyBar:
    """Complete daily observation; dates/times must be explicit ISO strings.

    Prices/amount are CNY; volume is an integer number of shares.
    instrument_id identifies a listing entity independently of its symbol.
    """

    instrument_id: str
    symbol: str
    trade_date: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    amount: float
    source: str
    source_version: str
    event_time: str
    available_at: str
    ingested_at: str
    adjustment_method: str
    factor_version: str | None = None
    quality_status: str = "accepted"
    supersedes_version: str | None = None


@dataclass(frozen=True)
class WriteResult:
    """A batch commits all records or raises, with no silent skip policy."""

    run_id: str
    inserted: int


@dataclass(frozen=True)
class ReadResult:
    """A selected version and metadata, without exposing SQLite row objects.

    data_snapshot_id is a content digest of this observation, not a complete
    database snapshot. TASK-002 does not implement named historical snapshots.
    """

    bar: DailyBar
    as_of: str
    mode: str
    data_snapshot_id: str
    definitions_version: str
    warnings: tuple[str, ...]
    lineage_refs: tuple[str, ...]

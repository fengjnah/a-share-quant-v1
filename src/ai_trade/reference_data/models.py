"""Business-effective dates are separate from observation/visibility timestamps."""

from dataclasses import dataclass
from typing import Generic, TypeVar

from ai_trade.data_access.models import DataUnavailableError


@dataclass(frozen=True)
class Provenance:
    source: str
    record_version: str
    event_time: str
    available_at: str
    observed_at: str
    ingested_at: str
    evidence_kind: str
    evidence_ref: str
    supersedes_version: str | None = None
    revision_reason: str | None = None


@dataclass(frozen=True)
class SecurityPeriod:
    """Known name validity [effective_from, effective_to); gaps mean unknown."""

    effective_from: str
    effective_to: str | None
    name: str


@dataclass(frozen=True)
class SecuritySnapshot:
    """One complete known timeline version for a stable listing entity.

    Delisting date is the first date no longer listed (exclusive lifetime end).
    Code changes for the same entity are not supported by the existing ID anchor.
    ST/risk history is not implemented and cannot be inferred from names.
    """

    instrument_id: str
    symbol: str
    exchange: str
    security_type: str
    listing_date: str
    delisting_date: str | None
    periods: tuple[SecurityPeriod, ...]
    provenance: Provenance
    quality_status: str = "accepted"


@dataclass(frozen=True)
class SecurityAtDate:
    snapshot: SecuritySnapshot
    period: SecurityPeriod
    risk_status: None = None


@dataclass(frozen=True)
class CalendarDay:
    exchange: str
    session_date: str
    is_trading_day: bool | None
    provenance: Provenance
    quality_status: str = "accepted"
    error_reason: str | None = None


T = TypeVar("T")


@dataclass(frozen=True)
class ReferenceResult(Generic[T]):
    value: T
    as_of: str
    mode: str
    data_snapshot_id: str
    definitions_version: str
    warnings: tuple[str, ...]
    lineage_refs: tuple[str, ...]
    missing_dates: tuple[str, ...] = ()
    source_error_dates: tuple[str, ...] = ()

    @property
    def complete(self) -> bool:
        """No missing/error dates in this query; not full history/source certification."""
        return not self.missing_dates and not self.source_error_dates


class SecurityDataMissingError(DataUnavailableError):
    """No visible master version, or no known effective period."""


class SecurityNotActiveError(DataUnavailableError):
    """The visible version explicitly places the date outside listing lifetime."""


class CalendarDataMissingError(DataUnavailableError):
    """No visible calendar observation; never interpreted as a closed market."""


class CalendarSourceError(DataUnavailableError):
    """A visible explicit source-error version blocks use of a calendar fact."""


class NoKnownTradingDayError(DataUnavailableError):
    """No known open day within the explicit bounded search interval."""

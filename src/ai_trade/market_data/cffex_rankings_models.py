"""Domain records and request boundary for CFFEX index-futures member holdings.

TASK-022A. This module defines the *published* ranking fact and its
vendor-independent request/result envelope. It deliberately mirrors the
evidence/time semantics of the daily-bar pipeline (source_version, run_id,
available_at, ingested_at, payload_hash) so the same evidence and future-
function rules apply to holdings as to price data.

Semantics that MUST NOT be violated (see TASK-022 review, section G):
  * A member absent from the Top-N of one side is UNKNOWN, not zero OI.
  * ``member_scope`` is one of {代客, 自营, 代客+自营, unknown}. Published names
    carry a category suffix; we preserve it and never merge unknown with known.
  * ``available_at`` requires a visible CFFEX calendar and session window; absent
    knowledge blocks record construction. Publication time may remain unknown.
  * ``net`` is a derived proxy (evidence_grade B), never a final-client fact.
"""

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
import re
from typing import Optional, Protocol

from ai_trade.data_access.models import DataUnavailableError


class CffexRankingsError(RuntimeError):
    """Base class for ranking-specific failures that must not be conflated with
    a successful, complete ingestion."""


class RankFormatError(CffexRankingsError):
    """The CSV did not match the reviewed named (>=2020) or legacy (<2020) layout."""


class RankingResponseError(CffexRankingsError):
    """The endpoint returned a non-CSV fallback (home page, error page, 404 body)."""

    def __init__(self, message: str, *, code: str = 'response_error', http_status: int | None = None):
        super().__init__(message)
        self.code = code
        self.http_status = http_status


class RankingTransportError(CffexRankingsError):
    """Network failure, distinct from an HTTP response or empty data."""


class RankingCalendarError(DataUnavailableError, CffexRankingsError):
    """CFFEX session knowledge is absent, erroneous or not visible at the cutoff."""


class RankingVersionError(CffexRankingsError):
    """Ambiguous, incomplete or conflicting caller-supplied revision history."""


class RankingDataUnavailableError(DataUnavailableError, CffexRankingsError):
    """No ranking version is visible at this as_of."""


class RankingValidationError(CffexRankingsError):
    """Field-level contract violation (bad date, missing rank, non-numeric OI...)."""


class MemberScope(str, Enum):
    """How the published member name was categorised. ``unknown`` means the suffix
    was missing or unrecognised and must not be merged into a known scope."""

    AGENT = "代客"
    PROPRIO = "自营"
    AGENT_AND_PROPRIO = "代客+自营"
    UNKNOWN = "unknown"


class RankingSide(str, Enum):
    LONG = "long"
    SHORT = "short"
    VOLUME = "volume"


RANK_SIDES = (RankingSide.LONG, RankingSide.SHORT, RankingSide.VOLUME)


@dataclass(frozen=True)
class CffexRankingsRequest:
    """One variety, one trade date, fetched as a single reviewable unit.

    ``trade_date`` is the *trade session* the file describes; the URL is keyed
    by its calendar month/day. A missing file is ambiguous unless independent
    CFFEX calendar evidence explicitly establishes a closed session.
    """

    exchange: str  # always "CFFEX" for this adapter
    variety: str  # one of IF, IH, IC, IM
    trade_date: str  # YYYY-MM-DD

    def validate(self) -> None:
        if self.exchange != 'CFFEX' or self.variety not in ('IF', 'IH', 'IC', 'IM'):
            raise RankingValidationError('request: explicit CFFEX and IF/IH/IC/IM required')
        if not isinstance(self.trade_date, str) or not re.fullmatch(r'[0-9]{4}-[0-9]{2}-[0-9]{2}', self.trade_date):
            raise RankingValidationError('trade_date: expected YYYY-MM-DD')
        try:
            date.fromisoformat(self.trade_date)
        except ValueError as exc:
            raise RankingValidationError('trade_date: invalid date') from exc

    def url(self) -> str:
        self.validate()
        basic = self.trade_date.replace("-", "")
        return (f"https://www.cffex.com.cn/sj/ccpm/{basic[:6]}/{basic[6:]}/"
                f"{self.variety}_1.csv")


@dataclass(frozen=True)
class RankingRow:
    """One published ranking fact for a member on one side of one contract.

    ``*_known`` flags make UNKNOWN explicit: when a member is not in the Top-N
    list for that side, the OI/``change`` fields are ``None`` and the flag is
    False. Consumers must not coalesce ``None`` to 0.
    """

    contract: str
    rank: int
    side: RankingSide
    member: str  # published short name, e.g. "中信期货(代客)"
    member_scope: MemberScope
    open_interest: Optional[int]  # None => not in top-N for this side
    open_interest_change: Optional[int]
    open_interest_known: bool
    rank_format: str  # "named" or "legacy"
    volume: Optional[int] = None
    volume_change: Optional[int] = None


@dataclass(frozen=True)
class CffexRankingsRecord:
    """A complete, parseable ranking file plus its provenance and time fences."""

    exchange: str
    variety: str
    trade_date: str
    contracts: tuple[str, ...]
    rows: tuple[RankingRow, ...]
    source: str
    source_version: str  # payload sha256
    payload_sha256: str
    run_id: str
    event_time: str
    available_at: str
    ingested_at: str
    rank_format: str  # "named" | "legacy" | "mixed"
    warnings: tuple[str, ...] = field(default_factory=tuple)
    observed_at: str = ''
    publication_time: Optional[str] = None
    earliest_session_date: str = ''
    calendar_refs: tuple[str, ...] = field(default_factory=tuple)
    evidence_kind: str = 'source_observation'
    supersedes_version: Optional[str] = None
    revision_reason: Optional[str] = None


@dataclass(frozen=True)
class IngestionOutcome:
    """Explicit result of one fetch; a non-success outcome carries no record.

    duplicate_payload compares an explicit prior record only; no durable registry
    exists. unavailable does not claim a holiday or a publication delay.
    """

    status: str  # one of: success, no_session, unpublished, network_error,
                 # response_error, schema_error, validation_error
    record: Optional[CffexRankingsRecord]
    issues: tuple[str, ...]
    http_status: Optional[int] = None


@dataclass(frozen=True)
class RankingSessionDay:
    """Injected CFFEX knowledge, never synthesized from weekday or SH calendar.

    Dates marked closed have no session times. Metadata is an explicit caller
    declaration, not automatic certification of historical coverage or permission.
    """

    exchange: str
    session_date: str
    is_trading_day: bool
    opens_at: Optional[str]
    closes_at: Optional[str]
    available_at: str
    ingested_at: str
    source: str
    evidence_ref: str
    evidence_kind: str = 'source_observation'


class RankingCalendar(Protocol):
    def get_day(self, *, exchange: str, session_date: str, as_of: str) -> RankingSessionDay: ...

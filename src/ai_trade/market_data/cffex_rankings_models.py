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
  * ``available_at`` is conservative: when the publication timestamp is unknown,
    it equals the observed/ingested time, and the record is only usable from the
    NEXT session (no same-day intraday use).
  * ``net`` is a derived proxy (evidence_grade B), never a final-client fact.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class CffexRankingsError(RuntimeError):
    """Base class for ranking-specific failures that must not be conflated with
    a successful, complete ingestion."""


class RankFormatError(CffexRankingsError):
    """The CSV did not match the reviewed named (>=2020) or legacy (<2020) layout."""


class RankingResponseError(CffexRankingsError):
    """The endpoint returned a non-CSV fallback (home page, error page, 404 body)."""


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
    by its calendar month/day, so ``2026-10-17`` (a non-trading Saturday) is a
    legitimate request that must resolve to an explicit "no session" outcome,
    never to a fabricated row.
    """

    exchange: str  # always "CFFEX" for this adapter
    variety: str  # one of IF, IH, IC, IM
    trade_date: str  # YYYY-MM-DD

    def url(self) -> str:
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
    rank_format: str  # "named" | "legacy"
    warnings: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class IngestionOutcome:
    """Explicit result of one fetch; a non-SUCCESS outcome carries no records."""

    status: str  # one of: success, no_session, unpublished, network_error,
                 # response_error, schema_error, validation_error
    record: Optional[CffexRankingsRecord]
    issues: tuple[str, ...]

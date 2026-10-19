"""M3 core v1: evidence declarations, diagnostics and fail-closed admission.

Verification receipts are supplied by an audited caller; a dataclass is not a
source verifier. Synthetic fixtures never certify a real source. No DB writes.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import json
import math
import re
from typing import Any

from ai_trade.data_access.validation import iso_date, timestamp

CONTRACT_VERSION = "m3-core-diagnostic-v1"
CALCULATION_VERSION = "m3-core-rules-v1"


class Verification(str, Enum):
    UNKNOWN = "UNKNOWN"
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    UNAVAILABLE = "UNAVAILABLE"


class Admission(str, Enum):
    BLOCKED = "BLOCKED"
    L1 = "L1_OBSERVATION"
    L2 = "L2_RESEARCH"
    L3 = "L3_STRATEGY"


class Status(str, Enum):
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    HISTORY_INSUFFICIENT = "HISTORY_INSUFFICIENT"
    FACTOR_MISSING = "FACTOR_MISSING"
    STALE = "STALE"
    TIME_UNCERTIFIED = "TIME_UNCERTIFIED"
    INVALID_DATA = "INVALID_DATA"
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"
    OBSERVATION_ONLY = "OBSERVATION_ONLY"
    RESEARCH_ALLOWED = "RESEARCH_ALLOWED"
    STRATEGY_ALLOWED = "STRATEGY_ALLOWED"
    BLOCKED = "BLOCKED"


class ReasonCode(str, Enum):
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    SOURCE_UNVERIFIED = "SOURCE_UNVERIFIED"
    AUTHORIZATION_UNKNOWN = "AUTHORIZATION_UNKNOWN"
    HISTORY_INSUFFICIENT = "HISTORY_INSUFFICIENT"
    FACTOR_MISSING = "FACTOR_MISSING"
    STALE = "STALE"
    TIME_UNCERTIFIED = "TIME_UNCERTIFIED"
    NOT_VISIBLE = "NOT_VISIBLE_AT_AS_OF"
    INVALID_DATA = "INVALID_DATA"
    CALENDAR_UNKNOWN = "CALENDAR_UNKNOWN"
    COVERAGE_INCOMPLETE = "COVERAGE_INCOMPLETE"
    UNIVERSE_UNKNOWN = "UNIVERSE_UNKNOWN"
    SCOPE_UNSUPPORTED = "SCOPE_UNSUPPORTED"
    PUBLICATION_UNKNOWN = "PUBLICATION_UNKNOWN"
    SYNTHETIC = "SYNTHETIC_NOT_SOURCE_ACCEPTANCE"
    EVIDENCE_CONFLICT = "EVIDENCE_CONFLICT"
    EVIDENCE_MISSING = "EVIDENCE_MISSING"
    SNAPSHOT_MISMATCH = "SNAPSHOT_MISMATCH"
    STRATEGY_GATE = "STRATEGY_EVIDENCE_REQUIRED"


@dataclass(frozen=True)
class Receipt:
    status: Verification = Verification.UNKNOWN
    refs: tuple[str, ...] = ()

    def __post_init__(self):
        if not isinstance(self.status, Verification) or not isinstance(self.refs, tuple) or any(
                not isinstance(r, str) or not r.strip() for r in self.refs):
            raise ValueError("Explicit verification enum and nonempty reference strings required")

    @property
    def verified(self) -> bool:
        return self.status is Verification.VERIFIED and bool(self.refs) and all(bool(r.strip()) for r in self.refs)


@dataclass(frozen=True)
class SourceEvidence:
    source: str
    source_version: str
    lineage_refs: tuple[str, ...]
    verification: Receipt = field(default_factory=Receipt)
    research_authorization: Receipt = field(default_factory=Receipt)
    time_verification: Receipt = field(default_factory=Receipt)
    evidence_kind: str = "source_observation"
    latest_source_date: str | None = None
    endpoint: str | None = None

    def __post_init__(self):
        if (not isinstance(self.source, str) or not self.source.strip()
                or not isinstance(self.source_version, str) or not self.source_version.strip()
                or not self.lineage_refs or any(not isinstance(r, str) or not r.strip() for r in self.lineage_refs)):
            raise ValueError("Explicit source, version and lineage are required even for L1")
        if self.evidence_kind not in {"source_observation", "synthetic"}:
            raise ValueError("Unknown evidence kind")
        if self.latest_source_date is not None:
            iso_date(self.latest_source_date)


@dataclass(frozen=True)
class CalendarEvidence:
    """Complete dated query result, not a list inferred from price observations."""
    market: str
    start: str
    end: str
    sessions: tuple[str, ...]
    available_at: str | None = None
    ingested_at: str | None = None
    receipt: Receipt = field(default_factory=Receipt)

    def __post_init__(self):
        iso_date(self.start); iso_date(self.end)
        if self.start > self.end or tuple(sorted(set(self.sessions))) != self.sessions:
            raise ValueError("Calendar range or unique ordered sessions invalid")
        for day in self.sessions:
            iso_date(day)
            if not self.start <= day <= self.end:
                raise ValueError("Calendar session outside declared query range")


@dataclass(frozen=True)
class Request:
    analysis_date: str
    as_of: str
    symbol: str
    instrument_type: str = "INDEX"
    mode: str = "research"

    def __post_init__(self):
        iso_date(self.analysis_date)
        cutoff = timestamp(self.as_of, "as_of")
        object.__setattr__(self, "as_of", cutoff)
        if not self.symbol.strip() or self.instrument_type not in {"INDEX", "STOCK", "CFFEX", "ALL_A"}:
            raise ValueError("Explicit identity and supported instrument type required")
        if self.mode not in {"research", "strict_backtest", "paper_trade"}:
            raise ValueError("Explicit supported mode required")
        # Future analysis dates cannot be used to label an already observed fact.
        import pandas as pd
        if self.analysis_date > pd.Timestamp(cutoff).tz_convert("Asia/Shanghai").date().isoformat():
            raise ValueError("analysis_date is after as_of")


@dataclass(frozen=True)
class Coverage:
    valid_samples: int
    expected_samples: int | None
    denominator: str
    denominator_refs: tuple[str, ...] = ()
    missing_dates: tuple[str, ...] = ()

    def __post_init__(self):
        if type(self.valid_samples) is not int or self.valid_samples < 0:
            raise ValueError("Valid sample count must be a nonnegative integer")
        if self.expected_samples is not None and (type(self.expected_samples) is not int or self.expected_samples < self.valid_samples):
            raise ValueError("Coverage denominator cannot be less than numerator")
        if self.expected_samples is not None and not self.denominator_refs:
            raise ValueError("A known coverage denominator requires evidence")

    @property
    def ratio(self) -> float | None:
        return self.valid_samples / self.expected_samples if self.expected_samples else None


@dataclass(frozen=True)
class Reason:
    code: ReasonCode
    detail: str
    next_action: str
    blocks: tuple[str, ...] = ("L2", "L3")


@dataclass(frozen=True)
class Diagnostic:
    indicator: str
    request: Request
    source: SourceEvidence
    data_latest_date: str | None
    times: dict[str, str | None]
    coverage: Coverage
    values: dict[str, Any]
    calculated: bool
    admission: Admission
    status: Status
    reasons: tuple[Reason, ...]
    missing_fields: tuple[str, ...] = ()
    definitions_version: str = CALCULATION_VERSION
    schema_version: str = CONTRACT_VERSION

    @property
    def data_snapshot_id(self) -> str:
        payload = [self.indicator, asdict(self.request), asdict(self.source), self.times,
                   asdict(self.coverage), clean(self.values), self.definitions_version]
        return hashlib.sha256(json.dumps(payload, sort_keys=True, allow_nan=False).encode()).hexdigest()

    def to_dict(self) -> dict:
        result = clean(asdict(self))
        result["data_snapshot_id"] = self.data_snapshot_id
        result["coverage"]["ratio"] = self.coverage.ratio
        result["time_verification"] = clean(asdict(self.source.time_verification))
        result["allowed_uses"] = {
            "observation": self.admission is not Admission.BLOCKED,
            "research": self.admission in {Admission.L2, Admission.L3},
            "strategy": self.admission is Admission.L3,
            "live_trading": False,
        }
        return result


def clean(value):
    """JSON null is UNKNOWN; a true numeric zero survives unchanged."""
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(k): clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if hasattr(value, "item"):
        return clean(value.item())
    return value


def strategy_admission(result: Diagnostic, *, implementation_sha: str,
                       review: dict | None = None) -> dict:
    """No upgrade from a boolean. Require a complete matching review receipt.

    This validates receipt consistency, not the identity/authority of its issuer.
    The deployment/research orchestrator must supply independently approved evidence.
    The result never grants live trading permission and never mutates the diagnostic.
    """
    required = {"implementation_sha", "rules_version", "data_snapshot_id", "independent_h_review_ref",
                "approved_at", "execution_constraints_ref", "out_of_sample_validation_ref"}
    ok = (result.admission in {Admission.L2, Admission.L3} and re.fullmatch(r"[0-9a-f]{40}", implementation_sha or "")
          and isinstance(review, dict) and required.issubset(review)
          and all(isinstance(review[k], str) and bool(review[k].strip()) for k in required))
    if ok:
        try:
            ok = (review["implementation_sha"] == implementation_sha
                  and review["rules_version"] == result.definitions_version
                  and review["data_snapshot_id"] == result.data_snapshot_id
                  and timestamp(review["approved_at"], "review.approved_at") <= result.request.as_of)
        except ValueError:
            ok = False
    fallback = Admission.L2 if result.admission is Admission.L3 else result.admission
    return {"admission": Admission.L3.value if ok else fallback.value,
            "strategy_allowed": bool(ok), "live_trading": False,
            "blocking_reasons": [] if ok else [ReasonCode.STRATEGY_GATE.value]}

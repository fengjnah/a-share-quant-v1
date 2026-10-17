"""Vendor-independent ingestion requests, outcomes and writer boundary."""

from dataclasses import dataclass
from enum import Enum
from typing import Iterable, Protocol

from ai_trade.data_access.models import DailyBar, WriteResult


@dataclass(frozen=True)
class DailyHistoryRequest:
    """An explicit, single-instrument historical daily request; no default adjustment."""

    instrument_id: str
    symbol: str
    start_date: str
    end_date: str
    adjustment_method: str


class IngestionStatus(str, Enum):
    SUCCESS = "success"
    EMPTY_RESPONSE = "empty_response"
    NETWORK_ERROR = "network_error"
    RATE_LIMITED = "rate_limited"
    RESPONSE_ERROR = "response_error"
    SCHEMA_ERROR = "schema_error"
    VALIDATION_ERROR = "validation_error"
    DUPLICATE = "duplicate"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class IngestionResult:
    """Success means the complete returned batch committed, not full date coverage."""

    run_id: str
    status: IngestionStatus
    source: str
    started_at: str
    observed_at: str | None
    validated_at: str | None
    completed_at: str
    evidence_directory: str
    response_sha256: str | None
    returned_rows: int
    inserted_rows: int
    records: tuple[DailyBar, ...]
    issues: tuple[str, ...]
    warnings: tuple[str, ...]
    http_status: int | None = None
    retry_after: str | None = None


class BarWriter(Protocol):
    """The ingestion service needs only the existing atomic writer port."""

    def write_many(self, bars: Iterable[DailyBar], *, run_id: str) -> WriteResult: ...


class SourceSchemaError(RuntimeError):
    """The SDK output no longer matches the reviewed table schema."""


class SourceResponseError(RuntimeError):
    """Malformed/ambiguous SDK response, without proven field or HTTP semantics."""


class EvidenceWriteError(OSError):
    """Evidence failed; committed may be true if the database already committed."""

    def __init__(self, message: str, *, database_committed: bool = False):
        self.database_committed = database_committed
        super().__init__(message)

"""Health evidence is separate from ingestion outcomes and production approval."""

from dataclasses import asdict, dataclass, field
from enum import Enum
import json
import re

from ai_trade.data_access.validation import iso_date, timestamp


class CheckType(str, Enum):
    CONFIGURATION = "configuration_check"
    CONNECTIVITY = "connectivity_check"
    MARKET_DATA = "market_data_check"


class HealthStatus(str, Enum):
    SUCCESS = "success"
    NETWORK_ERROR = "network_error"
    HTTP_ERROR = "http_error"
    PARSE_ERROR = "parse_error"
    EMPTY_DATA = "empty_data"
    QUALITY_ERROR = "quality_error"
    STALE_DATA = "stale_data"
    DB_ERROR = "db_error"
    NOT_RUN = "not_run"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class CalendarExpectation:
    """Caller-supplied, evidence-backed expected closed session, never a weekday guess."""

    expected_data_date: str | None = None
    evidence_ref: str | None = None
    status: str = "unknown"

    def __post_init__(self):
        if self.status not in ("known", "unknown", "source_error"):
            raise ValueError("invalid calendar status")
        if self.status == "known":
            iso_date(self.expected_data_date, "expected_data_date")
            if not self.evidence_ref:
                raise ValueError("known calendar requires evidence reference")
            if not re.fullmatch(r"[A-Za-z0-9_.:-]{1,256}", self.evidence_ref):
                raise ValueError("calendar evidence must be an identifier, not credentials/URL")
        elif self.expected_data_date is not None:
            raise ValueError("unknown calendar cannot supply an expected date")


@dataclass(frozen=True)
class HealthResult:
    check_id: str
    source_id: str
    interface_id: str
    started_at: str
    finished_at: str
    check_type: CheckType
    status: HealthStatus
    failure_stage: str | None = None
    error_type: str | None = None
    request_count: int = 0
    http_status: int | None = None
    dataframe_rows: int | None = None
    data_date_min: str | None = None
    data_date_max: str | None = None
    expected_data_date: str | None = None
    is_stale: bool | None = None
    validation_status: str = "not_run"
    db_write_status: str = "not_run"
    db_rows_inserted: int | None = None
    db_rows_read_back: int | None = None
    details_redacted: dict = field(default_factory=dict)

    def __post_init__(self):
        for value in (self.check_id, self.source_id, self.interface_id):
            if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,128}", value):
                raise ValueError("health identifiers must be bounded identifiers, not URLs")
        object.__setattr__(self, "check_type", CheckType(self.check_type))
        object.__setattr__(self, "status", HealthStatus(self.status))
        for name in ("started_at", "finished_at"):
            object.__setattr__(self, name, timestamp(getattr(self, name), name))
        if self.finished_at < self.started_at:
            raise ValueError("health clock cannot move backwards")
        for name in ("request_count", "dataframe_rows", "db_rows_inserted", "db_rows_read_back"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < 0):
                raise ValueError("counts must be nonnegative integers or null")
        if self.request_count is None:
            raise ValueError("send-boundary count must be explicit")
        if (self.check_type != CheckType.MARKET_DATA or self.status == HealthStatus.NOT_RUN) and (
                self.dataframe_rows is not None or self.request_count != 0):
            raise ValueError("unexecuted/non-market checks cannot claim HTTP sends or DataFrames")
        if self.status in (HealthStatus.NETWORK_ERROR, HealthStatus.HTTP_ERROR, HealthStatus.PARSE_ERROR):
            if self.dataframe_rows is not None:
                raise ValueError("failed fetch/parse cannot claim a DataFrame")
        for name in ("data_date_min", "data_date_max", "expected_data_date"):
            if getattr(self, name) is not None:
                iso_date(getattr(self, name), name)
        if self.is_stale is not None and type(self.is_stale) is not bool:
            raise ValueError("is_stale must be boolean or null")
        if self.http_status is not None and (type(self.http_status) is not int or not 100 <= self.http_status <= 599):
            raise ValueError("invalid HTTP status")
        if self.validation_status not in ("not_run", "empty_frame", "passed", "failed"):
            raise ValueError("invalid validation status")
        if self.db_write_status not in ("not_run", "failed", "committed"):
            raise ValueError("invalid database write status")
        if self.check_type == CheckType.MARKET_DATA and self.status == HealthStatus.SUCCESS:
            if not (self.http_status == 200 and self.dataframe_rows and self.validation_status == "passed"
                    and self.db_write_status == "committed" and self.is_stale is False
                    and self.data_date_max == self.expected_data_date
                    and self.db_rows_inserted == self.db_rows_read_back == self.dataframe_rows):
                raise ValueError("market success requires HTTP/data/freshness/database evidence")
        allowed = {"reason", "type_chain", "calendar_status", "candidate", "production_accepted",
                   "sdk_calls", "budget_exhausted", "http_observations", "sdk_version",
                   "ingestion_status", "network_phase", "rows_readback_match", "evidence_recorded",
                   "calendar_evidence_ref", "ingestion_evidence_ref", "response_sha256", "request_state"}
        allowed.add("request_policy_blocked")
        if set(self.details_redacted) - allowed:
            raise ValueError("unapproved health detail fields")
        # Details are controlled codes/counts, never raw exception messages or URLs.
        encoded = json.dumps(self.details_redacted, allow_nan=False)
        if len(encoded) > 12000 or re.search(r"://|@|(?i:cookie|password|authorization|token=)", encoded):
            raise ValueError("health details must be redacted codes, not credentials/URLs")
        for value in (self.failure_stage, self.error_type):
            if value is not None and not re.fullmatch(r"[A-Za-z0-9_]{1,80}", value):
                raise ValueError("failure metadata must contain codes/types only")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict) -> "HealthResult":
        return cls(**payload)

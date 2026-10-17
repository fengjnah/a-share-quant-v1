"""One-endpoint ingestion orchestration over the existing repository writer."""

import math
from dataclasses import asdict, replace
from datetime import datetime, timezone
from json import JSONDecodeError
from typing import Callable

import pandas as pd
from requests.exceptions import HTTPError, RequestException, JSONDecodeError as RequestsJSONDecodeError

from ai_trade.data_access.models import DuplicateRecordError, IntegrityError, ValidationError
from ai_trade.data_access.validation import text_field, timestamp, validate_bar
from ai_trade.market_data.akshare_adapter import (
    ADAPTER_VERSION, DailyHistoryClient, check_frame, map_frame, validate_request,
)
from ai_trade.market_data.evidence import EvidenceStore
from ai_trade.market_data.models import (
    BarWriter, DailyHistoryRequest, EvidenceWriteError, IngestionResult, IngestionStatus, SourceResponseError,
    SourceSchemaError,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DailyHistoryIngestor:
    """Archive an observed SDK response, validate, then commit a complete batch.

    No retries, source fallback, automatic revision or duplicate skipping occur.
    HTTP metadata hidden by AKShare cannot be reconstructed by this service.
    """

    def __init__(self, client: DailyHistoryClient, writer: BarWriter,
                 evidence: EvidenceStore, *, clock: Callable[[], datetime] = utc_now,
                 timeout: float = 10.0):
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be a finite positive number of seconds")
        text_field(client.sdk_version, "sdk_version")
        self.client = client
        self.writer = writer
        self.evidence = evidence
        self.clock = clock
        self.timeout = float(timeout)
        self.source = f"akshare-eastmoney:stock_zh_a_hist:{ADAPTER_VERSION}+sdk-{client.sdk_version}"
        text_field(self.source, "source")

    def _now(self, previous: str | None = None) -> str:
        current = self.clock()
        if not isinstance(current, datetime):
            raise ValidationError(("clock: timezone-aware datetime required",))
        value = timestamp(current.isoformat(), "clock")
        if previous is not None and value < previous:
            raise ValidationError(("clock: acquisition time cannot move backwards",))
        return value

    def collect(self, request: DailyHistoryRequest, *, run_id: str) -> IngestionResult:
        """Invalid requests fail before any SDK call; observed failures get a run result."""
        started = self._now()
        validate_request(request, now=datetime.fromisoformat(started))
        text_field(run_id, "run_id")
        folder = self.evidence.begin(run_id, {
            "run_id": run_id, "request": asdict(request), "started_at": started,
            "source": self.source, "sdk_version": self.client.sdk_version,
            "endpoint": "akshare.stock_zh_a_hist", "provider": "eastmoney",
            "parameters": {"symbol": request.symbol[:6], "period": "daily",
                           "start_date": request.start_date.replace("-", ""),
                           "end_date": request.end_date.replace("-", ""), "adjust": "",
                           "timeout": self.timeout},
            "availability_policy": "observed_on_fetch; no historical publication timestamp provided",
            "event_time_policy": "trade_date at regular-session 15:00 Asia/Shanghai; calendar not certified",
        })
        observed = validated = digest = None
        returned = inserted = 0
        records = ()
        issues: tuple[str, ...] = ()
        http_status = None
        retry_after = None
        status = IngestionStatus.SUCCESS
        try:
            try:
                frame = self.client.fetch(request, timeout=self.timeout)
            except (JSONDecodeError, RequestsJSONDecodeError, KeyError, TypeError, ValueError) as exc:
                raise SourceResponseError(f"{type(exc).__name__}: SDK parsing/signature failure") from exc
            observed = self._now(started)
            if isinstance(frame, pd.DataFrame):
                returned = len(frame.index)
                digest = self.evidence.response(folder, frame)
            check_frame(frame)
            if returned == 0:
                status = IngestionStatus.EMPTY_RESPONSE
                issues = ("SDK returned zero rows; cause and coverage are unproven, not a successful ingestion",)
            else:
                candidate = map_frame(frame, request, source=self.source, observed_at=observed)
                validated = self._now(observed)
                records = tuple(validate_bar(replace(bar, ingested_at=validated)) for bar in candidate)
                written = self.writer.write_many(records, run_id=run_id)
                inserted = written.inserted
        except SourceResponseError as exc:
            status, issues = IngestionStatus.RESPONSE_ERROR, (f"{type(exc).__name__}: ambiguous/malformed SDK response; HTTP metadata may be unavailable",)
        except HTTPError as exc:
            if exc.response is not None:
                http_status = exc.response.status_code
                retry_after = exc.response.headers.get("Retry-After")
            status = IngestionStatus.RATE_LIMITED if http_status == 429 else IngestionStatus.NETWORK_ERROR
            issues = (f"HTTP error from source; status={http_status}; no automatic retry",)
        except (RequestException, TimeoutError, ConnectionError) as exc:
            status, issues = IngestionStatus.NETWORK_ERROR, (f"{type(exc).__name__}: source transport failed",)
        except SourceSchemaError as exc:
            status, issues = IngestionStatus.SCHEMA_ERROR, (str(exc),)
        except DuplicateRecordError as exc:
            status, issues = IngestionStatus.DUPLICATE, (str(exc),)
        except IntegrityError as exc:
            status, issues = IngestionStatus.CONFLICT, (str(exc),)
        except ValidationError as exc:
            status, issues = IngestionStatus.VALIDATION_ERROR, exc.issues
        if status != IngestionStatus.SUCCESS:
            records = ()
        try:
            completed = self._now(validated or observed or started)
        except ValidationError as exc:
            raise EvidenceWriteError(
                f"clock invalid while finalizing evidence: {folder}; inspect database before retrying",
                database_committed=inserted > 0,
            ) from exc
        result = IngestionResult(
            run_id, status, self.source, started, observed, validated, completed,
            str(folder), digest, returned, inserted, records, issues,
            ("Date-range completeness, listing identity and exchange sessions are not certified.",
             "SDK-level evidence is not original HTTP bytes or historical publication evidence."),
            http_status, retry_after,
        )
        self.evidence.finish(folder, asdict(result), database_committed=inserted > 0)
        return result

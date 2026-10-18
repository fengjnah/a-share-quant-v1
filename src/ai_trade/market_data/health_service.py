"""Reuse ingestion/SQLite contracts, with conservative, source-specific health evidence."""

from dataclasses import dataclass
from datetime import datetime, timezone, date
from pathlib import Path
import tempfile
import hashlib
from typing import Callable
import uuid

import pandas as pd

from ai_trade.data_access.repository import SQLiteMarketDataRepository
from ai_trade.market_data.akshare_adapter import AkshareDailyClient, _market_date, validate_request
from ai_trade.market_data.evidence import EvidenceStore
from ai_trade.market_data.health_models import CalendarExpectation, CheckType, HealthResult, HealthStatus
from ai_trade.market_data.health_transport import BudgetBlocked, HealthTransport
from ai_trade.market_data.ingestor import DailyHistoryIngestor, _transport_type_chain
from ai_trade.market_data.models import DailyHistoryRequest, IngestionStatus
from ai_trade.market_data.tx_adapter import TxDailyClient
from ai_trade.storage.db import Database, DatabaseConfig


@dataclass(frozen=True)
class HealthSource:
    source_id: str
    interface_id: str
    client_factory: Callable
    targets: frozenset[tuple[str, str]]
    candidate: bool = False
    date_column: str = "日期"
    reviewed_sdk_version: str = "1.19.1"


SOURCES = {
    "eastmoney": HealthSource("eastmoney", "akshare.stock_zh_a_hist", AkshareDailyClient,
                              frozenset({("push2his.eastmoney.com", "/api/qt/stock/kline/get")})),
    "tencent": HealthSource("tencent", "akshare.stock_zh_a_hist_tx", TxDailyClient,
                            frozenset({("web.ifzq.gtimg.cn", "/other/klineweb/klineWeb/weekTrends"),
                                       ("proxy.finance.qq.com", "/ifzqgtimg/appstock/app/newfqkline/get")}),
                            candidate=True, date_column="date"),
}


class _ObservedClient:
    def __init__(self, client):
        self.client = client
        self.frame = None
        self.error = None
        self.calls = 0

    def __getattr__(self, name):
        return getattr(self.client, name)

    def fetch(self, request, *, timeout):
        self.calls += 1
        try:
            frame = self.client.fetch(request, timeout=timeout)
            if isinstance(frame, pd.DataFrame):
                self.frame = frame
            return frame
        except Exception as exc:
            self.error = exc
            raise


class _ScratchWriter:
    """Lazy schema creation: only a validated batch reaches the existing writer."""

    def __init__(self, root: Path, database_factory=Database):
        self.root = root
        self.database_factory = database_factory
        self.database = self.repository = None
        self.attempted = False
        self.inserted = None

    def write_many(self, records, *, run_id):
        self.attempted = True
        self.database = self.database_factory(DatabaseConfig(
            self.root / "health.sqlite3", environment="test", journal_mode="DELETE"))
        self.database.initialize()
        self.repository = SQLiteMarketDataRepository(self.database)
        result = self.repository.write_many(records, run_id=run_id)
        self.inserted = result.inserted
        return result


class HealthService:
    def __init__(self, sources=None, *, clock=None, database_factory=Database):
        self.sources = SOURCES if sources is None else sources
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.database_factory = database_factory

    def check(self, source_id: str, check_type=CheckType.CONFIGURATION, *,
              network_enabled: bool = False, max_requests: int = 0,
              request: DailyHistoryRequest | None = None,
              expectation: CalendarExpectation | None = None, timeout: float = 10) -> HealthResult:
        spec = self.sources[source_id]  # No implicit source selection/fallback.
        kind = CheckType(check_type)
        started = self.clock().isoformat()
        check_id = "health-" + uuid.uuid4().hex
        fields = dict(check_id=check_id, source_id=spec.source_id, interface_id=spec.interface_id,
                      started_at=started, check_type=kind)
        details = {"candidate": spec.candidate, "production_accepted": False, "sdk_calls": 0,
                   "request_state": "not_attempted"}

        def finish(status, **changes):
            return HealthResult(**fields, finished_at=self.clock().isoformat(), status=status,
                                details_redacted=details.copy(), **changes)

        if kind == CheckType.CONNECTIVITY:
            details["reason"] = "no_independent_approved_probe"
            return finish(HealthStatus.NOT_RUN)
        if kind == CheckType.MARKET_DATA and network_enabled is not True:
            details["reason"] = "real_network_not_enabled"
            return finish(HealthStatus.NOT_RUN)
        try:
            client = spec.client_factory()  # Version/local registration only, no fetch.
            if (spec.source_id != source_id or not callable(client.fetch)
                    or client.sdk_version != spec.reviewed_sdk_version):
                raise ValueError("unreviewed source registration/version")
            details["sdk_version"] = client.sdk_version
        except Exception as exc:
            details["reason"] = "dependency_or_registration_failed"
            return finish(HealthStatus.UNKNOWN, failure_stage="configuration",
                          error_type=_transport_type_chain(exc).split(" > ")[0])
        if kind == CheckType.CONFIGURATION:
            details["reason"] = "configuration_only_not_network_health"
            return finish(HealthStatus.SUCCESS)

        expected = expectation or CalendarExpectation()
        details["calendar_status"] = expected.status
        if expected.evidence_ref:
            details["calendar_evidence_ref"] = expected.evidence_ref
        try:
            if request is None or request.symbol != "600000.SH":
                raise ValueError("only the fixed approved sample 600000.SH is supported")
            validate_request(request, now=datetime.fromisoformat(started))
            span = (date.fromisoformat(request.end_date) - date.fromisoformat(request.start_date)).days
            if span > 6:
                raise ValueError("health sample must be at most seven calendar days")
            transport = HealthTransport(spec.targets, max_requests, timeout)
        except (ValueError, TypeError):
            details["reason"] = "invalid_request_or_explicit_budget"
            return finish(HealthStatus.NOT_RUN, failure_stage="configuration")

        root = Path(tempfile.mkdtemp(prefix="a-share-health-"))
        writer = _ScratchWriter(root, self.database_factory)
        observed = _ObservedClient(client)
        result = None
        local_error = None
        try:
            with transport.installed():
                result = DailyHistoryIngestor(observed, writer, EvidenceStore(root / "evidence"),
                                             clock=self.clock, timeout=timeout).collect(request, run_id=check_id)
        except Exception as exc:
            local_error = exc

        details.update(sdk_calls=observed.calls,
                       budget_exhausted=transport.blocked and transport.count >= transport.max_requests,
                       request_policy_blocked=transport.blocked or isinstance(local_error, BudgetBlocked),
                       http_observations=list(transport.responses), evidence_recorded=result is not None)
        details["request_state"] = ("http_response_observed" if transport.responses else
                                    "send_attempt_observed" if transport.count else "not_attempted")
        details["ingestion_evidence_ref"] = root.name + ":evidence:" + hashlib.sha256(check_id.encode()).hexdigest()
        if result and result.response_sha256:
            details["response_sha256"] = result.response_sha256
        error = observed.error or local_error
        if error is not None:
            details["type_chain"] = _transport_type_chain(error)
        http_status = transport.responses[-1] if transport.responses else (result.http_status if result else None)
        changes = dict(request_count=transport.count, http_status=http_status,
                       dataframe_rows=len(observed.frame) if observed.frame is not None else None,
                       expected_data_date=expected.expected_data_date,
                       validation_status="passed" if writer.attempted else "not_run",
                       db_write_status="failed" if writer.attempted else "not_run",
                       db_rows_inserted=writer.inserted)
        if writer.inserted is not None:
            changes["db_write_status"] = "committed"
        if observed.frame is not None:
            dates = []
            column = spec.date_column
            if column in observed.frame.columns and not observed.frame.columns.has_duplicates:
                for value in observed.frame[column]:
                    try:
                        dates.append(_market_date(value))
                    except (ValueError, TypeError):
                        pass
            if dates:
                changes.update(data_date_min=min(dates), data_date_max=max(dates))
        if error is not None:
            changes["error_type"] = _transport_type_chain(error).split(" > ")[0]
        if details["request_policy_blocked"]:
            details["reason"] = "send_budget_or_policy_blocked"
            return finish(HealthStatus.UNKNOWN, failure_stage="request_policy", **changes)
        if http_status is not None and http_status != 200:
            return finish(HealthStatus.HTTP_ERROR, failure_stage="http_response", **changes)
        if local_error is not None and isinstance(observed.error, OSError):
            details["network_phase"] = "undetermined"
            return finish(HealthStatus.NETWORK_ERROR, failure_stage="sdk_fetch_transport", **changes)
        if local_error is not None:
            stage = "sqlite_write" if writer.attempted and writer.inserted is None else "local_audit"
            return finish(HealthStatus.DB_ERROR if stage == "sqlite_write" else HealthStatus.UNKNOWN,
                          failure_stage=stage, **changes)
        details["ingestion_status"] = result.status.value
        if result.status == IngestionStatus.NETWORK_ERROR:
            details["network_phase"] = "undetermined"
            return finish(HealthStatus.NETWORK_ERROR, failure_stage="sdk_fetch_transport", **changes)
        if result.status == IngestionStatus.RESPONSE_ERROR:
            return finish(HealthStatus.PARSE_ERROR if http_status == 200 else HealthStatus.UNKNOWN,
                          failure_stage="sdk_parse" if http_status == 200 else "unobserved_response", **changes)
        if result.status == IngestionStatus.EMPTY_RESPONSE:
            changes["validation_status"] = "empty_frame"
            return finish(HealthStatus.EMPTY_DATA if http_status == 200 else HealthStatus.UNKNOWN,
                          failure_stage="empty_frame", **changes)
        if result.status != IngestionStatus.SUCCESS:
            changes["validation_status"] = "passed" if writer.attempted else "failed"
            changes["error_type"] = {
                IngestionStatus.SCHEMA_ERROR: "SourceSchemaError",
                IngestionStatus.VALIDATION_ERROR: "ValidationError",
                IngestionStatus.DUPLICATE: "DuplicateRecordError",
                IngestionStatus.CONFLICT: "IntegrityError",
            }.get(result.status)
            return finish(HealthStatus.DB_ERROR if writer.attempted else HealthStatus.QUALITY_ERROR,
                          failure_stage="sqlite_write" if writer.attempted else "data_validation", **changes)

        changes["validation_status"] = "passed"
        changes["db_rows_read_back"] = 0
        try:
            matched = 0
            for bar in result.records:
                read = writer.repository.get_bar(instrument_id=bar.instrument_id, trade_date=bar.trade_date,
                        source=bar.source, adjustment_method=bar.adjustment_method,
                        as_of=bar.ingested_at, mode="strict_backtest")
                if read is not None:
                    changes["db_rows_read_back"] += 1
                if read.bar != bar or f"run:{check_id}" not in read.lineage_refs:
                    raise ValueError("point-in-time readback differs")
                matched += 1
            with writer.database.connection() as conn:
                if (conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok"
                        or conn.execute("PRAGMA foreign_key_check").fetchall()):
                    raise ValueError("SQLite integrity check failed")
            changes["db_rows_read_back"] = matched
            if matched != result.returned_rows or matched != writer.inserted:
                raise ValueError("row count differs")
            details["rows_readback_match"] = True
        except Exception:
            changes["error_type"] = "ReadbackError"
            return finish(HealthStatus.DB_ERROR, failure_stage="sqlite_readback", **changes)
        if http_status != 200:
            details["reason"] = "http_response_unobserved"
            return finish(HealthStatus.UNKNOWN, failure_stage="unobserved_response", **changes)
        if expected.status != "known":
            details["reason"] = "freshness_calendar_unavailable"
            return finish(HealthStatus.UNKNOWN, failure_stage="freshness", **changes)
        changes["is_stale"] = changes["data_date_max"] < expected.expected_data_date
        if changes["is_stale"]:
            return finish(HealthStatus.STALE_DATA, failure_stage="freshness", **changes)
        if changes["data_date_max"] > expected.expected_data_date:
            details["reason"] = "calendar_data_date_conflict"
            return finish(HealthStatus.QUALITY_ERROR, failure_stage="freshness", **changes)
        return finish(HealthStatus.SUCCESS, **changes)

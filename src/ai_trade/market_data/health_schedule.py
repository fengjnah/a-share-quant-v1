"""Append-only health summaries and OS-scheduler plans; no installed jobs or network."""

from datetime import date, datetime, timedelta
import json
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_trade.market_data.evidence import EvidenceStore
from ai_trade.market_data.health_models import CalendarExpectation, CheckType, HealthResult, HealthStatus
from ai_trade.reference_data.models import CalendarSourceError, CalendarDataMissingError, NoKnownTradingDayError
from ai_trade.data_access.validation import validate_bar, timestamp


class HealthResultStore:
    def __init__(self, root: Path):
        self.evidence = EvidenceStore(root)

    def append(self, result: HealthResult) -> Path:
        folder = self.evidence.begin(result.check_id, {"kind": "source_health",
                    "source_id": result.source_id, "interface_id": result.interface_id,
                    "check_type": result.check_type})
        self.evidence.finish(folder, result.to_dict(),
                             database_committed=result.db_write_status == "committed")
        return folder

    def read_all(self) -> list[HealthResult]:
        # A partial/missing final record is not silently reported as healthy.
        results = []
        for folder in self.evidence.root.glob("*"):
            if not folder.is_dir():
                continue
            path = folder / "result.json"
            if not path.exists():
                raise ValueError("incomplete health audit requires manual review")
            results.append(HealthResult.from_dict(json.loads(path.read_text(encoding="utf-8"))))
        return sorted(results, key=lambda value: (value.finished_at, value.check_id))


def source_report(source_id: str, records: list[HealthResult]) -> dict:
    history = sorted((r for r in records if r.source_id == source_id),
                     key=lambda r: (r.finished_at, r.check_id))
    market = [r for r in history if r.check_type == CheckType.MARKET_DATA]
    latest = history[-1] if history else None
    checked = market[-1] if market else None
    failures = 0
    for record in reversed(market):
        if record.status == HealthStatus.SUCCESS:
            break
        if record.status not in (HealthStatus.NOT_RUN, HealthStatus.UNKNOWN):
            failures += 1
    status = checked.status if checked else HealthStatus.UNKNOWN
    state = "current_status_unknown"
    action = "explicit_market_check_or_manual_review"
    if status == HealthStatus.SUCCESS:
        state, action = "recent_check_passed_production_unverified", "review_production_evidence"
    elif status == HealthStatus.QUALITY_ERROR:
        state, action = "data_received_quality_failed", "stop_collection_manual_quality_review"
    elif status == HealthStatus.STALE_DATA:
        state, action = "stale_data", "review_dates_and_calendar"
    elif status not in (HealthStatus.UNKNOWN, HealthStatus.NOT_RUN):
        state, action = "current_check_chain_unavailable", "stop_collection_manual_review"
    success = [r for r in market if r.status == HealthStatus.SUCCESS]
    return {
        "source_id": source_id, "last_check_at": latest.finished_at if latest else None,
        "last_check_type": latest.check_type if latest else None,
        "last_check_result": latest.status if latest else "not_run",
        "last_market_result": checked.status if checked else "not_run",
        "state": state, "consecutive_market_failures": failures,
        "last_market_success_at": success[-1].finished_at if success else None,
        "failure_stage": checked.failure_stage if checked else None,
        "data_date": checked.data_date_max if checked else None,
        "is_stale": checked.is_stale if checked else None,
        "request_count": latest.request_count if latest else 0,
        "last_market_request_count": checked.request_count if checked else 0,
        "dataframe_rows": checked.dataframe_rows if checked else None,
        "http_status": checked.http_status if checked else None,
        "candidate": (latest.details_redacted.get("candidate", False) if latest else source_id == "tencent"),
        "db_write_status": checked.db_write_status if checked else "not_run",
        "next_action": action, "production_accepted": False,
    }


def calendar_expectation(calendar, *, verified: bool, exchange: str, completed_through: str,
                         search_start: str, as_of: str) -> CalendarExpectation:
    """Caller confirms the session-close cutoff and real calendar certification.

    Reuse strict, bounded as_of calendar queries; never derive weekdays/holidays.
    No database is opened or initialized here beyond the injected repository.
    """
    if not verified:
        return CalendarExpectation()
    cutoff = datetime.fromisoformat(timestamp(as_of, "as_of")).astimezone(ZoneInfo("Asia/Shanghai"))
    completed = date.fromisoformat(completed_through)
    span = (completed - date.fromisoformat(search_start)).days
    if (completed > cutoff.date() or not 0 <= span <= 31
            or (completed == cutoff.date() and cutoff.hour < 15)):
        return CalendarExpectation()
    before = (date.fromisoformat(completed_through) + timedelta(days=1)).isoformat()
    try:
        result = calendar.previous_known_trading_day(exchange=exchange, before=before,
                    search_start=search_start, as_of=as_of, mode="strict_backtest")
        if not result.complete or any("synthetic" in warning for warning in result.warnings):
            return CalendarExpectation()
        return CalendarExpectation(result.value.session_date, result.data_snapshot_id, "known")
    except CalendarSourceError:
        return CalendarExpectation(status="source_error")
    except (CalendarDataMissingError, NoKnownTradingDayError):
        return CalendarExpectation()


def schedule_plan(cadence: str, *, is_trading_day: bool | None = None) -> dict:
    plans = {
        "daily": ["configuration_check", "explicit_small_sample_market_check"],
        "weekly": ["offline_contract_tests", "compare_saved_source_snapshots"],
        "monthly": ["historical_coverage_audit_plan", "review_source_quality_evidence"],
    }
    return {"cadence": cadence, "actions": plans[cadence],
            "trading_day": is_trading_day,
            "expect_new_market_data": is_trading_day,
            "calendar_status": "known" if is_trading_day is not None else "unknown",
            "automatic_network_requests": 0, "installed_scheduler": False}


def compare_saved_records(left, right) -> dict:
    """Offline comparison only: no fetch, write, conflict winner or zero filling."""
    def index(records):
        indexed = {}
        for record in records:
            record = validate_bar(record)
            key = (record.instrument_id, record.trade_date, record.adjustment_method)
            if key in indexed or record.quality_status != "accepted":
                raise ValueError("duplicate/quarantined comparison input")
            indexed[key] = record
        return indexed
    first, second = index(left), index(right)
    common = sorted(first.keys() & second.keys())
    differences = []
    for key in common:
        changed = [name for name in ("open", "high", "low", "close", "volume", "amount")
                   if getattr(first[key], name) != getattr(second[key], name)]
        if changed:
            differences.append({"trade_date": key[1], "adjustment_method": key[2], "fields": changed})
    return {"left_rows": len(first), "right_rows": len(second), "common_keys": len(common),
            "left_only": len(first.keys() - second.keys()), "right_only": len(second.keys() - first.keys()),
            "differences": differences, "resolution": "manual_review_no_source_selected"}

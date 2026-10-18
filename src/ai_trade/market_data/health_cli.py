"""OS-task entry: python -m ai_trade.market_data.health_cli --help."""

import argparse
import json
from pathlib import Path

from ai_trade.market_data.health_models import CheckType, HealthStatus
from ai_trade.market_data.health_schedule import HealthResultStore, schedule_plan, source_report
from ai_trade.market_data.health_service import HealthService, SOURCES
from ai_trade.market_data.models import DailyHistoryRequest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Explicit, serial source health check; default is offline")
    parser.add_argument("--source", choices=tuple(SOURCES), required=True)
    parser.add_argument("--check-type", choices=[v.value for v in CheckType],
                        default=CheckType.CONFIGURATION.value)
    parser.add_argument("--audit-root", type=Path, required=True)
    parser.add_argument("--cadence", choices=("daily", "weekly", "monthly"), default="daily")
    parser.add_argument("--enable-network", action="store_true")
    parser.add_argument("--max-requests", type=int, default=0)
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--report-only", action="store_true")
    args = parser.parse_args(argv)
    store = HealthResultStore(args.audit_root)
    result = None
    try:
        if not args.report_only:
            request = None
            if args.start_date and args.end_date:
                request = DailyHistoryRequest("health-sample:600000:SH", "600000.SH",
                                             args.start_date, args.end_date, "none")
            result = HealthService().check(args.source, args.check_type, network_enabled=args.enable_network,
                                          max_requests=args.max_requests, request=request)
            store.append(result)
        report = {"schedule_plan": schedule_plan(args.cadence),
                  "result": result.to_dict() if result else None,
                  "source_report": source_report(args.source, store.read_all())}
        print(json.dumps(report, ensure_ascii=False, allow_nan=False, indent=2))
        return 0 if result is None or result.status == HealthStatus.SUCCESS else 2
    except Exception:
        # Raw exception messages can contain paths, URLs or proxy credentials.
        print(json.dumps({"status": "unknown", "error_type": "LocalHealthCheckError",
                          "check_id": result.check_id if result else None,
                          "db_write_status": result.db_write_status if result else "unknown",
                          "db_rows_inserted": result.db_rows_inserted if result else None}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

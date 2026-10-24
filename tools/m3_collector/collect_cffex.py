"""Offline-first CFFEX collector CLI for TASK-M3-COLLECTOR-001.

Collects a saved real CSV into the isolated test SQLite database using the
PR #51 storage contract. No network, no production database.

Usage:
    python tools/m3_collector/collect_cffex.py \
        --db test-data/m3-collector-test.sqlite3 \
        --root artifacts/collector-001 \
        --variety IF --date 2026-10-23
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from ai_trade.market_data.cffex_collector import CffexCollector
from ai_trade.storage.db import Database, DatabaseConfig


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="test-data/m3-collector-test.sqlite3")
    parser.add_argument("--root", default="artifacts/collector-001")
    parser.add_argument("--variety", required=True, choices=("IF", "IH", "IC", "IM"))
    parser.add_argument("--date", required=True)
    parser.add_argument("--observed-at", default=None,
                        help="ISO observed_at; defaults to collector clock")
    parser.add_argument("--ingested-at", default=None)
    args = parser.parse_args()

    # The ranking time fence requires calendar knowledge to be visible at the
    # ingestion cutoff; default both timestamps to now (UTC, aware).
    if args.observed_at is None:
        args.observed_at = datetime.now(timezone.utc).isoformat(timespec='microseconds')
    if args.ingested_at is None:
        args.ingested_at = args.observed_at

    db = Database(DatabaseConfig(Path(args.db), environment="test",
                                 journal_mode="DELETE", require_existing=True))
    root = Path(args.root)

    def offline(v: str, d: str) -> bytes:
        candidate = root / f"{v}_{d.replace('-', '')}_http.csv"
        if not candidate.is_file():
            raise FileNotFoundError(f"offline sample missing: {candidate}")
        return candidate.read_bytes()

    collector = CffexCollector(db, root, collect_from_file=offline)
    result = collector.collect(args.variety, args.date,
                              observed_at=args.observed_at,
                              ingested_at=args.ingested_at)
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 0 if result.status == "SUCCESS" else 2


if __name__ == "__main__":
    raise SystemExit(main())

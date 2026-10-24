from __future__ import annotations

"""Read-only CFFEX holdings query layer for the M3 page.

Queries the isolated test SQLite database written by CffexCollector.
Does not write or modify the database. Never returns mock data; if the
report is absent the result is None and the page shows the real error state.
"""

from pathlib import Path
from typing import Optional

from ai_trade.m3_store_market import MarketInputRepository
from ai_trade.storage.db import Database, DatabaseConfig


def open_test_db(db_path: Path, evidence_root: Optional[Path] = None) -> tuple:
    """Open the isolated test SQLite database read-only; never writes.

    evidence_root must match the root used at collection time, otherwise the
    evidence files cannot be located and provenance reconstruction fails.
    Returns (db, evidence_root) so the caller can build the repository.
    """
    db = Database(DatabaseConfig(Path(db_path), environment="test", journal_mode="DELETE",
                                 read_only=True, require_existing=True))
    return db, evidence_root


def list_cffex_reports(db: Database) -> list[dict]:
    """List all stored CFFEX reports in the test database."""
    from ai_trade.m3_store_values import rows
    with db.connection() as conn:
        reports = rows(conn, "cffex_report_versions", exchange="CFFEX")
    return sorted(reports, key=lambda r: (r["variety"], r["trade_date"], r["data_version_id"]))


def cffex_report(db: Database, variety: str, trade_date: str,
                 evidence_root: Optional[Path] = None) -> Optional[dict]:
    """Read back one CFFEX report; None if not found in the test database.

    evidence_root must match the root used at collection time, otherwise
    provenance reconstruction fails with a clear error rather than silent None.
    """
    from ai_trade.m3_store_values import rows
    with db.connection() as conn:
        found = rows(conn, "cffex_report_versions",
            exchange="CFFEX", variety=variety, trade_date=trade_date)
    if not found:
        return None
    latest = max(found, key=lambda r: r.get("data_version_id", ""))
    vid = latest["data_version_id"]
    root = evidence_root or Path(db.config.path).parent
    repo = MarketInputRepository(db, root)
    record = repo.get_cffex(vid)
    version, _, _ = repo.get_version(vid)
    return {
        "variety": variety,
        "trade_date": trade_date,
        "version_id": vid,
        "row_count": len(record.rows),
        "contracts": list(record.contracts),
        "format": record.rank_format,
        "payload_sha256": record.payload_sha256,
        "source": record.source,
        "quality_status": version['quality_status'],
        "evidence_kind": version['evidence_kind'],
        "ingested_at": record.ingested_at,
        "available_at": record.available_at,
        "event_time": record.event_time,
        "warnings": list(record.warnings),
        "rows": [
            {
                "contract": r.contract,
                "rank": r.rank,
                "side": r.side.value,
                "member": r.member,
                "member_scope": r.member_scope.value,
                "open_interest": r.open_interest,
                "open_interest_change": r.open_interest_change,
                "open_interest_known": r.open_interest_known,
                "volume": r.volume,
                "volume_change": r.volume_change,
            } for r in record.rows
        ],
    }


def cffex_net_position(rows: list, member: str, contract: str, scope: str = "") -> Optional[dict]:
    """Compute net position for one member on one contract from stored rows.

    A member absent from one side is UNKNOWN (None), never zero.
    Only returns a numeric net when both sides are known."""
    from ai_trade.market_data.cffex_rankings_models import RankingSide, MemberScope
    known_scopes = {s.value for s in MemberScope if s is not MemberScope.UNKNOWN}
    if scope not in known_scopes:
        return {"member": member, "net": None, "long_oi": None, "short_oi": None,
                "note": "scope unknown/absent; not computable, not zero"}
    long_oi = None
    short_oi = None
    for row in rows:
        if row["member"] != member or row["contract"] != contract:
            continue
        if row["member_scope"] != scope:
            continue
        if row["side"] == "long" and row["open_interest_known"]:
            long_oi = row["open_interest"]
        if row["side"] == "short" and row["open_interest_known"]:
            short_oi = row["open_interest"]
    net = (long_oi - short_oi) if (long_oi is not None and short_oi is not None) else None
    note = "B-grade proxy: exchange-published Top-N member seat; not final-client fact"
    if net is None:
        note = "Net UNKNOWN: at least one side missing from Top-N disclosure; zero is not implied"
    return {"member": member, "net": net,
            "long_oi": long_oi, "short_oi": short_oi,
            "note": note}

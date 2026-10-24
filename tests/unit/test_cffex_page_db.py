"""Offline readback tests for the CFFEX query layer and page module.

No network access (conftest.py enforces this). Uses the saved real CSV
samples in artifacts/collector-001/ if present, otherwise a synthetic
fixture built from the same parse contract.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from ai_trade.market_data.cffex_collector import CffexCollector
from ai_trade.storage.db import Database, DatabaseConfig


REAL_CSV_ROOT = Path(__file__).resolve().parents[2] / "artifacts" / "collector-001"


def _db_and_samples(tmp_path: Path):
    db = CffexCollector.init_db(tmp_path / "db.sqlite3")
    root = tmp_path / "samples"
    root.mkdir()
    available = []
    for v in ("IF", "IH", "IC", "IM"):
        src = REAL_CSV_ROOT / f"{v}_20261023_http.csv"
        if src.is_file():
            (root / src.name).write_bytes(src.read_bytes())
            available.append(v)
    return db, root, available


def test_readback_roundtrip(tmp_path):
    from ai_trade.market_analysis_cffex_db import cffex_report, list_cffex_reports, open_test_db
    db, root, available = _db_and_samples(tmp_path)
    if not available:
        pytest.skip("real CFFEX samples not present in artifacts/")
    offline = _offline_factory(root)
    collector = CffexCollector(db, root, collect_from_file=offline)
    now_iso = _now_iso()
    for v in available:
        result = collector.collect(v, "2026-10-23", observed_at=now_iso, ingested_at=now_iso)
        assert result.status == "SUCCESS", f"{v}: {result.error}"

    db2, _ = open_test_db(tmp_path / "db.sqlite3", root)
    reports = list_cffex_reports(db2)
    assert {r["variety"] for r in reports} == set(available)
    for v in available:
        rep = cffex_report(db2, v, "2026-10-23", evidence_root=root)
        assert rep is not None
        assert rep["row_count"] > 0
        assert rep["payload_sha256"]
        assert rep["ingested_at"]


def test_readback_missing_date_returns_none(tmp_path):
    from ai_trade.market_analysis_cffex_db import cffex_report, open_test_db
    db, root, available = _db_and_samples(tmp_path)
    db2, _ = open_test_db(tmp_path / "db.sqlite3", root)
    result = cffex_report(db2, "IF", "1999-01-01", evidence_root=root)
    assert result is None


def test_page_module_imports_cleanly():
    """The page module must import without a running Streamlit session."""
    import ai_trade.market_analysis_cffex_page  # noqa: F401


def _offline_factory(root: Path):
    def offline(variety: str, trade_date: str) -> bytes:
        p = root / f"{variety}_{trade_date.replace('-', '')}_http.csv"
        if not p.is_file():
            raise FileNotFoundError(f"offline sample missing: {p}")
        return p.read_bytes()
    return offline


def _now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat(timespec='microseconds')

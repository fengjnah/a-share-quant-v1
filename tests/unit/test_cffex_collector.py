"""Offline CFFEX collector tests using saved real CSV samples.

Unit tests never access the network (enforced by conftest.py). Real-network
tests are under tests/manual/ and require an explicit flag.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from ai_trade.market_data.cffex_collector import CffexCollector, CollectResult
from ai_trade.storage.db import Database, DatabaseConfig


REAL_CSV_ROOT = Path(__file__).resolve().parents[2] / "artifacts" / "collector-001"
VARIETIES = ("IF", "IH", "IC", "IM")
TRADE_DATE = "2026-10-23"


def _offline_factory(root: Path):
    def offline(variety: str, trade_date: str) -> bytes:
        p = root / f"{variety}_{trade_date.replace('-', '')}_http.csv"
        if not p.is_file():
            raise FileNotFoundError(f"offline sample missing: {p}")
        return p.read_bytes()
    return offline


def _db(tmp_path: Path) -> Database:
    db = CffexCollector.init_db(tmp_path / "test.sqlite3")
    return db


def test_collect_success_all_varieties(tmp_path, monkeypatch):
    db = _db(tmp_path)
    root = tmp_path / "samples"
    root.mkdir()
    for v in VARIETIES:
        src = REAL_CSV_ROOT / f"{v}_20261023_http.csv"
        if src.is_file():
            (root / src.name).write_bytes(src.read_bytes())
    offline = _offline_factory(root)
    collector = CffexCollector(db, root, collect_from_file=offline)
    # Ingestion audit requires finished_at <= now; default the collector clock
    # to the current UTC time rather than a fixed future timestamp.
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat(timespec='microseconds')
    for v in VARIETIES:
        if not (root / f"{v}_20261023_http.csv").is_file():
            continue
        result = collector.collect(v, TRADE_DATE,
                                  observed_at=now, ingested_at=now)
        assert result.status == "SUCCESS", f"{v}: {result.error}"
        assert result.version_id is not None
        assert result.row_count > 0
        # Idempotency: re-collect same payload, expect same version_id
        result2 = collector.collect(v, TRADE_DATE,
                                   observed_at=now, ingested_at=now)
        assert result2.status == "SUCCESS"
        assert result2.version_id == result.version_id, "duplicate not detected"


def test_collect_missing_file(tmp_path):
    db = _db(tmp_path)
    empty_root = tmp_path / "empty"
    empty_root.mkdir()
    collector = CffexCollector(db, empty_root, collect_from_file=_offline_factory(empty_root))
    result = collector.collect("IF", TRADE_DATE,
                              observed_at="2026-10-24T09:30:00+00:00",
                              ingested_at="2026-10-24T09:30:00+00:00")
    assert result.status in ("FAILED", "BLOCKED")
    assert "FileNotFoundError" in result.error or "fetch" in result.error


def test_collect_invalid_csv_rejected(tmp_path):
    """Error page or homepage fallback must not be accepted as a valid ranking."""
    db = _db(tmp_path)
    root = tmp_path / "bad"
    root.mkdir()
    (root / "IF_20261023_http.csv").write_bytes(b"<html><body>404 Not Found</body></html>")
    collector = CffexCollector(db, root, collect_from_file=_offline_factory(root))
    result = collector.collect("IF", TRADE_DATE,
                              observed_at="2026-10-24T09:30:00+00:00",
                              ingested_at="2026-10-24T09:30:00+00:00")
    assert result.status in ("FAILED", "BLOCKED")


def test_collect_empty_file_rejected(tmp_path):
    db = _db(tmp_path)
    root = tmp_path / "emptycsv"
    root.mkdir()
    (root / "IF_20261023_http.csv").write_bytes(b"")
    collector = CffexCollector(db, root, collect_from_file=_offline_factory(root))
    result = collector.collect("IF", TRADE_DATE,
                              observed_at="2026-10-24T09:30:00+00:00",
                              ingested_at="2026-10-24T09:30:00+00:00")
    assert result.status in ("FAILED", "BLOCKED")


def test_net_position_both_sides_present(tmp_path):
    """Net is numeric only when both long and short OI are known for the member."""
    from ai_trade.market_analysis_cffex_db import cffex_net_position
    rows = [
        {"contract": "IF2611", "side": "long",  "member": "甲期货(代客)",
         "member_scope": "代客", "open_interest": 1000, "open_interest_known": True,
         "volume": None, "volume_change": None, "rank": 1},
        {"contract": "IF2611", "side": "short", "member": "甲期货(代客)",
         "member_scope": "代客", "open_interest": 800,  "open_interest_known": True,
         "volume": None, "volume_change": None, "rank": 2},
    ]
    result = cffex_net_position(rows, "甲期货(代客)", "IF2611", "代客")
    assert result["net"] == 200
    assert result["long_oi"] == 1000
    assert result["short_oi"] == 800


def test_net_position_one_side_missing_is_unknown(tmp_path):
    """Member absent from one side → UNKNOWN, never zero."""
    from ai_trade.market_analysis_cffex_db import cffex_net_position
    rows = [
        {"contract": "IF2611", "side": "long", "member": "乙期货(代客)",
         "member_scope": "代客", "open_interest": 500, "open_interest_known": True,
         "volume": None, "volume_change": None, "rank": 1},
    ]
    result = cffex_net_position(rows, "乙期货(代客)", "IF2611", "代客")
    assert result["net"] is None
    assert result["short_oi"] is None
    assert "UNKNOWN" in result["note"] or "not zero" in result["note"] or "missing" in result["note"]


def test_net_position_unknown_scope_not_computable(tmp_path):
    from ai_trade.market_analysis_cffex_db import cffex_net_position
    rows = [
        {"contract": "IF2611", "side": "long",  "member": "丙期货(unknown)",
         "member_scope": "unknown", "open_interest": 100, "open_interest_known": True,
         "volume": None, "volume_change": None, "rank": 1},
        {"contract": "IF2611", "side": "short", "member": "丙期货(unknown)",
         "member_scope": "unknown", "open_interest": 50,  "open_interest_known": True,
         "volume": None, "volume_change": None, "rank": 1},
    ]
    result = cffex_net_position(rows, "丙期货(unknown)", "IF2611", "unknown")
    assert result["net"] is None

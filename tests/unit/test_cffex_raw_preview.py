"""Synthetic-only preparation; these tests never certify or display real data."""
from dataclasses import replace
from contextlib import contextmanager
import hashlib

import pytest
from streamlit.testing.v1 import AppTest

from ai_trade.m3_store_catalog import Batch, CatalogRepository
from ai_trade.market_analysis_cffex_raw_preview import (
    load_synthetic_preview, filter_preview_rows, synthetic_attempts,
)
from ai_trade.storage.db import Database
from test_cffex_rankings import named
from test_cffex_workbench_route import app_test_local_ipc  # local IPC, external network denied

DAY = "2026-10-16"
CAPTURED = "2026-10-16T09:00:00.000000+00:00"


@pytest.fixture
def archive(database, tmp_path):
    root = tmp_path / "evidence"
    repo = CatalogRepository(database, root)
    repo.register_source(source_id="synthetic:cffex", provider="SYNTHETIC",
                         endpoint_key="fixture:cffex", adapter_version="fixture-v1",
                         dataset_key="cffex_rankings", units_json={}, time_policy_version="unknown")

    def save(variety="IF", kind="synthetic", label=None, captured=CAPTURED):
        label = label or variety
        payload = named(variety=variety, day=DAY)
        eid = repo.put_evidence(payload, evidence_kind=kind, media_type="text/csv", captured_at=captured)
        batch = Batch("preview:" + label, "run:" + label, "synthetic:cffex", label,
                      {"schema_version": "m3-request-v1", "parameters":
                       {"variety": variety, "trade_date": DAY}}, CAPTURED, CAPTURED)
        repo.record_attempt(batch, outcome="BLOCKED", error_code="SYNTHETIC_ONLY", evidence_id=eid)
        return batch.attempt_id, eid, payload
    return database, root, repo, save


@pytest.mark.parametrize("variety", ["IF", "IH", "IC", "IM"])
def test_exact_archive_values_provenance_filters_and_read_only(archive, variety):
    db, root, repo, save = archive
    aid, eid, payload = save(variety)
    before = db.config.path.read_bytes()
    actual = load_synthetic_preview(db, root, aid)  # writable handle is reopened read-only
    assert db.config.path.read_bytes() == before
    assert actual["payload_sha256"] == hashlib.sha256(payload).hexdigest()
    assert actual["captured_at"] == CAPTURED and actual["hash_status"] == "MATCH"
    assert actual["source"]["source_id"] == "synthetic:cffex"
    assert actual["evidence_id"] == eid and actual["attempt_id"] == aid
    assert actual["variety"] == variety and actual["trade_date"] == DAY
    selected = filter_preview_rows(actual, contract=variety + "2611", member="甲会员(代客)", side="long")
    assert len(selected) == 1 and selected[0]["open_interest"] == 2999
    assert selected[0]["volume"] is None
    assert filter_preview_rows(actual, member="不存在") == []
    zeros = filter_preview_rows(actual, contract=variety + "2610", member="甲会员(代客)")
    assert all(r["open_interest"] == 0 for r in zeros)


@pytest.mark.parametrize("environment", ["local", "production"])
def test_formal_handles_rejected_before_connection(archive, monkeypatch, environment):
    db, root, _, _ = archive
    supplied = Database(replace(db.config, environment=environment))
    def forbidden(*args):
        raise AssertionError("formal database must not be opened")
    monkeypatch.setattr(Database, "connection", forbidden)
    with pytest.raises(ValueError, match="synthetic test database required"):
        load_synthetic_preview(supplied, root, "not-read")
    with pytest.raises(ValueError, match="synthetic test database required"):
        synthetic_attempts(supplied)


def test_real_kind_rejected_before_reading_bytes_even_in_test_database(archive, monkeypatch):
    db, root, _, save = archive
    aid, _, _ = save(kind="source_payload")
    def forbidden(*args):
        raise AssertionError("real payload must not be read")
    monkeypatch.setattr(CatalogRepository, "evidence_bytes", forbidden)
    assert synthetic_attempts(db) == []
    with pytest.raises(ValueError, match="real evidence display is not authorized"):
        load_synthetic_preview(db, root, aid)


@pytest.mark.parametrize("damage", ["hash", "missing", "size"])
def test_evidence_integrity_failure_is_visible(archive, damage):
    db, root, _, save = archive
    aid, _, payload = save()
    path = root / "sha256" / hashlib.sha256(payload).hexdigest()
    if damage == "missing":
        path.unlink()
    elif damage == "size":
        path.write_bytes(payload + b"x")
    else:
        path.write_bytes(b"x" + payload[1:])
    with pytest.raises(ValueError, match="evidence"):
        load_synthetic_preview(db, root, aid)


def test_unknown_capture_time_is_not_filled_from_attempt(archive):
    db, root, _, save = archive
    aid, _, _ = save(captured=None)
    preview = load_synthetic_preview(db, root, aid)
    assert preview["captured_at"] is None
    assert preview["attempt_finished_at"] == CAPTURED


def test_reader_uses_sqlite_read_only_for_every_connection(archive, monkeypatch):
    db, root, _, save = archive
    aid, _, _ = save()
    original = Database.connection
    seen = []
    @contextmanager
    def checked(self):
        with original(self) as conn:
            seen.append((self.config.read_only, self.config.require_existing,
                         conn.execute("PRAGMA query_only").fetchone()[0]))
            yield conn
    monkeypatch.setattr(Database, "connection", checked)
    load_synthetic_preview(db, root, aid)
    assert seen and all(v == (True, True, 1) for v in seen)


def app_script(db, root, enabled):
    return f'''
from pathlib import Path
from ai_trade.storage.db import Database, DatabaseConfig
from ai_trade.market_analysis_cffex_raw_preview import render_synthetic_raw_preview
db = Database(DatabaseConfig(Path({str(db.config.path)!r}), environment="test"))
render_synthetic_raw_preview(db, Path({str(root)!r}), enabled={enabled!r})
'''


def test_ui_default_off_never_queries_database(archive, monkeypatch):
    db, root, _, _ = archive
    def forbidden(*args):
        raise AssertionError("default-off must not connect")
    monkeypatch.setattr(Database, "connection", forbidden)
    app = AppTest.from_string(app_script(db, root, False)).run()
    assert not app.exception and not app.dataframe and not app.checkbox
    assert any("默认关闭" in v.value for v in app.info)


def test_ui_opt_in_four_varieties_filters_and_warnings(archive):
    db, root, _, save = archive
    for variety in ("IF", "IH", "IC", "IM"):
        save(variety)
    before = db.config.path.read_bytes()
    app = AppTest.from_string(app_script(db, root, True)).run()
    assert not app.exception and not app.dataframe
    app.checkbox[0].check().run()
    assert not app.exception and not app.error
    assert app.selectbox[0].options == ["IF", "IH", "IC", "IM"]
    assert "UNVERIFIED | NOT ADMITTED | NOT FOR RESEARCH OR TRADING" in app.warning[0].value
    assert any("SYNTHETIC TEST FIXTURE" in v.value for v in app.info)
    metadata = app.json[0].value
    assert "payload_sha256" in metadata and "MATCH" in metadata
    assert "fixture:cffex" in metadata and CAPTURED in metadata
    for variety in ("IF", "IH", "IC", "IM"):
        next(s for s in app.selectbox if s.label == "预览品种").set_value(variety).run()
        assert not app.exception and not app.error
        assert all(v.startswith(variety) for v in app.dataframe[0].value["contract"])
    next(s for s in app.selectbox if s.label == "预览合约").set_value("IM2611")
    next(s for s in app.selectbox if s.label == "预览会员").set_value("甲会员(代客)")
    next(s for s in app.selectbox if s.label == "预览排名类别").set_value("long").run()
    assert len(app.dataframe[0].value) == 1
    assert app.dataframe[0].value.iloc[0]["open_interest"] == 2999
    app.checkbox[0].uncheck().run()
    assert not app.dataframe
    assert db.config.path.read_bytes() == before


def test_ui_corruption_shows_no_values(archive):
    db, root, _, save = archive
    _, _, payload = save()
    (root / "sha256" / hashlib.sha256(payload).hexdigest()).write_bytes(b"broken")
    app = AppTest.from_string(app_script(db, root, True)).run()
    app.checkbox[0].check().run()
    assert not app.exception and not app.dataframe
    assert any("预览失败" in e.value for e in app.error)

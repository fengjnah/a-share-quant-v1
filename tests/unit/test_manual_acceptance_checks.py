"""Offline checks of the manual test's diagnostics and acceptance assertions.

These synthetic cases do not constitute real-source acceptance.
"""

import json
import runpy
from datetime import datetime, timedelta, timezone
from itertools import count
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest

from ai_trade.market_data.evidence import EvidenceStore
from ai_trade.market_data.ingestor import DailyHistoryIngestor
from ai_trade.market_data.models import DailyHistoryRequest, IngestionStatus


@pytest.fixture(scope="module")
def checks():
    return runpy.run_path(str(Path(__file__).parents[1] / "manual" / "test_akshare_daily_live.py"))


@pytest.mark.parametrize("message", [
    "https://fixture-user:fixture-secret@example.invalid/path?token=fixture-secret",
    "Max retries exceeded with url: /api/get?ut=fixture-secret&symbol=600000",
    "api_key=fixture-secret", "access_token:fixture-secret",
])
def test_diagnostics_redact_absolute_and_relative_urls(checks, message):
    result = checks["_error_chain"](RuntimeError(message))
    assert result[0]["type"] == "RuntimeError"
    assert "fixture-secret" not in json.dumps(result)
    assert "fixture-user" not in json.dumps(result)


def test_diagnostics_bound_cyclic_causes(checks):
    first, second = RuntimeError("first"), OSError("second")
    first.__cause__, second.__context__ = second, first
    assert [x["type"] for x in checks["_error_chain"](first)] == ["RuntimeError", "OSError"]


@pytest.mark.parametrize("mutation", [None, "response", "result", "sqlite"])
def test_acceptance_reads_real_sqlite_and_detects_inconsistent_evidence(
        checks, repository, database, tmp_path, mutation):
    frame = pd.DataFrame(json.loads((Path(__file__).parents[1] / "fixtures" / "akshare_daily.json")
                                   .read_text(encoding="utf-8")))
    client = SimpleNamespace(sdk_version="offline-fixture", fetch=lambda request, timeout: frame)
    ticks = count()
    clock = lambda: datetime(2026, 10, 17, tzinfo=timezone.utc) + timedelta(seconds=next(ticks))
    service = DailyHistoryIngestor(client, repository, EvidenceStore(tmp_path / "evidence"), clock=clock)
    request = DailyHistoryRequest("research:fixture", "600000.SH", "2026-10-14", "2026-10-15", "none")
    result = service.collect(request, run_id="offline-acceptance-check")
    assert result.status == IngestionStatus.SUCCESS
    folder = Path(result.evidence_directory)
    if mutation in ("response", "result"):
        path = folder / (mutation + ".json")
        path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")
        if mutation == "result":
            payload = json.loads(path.read_text(encoding="utf-8"))
            payload["inserted_rows"] = 999
            path.write_text(json.dumps(payload), encoding="utf-8")
    elif mutation == "sqlite":
        # Deliberately corrupt only this isolated fixture to verify readback assertions.
        with database.transaction() as conn:
            conn.execute("DROP TRIGGER immutable_daily_bar_versions_update")
            conn.execute("UPDATE daily_bar_versions SET close=10.5 WHERE version_id=1")
    verify = checks["_verify_saved_batch"]
    if mutation:
        with pytest.raises(AssertionError):
            verify(database, repository, result, frame)
    else:
        assert verify(database, repository, result, frame) == ["2026-10-14", "2026-10-15"]

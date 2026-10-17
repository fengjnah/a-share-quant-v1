"""Manual integration only; configure all inputs and pass the explicit pytest flag."""

import os
import uuid

import pytest

from ai_trade.data_access.repository import SQLiteMarketDataRepository
from ai_trade.market_data.akshare_adapter import AkshareDailyClient
from ai_trade.market_data.evidence import EvidenceStore
from ai_trade.market_data.ingestor import DailyHistoryIngestor
from ai_trade.market_data.models import DailyHistoryRequest, IngestionStatus
from ai_trade.storage.db import Database, DatabaseConfig


@pytest.mark.manual_integration
def test_akshare_daily_live(tmp_path):
    names = ("AKSHARE_TEST_INSTRUMENT_ID", "AKSHARE_TEST_SYMBOL", "AKSHARE_TEST_START", "AKSHARE_TEST_END")
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        pytest.fail("explicit manual configuration required: " + ", ".join(missing))
    request = DailyHistoryRequest(*(os.environ[name] for name in names), adjustment_method="none")
    db = Database(DatabaseConfig(tmp_path / "manual.sqlite3", "test"))
    db.initialize()
    service = DailyHistoryIngestor(AkshareDailyClient(), SQLiteMarketDataRepository(db),
                                   EvidenceStore(tmp_path / "evidence"))
    result = service.collect(request, run_id="manual-" + uuid.uuid4().hex)
    assert result.status == IngestionStatus.SUCCESS, (result.status, result.issues, result.evidence_directory)
    assert result.inserted_rows > 0

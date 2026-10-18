"""Offline control tests for the Tencent backup adapter and Demo source selector."""

from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import importlib.metadata

import pandas as pd
import pytest

from ai_trade.data_access.models import DataUnavailableError, DuplicateRecordError, ValidationError
from ai_trade.market_data.evidence import EvidenceStore
from ai_trade.market_data.ingestor import DailyHistoryIngestor
from ai_trade.market_data.models import DailyHistoryRequest, IngestionStatus, SourceSchemaError
from ai_trade.market_data.tx_adapter import TxDailyClient, tx_map_frame


@pytest.fixture(autouse=True)
def reviewed_version(monkeypatch):
    # Core offline CI installs [test,demo], not the optional live SDK.
    monkeypatch.setattr(importlib.metadata, "version", lambda name: "1.19.1")


class TestTxDailyClient:
    def test_symbol_mapping_sh(self):
        client = TxDailyClient()
        assert client._tx_symbol("600000.SH") == "sh600000"

    def test_symbol_mapping_sz(self):
        client = TxDailyClient()
        assert client._tx_symbol("000001.SZ") == "sz000001"

    def test_rejects_unknown_suffix(self):
        client = TxDailyClient()
        with pytest.raises(ValidationError):
            client._tx_symbol("111111.XX")

    def test_rejects_qfq(self):
        client = TxDailyClient()
        request = DailyHistoryRequest(
            "id", "600000.SH", "2026-10-14", "2026-10-15", "qfq")
        with pytest.raises(ValidationError):
            client.fetch(request, timeout=10.0)


class TestTxMapFrame:
    def _frame(self):
        from datetime import date as d
        return pd.DataFrame({
            "date": [d(2026, 10, 14), d(2026, 10, 15)],
            "open": [10.0, 10.2], "close": [10.5, 10.4],
            "high": [10.8, 10.9], "low": [9.9, 10.1],
            "volume": [10000, 20000],
            "turnover": [0.5, 0.6],
            "amount": [1e7, 2e7],
        })

    def test_maps_to_bars(self):
        request = DailyHistoryRequest(
            "cn-equity:600000:SH", "600000.SH", "2026-10-14", "2026-10-15", "none")
        bars = tx_map_frame(
            self._frame(), request,
            source="akshare-tencent:stock_zh_a_hist_tx:task-008-v1+sdk-1.19.1",
            observed_at="2026-10-18T00:00:00+00:00")
        assert len(bars) == 2
        assert bars[0].trade_date == "2026-10-14"
        assert bars[0].volume == 10000
        assert bars[0].amount == 1e7
        assert bars[0].source.startswith("akshare-tencent:")

    def test_rejects_out_of_range_date(self):
        request = DailyHistoryRequest(
            "cn-equity:600000:SH", "600000.SH", "2026-10-14", "2026-10-15", "none")
        frame = self._frame()
        from datetime import date as d
        frame.loc[0, "date"] = d(2026, 10, 10)  # out of range
        with pytest.raises(ValidationError):
            tx_map_frame(
                frame, request,
                source="akshare-tencent:stock_zh_a_hist_tx:task-008-v1+sdk-1.19.1",
                observed_at="2026-10-18T00:00:00+00:00")


@pytest.fixture
def tx_request():
    return DailyHistoryRequest("listing:synthetic:tx", "600000.SH",
                               "2026-10-14", "2026-10-15", "none")


@pytest.fixture
def tx_frame():
    return TestTxMapFrame()._frame()


def service_for(client, repository, tmp_path):
    return DailyHistoryIngestor(client, repository, EvidenceStore(tmp_path / "evidence"),
                                clock=lambda: datetime(2026, 10, 18, tzinfo=timezone.utc))


def test_fetch_uses_reviewed_module_and_parameters_once(monkeypatch, tx_request, tx_frame):
    from ai_trade.market_data import tx_adapter
    calls = []
    def fetch(**kwargs):
        calls.append(kwargs)
        return tx_frame
    def load(name):
        assert name == "akshare.stock_feature.stock_hist_tx"
        return SimpleNamespace(stock_zh_a_hist_tx=fetch)
    monkeypatch.setattr(tx_adapter.importlib, "import_module", load)
    client = TxDailyClient()
    assert client.fetch(tx_request, timeout=4) is tx_frame
    assert calls == [{"symbol": "sh600000", "start_date": "20261014",
                      "end_date": "20261015", "adjust": "", "timeout": 4}]


@pytest.mark.parametrize("field,value", [
    ("volume", 1.5), ("volume", -1), ("volume", True), ("volume", float("nan")),
    ("volume", float("inf")), ("volume", 2**63),
    ("open", True), ("open", float("nan")), ("open", "10"),
    ("low", 20.0), ("amount", -1.0), ("amount", float("inf")),
])
def test_bad_batch_never_partially_writes(field, value, tx_request, tx_frame,
                                        repository, database, tmp_path, monkeypatch):
    tx_frame[field] = tx_frame[field].astype(object)
    tx_frame.loc[1, field] = value
    client = TxDailyClient()
    monkeypatch.setattr(client, "fetch", lambda *a, **k: tx_frame)
    result = service_for(client, repository, tmp_path).collect(tx_request, run_id="bad")
    assert result.status == IngestionStatus.VALIDATION_ERROR
    assert result.inserted_rows == 0
    with database.connection() as conn:
        assert conn.execute("SELECT count(*) FROM daily_bar_versions").fetchone()[0] == 0
        assert conn.execute("SELECT count(*) FROM ingestion_runs").fetchone()[0] == 0


def test_tx_evidence_units_visibility_and_sqlite_readback(tx_request, tx_frame, repository,
                                                        database, tmp_path, monkeypatch):
    client = TxDailyClient()
    monkeypatch.setattr(client, "fetch", lambda *a, **k: tx_frame)
    service = service_for(client, repository, tmp_path)
    result = service.collect(tx_request, run_id="tx-success")
    assert result.status == IngestionStatus.SUCCESS
    assert result.returned_rows == result.inserted_rows == 2
    bar = result.records[0]
    assert (bar.volume, bar.amount) == (10000, 1e7)  # SDK shares/yuan: no second conversion.
    assert bar.adjustment_method == "none"
    args = dict(instrument_id=bar.instrument_id, trade_date=bar.trade_date,
                source=bar.source, adjustment_method="none", mode="strict_backtest")
    before = (datetime.fromisoformat(bar.available_at) - timedelta(microseconds=1)).isoformat()
    with pytest.raises(DataUnavailableError):
        repository.get_bar(**args, as_of=before)
    assert repository.get_bar(**args, as_of=bar.ingested_at).bar == bar
    evidence = json.loads((Path(result.evidence_directory) / "request.json").read_text())
    assert evidence["provider"] == "tencent"
    assert evidence["endpoint"] == "akshare.stock_zh_a_hist_tx"
    assert evidence["parameters"] == client.request_parameters(tx_request, timeout=10.0)
    repeated = service.collect(tx_request, run_id="tx-repeat")
    assert repeated.status == IngestionStatus.DUPLICATE and repeated.inserted_rows == 0
    with database.connection() as conn:
        assert conn.execute("SELECT count(*) FROM daily_bar_versions").fetchone()[0] == 2


@pytest.mark.parametrize("case,status", [("empty", IngestionStatus.EMPTY_RESPONSE),
                                        ("network", IngestionStatus.NETWORK_ERROR),
                                        ("schema", IngestionStatus.SCHEMA_ERROR),
                                        ("duplicate", IngestionStatus.DUPLICATE)])
def test_failures_are_distinct_and_never_call_eastmoney(case, status, tx_request, tx_frame,
                                                       repository, tmp_path, monkeypatch):
    from ai_trade.market_data.akshare_adapter import AkshareDailyClient
    def forbidden(*a, **k):
        raise AssertionError("automatic source fallback forbidden")
    monkeypatch.setattr(AkshareDailyClient, "fetch", forbidden)
    if case == "empty":
        tx_frame = pd.DataFrame()
    elif case == "schema":
        tx_frame = tx_frame.drop(columns=["amount"])
    elif case == "duplicate":
        tx_frame = pd.concat([tx_frame, tx_frame.iloc[[0]]], ignore_index=True)
    def fetch(*a, **k):
        if case == "network":
            raise ConnectionError("synthetic transport error")
        return tx_frame
    client = TxDailyClient()
    monkeypatch.setattr(client, "fetch", fetch)
    result = service_for(client, repository, tmp_path).collect(tx_request, run_id="failure")
    assert result.status == status and result.inserted_rows == 0
    assert (result.observed_at is None) == (case == "network")
    if case == "network":
        assert "cause_types=ConnectionError" in result.issues[0]


def test_mapper_rejects_adjusted_input(tx_request, tx_frame):
    with pytest.raises(ValidationError):
        tx_map_frame(tx_frame, replace(tx_request, adjustment_method="qfq"),
                     source="synthetic:tx", observed_at="2026-10-18T00:00:00+00:00")


def test_missing_column_raises(tx_request, tx_frame):
    with pytest.raises(SourceSchemaError):
        tx_map_frame(tx_frame.drop(columns=["amount"]), tx_request,
                     source="synthetic:tx", observed_at="2026-10-18T00:00:00+00:00")


@pytest.mark.parametrize("value", [None, pd.NaT, "not-a-date", datetime(2026, 10, 14, 1)])
def test_invalid_date_is_structured_validation_failure(value, tx_request, tx_frame):
    tx_frame["date"] = tx_frame["date"].astype(object)
    tx_frame.loc[0, "date"] = value
    with pytest.raises(ValidationError):
        tx_map_frame(tx_frame, tx_request, source="synthetic:tx",
                     observed_at="2026-10-18T00:00:00+00:00")

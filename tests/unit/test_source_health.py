"""Synthetic health checks only; real SQLite and simulated HTTP adapter responses."""

from dataclasses import replace
from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import socket

import pandas as pd
import pytest
import requests
from requests.exceptions import SSLError, Timeout

from ai_trade.market_data import health_service as hs
from ai_trade.market_data.health_models import CalendarExpectation, CheckType, HealthResult, HealthStatus
from ai_trade.market_data.health_schedule import HealthResultStore, source_report, schedule_plan
from ai_trade.market_data.health_service import HealthService, HealthSource
from ai_trade.market_data.tx_adapter import TxDailyClient
from ai_trade.market_data.models import DailyHistoryRequest


NOW = datetime(2026, 10, 18, tzinfo=timezone.utc)
REQUEST = DailyHistoryRequest("synthetic:health:1", "600000.SH", "2026-10-14", "2026-10-15", "none")
KNOWN = CalendarExpectation("2026-10-15", "synthetic-test-only:calendar-snapshot", "known")


@pytest.fixture
def harness(monkeypatch):
    frames = {
        "eastmoney": pd.DataFrame({"日期": ["2026-10-15"], "股票代码": ["600000"], "开盘": [10.0],
                    "收盘": [11.0], "最高": [12.0], "最低": [9.0], "成交量": [123], "成交额": [135300.0]}),
        "tencent": pd.DataFrame({"date": ["2026-10-15"], "open": [10.0], "close": [11.0],
                    "high": [12.0], "low": [9.0], "volume": [12300], "amount": [135300.0]}),
    }
    state = {"status": 200, "error": None, "fetch_error": None, "calls": [], "sends": [],
             "parse_error": False, "http": True}

    def fake_send(adapter, prepared, **kwargs):
        state["sends"].append({"retries": adapter.max_retries.total, "timeout": kwargs["timeout"],
                               "verify": kwargs["verify"]})
        if state["error"]:
            raise state["error"]
        response = requests.Response()
        response.status_code = state["status"]
        response.url = prepared.url
        response.request = prepared
        response._content = b'not-json' if state["parse_error"] else b'{}'
        response._content_consumed = True
        return response
    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", fake_send)

    def fetch(source, timeout):
        state["calls"].append(source)
        if state["fetch_error"]:
            raise state["fetch_error"]
        if state["http"]:
            target = sorted(hs.SOURCES[source].targets)[0]
            response = requests.get("https://" + target[0] + target[1], timeout=timeout)
            response.json()
        return frames[source]

    class Eastmoney:
        sdk_version = "1.19.1"
        def fetch(self, request, *, timeout):
            return fetch("eastmoney", timeout)
    class Tencent(TxDailyClient):
        def __init__(self):
            self.sdk_version = "1.19.1"
        def fetch(self, request, *, timeout):
            return fetch("tencent", timeout)
    sources = {key: replace(hs.SOURCES[key], client_factory=value)
               for key, value in [("eastmoney", Eastmoney), ("tencent", Tencent)]}
    service = HealthService(sources, clock=lambda: NOW)
    return service, state, frames


def market(service, source="eastmoney", **kwargs):
    return service.check(source, CheckType.MARKET_DATA, network_enabled=True, max_requests=1,
                         request=REQUEST, expectation=KNOWN, **kwargs)


@pytest.mark.parametrize("source", ["eastmoney", "tencent"])
def test_configuration_does_not_call_fetch(harness, source):
    service, state, _ = harness
    result = service.check(source)
    assert result.status == HealthStatus.SUCCESS
    assert result.request_count == 0 and result.dataframe_rows is None
    assert state["calls"] == state["sends"] == []
    assert source_report(source, [result])["state"] == "current_status_unknown"


def test_configuration_failure_is_not_network_failure(harness):
    service, _, _ = harness
    def broken():
        raise RuntimeError("https://user:password@proxy/?token=hidden")
    service.sources = {"eastmoney": replace(service.sources["eastmoney"], client_factory=broken)}
    result = service.check("eastmoney")
    assert result.status == HealthStatus.UNKNOWN and result.failure_stage == "configuration"
    assert result.request_count == 0 and "password" not in json.dumps(result.to_dict())


@pytest.mark.parametrize("source", ["eastmoney", "tencent"])
def test_success_reuses_real_sqlite_units_and_point_in_time(harness, source, monkeypatch, tmp_path):
    service, state, _ = harness
    sentinel = tmp_path / "production.sqlite3"
    monkeypatch.setenv("QUANT_DB_ENV", "production")
    monkeypatch.setenv("QUANT_DB_PATH", str(sentinel))
    result = market(service, source)
    assert result.status == HealthStatus.SUCCESS
    assert result.dataframe_rows == result.db_rows_inserted == result.db_rows_read_back == 1
    assert result.is_stale is False and result.http_status == 200
    assert result.validation_status == "passed" and result.db_write_status == "committed"
    assert result.details_redacted["rows_readback_match"] is True
    assert result.request_count == 1 and state["calls"] == [source]
    assert state["sends"] == [{"retries": 0, "timeout": 10.0, "verify": True}]
    assert not sentinel.exists()
    assert HealthResult.from_dict(json.loads(json.dumps(result.to_dict()))) == result


@pytest.mark.parametrize("error", [socket.gaierror("hidden"), ConnectionRefusedError("hidden"),
                                   SSLError("hidden"), Timeout("hidden")])
def test_transport_failures_do_not_infer_dns_tcp_tls_root_cause(harness, error):
    service, state, _ = harness
    state["error"] = error
    result = market(service)
    assert result.status == HealthStatus.NETWORK_ERROR
    assert result.dataframe_rows is None and result.http_status is None
    assert result.request_count == 1 and result.db_write_status == "not_run"
    assert result.failure_stage not in ("dns", "tcp", "tls")
    assert state["calls"] == ["eastmoney"]  # never Tencent fallback


@pytest.mark.parametrize("status", [301, 403, 429, 500])
def test_observed_http_errors_do_not_become_parse_or_empty(harness, status):
    service, state, _ = harness
    state["status"] = status
    result = market(service)
    assert result.status == HealthStatus.HTTP_ERROR and result.http_status == status
    assert result.dataframe_rows is None and result.request_count == 1


def test_parse_requires_response_evidence(harness):
    service, state, _ = harness
    state["parse_error"] = True
    result = market(service)
    assert result.status == HealthStatus.PARSE_ERROR and result.http_status == 200
    assert result.dataframe_rows is None
    state["parse_error"] = False
    state["fetch_error"] = ValueError("parsing failed without HTTP evidence")
    result = market(service)
    assert result.status == HealthStatus.UNKNOWN and result.dataframe_rows is None


def test_empty_dataframe_requires_successful_request_evidence(harness):
    service, state, frames = harness
    frames["eastmoney"] = pd.DataFrame()
    result = market(service)
    assert result.status == HealthStatus.EMPTY_DATA and result.dataframe_rows == 0
    assert result.db_write_status == "not_run"
    state["http"] = False
    result = market(service)
    assert result.status == HealthStatus.UNKNOWN and result.dataframe_rows == 0


def test_nonempty_frame_without_http_observation_is_not_full_success(harness):
    service, state, _ = harness
    state["http"] = False
    result = market(service)
    assert result.status == HealthStatus.UNKNOWN and result.http_status is None
    assert result.dataframe_rows == result.db_rows_read_back == 1


@pytest.mark.parametrize("field,value", [("最高", 1), ("成交量", -1), ("成交额", -1)])
def test_quality_failure_has_no_database_write(harness, field, value):
    service, _, frames = harness
    frames["eastmoney"].loc[0, field] = value
    result = market(service)
    assert result.status == HealthStatus.QUALITY_ERROR and result.validation_status == "failed"
    assert result.dataframe_rows == 1 and result.db_write_status == "not_run"
    assert result.db_rows_inserted is None and result.db_rows_read_back is None


def test_stale_calendar_unknown_and_source_error_are_distinct(harness):
    service, _, _ = harness
    stale = service.check("eastmoney", CheckType.MARKET_DATA, network_enabled=True, max_requests=1,
                request=REQUEST, expectation=CalendarExpectation("2026-10-16", "fixture", "known"))
    assert stale.status == HealthStatus.STALE_DATA and stale.is_stale is True
    for expectation in [CalendarExpectation(), CalendarExpectation(status="source_error")]:
        result = service.check("eastmoney", CheckType.MARKET_DATA, network_enabled=True,
                              max_requests=1, request=REQUEST, expectation=expectation)
        assert result.status == HealthStatus.UNKNOWN and result.is_stale is None
        assert result.validation_status == "passed" and result.db_rows_read_back == 1


def test_database_write_and_readback_failures(harness, monkeypatch):
    service, _, _ = harness
    def failed_database(config):
        raise OSError("secret database path")
    service.database_factory = failed_database
    result = market(service)
    assert result.status == HealthStatus.DB_ERROR and result.failure_stage == "sqlite_write"
    service.database_factory = hs.Database
    monkeypatch.setattr(hs.SQLiteMarketDataRepository, "get_bar", lambda *a, **k: None)
    result = market(service)
    assert result.status == HealthStatus.DB_ERROR and result.failure_stage == "sqlite_readback"
    assert result.db_write_status == "committed" and result.db_rows_inserted == 1


def test_not_run_budget_and_connectivity_never_fetch(harness):
    service, state, _ = harness
    for source in ("eastmoney", "tencent"):
        result = service.check(source, CheckType.MARKET_DATA)
        assert result.status == HealthStatus.NOT_RUN and result.dataframe_rows is None
        assert result.request_count == 0
        result = service.check(source, CheckType.CONNECTIVITY, network_enabled=True)
        assert result.status == HealthStatus.NOT_RUN
    result = service.check("eastmoney", CheckType.MARKET_DATA, network_enabled=True, request=REQUEST)
    assert result.status == HealthStatus.NOT_RUN and state["calls"] == []


def test_secret_exception_messages_never_enter_audit(harness, tmp_path):
    service, state, _ = harness
    state["error"] = requests.ConnectionError("https://user:password@proxy/?token=hidden")
    result = market(service)
    store = HealthResultStore(tmp_path / "health-results")
    path = store.append(result)
    encoded = (path / "result.json").read_text(encoding="utf-8")
    assert "password" not in encoded and "hidden" not in encoded and "https://" not in encoded
    assert store.read_all() == [result]


def test_importing_health_entry_never_sends(harness):
    _, state, _ = harness
    importlib.import_module("ai_trade.market_data.health_cli")
    assert state["calls"] == state["sends"] == []


@pytest.mark.parametrize("budget,status,count", [(1, HealthStatus.UNKNOWN, 1),
                                                (2, HealthStatus.SUCCESS, 2)])
def test_tencent_start_probe_and_page_count_as_two_gets(harness, budget, status, count):
    service, _, frames = harness
    class Tencent(TxDailyClient):
        sdk_version = "1.19.1"
        def __init__(self): pass
        def fetch(self, request, *, timeout):
            for host, path in sorted(hs.SOURCES["tencent"].targets):
                requests.get("https://" + host + path, timeout=timeout)
            return frames["tencent"]
    service.sources = {"tencent": replace(service.sources["tencent"], client_factory=Tencent)}
    result = service.check("tencent", CheckType.MARKET_DATA, network_enabled=True,
                           max_requests=budget, request=REQUEST, expectation=KNOWN)
    assert result.status == status and result.request_count == count
    assert result.details_redacted["sdk_calls"] == 1
    if budget == 1:
        assert result.dataframe_rows is None and result.db_write_status == "not_run"


def test_reports_do_not_let_configuration_success_reset_market_failures(harness):
    service, state, _ = harness
    state["status"] = 500
    failed = market(service)
    failed2 = replace(failed, check_id="later-failure", finished_at="2026-10-18T00:00:01+00:00")
    configured = replace(service.check("eastmoney"), finished_at="2026-10-18T00:00:02+00:00")
    report = source_report("eastmoney", [failed, failed2, configured])
    assert report["consecutive_market_failures"] == 2
    assert report["state"] == "current_check_chain_unavailable"
    assert report["last_market_success_at"] is None


@pytest.mark.parametrize("cadence", ["daily", "weekly", "monthly"])
def test_schedule_is_plan_only(cadence):
    plan = schedule_plan(cadence)
    assert plan["automatic_network_requests"] == 0 and not plan["installed_scheduler"]
    assert plan["calendar_status"] == "unknown"

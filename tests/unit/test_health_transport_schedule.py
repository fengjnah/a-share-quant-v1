"""Offline send-boundary, persistence and calendar-adapter controls."""

from dataclasses import replace
from types import SimpleNamespace

import pytest
import requests

from ai_trade.market_data.health_cli import main
from ai_trade.market_data.health_models import CalendarExpectation, CheckType, HealthResult, HealthStatus
from ai_trade.market_data.health_schedule import HealthResultStore, calendar_expectation, source_report
from ai_trade.market_data.health_schedule import compare_saved_records
from ai_trade.data_access.models import DuplicateRecordError
from ai_trade.market_data.health_transport import BudgetBlocked, HealthTransport
from ai_trade.reference_data.models import CalendarDataMissingError, CalendarSourceError


TARGET = "https://push2his.eastmoney.com/api/qt/stock/kline/get"
ALLOWED = frozenset({("push2his.eastmoney.com", "/api/qt/stock/kline/get")})


@pytest.fixture
def adapter(monkeypatch):
    calls = []
    def send(instance, prepared, **kwargs):
        calls.append((prepared.method, dict(prepared.headers), prepared.url, kwargs,
                      instance.max_retries.total))
        response = requests.Response()
        response.status_code = 200
        response._content = b'{}'
        response._content_consumed = True
        response.request = prepared
        return response
    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    return calls


def test_budget_preserves_request_parameters_headers_and_stops_second_send(adapter):
    trace = HealthTransport(ALLOWED, 1, 3)
    with trace.installed():
        requests.get(TARGET, params={"secid": "1.600000"}, headers={"X-Test": "same"})
        with pytest.raises(BudgetBlocked):
            requests.get(TARGET)
    assert trace.count == 1 and trace.blocked
    assert len(adapter) == 1 and adapter[0][1]["X-Test"] == "same"
    assert adapter[0][2].endswith("?secid=1.600000")
    assert adapter[0][3]["timeout"] == 3 and adapter[0][4] == 0


def test_identical_sdk_retry_is_blocked_even_with_budget_remaining(adapter):
    trace = HealthTransport(ALLOWED, 3, 3)
    with trace.installed():
        requests.get(TARGET)
        with pytest.raises(BudgetBlocked):
            requests.get(TARGET)
    assert trace.count == len(adapter) == 1


@pytest.mark.parametrize("url,kwargs", [("https://unapproved.example/path", {}),
                                        (TARGET, {"verify": False}),
                                        (TARGET.replace("https://", "http://"), {})])
def test_unapproved_targets_or_insecure_tls_are_blocked(adapter, url, kwargs):
    trace = HealthTransport(ALLOWED, 1, 2)
    with trace.installed(), pytest.raises(BudgetBlocked):
        requests.get(url, **kwargs)
    assert trace.count == 0 and adapter == []


def test_retry_policy_and_hooks_restore_on_exception(monkeypatch):
    def fail(instance, prepared, **kwargs):
        assert instance.max_retries.total == instance.max_retries.read == 0
        raise requests.ConnectionError("secret proxy URL must not be logged")
    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", fail)
    old_session, old_adapter = requests.Session.send, requests.adapters.HTTPAdapter.send
    trace = HealthTransport(ALLOWED, 1, 3)
    with pytest.raises(requests.ConnectionError), trace.installed():
        requests.get(TARGET)
    assert requests.Session.send is old_session and requests.adapters.HTTPAdapter.send is old_adapter
    with HealthTransport(ALLOWED, 1, 3).installed():
        pass  # the serial lock was also released


def test_redirect_is_http_failure_without_following(monkeypatch):
    calls = []
    def redirect(instance, prepared, **kwargs):
        calls.append(prepared.url)
        response = requests.Response()
        response.status_code = 302
        response._content = b''
        response._content_consumed = True
        response.headers["Location"] = "https://unapproved.example/path"
        return response
    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", redirect)
    trace = HealthTransport(ALLOWED, 3, 3)
    with trace.installed(), pytest.raises(requests.HTTPError):
        requests.get(TARGET)
    assert len(calls) == trace.count == 1 and trace.responses == [302]


def test_parallel_health_context_forbidden():
    with HealthTransport(ALLOWED, 1, 3).installed():
        with pytest.raises(BudgetBlocked), HealthTransport(ALLOWED, 1, 3).installed():
            pass


@pytest.mark.parametrize("verified,warnings,status", [(False, (), "unknown"),
        (True, ("synthetic evidence: not verified real-source data",), "unknown"),
        (True, (), "known")])
def test_calendar_uses_explicit_bounded_as_of_query(verified, warnings, status):
    calls = []
    class Calendar:
        def previous_known_trading_day(self, **kwargs):
            calls.append(kwargs)
            return SimpleNamespace(value=SimpleNamespace(session_date="2026-10-16"),
                    data_snapshot_id="fixture:calendar", warnings=warnings, complete=True)
    result = calendar_expectation(Calendar(), verified=verified, exchange="SH",
                    completed_through="2026-10-18", search_start="2026-10-14",
                    as_of="2026-10-18T08:00:00+00:00")
    assert result.status == status
    if verified:
        assert calls == [{"exchange": "SH", "before": "2026-10-19", "search_start": "2026-10-14",
                          "as_of": "2026-10-18T08:00:00+00:00", "mode": "strict_backtest"}]
    else:
        assert calls == []


@pytest.mark.parametrize("error,status", [(CalendarDataMissingError, "unknown"),
                                         (CalendarSourceError, "source_error")])
def test_calendar_errors_not_treated_as_closed_days(error, status):
    class Calendar:
        def previous_known_trading_day(self, **kwargs):
            raise error("fixture")
    assert calendar_expectation(Calendar(), verified=True, exchange="SH", completed_through="2026-10-18",
                    search_start="2026-10-14", as_of="2026-10-18T08:00:00+00:00").status == status


def test_calendar_does_not_expect_future_sessions():
    assert calendar_expectation(object(), verified=True, exchange="SH", completed_through="2026-10-19",
                    search_start="2026-10-14", as_of="2026-10-18T08:00:00+00:00").status == "unknown"


def test_store_is_append_only_and_partial_records_are_not_healthy(tmp_path):
    value = HealthResult("fixture", "tencent", "akshare.stock_zh_a_hist_tx",
                         "2026-10-18T08:00:00+08:00", "2026-10-18T08:01:00+08:00",
                         CheckType.CONFIGURATION, HealthStatus.SUCCESS)
    store = HealthResultStore(tmp_path / "health")
    path = store.append(value)
    assert store.read_all() == [value]
    with pytest.raises(DuplicateRecordError):
        store.append(value)
    path.joinpath("result.json").unlink()  # controlled test fixture failure
    with pytest.raises(ValueError):
        store.read_all()


def test_results_reject_credential_details_and_false_zero_counts():
    args = dict(check_id="fixture", source_id="tencent", interface_id="akshare.stock_zh_a_hist_tx",
                started_at="2026-10-18T00:00:00Z", finished_at="2026-10-18T00:01:00Z",
                check_type="market_data_check", status="network_error")
    with pytest.raises(ValueError):
        HealthResult(**args, details_redacted={"reason": "https://user:password@example/"})
    with pytest.raises(ValueError):
        HealthResult(**args, dataframe_rows=0)


def test_cli_default_market_check_is_disabled_and_reportable(tmp_path, capsys):
    args = ["--source", "tencent", "--audit-root", str(tmp_path / "reports"),
            "--check-type", "market_data_check"]
    assert main(args) == 2
    output = capsys.readouterr().out
    assert '"dataframe_rows": null' in output and '"request_count": 0' in output
    assert '"state": "current_status_unknown"' in output
    assert main(["--source", "tencent", "--audit-root", str(tmp_path / "reports"), "--report-only"]) == 0


def test_offline_cross_source_comparison_never_selects_a_winner(bar):
    result = compare_saved_records([replace(bar, source="synthetic:left:v1")],
                                  [replace(bar, source="synthetic:right:v1", volume=bar.volume + 1)])
    assert result["differences"] == [{"trade_date": bar.trade_date, "adjustment_method": "none", "fields": ["volume"]}]
    assert result["resolution"] == "manual_review_no_source_selected"
    assert compare_saved_records([bar], [])["left_only"] == 1
    with pytest.raises(ValueError):
        compare_saved_records([bar, bar], [bar])


def test_cli_audit_failure_retains_database_commit_marker(monkeypatch, tmp_path, capsys):
    from ai_trade.market_data import health_cli
    value = HealthResult("fixture", "eastmoney", "akshare.stock_zh_a_hist",
                         "2026-10-18T00:00:00Z", "2026-10-18T00:01:00Z",
                         CheckType.MARKET_DATA, HealthStatus.UNKNOWN, dataframe_rows=1,
                         db_write_status="committed", db_rows_inserted=1)
    monkeypatch.setattr(health_cli.HealthService, "check", lambda *a, **k: value)
    def failed_append(*args):
        raise OSError("password must not escape")
    monkeypatch.setattr(HealthResultStore, "append", failed_append)
    assert main(["--source", "eastmoney", "--audit-root", str(tmp_path)]) == 2
    out = capsys.readouterr().out
    assert '"db_write_status": "committed"' in out and '"db_rows_inserted": 1' in out
    assert "password" not in out

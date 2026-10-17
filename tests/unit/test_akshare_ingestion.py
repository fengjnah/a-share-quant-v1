"""Synthetic SDK responses only. No AKShare import or network is needed."""

import hashlib
import json
import socket
from http.client import RemoteDisconnected
from dataclasses import replace
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from requests import Response
from requests.exceptions import HTTPError, Timeout, ConnectionError, JSONDecodeError
from urllib3.exceptions import ProtocolError

from ai_trade.data_access.models import DataUnavailableError, DuplicateRecordError, ValidationError
from ai_trade.market_data.akshare_adapter import AkshareDailyClient, check_frame, map_frame
from ai_trade.market_data.evidence import EvidenceStore
from ai_trade.market_data.ingestor import DailyHistoryIngestor, _transport_type_chain
from ai_trade.market_data.models import (
    DailyHistoryRequest, EvidenceWriteError, IngestionStatus, SourceSchemaError,
)


@pytest.fixture
def frame():
    path = Path(__file__).parents[1] / "fixtures" / "akshare_daily.json"
    return pd.DataFrame(json.loads(path.read_text(encoding="utf-8")))


@pytest.fixture
def history_request():
    return DailyHistoryRequest("listing:synthetic:1", "600000.SH", "2026-10-14", "2026-10-15", "none")


class FakeClient:
    sdk_version = "fixture-v1"

    def __init__(self, frame):
        self.frame = frame
        self.error = None
        self.calls = []

    def fetch(self, request, *, timeout):
        self.calls.append((request, timeout))
        if self.error:
            raise self.error
        return self.frame


class Clock:
    def __init__(self):
        self.now = datetime(2026, 10, 17, 8, tzinfo=timezone.utc)

    def __call__(self):
        value = self.now
        self.now += timedelta(seconds=1)
        return value


@pytest.fixture
def harness(frame, repository, tmp_path):
    client = FakeClient(frame)
    evidence = EvidenceStore(tmp_path / "evidence")
    service = DailyHistoryIngestor(client, repository, evidence, clock=Clock())
    return service, client, evidence


def read_evidence(result, name):
    return json.loads((Path(result.evidence_directory) / name).read_text(encoding="utf-8"))


def row_count(database):
    with database.connection() as conn:
        return conn.execute("SELECT count(*) FROM daily_bar_versions").fetchone()[0]


def test_mapping_units_timestamps_lineage_and_real_writer(harness, history_request, database, repository):
    service, client, _ = harness
    result = service.collect(history_request, run_id="success")
    assert result.status == IngestionStatus.SUCCESS
    assert result.inserted_rows == result.returned_rows == 2
    first = result.records[0]
    assert (first.open, first.high, first.low, first.close, first.volume, first.amount) == (10, 12, 9, 11, 12300, 135300)
    assert first.event_time == "2026-10-14T07:00:00.000000+00:00"
    assert first.available_at == result.observed_at == "2026-10-17T08:00:01.000000+00:00"
    assert first.ingested_at == result.validated_at == "2026-10-17T08:00:02.000000+00:00"
    assert first.adjustment_method == "none" and first.factor_version is None
    assert "stock_zh_a_hist" in first.source and "fixture-v1" in first.source
    assert first.source_version.startswith("row-sha256:")
    arguments = dict(instrument_id=first.instrument_id, trade_date=first.trade_date,
                     source=first.source, adjustment_method="none", mode="strict_backtest")
    with pytest.raises(DataUnavailableError):
        repository.get_bar(**arguments, as_of="2026-10-15T16:00:00+08:00")
    with pytest.raises(DataUnavailableError):
        repository.get_bar(**arguments, as_of=result.observed_at)
    assert repository.get_bar(**arguments, as_of=result.validated_at).bar == first
    request = read_evidence(result, "request.json")
    assert request["availability_policy"].startswith("observed_on_fetch")
    assert request["parameters"]["adjust"] == "" and request["run_id"] == "success"
    payload = (Path(result.evidence_directory) / "response.json").read_bytes()
    assert hashlib.sha256(payload).hexdigest() == result.response_sha256
    assert read_evidence(result, "response.json")["not_raw_http"] is True
    assert read_evidence(result, "result.json")["status"] == "success"
    assert row_count(database) == 2 and len(client.calls) == 1


def test_repeat_payload_is_explicit_duplicate_and_both_attempts_retained(harness, history_request, database):
    service, _, _ = harness
    first = service.collect(history_request, run_id="first")
    second = service.collect(history_request, run_id="retry")
    assert second.status == IngestionStatus.DUPLICATE
    assert second.inserted_rows == 0 and second.records == ()
    assert first.response_sha256 == second.response_sha256
    assert first.evidence_directory != second.evidence_directory
    assert read_evidence(second, "result.json")["status"] == "duplicate"
    assert row_count(database) == 2


def test_same_run_id_cannot_overwrite_evidence(harness, history_request):
    service, client, _ = harness
    result = service.collect(history_request, run_id="same-run")
    before = (Path(result.evidence_directory) / "result.json").read_bytes()
    with pytest.raises(DuplicateRecordError, match="run_id"):
        service.collect(history_request, run_id="same-run")
    assert len(client.calls) == 1
    assert (Path(result.evidence_directory) / "result.json").read_bytes() == before


@pytest.mark.parametrize("changed", [False, True])
def test_duplicate_dates_in_response_are_not_selected(harness, history_request, database, changed):
    service, client, _ = harness
    extra = client.frame.iloc[[0]].copy()
    if changed:
        extra["收盘"] = 10.5
    client.frame = pd.concat([client.frame, extra], ignore_index=True)
    result = service.collect(history_request, run_id="duplicates")
    assert result.status == IngestionStatus.DUPLICATE and result.inserted_rows == 0
    assert row_count(database) == 0


def test_changed_existing_prices_require_explicit_revision_review(harness, history_request, database):
    service, client, _ = harness
    service.collect(history_request, run_id="first")
    client.frame.loc[0, "收盘"] = 10.5
    result = service.collect(history_request, run_id="changed")
    assert result.status == IngestionStatus.CONFLICT and row_count(database) == 2


@pytest.mark.parametrize(("column", "value"), [
    ("开盘", -1), ("最高", 8), ("最低", 20), ("收盘", 0), ("收盘", float("nan")),
    ("收盘", float("inf")), ("开盘", "10.0"), ("成交量", -1), ("成交量", 0.001),
    ("成交量", 10**18), ("成交量", float("inf")), ("成交额", -1), ("成交额", float("nan")),
    ("日期", "2026-02-30"), ("日期", "2026-10-13"), ("日期", None),
    ("股票代码", "000001"), ("股票代码", None), ("股票代码", 600000),
])
def test_invalid_data_rejects_whole_response(harness, history_request, database, column, value):
    service, client, _ = harness
    client.frame = client.frame.astype(object)
    client.frame.loc[1, column] = value  # A valid earlier row must not leak into the database.
    result = service.collect(history_request, run_id="invalid")
    assert result.status == IngestionStatus.VALIDATION_ERROR
    assert result.issues and result.inserted_rows == 0 and row_count(database) == 0
    assert (Path(result.evidence_directory) / "response.json").is_file()


@pytest.mark.parametrize("mutation", ["missing", "renamed", "added", "duplicate", "not_frame", "empty_changed_schema"])
def test_schema_drift_is_distinct(harness, history_request, database, mutation):
    service, client, _ = harness
    if mutation == "missing":
        client.frame = client.frame.drop(columns=["成交额"])
    elif mutation == "renamed":
        client.frame = client.frame.rename(columns={"收盘": "close"})
    elif mutation == "added":
        client.frame["unknown_column"] = 1
    elif mutation == "duplicate":
        client.frame = pd.concat([client.frame, client.frame[["收盘"]]], axis=1)
    elif mutation == "not_frame":
        client.frame = [{"close": 1}]
    else:
        client.frame = pd.DataFrame(columns=["unexpected"])
    result = service.collect(history_request, run_id="schema")
    assert result.status == IngestionStatus.SCHEMA_ERROR
    assert row_count(database) == 0


@pytest.mark.parametrize("keep_schema", [False, True])
def test_empty_is_not_success(harness, history_request, database, keep_schema):
    service, client, _ = harness
    client.frame = client.frame.iloc[:0] if keep_schema else pd.DataFrame()
    result = service.collect(history_request, run_id="empty")
    assert result.status == IngestionStatus.EMPTY_RESPONSE
    assert result.returned_rows == result.inserted_rows == row_count(database) == 0
    assert result.response_sha256 and result.observed_at and result.validated_at is None


@pytest.mark.parametrize("failure", [Timeout("timeout"), ConnectionError("offline"), TimeoutError("timeout")])
def test_network_error_has_evidence_but_no_rows(harness, history_request, database, failure):
    service, client, _ = harness
    client.error = failure
    result = service.collect(history_request, run_id="network")
    assert result.status == IngestionStatus.NETWORK_ERROR
    assert result.observed_at is None and result.response_sha256 is None
    assert row_count(database) == 0
    assert read_evidence(result, "result.json")["status"] == "network_error"


def test_transport_failure_keeps_safe_type_chain_without_secrets(harness, history_request, database):
    service, client, _ = harness
    secret = "https://proxy-user:proxy-password@proxy.example/path?token=hidden"
    remote = RemoteDisconnected(secret)
    protocol = ProtocolError(secret)
    protocol.__context__ = remote
    failure = ConnectionError(secret)
    failure.__cause__ = protocol
    client.error = failure

    result = service.collect(history_request, run_id="safe-network-diagnostic")
    saved = read_evidence(result, "result.json")
    assert result.status == IngestionStatus.NETWORK_ERROR
    assert result.observed_at is None and result.response_sha256 is None
    assert result.inserted_rows == row_count(database) == 0
    assert not (Path(result.evidence_directory) / "response.json").exists()
    assert "cause_types=ConnectionError > ProtocolError > RemoteDisconnected" in result.issues[0]
    assert "failure_stage=sdk_fetch_transport; network_phase=undetermined" in result.issues[0]
    assert saved["issues"] == list(result.issues)
    assert secret not in json.dumps(saved) and "proxy-password" not in json.dumps(saved)


def test_transport_type_chain_masks_unrecognized_exception_names():
    unknown = type("CredentialLikeName", (Exception,), {})("private-token")
    failure = ConnectionError("transport failed")
    failure.__cause__ = unknown
    assert _transport_type_chain(failure) == "ConnectionError > OtherError"


@pytest.mark.parametrize("code", [429, 403, 500])
def test_proven_rate_limit_is_not_guessed_from_other_http_codes(harness, history_request, code):
    service, client, _ = harness
    response = Response()
    response.status_code = code
    response.headers["Retry-After"] = "60"
    client.error = HTTPError(response=response)
    result = service.collect(history_request, run_id="http")
    expected = IngestionStatus.RATE_LIMITED if code == 429 else IngestionStatus.NETWORK_ERROR
    assert result.status == expected and result.http_status == code
    assert result.retry_after == "60" and len(client.calls) == 1


@pytest.mark.parametrize("failure", [JSONDecodeError("bad JSON", "<html>", 0), KeyError("data"), ValueError("invalid payload")])
def test_ambiguous_response_is_not_claimed_as_a_field_change_or_limit(harness, history_request, failure):
    service, client, _ = harness
    client.error = failure
    result = service.collect(history_request, run_id="ambiguous")
    assert result.status == IngestionStatus.RESPONSE_ERROR
    assert result.http_status is None


@pytest.mark.parametrize("changes", [
    {"adjustment_method": "qfq"}, {"adjustment_method": "hfq"}, {"adjustment_method": ""},
    {"symbol": "600000"}, {"symbol": "000001.SH"}, {"symbol": "920001.BJ"},
    {"symbol": "510300.SH"}, {"instrument_id": ""}, {"end_date": "2026-10-17"},
    {"end_date": "2026-10-18"}, {"start_date": "2026-10-16"}, {"start_date": "20261014"},
])
def test_invalid_request_never_calls_sdk(harness, history_request, changes):
    service, client, evidence = harness
    with pytest.raises(ValidationError):
        service.collect(replace(history_request, **changes), run_id="invalid-request")
    assert client.calls == [] and not evidence.root.exists()


def test_out_of_order_rows_and_date_objects_are_normalized(harness, history_request):
    service, client, _ = harness
    client.frame["日期"] = [date(2026, 10, 14), date(2026, 10, 15)]
    client.frame = client.frame.iloc[::-1]
    result = service.collect(history_request, run_id="dates")
    assert [bar.trade_date for bar in result.records] == ["2026-10-14", "2026-10-15"]


def test_run_id_cannot_escape_evidence_root(harness, history_request):
    service, _, evidence = harness
    result = service.collect(history_request, run_id="../outside")
    assert Path(result.evidence_directory).parent == evidence.root


@pytest.mark.parametrize("stage", ["request", "response", "result"])
def test_evidence_failure_never_falsely_claims_database_rollback(harness, history_request, database, monkeypatch, stage):
    service, _, evidence = harness
    original = evidence._write
    def failing(path, payload):
        if path.name == stage + ".json":
            raise OSError("synthetic disk failure")
        original(path, payload)
    monkeypatch.setattr(evidence, "_write", failing)
    with pytest.raises(EvidenceWriteError) as error:
        service.collect(history_request, run_id="disk")
    assert error.value.database_committed is (stage == "result")
    assert row_count(database) == (2 if stage == "result" else 0)


def test_unexpected_programming_failure_is_not_hidden(harness, history_request):
    service, client, _ = harness
    client.error = RuntimeError("unexpected failure")
    with pytest.raises(RuntimeError, match="unexpected"):
        service.collect(history_request, run_id="unexpected")


def test_unit_network_guard_is_active():
    with pytest.raises(AssertionError, match="must not access"):
        socket.create_connection(("example.invalid", 443))


def test_sdk_calls_only_reviewed_endpoint_with_explicit_parameters(monkeypatch, frame, history_request):
    import ai_trade.market_data.akshare_adapter as module
    monkeypatch.setattr(module.importlib.metadata, "version", lambda name: "1.19.1")
    calls = []
    def fetch(**kwargs):
        calls.append(kwargs)
        return frame
    def load(name):
        assert name == "akshare.stock_feature.stock_hist_em"
        return SimpleNamespace(stock_zh_a_hist=fetch)
    monkeypatch.setattr(module.importlib, "import_module", load)
    client = AkshareDailyClient()
    assert client.fetch(history_request, timeout=9) is frame
    assert calls == [dict(symbol="600000", period="daily", start_date="20261014", end_date="20261015", adjust="", timeout=9)]


def test_unreviewed_sdk_version_is_rejected(monkeypatch):
    import ai_trade.market_data.akshare_adapter as module
    monkeypatch.setattr(module.importlib.metadata, "version", lambda name: "future-version")
    with pytest.raises(RuntimeError, match="not reviewed"):
        AkshareDailyClient()


@pytest.mark.parametrize("adjustment", ["qfq", "hfq", ""])
def test_low_level_entry_points_cannot_silently_ignore_adjustment(monkeypatch, frame, history_request, adjustment):
    import ai_trade.market_data.akshare_adapter as module
    monkeypatch.setattr(module.importlib.metadata, "version", lambda name: "1.19.1")
    request = replace(history_request, adjustment_method=adjustment)
    with pytest.raises(ValidationError, match="adjustment_method"):
        AkshareDailyClient().fetch(request, timeout=10)
    with pytest.raises(ValidationError, match="adjustment_method"):
        map_frame(frame, request, source="synthetic:daily:v1", observed_at="2026-10-17T08:00:00Z")


def test_clock_failure_after_commit_is_explicit(harness, history_request, database):
    service, _, _ = harness
    start = datetime(2026, 10, 17, 8, tzinfo=timezone.utc)
    times = iter([start, start + timedelta(seconds=1), start + timedelta(seconds=2), start])
    service.clock = lambda: next(times)
    with pytest.raises(EvidenceWriteError, match="clock") as error:
        service.collect(history_request, run_id="clock")
    assert error.value.database_committed is True and row_count(database) == 2


def test_known_optional_vendor_fields_do_not_leak_to_business(harness, history_request):
    service, client, _ = harness
    client.frame = client.frame.drop(columns=["振幅", "涨跌幅", "涨跌额", "换手率"])
    result = service.collect(history_request, run_id="minimal-schema")
    assert result.status == IngestionStatus.SUCCESS and result.inserted_rows == 2
    assert not hasattr(result.records[0], "换手率")


def test_shenzhen_leading_zero_is_preserved(harness, history_request):
    service, client, _ = harness
    client.frame["股票代码"] = "000001"
    request = replace(history_request, symbol="000001.SZ")
    result = service.collect(request, run_id="sz")
    assert result.status == IngestionStatus.SUCCESS
    assert all(record.symbol == "000001.SZ" for record in result.records)


def test_missing_sdk_has_actionable_error(monkeypatch):
    import ai_trade.market_data.akshare_adapter as module
    def missing(name):
        raise module.importlib.metadata.PackageNotFoundError(name)
    monkeypatch.setattr(module.importlib.metadata, "version", missing)
    with pytest.raises(RuntimeError, match="pip install"):
        AkshareDailyClient()

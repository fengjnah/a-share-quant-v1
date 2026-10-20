"""Offline pipeline boundaries. Fixtures never certify a real source or license."""
from copy import deepcopy
import importlib.util
import json
from pathlib import Path

import jsonschema
import pandas as pd
import pytest
import requests

from ai_trade.m3_data_pipeline import build_bundle, public_summary, inventory
from ai_trade.market_data.health_transport import BudgetBlocked
from test_market_analysis_core import prices

ROOT = Path(__file__).parents[2]
spec = importlib.util.spec_from_file_location("pipeline_cli", ROOT / "scripts/verify_m3_pipeline.py")
cli = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cli)
SCHEMA = json.loads((ROOT / "docs/M3_DIAGNOSTIC_V1.schema.json").read_text(encoding="utf-8"))
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA, format_checker=jsonschema.FormatChecker())


def observation():
    f = prices(105)
    return dict(source="unit:price:v1", symbol="sh000300", trade_date=f.trade_date.iloc[-1],
        prices=f[["trade_date", "open", "high", "low", "close"]].to_dict("records"),
        observed_at="2026-10-19T08:00:00Z", ingested_at="2026-10-19T08:00:01Z", available_at=None)


def bundle(observations=None, **changes):
    values = dict(analysis_date="2026-05-29", as_of="2026-10-19T12:00:00Z", run_id="fixture-batch")
    values.update(changes)
    result = build_bundle(observations or {}, **values)
    for d in result["diagnostics"].values():
        VALIDATOR.validate(d)
    json.dumps(result, allow_nan=False)
    return result


def test_empty_sources_are_separate_blocked_core_diagnostics():
    result = bundle()
    assert set(result["diagnostics"]) == {"daily_trend", "weekly_structure", "wave", "price_proxy",
        "market_breadth", "fear_greed", "cffex_position", "environment"}
    assert all(d["admission"] == "BLOCKED" for d in result["diagnostics"].values())
    assert result["core_review"]["state"] == "PENDING"


@pytest.mark.parametrize("mode", ("research", "strict_backtest", "paper_trade"))
def test_transport_success_does_not_issue_receipts_or_hide_unknown_quality(mode):
    item = observation(); before = deepcopy(item)
    result = bundle({"sina_index": item}, mode=mode)
    d = result["diagnostics"]["daily_trend"]
    assert d["admission"] == ("L1_OBSERVATION" if mode == "research" else "BLOCKED")
    assert all(d["source"][key]["status"] == "UNKNOWN" for key in ("verification", "time_verification", "research_authorization"))
    assert "quality_status" in d["missing_fields"]
    assert d["times"]["available_at"] is None and d["coverage"]["expected_samples"] is None
    assert not d["allowed_uses"]["research"] and not d["allowed_uses"]["live_trading"]
    assert item == before


def test_legacy_observation_does_not_gain_ingestion_or_event_time():
    item = observation(); del item["ingested_at"]
    d = bundle({"sina_index": item})["diagnostics"]["daily_trend"]
    assert d["times"]["ingested_at"] is None and d["times"]["event_time"] is None
    assert set(("ingested_at", "event_time", "quality_status")).issubset(d["missing_fields"])


def test_late_acquisition_cannot_replay_old_history():
    result = bundle({"sina_index": observation()}, as_of="2026-10-18T12:00:00Z")
    assert all(d["admission"] == "BLOCKED" for d in result["diagnostics"].values())
    assert result["diagnostics"]["daily_trend"]["values"] == {}


@pytest.mark.parametrize("mutation", ("mixed_identity", "duplicate_date", "nan_price"))
def test_bad_records_propagate_without_selection_or_partial_calculation(mutation):
    item = observation()
    if mutation == "mixed_identity":
        item["prices"][50]["symbol"] = "other"
    elif mutation == "duplicate_date":
        item["prices"][50]["trade_date"] = item["prices"][49]["trade_date"]
    else:
        item["prices"][50]["close"] = None
    result = bundle({"sina_index": item})
    for name in ("daily_trend", "wave", "fear_greed", "environment"):
        d = result["diagnostics"][name]
        assert d["status"] == "INVALID_DATA" and d["admission"] == "BLOCKED"
        assert d["values"] == {} and not any(d["allowed_uses"].values())


def test_partial_breadth_and_stock_amount_cannot_make_full_score():
    item = observation()
    for row in item["prices"]:
        row["amount_cny"] = 1_000_000
    breadth = dict(source="unit:breadth:v1", trade_date=item["trade_date"], observed_at=item["observed_at"],
        ingested_at=item["ingested_at"], available_at=None,
        breadth=dict(advances=60,declines=30,flat=5,limit_up=8,limit_down=2))
    result = bundle({"sina_index": item, "legu_breadth": breadth})
    assert not result["diagnostics"]["market_breadth"]["values"]["all_a_scope_verified"]
    fg = result["diagnostics"]["fear_greed"]
    assert fg["values"]["score"] is None and fg["values"]["price_proxy"] is not None
    assert not fg["allowed_uses"]["research"]
    assert result["diagnostics"]["environment"]["values"]["conclusion"] == "数据不足"


def test_raw_cffex_csv_is_not_converted_into_a_certified_ranking_version():
    raw = dict(source="cffex:rankings:v2", trade_date="2026-10-16", raw_csv_hex="666f6f", rows=120)
    d = bundle({"cffex_rankings": raw})["diagnostics"]["cffex_position"]
    assert d["admission"] == "BLOCKED" and d["values"]["direction"] is None
    assert any(r["code"] == "SOURCE_UNAVAILABLE" for r in d["reasons"])


def test_publishable_summary_drops_all_input_and_numeric_output_values():
    result = bundle({"sina_index": observation()})
    exported = public_summary(result, {"sina_index": {"status": "PASS", "returned_rows": 105}})
    assert all("values" not in d for d in exported["diagnostics"].values())
    assert "prices" not in exported and "records" not in exported and "raw_csv_hex" not in exported
    assert exported["sources"]["sina_index"]["status"] == "PASS"
    assert exported["diagnostics"]["daily_trend"]["admission"] == "L1_OBSERVATION"


def test_default_run_never_constructs_a_client_or_starts_network_worker(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "REPO", tmp_path)
    monkeypatch.setattr(cli.subprocess, "run", lambda *a, **k: pytest.fail("offline must not start worker"))
    root = cli.run(tmp_path / "artifacts" / "audit")
    summary = json.loads((root / "summary.json").read_text(encoding="utf-8"))
    assert all(summary["sources"][key]["status"] == "NOT RUN" for key in cli.LIVE)
    assert all(summary["sources"][key]["request_count"] == 0 for key in cli.LIVE)
    assert summary["sources"]["historical_st"]["status"] == "BLOCKED"
    assert summary["execution"]["enable_live"] is False


def test_worker_requires_enable_before_directory_or_client(tmp_path):
    with pytest.raises(ValueError, match="Explicit"):
        cli.worker("sina_index", tmp_path / "never-created", "test")
    assert not (tmp_path / "never-created").exists()


def test_output_cannot_target_a_production_path(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "REPO", tmp_path / "checkout")
    with pytest.raises(ValueError, match="artifacts"):
        cli.checked_root(tmp_path / "production")


@pytest.mark.parametrize("mutation", ("second_query_same_endpoint", "wrong_host", "tls_disabled"))
def test_transport_budget_blocks_before_real_send_and_restores_patch(tmp_path, monkeypatch, mutation):
    calls = []
    def fake(adapter, request, **kwargs):
        calls.append(request.url)
        response = requests.Response(); response.status_code = 200
        response._content = b"real-transport-is-never-called"; response._content_consumed = True
        return response
    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", fake)
    url = inventory()["sina_index"]["endpoint"]
    with cli.capture_http("sina_index", tmp_path) as trace:
        if mutation == "second_query_same_endpoint":
            requests.get(url, params={"d":"first"})
            with pytest.raises(BudgetBlocked): requests.get(url, params={"d":"second"})
            assert len(trace) == 1 and len(calls) == 1
            assert trace[0]["http_status"] == 200 and trace[0]["response_bytes"] > 0
        else:
            with pytest.raises(BudgetBlocked):
                requests.get("https://unapproved.invalid/" if mutation == "wrong_host" else url,
                             verify=False if mutation == "tls_disabled" else True)
            assert not calls and not trace
    assert requests.adapters.HTTPAdapter.send is fake


def test_response_size_failure_keeps_observed_http_status(tmp_path, monkeypatch):
    def fake(*args, **kwargs):
        response=requests.Response();response.status_code=200
        response._content=b"x" * 2_000_001;response._content_consumed=True
        return response
    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", fake)
    with cli.capture_http("cffex_rankings", tmp_path) as trace:
        with pytest.raises(BudgetBlocked, match="size"):
            requests.get(inventory()["cffex_rankings"]["endpoint"])
    assert trace[0]["http_status"] == 200 and trace[0]["error_type"] == "BudgetBlocked"
    assert trace[0]["payload_sha256"] is None

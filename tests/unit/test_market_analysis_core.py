"""Offline adversarial fixtures. Verified receipts below are caller declarations
for gate testing, never acceptance of a real source, calendar or authorization.
"""
from dataclasses import replace
import json

import pandas as pd
import pytest

from ai_trade.market_analysis_contract import (
    Admission, CalendarEvidence, Coverage, Receipt, Request, SourceEvidence,
    Status, Verification, strategy_admission,
)
from ai_trade.market_analysis_core import (
    breadth_diagnostic, cffex_diagnostic, environment_diagnostic,
    fear_greed_diagnostic, price_diagnostics,
)


def receipt(*refs):
    return Receipt(Verification.VERIFIED, refs or ("unit-test-declaration",))


def source(name="unit:price:v1", **kwargs):
    return SourceEvidence(name, "unit-version-1", ("unit-snapshot-1",),
                          receipt(), receipt(), receipt(), **kwargs)


def prices(n=150):
    days = pd.bdate_range("2026-01-05", periods=n).strftime("%Y-%m-%d")
    return pd.DataFrame([dict(trade_date=d, symbol="sh000300", source="unit:price:v1",
        open=100+i, high=102+i, low=99+i, close=101+i, adjustment_method="none",
        event_time=d+"T15:00:00+08:00", observed_at=d+"T16:00:00+08:00",
        ingested_at=d+"T16:01:00+08:00", available_at=d+"T16:02:00+08:00") for i, d in enumerate(days)])


def request(f, **kwargs):
    return Request(f.trade_date.iloc[-1], "2026-10-19T12:00:00Z", "sh000300", **kwargs)


def calendar(f):
    return CalendarEvidence("CN_A", f.trade_date.iloc[0], f.trade_date.iloc[-1],
        tuple(f.trade_date), "2025-12-01T00:00:00Z", "2025-12-01T00:00:00Z", receipt("unit-calendar"))


def market(f):
    m = f[["trade_date", "event_time", "observed_at", "ingested_at", "available_at"]].copy()
    m["source"] = "unit:breadth:v1"
    for k, v in dict(advances=60, declines=30, flat=5, limit_up=8, limit_down=2,
                     eligible_count=100, suspended=5, unavailable=0, missing=0).items():
        m[k] = v
    m["universe_date"] = m.trade_date
    m["universe_snapshot_ref"] = "unit-universe:" + m.trade_date
    m["universe_available_at"] = m.available_at
    m["universe_ingested_at"] = m.ingested_at
    m["market_amount_cny"] = [1_000_000 + 100*i for i in range(len(m))]
    return m


def compute(f, **kwargs):
    return price_diagnostics(f, request=request(f), source=source(), calendar=calendar(f), **kwargs)


def codes(d):
    return {r.code.value for r in d.reasons}


def test_contract_unknown_zero_json_and_snapshot_identity():
    f = prices()
    d = compute(f)["daily_trend"]
    payload = d.to_dict()
    assert payload["schema_version"] == "m3-core-diagnostic-v1"
    assert payload["allowed_uses"] == dict(observation=True, research=True, strategy=False, live_trading=False)
    assert len(d.data_snapshot_id) == 64
    assert replace(d, values={"unknown": None, "zero": 0}).to_dict()["values"] == {"unknown": None, "zero": 0}
    assert replace(d, request=replace(d.request, as_of="2026-10-19T13:00:00Z")).data_snapshot_id != d.data_snapshot_id
    json.dumps(payload, allow_nan=False)
    from pathlib import Path
    import jsonschema
    from ai_trade.market_analysis_contract import ReasonCode
    schema = json.loads((Path(__file__).parents[2]/"docs/M3_DIAGNOSTIC_V1.schema.json").read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(payload)
    assert set(schema["properties"]["status"]["enum"]) == {s.value for s in Status}
    assert set(schema["properties"]["reasons"]["items"]["properties"]["code"]["enum"]) == {s.value for s in ReasonCode}
    with pytest.raises(ValueError):
        Receipt("VERIFIED", ("unchecked",))
    with pytest.raises(ValueError):
        Coverage(5, 4, "bad", ("ref",))


@pytest.mark.parametrize("n,ready", [(59, False), (60, True)])
def test_daily_exact_minimum(n, ready):
    d = compute(prices(n))["daily_trend"]
    assert d.calculated == ready
    assert (d.admission is Admission.L2) == ready
    assert (d.values["MA60"] is not None) == ready


@pytest.mark.parametrize("n,ready", [(99, False), (101, True)])
def test_weekly_closed_minimum_ohlc(n, ready):
    f = prices(n)
    d = compute(f)["weekly_structure"]
    assert d.calculated == ready
    assert d.values["partial_current_week_used"] is False
    first = d.values["weeks"][0]
    assert (first["open"], first["high"], first["low"], first["close"]) == (100, 106, 99, 105)
    assert all(w["last_date"] < pd.Period(request(f).analysis_date, freq="W-SUN").start_time.date().isoformat() for w in d.values["weeks"])


def test_partial_first_week_is_excluded():
    f = prices(102).iloc[2:].reset_index(drop=True)
    d = compute(f)["weekly_structure"]
    assert d.coverage.valid_samples == 19
    assert not d.calculated
    full = prices(102)
    d = price_diagnostics(f, request=request(f), source=source(), calendar=calendar(full))["weekly_structure"]
    assert d.coverage.valid_samples == 19 and not d.calculated


def test_missing_calendar_session_stale_and_no_fake_denominator():
    f = prices()
    cal = calendar(f)
    missing = f.iloc[30].trade_date
    g = f.drop(index=30)
    d = price_diagnostics(g, request=request(f), source=source(), calendar=cal)["daily_trend"]
    assert d.coverage.ratio == 149/150 and d.coverage.missing_dates == (missing,)
    assert d.admission is Admission.L1
    d = price_diagnostics(f.iloc[:-1], request=request(f), source=source(), calendar=cal)["daily_trend"]
    assert d.status is Status.STALE and d.data_latest_date == f.trade_date.iloc[-2]
    d = price_diagnostics(f, request=request(f), source=source())["daily_trend"]
    assert d.coverage.ratio is None and "CALENDAR_UNKNOWN" in codes(d)


@pytest.mark.parametrize("column", ["observed_at", "available_at", "ingested_at"])
def test_late_capture_does_not_enter_historical_as_of(column):
    f = prices()
    f.loc[f.index[-1], column] = "2026-10-20T12:00:00Z"
    # Keep timestamp ordering valid; test visibility rather than invalid ordering.
    if column == "observed_at":
        f.loc[f.index[-1], "ingested_at"] = "2026-10-20T12:01:00Z"
    d = compute(f)["daily_trend"]
    assert d.data_latest_date == f.trade_date.iloc[-2]
    assert d.values["close"] == f.close.iloc[-2]
    assert d.status is Status.STALE


@pytest.mark.parametrize("mutation", ["bad_date", "duplicate", "mixed_symbol", "negative_price", "bad_event", "naive_time", "mixed_source"])
def test_invalid_input_fail_closed(mutation):
    f = prices()
    if mutation == "bad_date": f.loc[0, "trade_date"] = "2026-02-30"
    if mutation == "duplicate": f.loc[1, "trade_date"] = f.trade_date.iloc[0]
    if mutation == "mixed_symbol": f.loc[0, "symbol"] = "sh000001"
    if mutation == "negative_price": f.loc[0, "close"] = -1
    if mutation == "bad_event": f.loc[0, "event_time"] = "2026-01-04T15:00:00+08:00"
    if mutation == "naive_time": f.loc[0, "observed_at"] = "2026-01-05T16:00:00"
    if mutation == "mixed_source": f.loc[0, "source"] = "other"
    # Calendar built before mutation only where its date validator would reject.
    d = price_diagnostics(f, request=Request("2026-07-31", "2026-10-19T12:00:00Z", "sh000300"), source=source())["wave"]
    assert d.status is Status.INVALID_DATA and d.values == {} and d.admission is Admission.BLOCKED


def test_no_data_and_uncertified_historical_time_modes():
    f = prices()
    empty = price_diagnostics(pd.DataFrame(), request=request(f), source=source())["daily_trend"]
    assert empty.status is Status.SOURCE_UNAVAILABLE
    g = f.drop(columns=["available_at", "ingested_at"])
    d = compute(g)["daily_trend"]
    assert d.times["available_at"] is None and d.admission is Admission.L1
    strict = price_diagnostics(g, request=request(f, mode="strict_backtest"), source=source(), calendar=calendar(f))["daily_trend"]
    assert strict.admission is Admission.BLOCKED and strict.values == {}
    with pytest.raises(ValueError):
        Request("2026-10-20", "2026-10-19T00:00:00Z", "sh000300")


def test_right_confirmation_and_prefix_replay():
    f = prices(70)
    f.loc[60, "high"] = 400
    early = price_diagnostics(f.iloc[:63], request=request(f.iloc[:63]), source=source(), calendar=calendar(f))["wave"]
    late = price_diagnostics(f.iloc[:64], request=request(f.iloc[:64]), source=source(), calendar=calendar(f))["wave"]
    assert not any(p["trade_date"] == f.trade_date.iloc[60] for p in early.values["pivots"])
    p = next(p for p in late.values["pivots"] if p["trade_date"] == f.trade_date.iloc[60])
    assert p["confirmed_date"] == f.trade_date.iloc[63]
    assert p["first_usable_at"] == "2026-04-02T08:02:00.000000+00:00"
    assert len(p["confirmation_input_dates"]) == 7
    # Appending unknown future bars cannot change a historical analysis.
    replay = price_diagnostics(f, request=request(f.iloc[:64]), source=source(), calendar=calendar(f))["wave"]
    assert replay.values == late.values


def test_breadth_denominator_partition_and_dated_universe():
    f = prices(2); m = market(f)
    req = replace(request(f), symbol="ALL_A", instrument_type="ALL_A")
    d = breadth_diagnostic(m, request=req, source=source("unit:breadth:v1"), calendar=calendar(f), universe_receipt=receipt(*m.universe_snapshot_ref))
    assert d.admission is Admission.L2
    assert d.values["universe_coverage"][-1]["numerator"] == 100
    assert d.values["universe_coverage"][-1]["denominator"] == 100
    assert d.values["universe_coverage"][-1]["quoted_denominator"] == 95
    bad = m.copy(); bad.loc[0, "universe_date"] = f.trade_date.iloc[-1]
    d = breadth_diagnostic(bad, request=req, source=source("unit:breadth:v1"), universe_receipt=receipt(*m.universe_snapshot_ref))
    assert d.status is Status.INVALID_DATA
    small = m.copy(); small["eligible_count"] = 1000; small["missing"] = 900
    d = breadth_diagnostic(small, request=req, source=source("unit:breadth:v1"), calendar=calendar(f), universe_receipt=receipt(*m.universe_snapshot_ref))
    assert d.values["universe_coverage"][-1]["ratio"] == .1
    assert d.admission is Admission.L1


@pytest.mark.parametrize("mutation", ["denominator", "identity", "future_universe", "missing_count", "negative", "partition"])
def test_breadth_missing_bad_or_future_universe_never_qualifies(mutation):
    f = prices(2); m = market(f)
    if mutation == "denominator": m = m.drop(columns=["eligible_count"])
    if mutation == "identity": m["universe_snapshot_ref"] = "unbound-ref"
    if mutation == "future_universe": m["universe_available_at"] = "2027-01-01T00:00:00Z"
    if mutation == "missing_count": m = m.drop(columns=["flat"])
    if mutation == "negative": m["advances"] = -1
    if mutation == "partition": m["eligible_count"] = 101
    d = breadth_diagnostic(m, request=replace(request(f), instrument_type="ALL_A"), source=source("unit:breadth:v1"), calendar=calendar(f), universe_receipt=receipt("unit-universe:"+f.trade_date.iloc[0]))
    assert d.admission is not Admission.L2
    assert not d.values.get("all_a_scope_verified")


def test_full_six_factors_and_proxy_separate_and_exact_formula():
    f = prices(90); m = market(f)
    d = fear_greed_diagnostic(f, request=request(f), source=source(), calendar=calendar(f), market_frame=m,
                             market_source=source("unit:breadth:v1"), universe_receipt=receipt(*m.universe_snapshot_ref))
    assert d.admission is Admission.L2 and d.values["experimental"]
    assert d.values["score"] == pytest.approx(sum(d.values["factors"][k]*w for k, w in d.values["weights"].items()))
    assert d.values["factor_weight_coverage"] == 1
    assert d.values["market_snapshot_id"]
    f["amount_cny"] = 1_000_000
    missing = fear_greed_diagnostic(f, request=request(f), source=source(), calendar=calendar(f))
    assert missing.values["score"] is None and missing.values["percentile"] is None
    assert missing.values["price_proxy"] is not None
    assert set(missing.values["missing_factors"]) == {"上涨占比", "涨停占比", "成交额"}
    assert missing.admission is Admission.L1


@pytest.mark.parametrize("field", ["advances", "limit_up", "market_amount_cny"])
def test_any_missing_market_factor_nulls_full_score(field):
    f = prices(90); m = market(f).drop(columns=[field])
    d = fear_greed_diagnostic(f, request=request(f), source=source(), calendar=calendar(f), market_frame=m,
                             market_source=source("unit:breadth:v1"), universe_receipt=receipt(*m.universe_snapshot_ref))
    assert d.values["score"] is None and not d.calculated


def test_percentile_excludes_current_and_future():
    from ai_trade.market_analysis import past_percentile
    s = pd.Series([10.0]*20+[20.0, -100.0])
    assert past_percentile(s).iloc[20] == 100
    assert past_percentile(s.iloc[:21]).iloc[-1] == 100
    f = prices(91)
    a = compute(f.iloc[:90])["price_proxy"].values
    b = price_diagnostics(f, request=request(f.iloc[:90]), source=source(), calendar=calendar(f))["price_proxy"].values
    assert a == b


def cffex_fixture():
    from test_cffex_rankings import _build, _req, named
    record = _build(_req("IF"), named(), run_id="synthetic-core", observed_at="2026-10-16T08:35:00Z", ingested_at="2026-10-16T08:35:00Z")
    req = Request("2026-10-16", "2026-10-19T12:00:00Z", "IF2611", "CFFEX")
    src = SourceEvidence(record.source, record.source_version, (record.source_version,), receipt(), receipt(), receipt(), evidence_kind="synthetic")
    cal = CalendarEvidence("CFFEX", "2026-10-16", "2026-10-16", ("2026-10-16",), "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z", receipt("synthetic-calendar"))
    return record, req, src, cal


def test_cffex_arithmetic_scope_contract_zero_unknown_and_expiry():
    from ai_trade.market_data.cffex_rankings_models import MemberScope
    record, req, src, cal = cffex_fixture()
    def run(member, contract="IF2611", scope=MemberScope.AGENT):
        return cffex_diagnostic([record], request=replace(req, symbol=contract), source=src, member=member, scope=scope, calendar=cal)
    d = run("甲会员(代客)")
    assert d.values["net"] == 1000 and d.values["net_change"] == -4287
    assert d.values["direction"] is None and "PUBLICATION_UNKNOWN" in codes(d)
    assert d.values["expiry_month"] == "2026-11" and d.values["rollover"] == "UNKNOWN"
    assert run("甲会员(代客)", "IF2610").values["net"] == 0
    assert run("单侧多(代客)").values["net"] is None
    assert run("甲会员(代客)", scope=MemberScope.PROPRIO).values["net"] is None
    assert run("甲会员(代客)", scope=MemberScope.AGENT_AND_PROPRIO).admission is Admission.BLOCKED
    assert run("甲会员(代客)", "IH2611").status is Status.INVALID_DATA
    assert cffex_diagnostic([record], request=replace(req, as_of="2026-10-16T09:00:00Z"), source=src, member="甲会员(代客)", scope=MemberScope.AGENT).admission is Admission.BLOCKED


def test_cffex_requires_publication_scope_and_calendar_before_direction():
    from ai_trade.market_data.cffex_rankings_models import MemberScope
    r, req, src, cal = cffex_fixture()
    # Simulate caller assertions, not real data acceptance.
    r = replace(r, evidence_kind="source_observation", publication_time="2026-10-16T08:00:00Z")
    src = replace(src, evidence_kind="source_observation")
    params = dict(request=req, source=src, member="甲会员(代客)", scope=MemberScope.AGENT,
                  calendar=cal, scope_receipt=receipt("scope"), publication_receipt=receipt("publication"))
    assert cffex_diagnostic([r], **params).values["direction"] == "偏多"
    params["calendar"] = None
    assert cffex_diagnostic([r], **params).values["direction"] is None
    params["calendar"] = cal; params["publication_receipt"] = Receipt()
    assert cffex_diagnostic([r], **params).values["direction"] is None


def test_environment_conflict_missing_and_snapshot_mismatch():
    f = prices(); p = compute(f); req = request(f)
    wave = p["wave"]
    # Test aggregate policy with explicitly constructed component diagnostics.
    fut = replace(wave, indicator="cffex_position", values={"direction": "偏空"})
    fg = replace(wave, indicator="fear_greed", values={"score": 80})
    d = environment_diagnostic(dict(cffex_position=fut, wave=wave, fear_greed=fg), request=req)
    assert d.values["conclusion"] == "证据冲突" and d.status is Status.EVIDENCE_CONFLICT
    assert d.admission is not Admission.L2 and d.values["probability"] is None
    missing = environment_diagnostic(dict(wave=wave), request=req)
    assert missing.values["conclusion"] == "数据不足"
    stale = replace(wave, request=replace(req, analysis_date=f.trade_date.iloc[-2]))
    d = environment_diagnostic(dict(wave=stale), request=req)
    assert "SNAPSHOT_MISMATCH" in codes(d)
    unqualified = replace(fut, admission=Admission.L1)
    d = environment_diagnostic(dict(cffex_position=unqualified, wave=wave, fear_greed=fg), request=req)
    assert d.values["conclusion"] == "数据不足"


def test_l3_needs_sha_data_and_independent_execution_review_receipt():
    d = compute(prices())["daily_trend"]
    sha = "a"*40
    assert not strategy_admission(d, implementation_sha=sha)["strategy_allowed"]
    review = dict(implementation_sha=sha, rules_version=d.definitions_version,
        data_snapshot_id=d.data_snapshot_id, independent_h_review_ref="H-review:unit",
        approved_at="2026-10-19T11:00:00Z", execution_constraints_ref="execution:unit",
        out_of_sample_validation_ref="oos:unit")
    result = strategy_admission(d, implementation_sha=sha, review=review)
    assert result["strategy_allowed"] and not result["live_trading"]
    for field in review:
        bad = dict(review); bad.pop(field)
        assert not strategy_admission(d, implementation_sha=sha, review=bad)["strategy_allowed"]
    assert not strategy_admission(d, implementation_sha="b"*40, review=review)["strategy_allowed"]
    assert not strategy_admission(replace(d, admission=Admission.L1), implementation_sha=sha, review=review)["strategy_allowed"]


def test_synthetic_or_unknown_authorization_cannot_reach_research():
    f = prices()
    for s in (source(evidence_kind="synthetic"), replace(source(), research_authorization=Receipt()),
              replace(source(), time_verification=Receipt())):
        d = price_diagnostics(f, request=request(f), source=s, calendar=calendar(f))["daily_trend"]
        assert d.calculated and d.admission is Admission.L1


@pytest.mark.parametrize("behavior", ["success", "second_request", "wrong_endpoint", "oversized", "http_error"])
def test_public_worker_bounds_and_tls(monkeypatch, behavior):
    import sys
    from types import SimpleNamespace
    from unittest.mock import Mock
    import requests
    from ai_trade import market_analysis_data as data
    monkeypatch.setattr("importlib.metadata.version", lambda _: "1.19.1")
    response = Mock(status_code=200, is_redirect=False, apparent_encoding="utf-8")
    response.iter_content.return_value = iter([b"a" * 8_000_001] if behavior == "oversized" else [b"source-response"])
    if behavior == "http_error":
        response.status_code = 503
        response.raise_for_status.side_effect = requests.HTTPError()
    get = Mock(return_value=response)
    monkeypatch.setattr(requests, "get", get)
    def sdk(symbol):
        url = data.PUBLIC_ENDPOINTS["index"].format(symbol=symbol)
        requests.get("https://unreviewed.invalid" if behavior == "wrong_endpoint" else url)
        if behavior == "second_request": requests.get(url)
        return pd.DataFrame([dict(date="2026-10-16", open=1, high=2, low=1, close=2)])
    monkeypatch.setitem(sys.modules, "akshare", SimpleNamespace(stock_zh_index_daily=sdk))
    if behavior == "success":
        item = data._worker("index", "sh000300")
        assert item["available_at"] is None and len(item["http_trace"]) == 1
        assert item["http_trace"][0]["status"] == 200
    else:
        with pytest.raises((ValueError, requests.HTTPError)):
            data._worker("index", "sh000300")
    assert get.call_count == (0 if behavior == "wrong_endpoint" else 1)
    if get.called:
        assert get.call_args.kwargs["verify"] is True
        assert get.call_args.kwargs["timeout"] == (5, 8)
        assert get.call_args.kwargs["allow_redirects"] is False


def test_old_snapshots_do_not_acquire_fabricated_ingestion_time():
    from ai_trade.market_analysis_data import price_frame
    item = dict(prices=[dict(trade_date="2026-10-16", close=1)], symbol="sh000300", source="old", observed_at="2026-10-19T00:00:00Z")
    assert "ingested_at" not in price_frame(item)

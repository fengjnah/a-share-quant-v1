"""Synthetic, hand-checkable selector cases; never real-data acceptance evidence."""
from dataclasses import replace
from datetime import date, timedelta

import pandas as pd
import pytest

from ai_trade.daily_candidates import CandidateBatch, Evaluation, STRATEGIES, evaluate, score_rows, sort_evaluations, table_row
from ai_trade.daily_candidates_data import load_batch, local_coverage
from ai_trade.data_access.models import DailyBar
from ai_trade.data_access.repository import SQLiteMarketDataRepository
from ai_trade.market_state import MARKET_MODES, MarketState
from ai_trade.trading_analysis import analyze

ASOF = "2026-10-18T12:00:00+00:00"
SOURCE = "synthetic:m4:unit"


def observations(n=65):
    return pd.DataFrame([dict(symbol="600000.SH", trade_date=(date(2026, 1, 1)+timedelta(days=i)).isoformat(),
        open=100.+i, high=101.+i, low=99.+i, close=100.+i, volume_shares=1000,
        amount_cny=100000., source=SOURCE, source_version=f"synthetic-{i}", run_id="synthetic-m4",
        event_time=(date(2026, 1, 1)+timedelta(days=i)).isoformat()+"T07:00:00+00:00",
        available_at="2026-10-18T10:00:00+00:00", ingested_at="2026-10-18T10:01:00+00:00",
        quality_status="accepted", adjustment_method="none") for i in range(n)])


def calculation(f=None):
    f = observations() if f is None else f
    return analyze(f, analysis_date=f.trade_date.max(), as_of=ASOF, computed_at=ASOF, equity=100000.)


def market(day, **kw):
    return MarketState(day, "偏强", ASOF, True, "synthetic:validated-test-only", (), **kw)


def test_modes_differ_on_trend_without_relaxing_shared_data_gates():
    r = calculation()
    strict = evaluate(r, strategy=STRATEGIES[0], market=market(r.summary["analysis_date"]))
    trend = evaluate(r, strategy=STRATEGIES[1], market=market(r.summary["analysis_date"]))
    assert not strict.research_match and trend.research_match
    assert strict.score == trend.score == 40
    assert not strict.eligible and not trend.eligible  # M2 risk-status/weekly gates remain unknown.
    assert any("股票池约束未通过" in e for e in trend.exclusions)
    assert trend.risk["risk_budget"] == 1000
    assert trend.risk["structure_stop"] == 153
    assert trend.risk["atr_stop"] == trend.risk["final_stop"] == 160
    assert trend.risk["theoretical_shares"] is None and trend.risk["lot_size"] is None
    assert sum(x["得分"] for x in score_rows(trend)) == trend.score
    assert table_row(trend, 1)["研究止损参考"] == trend.risk["final_stop"]


@pytest.mark.parametrize("state,mode,expected", [("偏强", MARKET_MODES[0], True), ("震荡", MARKET_MODES[0], True),
    ("震荡", MARKET_MODES[1], False), ("偏弱", MARKET_MODES[0], False),
    ("证据冲突", MARKET_MODES[0], False), ("数据不足", MARKET_MODES[0], False)])
def test_market_gate_controls_output(state, mode, expected):
    r = calculation()
    # Test-only fully known gates, to isolate the market predicate from unavailable real inputs.
    r.summary.update(exclusions=[], technical_signal=True)
    m = replace(market(r.summary["analysis_date"]), state=state)
    e = evaluate(r, strategy=STRATEGIES[0], market=m, market_mode=mode)
    assert e.eligible is expected


@pytest.mark.parametrize("change", [dict(validated=False), dict(available_at=None),
    dict(available_at="2026-10-19T00:00:00+00:00"), dict(analysis_date="2026-01-01")])
def test_unverified_future_or_wrong_date_market_never_passes(change):
    m = replace(market("2026-03-06"), **change)
    assert not m.allows(analysis_date="2026-03-06", as_of=ASOF, mode=MARKET_MODES[0])


def test_order_and_max_five_follow_scores_with_stable_ties():
    rows = []
    for i, score in enumerate([40, 65, 55, 40, 80, 15, 75]):
        r = calculation()
        r.summary.update(symbol=f"60000{i}.SH", score=score, exclusions=[], technical_signal=True)
        rows.append(evaluate(r, strategy=STRATEGIES[0], market=market(r.summary["analysis_date"])))
    rows.append(Evaluation("600999.SH", exclusions=["missing"]))
    batch = CandidateBatch("2026-03-06", ASOF, STRATEGIES[0], MARKET_MODES[0], market("2026-03-06"), sort_evaluations(rows))
    assert [r.score for r in batch.candidates] == [80, 75, 65, 55, 40]
    assert batch.candidates[-1].symbol == "600000.SH"
    assert batch.evaluations[-1].score is None


def save(database, f):
    bars = [DailyBar(instrument_id="synthetic:m4:600000", symbol=row["symbol"], trade_date=row["trade_date"],
                    open=row["open"], high=row["high"], low=row["low"], close=row["close"],
                    volume=row["volume_shares"], amount=row["amount_cny"], source=row["source"],
                    source_version=row["source_version"], event_time=row["event_time"],
                    available_at=row["available_at"], ingested_at=row["ingested_at"], adjustment_method="none")
            for row in f.to_dict("records")]
    SQLiteMarketDataRepository(database).write_many(bars, run_id="synthetic-m4")


def test_local_missing_status_empty_candidate_and_shared_detail(database):
    f = observations()
    save(database, f)
    batch = load_batch(database, source=SOURCE, analysis_date=f.trade_date.max(), as_of=ASOF,
                       strategy=STRATEGIES[1], market_mode=MARKET_MODES[0])
    assert batch.candidates == []
    row = batch.evaluations[0]
    assert row.name.startswith("未知")
    assert row.analysis is not None and row.score == 40
    assert table_row(row, 1)["收盘价"] == row.analysis.frame.close.iloc[-1]
    assert row.risk["equity"] is None and row.risk["risk_budget"] is None
    assert any("历史证券名称/身份不可确认" in r for r in row.exclusions)
    assert any("数据不足" in r for r in row.exclusions)
    with pytest.raises(ValueError, match="分析日期"):
        load_batch(database, source=SOURCE, analysis_date="2026-03-07", as_of=ASOF,
                   strategy=STRATEGIES[0], market_mode=MARKET_MODES[0])
    _, dates = local_coverage(database, source=SOURCE, as_of="2026-10-17T00:00:00+00:00")
    assert dates == []  # Later ingestion cannot create historical visibility.


def test_insufficient_and_unknown_security_never_create_candidates(database):
    f = observations(14)
    save(database, f)
    batch = load_batch(database, source=SOURCE, analysis_date=f.trade_date.max(), as_of=ASOF,
                       strategy=STRATEGIES[0], market_mode=MARKET_MODES[0], symbol="600001")
    assert not batch.candidates and batch.evaluations[0].analysis is None
    r = calculation(f)
    e = evaluate(r, strategy=STRATEGIES[1], market=MarketState(r.summary["analysis_date"]))
    assert e.score is None and not e.eligible


def test_future_rows_do_not_change_historical_ranking_or_details():
    f = observations()
    before = calculation(f.iloc[:-1])
    after = analyze(f, analysis_date=f.trade_date.iloc[-2], as_of=ASOF, computed_at=ASOF, equity=100000.)
    assert before.summary == after.summary
    pd.testing.assert_frame_equal(before.frame, after.frame)
    assert after.summary["signal_available_at"] == "2026-10-18T12:00:00.000000+00:00"


@pytest.mark.parametrize("problem", ["missing_available_at", "future_ingested", "bad_price", "duplicate"])
def test_history_anomalies_never_reach_selector(problem):
    f = observations()
    if problem == "missing_available_at": f = f.drop(columns="available_at")
    elif problem == "future_ingested": f.loc[64, "ingested_at"] = "2026-10-19T00:00:00+00:00"
    elif problem == "bad_price": f.loc[64, "close"] = float("nan")
    else: f = pd.concat([f, f.tail(1)], ignore_index=True)
    with pytest.raises(ValueError): calculation(f)

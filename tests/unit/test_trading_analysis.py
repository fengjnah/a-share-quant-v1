"""Hand-checkable synthetic observations; never evidence of real market returns."""
from datetime import date, datetime, timedelta

import pandas as pd
import pytest

from ai_trade.trading_analysis import analyze, risk_reference

ASOF="2026-10-18T15:00:00+00:00"


def frame(n=61, rising=False):
    rows=[]
    for i in range(n):
        day=(date(2026,1,1)+timedelta(days=i)).isoformat()
        c=100.0+i if rising else 10.0
        rows.append(dict(symbol="600000.SH",trade_date=day,open=c,high=c+1,low=c-1,close=c,
            volume_shares=1000,amount_cny=100000.0,source="synthetic:unit:m2",source_version=f"synthetic-{i}",
            run_id="synthetic-m2",event_time=day+"T07:00:00+00:00",available_at="2026-10-18T10:00:00+00:00",
            ingested_at="2026-10-18T10:01:00+00:00",quality_status="accepted",adjustment_method="none"))
    return pd.DataFrame(rows)


def run(f, **kw):
    return analyze(f,analysis_date=kw.pop("analysis_date",f.trade_date.max()),as_of=ASOF,computed_at=ASOF,**kw)


def test_ma_warmup_and_no_backfill():
    r=run(frame(61,True))
    assert r.frame.MA5.iloc[:4].isna().all()
    assert r.frame.MA5.iloc[4]==102
    assert r.frame.MA60.iloc[:59].isna().all()
    assert r.frame.MA60.iloc[59]==129.5
    assert r.summary["metrics"]["MA60"]==130.5
    assert r.summary["score"]==40
    assert not r.summary["eligible"] and r.summary["market_state"]=="数据不足"


def test_wilder_atr_seed_and_recurrence_hand_calculation():
    f=frame(16)
    f.loc[15,["open","high","low","close"]]=[12,14,10,13]
    r=run(f)
    assert r.frame.ATR14.iloc[:14].isna().all()
    assert r.frame.ATR14.iloc[14]==2
    assert r.frame.ATR14.iloc[15]==pytest.approx((2*13+4)/14)


@pytest.mark.parametrize("n",[1,2,14,20,59])
def test_insufficient_history_is_unknown_not_a_zero_score(n):
    r=run(frame(n))
    assert r.summary["score"] is None and r.summary["technical_signal"] is None
    assert any("历史不足" in x for x in r.summary["exclusions"])
    if n<15: assert r.summary["metrics"]["ATR14"] is None
    assert r.risk["equity"] is None and r.risk["theoretical_shares"] is None


@pytest.mark.parametrize("close,volume,expected",[(11,1500,False),(11.01,1500,True),(11.01,1499,False)])
def test_breakout_excludes_current_high_and_volume_boundary(close,volume,expected):
    f=frame();f.loc[60,["open","high","low","close","volume_shares"]]=[10,12,9,close,volume]
    assert run(f).summary["conditions"]["放量突破"] is expected


@pytest.mark.parametrize("volume,expected",[(700,True),(701,False)])
def test_shrinking_pullback_inclusive_volume_boundary(volume,expected):
    f=frame()
    f[["open","close"]]=9.;f["high"]=10.;f["low"]=8.
    f.loc[59,["high","close"]]=[13,12]
    f.loc[60,["open","high","low","close","volume_shares"]]=[10.5,11,9,10,volume]
    assert run(f).summary["conditions"]["缩量回调"] is expected


@pytest.mark.parametrize("op,close,expected",[(9.9,10.1,True),(10,10.1,False),(9.9,10,False)])
def test_bullish_body_crosses_all_three_prior_lines_strictly(op,close,expected):
    f=frame();f.loc[60,["open","high","low","close"]]=[op,11,9,close]
    assert run(f).summary["conditions"]["一阳穿三线"] is expected


@pytest.mark.parametrize("volume",[0,10000])
def test_zero_or_extreme_volume_never_generates_a_signal(volume):
    f=frame();f.loc[60,"volume_shares"]=volume
    r=run(f)
    assert r.summary["technical_signal"] is None and r.summary["score"] is None
    assert r.risk["final_stop"] is None and r.risk["theoretical_shares"] is None
    assert any("异常" in s or "零成交" in s for s in r.summary["exclusions"])


def test_known_failed_conditions_get_zero_score_with_explicit_exclusions():
    r=run(frame())
    assert r.summary["score"]==0 and r.summary["technical_signal"] is False
    assert r.summary["signal_state"]=="未满足"
    assert any("组合未满足" in s for s in r.summary["exclusions"])
    assert r.summary["weekly_filter"] is None


@pytest.mark.parametrize("problem",["duplicate","missing","nan","bad_ohlc","fractional_volume","future_available","future_ingested","mixed_source"])
def test_bad_or_unavailable_observations_are_rejected(problem):
    f=frame()
    if problem=="duplicate":f=pd.concat([f,f.tail(1)],ignore_index=True)
    elif problem=="missing":f=f.drop(columns="close")
    elif problem=="nan":f.loc[60,"close"]=float("nan")
    elif problem=="bad_ohlc":f.loc[60,"high"]=1
    elif problem=="fractional_volume":f["volume_shares"]=f.volume_shares.astype(float);f.loc[60,"volume_shares"]=1.5
    elif problem=="future_available":f.loc[60,"available_at"]="2026-10-19T00:00:00+00:00"
    elif problem=="future_ingested":f.loc[60,"ingested_at"]="2026-10-19T00:00:00+00:00"
    elif problem=="mixed_source":f.loc[60,"source"]="synthetic:other:m2"
    with pytest.raises(ValueError):run(f)


def test_appending_future_prices_does_not_change_any_historical_feature():
    f=frame(62,True);end=f.trade_date.iloc[60]
    before=run(f.iloc[:61],analysis_date=end)
    f.loc[61,"close"]=float("nan")  # This row is after the requested event-date cutoff.
    after=run(f,analysis_date=end)
    pd.testing.assert_frame_equal(before.frame,after.frame)
    assert before.summary==after.summary
    assert datetime.fromisoformat(after.summary["signal_available_at"]) == datetime.fromisoformat(ASOF)
    assert after.summary["signal_available_at"] > after.summary["latest_trade_date"]


def test_current_week_is_excluded_and_stale_dates_are_unknown():
    f=frame(170,True)
    first=run(f)
    start=pd.Timestamp(f.trade_date.iloc[-1]).to_period("W-SUN").start_time
    current=pd.to_datetime(f.trade_date)>=start
    for k in ["open","high","low","close"]:f.loc[current,k]=f.loc[current,k]+1000
    second=run(f)
    assert first.summary["weekly_sample_trend"]==second.summary["weekly_sample_trend"]
    assert first.summary["weekly_count"]==second.summary["weekly_count"]
    stale=run(f,analysis_date=(date.fromisoformat(f.trade_date.max())+timedelta(days=1)).isoformat())
    assert stale.summary["technical_signal"] is None
    assert any("过期" in s for s in stale.summary["exclusions"])


def test_historical_cutoff_does_not_backdate_the_calculation():
    with pytest.raises(ValueError,match="计算时点"):
        analyze(frame(),analysis_date="2026-03-02",as_of=ASOF,computed_at="2026-10-17T00:00:00+00:00")
    r=analyze(frame(),analysis_date="2026-03-02",as_of=ASOF,computed_at="2026-10-19T00:00:00+00:00")
    assert r.summary["signal_available_at"]=="2026-10-19T00:00:00.000000+00:00"


def test_stops_and_one_percent_budget_are_reproducible():
    r=risk_reference(10,1,7,100000)
    assert r["atr_stop"]==8 and r["structure_stop"]==7 and r["final_stop"]==8
    assert r["risk_budget"]==1000 and r["theoretical_shares"]==500
    assert risk_reference(10,1,11,100000)["final_stop"] is None
    assert risk_reference(10,None,7,100000)["theoretical_shares"] is None
    assert risk_reference(10,1,7,None)["risk_budget"] is None


@pytest.mark.parametrize("equity",[-1,0,float("nan"),float("inf"),True])
def test_invalid_equity_is_not_replaced_by_a_default(equity):
    with pytest.raises(ValueError):risk_reference(10,1,7,equity)

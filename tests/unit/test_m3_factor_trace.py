"""Trace cannot change old scores, missing semantics or causal windows."""
import pandas as pd
import pytest

from ai_trade.market_analysis import WEIGHTS,fear_greed,fear_greed_with_trace
from m3_fear_greed_baseline import baseline_fear_greed
from test_market_analysis import prices, ASOF


def market(f):
    return pd.DataFrame([dict(trade_date=d,observed_at=ASOF,advances=60,declines=30,flat=10,limit_up=3,limit_down=1) for d in f.trade_date])


@pytest.mark.parametrize('scenario',['full','missing','zero','no_amount','prefix'])
def test_trace_and_public_dataframe_exactly_equal_frozen_original(scenario):
    f=prices(100); b=market(f)
    if scenario=='missing': b=None
    if scenario=='zero':
        b[['advances','declines','flat','limit_up','limit_down']]=0
        f['amount_cny']=0.
    if scenario=='no_amount': f=f.drop(columns='amount_cny')
    date=f.trade_date.iloc[60] if scenario=='prefix' else f.trade_date.iloc[-1]
    args=dict(analysis_date=date,as_of=ASOF,breadth=b)
    expected=baseline_fear_greed(f,**args)
    computed,trace=fear_greed_with_trace(f,**args)
    pd.testing.assert_frame_equal(expected,computed,check_exact=True)
    pd.testing.assert_frame_equal(expected,fear_greed(f,**args),check_exact=True)
    assert len(trace)==len(computed)*6
    for x in trace:
        assert x['weight']==WEIGHTS[x['factor_key']]
        value=computed.loc[computed.trade_date==x['business_date'],x['factor_key']].item()
        assert x['normalized_value']==(None if pd.isna(value) else value)
        if x['normalized_value'] is None:
            assert x['contribution'] is None and x['status']=='MISSING' and x['reasons_json']
    if scenario in ('missing','zero','no_amount'): assert computed.score.isna().all()


def test_raw_values_and_current_sample_exclusion_hand_check():
    f=prices(100); b=market(f)
    computed,trace=fear_greed_with_trace(f,analysis_date=f.trade_date.iloc[-1],as_of=ASOF,breadth=b)
    last={x['factor_key']:x for x in trace if x['business_date']==f.trade_date.iloc[-1]}
    assert last['趋势']['raw_value']==f.close.iloc[-1]/f.close.iloc[-20:].mean()-1
    assert last['动量']['raw_value']==f.close.iloc[-1]/f.close.iloc[-6]-1
    assert last['上涨占比']['raw_value']==.6 and last['上涨占比']['normalized_value']==60.
    assert last['涨停占比']['raw_value']==.75 and last['涨停占比']['normalized_value']==75.
    assert last['成交额']['raw_value']==f.amount_cny.iloc[-1]/f.amount_cny.iloc[-21:-1].mean()
    # A much larger unseen future observation cannot alter this prefix.
    extended=pd.concat([f,pd.DataFrame([dict(f.iloc[-1],trade_date='2026-10-19',close=1e6,open=1e6,high=1e6,low=1e6)])],ignore_index=True)
    _,future_trace=fear_greed_with_trace(extended,analysis_date=f.trade_date.iloc[-1],as_of=ASOF,breadth=b)
    assert future_trace==trace

"""Presentation boundaries reuse existing synthetic M4 calculation fixtures."""
import pytest

from ai_trade.daily_candidates import CandidateBatch, STRATEGIES, evaluate
from ai_trade.daily_candidates_view import data_status, events, monitor_row, risk_row, symbols_input
from ai_trade.market_state import MARKET_MODES, MarketState
from test_daily_candidates import ASOF, calculation, observations


def batch(row):
    day = row.analysis.summary['analysis_date']
    return CandidateBatch(day, ASOF, STRATEGIES[0], MARKET_MODES[0], MarketState(day), [row])


def test_stages_and_exit_records_are_never_inferred_from_real_indicators():
    result = calculation()
    row = evaluate(result, strategy=STRATEGIES[1], market=MarketState(result.summary['analysis_date']))
    assert row.research_match
    monitor = monitor_row(row)
    assert monitor['当前阶段'] == '阶段待识别'
    assert monitor['阶段进入日期'] is None and monitor['持续交易日数'] is None
    assert monitor['整理区间上沿'] is None and monitor['整理区间下沿'] is None
    assert monitor['综合评分'] is None and monitor['技术研究评分'] == result.summary['score']
    risk = risk_row(row)
    assert risk['当前结构止损'] == result.risk['structure_stop']
    assert risk['ATR止损'] == result.risk['atr_stop']
    assert risk['初始结构止损'] is None and risk['连续收盘跌破MA5交易日数'] is None
    assert risk['参考风险金额（元）'] == 1000 and risk['理论股数'] is None


def test_synthetic_status_never_claims_true_source_and_stale_timestamp_survives():
    result = calculation()
    row = evaluate(result, strategy=STRATEGIES[0], market=MarketState(result.summary['analysis_date']))
    status = data_status(batch(row), today='2026-10-20')
    assert status['synthetic'] and status['state'].startswith('离线演示')
    assert status['updated'] == result.summary['latest_ingested_at']
    # Source declaration for testing the historical-age presentation only.
    for field in ('source', 'source_version', 'run_id'):
        result.frame[field] = 'observation:v1'
    status = data_status(batch(row), today='2026-10-20')
    assert status['state'] == '数据过期 / 历史快照'
    assert status['latest'] == result.summary['latest_trade_date']


def test_only_existing_m2_event_names_dates_and_timestamps_are_exposed():
    f = observations()
    f.loc[64, ['open','high','low','close','volume_shares']] = [164.,170.,163.,169.,1600]
    result = calculation(f)
    row = evaluate(result, strategy=STRATEGIES[0], market=MarketState(result.summary['analysis_date']))
    marks = events(row)
    assert not marks.empty and set(marks['独立M2条件']) <= {'放量突破','缩量回调','一阳穿三线'}
    assert marks['行情日期'].max() <= result.summary['analysis_date']
    assert marks['指标可用时间'].min() == result.summary['signal_available_at']
    assert not any('二次' in kind or '首次' in kind for kind in marks['独立M2条件'])


def test_watch_codes_support_multiple_separators_and_bound_the_work():
    assert symbols_input('600000, 600378\n000001；600000') == ('600000','600378','000001')
    with pytest.raises(ValueError): symbols_input('')
    with pytest.raises(ValueError): symbols_input(','.join(str(i) for i in range(21)))

"""Offline UI mapping regressions; unit receipts never certify real sources."""
from dataclasses import replace
import json

import pandas as pd
import pytest

from ai_trade.market_analysis_contract import Admission, ReasonCode, Status, Verification
from ai_trade.market_analysis_core import environment_diagnostic
from ai_trade.market_analysis_data import save_snapshot
from ai_trade.market_analysis_view import (
    MODULES, STATUS_LABELS, LocalInput, catalogue, coverage_text, diagnostic_bundle,
    displayable, evidence_payload, from_snapshots, from_stock_frame, overview_html,
    safe_text, unavailable,
)
from test_market_analysis_core import calendar, compute, market, prices, request, source


def bundle(f=None, **kwargs):
    f = prices() if f is None else f
    return diagnostic_bundle(LocalInput(f, source()), unavailable('breadth'), request=request(f), **kwargs)


def test_formal_family_mapping_and_unknown_denominator():
    result = bundle()
    assert tuple(result) == tuple(MODULES)
    assert set(STATUS_LABELS) == set(Status)
    assert result['daily_trend'] == compute_without_calendar(prices())
    d = result['daily_trend']
    assert coverage_text(d) == '150 / UNKNOWN · UNKNOWN'
    assert d.admission is Admission.L1
    p = evidence_payload(d)
    assert p['coverage']['ratio'] is None and p['coverage']['expected_samples'] is None
    assert p['allowed_uses']['live_trading'] is False
    html = overview_html(result)
    assert html.count('<article') == 8
    assert '150 / UNKNOWN' in html and '100%' not in html


def compute_without_calendar(f):
    from ai_trade.market_analysis_core import price_diagnostics
    return price_diagnostics(f, request=request(f), source=source())['daily_trend']


@pytest.mark.parametrize('scenario', ['empty', 'partial', 'stale', 'mismatch', 'illegal', 'time_missing', 'parse_error'])
def test_real_core_scenario_mapping_does_not_upgrade(scenario):
    f = prices()
    price = LocalInput(f, source())
    req = request(f)
    if scenario == 'empty': price = unavailable('price')
    if scenario == 'stale': req = replace(req, analysis_date='2026-10-16')
    if scenario == 'mismatch': price.frame = f.assign(symbol='sh000001')
    if scenario == 'illegal': price.frame = f.assign(close=-1)
    if scenario == 'time_missing': price.frame = f.drop(columns='observed_at')
    if scenario == 'parse_error': price = unavailable('price', '摘要校验失败')
    result = diagnostic_bundle(price, unavailable('breadth'), request=req)
    daily, full = result['daily_trend'], result['fear_greed']
    assert full.to_dict()['values'].get('score') is None
    assert not displayable(full)
    assert result['environment'].admission is Admission.BLOCKED
    if scenario in ('mismatch', 'illegal', 'parse_error'):
        assert daily.status is Status.INVALID_DATA and daily.admission is Admission.BLOCKED
        assert not displayable(daily)
    elif scenario == 'empty':
        assert daily.status is Status.SOURCE_UNAVAILABLE and not displayable(daily)
    elif scenario == 'time_missing':
        assert daily.admission is Admission.BLOCKED and 'observed_at' in daily.missing_fields
    elif scenario == 'stale':
        assert daily.status is Status.STALE and daily.data_latest_date == f.trade_date.iloc[-1]
        assert daily.admission is Admission.L1
    elif scenario == 'partial':
        assert ReasonCode.FACTOR_MISSING in {r.code for r in full.reasons}
        assert displayable(result['price_proxy'])
    assert all(not d.to_dict()['allowed_uses']['live_trading'] for d in result.values())


def test_conflict_is_preserved_and_blocked_payload_never_displayable():
    d = compute(prices())['wave']
    fg = replace(d, indicator='fear_greed', values={'score': 80})
    fut = replace(d, indicator='cffex_position', values={'direction': '偏空'})
    conflict = environment_diagnostic(dict(wave=d, fear_greed=fg, cffex_position=fut), request=d.request)
    assert conflict.status is Status.EVIDENCE_CONFLICT
    assert 'EVIDENCE_CONFLICT' in overview_html({'environment': conflict})
    for status in (Status.INVALID_DATA, Status.BLOCKED):
        assert not displayable(replace(d, status=status, values={'score': 999999}))
    assert not displayable(replace(d, admission=Admission.BLOCKED))


def item(f=None):
    f = prices() if f is None else f
    return dict(source='unit:price:v1', kind='index', symbol='sh000300', trade_date=f.trade_date.iloc[-1],
                prices=f.to_dict('records'), observed_at='2026-10-19T12:00:00Z')


def test_archive_mapping_preserves_row_identity_time_and_unknown_receipts(tmp_path):
    f = prices().drop(columns=['observed_at', 'quality_status', 'available_at'])
    raw = item(f)
    mapped = from_snapshots([raw], kind='index')
    assert 'available_at' not in mapped.frame and 'quality_status' not in mapped.frame
    assert mapped.frame.observed_at.iloc[0] == raw['observed_at']
    assert mapped.source.time_verification.status is Verification.UNKNOWN
    assert not mapped.source.verification.verified
    raw['prices'][0]['symbol'] = 'sh000001'
    mapped = from_snapshots([raw], kind='index')
    result = diagnostic_bundle(mapped, unavailable('breadth'), request=request(prices()))
    assert result['daily_trend'].status is Status.INVALID_DATA
    save_snapshot(tmp_path, raw)
    saved, error = catalogue(tmp_path, kind='index', symbol='sh000300', analysis_date='2026-10-16')
    assert len(saved) == 1 and error is None
    (tmp_path/'m3-observations'/'bad.json').write_text('[]')
    assert catalogue(tmp_path, kind='index', symbol='sh000300', analysis_date='2026-10-16')[1]


def test_breadth_does_not_overwrite_dates_or_deduplicate_versions():
    m = market(prices(1)).iloc[0].to_dict()
    raw = dict(source='unit:breadth:v1', symbol='market', trade_date=m['trade_date'], breadth=m)
    mapped = from_snapshots([raw, raw], kind='breadth')
    assert len(mapped.frame) == 2
    result = diagnostic_bundle(unavailable('price'), mapped, request=request(prices(1)))
    assert result['market_breadth'].status is Status.INVALID_DATA
    raw['trade_date'] = '2026-10-16'
    assert from_snapshots([raw], kind='breadth').error


def test_stock_never_fabricates_observation_from_ingestion():
    f = prices().drop(columns='observed_at')
    mapped = from_stock_frame(f, source='unit:price:v1', request=request(f))
    assert 'observed_at' not in mapped.frame
    assert bundle(mapped.frame)['daily_trend'].admission is Admission.BLOCKED


def test_metadata_is_sanitized_and_raw_payload_omitted():
    d = compute(prices())['daily_trend']
    d = replace(d, source=replace(d.source, source='https://user:pwd@host/path?token=abc#part'),
                values={'raw_csv_hex': 'not-public', 'score': 42})
    payload = evidence_payload(d)
    encoded = json.dumps(payload)
    assert payload['source']['source'] == 'https://host/path'
    assert 'not-public' not in encoded and 'pwd' not in encoded and 'token=abc' not in encoded
    assert safe_text('token=secret\nname') == 'token=[已隐藏]'
    assert safe_text(None) == 'UNKNOWN' and safe_text(0) == '0'
    assert '&lt;script&gt;' not in overview_html({'daily_trend': d})  # no arbitrary source HTML in cards

"""Regression fixtures only: receipts here never certify real data or permission."""
from dataclasses import replace
import json
from pathlib import Path

import jsonschema
import pandas as pd
import pytest

from ai_trade.market_analysis_contract import Admission, Receipt, Status, strategy_admission
from ai_trade.market_analysis_core import (
    breadth_diagnostic, cffex_diagnostic, environment_diagnostic,
    fear_greed_diagnostic, price_diagnostics,
)
from ai_trade.market_data.cffex_rankings_models import MemberScope
from test_market_analysis_core import calendar, cffex_fixture, market, prices, receipt, request, source

SCHEMA = json.loads((Path(__file__).parents[2] / 'docs/M3_DIAGNOSTIC_V1.schema.json').read_text(encoding='utf-8'))
VALIDATOR = jsonschema.Draft202012Validator(SCHEMA, format_checker=jsonschema.FormatChecker())
MODES = ('research', 'strict_backtest', 'paper_trade')
KINDS = ('prices', 'fear_prices', 'breadth', 'fear_market')
BAD_IDENTITIES = (None, float('nan'), '', '   ', 42, True, [], {}, ' padded ', 'bad\nidentifier', 'x'*257, 'other')
BAD_QUALITY = ('quarantined', 'rejected', 'UNKNOWN', '', True, 0, [], {})
BAD_AMOUNTS = ('bad', None, '', True, float('nan'), float('inf'), -float('inf'), -1, [], {})


def inputs():
    f = prices(105)
    f['quality_status'] = 'accepted'
    m = market(f)
    m['quality_status'] = 'accepted'
    m['symbol'] = 'ALL_A'
    return f, m


def set_cell(frame, column, position, value):
    frame[column] = frame[column].astype(object)
    frame.at[frame.index[position], column] = value


def call(kind, f, m, mode='research'):
    req = request(f, mode=mode)
    if kind == 'prices':
        return tuple(price_diagnostics(f, request=req, source=source(), calendar=calendar(f)).values())
    if kind == 'breadth':
        return (breadth_diagnostic(m, request=replace(req, symbol='ALL_A', instrument_type='ALL_A'),
                source=source('unit:breadth:v1'), calendar=calendar(f),
                universe_receipt=receipt(*m.universe_snapshot_ref)),)
    return (fear_greed_diagnostic(f, request=req, source=source(), calendar=calendar(f),
            market_frame=m, market_source=source('unit:breadth:v1'),
            universe_receipt=receipt(*m.universe_snapshot_ref)),)


def assert_blocked(diagnostic, field=None, day=None):
    payload = diagnostic.to_dict()
    VALIDATOR.validate(payload)
    assert diagnostic.status is Status.INVALID_DATA
    assert diagnostic.admission is Admission.BLOCKED
    assert not diagnostic.calculated and diagnostic.values == {}
    assert payload['allowed_uses'] == dict(observation=False, research=False, strategy=False, live_trading=False)
    if field:
        details = ' '.join(r.detail for r in diagnostic.reasons)
        assert field in details
        if day:
            assert day in details


@pytest.mark.parametrize('finding', ('H1-source', 'H1-symbol', 'H2-quality', 'M1-turnover'))
def test_review_counterexamples_fail_closed(finding):
    f, m = inputs()
    kind, field = 'prices', 'source'
    if finding == 'H1-source': set_cell(f, field, -1, None)
    if finding == 'H1-symbol':
        field = 'symbol'; set_cell(f, field, -1, None)
    if finding == 'H2-quality':
        field = 'quality_status'; set_cell(f, field, -1, 'quarantined')
    if finding == 'M1-turnover':
        kind, field = 'fear_market', 'market_amount_cny'; set_cell(m, field, -1, 'bad')
    for d in call(kind, f, m, 'paper_trade'):
        assert_blocked(d, field, f.trade_date.iloc[-1])


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('position', (0, 50, -1))
@pytest.mark.parametrize('field', ('source', 'symbol'))
@pytest.mark.parametrize('value', BAD_IDENTITIES)
def test_every_visible_identity_is_checked(kind, mode, position, field, value):
    f, m = inputs()
    target = m if kind in ('breadth', 'fear_market') else f
    set_cell(target, field, position, value)
    for d in call(kind, f, m, mode):
        assert_blocked(d, field, target.trade_date.iloc[position])


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('position', (0, 50, -1))
@pytest.mark.parametrize('value', BAD_QUALITY)
def test_explicit_quality_rejection_cannot_be_overridden_by_receipts(kind, mode, position, value):
    f, m = inputs()
    target = m if kind in ('breadth', 'fear_market') else f
    set_cell(target, 'quality_status', position, value)
    assert source().verification.verified and source().research_authorization.verified
    for d in call(kind, f, m, mode):
        assert_blocked(d, 'quality_status', target.trade_date.iloc[position])


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('position', (0, 50, -1))
@pytest.mark.parametrize('value', (None, float('nan'), pd.NA))
def test_missing_quality_remains_unknown(kind, mode, position, value):
    f, m = inputs()
    target = m if kind in ('breadth', 'fear_market') else f
    set_cell(target, 'quality_status', position, value)
    for d in call(kind, f, m, mode):
        VALIDATOR.validate(d.to_dict())
        assert d.admission is (Admission.L1 if mode == 'research' else Admission.BLOCKED)
        assert not d.to_dict()['allowed_uses']['research']
        assert 'quality_status' in d.missing_fields
        assert any(r.code.value == 'EVIDENCE_MISSING' and 'quality_status' in r.detail for r in d.reasons)


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('mode', MODES)
def test_absent_quality_column_is_not_accepted(kind, mode):
    f, m = inputs()
    target = m if kind in ('breadth', 'fear_market') else f
    target.drop(columns='quality_status', inplace=True)
    for d in call(kind, f, m, mode):
        assert d.admission is (Admission.L1 if mode == 'research' else Admission.BLOCKED)
        assert 'quality_status' in d.missing_fields


@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('position', (0, 50, -1))
@pytest.mark.parametrize('value', BAD_AMOUNTS)
def test_turnover_bad_sample_is_structured_not_an_exception(mode, position, value):
    f, m = inputs()
    set_cell(m, 'market_amount_cny', position, value)
    for d in call('fear_market', f, m, mode):
        assert_blocked(d, 'market_amount_cny', m.trade_date.iloc[position])
        assert 'ALL_A' in ' '.join(r.detail for r in d.reasons)


@pytest.mark.parametrize('kind', KINDS)
@pytest.mark.parametrize('mode', MODES)
def test_accepted_control_still_qualifies(kind, mode):
    f, m = inputs()
    for d in call(kind, f, m, mode):
        VALIDATOR.validate(d.to_dict())
        assert d.admission is Admission.L2 and d.calculated
        assert d.to_dict()['allowed_uses']['research']
        assert not d.to_dict()['allowed_uses']['live_trading']


@pytest.mark.parametrize('position', (0, 50, -1))
@pytest.mark.parametrize('amount', (0, 0.0, 123, 123.5))
def test_real_zero_and_finite_numeric_turnover_survive(position, amount):
    f, m = inputs()
    set_cell(m, 'market_amount_cny', position, amount)
    d, = call('fear_market', f, m)
    assert d.admission is Admission.L2 and d.calculated
    assert d.values['score'] is not None


def cffex(quality_status='accepted', mode='research'):
    record, req, src, cal = cffex_fixture()
    record = replace(record, evidence_kind='source_observation', publication_time='2026-10-16T08:00:00Z')
    src = replace(src, evidence_kind='source_observation')
    return cffex_diagnostic([record], request=replace(req, mode=mode), source=src,
            member='甲会员(代客)', scope=MemberScope.AGENT, calendar=cal,
            scope_receipt=receipt(), publication_receipt=receipt(), quality_status=quality_status)


@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('quality', BAD_QUALITY)
def test_cffex_quality_gate(mode, quality):
    assert_blocked(cffex(quality, mode), 'quality_status', '2026-10-16')


@pytest.mark.parametrize('mode', MODES)
def test_cffex_missing_quality_is_not_certified_by_receipts(mode):
    d = cffex(None, mode)
    assert d.admission is (Admission.L1 if mode == 'research' else Admission.BLOCKED)
    assert d.values.get('direction') is None
    assert 'quality_status' in d.missing_fields
    VALIDATOR.validate(d.to_dict())


@pytest.mark.parametrize('mode', MODES)
def test_cffex_explicit_accepted_control(mode):
    d = cffex('accepted', mode)
    assert d.admission is Admission.L2 and d.values['direction'] == '偏多'
    VALIDATOR.validate(d.to_dict())


def test_rejected_component_never_opens_environment_or_l3():
    f, m = inputs()
    f.loc[f.index[-1], 'quality_status'] = 'quarantined'
    rejected = price_diagnostics(f, request=request(f), source=source(), calendar=calendar(f))['wave']
    combined = environment_diagnostic({'wave': rejected}, request=request(f))
    assert not combined.to_dict()['allowed_uses']['research']
    assert not strategy_admission(rejected, implementation_sha='a'*40)['strategy_allowed']
    assert combined.to_dict()['allowed_uses']['live_trading'] is False

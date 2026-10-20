"""R1–R4 offline counterexamples. Receipts are fixtures, not source acceptance."""
from dataclasses import replace
from datetime import timedelta, timezone
from decimal import Decimal
from fractions import Fraction
import json

import numpy as np
import pandas as pd
import pytest

from ai_trade.market_analysis_contract import Admission, Request
from ai_trade.market_analysis_core import (
    breadth_diagnostic, cffex_diagnostic, environment_diagnostic,
    fear_greed_diagnostic, price_diagnostics,
)
from ai_trade.market_data.cffex_rankings_models import MemberScope
from test_market_analysis_core import calendar, cffex_fixture, market, prices, receipt, request, source
from test_market_analysis_core_validation import MODES, assert_blocked, set_cell, VALIDATOR

CONTROLS = tuple(map(chr, (*range(32), *range(127, 160))))
COUNTS = ('advances', 'declines', 'flat', 'limit_up', 'limit_down',
          'eligible_count', 'suspended', 'unavailable', 'missing')
NUMERIC_PATHS = tuple((kind, field) for kind in ('price', 'fear_price')
                      for field in ('open', 'high', 'low', 'close')) + (
    ('fear_market', 'market_amount_cny'),
) + tuple((kind, field) for kind in ('breadth', 'fear_market') for field in COUNTS)
SCALARS = tuple(dict.fromkeys((int, float, np.int8, np.int16, np.int32, np.int64,
                              np.uint8, np.uint16, np.uint32, np.uint64,
                              np.float16, np.float32, np.float64, np.longdouble)))


def cffex_input(mode='research', field=None, value=None):
    record, req, src, cal = cffex_fixture()
    record = replace(record, evidence_kind='source_observation', publication_time='2026-10-16T08:00:00Z')
    src = replace(src, evidence_kind='source_observation')
    member = '甲会员(代客)'
    if field == 'source':
        record, src = replace(record, source=value), replace(src, source=value)
    elif field == 'symbol':
        record = replace(record, contracts=(value,), rows=tuple(replace(r, contract=value) for r in record.rows))
        req = replace(req, symbol=value)
    elif field == 'member':
        record = replace(record, rows=tuple(replace(r, member=value) for r in record.rows))
        member = value
    elif field == 'source_version':
        record = replace(record, source_version=value)
        src = replace(src, source_version=value, lineage_refs=(value,))
    return cffex_diagnostic([record], request=replace(req, mode=mode), source=src, member=member,
        scope=MemberScope.AGENT, calendar=cal, scope_receipt=receipt(), publication_receipt=receipt(),
        quality_status='accepted')


def diagnose(kind, f, m, mode='research', *, req=None, src=None, market_src=None):
    req = req or request(f, mode=mode)
    src = src or source()
    market_src = market_src or source('unit:breadth:v1')
    if kind == 'price':
        return tuple(price_diagnostics(f, request=req, source=src, calendar=calendar(f)).values())
    if kind == 'breadth':
        req = req if req.instrument_type == 'ALL_A' else replace(req, symbol='ALL_A', instrument_type='ALL_A')
        return (breadth_diagnostic(m, request=req, source=market_src, calendar=calendar(f),
                                  universe_receipt=receipt(*m.universe_snapshot_ref)),)
    fear = fear_greed_diagnostic(f, request=req, source=src, calendar=calendar(f), market_frame=m,
        market_source=market_src, universe_receipt=receipt(*m.universe_snapshot_ref))
    if kind != 'environment':
        return (fear,)
    wave = price_diagnostics(f, request=req, source=src, calendar=calendar(f))['wave']
    return (environment_diagnostic({'wave': wave, 'fear_greed': fear,
                                   'cffex_position': cffex_input(mode)}, request=req),)


def blocked(d, field, day=None):
    assert_blocked(d, field, day)
    json.dumps(d.to_dict(), allow_nan=False)
    assert not d.to_dict()['allowed_uses']['research']


@pytest.mark.parametrize('finding', ('R1', 'R2', 'R3-price', 'R3-amount', 'R3-breadth', 'R4-price', 'R4-fear'))
def test_review_regressions(finding):
    f = prices(105); m = market(f)
    if finding == 'R1':
        value = 'unit:price:\x7fv1'; f['source'] = value
        for d in diagnose('price', f, m, src=source(value)):
            blocked(d, 'source')
    elif finding.startswith('R4'):
        baseline = diagnose('price' if finding == 'R4-price' else 'fear_price', f, m)
        f['observed_at'] = [pd.Timestamp(v).tz_convert(timezone(timedelta(hours=-10))).isoformat()
                            for v in f.observed_at]
        actual = diagnose('price' if finding == 'R4-price' else 'fear_price', f, m)
        assert [d.to_dict() for d in actual] == [d.to_dict() for d in baseline]
    else:
        kind, target, field = ('price', f, 'high') if finding == 'R3-price' else (
            ('breadth', m, 'advances') if finding == 'R3-breadth' else ('fear_market', m, 'market_amount_cny'))
        set_cell(target, field, 50, Fraction(1234567, 2) if finding == 'R2' else 10**400)
        for d in diagnose(kind, f, m):
            blocked(d, field, target.trade_date.iloc[50])


IDENTITY_PATHS = tuple((kind, field) for kind in ('price', 'fear_price', 'breadth', 'environment')
                       for field in ('source', 'symbol')) + (('fear_market', 'source'),)


@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('kind,field', IDENTITY_PATHS)
def test_matching_invalid_declaration_and_records_cannot_gain_admission(mode, kind, field):
    f = prices(205 if kind == 'environment' else 105); m = market(f)
    for control in CONTROLS:
        value = 'unit:bad' + control + ':v1'
        req, src, market_src = request(f, mode=mode), source(), source('unit:breadth:v1')
        target = m if kind in ('breadth', 'fear_market') else f
        target[field] = value
        if field == 'source':
            if target is m: market_src = source(value)
            else: src = source(value)
        elif kind == 'breadth':
            req = replace(req, symbol=value, instrument_type='ALL_A')
        else:
            req = replace(req, symbol=value)
        for d in diagnose(kind, f, m, mode, req=req, src=src, market_src=market_src):
            blocked(d, field)


@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('field', ('source', 'symbol', 'member', 'source_version'))
def test_cffex_matching_control_character_identities_are_structured(mode, field):
    for control in CONTROLS:
        blocked(cffex_input(mode, field, 'bad' + control + 'identity'), field)


@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('kind', ('price', 'breadth', 'fear_market'))
def test_record_only_controls_are_checked_at_every_position(mode, kind):
    f = prices(105); m = market(f)
    m['symbol'] = 'ALL_A'
    for position in (0, 50, -1):
        for field in ('source', 'symbol'):
            for control in ('\x00', '\x7f', '\x80', '\x85', '\x9f'):
                target = m.copy() if kind != 'price' else f.copy()
                set_cell(target, field, position, 'bad' + control + 'identity')
                for d in diagnose(kind, target if kind == 'price' else f,
                                  m if kind == 'price' else target, mode):
                    blocked(d, field, target.trade_date.iloc[position])


@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('kind,field', NUMERIC_PATHS)
@pytest.mark.parametrize('value', (Fraction(5, 2), Decimal('2.5'), 2+0j, np.bool_(True), 10**400))
def test_unsupported_or_overflowing_scalars_are_contextual(mode, kind, field, value):
    f = prices(105); m = market(f)
    target = f if kind in ('price', 'fear_price') else m
    set_cell(target, field, 50, value)
    for d in diagnose(kind, f, m, mode):
        blocked(d, field, target.trade_date.iloc[50])
        assert ('ALL_A' if target is m else 'sh000300') in ' '.join(r.detail for r in d.reasons)


@pytest.mark.parametrize('kind', ('price', 'fear_price', 'breadth', 'fear_market'))
@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('scalar', SCALARS)
def test_supported_numeric_scalars_have_full_chain_controls(kind, mode, scalar):
    f = prices(105); m = market(f)
    if kind in ('price', 'fear_price'):
        for field in ('open', 'high', 'low', 'close'):
            set_cell(f, field, 0, scalar(f[field].iloc[0]))
    else:
        for field in COUNTS:
            set_cell(m, field, 0, scalar(m[field].iloc[0]))
        # A valid amount inside every tested scalar's range, including int8/float16.
        set_cell(m, 'market_amount_cny', 0, scalar(100))
    originals = (f.copy(deep=True), m.copy(deep=True))
    for d in diagnose(kind, f, m, mode):
        assert d.admission is Admission.L2 and d.calculated
        VALIDATOR.validate(d.to_dict())
        json.dumps(d.to_dict(), allow_nan=False)
    pd.testing.assert_frame_equal(f, originals[0]); pd.testing.assert_frame_equal(m, originals[1])


@pytest.mark.parametrize('kind', ('price', 'fear_price', 'fear_market'))
@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('offset', (-12, -10, 0, 8, 14))
def test_equivalent_offsets_have_identical_diagnostics_and_preserve_inputs(kind, mode, offset):
    f = prices(105); m = market(f)
    baseline = diagnose(kind, f, m, mode)
    for frame in (f, m):
        for field in ('event_time', 'observed_at', 'ingested_at', 'available_at',
                      'universe_available_at', 'universe_ingested_at'):
            if field in frame:
                frame[field] = [pd.Timestamp(v).tz_convert(timezone(timedelta(hours=offset))).isoformat()
                                for v in frame[field]]
    req = request(f, mode=mode)
    req = Request(req.analysis_date,
                  pd.Timestamp(req.as_of).tz_convert(timezone(timedelta(hours=offset))).isoformat(),
                  req.symbol, req.instrument_type, req.mode)
    originals = (f.copy(deep=True), m.copy(deep=True))
    actual = diagnose(kind, f, m, mode, req=req)
    assert [d.to_dict() for d in actual] == [d.to_dict() for d in baseline]
    pd.testing.assert_frame_equal(f, originals[0]); pd.testing.assert_frame_equal(m, originals[1])


@pytest.mark.parametrize('mode', MODES)
def test_invalid_cffex_component_clears_environment_values(mode):
    f = prices(205); m = market(f); req = request(f, mode=mode)
    wave = price_diagnostics(f, request=req, source=source(), calendar=calendar(f))['wave']
    fear, = diagnose('fear_price', f, m, mode)
    for field in ('source', 'symbol', 'member'):
        fut = cffex_input(mode, field, 'bad\x7fidentity')
        result = environment_diagnostic({'wave': wave, 'fear_greed': fear, 'cffex_position': fut}, request=req)
        blocked(result, field)


@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('field,value', (('high', 10**400), ('high', Fraction(150, 1)),
                                       ('market_amount_cny', 10**400), ('market_amount_cny', Fraction(5, 2))))
def test_invalid_numeric_components_cannot_open_environment(mode, field, value):
    f = prices(205); m = market(f); req = request(f, mode=mode)
    target = f if field == 'high' else m
    set_cell(target, field, 50, value)
    wave = price_diagnostics(f, request=req, source=source(), calendar=calendar(f))['wave']
    fear, = diagnose('fear_price', f, m, mode)
    result = environment_diagnostic({'wave': wave, 'fear_greed': fear,
                                    'cffex_position': cffex_input(mode)}, request=req)
    blocked(result, field, target.trade_date.iloc[50])


@pytest.mark.parametrize('mode', MODES)
@pytest.mark.parametrize('kind', ('price', 'fear_price', 'breadth', 'fear_market'))
def test_numpy_missing_quality_retains_unknown_semantics(mode, kind):
    f = prices(105); m = market(f)
    set_cell(f if kind in ('price', 'fear_price') else m, 'quality_status', 50, np.float32('nan'))
    for d in diagnose(kind, f, m, mode):
        assert d.admission is (Admission.L1 if mode == 'research' else Admission.BLOCKED)
        assert 'quality_status' in d.missing_fields
        assert not d.to_dict()['allowed_uses']['research']


@pytest.mark.parametrize('kind', ('price', 'fear_price'))
@pytest.mark.parametrize('mode', MODES)
def test_offset_normalization_does_not_admit_a_future_acquisition(kind, mode):
    f = prices(105); m = market(f)
    req = replace(request(f, mode=mode), as_of=f.observed_at.iloc[-1])
    baseline = diagnose(kind, f, m, mode, req=req)
    for frame in (f, m):
        for field in ('event_time', 'observed_at', 'ingested_at', 'available_at'):
            frame[field] = [pd.Timestamp(v).tz_convert(timezone(timedelta(hours=-10))).isoformat()
                            for v in frame[field]]
    actual = diagnose(kind, f, m, mode, req=req)
    assert [d.to_dict() for d in actual] == [d.to_dict() for d in baseline]
    for d in actual:
        assert d.data_latest_date != f.trade_date.iloc[-1]
        assert not d.to_dict()['allowed_uses']['research']

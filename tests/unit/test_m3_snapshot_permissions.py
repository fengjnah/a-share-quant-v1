"""Offline source-shaped fixtures test permissions, never certify real data."""
from dataclasses import replace

import pytest

from ai_trade.market_analysis_contract import Receipt, Verification
from ai_trade.market_analysis_core import environment_diagnostic
from ai_trade.m3_store_results import Computation
from m3_storage_fixtures import (repo, source, batch, provenance, snapshot,
    compute, NOW, DAY, A)
from test_m3_storage_results import execute

CLAIMS = ('source_verification', 'research_authorization', 'time_verification')


def permission_case(r, uses, *, restricted='research_authorization', available=A,
                    decision='VERIFIED', expires=None):
    sid = source(r, 'index_bar', units={'price': 'index_point'})
    r.register_instrument(catalog_id='index:fixture', entity_kind='INDEX',
        namespace='synthetic', entity_key='TEST_INDEX')
    # Source-observation envelope deliberately exercises the non-synthetic gate;
    # these bytes/authority remain explicit offline fixtures, not real evidence.
    ev = r.put_evidence(b'offline permission fixture', evidence_kind='observation')
    row = dict(catalog_id='index:fixture', trade_date=DAY, open=100, high=102,
        low=99, close=101, volume=None, volume_unit=None, amount_cny=None,
        adjustment_definition='none')
    ids = r.save_index([row], [provenance(ev, evidence_kind='source_observation')],
                      batch=batch(sid, 'permission'))
    r.assess(assessment_id='quality', data_version_id=ids[0], rules_version='fixture',
        decision='PASS', reasons_json=[], metrics_json={})
    checks = [dict(check_role='quality', assessment_id='quality')]
    for claim in CLAIMS:
        r.receipt(receipt_id=claim, scope_type='SOURCE', source_id=sid,
            data_version_id=None, claims_json=dict(schema_version='m3-receipt-v1',
                claim_type=claim, issuer='test-authority',
                authority_ref='synthetic-test-authority-only',
                allowed_uses=list(uses if claim == restricted else ('research', 'storage')),
                scope='ALL_A', valid_business_range=['2026-01-01', '2026-12-31']),
            decision=decision if claim == restricted else 'VERIFIED', issued_at=available,
            available_at=available, expires_at=expires, evidence_id=ev, supersedes_id=None)
        checks.append(dict(check_role=claim, receipt_id=claim))
    return ids, checks


@pytest.mark.parametrize('mode', ['research', 'strict_backtest', 'paper_trade'])
@pytest.mark.parametrize('restricted', CLAIMS)
@pytest.mark.parametrize('uses', [[], ['display'], ['storage'], ['research'], ['research', 'storage']])
def test_snapshot_requires_explicit_research_and_storage_uses(database, tmp_path, mode, restricted, uses):
    r = repo(database, tmp_path)
    ids, checks = permission_case(r, uses, restricted=restricted)
    sid = snapshot(r, ids, checks=checks, mode=mode)
    frozen = r.get_snapshot(sid)
    complete = set(uses) >= {'research', 'storage'}
    assert frozen['snapshot']['completeness'] == (
        'COMPLETE' if complete else 'PARTIAL' if mode == 'research' else 'BLOCKED')
    reasons = frozen['snapshot']['blocking_reasons_json']
    assert reasons == ([] if complete else ['RECEIPT_USE_NOT_AUTHORIZED:' + restricted])
    assert snapshot(r, ids, checks=checks, mode=mode) == sid
    assert r.get_snapshot(sid) == frozen


@pytest.mark.parametrize('case', ['future', 'expired', 'revoked', 'untrusted', 'business_date'])
def test_permission_does_not_replace_existing_time_trust_or_date_gates(database, tmp_path, case):
    r = repo(database, tmp_path)
    ids, checks = permission_case(r, ['research', 'storage'],
        available='2026-10-23T00:00:00Z' if case == 'future' else A,
        expires=NOW if case == 'expired' else None,
        decision='REVOKED' if case == 'revoked' else 'VERIFIED')
    if case == 'untrusted':
        r.trust_roots = {}
    if case == 'revoked':
        sid = snapshot(r, ids, checks=checks, mode='strict_backtest')
        assert r.get_snapshot(sid)['snapshot']['completeness'] == 'BLOCKED'
        assert 'RECEIPT_REVOKED' in r.get_snapshot(sid)['snapshot']['blocking_reasons_json']
    else:
        with pytest.raises(ValueError):
            snapshot(r, ids, checks=checks, analysis_date='2027-01-01' if case == 'business_date' else DAY)


def verified_adapter(frozen, parameters):
    actual = compute(frozen, parameters)
    diagnostics = dict(actual.diagnostics)
    d = diagnostics['daily_trend']
    diagnostics['daily_trend'] = replace(d, source=replace(d.source,
        verification=Receipt(Verification.VERIFIED, ('source_verification',)),
        research_authorization=Receipt(Verification.VERIFIED, ('research_authorization',)),
        time_verification=Receipt(Verification.VERIFIED, ('time_verification',))))
    diagnostics['environment'] = environment_diagnostic(
        {k: v for k, v in diagnostics.items() if k != 'environment'}, request=d.request)
    return Computation(diagnostics, actual.factors)


@pytest.mark.parametrize('uses', [['display'], ['research', 'storage']])
def test_result_consumer_checks_frozen_receipt_uses_and_preserves_failure(database, tmp_path, uses):
    r = repo(database, tmp_path)
    ids, checks = permission_case(r, uses)
    sid = snapshot(r, ids, checks=checks)
    if uses == ['display']:
        with pytest.raises(ValueError, match='receipt.*use|use.*receipt'):
            execute(r, sid, adapter=verified_adapter)
        saved = r.get_run('analysis-one')
        assert saved['run']['status'] == 'FAILED'
        assert not saved['diagnostics'] and not saved['factors']
    else:
        execute(r, sid, adapter=verified_adapter)
        assert len(r.get_run('analysis-one')['diagnostics']) == 8


def test_old_complete_manifest_cannot_bypass_result_permission_check(database, tmp_path, monkeypatch):
    r = repo(database, tmp_path)
    ids, checks = permission_case(r, ['display'])
    current_check = r._check_record
    def legacy_check(*args):
        decision, warnings = current_check(*args)
        return decision, [w for w in warnings if not w.startswith('RECEIPT_USE_NOT_AUTHORIZED:')]
    # Reproduce the released sealing policy only in this isolated fixture.
    # Persist a valid old hash/COMPLETE manifest, then restore the current policy.
    with monkeypatch.context() as historical:
        historical.setattr(r, '_check_record', legacy_check)
        sid = snapshot(r, ids, checks=checks)
    before = r.get_snapshot(sid)
    assert before['snapshot']['completeness'] == 'COMPLETE'
    with pytest.raises(ValueError, match='receipt.*use|use.*receipt'):
        execute(r, sid, adapter=verified_adapter)
    assert r.get_run('analysis-one')['run']['status'] == 'FAILED'
    assert r.get_snapshot(sid) == before


def test_permission_snapshot_freezes_decisions_at_cutoff(database, tmp_path):
    r = repo(database, tmp_path)
    ids, checks = permission_case(r, ['research', 'storage'])
    sid = snapshot(r, ids, checks=checks)
    before = r.get_snapshot(sid)
    r.clock = lambda: '2026-10-23T00:00:00Z'
    from m3_storage_fixtures import receipt
    receipt(r, 'synthetic:index_bar', 'research_authorization', previous='research_authorization',
        decision='REVOKED', available='2026-10-23T00:00:00Z', label='later-revocation')
    assert r.get_snapshot(sid) == before
    assert before['snapshot']['completeness'] == 'COMPLETE'
    with pytest.raises(ValueError, match='expired/superseded'):
        snapshot(r, ids, checks=checks, as_of='2026-10-23T00:00:00Z')


@pytest.mark.parametrize('decision', ['FAIL', 'UNKNOWN'])
def test_authorized_receipts_cannot_override_latest_quality_decision(database, tmp_path, decision):
    r = repo(database, tmp_path)
    ids, checks = permission_case(r, ['research', 'storage'])
    r.clock = lambda: '2026-10-23T00:00:00Z'
    r.assess(assessment_id='quality-later', data_version_id=ids[0], rules_version='fixture',
        decision=decision, reasons_json=['offline quality decision'], metrics_json={},
        supersedes_id='quality')
    checks[0] = dict(check_role='quality', assessment_id='quality-later')
    sid = snapshot(r, ids, checks=checks, mode='strict_backtest', as_of='2026-10-23T00:00:00Z')
    result = r.get_snapshot(sid)['snapshot']
    assert result['completeness'] == 'BLOCKED'
    assert result['blocking_reasons_json'] == ['QUALITY_' + decision]

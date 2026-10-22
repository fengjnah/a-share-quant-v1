"""Exact input/decision freezes, real core outputs, replay and failure evidence."""
from copy import deepcopy
from dataclasses import replace
from pathlib import Path
import sqlite3

import pytest

from ai_trade.m3_store_results import Computation, capture_build
from ai_trade.m3_store_values import stamp
from m3_storage_fixtures import repo,index,snapshot,scope,compute,PARAMS,NOW,DAY,A,receipt
from test_m3_storage_market import report

ROOT=Path(__file__).resolve().parents[2]


def execute(r,sid,run_id='analysis-one',adapter=compute,**changes):
    args=dict(analysis_run_id=run_id,snapshot_id=sid,parameters=deepcopy(PARAMS),compute=adapter,source_root=ROOT,build=capture_build(ROOT,adapter))
    return r.execute(**(args|changes))


def test_snapshot_unknown_denominator_decisions_stay_partial(database,tmp_path):
    r=repo(database,tmp_path); _,ids,_,_=index(r,3); sid=snapshot(r,ids)
    assert snapshot(r,ids)==sid
    frozen=r.get_snapshot(sid)
    assert frozen['snapshot']['completeness']=='PARTIAL'
    assert 'SYNTHETIC_INPUT' in frozen['snapshot']['blocking_reasons_json']
    assert 'QUALITY_DECISION_MISSING' in frozen['snapshot']['blocking_reasons_json']
    assert [x['expected_sha256'] for x in frozen['items']]==[r.get_version(v)[0]['payload_sha256'] for v in ids]
    with database.connection() as c:
        with pytest.raises(sqlite3.IntegrityError,match='sealed'): c.execute('INSERT INTO input_snapshot_items SELECT * FROM input_snapshot_items WHERE snapshot_id=?',(sid,))
    blocked=snapshot(r,ids,mode='strict_backtest')
    assert r.get_snapshot(blocked)['snapshot']['completeness']=='BLOCKED'


@pytest.mark.parametrize('case',['source','duplicate','future','required','date','check'])
def test_snapshot_scope_future_and_missing_roles(database,tmp_path,case):
    r=repo(database,tmp_path); _,ids,_,_=index(r)
    args={}
    if case=='source': args['scope']=scope({'price_row':['wrong-source']})
    elif case=='duplicate': args['items']=[dict(role='price_row',data_version_id=ids[0],required=1)]*2
    elif case=='future': args['as_of']=A
    elif case=='date': args['analysis_date']='2026-10-15'
    elif case=='check': args['checks']=[dict(check_role='quality',assessment_id='not-there')]
    else:
        sid=snapshot(r,ids,scope=scope(required=['price_row','breadth']))
        assert 'MISSING_ROLE:breadth' in r.get_snapshot(sid)['snapshot']['blocking_reasons_json']; return
    with pytest.raises((ValueError,sqlite3.IntegrityError)): snapshot(r,ids,**args)


def test_snapshot_freezes_old_quality_decision_after_later_failure(database,tmp_path):
    r=repo(database,tmp_path); _,ids,_,_=index(r)
    r.assess(assessment_id='q1',data_version_id=ids[0],rules_version='fixture-q',decision='PASS',reasons_json=[],metrics_json={})
    sid=snapshot(r,ids,checks=[dict(check_role='quality',assessment_id='q1')]); before=r.get_snapshot(sid)
    r.clock=lambda:'2026-10-23T00:00:00Z'
    r.assess(assessment_id='q2',data_version_id=ids[0],rules_version='fixture-q',decision='FAIL',reasons_json=['later discovery'],metrics_json={},supersedes_id='q1')
    assert r.get_snapshot(sid)==before
    assert r.decision_at(as_of='2026-10-23T00:00:00Z',data_version_id=ids[0],rules_version='fixture-q')['decision']=='FAIL'


def test_snapshot_freezes_receipt_and_business_range(database,tmp_path):
    r=repo(database,tmp_path); sid,ids,_,_=index(r)
    rid=receipt(r,sid,'source_verification')
    snap=snapshot(r,ids,checks=[dict(check_role='source_verification',receipt_id=rid)])
    before=r.get_snapshot(snap)
    r.clock=lambda:'2026-10-23T00:00:00Z'
    receipt(r,sid,'source_verification',previous=rid,decision='REVOKED',available='2026-10-23T00:00:00Z',label='revoke')
    assert r.get_snapshot(snap)==before
    with pytest.raises(ValueError,match='expired/superseded'):
        snapshot(r,ids,as_of='2026-10-23T00:00:00Z',checks=[dict(check_role='source_verification',receipt_id=rid)])


def test_cffex_snapshot_requires_full_calendar_and_lineage_decision(database,tmp_path):
    r=repo(database,tmp_path); calendars,payload,record,p,b=report(r)
    vid=r.save_cffex(payload,record,p,batch=b,calendar_version_ids=calendars)
    sc=scope({'cffex_report':[b.source_id],'calendar_row':['synthetic:market_session']},['cffex_report'])
    args=dict(analysis_date=DAY,as_of=NOW,mode='research',scope=sc,items=[dict(role='cffex_report',data_version_id=vid,required=1)])
    with pytest.raises(ValueError,match='calendar'): r.seal_snapshot(**args)
    args['items'] += [dict(role='calendar_row',data_version_id=v,required=1) for v in calendars]
    with pytest.raises(ValueError,match='lineage assessment'): r.seal_snapshot(**args)
    args['checks']=[dict(check_role='quality',assessment_id='cffex-lineage:'+vid)]
    snap=r.seal_snapshot(**args)
    assert r.get_snapshot(snap)['snapshot']['completeness']=='PARTIAL'


def test_real_core_outputs_and_6_per_day_trace_persist_and_replay(database,tmp_path):
    r=repo(database,tmp_path); _,ids,_,_=index(r,65); sid=snapshot(r,ids)
    rid=execute(r,sid); saved=r.get_run(rid)
    assert len(saved['diagnostics'])==8 and len(saved['factors'])==65*6
    assert saved['run']['status']=='PARTIAL' and saved['run']['quality_status']=='UNKNOWN'
    actual=compute(r.get_snapshot(sid),PARAMS)
    for d in saved['diagnostics']:
        assert d['diagnostic_json']==actual.diagnostics[d['indicator']].to_dict()
        assert d['strategy_admission_json']['live_trading'] is False
        assert not d['strategy_admission_json']['strategy_allowed']
    fg=next(d for d in saved['diagnostics'] if d['indicator']=='fear_greed')
    assert fg['diagnostic_json']['values']['score'] is None
    assert {f['factor_key'] for f in saved['factors'] if f['business_date']==DAY and f['status']=='MISSING'}=={'上涨占比','涨停占比','成交额'}
    execute(r,sid,'replay-one',replay_of_run_id=rid)
    assert r.get_run('replay-one')['run']['result_sha256']==saved['run']['result_sha256']
    assert len(r.find_runs(analysis_date=DAY,as_of=NOW,snapshot_id=sid))==2
    with database.connection() as c:
        with pytest.raises(sqlite3.IntegrityError,match='sealed'): c.execute('INSERT INTO factor_values SELECT * FROM factor_values WHERE analysis_run_id=?',(rid,))
        with pytest.raises(sqlite3.IntegrityError,match='immutable'): c.execute('DELETE FROM analysis_runs WHERE analysis_run_id=?',(rid,))


def test_empty_input_runs_persist_blocking_diagnostics_no_factors(database,tmp_path):
    r=repo(database,tmp_path); sid=snapshot(r,[])
    rid=execute(r,sid); saved=r.get_run(rid)
    assert saved['run']['status']=='BLOCKED' and not saved['factors']
    assert all(x['admission']=='BLOCKED' for x in saved['diagnostics'])


def broken_adapter(frozen,parameters): raise RuntimeError('synthetic error; must not be saved as raw text')


def test_adapter_failure_records_failed_run_without_partial_results(database,tmp_path):
    r=repo(database,tmp_path); _,ids,_,_=index(r); sid=snapshot(r,ids)
    with pytest.raises(RuntimeError): execute(r,sid,adapter=broken_adapter)
    saved=r.get_run('analysis-one')
    assert saved['run']['status']=='FAILED' and not saved['diagnostics'] and not saved['factors']
    assert saved['run']['blocking_reasons_json']==['ANALYSIS_FAILED:RuntimeError']


def mutated_adapter(frozen,parameters):
    value=compute(frozen,parameters)
    frozen['inputs'].clear()
    return value


def wrong_factor_adapter(frozen,parameters):
    value=compute(frozen,parameters)
    entries=list(value.factors); entry=dict(entries[-1]); entry['weight']=.99; entries[-1]=entry
    return Computation(value.diagnostics,tuple(entries))


def false_research_adapter(frozen,parameters):
    from ai_trade.market_analysis_contract import Admission
    value=compute(frozen,parameters); ds=dict(value.diagnostics)
    ds['daily_trend']=replace(ds['daily_trend'],admission=Admission.L2)
    return Computation(ds,value.factors)


@pytest.mark.parametrize('adapter,match',[(mutated_adapter,'mutated'),(wrong_factor_adapter,'weight'),(false_research_adapter,'incomplete')])
def test_invalid_adapter_output_never_seals_partial_rows(database,tmp_path,adapter,match):
    r=repo(database,tmp_path); _,ids,_,_=index(r,3); sid=snapshot(r,ids)
    with pytest.raises(ValueError,match=match): execute(r,sid,adapter=adapter)
    saved=r.get_run('analysis-one')
    assert saved['run']['status']=='FAILED' and saved['diagnostics']==[] and saved['factors']==[]


def test_declared_build_must_equal_actual_build(database,tmp_path):
    r=repo(database,tmp_path); _,ids,_,_=index(r); sid=snapshot(r,ids)
    build=capture_build(ROOT,compute); build['code_sha']='f'*40
    with pytest.raises(ValueError,match='actual build'): execute(r,sid,build=build)
    with database.connection() as c: assert c.execute('SELECT count(*) FROM analysis_runs').fetchone()[0]==0


def test_replay_parameter_changes_are_rejected(database,tmp_path):
    r=repo(database,tmp_path); _,ids,_,_=index(r); sid=snapshot(r,ids); execute(r,sid)
    changed=deepcopy(PARAMS); changed['config_version']='changed'
    with pytest.raises(ValueError,match='replay input/config/build/review'): execute(r,sid,'bad-replay',parameters=changed,replay_of_run_id='analysis-one')
    assert r.get_run('bad-replay')['run']['status']=='FAILED'

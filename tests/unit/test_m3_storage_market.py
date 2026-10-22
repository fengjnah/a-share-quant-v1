"""Synthetic historical membership, formal aggregate gates, CFFEX round trips."""
from dataclasses import replace
import hashlib
import sqlite3

import pytest

from ai_trade.reference_data.models import Provenance as OldProvenance, SecuritySnapshot, SecurityPeriod
from ai_trade.security_master.repository import SQLiteSecurityMaster
from ai_trade.market_data.cffex_rankings import build_record, CffexRankingsClient
from ai_trade.market_data.cffex_rankings_models import CffexRankingsRequest
from ai_trade.m3_store_values import canonical, digest, stamp
from test_cffex_rankings import named, legacy
from m3_storage_fixtures import (repo, source, index, evidence, batch, provenance,receipt,NOW,DAY,T,A,I)


def universe(r,database,*,unknown=False):
    meta=OldProvenance('synthetic:security:v1','v1','2026-01-01T00:00:00Z',A,A,I,'synthetic','fixture')
    security=SecuritySnapshot('fixture:equity','600000.SH','SH','A_SHARE','2026-01-01',None,
        (SecurityPeriod('2026-01-01',None,'SYNTHETIC'),),meta)
    SQLiteSecurityMaster(database).write_many([security],run_id='old-security')
    with database.connection() as c: old=c.execute('SELECT version_id FROM security_versions').fetchone()[0]
    sid=source(r,'security_state'); ev=evidence(r,'state')
    state=dict(instrument_id='fixture:equity',effective_from='2026-01-01',effective_to=None,st_status=None if unknown else 'NORMAL',suspended=0,delisting_organization=0)
    state_id=r.save_states([state],[provenance(ev)],batch=batch(sid,'state'))[0]
    us=source(r,'universe'); record=dict(universe_key='ALL_A',trade_date=DAY,definition_version='fixture-all-a-v1',eligible_count=1)
    member=dict(instrument_id='fixture:equity',membership_status='ELIGIBLE',security_version_id=old,state_version_id=state_id,inclusion_reason='synthetic historical listing')
    uid=r.save_universe(record,[member],provenance(evidence(r,'universe')),batch=batch(us,'universe'))
    r.assess(assessment_id='universe-quality',data_version_id=uid,rules_version='fixture-q-v1',decision='PASS',reasons_json=[],metrics_json={'synthetic':True})
    return uid,state_id,old


def aggregate_setup(database,tmp_path,dataset):
    r=repo(database,tmp_path); uid,_,_=universe(r,database)
    sid=source(r,dataset,units={'amount':'CNY'})
    receipts={claim:receipt(r,sid,claim,version=uid if claim=='universe_verification' else None)
              for claim in ('source_verification','research_authorization','time_verification','universe_verification')}
    p=provenance(evidence(r,'aggregate'),available_at=NOW,observed_at=NOW,ingested_at=NOW)
    return r,uid,sid,receipts,p


def breadth_record(uid):
    return dict(universe_version_id=uid,market_key='ALL_A',trade_date=DAY,advances=1,declines=0,flat=0,
        limit_up=0,limit_down=0,suspended=0,unavailable=0,missing=0,eligible_count=1,definition_version='fixture-breadth-v1')


def test_unknown_historical_state_does_not_become_eligible(database,tmp_path):
    r=repo(database,tmp_path)
    with pytest.raises(ValueError,match='unknown historical'): universe(r,database,unknown=True)
    with database.connection() as c:
        assert c.execute('SELECT count(*) FROM universe_versions').fetchone()[0]==0
        assert c.execute("SELECT outcome FROM ingestion_attempts WHERE request_key='universe'").fetchone()[0]=='FAILED'


def test_state_overlap_is_not_silently_closed(database,tmp_path):
    r=repo(database,tmp_path); _,sid,_=universe(r,database)
    v,body,_=r.get_version(sid); body.pop('data_version_id')
    body['effective_from']='2026-10-01'
    with pytest.raises(ValueError,match='overlapping'):
        r.save_states([body],[provenance(evidence(r,'overlap'))],batch=batch(v['source_id'],'overlap'))


@pytest.mark.parametrize('change',[{'eligible_count':None},{'missing':1},{'advances':0},{'limit_up':2},{'universe_version_id':None},{'trade_date':'2026-10-15'}])
def test_breadth_requires_exact_known_partition(database,tmp_path,change):
    r,uid,sid,receipts,p=aggregate_setup(database,tmp_path,'market_breadth')
    with pytest.raises((ValueError,sqlite3.IntegrityError)):
        r.save_breadth(breadth_record(uid)|change,p,batch=batch(sid,'breadth'),receipts=receipts,universe_assessment_id='universe-quality')
    with database.connection() as c: assert c.execute('SELECT count(*) FROM market_breadth_versions').fetchone()[0]==0


def test_breadth_full_partition_saves_but_never_certifies_real_source(database,tmp_path):
    r,uid,sid,receipts,p=aggregate_setup(database,tmp_path,'market_breadth')
    vid=r.save_breadth(breadth_record(uid),p,batch=batch(sid,'breadth'),receipts=receipts,universe_assessment_id='universe-quality')
    v,body,_=r.get_version(vid)
    assert body['advances']==1 and body['flat']==0 and v['evidence_kind']=='synthetic'


@pytest.mark.parametrize('gate',['missing','revoked','expired','wrong_date','untrusted'])
def test_market_receipt_gate_fail_closed(database,tmp_path,gate):
    r,uid,sid,receipts,p=aggregate_setup(database,tmp_path,'market_breadth')
    if gate=='missing': del receipts['time_verification']
    elif gate=='revoked': receipt(r,sid,'source_verification',previous=receipts['source_verification'],decision='REVOKED',available='2026-10-17T00:00:00Z',label='revocation')
    elif gate=='expired':
        receipts['time_verification']=receipt(r,sid,'time_verification',previous=receipts['time_verification'],available='2026-10-17T00:00:00Z',expires='2026-10-18T00:00:00Z',label='expires')
    elif gate=='wrong_date':
        receipts['time_verification']=receipt(r,sid,'time_verification',previous=receipts['time_verification'],available='2026-10-17T00:00:00Z',span=['2026-10-19','2026-10-20'],label='wrong-date')
    else: r.trust_roots={}
    with pytest.raises(ValueError): r.save_breadth(breadth_record(uid),p,batch=batch(sid,'blocked'),receipts=receipts,universe_assessment_id='universe-quality')


def amount(r,uid,sid,p,*,change=None):
    raw=evidence(r,'native-total')
    manifest=dict(schema_version='m3-published-amount-v1',source_id=sid,source_version='v1',market_key='ALL_A',trade_date=DAY,
        amount_cny=100.0,amount_unit='CNY',contributing_count=1,universe_version_id=uid,raw_evidence_id=raw)
    manifest.update(change or {})
    ev=r.put_evidence(canonical(manifest).encode(),evidence_kind='observation')
    record=dict(universe_version_id=uid,market_key='ALL_A',trade_date=DAY,market_amount_cny=100.,contributing_count=1,definition_version='fixture-total-v1')
    return record,replace(p,evidence_id=ev)


def test_native_total_not_double_counted_and_all_lineage_retained(database,tmp_path):
    r,uid,sid,receipts,p=aggregate_setup(database,tmp_path,'market_amount')
    row,p=amount(r,uid,sid,p)
    vid=r.save_amount(row,p,batch=batch(sid,'amount'),receipts=receipts,universe_assessment_id='universe-quality')
    assert r.save_amount(row,p,batch=batch(sid,'duplicate'),receipts=receipts,universe_assessment_id='universe-quality')==vid
    assert r.get_version(vid)[1]['market_amount_cny']==100.
    with database.connection() as c: assert c.execute('SELECT count(*) FROM market_amount_versions').fetchone()[0]==1


@pytest.mark.parametrize('change',[{'amount_unit':'万元'},{'market_key':'SH'},{'contributing_count':2},{'amount_cny':101.},{'source_version':'other'}])
def test_native_total_manifest_must_match_exact_scope_and_unit(database,tmp_path,change):
    r,uid,sid,receipts,p=aggregate_setup(database,tmp_path,'market_amount')
    row,p=amount(r,uid,sid,p,change=change)
    with pytest.raises(ValueError,match='scope/value'): r.save_amount(row,p,batch=batch(sid,'amount'),receipts=receipts,universe_assessment_id='universe-quality')


def sessions(r):
    sid=source(r,'market_session'); ids=[]
    for d,opened in [('2026-10-16',1),('2026-10-17',0),('2026-10-18',0),('2026-10-19',1)]:
        row=dict(market_key='CFFEX',session_date=d,is_trading_day=opened,opens_at=d+'T09:30:00+08:00' if opened else None,closes_at=d+'T15:00:00+08:00' if opened else None,error_reason=None)
        p=provenance(evidence(r,'session:'+d),event_time='2026-01-01T00:00:00Z',available_at='2026-01-01T00:00:00Z',observed_at='2026-01-01T00:00:00Z',ingested_at='2026-01-01T00:00:00Z')
        ids.append(r.save_session(row,p,batch=batch(sid,d)))
    return ids


def report(r,payload=None):
    ids=sessions(r); payload=payload or named(contracts=['IF2611'])
    sid=source(r,'cffex_report',CffexRankingsClient().source_label())
    b=batch(sid,'report')
    ev=r.put_evidence(payload,evidence_kind='synthetic',media_type='text/csv',captured_at=A)
    record=build_record(CffexRankingsRequest('CFFEX','IF',DAY),payload,run_id=b.run_id,observed_at=A,ingested_at=I,calendar=r.ranking_calendar(ids),evidence_kind='synthetic')
    p=provenance(ev,record.source_version,event_time=record.event_time,available_at=record.available_at,observed_at=record.observed_at,ingested_at=record.ingested_at)
    return ids,payload,record,p,b


def test_cffex_named_zero_quantities_and_frozen_calendar_roundtrip(database,tmp_path):
    r=repo(database,tmp_path); ids,payload,record,p,b=report(r,named(contracts=['IF2610']))
    vid=r.save_cffex(payload,record,p,batch=b,calendar_version_ids=ids)
    assert r.get_cffex(vid)==record
    assert r.save_cffex(payload,record,p,batch=batch(b.source_id,'report'),calendar_version_ids=ids)==vid
    v,row,children=r.get_version(vid)
    assert row['published_at'] is None and row['scope_evidence_id'] is None
    assert row['earliest_session_date']=='2026-10-19' and len(children)==60
    assert all(c['open_interest']==0 for _,c in children if c['side']!='volume')
    with database.connection() as c:
        assert c.execute('SELECT count(*) FROM quality_assessments WHERE rules_version=?',('m3-cffex-lineage-v1',)).fetchone()[0]==1
        with pytest.raises(sqlite3.IntegrityError,match='sealed'):
            c.execute('INSERT INTO cffex_rank_rows SELECT * FROM cffex_rank_rows WHERE report_version_id=?',(vid,))


@pytest.mark.parametrize('kind',['mixed','blank'])
def test_unrepresentable_cffex_remains_evidence_and_blocked_attempt(database,tmp_path,kind):
    payload=legacy(DAY,'IF2611') if kind=='mixed' else named(contracts=['IF2611']).decode('gbk').replace('甲会员(代客)','').encode('gbk')
    r=repo(database,tmp_path); ids,payload,record,p,b=report(r,payload)
    assert r.save_cffex(payload,record,p,batch=b,calendar_version_ids=ids) is None
    assert r.evidence_bytes(p.evidence_id)==payload
    with database.connection() as c:
        assert c.execute('SELECT count(*) FROM cffex_report_versions').fetchone()[0]==0
        assert c.execute('SELECT outcome FROM ingestion_attempts WHERE attempt_id=?',(b.attempt_id,)).fetchone()[0]=='BLOCKED'
        assert c.execute('SELECT 1 FROM ingestion_runs WHERE run_id=?',(b.run_id,)).fetchone() is None


def test_missing_cffex_calendar_never_weekday_fallback(database,tmp_path):
    r=repo(database,tmp_path); ids,payload,record,p,b=report(r)
    with pytest.raises(Exception): r.save_cffex(payload,record,p,batch=b,calendar_version_ids=ids[:1])
    with database.connection() as c:
        assert c.execute('SELECT count(*) FROM cffex_report_versions').fetchone()[0]==0
        assert c.execute('SELECT outcome FROM ingestion_attempts WHERE attempt_id=?',(b.attempt_id,)).fetchone()[0]=='FAILED'

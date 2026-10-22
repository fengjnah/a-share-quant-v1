"""Evidence, provenance, legacy mapping and independent decision boundaries."""
from dataclasses import replace
import sqlite3

import pytest

from ai_trade.data_access.repository import SQLiteMarketDataRepository
from ai_trade.m3_store_values import canonical, fields, stamp
from m3_storage_fixtures import (repo, source, index, evidence, batch, provenance,
    receipt, NOW, DAY, T, A, I)


def test_evidence_content_addressed_duplicate_and_tamper(database,tmp_path):
    r=repo(database,tmp_path); ev=evidence(r)
    assert evidence(r)==ev
    with database.connection() as c: row=c.execute('SELECT * FROM evidence_objects').fetchone()
    target=r.evidence_path(row['relative_uri'])
    assert r.evidence_bytes(ev)==target.read_bytes()
    target.write_bytes(b'corrupt')
    with pytest.raises(ValueError,match='missing/oversized|corrupted'): r.evidence_bytes(ev)
    with pytest.raises(ValueError,match='conflict'): evidence(r)
    with database.connection() as c: assert c.execute('SELECT count(*) FROM evidence_objects').fetchone()[0]==1


@pytest.mark.parametrize('path',['../secret','/external','C:/external','a/../b','a\\b','./x','a:stream','https://example.org/raw'])
def test_evidence_path_escape_refused(database,tmp_path,path):
    with pytest.raises(ValueError): repo(database,tmp_path).evidence_path(path)


@pytest.mark.parametrize('value',[float('nan'),float('inf'),float('-inf'),2**70,{'password':'no'}, {'a':object()}])
def test_strict_json_no_nonfinite_or_secret(value):
    with pytest.raises(ValueError): canonical(value)


@pytest.mark.parametrize('value',[True,'1',float('inf'),float('nan'),-1,2**70])
def test_exact_integer_no_coercion(value):
    with pytest.raises(ValueError): fields('evidence_objects',dict(evidence_id='x',sha256='a'*64,relative_uri='x',byte_size=value,media_type='a',evidence_kind='synthetic',registered_at=NOW,privacy_class='private'))


def test_timezone_canonicalization():
    assert stamp('2026-10-16T16:00:00+08:00')==A
    with pytest.raises(ValueError): stamp('2026-10-16T16:00:00')


def test_source_identity_cannot_change_units(database,tmp_path):
    r=repo(database,tmp_path); sid=source(r,'index_bar',units={'price':'index_point'})
    with pytest.raises(ValueError,match='different content'): source(r,'index_bar',units={'price':'CNY'})
    with pytest.raises(ValueError): r.register_source(source_id='unsafe',provider='SYNTHETIC',endpoint_key='https://user:secret@example.org',adapter_version='v1',dataset_key='index_bar',units_json={},time_policy_version='v1')


def test_duplicate_same_content_records_attempt_without_second_run(database,tmp_path):
    r=repo(database,tmp_path); sid,ids,records,ps=index(r,2)
    assert r.save_index(records,ps,batch=batch(sid,'retry'))==ids
    assert r.save_index(records,ps,batch=batch(sid,'indices'))==ids
    with database.connection() as c:
        assert c.execute('SELECT count(*) FROM ingestion_runs').fetchone()[0]==1
        assert c.execute('SELECT count(*) FROM data_versions').fetchone()[0]==2
        assert c.execute("SELECT outcome FROM ingestion_attempts WHERE attempt_id=?",(batch(sid,'retry').attempt_id,)).fetchone()[0]=='DUPLICATE'


def test_conflicting_same_source_version_rolls_back_and_audits(database,tmp_path):
    r=repo(database,tmp_path); sid,ids,records,ps=index(r)
    with pytest.raises(sqlite3.IntegrityError): r.save_index([records[0]|{'close':100.5}],ps,batch=batch(sid,'conflict'))
    with database.connection() as c:
        assert c.execute('SELECT count(*) FROM data_versions').fetchone()[0]==1
        assert c.execute('SELECT count(*) FROM ingestion_runs').fetchone()[0]==1
        assert c.execute("SELECT outcome FROM ingestion_attempts WHERE attempt_id=?",(batch(sid,'conflict').attempt_id,)).fetchone()[0]=='FAILED'


def test_batch_failure_is_atomic_and_not_successful_run(database,tmp_path):
    r=repo(database,tmp_path); sid,ids,records,ps=index(r)
    values=[records[0]|{'trade_date':'2026-10-15'},records[0]|{'trade_date':'2026-10-14','high':50}]
    with pytest.raises(sqlite3.IntegrityError): r.save_index(values,[ps[0],ps[0]],batch=batch(sid,'broken'))
    with database.connection() as c:
        assert c.execute('SELECT count(*) FROM index_bar_versions').fetchone()[0]==1
        assert c.execute('SELECT count(*) FROM ingestion_runs').fetchone()[0]==1
        assert c.execute("SELECT committed_run_id FROM ingestion_attempts WHERE outcome='FAILED'").fetchone()[0] is None


def test_latest_quarantine_never_falls_back_to_old_accepted(database,tmp_path):
    r=repo(database,tmp_path); sid,ids,records,ps=index(r)
    revised=replace(ps[0],record_version='v2',quality_status='quarantined',available_at='2026-10-17T08:00:00Z',observed_at='2026-10-17T08:00:00Z',ingested_at='2026-10-17T08:01:00Z',supersedes_id=ids[0],revision_reason='synthetic correction')
    new=r.save_index([records[0]|{'close':100.5}],[revised],batch=batch(sid,'revision'))[0]
    key=dict(catalog_id='index:fixture',trade_date=DAY,adjustment_definition='none')
    assert r.select_visible(dataset='index_bar',business_key=key,source_id=sid,as_of=I,mode='strict_backtest')[0]['data_version_id']==ids[0]
    assert r.select_visible(dataset='index_bar',business_key=key,source_id=sid,as_of=NOW,mode='research')[0]['data_version_id']==new
    with pytest.raises(ValueError,match='no fallback'): r.select_visible(dataset='index_bar',business_key=key,source_id=sid,as_of=NOW,mode='strict_backtest')
    with pytest.raises(sqlite3.IntegrityError): r.save_index([records[0]],[replace(revised,record_version='v3')],batch=batch(sid,'fork'))


def test_legacy_bar_keeps_unknown_observation_and_old_rows(database,tmp_path,bar):
    SQLiteMarketDataRepository(database).write_many([bar],run_id='old')
    r=repo(database,tmp_path); source(r,'daily_bar',bar.source,{'amount':'CNY'})
    with database.connection() as c:
        before=[tuple(x) for x in c.execute('SELECT * FROM daily_bar_versions')]
        old_id=before[0][0]
    vid=r.link_legacy('daily_bar',old_id)
    assert r.link_legacy('daily_bar',old_id)==vid
    v,old,_=r.get_version(vid)
    assert v['observed_at'] is None and old['ingested_at']==stamp(bar.ingested_at)
    with database.connection() as c: assert [tuple(x) for x in c.execute('SELECT * FROM daily_bar_versions')]==before
    with pytest.raises(ValueError,match='no fallback'):
        r.select_visible(dataset='daily_bar',business_key=v['business_key'],source_id=bar.source,as_of=NOW,mode='strict_backtest')


def test_receipts_trust_expiry_revocation_and_asof(database,tmp_path):
    r=repo(database,tmp_path); sid=source(r,'market_breadth')
    first=receipt(r,sid,'source_verification')
    assert r.decision_at(as_of=I,source_id=sid,claim_type='source_verification')['receipt_id']==first
    latest=receipt(r,sid,'source_verification',decision='REVOKED',previous=first,available='2026-10-17T08:00:00Z',label='revoked')
    assert r.decision_at(as_of=NOW,source_id=sid,claim_type='source_verification')['decision']=='REVOKED'
    assert r.decision_at(as_of=I,source_id=sid,claim_type='source_verification')['receipt_id']==first
    r.trust_roots={}
    with pytest.raises(ValueError,match='untrusted'): receipt(r,sid,'time_verification')
    with pytest.raises(ValueError,match='trust root'): r.decision_at(as_of=I,source_id=sid,claim_type='source_verification')


def test_expired_and_ambiguous_receipts_fail_closed(database,tmp_path):
    r=repo(database,tmp_path); sid=source(r,'market_breadth')
    receipt(r,sid,'source_verification',expires='2026-10-17T08:00:00Z')
    assert r.decision_at(as_of=NOW,source_id=sid,claim_type='source_verification') is None
    receipt(r,sid,'source_verification',label='ambiguous')
    with pytest.raises(ValueError,match='ambiguous'): r.decision_at(as_of=I,source_id=sid,claim_type='source_verification')


def test_quality_no_backdate_no_pick_pass_among_roots(database,tmp_path):
    r=repo(database,tmp_path); _,ids,_,_=index(r)
    row=dict(assessment_id='one',data_version_id=ids[0],rules_version='fixture-q-v1',decision='PASS',reasons_json=[],metrics_json={})
    with pytest.raises(ValueError,match='actual'): r.assess(**(row|{'assessed_at':A}))
    r.assess(**row)
    r.assess(**(row|{'assessment_id':'two','decision':'FAIL','reasons_json':['fixture']}))
    with pytest.raises(ValueError,match='ambiguous'): r.decision_at(as_of=NOW,data_version_id=ids[0],rules_version='fixture-q-v1')

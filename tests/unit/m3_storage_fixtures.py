"""Synthetic declarations only; none certify a vendor, market or deployment."""
from dataclasses import replace
import hashlib
import json

import pandas as pd

from ai_trade.m3_store_catalog import Batch, Provenance
from ai_trade.m3_store_results import Computation, M3ResultRepository
from ai_trade.m3_store_values import canonical, stamp
from ai_trade.market_analysis import fear_greed_with_trace
from ai_trade.market_analysis_contract import Request, SourceEvidence
from ai_trade.market_analysis_core import (price_diagnostics, breadth_diagnostic,
    fear_greed_diagnostic,cffex_diagnostic,environment_diagnostic)
from ai_trade.market_data.cffex_rankings_models import MemberScope

NOW='2026-10-22T00:00:00.000000+00:00'
DAY='2026-10-16'
T='2026-10-16T07:00:00.000000+00:00'
A='2026-10-16T08:00:00.000000+00:00'
I='2026-10-16T08:01:00.000000+00:00'
AUTHORITY={'test-authority':dict(authority_ref='synthetic-test-authority-only',scope_types=['SOURCE','DATA','REVIEW'],
    claim_types=['source_verification','research_authorization','time_verification','universe_verification','scope_verification','publication_verification','review'],
    allowed_uses=['research','storage','display'])}


def repo(database,tmp_path):
    return M3ResultRepository(database,tmp_path/'evidence',clock=lambda:NOW,trust_roots=AUTHORITY)


def source(r,dataset,source_id=None,units=None):
    sid=source_id or 'synthetic:'+dataset
    r.register_source(source_id=sid,provider='SYNTHETIC',endpoint_key='fixture:'+sid,adapter_version='test-v1',
        dataset_key=dataset,units_json=units or {},time_policy_version='synthetic-time-v1')
    return sid


def batch(sid,label='one',finished=NOW):
    run_source=hashlib.sha256(sid.encode()).hexdigest()[:16]
    return Batch('attempt:'+sid+':'+label,'run:'+run_source+':'+label,sid,label,
        {'schema_version':'m3-request-v1','parameters':{'operation':'fixture'}},I,finished)


def provenance(evidence,version='v1',**changes):
    return replace(Provenance(version,T,A,A,I,evidence,'accepted','synthetic'),**changes)


def evidence(r,value='fixture'):
    return r.put_evidence(canonical({'synthetic':value}).encode(),evidence_kind='synthetic',captured_at=NOW)


def index(r,n=1):
    sid=source(r,'index_bar',units={'price':'index_point'})
    r.register_instrument(catalog_id='index:fixture',entity_kind='INDEX',namespace='synthetic',entity_key='TEST_INDEX')
    days=pd.bdate_range(end=DAY,periods=n).strftime('%Y-%m-%d')
    records=[dict(catalog_id='index:fixture',trade_date=d,open=100+i,high=102+i,low=99+i,close=101+i,
                  volume=None,volume_unit=None,amount_cny=None,adjustment_definition='none') for i,d in enumerate(days)]
    ev=evidence(r,'index-series')
    ps=[provenance(ev,event_time=d+'T07:00:00Z',available_at=d+'T08:00:00Z',observed_at=d+'T08:00:00Z',ingested_at=d+'T08:01:00Z') for d in days]
    ids=r.save_index(records,ps,batch=batch(sid,'indices'))
    return sid,ids,records,ps


def scope(sources=None,required=None):
    return dict(schema_version='m3-scope-v1',market='ALL_A',symbols=['TEST_INDEX','IF'],
                required_roles=required or ['price_row'],source_bindings=sources or {'price_row':['synthetic:index_bar']})


def snapshot(r,ids,**changes):
    args=dict(analysis_date=DAY,as_of=NOW,mode='research',scope=scope(),
              items=[dict(role='price_row',data_version_id=v,required=1) for v in ids])
    return r.seal_snapshot(**(args|changes))


def receipt(r,sid,claim,*,version=None,decision='VERIFIED',previous=None,available=A,expires=None,label=None,span=None):
    ev=r.put_evidence(canonical({'synthetic_receipt':label or claim,'available':available,'decision':decision}).encode(),evidence_kind='receipt')
    rid=label or claim+':'+(version or sid)
    r.receipt(receipt_id=rid,scope_type='DATA' if version else 'SOURCE',source_id=None if version else sid,data_version_id=version,
        claims_json=dict(schema_version='m3-receipt-v1',claim_type=claim,issuer='test-authority',authority_ref='synthetic-test-authority-only',allowed_uses=['research','storage'],scope='ALL_A',valid_business_range=span or ['2026-01-01','2026-12-31']),
        decision=decision,issued_at=available,available_at=available,expires_at=expires,evidence_id=ev,supersedes_id=previous)
    return rid


def compute(frozen,parameters):
    """Test adapter calls the existing core; intentionally uncertified inputs."""
    p=frozen['snapshot']; req=Request(p['analysis_date'],p['as_of'],'TEST_INDEX',mode=p['mode'])
    inputs=[x for x in frozen['inputs'] if x['item']['role']=='price_row']
    source_evidence=SourceEvidence('synthetic:index_bar','fixture-series',tuple(x['version']['data_version_id'] for x in inputs) or ('NO_INPUT',),evidence_kind='synthetic')
    frame=pd.DataFrame([dict(x['record'],symbol='TEST_INDEX',source='synthetic:index_bar',quality_status=x['version']['quality_status'],adjustment_method='none',
        **{k:x['version'][k] for k in ('event_time','available_at','observed_at','ingested_at')}) for x in inputs])
    if frame.empty: frame=pd.DataFrame(columns=['trade_date','open','high','low','close'])
    diagnostics=price_diagnostics(frame,request=req,source=source_evidence)
    diagnostics['fear_greed']=fear_greed_diagnostic(frame,request=req,source=source_evidence)
    diagnostics['market_breadth']=breadth_diagnostic(pd.DataFrame(),request=Request(p['analysis_date'],p['as_of'],'ALL_A','ALL_A',p['mode']),source=source_evidence)
    diagnostics['cffex_position']=cffex_diagnostic([],request=Request(p['analysis_date'],p['as_of'],'IF','CFFEX',p['mode']),source=source_evidence,member='fixture',scope=MemberScope.AGENT,contract='IF2611')
    diagnostics['environment']=environment_diagnostic(diagnostics,request=req)
    factors=()
    if not frame.empty:
        _,trace=fear_greed_with_trace(frame.drop(columns=['amount_cny']),analysis_date=req.analysis_date,as_of=req.as_of)
        factors=tuple(trace)
    return Computation(diagnostics,factors)


PARAMS=dict(schema_version='m3-analysis-parameters-v1',config_version='synthetic-fixture-v1',values={})

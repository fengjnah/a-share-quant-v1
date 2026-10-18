"""Evidence and planning invariants; every test is offline and database-free."""
import copy
import hashlib
import json
import re
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest

from ai_trade.project_progress.core import (
    ROOT, METRICS, PlanError, calculate, load, propose, read_json, seal, snapshots, validate,
)
from ai_trade.project_progress.render import board, roadmap
from ai_trade.project_progress.views import recent_deliveries, task_rows


@pytest.fixture
def data():
    return load()


def reseal(data):
    for i, event in enumerate(data['events']):
        data['events'][i] = seal(event, data['events'][i-1]['hash'] if i else '0'*64)
    return data


def feedback(data, task='TASK-002', acceptance='offline', status='FAIL'):
    e = copy.deepcopy(snapshots(data)[task])
    e['state'] = 'PARTIAL'
    e['at'] = data['updated_at']
    e['reason'] = 'synthetic feedback fixture, not an actual project regression'
    e['results'][acceptance] = {'status':status,'evidence':[]}
    return {'event':e,'new_evidence':[]}


def test_independent_decimal_recomputation_and_zero_credit_plans(data):
    latest = {e['task_id']:e for e in data['events']}
    total = Decimal(0)
    for stage in data['stages']:
        for task in data['tasks']:
            if task['stage'] != stage['id']:
                continue
            e = latest[task['id']]
            points = sum(Decimal(str(a['weight'])) for a in task['acceptance']
                         if e['results'][a['id']]['status']=='PASS')
            if e['state'] in ('PLANNED','REJECTED'):
                points=Decimal(0)
            total += Decimal(str(stage['weight'])) * Decimal(str(task['weight'])) * points/10000
    assert calculate(data)['project_percent'] == float(total)
    assert 0 < total < 100
    for t in data['tasks']:
        if t['origin']=='SUGGESTION':
            assert calculate(data)['task_percent'][t['id']]==0


@pytest.mark.parametrize('change', ['negative','bool','project_total','task_total','ac_total','duplicate','missing_reference','cycle','NaN'])
def test_invalid_plan_is_rejected(data, change):
    if change=='negative':data['stages'][0]['weight']=-1
    if change=='bool':data['stages'][0]['weight']=True
    if change=='project_total':data['stages'][0]['weight']+=1
    if change=='task_total':data['tasks'][0]['weight']=1
    if change=='ac_total':data['tasks'][0]['acceptance'][0]['weight']=99
    if change=='duplicate':data['tasks'].append(copy.deepcopy(data['tasks'][0]))
    if change=='missing_reference':data['tasks'][0]['depends_on']=[{'task':'TASK-NONEXISTENT','acceptance':[]}]
    if change=='cycle':data['stages'][0]['depends_on']=['S2']
    if change=='NaN':data['stages'][0]['weight']=float('nan')
    with pytest.raises((PlanError,ValueError)):
        validate(data)


@pytest.mark.parametrize('kind', ['missing','wrong_type','planned_pass','task_pass','review','production','merge'])
def test_evidence_and_lifecycle_cannot_be_conflated(data, kind):
    e = data['events'][0]
    if kind=='missing':next(iter(e['results'].values()))['evidence']=[]
    if kind=='wrong_type':next(iter(e['results'].values()))['evidence']=['E-PR']
    if kind=='planned_pass':e['state']='PLANNED'
    if kind=='task_pass':
        e['state']='PASS';next(iter(e['results'].values()))['status']='UNVERIFIED'
    if kind=='review':e['review']={'status':'PASS','evidence':['E-002-offline']}
    if kind=='production':e['production']={'status':'PASS','evidence':['E-PR']}
    if kind=='merge':
        e=next(x for x in data['events'] if x['task_id']=='TASK-016');e['prs']=[]
    reseal(data)
    with pytest.raises(PlanError):validate(data)


def test_feedback_preserves_history_reduces_progress_and_blocks_dependents(data):
    before = copy.deepcopy(data)
    updated = propose(data, feedback(data))
    assert data==before
    assert updated['events'][:-1]==before['events']
    assert calculate(updated)['project_percent'] < calculate(data)['project_percent']
    blockers={b['id']:b for b in calculate(updated)['blockers']}
    assert 'TASK-003' in blockers
    assert 'TASK-002:offline' in blockers['TASK-003']['dependencies']
    assert calculate(updated)['next']['id']!='TASK-PLAN-BACKTEST'


def test_rejected_retains_history_but_never_earns_completion(data):
    f=feedback(data);f['event']['state']='REJECTED'
    updated=propose(data,f)
    assert calculate(updated)['task_percent']['TASK-002']==0
    assert calculate(updated)['state_counts']['REJECTED']==1


def test_tampered_history_and_criteria_revision_are_rejected(data):
    altered=copy.deepcopy(data);altered['events'][0]['reason']='rewritten'
    with pytest.raises(PlanError,match='hash'):validate(altered)
    reseal(altered)
    with pytest.raises(PlanError,match='prefix'):validate(altered,baseline=data)
    altered=copy.deepcopy(data);altered['tasks'][0]['acceptance'][0]['label']='lowered threshold'
    with pytest.raises(PlanError,match='plan'):validate(altered,baseline=data)


@pytest.mark.parametrize('checkout_newline', ['LF', 'CRLF'])
def test_formal_docs_and_local_evidence_hashes_are_reproducible(data, checkout_newline):
    assert (ROOT/'docs/TASK_BOARD.md').read_text(encoding='utf-8')==board(data)
    assert (ROOT/'docs/ROADMAP_V1_3.md').read_text(encoding='utf-8')==roadmap(data)
    formats=read_json(ROOT/'docs/evidence/TASK_018_HASH_FORMAT.json')
    assert formats['default_recorded_bytes']=='UTF-8 LF'
    crlf_ids=set(formats['historical_crlf_evidence_ids'])
    assert crlf_ids <= {e['id'] for e in data['evidence']}
    for ev in data['evidence']:
        if ev['ref'].startswith(('docs/','src/','tests/')):
            raw=(ROOT/ev['ref']).read_bytes().replace(b'\r\n',b'\n')
            # Emulate both clean Git checkout formats, then reconstruct the recorded format.
            if checkout_newline=='CRLF':raw=raw.replace(b'\n',b'\r\n')
            recorded=raw.replace(b'\r\n',b'\n')
            if ev['id'] in crlf_ids:recorded=recorded.replace(b'\n',b'\r\n')
            assert hashlib.sha256(recorded).hexdigest()==ev['sha256'],ev['id']


def test_governance_entry_points_and_local_document_links_resolve():
    """A published policy must be reachable from the actual execution entry points."""
    files = ['AGENTS.md', 'docs/tasks/TASK_TEMPLATE.md', 'docs/OPEN_SOURCE_RESEARCH_POLICY.md',
             'docs/TASK_BOARD.md', 'docs/ROADMAP_V1_3.md']
    policy = ROOT/'docs/OPEN_SOURCE_RESEARCH_POLICY.md'
    for name in files:
        path = ROOT/name
        targets = []
        for destination in re.findall(r'\[[^\]]+\]\(([^)]+)\)', path.read_text(encoding='utf-8')):
            parsed = urlsplit(destination)
            if parsed.scheme or not parsed.path:
                continue
            target = (path.parent/unquote(parsed.path)).resolve()
            assert target.exists(), (name, destination)
            targets.append(target)
        if path != policy:
            assert policy.resolve() in targets, name


def test_duplicate_json_keys_and_nonfinite_are_not_silently_accepted(tmp_path):
    for content in ['{"x":1,"x":2}', '{"x":NaN}']:
        p=tmp_path/'invalid.json';p.write_text(content,encoding='utf-8')
        with pytest.raises(PlanError):read_json(p)


def test_cli_read_only_simulation_and_candidate_exclusive_creation(data,tmp_path):
    digest=hashlib.sha256(METRICS.read_bytes()).hexdigest()
    run=lambda *args: subprocess.run([sys.executable,'-m','ai_trade.project_progress',*args],
                                    cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=30)
    assert run('--check-docs').returncode==0
    scenario=run('--simulate','TASK-002','offline','FAIL')
    assert scenario.returncode==0,scenario.stdout
    simulated=json.loads(scenario.stdout)
    assert simulated['after_percent']<simulated['before_percent']
    assert 'TASK-003' in simulated['impacted_dependencies']
    f=tmp_path/'feedback.json';f.write_text(json.dumps(feedback(data)),encoding='utf-8')
    target=tmp_path/'candidate.json'
    assert run('--propose',str(f),'--candidate',str(target)).returncode==0
    candidate_bytes=target.read_bytes()
    assert run('--propose',str(f),'--candidate',str(target)).returncode==2
    assert target.read_bytes()==candidate_bytes
    assert run('--propose',str(f),'--candidate',str(METRICS)).returncode==2
    assert hashlib.sha256(METRICS.read_bytes()).hexdigest()==digest


def test_no_formal_strategy_recommendation_before_data_and_time_review(data):
    missing={b['id']:b['dependencies'] for b in calculate(data)['blockers']}
    assert missing['TASK-PLAN-BACKTEST']
    assert any('TASK-PLAN-TIME-REVIEW' in d for d in missing['TASK-PLAN-BACKTEST'])
    assert not any(e['review']['status']=='PASS' for e in data['events'])


@pytest.mark.parametrize('change',['hours','timestamp','suggestion_state','schema_extra','no_mandatory'])
def test_invalid_feedback_and_metadata_fail_closed(data,change):
    if change=='hours':
        t=next(t for t in data['tasks'] if t['estimated_hours']);t['estimated_hours'].update(low=99,high=1)
    if change=='timestamp':data['events'][-1]['at']='2020-01-01T00:00:00Z'
    if change=='suggestion_state':
        suggestion=next(t['id'] for t in data['tasks'] if t['origin']=='SUGGESTION')
        next(e for e in data['events'] if e['task_id']==suggestion)['state']='READY'
    if change=='schema_extra':data['tasks'][0]['invented_percent']=100
    if change=='no_mandatory':data['tasks'][0]['acceptance'][0]['mandatory']=False
    reseal(data)
    with pytest.raises(PlanError):validate(data)


def test_rejected_scenario_does_not_subtract_credit_twice(data,tmp_path):
    f=feedback(data);f['event']['state']='REJECTED'
    rejected=propose(data,f);p=tmp_path/'rejected.json';p.write_text(json.dumps(rejected),encoding='utf-8')
    r=subprocess.run([sys.executable,'-m','ai_trade.project_progress','--metrics',str(p),
                      '--simulate','TASK-002','code','FAIL'],cwd=ROOT,capture_output=True,text=True,encoding='utf-8')
    assert r.returncode==0,r.stdout
    result=json.loads(r.stdout)
    assert result['after_percent']==result['before_percent']


def test_delivery_feedback_keeps_original_plan_and_event_prefix(data):
    # Trusted pre-update event hash, not a freshly resealed rewrite of old history.
    assert data['events'][43]['hash']=='b902e289735801cfe9b94f66640fb048260c5d73d083a36ebab8adf6a9f034f5'
    assert data['plan_version']=='1.0'
    assert len(data['tasks'])==40
    assert calculate(data)['project_percent']==21.85
    event=snapshots(data)['TASK-018']
    assert event['results']['merge']['status']=='PASS'
    assert event['review']['status']=='UNVERIFIED'
    assert event['state']=='PARTIAL'
    assert event['production']['status']=='NOT_RUN'
    assert all(calculate(data)['stage_percent'][f'S{i}']==0 for i in range(5,11))


def test_delivery_projection_requires_current_citation_commit_and_pr_type(data):
    ids={e['id'] for e in recent_deliveries(data)}
    assert ids=={'E-PROGRESS-21','E-DELIVERY-23','E-DELIVERY-24','E-DELIVERY-25'}
    assert not {'E-M2-LIVE','E-M2-OFFLINE','E-M2-UI'} & ids
    assert len(recent_deliveries(data,limit=2))==2
    data['evidence'].append({**data['evidence'][-1], 'id':'synthetic-uncited', 'kind':'pr'})
    assert 'synthetic-uncited' not in {e['id'] for e in recent_deliveries(data)}
    for event in data['events']:
        event['basis']=[ref for ref in event['basis'] if ref!='E-DELIVERY-25']
    assert 'E-DELIVERY-25' not in {e['id'] for e in recent_deliveries(data)}


def test_task_matrix_does_not_conflate_code_live_review_merge_and_production(data):
    before=copy.deepcopy(data)
    rows={r['TASK']:r for r in task_rows(data,calculate(data))}
    assert rows['TASK-018']['PR']=='#21 MERGED'
    assert rows['TASK-018']['UI']=='PASS'
    assert rows['TASK-018']['独立审查']=='UNVERIFIED'
    assert rows['TASK-018']['生产准入']=='NOT_RUN'
    assert rows['TASK-004A']['真实源']=='FAIL'
    assert rows['TASK-015']['真实源']=='UNVERIFIED'
    assert rows['TASK-009']['UI']=='未单列'
    assert rows['TASK-PLAN-SELECTION']['状态']=='PLANNED'
    assert rows['TASK-PLAN-SELECTION']['代码']=='UNVERIFIED'
    assert data==before


def test_delivery_order_compares_instants_not_timezone_strings(data):
    a=next(e for e in data['evidence'] if e['id']=='E-DELIVERY-24')
    b=next(e for e in data['evidence'] if e['id']=='E-DELIVERY-25')
    a['recorded_at']='2026-10-18T23:10:00Z'
    b['recorded_at']='2026-10-19T07:09:15+08:00'
    assert recent_deliveries(data)[0]['id']=='E-DELIVERY-24'

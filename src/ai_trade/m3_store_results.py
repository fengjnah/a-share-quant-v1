"""Explicit M3 runs over sealed inputs. No page hook, scheduler or publisher.

The caller supplies a reviewed computation adapter. Stored code is never
executed. Replay uses the same adapter/build and exact frozen inputs/decisions.
"""
from dataclasses import dataclass
import hashlib
from importlib import metadata
import inspect
from pathlib import Path
import platform
import subprocess

from ai_trade.market_analysis import WEIGHTS
from ai_trade.market_analysis_contract import (
    Admission, CALCULATION_VERSION, CONTRACT_VERSION, Diagnostic, Status,
    strategy_admission,
)
from ai_trade.m3_store_snapshots import SnapshotRepository
from ai_trade.m3_store_values import canonical, digest, fields, insert, one, rows, stamp, text


INDICATORS = {'daily_trend','weekly_structure','wave','market_breadth',
              'fear_greed','price_proxy','cffex_position','environment'}
ADMISSION = {Admission.BLOCKED:'BLOCKED', Admission.L1:'L1',
             Admission.L2:'L2', Admission.L3:'L3'}


@dataclass(frozen=True)
class Computation:
    diagnostics: dict[str, Diagnostic]
    factors: tuple[dict, ...] = ()


def capture_build(root, compute):
    """Actual local source identity, including uncommitted/untracked Python.

    Dirty builds can produce isolated PARTIAL/BLOCKED evidence, never SUCCESS.
    This is reproducibility metadata, not a source or review certificate.
    """
    root=Path(root).resolve()
    def git(*args):
        return subprocess.check_output(['git','-C',str(root),*args],text=True,encoding='utf-8').strip()
    sha=git('rev-parse','HEAD')
    files={p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
           for p in sorted((root/'src'/'ai_trade').rglob('*.py'))}
    adapter=Path(inspect.getsourcefile(compute) or '').resolve()
    if not adapter.is_file(): raise ValueError('file-backed computation adapter required')
    return {'schema_version':'m3-build-v1','code_sha':sha,'source_sha256':digest(files),
            'source_dirty':bool(git('status','--porcelain','--untracked-files=all','--','src/ai_trade')),
            'adapter_sha256':hashlib.sha256(adapter.read_bytes()).hexdigest(),
            'adapter_name':compute.__module__+'.'+compute.__qualname__,
            'python':platform.python_version(),'sqlite':__import__('sqlite3').sqlite_version,
            'dependencies':{k:metadata.version(k) for k in ('pandas','jsonschema')}}


def result_hash(snapshot_id, parameters, diagnostics, factors, dependencies):
    # Run/creation/consumption times are execution facts, not analysis values.
    return digest({'snapshot_id':snapshot_id,'parameters':parameters,
        'diagnostics':[{k:v for k,v in d.items() if k!='analysis_run_id'} for d in diagnostics],
        'factors':[{k:v for k,v in f.items() if k!='analysis_run_id'} for f in factors],
        'dependencies':[{k:v for k,v in d.items() if k not in ('analysis_run_id','consumed_at')} for d in dependencies]})


class M3ResultRepository(SnapshotRepository):
    def _diagnostics(self, computation, frozen, run_id, code_sha, review):
        if not isinstance(computation,Computation) or set(computation.diagnostics)!=INDICATORS:
            raise ValueError('exact eight core diagnostics required')
        p=frozen['snapshot']; result=[]
        known_versions={x['version']['data_version_id'] for x in frozen['inputs']}
        for key in sorted(INDICATORS):
            d=computation.diagnostics[key]
            if not isinstance(d,Diagnostic) or d.indicator!=key or d.schema_version!=CONTRACT_VERSION or d.definitions_version!=CALCULATION_VERSION:
                raise ValueError('core Diagnostic and current contract/rules required')
            if (d.request.analysis_date!=p['analysis_date'] or stamp(d.request.as_of)!=p['as_of']
                    or d.request.mode!=p['mode']): raise ValueError('diagnostic request/snapshot mismatch')
            if d.request.symbol not in {p['scope_json']['market'],*p['scope_json']['symbols']}:
                raise ValueError('diagnostic symbol outside frozen scope')
            if d.data_latest_date is not None and d.data_latest_date>p['analysis_date']:
                raise ValueError('future diagnostic business date')
            if any(v is not None and stamp(v)>p['as_of'] for v in d.times.values()):
                raise ValueError('future diagnostic time')
            if d.admission is Admission.L3: raise ValueError('core cannot grant L3; use separately reviewed strategy gate')
            if d.admission is Admission.L2 and p['completeness']!='COMPLETE':
                raise ValueError('incomplete snapshot cannot claim research admission')
            def numeric(v):
                if type(v) in (int,float): return True
                if isinstance(v,dict): return any(numeric(x) for x in v.values())
                if isinstance(v,(list,tuple)): return any(numeric(x) for x in v)
                return False
            if d.status is Status.INVALID_DATA and (d.values or d.calculated): raise ValueError('invalid diagnostic must clear values')
            if (d.status is Status.BLOCKED or d.admission is Admission.BLOCKED) and (numeric(d.values) or d.calculated or d.values.get('direction') is not None):
                raise ValueError('blocked diagnostic must not retain usable numbers/direction')
            # An observation must bind concrete version IDs, not an arbitrary
            # path or a free-form source label. Empty inputs may only block.
            if d.admission is not Admission.BLOCKED and not known_versions.intersection(d.source.lineage_refs):
                raise ValueError('observed diagnostic lacks frozen input lineage')
            receipts={x['decision'].get('receipt_id'):x['decision'] for x in frozen['decisions'] if x['check']['receipt_id']}
            for role,receipt in [('source_verification',d.source.verification),
                                 ('research_authorization',d.source.research_authorization),
                                 ('time_verification',d.source.time_verification)]:
                if key=='environment':
                    # Core-derived receipts reference component diagnostic
                    # hashes, never independently certify any source.
                    if not set(receipt.refs).issubset({x.data_snapshot_id for x in computation.diagnostics.values()}): raise ValueError('derived receipt component mismatch')
                    continue
                if receipt.verified and any(r not in receipts or receipts[r]['claims_json']['claim_type']!=role or receipts[r]['decision']!='VERIFIED' for r in receipt.refs):
                    raise ValueError('core verification must bind frozen matching receipts')
            value=d.to_dict(); canonical(value)
            gate=strategy_admission(d,implementation_sha=code_sha,review=review)
            result.append(fields('m3_diagnostics',dict(analysis_run_id=run_id,indicator=key,
                input_snapshot_id=p['snapshot_id'],diagnostic_snapshot_id=d.data_snapshot_id,
                status=d.status.value,admission=ADMISSION[d.admission],calculated=int(d.calculated),
                data_latest_date=d.data_latest_date,diagnostic_json=value,strategy_admission_json=gate)))
        return result

    def _factors(self, computation, frozen, run_id):
        parent=frozen['snapshot']; diag=computation.diagnostics['fear_greed']; factors=[]; by_day={}
        unavailable=diag.status in (Status.INVALID_DATA,Status.BLOCKED) or diag.admission is Admission.BLOCKED
        if unavailable and computation.factors: raise ValueError('blocked score cannot publish factor values')
        expected={'factor_key','business_date','raw_value','raw_unit','normalized_value',
                  'normalization_version','weight','contribution','status','reasons_json'}
        for entry in computation.factors:
            if set(entry)!=expected or entry['factor_key'] not in WEIGHTS: raise ValueError('factor trace schema mismatch')
            f=fields('factor_values',dict(entry,analysis_run_id=run_id,indicator='fear_greed',input_snapshot_id=parent['snapshot_id']))
            if f['business_date']>parent['analysis_date'] or f['normalization_version']!=CALCULATION_VERSION or f['weight']!=WEIGHTS[f['factor_key']] or f['raw_unit']!='ratio':
                raise ValueError('factor time/rules/unit/weight mismatch')
            if f['status']=='AVAILABLE':
                if f['raw_value'] is None or f['normalized_value'] is None or f['contribution']!=f['normalized_value']*f['weight'] or f['reasons_json']:
                    raise ValueError('available factor raw/normalized/contribution mismatch')
            elif f['normalized_value'] is not None or f['contribution'] is not None or not f['reasons_json']:
                raise ValueError('unavailable factor needs explicit NULL and reasons')
            day=by_day.setdefault(f['business_date'],{})
            if f['factor_key'] in day: raise ValueError('duplicate factor')
            day[f['factor_key']]=f; factors.append(f)
        if any(set(values)!=set(WEIGHTS) for values in by_day.values()): raise ValueError('six factors per represented day required')
        historical=diag.values.get('historical_scores',[])
        if set(by_day)!={x['trade_date'] for x in historical}: raise ValueError('trace dates must exactly match core score history')
        for row in historical:
            fs=by_day[row['trade_date']]
            score=sum(fs[k]['contribution'] for k in WEIGHTS) if all(fs[k]['status']=='AVAILABLE' for k in WEIGHTS) else None
            if row['score']!=score: raise ValueError('trace weighted score differs from core')
        if by_day:
            latest=by_day[max(by_day)]
            if any(diag.values.get('factors',{}).get(k)!=latest[k]['normalized_value'] for k in WEIGHTS): raise ValueError('latest factors differ from core diagnostic')
            if diag.values.get('weights')!=WEIGHTS: raise ValueError('core weight definition differs')
        return sorted(factors,key=lambda f:(f['business_date'],f['factor_key']))

    def _review(self, frozen, receipt_id, build):
        if receipt_id is None: return None
        candidates=[x['decision'] for x in frozen['decisions'] if x['check']['receipt_id']==receipt_id and x['check']['check_role']=='review']
        if len(candidates)!=1: raise ValueError('review must be frozen in input snapshot')
        r=candidates[0]
        if r['scope_type']!='REVIEW' or r['decision']!='VERIFIED' or not self._trusted(r) or build['source_dirty']:
            raise ValueError('independent trusted review of clean code required')
        return r['claims_json']

    def execute(self, **arguments):
        try:
            return self._execute(**arguments)
        except Exception as original:
            # Record only an actual, validated local build and valid snapshot.
            # Do not turn configuration/identity failures into invented runs.
            build=arguments.get('build'); compute=arguments.get('compute')
            if build is not None and compute is not None and capture_build(arguments['source_root'],compute)==build:
                with self.database.connection() as c:
                    exists=c.execute('SELECT 1 FROM analysis_runs WHERE analysis_run_id=?',(arguments.get('analysis_run_id'),)).fetchone()
                if not exists:
                    try:
                        self.record_failure(analysis_run_id=arguments['analysis_run_id'],snapshot_id=arguments['snapshot_id'],
                            parameters=arguments['parameters'],build=build,error_code=type(original).__name__)
                    except Exception as audit_error:
                        raise ValueError('analysis failed; failure audit also failed: '+type(audit_error).__name__) from original
            raise

    def record_failure(self, *, analysis_run_id, snapshot_id, parameters, build, error_code):
        self.require(5); p=self.get_snapshot(snapshot_id)['snapshot']; text(error_code)
        canonical(parameters); canonical(build)
        row=dict(analysis_run_id=analysis_run_id,module='M3',analysis_date=p['analysis_date'],as_of=p['as_of'],generated_at=self._now(),
            code_sha=build['code_sha'],rules_version=CALCULATION_VERSION,contract_version=CONTRACT_VERSION,
            parameters_json=parameters,parameters_sha256=digest(parameters),environment_json=build,environment_sha256=digest(build),input_snapshot_id=snapshot_id,
            status='FAILED',quality_status='UNKNOWN',blocking_reasons_json=['ANALYSIS_FAILED:'+error_code],result_sha256=result_hash(snapshot_id,parameters,[],[],[]))
        with self.database.transaction() as c: insert(c,'analysis_runs',row)
        return analysis_run_id

    def _execute(self, *, analysis_run_id, snapshot_id, parameters, compute, source_root,
                build, review_receipt_id=None, dependencies=(), replay_of_run_id=None):
        """Call a file-backed adapter once, then atomically seal all results.

        The adapter receives frozen rows/decisions and versioned parameters;
        it must call the existing core. This API does not supply market data or
        certify an adapter. Invalid outputs fail atomically and remain errors.
        """
        self.require(5); text(analysis_run_id)
        if not isinstance(parameters,dict) or set(parameters)!={'schema_version','config_version','values'} or parameters['schema_version']!='m3-analysis-parameters-v1' or not isinstance(parameters['values'],dict):
            raise ValueError('versioned analysis parameters required')
        text(parameters['config_version']); canonical(parameters)
        if capture_build(source_root,compute)!=build: raise ValueError('actual build differs from declared build')
        frozen=self.get_snapshot(snapshot_id); p=frozen['snapshot']
        with self.database.connection() as c:
            if c.execute('SELECT 1 FROM analysis_runs WHERE analysis_run_id=?',(analysis_run_id,)).fetchone(): raise ValueError('run ID already used; read it explicitly')
        review=self._review(frozen,review_receipt_id,build)
        original_parameters=canonical(parameters)
        computation=compute(frozen,parameters)
        if canonical(parameters)!=original_parameters: raise ValueError('adapter mutated analysis parameters')
        # The adapter cannot mutate its arguments and silently change lineage.
        if self.get_snapshot(snapshot_id)!=frozen: raise ValueError('adapter mutated frozen inputs')
        if capture_build(source_root,compute)!=build: raise ValueError('build changed during computation')
        diagnostics=self._diagnostics(computation,frozen,analysis_run_id,build['code_sha'],review)
        factors=self._factors(computation,frozen,analysis_run_id)
        generated=self._now(); deps=[]
        for d in dependencies:
            if set(d)!={'role','upstream_run_id','gate_policy_version'}: raise ValueError('dependency fields invalid')
            upstream=self.get_run(d['upstream_run_id'])['run']
            if upstream['module']!='M3': raise ValueError('unsupported dependency module')
            deps.append(fields('analysis_dependencies',dict(d,analysis_run_id=analysis_run_id,upstream_result_sha256=upstream['result_sha256'],consumed_at=generated)))
        deps.sort(key=lambda d:(d['role'],d['upstream_run_id']))
        blocked=all(d['admission']=='BLOCKED' for d in diagnostics)
        reasons=list(p['blocking_reasons_json'])
        if build['source_dirty']: reasons.append('DIRTY_BUILD_NOT_FORMAL')
        if any(d['admission']!='L2' for d in diagnostics): reasons.append('NOT_ALL_MODULES_RESEARCH_ALLOWED')
        status='BLOCKED' if blocked or p['completeness']=='BLOCKED' else 'PARTIAL' if reasons else 'SUCCESS'
        quality='INVALID' if any(d['status']=='INVALID_DATA' for d in diagnostics) else 'UNKNOWN' if reasons else 'VALID'
        output_hash=result_hash(snapshot_id,parameters,diagnostics,factors,deps)
        row=dict(analysis_run_id=analysis_run_id,module='M3',analysis_date=p['analysis_date'],as_of=p['as_of'],generated_at=generated,code_sha=build['code_sha'],rules_version=CALCULATION_VERSION,contract_version=CONTRACT_VERSION,
            parameters_json=parameters,parameters_sha256=digest(parameters),environment_json=build,environment_sha256=digest(build),input_snapshot_id=snapshot_id,status=status,quality_status=quality,blocking_reasons_json=sorted(set(reasons)),result_sha256=output_hash,review_receipt_id=review_receipt_id,replay_of_run_id=replay_of_run_id)
        with self.database.transaction() as c:
            if replay_of_run_id:
                old=self._run(c,replay_of_run_id)['run']
                if old['input_snapshot_id']!=snapshot_id or old['parameters_json']!=parameters or old['environment_json']!=build or old['review_receipt_id']!=review_receipt_id: raise ValueError('replay input/config/build/review mismatch')
                if old['result_sha256']!=output_hash: raise ValueError('REPLAY_RESULT_MISMATCH')
            for d in diagnostics: insert(c,'m3_diagnostics',d)
            for f in factors: insert(c,'factor_values',f)
            for d in deps: insert(c,'analysis_dependencies',d)
            insert(c,'analysis_runs',row)
        return analysis_run_id

    def _run(self,c,run_id):
        r=one(c,'analysis_runs',analysis_run_id=run_id)
        ds=sorted(rows(c,'m3_diagnostics',analysis_run_id=run_id),key=lambda d:d['indicator'])
        fs=sorted(rows(c,'factor_values',analysis_run_id=run_id),key=lambda f:(f['business_date'],f['factor_key']))
        deps=sorted(rows(c,'analysis_dependencies',analysis_run_id=run_id),key=lambda d:(d['role'],d['upstream_run_id']))
        if digest(r['parameters_json'])!=r['parameters_sha256'] or digest(r['environment_json'])!=r['environment_sha256'] or result_hash(r['input_snapshot_id'],r['parameters_json'],ds,fs,deps)!=r['result_sha256']:
            raise ValueError('stored run hash mismatch')
        frozen=self._snapshot(c,r['input_snapshot_id'])
        return {'run':r,'diagnostics':ds,'factors':fs,'dependencies':deps,'snapshot':frozen}

    def get_run(self,analysis_run_id):
        self.require(5)
        with self.database.connection() as c:
            c.execute('BEGIN')
            return self._run(c,analysis_run_id)

    def find_runs(self, *, analysis_date, as_of, snapshot_id):
        """No implicit latest-run or source fallback selection."""
        self.require(5)
        with self.database.connection() as c:
            return sorted(rows(c,'analysis_runs',analysis_date=analysis_date,as_of=stamp(as_of),input_snapshot_id=snapshot_id),key=lambda r:(r['generated_at'],r['analysis_run_id']))

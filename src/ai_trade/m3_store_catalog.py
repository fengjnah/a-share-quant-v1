"""Source/evidence/version/decision repositories. No collectors or init calls."""
from dataclasses import asdict, dataclass
import hashlib
from pathlib import Path, PurePosixPath
import sqlite3
from functools import wraps

from ai_trade.storage.m3_schema import TYPED, TABLES
from ai_trade.storage.workbench import inspect_database
from ai_trade.m3_store_values import canonical, decoded, digest, fields, insert, one, rows, stamp, text, utc_now


@dataclass(frozen=True)
class Batch:
    attempt_id: str
    run_id: str
    source_id: str
    request_key: str
    request: dict
    started_at: str
    finished_at: str


@dataclass(frozen=True)
class Provenance:
    record_version: str
    event_time: str | None
    available_at: str | None
    observed_at: str | None
    ingested_at: str | None
    evidence_id: str | None
    quality_status: str = 'unknown'
    evidence_kind: str = 'source_observation'
    supersedes_id: str | None = None
    revision_reason: str | None = None


def audited_write(method):
    """Keep pre-transaction parse/validation failures as completed attempts."""
    @wraps(method)
    def call(self,*args,**kwargs):
        try: return method(self,*args,**kwargs)
        except Exception as original:
            batch=kwargs.get('batch')
            if isinstance(batch,Batch):
                with self.database.connection() as c:
                    exists=c.execute('SELECT 1 FROM ingestion_attempts WHERE attempt_id=?',(batch.attempt_id,)).fetchone()
                if not exists:
                    try: self.record_attempt(batch,outcome='FAILED',error_code=type(original).__name__)
                    except Exception as audit_error: raise ValueError('input rejected; failure audit also failed: '+type(audit_error).__name__) from original
            raise
    return call


class CatalogRepository:
    def __init__(self, database, evidence_root, *, trust_roots=None, clock=utc_now):
        self.database=database
        self.evidence_root=Path(evidence_root).absolute()
        self.trust_roots=trust_roots or {}
        self.clock=clock

    def _now(self): return stamp(self.clock())

    def require(self, minimum):
        state=inspect_database(self.database)
        if state['schema_version']<minimum: raise ValueError('SCHEMA_CAPABILITY_MISSING')
        return state

    def _put(self, table, row):
        self.require(3)
        value=fields(table,row)
        with self.database.transaction() as conn:
            keys={k:value[k] for k in TABLES[table].pk}
            existing=conn.execute(f'SELECT * FROM {table} WHERE '+' AND '.join(f'{k}=?' for k in keys),tuple(keys.values())).fetchone()
            if existing is not None:
                if decoded(table,existing)!=value: raise ValueError('same ID has different content')
                return value
            return insert(conn,table,value)

    def register_source(self, **row):
        if not isinstance(row.get('units_json'),dict): raise ValueError('typed units object required')
        if 'registered_at' not in row:
            self.require(3)
            with self.database.connection() as c:
                old=c.execute('SELECT registered_at FROM data_sources WHERE source_id=?',(row.get('source_id'),)).fetchone()
            if old: row['registered_at']=old[0]
        return self._put('data_sources',dict(row,registered_at=row.get('registered_at',self._now())))

    def register_instrument(self, **row):
        if 'registered_at' not in row:
            self.require(3)
            with self.database.connection() as c:
                old=c.execute('SELECT registered_at FROM instrument_catalog WHERE catalog_id=?',(row.get('catalog_id'),)).fetchone()
            if old: row['registered_at']=old[0]
        return self._put('instrument_catalog',dict(row,registered_at=row.get('registered_at',self._now())))

    def evidence_path(self, relative_uri):
        uri=text(relative_uri); p=PurePosixPath(uri)
        if p.is_absolute() or any(x in ('..','.') for x in uri.split('/')) or '\\' in uri or ':' in uri: raise ValueError('unsafe evidence path')
        root=self.evidence_root
        if root.resolve()!=root: raise ValueError('symlink evidence root')
        target=root.joinpath(*p.parts)
        if not target.resolve().is_relative_to(root.resolve()): raise ValueError('evidence path outside root')
        for q in (target,*target.parents):
            if q.is_symlink(): raise ValueError('symlink evidence path')
            if q==root: break
        return target

    def put_evidence(self, payload, *, evidence_kind, media_type='application/json', captured_at=None, evidence_id=None):
        if not isinstance(payload,bytes) or len(payload)>8_000_000: raise ValueError('bounded evidence bytes required')
        self.require(3)
        sha=hashlib.sha256(payload).hexdigest(); uri='sha256/'+sha
        path=self.evidence_path(uri); path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():
            if path.read_bytes()!=payload: raise ValueError('evidence hash conflict')
        else:
            with path.open('xb') as f: f.write(payload)
        with self.database.connection() as c:
            old=c.execute('SELECT * FROM evidence_objects WHERE sha256=? AND privacy_class=?',(sha,'private')).fetchone()
        if old is not None:
            old=decoded('evidence_objects',old)
            if evidence_id is not None and old['evidence_id']!=evidence_id: raise ValueError('evidence already registered with another identity')
            if old['evidence_kind']!=evidence_kind or old['media_type']!=media_type: raise ValueError('evidence type cannot be relabeled')
            return old['evidence_id']
        row=dict(evidence_id=evidence_id or 'evidence:'+sha,sha256=sha,relative_uri=uri,byte_size=len(payload),media_type=media_type,evidence_kind=evidence_kind,captured_at=captured_at,registered_at=self._now(),privacy_class='private')
        self._put('evidence_objects',row)
        return row['evidence_id']

    def evidence_bytes(self, evidence_id, conn=None):
        if conn is None:
            with self.database.connection() as c: return self.evidence_bytes(evidence_id,c)
        row=one(conn,'evidence_objects',evidence_id=evidence_id)
        path=self.evidence_path(row['relative_uri'])
        if not path.is_file() or path.stat().st_size!=row['byte_size'] or row['byte_size']>8_000_000: raise ValueError('evidence missing/oversized')
        data=path.read_bytes()
        if hashlib.sha256(data).hexdigest()!=row['sha256']: raise ValueError('evidence corrupted')
        return data

    def record_attempt(self, batch, *, outcome, error_code=None, returned_rows=None, committed_run_id=None, evidence_id=None, conn=None):
        if not isinstance(batch,Batch) or not isinstance(batch.request,dict) or batch.request.get('schema_version')!='m3-request-v1': raise ValueError('versioned Batch required')
        allowed={'schema_version','parameters'}
        if set(batch.request)!=allowed or not isinstance(batch.request['parameters'],dict): raise ValueError('request shape invalid')
        if set(batch.request['parameters'])-{'symbol','start_date','end_date','variety','trade_date','kind','source_version','operation'}: raise ValueError('unapproved request parameter')
        value=fields('ingestion_attempts',dict(attempt_id=batch.attempt_id,source_id=batch.source_id,request_key=batch.request_key,request_json=batch.request,started_at=batch.started_at,finished_at=batch.finished_at,outcome=outcome,error_code=error_code,returned_rows=returned_rows,committed_run_id=committed_run_id,evidence_id=evidence_id))
        if value['finished_at']>self._now(): raise ValueError('attempt completion cannot be in future')
        if conn is None: return self._put('ingestion_attempts',value)
        return insert(conn,'ingestion_attempts',value)

    def assess(self, **row):
        if not isinstance(row.get('reasons_json'),list) or not isinstance(row.get('metrics_json'),dict): raise ValueError('typed assessment required')
        now=self._now()
        if row.get('assessed_at') is not None and stamp(row['assessed_at'])!=now: raise ValueError('local assessments use actual assessment time; historical import unsupported')
        row['assessed_at']=now
        return self._put('quality_assessments',row)

    def _trusted(self, receipt):
        claims=receipt['claims_json']; authority=self.trust_roots.get(claims.get('issuer'))
        return (isinstance(authority,dict) and authority.get('authority_ref')==claims.get('authority_ref')
                and receipt['scope_type'] in authority.get('scope_types',())
                and claims.get('claim_type') in authority.get('claim_types',())
                and set(claims.get('allowed_uses',())).issubset(authority.get('allowed_uses',())))

    def receipt(self, **row):
        claims=row.get('claims_json')
        required={'schema_version','claim_type','issuer','authority_ref','allowed_uses','scope','valid_business_range'}
        review={'implementation_sha','rules_version','data_snapshot_id','independent_h_review_ref','approved_at','execution_constraints_ref','out_of_sample_validation_ref'}
        if not isinstance(claims,dict) or set(claims)!=(required|review if row.get('scope_type')=='REVIEW' else required) or claims['schema_version']!='m3-receipt-v1': raise ValueError('receipt claims schema mismatch')
        if not isinstance(claims['allowed_uses'],list) or set(claims['allowed_uses'])-{'research','storage','automation','display','redistribution'}: raise ValueError('unknown allowed use')
        span=claims['valid_business_range']
        if not isinstance(span,list) or len(span)!=2 or span[0]>span[1]: raise ValueError('receipt business range invalid')
        from datetime import date
        if any(not isinstance(d,str) or date.fromisoformat(d).isoformat()!=d for d in span): raise ValueError('receipt date invalid')
        if row['decision'] in ('VERIFIED','REVOKED') and not self._trusted(row): raise ValueError('untrusted receipt issuer/authority/scope')
        return self._put('verification_receipts',row)

    def decision_at(self, *, as_of, data_version_id=None, attempt_id=None, rules_version=None, source_id=None, claim_type=None):
        cutoff=stamp(as_of)
        with self.database.connection() as conn:
            if claim_type is None:
                items=rows(conn,'quality_assessments',**({"data_version_id":data_version_id} if data_version_id else {'attempt_id':attempt_id}))
                selected=[v for v in items if v['assessed_at']<=cutoff and v['rules_version']==rules_version]
                if not selected: return None
                if len([v for v in selected if v['supersedes_id'] is None])!=1: raise ValueError('ambiguous quality decision roots')
                return max(selected,key=lambda v:v['assessed_at'])
            items=rows(conn,'verification_receipts',**({'source_id':source_id} if source_id else {'data_version_id':data_version_id}))
            selected=[v for v in items if v['available_at']<=cutoff and v['claims_json']['claim_type']==claim_type]
            if not selected: return None
            # Distinct roots are ambiguous, not an opportunity to choose PASS.
            roots={v['receipt_id'] for v in selected if v['supersedes_id'] is None}
            if len(roots)!=1: raise ValueError('ambiguous receipt roots')
            latest=max(selected,key=lambda v:(v['available_at'],v['receipt_id']))
            if latest['expires_at'] is not None and latest['expires_at']<=cutoff: return None
            if latest['decision']=='VERIFIED' and not self._trusted(latest): raise ValueError('receipt trust root not configured')
            return latest

    @staticmethod
    def _identity(version):
        return digest({k:v for k,v in version.items() if k not in ('data_version_id','registered_at','attempt_id')})

    def _prepare(self, dataset, body, provenance, *, batch, business_key, children=()):
        table=TYPED[dataset]
        if table=='legacy_version_links': raise ValueError('use explicit legacy linker')
        body=fields(table,dict(body,data_version_id='0'*64))
        del body['data_version_id']
        normalized=[]
        for child_table,child in children:
            parent_key='universe_version_id' if child_table=='universe_members' else 'report_version_id'
            normalized.append((child_table,fields(child_table,dict(child,**{parent_key:'0'*64}))))
        normalized=sorted(normalized,key=canonical)
        unbound=self._unbound(normalized)
        version=dict(asdict(provenance),dataset_key=dataset,business_key=business_key,source_id=batch.source_id,registered_at=self._now(),attempt_id=batch.attempt_id,payload_sha256=digest({'record':body,'children':unbound}))
        version['data_version_id']='0'*64
        version=fields('data_versions',version)
        version['data_version_id']=self._identity(version)
        row=fields(table,dict(body,data_version_id=version['data_version_id']))
        bound=[]
        for child_table,child in normalized:
            key='universe_version_id' if child_table=='universe_members' else 'report_version_id'
            bound.append((child_table,dict(child,**{key:version['data_version_id']})))
        return version,row,bound

    def _write(self, prepared, batch, *, returned_rows=None, validate=None, finalize=None, failure_evidence_id=None):
        self.require(4)
        if not prepared: raise ValueError('empty input batch')
        try:
            with self.database.transaction() as conn:
                for version,_,_ in prepared:
                    source=one(conn,'data_sources',source_id=batch.source_id)
                    if source['dataset_key']!=version['dataset_key']: raise ValueError('batch source dataset mismatch')
                    if version['evidence_id']: self.evidence_bytes(version['evidence_id'],conn)
                    if version['ingested_at'] and version['ingested_at']>stamp(batch.finished_at): raise ValueError('ingestion after batch completion')
                ids=[p[0]['data_version_id'] for p in prepared]
                if len(set(ids))!=len(ids): raise ValueError('duplicate version in batch')
                existing=[conn.execute('SELECT * FROM data_versions WHERE data_version_id=?',(v,)).fetchone() for v in ids]
                if any(existing):
                    if not all(existing): raise ValueError('partially duplicated batch')
                    for old,(version,_,_) in zip(existing,prepared):
                        if self._identity(decoded('data_versions',old))!=self._identity(version): raise ValueError('duplicate content conflict')
                    attempt=conn.execute('SELECT * FROM ingestion_attempts WHERE attempt_id=?',(batch.attempt_id,)).fetchone()
                    if attempt is None: self.record_attempt(batch,outcome='DUPLICATE',returned_rows=returned_rows,conn=conn)
                    else:
                        old=decoded('ingestion_attempts',attempt)
                        if old['source_id']!=batch.source_id or old['request_json']!=batch.request or old['committed_run_id']!=batch.run_id: raise ValueError('attempt retry mismatch')
                    return ids
                if validate: validate(conn,prepared)
                conn.execute('INSERT INTO ingestion_runs VALUES (?,?)',(text(batch.run_id),self._now()))
                self.record_attempt(batch,outcome='SUCCESS',returned_rows=returned_rows,committed_run_id=batch.run_id,conn=conn)
                for version,row,children in prepared:
                    for child_table,child in children: insert(conn,child_table,child)
                    insert(conn,TYPED[version['dataset_key']],row)
                    insert(conn,'data_versions',version)
                if finalize: finalize(conn,ids)
                return ids
        except (ValueError,sqlite3.Error) as exc:
            # Preserve a failed attempt after the failed data transaction. Never
            # invent a successful ingestion_run or replace a prior attempt.
            try:
                with self.database.connection() as c:
                    exists=c.execute('SELECT 1 FROM ingestion_attempts WHERE attempt_id=?',(batch.attempt_id,)).fetchone()
                if not exists: self.record_attempt(batch,outcome='FAILED',error_code=type(exc).__name__,returned_rows=returned_rows,evidence_id=failure_evidence_id)
            except (ValueError,sqlite3.Error) as audit_error:
                raise ValueError(f'data write rejected; failure audit also failed: {type(audit_error).__name__}') from exc
            raise

    def _version(self, conn, version_id):
        v=one(conn,'data_versions',data_version_id=version_id)
        if self._identity(v)!=version_id: raise ValueError('version envelope hash mismatch')
        table=TYPED[v['dataset_key']]; row=one(conn,table,data_version_id=version_id)
        if table=='legacy_version_links':
            column={'daily_bar':'daily_bar_version_id','security':'security_version_id','calendar':'calendar_version_id'}[v['dataset_key']]
            old=self._legacy(conn,v['dataset_key'],row[column])
            if digest(old)!=v['payload_sha256']: raise ValueError('legacy payload changed')
            return v,old,[]
        body={k:val for k,val in row.items() if k!='data_version_id'}
        children=[]
        if table in ('universe_versions','cffex_report_versions'):
            child,key=('universe_members','universe_version_id') if table=='universe_versions' else ('cffex_rank_rows','report_version_id')
            children=[(child,x) for x in sorted(rows(conn,child,**{key:version_id}),key=canonical)]
        if table!='legacy_version_links' and digest({'record':body,'children':self._unbound(children)})!=v['payload_sha256']: raise ValueError('typed payload hash mismatch')
        return v,row,children

    @staticmethod
    def _unbound(children):
        return [(t,{k:v for k,v in r.items() if k not in ('universe_version_id','report_version_id')}) for t,r in children]

    def get_version(self, version_id):
        self.require(3)
        with self.database.connection() as conn: return self._version(conn,version_id)

    def select_visible(self, *, dataset, business_key, source_id, as_of, mode):
        if mode not in ('research','strict_backtest','paper_trade'): raise ValueError('explicit mode required')
        cutoff=stamp(as_of)
        with self.database.connection() as conn:
            candidates=rows(conn,'data_versions',dataset_key=dataset,business_key=canonical(business_key),source_id=source_id)
            visible=[v for v in candidates if all(v[k] is not None and v[k]<=cutoff for k in ('event_time','available_at','ingested_at'))]
            if not visible: raise ValueError('no visible version')
            chosen=max(visible,key=lambda v:(max(v['available_at'],v['ingested_at']),v['data_version_id']))
            if mode!='research' and (chosen['quality_status']!='accepted' or chosen['observed_at'] is None or chosen['observed_at']>cutoff): raise ValueError('latest version not eligible; no fallback')
            return self._version(conn,chosen['data_version_id'])

    @staticmethod
    def _legacy(conn,dataset,version_id):
        if dataset=='daily_bar':
            result=conn.execute('SELECT v.*,b.instrument_id,b.trade_date,b.adjustment_method,i.symbol FROM daily_bar_versions v JOIN daily_bars b ON b.bar_id=v.bar_id JOIN instruments i ON i.instrument_id=b.instrument_id WHERE v.version_id=?',(version_id,)).fetchone()
        elif dataset in ('security','calendar'):
            result=conn.execute(f'SELECT * FROM {"security_versions" if dataset=="security" else "calendar_versions"} WHERE version_id=?',(version_id,)).fetchone()
        else: raise ValueError('unknown legacy dataset')
        if result is None: raise ValueError('legacy version missing')
        # Local rowids are handles, not global content identities.
        return {k:v for k,v in dict(result).items() if k not in ('version_id','bar_id')}

    def link_legacy(self, dataset, version_id, *, revision_reason=None, evidence_id=None):
        """Explicit same-store indexing only. No scan/import or old-row updates."""
        self.require(3)
        with self.database.transaction() as conn:
            old=self._legacy(conn,dataset,version_id)
            if dataset=='daily_bar': key={k:old[k] for k in ('instrument_id','trade_date','adjustment_method')}
            elif dataset=='security': key={'instrument_id':old['instrument_id']}
            else: key={k:old[k] for k in ('exchange','session_date')}
            record_version=old['source_version'] if dataset=='daily_bar' else old['record_version']
            source=one(conn,'data_sources',source_id=old['source'])
            if source['dataset_key']!=dataset: raise ValueError('legacy source binding mismatch')
            previous=old.get('supersedes_version')
            parent=None
            if previous:
                parent_row=conn.execute('SELECT data_version_id FROM data_versions WHERE dataset_key=? AND business_key=? AND source_id=? AND record_version=?',(dataset,canonical(key),old['source'],previous)).fetchone()
                if parent_row is None: raise ValueError('index predecessor before revision')
                parent=parent_row[0]
                if not old.get('revision_reason') and not (revision_reason and evidence_id): raise ValueError('legacy revision reason unknown; explicit evidence required')
            if evidence_id: self.evidence_bytes(evidence_id,conn)
            version=fields('data_versions',dict(data_version_id='0'*64,dataset_key=dataset,business_key=key,source_id=old['source'],record_version=record_version,event_time=old['event_time'],available_at=old['available_at'],observed_at=old.get('observed_at'),ingested_at=old['ingested_at'],registered_at=self._now(),payload_sha256=digest(old),quality_status=old['quality_status'] if old['quality_status'] in ('accepted','quarantined') else 'unknown',evidence_kind='legacy_unknown',evidence_id=evidence_id,supersedes_id=parent,revision_reason=(old.get('revision_reason') or revision_reason) if parent else None))
            version['data_version_id']=self._identity(version)
            existing=conn.execute('SELECT 1 FROM data_versions WHERE data_version_id=?',(version['data_version_id'],)).fetchone()
            if existing:
                self._version(conn,version['data_version_id'])
                return version['data_version_id']
            column={'daily_bar':'daily_bar_version_id','security':'security_version_id','calendar':'calendar_version_id'}[dataset]
            insert(conn,'legacy_version_links',dict(data_version_id=version['data_version_id'],**{column:version_id}))
            insert(conn,'data_versions',version)
            return version['data_version_id']

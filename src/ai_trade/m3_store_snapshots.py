"""Sealed, exact-version input manifests and frozen quality/receipt decisions."""
from ai_trade.m3_store_market import MarketInputRepository
from ai_trade.m3_store_values import canonical, digest, insert, one, rows, stamp, text


ROLES = {'price_row':{'index_bar','daily_bar'}, 'calendar_row':{'calendar','market_session'},
         'universe':{'universe'},'breadth':{'market_breadth'},'amount':{'market_amount'},
         'status':{'security_state'},'security':{'security'},'cffex_report':{'cffex_report'}}
CHECK_ROLES={'quality','source_verification','research_authorization','time_verification',
             'universe_verification','scope_verification','publication_verification','review'}


def snapshot_hash(parent,items,checks):
    stable={k:v for k,v in parent.items() if k not in ('snapshot_id','manifest_sha256','created_at')}
    unbound=lambda xs:[{k:v for k,v in x.items() if k!='snapshot_id'} for x in xs]
    return digest({'snapshot':stable,'items':unbound(items),'checks':unbound(checks)})


class SnapshotRepository(MarketInputRepository):
    def _check_record(self,c,check,cutoff,versions,scope):
        if check['check_role'] not in CHECK_ROLES: raise ValueError('unknown snapshot check role')
        if check.get('assessment_id'):
            if check['check_role']!='quality' or check.get('receipt_id'): raise ValueError('check target/role mismatch')
            d=one(c,'quality_assessments',assessment_id=check['assessment_id'])
            if d['data_version_id'] not in {v['data_version_id'] for v in versions} or d['assessed_at']>cutoff: raise ValueError('quality decision target/time mismatch')
            current=self.decision_at(as_of=cutoff,data_version_id=d['data_version_id'],rules_version=d['rules_version'])
            if current is None or current['assessment_id']!=d['assessment_id']: raise ValueError('latest visible quality decision required')
            return d,([] if d['decision']=='PASS' else ['QUALITY_'+d['decision']])
        if not check.get('receipt_id') or check['check_role']=='quality': raise ValueError('one check target required')
        d=one(c,'verification_receipts',receipt_id=check['receipt_id']); claims=d['claims_json']
        if claims['claim_type']!=check['check_role'] or d['available_at']>cutoff: raise ValueError('receipt claim/time mismatch')
        if d['data_version_id'] is not None and d['data_version_id'] not in {v['data_version_id'] for v in versions}: raise ValueError('receipt outside input versions')
        if d['source_id'] is not None and d['source_id'] not in {v['source_id'] for v in versions}: raise ValueError('receipt outside input sources')
        if claims['scope'] not in {scope['market'],*scope['symbols']}: raise ValueError('receipt scope mismatch')
        if d['scope_type']!='REVIEW':
            selected=self.decision_at(as_of=cutoff,data_version_id=d['data_version_id'],source_id=d['source_id'],claim_type=claims['claim_type'])
            if selected is None or selected['receipt_id']!=d['receipt_id']: raise ValueError('expired/superseded receipt')
        self.evidence_bytes(d['evidence_id'],c)
        warnings=[]
        if d['decision']!='VERIFIED' or not self._trusted(d): warnings.append('RECEIPT_'+d['decision'])
        return d,warnings

    def seal_snapshot(self, *, analysis_date, as_of, mode, scope, items, checks=(), selection_policy_version='m3-explicit-inputs-v1', blocking_reasons=()):
        self.require(5); cutoff=stamp(as_of)
        if selection_policy_version!='m3-explicit-inputs-v1': raise ValueError('unknown selection policy')
        if set(scope)!={'schema_version','market','symbols','required_roles','source_bindings'} or scope['schema_version']!='m3-scope-v1': raise ValueError('scope schema mismatch')
        if not isinstance(scope['symbols'],list) or not isinstance(scope['source_bindings'],dict) or not isinstance(scope['required_roles'],list) or set(scope['required_roles'])-set(ROLES): raise ValueError('scope fields invalid')
        if set(scope['source_bindings'])-set(ROLES): raise ValueError('unknown source binding role')
        text(scope['market'])
        for symbol in scope['symbols']: text(symbol)
        if len(set(scope['symbols']))!=len(scope['symbols']) or len(set(scope['required_roles']))!=len(scope['required_roles']): raise ValueError('duplicate scope symbol/role')
        for sources in scope['source_bindings'].values():
            if not isinstance(sources,list) or not sources or len(set(sources))!=len(sources): raise ValueError('explicit unique source lists required')
            for source in sources: text(source)
        if cutoff>self._now(): raise ValueError('future analysis knowledge cutoff')
        reasons=list(blocking_reasons); bound_items=[]; bound_checks=[]; versions=[]; indexes={}
        with self.database.transaction() as c:
            for item in items:
                if set(item)!={'role','data_version_id','required'} or item['role'] not in ROLES: raise ValueError('input item schema mismatch')
                role=item['role']; v,r,_=self._version(c,item['data_version_id'])
                if v['dataset_key'] not in ROLES[role]: raise ValueError('input role/dataset mismatch')
                if v['source_id'] not in scope['source_bindings'].get(role,[]): raise ValueError('explicit source binding required')
                for field in ('event_time','available_at','observed_at','ingested_at'):
                    if v[field] is None: reasons.append('UNKNOWN_TIME:'+field)
                    elif v[field]>cutoff: raise ValueError('future input is not an analysis input')
                if v['quality_status']!='accepted': reasons.append('QUALITY_'+v['quality_status'])
                if v['evidence_kind']=='synthetic': reasons.append('SYNTHETIC_INPUT')
                day=r.get('trade_date')
                if day and day>analysis_date: raise ValueError('future business date')
                if role=='status' and (r['effective_from']>analysis_date or (r['effective_to'] is not None and r['effective_to']<=analysis_date)): raise ValueError('state not active on analysis date')
                if role=='security' and (r['listing_date']>analysis_date or (r['delisting_date'] is not None and r['delisting_date']<=analysis_date)): raise ValueError('identity not active on analysis date')
                if v['available_at'] is not None and v['ingested_at'] is not None:
                    latest=self.select_visible(dataset=v['dataset_key'],business_key=v['business_key'],source_id=v['source_id'],as_of=cutoff,mode='research')[0]
                    if latest['data_version_id']!=v['data_version_id']: raise ValueError('older version cannot hide latest visible revision')
                if v['evidence_id']: self.evidence_bytes(v['evidence_id'],c)
                n=indexes.get(role,0); indexes[role]=n+1
                bound_items.append(dict(role=role,ordinal=n,data_version_id=v['data_version_id'],expected_sha256=v['payload_sha256'],required=item['required']))
                versions.append(v)
            for role in scope['required_roles']:
                if role not in indexes: reasons.append('MISSING_ROLE:'+role)
            counts={}
            for check in checks:
                if set(check)-{'check_role','assessment_id','receipt_id'}: raise ValueError('check fields mismatch')
                d,warnings=self._check_record(c,check,cutoff,versions,scope); reasons.extend(warnings)
                if d.get('claims_json') and not d['claims_json']['valid_business_range'][0]<=analysis_date<=d['claims_json']['valid_business_range'][1]: raise ValueError('receipt outside analysis business date')
                role=check['check_role']; n=counts.get(role,0); counts[role]=n+1
                bound_checks.append(dict(check_role=role,ordinal=n,assessment_id=check.get('assessment_id'),receipt_id=check.get('receipt_id'),expected_sha256=digest(d)))
            assessed={one(c,'quality_assessments',assessment_id=x['assessment_id'])['data_version_id'] for x in bound_checks if x['assessment_id']}
            if any(v['data_version_id'] not in assessed for v in versions): reasons.append('QUALITY_DECISION_MISSING')
            version_ids={v['data_version_id'] for v in versions}
            for v in versions:
                if v['dataset_key']=='cffex_report':
                    import json
                    lineage=one(c,'quality_assessments',assessment_id='cffex-lineage:'+v['data_version_id'])
                    manifest=json.loads(self.evidence_bytes(lineage['metrics_json']['lineage_evidence_id'],c))
                    if not set(manifest['calendar_versions']).issubset(version_ids): raise ValueError('CFFEX calendar versions must be frozen as snapshot inputs')
                    if lineage['assessment_id'] not in {x['assessment_id'] for x in bound_checks}: raise ValueError('CFFEX lineage assessment must be frozen')
            for role in ('source_verification','research_authorization','time_verification'):
                targeted={one(c,'verification_receipts',receipt_id=x['receipt_id'])['source_id'] for x in bound_checks if x['receipt_id'] and x['check_role']==role}
                if any(v['source_id'] not in targeted for v in versions): reasons.append('MISSING_CHECK:'+role)
            reasons=sorted(set(reasons))
            complete='BLOCKED' if not bound_items or mode!='research' and reasons else 'PARTIAL' if reasons else 'COMPLETE'
            bound_items.sort(key=lambda x:(x['role'],x['ordinal'])); bound_checks.sort(key=lambda x:(x['check_role'],x['ordinal']))
            parent=dict(analysis_date=analysis_date,as_of=cutoff,mode=mode,scope_json=scope,selection_policy_version=selection_policy_version,item_count=len(bound_items),check_count=len(bound_checks),checks_sha256=digest(bound_checks),completeness=complete,blocking_reasons_json=reasons,created_at=self._now())
            sid=snapshot_hash(parent,bound_items,bound_checks); parent.update(snapshot_id=sid,manifest_sha256=sid)
            existing=c.execute('SELECT 1 FROM input_snapshots WHERE snapshot_id=?',(sid,)).fetchone()
            if existing:
                self._snapshot(c,sid)
                return sid
            for item in bound_items: insert(c,'input_snapshot_items',dict(item,snapshot_id=sid))
            for check in bound_checks: insert(c,'input_snapshot_checks',dict(check,snapshot_id=sid))
            insert(c,'input_snapshots',parent)
            return sid

    def _snapshot(self,c,sid):
        p=one(c,'input_snapshots',snapshot_id=sid)
        items=sorted(rows(c,'input_snapshot_items',snapshot_id=sid),key=lambda x:(x['role'],x['ordinal']))
        checks=sorted(rows(c,'input_snapshot_checks',snapshot_id=sid),key=lambda x:(x['check_role'],x['ordinal']))
        unbound_checks=[{k:v for k,v in x.items() if k!='snapshot_id'} for x in checks]
        if len(items)!=p['item_count'] or len(checks)!=p['check_count'] or digest(unbound_checks)!=p['checks_sha256'] or snapshot_hash(p,items,checks)!=sid: raise ValueError('snapshot manifest corrupted')
        data=[]; decisions=[]
        for item in items:
            v,r,child=self._version(c,item['data_version_id'])
            if item['expected_sha256']!=v['payload_sha256']: raise ValueError('input hash mismatch')
            if v['evidence_id']: self.evidence_bytes(v['evidence_id'],c)
            data.append({'item':item,'version':v,'record':r,'children':child})
        for check in checks:
            d=one(c,'quality_assessments',assessment_id=check['assessment_id']) if check['assessment_id'] else one(c,'verification_receipts',receipt_id=check['receipt_id'])
            if digest(d)!=check['expected_sha256']: raise ValueError('frozen decision changed')
            if d.get('evidence_id'): self.evidence_bytes(d['evidence_id'],c)
            decisions.append({'check':check,'decision':d})
        return {'snapshot':p,'items':items,'checks':checks,'inputs':data,'decisions':decisions}

    def get_snapshot(self,snapshot_id):
        self.require(5)
        with self.database.connection() as c:
            c.execute('BEGIN')
            return self._snapshot(c,snapshot_id)

"""Typed M3 inputs and explicit, fail-closed market/reported-ranking writes."""
from dataclasses import asdict
from datetime import datetime
import json
import math
from zoneinfo import ZoneInfo

from ai_trade.m3_store_catalog import CatalogRepository, audited_write
from ai_trade.m3_store_values import canonical, digest, insert, one, rows, stamp


class MarketInputRepository(CatalogRepository):
    @audited_write
    def save_index(self, records, provenance, *, batch):
        records=list(records); provenance=list(provenance)
        if len(records)!=len(provenance): raise ValueError('one provenance per index row required')
        prepared=[self._prepare('index_bar',r,p,batch=batch,business_key={k:r[k] for k in ('catalog_id','trade_date','adjustment_definition')}) for r,p in zip(records,provenance)]
        def validate(c,values):
            source=one(c,'data_sources',source_id=batch.source_id)
            if source['units_json'].get('price')!='index_point': raise ValueError('explicit index-point unit required')
            for _,r,_ in values:
                if one(c,'instrument_catalog',catalog_id=r['catalog_id'])['entity_kind']!='INDEX': raise ValueError('not an index')
        return self._write(prepared,batch,returned_rows=len(records),validate=validate)

    @audited_write
    def save_session(self, record, provenance, *, batch):
        p=self._prepare('market_session',record,provenance,batch=batch,business_key={k:record[k] for k in ('market_key','session_date')})
        r=p[1]
        if r['is_trading_day']==1:
            for k in ('opens_at','closes_at'):
                if datetime.fromisoformat(r[k]).astimezone(ZoneInfo('Asia/Shanghai')).date().isoformat()!=r['session_date']: raise ValueError('CFFEX session timestamp/date mismatch')
        return self._write([p],batch,returned_rows=1)[0]

    @audited_write
    def save_states(self, records, provenance, *, batch):
        records=list(records); provenance=list(provenance)
        if len(records)!=len(provenance): raise ValueError('one provenance per state required')
        prepared=[self._prepare('security_state',r,p,batch=batch,business_key={k:r[k] for k in ('instrument_id','effective_from')}) for r,p in zip(records,provenance)]
        def validate(c,values):
            # Validate the prospective visible frontier, including corrections
            # in this batch, rather than comparing to superseded intervals.
            cutoff=max((v['ingested_at'] or v['registered_at']) for v,_,_ in values)
            candidates={}
            for v in rows(c,'data_versions',dataset_key='security_state',source_id=batch.source_id):
                if all(v[k] is not None and v[k]<=cutoff for k in ('available_at','ingested_at')):
                    k=canonical(v['business_key'])
                    if k not in candidates or max(v['available_at'],v['ingested_at'])>candidates[k][0]: candidates[k]=(max(v['available_at'],v['ingested_at']),one(c,'security_state_versions',data_version_id=v['data_version_id']))
            for v,r,_ in values: candidates[canonical(v['business_key'])]=(max(v['available_at'] or '',v['ingested_at'] or ''),r)
            by_entity={}
            for _,r in candidates.values(): by_entity.setdefault(r['instrument_id'],[]).append(r)
            for group in by_entity.values():
                ordered=sorted(group,key=lambda r:r['effective_from'])
                if any(a['effective_to'] is None or a['effective_to']>b['effective_from'] for a,b in zip(ordered,ordered[1:])): raise ValueError('overlapping visible state intervals')
        return self._write(prepared,batch,returned_rows=len(records),validate=validate)

    @staticmethod
    def _visible(v,cutoff):
        if any(v[k] is None or v[k]>cutoff for k in ('event_time','available_at','observed_at','ingested_at')): raise ValueError('input version time UNKNOWN/future')
        if v['quality_status']!='accepted': raise ValueError('input structural quality not accepted')

    @audited_write
    def save_universe(self, record, members, provenance, *, batch):
        members=sorted(list(members),key=canonical)
        row=dict(record,member_count=len(members),members_sha256=digest(members))
        children=[('universe_members',m) for m in members]
        p=self._prepare('universe',row,provenance,batch=batch,business_key={k:row[k] for k in ('universe_key','trade_date','definition_version')},children=children)
        def validate(c,values):
            v,r,child=values[0]; cutoff=max(v['available_at'] or '',v['ingested_at'] or '')
            for _,m in child:
                if m['membership_status']!='ELIGIBLE': continue
                old=c.execute('SELECT * FROM security_versions WHERE version_id=?',(m['security_version_id'],)).fetchone()
                if old is None or old['instrument_id']!=m['instrument_id'] or not old['listing_date']<=r['trade_date'] or (old['delisting_date'] is not None and r['trade_date']>=old['delisting_date']): raise ValueError('historical identity/lifetime mismatch')
                if any(old[k]>cutoff for k in ('event_time','available_at','observed_at','ingested_at')): raise ValueError('future historical identity')
                sv,s,_=self._version(c,m['state_version_id']); self._visible(sv,cutoff)
                if sv['dataset_key']!='security_state' or s['instrument_id']!=m['instrument_id'] or not s['effective_from']<=r['trade_date'] or (s['effective_to'] is not None and r['trade_date']>=s['effective_to']): raise ValueError('historical state/date mismatch')
                if any(s[k] is None for k in ('st_status','suspended','delisting_organization')): raise ValueError('unknown historical membership state')
        return self._write([p],batch,returned_rows=len(members),validate=validate)[0]

    def _market_gate(self,c,row,provenance,batch,receipts,assessment_id):
        cutoff=max(stamp(provenance.available_at),stamp(provenance.ingested_at))
        uv,u,children=self._version(c,row['universe_version_id']); self._visible(uv,cutoff)
        if uv['dataset_key']!='universe' or u['universe_key']!=row['market_key'] or u['trade_date']!=row['trade_date'] or not u['eligible_count'] or u['eligible_count']!=sum(m['membership_status']=='ELIGIBLE' for _,m in children): raise ValueError('known same-date market universe required')
        if any(m['membership_status']=='UNKNOWN' for _,m in children): raise ValueError('universe membership incomplete')
        a=one(c,'quality_assessments',assessment_id=assessment_id)
        if a['data_version_id']!=uv['data_version_id'] or a['decision']!='PASS' or a['assessed_at']>cutoff: raise ValueError('universe quality assessment required')
        latest=self.decision_at(as_of=cutoff,data_version_id=uv['data_version_id'],rules_version=a['rules_version'])
        if latest is None or latest['assessment_id']!=assessment_id: raise ValueError('stale quality decision')
        required={'source_verification','research_authorization','time_verification','universe_verification'}
        if set(receipts)!=required: raise ValueError('independent market receipts required')
        for claim,rid in receipts.items():
            r=one(c,'verification_receipts',receipt_id=rid); claims=r['claims_json']
            expected_data=uv['data_version_id'] if claim=='universe_verification' else None
            if r['decision']!='VERIFIED' or not self._trusted(r) or r['available_at']>cutoff or (r['expires_at'] and r['expires_at']<=cutoff) or claims['claim_type']!=claim or claims['scope']!=row['market_key'] or not claims['valid_business_range'][0]<=row['trade_date']<=claims['valid_business_range'][1]: raise ValueError('market receipt unverified/outside scope/time')
            if expected_data:
                if r['data_version_id']!=expected_data: raise ValueError('universe receipt target mismatch')
                selected=self.decision_at(as_of=cutoff,data_version_id=expected_data,claim_type=claim)
            else:
                if r['source_id']!=batch.source_id: raise ValueError('source receipt mismatch')
                selected=self.decision_at(as_of=cutoff,source_id=batch.source_id,claim_type=claim)
            if not selected or selected['receipt_id']!=rid: raise ValueError('revoked or superseded receipt')
            if not {'research','storage'}.issubset(claims['allowed_uses']): raise ValueError('storage/research authorization absent')
        if provenance.quality_status!='accepted' or any(x is None for x in (provenance.event_time,provenance.available_at,provenance.observed_at,provenance.ingested_at)): raise ValueError('complete aggregate time/quality required')
        return u,children,cutoff

    @audited_write
    def save_breadth(self, record, provenance, *, batch, receipts, universe_assessment_id):
        p=self._prepare('market_breadth',record,provenance,batch=batch,business_key={k:record[k] for k in ('market_key','trade_date','definition_version')})
        def validate(c,values):
            _,r,_=values[0]; u,_,_=self._market_gate(c,r,provenance,batch,receipts,universe_assessment_id)
            names=('advances','declines','flat','limit_up','limit_down','suspended','unavailable','missing','eligible_count')
            if any(r[k] is None for k in names) or r['eligible_count']!=u['eligible_count'] or sum(r[k] for k in ('advances','declines','flat','suspended','unavailable','missing'))!=u['eligible_count'] or r['unavailable']!=0 or r['missing']!=0: raise ValueError('complete all-A partition required')
        return self._write([p],batch,returned_rows=1,validate=validate)[0]

    @audited_write
    def save_amount(self, record, provenance, *, batch, receipts, universe_assessment_id):
        p=self._prepare('market_amount',record,provenance,batch=batch,business_key={k:record[k] for k in ('market_key','trade_date','definition_version')})
        def validate(c,values):
            _,r,_=values[0]; u,members,cutoff=self._market_gate(c,r,provenance,batch,receipts,universe_assessment_id)
            if one(c,'data_sources',source_id=batch.source_id)['units_json'].get('amount')!='CNY': raise ValueError('CNY amount unit required')
            if r['market_amount_cny'] is None or r['contributing_count']!=u['eligible_count']: raise ValueError('complete amount coverage required')
            if provenance.evidence_id is None: raise ValueError('contribution manifest required')
            manifest=json.loads(self.evidence_bytes(provenance.evidence_id,c))
            if manifest.get('schema_version')=='m3-published-amount-v1':
                required={'schema_version','source_id','source_version','market_key','trade_date','amount_cny','amount_unit','contributing_count','universe_version_id','raw_evidence_id'}
                if set(manifest)!=required: raise ValueError('published amount manifest schema mismatch')
                expected=dict(source_id=batch.source_id,source_version=provenance.record_version,market_key=r['market_key'],trade_date=r['trade_date'],amount_cny=r['market_amount_cny'],amount_unit='CNY',contributing_count=r['contributing_count'],universe_version_id=r['universe_version_id'])
                if any(manifest[k]!=v for k,v in expected.items()): raise ValueError('published amount scope/value mismatch')
                raw=one(c,'evidence_objects',evidence_id=manifest['raw_evidence_id'])
                if raw['evidence_kind'] not in ('source_payload','sdk_frame','synthetic'): raise ValueError('source fact evidence required')
                # This is a native published total, explicitly distinct from a
                # local sum. Its reviewed mapping is frozen with the raw source.
                self.evidence_bytes(raw['evidence_id'],c)
                return
            if set(manifest)!={'schema_version','contributions'} or manifest['schema_version']!='m3-amount-inputs-v1': raise ValueError('amount manifest schema mismatch')
            expected={m['instrument_id'] for _,m in members if m['membership_status']=='ELIGIBLE'}; seen=set(); amounts=[]
            for item in manifest['contributions']:
                if set(item)!={'data_version_id','expected_sha256'}: raise ValueError('invalid contribution reference')
                v,b,_=self._version(c,item['data_version_id']); self._visible(v,cutoff)
                if v['payload_sha256']!=item['expected_sha256'] or v['dataset_key']!='daily_bar' or b['trade_date']!=r['trade_date'] or b['adjustment_method']!='none' or b['instrument_id'] not in expected or b['instrument_id'] in seen: raise ValueError('duplicate/wrong entity/date/price basis contribution')
                source=one(c,'data_sources',source_id=v['source_id'])
                if source['units_json'].get('amount')!='CNY': raise ValueError('contribution unit mismatch')
                seen.add(b['instrument_id']); amounts.append(b['amount'])
            total=math.fsum(amounts)
            if seen!=expected or len(seen)!=r['contributing_count'] or abs(total-r['market_amount_cny'])>2*math.ulp(total): raise ValueError('amount provenance/total mismatch')
        return self._write([p],batch,returned_rows=1,validate=validate)[0]

    def save_cffex(self, payload, record, provenance, *, batch, calendar_version_ids, scope_evidence_id=None):
        """Only the approved complete named subset. Other files remain evidence."""
        from ai_trade.m3_store_catalog import Batch
        evidence=None
        try:
            with self.database.connection() as c:
                previous=c.execute('SELECT outcome FROM ingestion_attempts WHERE attempt_id=?',(batch.attempt_id,)).fetchone()
            if previous is not None and previous[0] in ('FAILED','BLOCKED'):
                raise ValueError('attempt already finalized; retry with a new attempt ID')
            evidence=self.put_evidence(payload,evidence_kind='synthetic' if provenance.evidence_kind=='synthetic' else 'source_payload',media_type='text/csv',captured_at=provenance.observed_at)
            return self._save_cffex(payload,record,provenance,batch=batch,calendar_version_ids=calendar_version_ids,scope_evidence_id=scope_evidence_id,evidence=evidence)
        except Exception as original:
            if isinstance(batch,Batch):
                try:
                    with self.database.connection() as c:
                        exists=c.execute('SELECT 1 FROM ingestion_attempts WHERE attempt_id=?',(batch.attempt_id,)).fetchone()
                    if not exists:
                        self.record_attempt(batch,outcome='FAILED',error_code=type(original).__name__,evidence_id=evidence)
                except Exception as audit_error:
                    raise ValueError('input rejected; failure audit also failed: '+type(audit_error).__name__) from original
            raise

    def _save_cffex(self, payload, record, provenance, *, batch, calendar_version_ids, scope_evidence_id, evidence):
        """Validate only after the exact response is archived for failure audit."""
        from ai_trade.market_data.cffex_rankings import parse, build_record
        from ai_trade.market_data.cffex_rankings_models import CffexRankingsRequest
        request=CffexRankingsRequest(record.exchange,record.variety,record.trade_date)
        fmt,parsed=parse(payload,request)
        if fmt!='named' or any(not r.member for r in parsed):
            self.record_attempt(batch,outcome='BLOCKED',error_code='UNREPRESENTABLE_RANK_ROWS',returned_rows=len(parsed),evidence_id=evidence)
            return None
        if tuple(parsed)!=record.rows or record.source!=batch.source_id or record.source_version!=provenance.record_version: raise ValueError('report source/version/rows mismatch')
        if record.run_id!=batch.run_id or evidence!=provenance.evidence_id: raise ValueError('report batch/evidence mismatch')
        calendar=self.ranking_calendar(calendar_version_ids)
        rebuilt=build_record(request,payload,run_id=record.run_id,observed_at=record.observed_at,ingested_at=record.ingested_at,publication_time=record.publication_time,calendar=calendar,evidence_kind=record.evidence_kind,supersedes_version=record.supersedes_version,revision_reason=record.revision_reason)
        if rebuilt!=record: raise ValueError('report cannot be reconstructed from frozen calendar/raw bytes')
        with self.database.connection() as c:
            sessions=[(v,self._version(c,v)[1]) for v in calendar_version_ids]
        eligible=[v for v,s in sessions if s['session_date']==record.earliest_session_date]
        if len(eligible)!=1: raise ValueError('eligible session exact version missing')
        manifest={'schema_version':'m3-cffex-lineage-v1','calendar_versions':list(calendar_version_ids),'calendar_refs':list(record.calendar_refs),'scope_evidence_id':scope_evidence_id}
        manifest_id=self.put_evidence(canonical(manifest).encode(),evidence_kind='observation')
        children=[('cffex_rank_rows',dict(contract=r.contract,side=r.side.value,rank=r.rank,member_label_raw=r.member,member_key=None,member_scope=r.member_scope.value,open_interest=r.open_interest,open_interest_change=r.open_interest_change,volume=r.volume,volume_change=r.volume_change)) for r in parsed]
        body=dict(exchange=record.exchange,variety=record.variety,trade_date=record.trade_date,format_version=fmt,published_at=record.publication_time,earliest_session_date=record.earliest_session_date,calendar_version_id=eligible[0],row_count=len(children),rows_sha256=digest(sorted([r for _,r in children],key=canonical)),scope_evidence_id=scope_evidence_id)
        p=self._prepare('cffex_report',body,provenance,batch=batch,business_key={k:body[k] for k in ('exchange','variety','trade_date')},children=children)
        for key in ('event_time','available_at','observed_at','ingested_at'):
            if p[0][key]!=stamp(getattr(record,key)): raise ValueError('report time envelope mismatch')
        def finalize(c,ids):
            insert(c,'quality_assessments',dict(assessment_id='cffex-lineage:'+ids[0],data_version_id=ids[0],rules_version='m3-cffex-lineage-v1',assessed_at=self._now(),decision='UNKNOWN',reasons_json=['SOURCE_SCOPE_PUBLICATION_REQUIRE_INDEPENDENT_VERIFICATION'],metrics_json={'schema_version':'m3-quality-v1','lineage_evidence_id':manifest_id},evidence_id=manifest_id))
        return self._write([p],batch,returned_rows=len(parsed),finalize=finalize,failure_evidence_id=evidence)[0]

    def ranking_calendar(self, version_ids):
        from ai_trade.market_data.cffex_rankings_models import RankingSessionDay
        days={}
        with self.database.connection() as c:
            for vid in version_ids:
                v,r,_=self._version(c,vid)
                if v['dataset_key']!='market_session' or r['session_date'] in days: raise ValueError('duplicate/wrong session dataset')
                days[r['session_date']]=(v,r)
        class Calendar:
            def get_day(inner,*,exchange,session_date,as_of):
                if exchange!='CFFEX' or session_date not in days: raise KeyError(session_date)
                v,r=days[session_date]
                if r['is_trading_day'] is None or v['available_at'] is None or v['ingested_at'] is None or not v['evidence_id']: raise KeyError('unknown CFFEX calendar')
                return RankingSessionDay(exchange,session_date,bool(r['is_trading_day']),r['opens_at'],r['closes_at'],v['available_at'],v['ingested_at'],v['source_id'],v['evidence_id'],v['evidence_kind'] if v['evidence_kind']=='synthetic' else 'source_observation')
        return Calendar()

    def get_cffex(self, version_id):
        from ai_trade.market_data.cffex_rankings import build_record
        from ai_trade.market_data.cffex_rankings_models import CffexRankingsRequest
        with self.database.connection() as c:
            v,r,children=self._version(c,version_id)
            if v['dataset_key']!='cffex_report': raise ValueError('CFFEX report required')
            lineage=one(c,'quality_assessments',assessment_id='cffex-lineage:'+version_id)
            manifest=json.loads(self.evidence_bytes(lineage['metrics_json']['lineage_evidence_id'],c))
            attempt=one(c,'ingestion_attempts',attempt_id=v['attempt_id'])
            parent=one(c,'data_versions',data_version_id=v['supersedes_id'])['record_version'] if v['supersedes_id'] else None
            payload=self.evidence_bytes(v['evidence_id'],c)
        result=build_record(CffexRankingsRequest(r['exchange'],r['variety'],r['trade_date']),payload,run_id=attempt['committed_run_id'],observed_at=v['observed_at'],ingested_at=v['ingested_at'],publication_time=r['published_at'],calendar=self.ranking_calendar(manifest['calendar_versions']),evidence_kind=v['evidence_kind'],supersedes_version=parent,revision_reason=v['revision_reason'])
        if result.source_version!=v['record_version'] or stamp(result.available_at)!=v['available_at'] or list(result.calendar_refs)!=manifest['calendar_refs']: raise ValueError('CFFEX reconstructed provenance mismatch')
        actual=[dict(contract=x.contract,side=x.side.value,rank=x.rank,member_label_raw=x.member,member_key=None,member_scope=x.member_scope.value,open_interest=x.open_interest,open_interest_change=x.open_interest_change,volume=x.volume,volume_change=x.volume_change) for x in result.rows]
        if digest(sorted(actual,key=canonical))!=r['rows_sha256']: raise ValueError('CFFEX row hash mismatch')
        return result

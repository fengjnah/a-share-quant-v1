"""Additive M3 migrations. No I/O; v1/v2 SQL is deliberately untouched.

The fields and keys are the approved subset of DATA_DICTIONARY B/R/A.
Compound objects insert children first (deferred FK), then their immutable
parent. Once the parent exists, its children cannot be extended.
"""
from dataclasses import dataclass


def date_check(c):
    return f"({c} GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' AND date({c}, '+0 days') IS NOT NULL AND date({c}, '+0 days')={c})"


def time_check(c):
    return f"(length({c})=32 AND substr({c},11,1)='T' AND substr({c},20,1)='.' AND substr({c},27)='+00:00' AND julianday({c}) IS NOT NULL)"


def hash_check(c, size=64):
    return f"(length({c})={size} AND {c} NOT GLOB '*[^0-9a-f]*')"


@dataclass(frozen=True)
class Table:
    columns: str
    pk: tuple[str, ...]
    constraints: tuple[str, ...] = ()
    indexes: tuple[tuple[str, ...], ...] = ()

    @property
    def fields(self):
        return tuple(s.split(':')[0] for s in self.columns.split())


# t=nonempty text, j=JSON, d=date, s=UTC timestamp, h=hash, c=code SHA,
# n=nonnegative integer, i=signed integer, b=bool, f=finite real,
# p=positive finite real. '?' is the only nullable marker.
TABLES = {
    'data_sources': Table('source_id:t provider:t endpoint_key:t adapter_version:t dataset_key:t units_json:j time_policy_version:t registered_at:s', ('source_id',),
        ('UNIQUE(provider,endpoint_key,adapter_version,dataset_key,time_policy_version)',), (('dataset_key','registered_at'),)),
    'evidence_objects': Table('evidence_id:t sha256:h relative_uri:t byte_size:n media_type:t evidence_kind:t captured_at:s? registered_at:s privacy_class:t', ('evidence_id',),
        ("UNIQUE(sha256,privacy_class)", "CHECK(evidence_kind IN ('source_payload','sdk_frame','observation','receipt','synthetic'))"), (('registered_at',),)),
    'ingestion_attempts': Table('attempt_id:t source_id:t request_key:t request_json:j started_at:s finished_at:s outcome:t error_code:t? returned_rows:n? committed_run_id:t? evidence_id:t?', ('attempt_id',),
        ("UNIQUE(source_id,request_key,attempt_id)", "CHECK(outcome IN ('SUCCESS','FAILED','BLOCKED','DUPLICATE'))", "CHECK(finished_at>=started_at)", "CHECK(outcome<>'SUCCESS' OR committed_run_id IS NOT NULL)"), (('source_id','finished_at'),('committed_run_id',))),
    'data_versions': Table('data_version_id:h dataset_key:t business_key:j source_id:t record_version:t event_time:s? available_at:s? observed_at:s? ingested_at:s? registered_at:s payload_sha256:h quality_status:t evidence_kind:t evidence_id:t? attempt_id:t? supersedes_id:h? revision_reason:t?', ('data_version_id',),
        ("UNIQUE(dataset_key,business_key,source_id,record_version)", "UNIQUE(supersedes_id)", "CHECK(quality_status IN ('accepted','quarantined','unknown'))", "CHECK(evidence_kind IN ('source_observation','synthetic','legacy_unknown'))", "CHECK((supersedes_id IS NULL AND revision_reason IS NULL) OR (supersedes_id IS NOT NULL AND revision_reason IS NOT NULL AND supersedes_id<>data_version_id))", "CHECK(event_time IS NULL OR available_at IS NULL OR event_time<=available_at)", "CHECK(event_time IS NULL OR observed_at IS NULL OR event_time<=observed_at)", "CHECK(observed_at IS NULL OR ingested_at IS NULL OR observed_at<=ingested_at)"), (('dataset_key','business_key','available_at','ingested_at'),('source_id','registered_at'))),
    'legacy_version_links': Table('data_version_id:h daily_bar_version_id:i? security_version_id:i? calendar_version_id:i?', ('data_version_id',),
        ('CHECK((daily_bar_version_id IS NOT NULL)+(security_version_id IS NOT NULL)+(calendar_version_id IS NOT NULL)=1)', 'UNIQUE(daily_bar_version_id)', 'UNIQUE(security_version_id)', 'UNIQUE(calendar_version_id)')),
    'quality_assessments': Table('assessment_id:t data_version_id:h? attempt_id:t? rules_version:t assessed_at:s decision:t reasons_json:j metrics_json:j evidence_id:t? supersedes_id:t?', ('assessment_id',),
        ("CHECK((data_version_id IS NOT NULL)+(attempt_id IS NOT NULL)=1)", "CHECK(decision IN ('PASS','FAIL','UNKNOWN'))", 'UNIQUE(supersedes_id)'), (('data_version_id','assessed_at'),('attempt_id','assessed_at'))),
    'verification_receipts': Table('receipt_id:t scope_type:t source_id:t? data_version_id:h? claims_json:j decision:t issued_at:s available_at:s expires_at:s? evidence_id:t supersedes_id:t?', ('receipt_id',),
        ("CHECK((scope_type='SOURCE' AND source_id IS NOT NULL AND data_version_id IS NULL) OR (scope_type='DATA' AND source_id IS NULL AND data_version_id IS NOT NULL) OR (scope_type='REVIEW' AND source_id IS NULL AND data_version_id IS NULL))", "CHECK(decision IN ('VERIFIED','UNVERIFIED','REVOKED'))", 'CHECK(issued_at<=available_at)', 'CHECK(expires_at IS NULL OR expires_at>available_at)', 'UNIQUE(supersedes_id)'), (('scope_type','available_at'),('source_id','available_at'),('data_version_id','available_at'))),
    'instrument_catalog': Table('catalog_id:t entity_kind:t namespace:t entity_key:t equity_anchor_id:t? registered_at:s', ('catalog_id',),
        ("CHECK(entity_kind IN ('EQUITY','INDEX','SECTOR','FUTURE_CONTRACT'))", "CHECK(entity_kind='EQUITY' OR equity_anchor_id IS NULL)", 'UNIQUE(namespace,entity_key)', 'UNIQUE(equity_anchor_id)'), (('entity_kind','namespace'),)),
    'security_state_versions': Table('data_version_id:h instrument_id:t effective_from:d effective_to:d? st_status:t? suspended:b? delisting_organization:b? buy_allowed:b? sell_allowed:b? lot_size:n? limit_up_price:p? limit_down_price:p?', ('data_version_id',),
        ("CHECK(st_status IS NULL OR st_status IN ('NORMAL','ST','STAR_ST'))", 'CHECK(effective_to IS NULL OR effective_to>effective_from)', 'CHECK(lot_size IS NULL OR lot_size>0)', 'CHECK(limit_up_price IS NULL OR limit_down_price IS NULL OR limit_down_price<=limit_up_price)'), (('instrument_id','effective_from','effective_to'),)),
    'market_session_versions': Table('data_version_id:h market_key:t session_date:d is_trading_day:b? opens_at:s? closes_at:s? error_reason:t?', ('data_version_id',),
        ("CHECK(market_key='CFFEX')", 'CHECK((is_trading_day=1 AND opens_at IS NOT NULL AND closes_at IS NOT NULL AND opens_at<closes_at AND error_reason IS NULL) OR (is_trading_day=0 AND opens_at IS NULL AND closes_at IS NULL AND error_reason IS NULL) OR (is_trading_day IS NULL AND opens_at IS NULL AND closes_at IS NULL AND error_reason IS NOT NULL))'), (('market_key','session_date'),)),
    'index_bar_versions': Table('data_version_id:h catalog_id:t trade_date:d open:p high:p low:p close:p volume:f? volume_unit:t? amount_cny:f? adjustment_definition:t', ('data_version_id',),
        ('CHECK(low<=open AND open<=high AND low<=close AND close<=high)', 'CHECK((volume IS NULL)=(volume_unit IS NULL))', 'CHECK(volume IS NULL OR volume>=0)', 'CHECK(amount_cny IS NULL OR amount_cny>=0)'), (('catalog_id','trade_date'),)),
    'universe_versions': Table('data_version_id:h universe_key:t trade_date:d definition_version:t eligible_count:n? member_count:n members_sha256:h', ('data_version_id',),
        ('CHECK(eligible_count IS NULL OR eligible_count<=member_count)',), (('universe_key','trade_date'),)),
    'universe_members': Table('universe_version_id:h instrument_id:t membership_status:t security_version_id:i? state_version_id:h? inclusion_reason:t', ('universe_version_id','instrument_id'),
        ("CHECK(membership_status IN ('ELIGIBLE','EXCLUDED','UNKNOWN'))", "CHECK(membership_status<>'ELIGIBLE' OR (security_version_id IS NOT NULL AND state_version_id IS NOT NULL))"), (('instrument_id','universe_version_id'),)),
    'market_breadth_versions': Table('data_version_id:h universe_version_id:h? market_key:t trade_date:d advances:n? declines:n? flat:n? limit_up:n? limit_down:n? suspended:n? unavailable:n? missing:n? eligible_count:n? definition_version:t', ('data_version_id',),
        ('CHECK(limit_up IS NULL OR advances IS NULL OR limit_up<=advances)', 'CHECK(limit_down IS NULL OR declines IS NULL OR limit_down<=declines)'), (('market_key','trade_date'),)),
    'market_amount_versions': Table('data_version_id:h universe_version_id:h? market_key:t trade_date:d market_amount_cny:f? contributing_count:n? definition_version:t', ('data_version_id',),
        ('CHECK(market_amount_cny IS NULL OR market_amount_cny>=0)',), (('market_key','trade_date'),)),
    'cffex_report_versions': Table('data_version_id:h exchange:t variety:t trade_date:d format_version:t published_at:s? earliest_session_date:d? calendar_version_id:h? row_count:n rows_sha256:h scope_evidence_id:t?', ('data_version_id',),
        ("CHECK(exchange='CFFEX' AND variety IN ('IF','IH','IC','IM'))", 'CHECK(earliest_session_date IS NULL OR earliest_session_date>trade_date)'), (('variety','trade_date'),)),
    'cffex_rank_rows': Table('report_version_id:h contract:t side:t rank:n member_label_raw:t member_key:t? member_scope:t open_interest:n? open_interest_change:i? volume:n? volume_change:i?', ('report_version_id','contract','side','rank'),
        ("CHECK(side IN ('long','short','volume'))", "CHECK(member_scope IN ('代客','自营','代客+自营','unknown'))", 'CHECK(rank>0)', 'UNIQUE(report_version_id,contract,side,member_label_raw,member_scope)', "CHECK((side='volume' AND open_interest IS NULL AND open_interest_change IS NULL) OR (side IN ('long','short') AND volume IS NULL AND volume_change IS NULL))", 'CHECK(open_interest IS NOT NULL OR open_interest_change IS NULL)', 'CHECK(volume IS NOT NULL OR volume_change IS NULL)'), (('report_version_id','contract','member_key','member_scope'),)),
    'input_snapshots': Table('snapshot_id:h analysis_date:d as_of:s mode:t scope_json:j selection_policy_version:t manifest_sha256:h item_count:n check_count:n checks_sha256:h completeness:t blocking_reasons_json:j created_at:s', ('snapshot_id',),
        ("UNIQUE(manifest_sha256)", 'CHECK(snapshot_id=manifest_sha256)', "CHECK(mode IN ('research','strict_backtest','paper_trade'))", "CHECK(completeness IN ('COMPLETE','PARTIAL','BLOCKED'))", 'CHECK(created_at>=as_of)'), (('analysis_date','as_of'),)),
    'input_snapshot_items': Table('snapshot_id:h role:t ordinal:n data_version_id:h expected_sha256:h required:b', ('snapshot_id','role','ordinal'),
        ('UNIQUE(snapshot_id,role,data_version_id)',), (('data_version_id','snapshot_id'),)),
    'input_snapshot_checks': Table('snapshot_id:h check_role:t ordinal:n assessment_id:t? receipt_id:t? expected_sha256:h', ('snapshot_id','check_role','ordinal'),
        ('CHECK((assessment_id IS NOT NULL)+(receipt_id IS NOT NULL)=1)', 'UNIQUE(snapshot_id,check_role,assessment_id)', 'UNIQUE(snapshot_id,check_role,receipt_id)'), (('assessment_id',),('receipt_id',))),
    'analysis_runs': Table('analysis_run_id:t module:t analysis_date:d as_of:s generated_at:s code_sha:c rules_version:t contract_version:t parameters_json:j parameters_sha256:h environment_json:j environment_sha256:h input_snapshot_id:h status:t quality_status:t blocking_reasons_json:j result_sha256:h review_receipt_id:t? replay_of_run_id:t?', ('analysis_run_id',),
        ("CHECK(module IN ('M2','M3','M4','M5'))", "CHECK(status IN ('SUCCESS','PARTIAL','BLOCKED','FAILED'))", "CHECK(quality_status IN ('VALID','INVALID','UNKNOWN'))", 'CHECK(generated_at>=as_of)'), (('module','analysis_date','as_of'),('code_sha','rules_version','input_snapshot_id','parameters_sha256'))),
    'analysis_dependencies': Table('analysis_run_id:t role:t upstream_run_id:t upstream_result_sha256:h consumed_at:s gate_policy_version:t', ('analysis_run_id','role','upstream_run_id'),
        ('CHECK(analysis_run_id<>upstream_run_id)',), (('upstream_run_id',),)),
    'm3_diagnostics': Table('analysis_run_id:t indicator:t input_snapshot_id:h diagnostic_snapshot_id:h status:t admission:t calculated:b data_latest_date:d? diagnostic_json:j strategy_admission_json:j', ('analysis_run_id','indicator'),
        ("CHECK(admission IN ('BLOCKED','L1','L2','L3'))",
         "CHECK((json_extract(diagnostic_json,'$.indicator')=indicator AND json_extract(diagnostic_json,'$.status')=status AND json_extract(diagnostic_json,'$.data_snapshot_id')=diagnostic_snapshot_id AND json_extract(diagnostic_json,'$.calculated')=calculated AND json_extract(diagnostic_json,'$.admission')=CASE admission WHEN 'L1' THEN 'L1_OBSERVATION' WHEN 'L2' THEN 'L2_RESEARCH' WHEN 'L3' THEN 'L3_STRATEGY' ELSE admission END) IS TRUE)",
         "CHECK(json_type(strategy_admission_json,'$.live_trading')='false')",
         "CHECK(status<>'INVALID_DATA' OR (calculated=0 AND json_extract(diagnostic_json,'$.values')='{}'))",
         "CHECK((status<>'BLOCKED' AND admission<>'BLOCKED') OR calculated=0)"), (('indicator','data_latest_date','admission'),('diagnostic_snapshot_id',))),
    'factor_values': Table('analysis_run_id:t indicator:t factor_key:t business_date:d input_snapshot_id:h raw_value:f? raw_unit:t normalized_value:f? normalization_version:t weight:f? contribution:f? status:t reasons_json:j', ('analysis_run_id','indicator','factor_key','business_date'),
        ('CHECK(weight IS NULL OR (weight>=0 AND weight<=1))', 'CHECK(normalized_value IS NULL OR (normalized_value>=0 AND normalized_value<=100))', "CHECK(status IN ('AVAILABLE','MISSING','INVALID','BLOCKED'))",
         "CHECK((status='AVAILABLE' AND raw_value IS NOT NULL AND normalized_value IS NOT NULL AND weight IS NOT NULL AND contribution IS NOT NULL AND contribution=normalized_value*weight) OR (status<>'AVAILABLE' AND normalized_value IS NULL AND contribution IS NULL))"), (('factor_key','business_date'),)),
}

# Explicit references; deferred constraints permit child-first sealing. All use
# RESTRICT deletion, never CASCADE. Every FK receives a usable leading index.
FKS = {
 'ingestion_attempts': [('source_id','data_sources','source_id'),('committed_run_id','ingestion_runs','run_id'),('evidence_id','evidence_objects','evidence_id')],
 'data_versions': [('source_id','data_sources','source_id'),('evidence_id','evidence_objects','evidence_id'),('attempt_id','ingestion_attempts','attempt_id'),('supersedes_id','data_versions','data_version_id')],
 'legacy_version_links': [('data_version_id','data_versions','data_version_id'),('daily_bar_version_id','daily_bar_versions','version_id'),('security_version_id','security_versions','version_id'),('calendar_version_id','calendar_versions','version_id')],
 'quality_assessments': [('data_version_id','data_versions','data_version_id'),('attempt_id','ingestion_attempts','attempt_id'),('evidence_id','evidence_objects','evidence_id'),('supersedes_id','quality_assessments','assessment_id')],
 'verification_receipts': [('source_id','data_sources','source_id'),('data_version_id','data_versions','data_version_id'),('evidence_id','evidence_objects','evidence_id'),('supersedes_id','verification_receipts','receipt_id')],
 'instrument_catalog': [('equity_anchor_id','instruments','instrument_id')],
 'security_state_versions': [('data_version_id','data_versions','data_version_id'),('instrument_id','instruments','instrument_id')],
 'market_session_versions': [('data_version_id','data_versions','data_version_id')],
 'index_bar_versions': [('data_version_id','data_versions','data_version_id'),('catalog_id','instrument_catalog','catalog_id')],
 'universe_versions': [('data_version_id','data_versions','data_version_id')],
 'universe_members': [('universe_version_id','universe_versions','data_version_id'),('instrument_id','instruments','instrument_id'),('security_version_id','security_versions','version_id'),('state_version_id','security_state_versions','data_version_id')],
 'market_breadth_versions': [('data_version_id','data_versions','data_version_id'),('universe_version_id','universe_versions','data_version_id')],
 'market_amount_versions': [('data_version_id','data_versions','data_version_id'),('universe_version_id','universe_versions','data_version_id')],
 'cffex_report_versions': [('data_version_id','data_versions','data_version_id'),('calendar_version_id','market_session_versions','data_version_id'),('scope_evidence_id','evidence_objects','evidence_id')],
 'cffex_rank_rows': [('report_version_id','cffex_report_versions','data_version_id')],
 'input_snapshot_items': [('snapshot_id','input_snapshots','snapshot_id'),('data_version_id','data_versions','data_version_id')],
 'input_snapshot_checks': [('snapshot_id','input_snapshots','snapshot_id'),('assessment_id','quality_assessments','assessment_id'),('receipt_id','verification_receipts','receipt_id')],
 'analysis_runs': [('input_snapshot_id','input_snapshots','snapshot_id'),('review_receipt_id','verification_receipts','receipt_id'),('replay_of_run_id','analysis_runs','analysis_run_id')],
 'analysis_dependencies': [('analysis_run_id','analysis_runs','analysis_run_id'),('upstream_run_id','analysis_runs','analysis_run_id')],
 'm3_diagnostics': [('analysis_run_id','analysis_runs','analysis_run_id'),('input_snapshot_id','input_snapshots','snapshot_id')],
 'factor_values': [('analysis_run_id','analysis_runs','analysis_run_id'),('input_snapshot_id','input_snapshots','snapshot_id'),('analysis_run_id,indicator','m3_diagnostics','analysis_run_id,indicator')],
}

GROUPS = (
 tuple(list(TABLES)[:8]),
 tuple(list(TABLES)[8:17]),
 tuple(list(TABLES)[17:]),
)
TYPED = {'daily_bar':'legacy_version_links', 'security':'legacy_version_links', 'calendar':'legacy_version_links',
         'security_state':'security_state_versions', 'market_session':'market_session_versions',
         'index_bar':'index_bar_versions', 'universe':'universe_versions',
         'market_breadth':'market_breadth_versions', 'market_amount':'market_amount_versions',
         'cffex_report':'cffex_report_versions'}


def _column(spec):
    name, typ = spec.split(':'); optional = typ.endswith('?'); typ = typ.rstrip('?')
    sql_type = 'INTEGER' if typ in ('n','i','b') else 'REAL' if typ in ('f','p') else 'TEXT'
    checks = {'t':f"length(trim({name}))>0", 'j':f'json_valid({name})', 'd':date_check(name),
              's':time_check(name), 'h':hash_check(name), 'c':hash_check(name,40),
              'n':f"typeof({name})='integer' AND {name}>=0", 'i':f"typeof({name})='integer'",
              'b':f"typeof({name})='integer' AND {name} IN (0,1)",
              'f':f"typeof({name}) IN ('real','integer') AND abs({name})<=1.7976931348623157e308",
              'p':f"typeof({name}) IN ('real','integer') AND {name}>0 AND {name}<=1.7976931348623157e308"}
    check = checks[typ]
    return f"{name} {sql_type}" + ('' if optional else ' NOT NULL') + f' CHECK({name} IS NULL OR ({check}))'


def _table(name):
    table=TABLES[name]
    columns=[_column(c) for c in table.columns.split()]
    constraints=[f"PRIMARY KEY({','.join(table.pk)})", *table.constraints]
    for cols,parent,keys in FKS.get(name,()):
        constraints.append(f'FOREIGN KEY({cols}) REFERENCES {parent}({keys}) ON DELETE RESTRICT DEFERRABLE INITIALLY DEFERRED')
    result=[f"CREATE TABLE {name} ("+','.join(columns+constraints)+')']
    indexes=list(table.indexes)
    # A few redundant PK/UNIQUE-backed indexes are avoided by checking leading
    # PK/index columns. FK-specific names are stable migration content.
    for cols,_,_ in FKS.get(name,()):
        fields=tuple(cols.split(','))
        if table.pk[:len(fields)]!=fields and not any(i[:len(fields)]==fields for i in indexes):
            indexes.append(fields)
    for i,fields in enumerate(dict.fromkeys(indexes)):
        result.append(f"CREATE INDEX m3_{name}_{i} ON {name}({','.join(fields)})")
    for op in ('UPDATE','DELETE'):
        result.append(f"CREATE TRIGGER m3_immutable_{name}_{op.lower()} BEFORE {op} ON {name} BEGIN SELECT RAISE(ABORT,'M3 audit rows are immutable'); END")
    return result


def _guard(child, child_key, parent, parent_key):
    return f"CREATE TRIGGER m3_sealed_{child} BEFORE INSERT ON {child} WHEN EXISTS(SELECT 1 FROM {parent} WHERE {parent_key}=NEW.{child_key}) BEGIN SELECT RAISE(ABORT,'parent already sealed'); END"


def _version_seal(extended):
    names=tuple(dict.fromkeys(TYPED.values())) if extended else ('legacy_version_links',)
    count='+'.join(f'(SELECT count(*) FROM {n} WHERE data_version_id=NEW.data_version_id)' for n in names)
    choices=[]
    for kind,table in TYPED.items():
        if table not in names: continue
        extra=(f" AND {dict(daily_bar='daily_bar_version_id',security='security_version_id',calendar='calendar_version_id')[kind]} IS NOT NULL" if table=='legacy_version_links' else '')
        choices.append(f"(NEW.dataset_key='{kind}' AND EXISTS(SELECT 1 FROM {table} WHERE data_version_id=NEW.data_version_id{extra}))")
    return f"""CREATE TRIGGER m3_seal_versions BEFORE INSERT ON data_versions BEGIN
      SELECT CASE WHEN ({count})<>1 OR NOT ({' OR '.join(choices)}) THEN RAISE(ABORT,'exactly one matching typed version required') END;
      SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM data_sources s WHERE s.source_id=NEW.source_id AND s.dataset_key=NEW.dataset_key) THEN RAISE(ABORT,'source dataset mismatch') END;
      SELECT CASE WHEN NEW.supersedes_id IS NOT NULL AND NOT EXISTS(
        SELECT 1 FROM data_versions p WHERE p.data_version_id=NEW.supersedes_id
          AND p.dataset_key=NEW.dataset_key AND p.business_key=NEW.business_key AND p.source_id=NEW.source_id
          AND (p.event_time IS NULL OR NEW.event_time=p.event_time)
          AND (p.available_at IS NULL OR NEW.available_at>=p.available_at)
          AND (p.ingested_at IS NULL OR NEW.ingested_at>=p.ingested_at)
          AND (p.observed_at IS NULL OR NEW.observed_at>=p.observed_at)
          AND max(coalesce(NEW.available_at,''),coalesce(NEW.ingested_at,''))>max(coalesce(p.available_at,''),coalesce(p.ingested_at,'')))
        THEN RAISE(ABORT,'revision visibility must advance in same chain') END;
    END"""


def provenance_statements():
    result=[s for n in GROUPS[0] for s in _table(n)]
    result += ["CREATE UNIQUE INDEX m3_version_root ON data_versions(dataset_key,business_key,source_id) WHERE supersedes_id IS NULL",
               _guard('legacy_version_links','data_version_id','data_versions','data_version_id'),_version_seal(False)]
    for table,key,clock,target in [('quality_assessments','assessment_id','assessed_at',"p.data_version_id IS NEW.data_version_id AND p.attempt_id IS NEW.attempt_id AND p.rules_version=NEW.rules_version"),
                                    ('verification_receipts','receipt_id','available_at',"p.scope_type=NEW.scope_type AND p.source_id IS NEW.source_id AND p.data_version_id IS NEW.data_version_id AND json_extract(p.claims_json,'$.claim_type') IS json_extract(NEW.claims_json,'$.claim_type')")]:
        result.append(f"CREATE TRIGGER m3_chain_{table} BEFORE INSERT ON {table} WHEN NEW.supersedes_id IS NOT NULL BEGIN SELECT CASE WHEN NOT EXISTS(SELECT 1 FROM {table} p WHERE p.{key}=NEW.supersedes_id AND {target} AND NEW.{clock}>p.{clock}) THEN RAISE(ABORT,'decision revision must advance same target') END; END")
    return tuple(result)


def market_statements():
    result=[s for n in GROUPS[1] for s in _table(n)]
    for table in dict.fromkeys(TYPED.values()):
        if table!='legacy_version_links': result.append(_guard(table,'data_version_id','data_versions','data_version_id'))
    result += [_guard('universe_members','universe_version_id','universe_versions','data_version_id'),
               _guard('cffex_rank_rows','report_version_id','cffex_report_versions','data_version_id'),
               'DROP TRIGGER m3_seal_versions',_version_seal(True),
               "CREATE TRIGGER m3_index_kind BEFORE INSERT ON index_bar_versions WHEN NOT EXISTS(SELECT 1 FROM instrument_catalog WHERE catalog_id=NEW.catalog_id AND entity_kind='INDEX') BEGIN SELECT RAISE(ABORT,'index catalog required'); END",
               "CREATE TRIGGER m3_seal_universe BEFORE INSERT ON universe_versions BEGIN SELECT CASE WHEN NEW.member_count<>(SELECT count(*) FROM universe_members WHERE universe_version_id=NEW.data_version_id) OR (NEW.eligible_count IS NOT NULL AND (NEW.eligible_count<>(SELECT count(*) FROM universe_members WHERE universe_version_id=NEW.data_version_id AND membership_status='ELIGIBLE') OR EXISTS(SELECT 1 FROM universe_members WHERE universe_version_id=NEW.data_version_id AND membership_status='UNKNOWN'))) THEN RAISE(ABORT,'universe count/unknown mismatch') END; END",
               "CREATE TRIGGER m3_seal_report BEFORE INSERT ON cffex_report_versions WHEN NEW.row_count<>(SELECT count(*) FROM cffex_rank_rows WHERE report_version_id=NEW.data_version_id) OR NEW.format_version<>'named' OR NEW.row_count=0 BEGIN SELECT RAISE(ABORT,'complete named report required'); END"]
    return tuple(result)


def analysis_statements():
    result=[s for n in GROUPS[2] for s in _table(n)]
    for child,key,parent,pkey in [('input_snapshot_items','snapshot_id','input_snapshots','snapshot_id'),('input_snapshot_checks','snapshot_id','input_snapshots','snapshot_id'),('m3_diagnostics','analysis_run_id','analysis_runs','analysis_run_id'),('factor_values','analysis_run_id','analysis_runs','analysis_run_id'),('analysis_dependencies','analysis_run_id','analysis_runs','analysis_run_id')]:
        result.append(_guard(child,key,parent,pkey))
    result += ["""CREATE TRIGGER m3_seal_snapshot BEFORE INSERT ON input_snapshots BEGIN
       SELECT CASE WHEN NEW.item_count<>(SELECT count(*) FROM input_snapshot_items WHERE snapshot_id=NEW.snapshot_id) OR NEW.check_count<>(SELECT count(*) FROM input_snapshot_checks WHERE snapshot_id=NEW.snapshot_id) THEN RAISE(ABORT,'snapshot child count mismatch') END;
       SELECT CASE WHEN EXISTS(SELECT 1 FROM input_snapshot_items WHERE snapshot_id=NEW.snapshot_id GROUP BY role HAVING min(ordinal)<>0 OR max(ordinal)<>count(*)-1) OR EXISTS(SELECT 1 FROM input_snapshot_checks WHERE snapshot_id=NEW.snapshot_id GROUP BY check_role HAVING min(ordinal)<>0 OR max(ordinal)<>count(*)-1) THEN RAISE(ABORT,'noncontiguous input ordinal') END;
    END""", """CREATE TRIGGER m3_seal_run BEFORE INSERT ON analysis_runs BEGIN
      SELECT CASE WHEN NEW.module<>'M3' AND NEW.status='SUCCESS' THEN RAISE(ABORT,'module result capability not installed') END;
      SELECT CASE WHEN NEW.module='M3' AND NEW.status<>'FAILED' AND ((SELECT count(*) FROM m3_diagnostics WHERE analysis_run_id=NEW.analysis_run_id)<>8 OR EXISTS(SELECT 1 FROM m3_diagnostics WHERE analysis_run_id=NEW.analysis_run_id AND indicator NOT IN ('daily_trend','weekly_structure','wave','market_breadth','fear_greed','price_proxy','cffex_position','environment'))) THEN RAISE(ABORT,'eight M3 diagnostics required') END;
      SELECT CASE WHEN EXISTS(SELECT 1 FROM input_snapshots s WHERE s.snapshot_id=NEW.input_snapshot_id AND (s.analysis_date<>NEW.analysis_date OR s.as_of<>NEW.as_of)) OR EXISTS(SELECT 1 FROM m3_diagnostics d WHERE d.analysis_run_id=NEW.analysis_run_id AND d.input_snapshot_id<>NEW.input_snapshot_id) OR EXISTS(SELECT 1 FROM factor_values f WHERE f.analysis_run_id=NEW.analysis_run_id AND f.input_snapshot_id<>NEW.input_snapshot_id) THEN RAISE(ABORT,'analysis snapshot scope mismatch') END;
      SELECT CASE WHEN EXISTS(SELECT 1 FROM analysis_dependencies d JOIN analysis_runs u ON d.upstream_run_id=u.analysis_run_id WHERE d.analysis_run_id=NEW.analysis_run_id AND (u.as_of>NEW.as_of OR u.generated_at>d.consumed_at OR d.consumed_at>NEW.generated_at OR u.analysis_date<>NEW.analysis_date OR u.result_sha256<>d.upstream_result_sha256)) THEN RAISE(ABORT,'dependency scope/time/hash mismatch') END;
      SELECT CASE WHEN EXISTS(WITH RECURSIVE parents(id) AS (SELECT upstream_run_id FROM analysis_dependencies WHERE analysis_run_id=NEW.analysis_run_id UNION SELECT d.upstream_run_id FROM analysis_dependencies d JOIN parents p ON d.analysis_run_id=p.id) SELECT 1 FROM parents WHERE id=NEW.analysis_run_id) THEN RAISE(ABORT,'cyclic analysis dependencies') END;
    END"""]
    return tuple(result)

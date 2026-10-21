# M3 核心最小模型字段契约（待批准）

TASK-M3-CORE-DATA-MODEL-001。以下24节逐字复用 main `04e530871e2c8b4889c60027ac8d1ec4275009a2` 的 DATA_DICTIONARY；不修改其字段、NULL、键、索引或粒度。复制是本任务的可审查字段范围，不是SQL或实施批准。全部示例仍为SYNTHETIC，不导入正式库。

类型、全局不可变/四时点/哈希/JSON规则完整继承 [原字典第0节](DATA_DICTIONARY.md#0-记法与所有候选表适用的规则)。跨表与实施边界见[方案](../audits/TASK-M3-CORE-DATA-MODEL-001.md)。字典片段hash见[机器证据](../evidence/TASK_M3_CORE_DATA_MODEL_001_AUDIT.json)。

### B01 data_sources

字段：`source_id TEXT! PK; provider TEXT!; endpoint_key TEXT!; adapter_version TEXT!; dataset_key TEXT!; units_json JSON!; time_policy_version TEXT!; registered_at TS!`。
粒度=端点/适配器/数据集/口径版本，U(provider,endpoint_key,adapter_version,dataset_key,time_policy_version)，I(dataset_key,registered_at)，无FK。端点是无token模板，不存Authorization/代理凭据。修改来源定义新增source_id；无“许可=true”默认字段，许可由B07带时间证据给出。
生产/仓储/消费：经审核的配置登记→拟SourceRepository→所有版本/采集，非供应商自动认证。技术registered_at不参与行情事件判断。示意：`{source_id:"DEMO-SOURCE",provider:"SYNTHETIC",endpoint_key:"demo://index",adapter_version:"demo-v1",dataset_key:"index_bar",units_json:{price:"index_point"},time_policy_version:"demo-time-v1",registered_at:G}`。

### B02 evidence_objects

字段：`evidence_id TEXT! PK; sha256 TEXT!; relative_uri TEXT!; byte_size INTEGER!; media_type TEXT!; evidence_kind TEXT!; captured_at TS?; registered_at TS!; privacy_class TEXT!`。
粒度=一份不可变字节证据，U(sha256,privacy_class)，I(registered_at)，无FK。byte_size≥0；kind为source_payload/sdk_frame/observation/receipt/synthetic；URI限私有root内相对路径，禁止穿越/符号链接/外链。captured未知不补造，SDK帧不写source_payload。丢失文件保留引用并另报质量失败，不悄悄删索引。
EvidenceStore适配→EvidenceRepository→M0/审计/版本解析。示意：`{evidence_id:"DEMO-EVIDENCE",sha256:H,relative_uri:"synthetic/demo.json",byte_size:2,media_type:"application/json",evidence_kind:"synthetic",registered_at:G,privacy_class:"private"}`。

### B03 ingestion_attempts

字段：`attempt_id TEXT! PK; source_id TEXT! FK→B01; request_key TEXT!; request_json JSON!; started_at TS!; finished_at TS!; outcome TEXT!; error_code TEXT?; returned_rows INTEGER?; committed_run_id TEXT? FK→ingestion_runs.run_id; evidence_id TEXT? FK→B02`。
粒度=一次已结束发送/解析/写入尝试，U(source_id,request_key,attempt_id)，I(source_id,finished_at)、I(committed_run_id)。outcome=SUCCESS/FAILED/BLOCKED/DUPLICATE；成功必须run存在，失败未返回行数用NULL而非0。request_json去凭据，只保存允许参数；重试新attempt，不复用run或改原行。进行中状态在日志，不伪造finished_at；崩溃后恢复只按可证事实登记BLOCKED。
采集编排→IngestionAuditRepository→M0质量/运维。示意：`{attempt_id:"DEMO-ATTEMPT",source_id:"DEMO-SOURCE",request_key:"DEMO-REQUEST",request_json:{symbol:"DEMO_INDEX"},started_at:O,finished_at:I,outcome:"BLOCKED",error_code:"AUTHORIZATION_UNKNOWN"}`。

### B04 data_versions（通用引用目录，不替代事实表）

字段：`data_version_id TEXT! PK; dataset_key TEXT!; business_key JSON!; source_id TEXT! FK→B01; record_version TEXT!; event_time TS?; available_at TS?; observed_at TS?; ingested_at TS?; registered_at TS!; payload_sha256 TEXT!; quality_status TEXT!; evidence_kind TEXT!; evidence_id TEXT? FK→B02; attempt_id TEXT? FK→B03; supersedes_id TEXT? FK→B04; revision_reason TEXT?`。
粒度=来源内一个业务对象的不可变版本；business_key必须规范JSON文本。U(dataset_key,business_key,source_id,record_version)，U(supersedes_id)，部分U(dataset_key,business_key,source_id) WHERE supersedes_id IS NULL；I(dataset_key,business_key,available_at,ingested_at)，I(source_id,registered_at)。data_version_id为封套/键/载荷摘要的全局内容ID，不能用旧跨库整数ID代替。质量=accepted/quarantined/unknown；evidence_kind=source_observation/synthetic/legacy_unknown。
缺任一时点允许存“观察目录”，**不能封存为严格可用输入**；已知时点执行相应先后关系。修订同dataset/business/source、显式前驱/原因，不分叉；max(available,ingested)严格推进，已知observed不倒退，未知链不据此认证历史。源变更是显式选择另链，不能自动拼成同源。
领域写入/旧版目录桥→VersionCatalogRepository→所有输入快照。示意：`{data_version_id:"DEMO-DV",dataset_key:"index_bar",business_key:{symbol:"DEMO_INDEX",trade_date:"2026-10-16"},source_id:"DEMO-SOURCE",record_version:"DEMO-V1",event_time:T,available_at:A,observed_at:O,ingested_at:I,registered_at:G,payload_sha256:H,quality_status:"accepted",evidence_kind:"synthetic",evidence_id:"DEMO-EVIDENCE"}`。

### B05 legacy_version_links

字段：`data_version_id TEXT! PK FK→B04; daily_bar_version_id INTEGER? FK→daily_bar_versions.version_id; security_version_id INTEGER? FK→security_versions.version_id; calendar_version_id INTEGER? FK→calendar_versions.version_id`。
粒度=本库一个现有版本的目录映射；三个nullable字段恰好一个非NULL，分别U各字段。dataset必须匹配所选列；目录source/version/时间/哈希必须与原行一致。没有旧数据改写；无观测时间不能新增observed。桥所在库的DB身份由部署配置绑定，导出使用data_version_id+hash，不暴露可碰撞的整数ID。
授权只读索引回填/新写适配→LegacyVersionCatalog→SnapshotRepository/M2/M4。示意：`{data_version_id:"DEMO-LEGACY-DV",daily_bar_version_id:1}`。

### B06 quality_assessments

字段：`assessment_id TEXT! PK; data_version_id TEXT? FK→B04; attempt_id TEXT? FK→B03; rules_version TEXT!; assessed_at TS!; decision TEXT!; reasons_json JSON!; metrics_json JSON!; evidence_id TEXT? FK→B02; supersedes_id TEXT? FK→B06`。
粒度=一次质量决定，两个目标恰一非NULL；U(supersedes_id)，I(data_version_id,assessed_at)、I(attempt_id,assessed_at)。decision=PASS/FAIL/UNKNOWN；JSON有类型/单位且无原始行情和secret。新决定追加，时点必须前进；新FAIL不回退旧PASS。结构质量不等于授权/时间认证。
验证器→QualityRepository→快照封存/来源诊断。示意：`{assessment_id:"DEMO-Q",data_version_id:"DEMO-DV",rules_version:"demo-quality-v1",assessed_at:G,decision:"UNKNOWN",reasons_json:["SYNTHETIC"],metrics_json:{rows:1}}`。

### B07 verification_receipts

字段：`receipt_id TEXT! PK; scope_type TEXT!; source_id TEXT? FK→B01; data_version_id TEXT? FK→B04; claims_json JSON!; decision TEXT!; issued_at TS!; available_at TS!; expires_at TS?; evidence_id TEXT! FK→B02; supersedes_id TEXT? FK→B07`。
粒度=一次有权限签发者的证据决定；scope SOURCE→仅source_id，DATA→仅data_version_id，REVIEW→二者NULL。decision=VERIFIED/UNVERIFIED/REVOKED；U(supersedes_id)，I(scope_type,available_at)、I(source_id,available_at)、I(data_version_id,available_at)。收据查询使用available≤as_of、未过期及最新可见撤销语义；claims内issuer/authority_ref/allowed_uses(研究、存储、自动化、展示、再分发逐项)/scope/valid_business_range必填。REVIEW另需implementation_sha/rules_version/data_snapshot_id/independent_h_review_ref/approved_at/execution_constraints_ref/out_of_sample_validation_ref，不得只有布尔validated。
独立授权/审查流程→ReceiptRepository→M3核心适配和发布验证；collector没有签发权。表中有声明不证明issuer可信，信任根是独立批准配置，未配置即BLOCKED。示意：`{receipt_id:"DEMO-RECEIPT",scope_type:"SOURCE",source_id:"DEMO-SOURCE",claims_json:{issuer:"SYNTHETIC",authority_ref:"DEMO-NO-AUTHORITY",allowed_uses:[],scope:"demo",valid_business_range:["2026-10-16","2026-10-16"]},decision:"UNVERIFIED",issued_at:G,available_at:G,evidence_id:"DEMO-EVIDENCE"}`。

### B08 instrument_catalog

字段：`catalog_id TEXT! PK; entity_kind TEXT!; namespace TEXT!; entity_key TEXT!; equity_anchor_id TEXT? FK→instruments.instrument_id; registered_at TS!`。
粒度=技术实体登记；kind=EQUITY/INDEX/SECTOR/FUTURE_CONTRACT，U(namespace,entity_key)，U(equity_anchor_id)，I(entity_kind,namespace)。非EQUITY的anchor必须NULL；EQUITY桥不因存在而认证上市实体，不保存当前名称当历史名。旧股票id不重键，指数不写旧instruments。
身份审核/源映射→InstrumentCatalogRepository→指数/行业/持仓/结果引用。示意：`{catalog_id:"DEMO-INDEX",entity_kind:"INDEX",namespace:"synthetic",entity_key:"DEMO_INDEX",registered_at:G}`。

### B09 security_state_versions

字段：`data_version_id TEXT! PK FK→B04; instrument_id TEXT! FK→instruments; effective_from DATE!; effective_to DATE?; st_status TEXT?; suspended BOOL?; delisting_organization BOOL?; buy_allowed BOOL?; sell_allowed BOOL?; lot_size INTEGER?; limit_up_price REAL?; limit_down_price REAL?`。
粒度=单实体状态有效段的完整来源版本；business_key含instrument_id/effective_from。I(instrument_id,effective_from,effective_to)；状态段按来源/as_of不能重叠；st枚举NORMAL/ST/STAR_ST，仅有明确证据才非NULL；lot_size>0，限价>0，未知不执行/不推休市。半开有效区间，修改追加前驱版本，源内缺字段仍保持NULL。
状态适配器→SecurityStateRepository→M4/M5风险，不替代E06名称/生命期。示意：`{data_version_id:"DEMO-STATE-DV",instrument_id:"listing:DEMO:A",effective_from:"2026-10-16"}`，所有状态未知。

### B10 market_session_versions

字段：`data_version_id TEXT! PK FK→B04; market_key TEXT!; session_date DATE!; is_trading_day BOOL?; opens_at TS?; closes_at TS?; error_reason TEXT?`。
粒度=非现有SH/SZ/BJ市场的一日来源版本；P0仅CFFEX，禁止重复注册SH/SZ/BJ。I(market_key,session_date)。unknown/source_error不当休市；已知开市需明确开收盘、opens<closes，时区按权威会话。event_time是该日历公告事件，绝不要求公告晚于未来session。
日历源→ExtendedCalendarRepository，适配现有RankingCalendar→CFFEX/M5；CN_A由原E07各市场版本及manifest范围解释。示意：`{data_version_id:"DEMO-SESSION-DV",market_key:"CFFEX",session_date:"2026-10-16",error_reason:"SYNTHETIC_UNKNOWN_SESSION"}`。

### B11 index_bar_versions

字段：`data_version_id TEXT! PK FK→B04; catalog_id TEXT! FK→B08; trade_date DATE!; open REAL!; high REAL!; low REAL!; close REAL!; volume REAL?; volume_unit TEXT?; amount_cny REAL?; adjustment_definition TEXT!`。
粒度=单指数单日来源/口径版本；catalog必须INDEX，business_key含catalog/date/adjustment。I(catalog_id,trade_date)；OHLC正有限且关系正确，单位指数点；volume/amount非负；volume与unit成对存在，未知不得填0。不将550行当完整日历，不从无量OHLC生成市场成交额。
旧指数观察的授权导入/未来源→IndexPriceRepository→M3；版本时间由B04。示意：`{data_version_id:"DEMO-DV",catalog_id:"DEMO-INDEX",trade_date:"2026-10-16",open:100,high:102,low:99,close:101,adjustment_definition:"DEMO_SOURCE_DEFINITION"}`。

### B14 universe_versions

字段：`data_version_id TEXT! PK FK→B04; universe_key TEXT!; trade_date DATE!; definition_version TEXT!; eligible_count INTEGER?; member_count INTEGER!; members_sha256 TEXT!`。
粒度=一个历史日/明确市场范围的证券池完整版本；I(universe_key,trade_date)，count≥0；members_hash按B15有序完整集合计算。eligible_count未知仍可保存观察，但不能作为全A覆盖分母；完整成员与历史状态/日历的可见证据齐备才可认证。现有M4最多20股不是CN_A universe。
未来历史池构建→UniverseRepository→宽度/成交额/M4/M5。示意：`{data_version_id:"DEMO-UNIVERSE-DV",universe_key:"DEMO_A",trade_date:"2026-10-16",definition_version:"demo-universe-v1",member_count:1,members_sha256:H}`。

### B15 universe_members

字段：`universe_version_id TEXT! FK→B14.data_version_id; instrument_id TEXT! FK→instruments; membership_status TEXT!; security_version_id INTEGER? FK→security_versions; state_version_id TEXT? FK→B09.data_version_id; inclusion_reason TEXT!`。
PK(universe_version_id,instrument_id)，I(instrument_id,universe_version_id)。粒度=某池版本一个成员；status=ELIGIBLE/EXCLUDED/UNKNOWN，与历史身份/状态引用一致，缺证据不得ELIGIBLE。父行和全部成员同事务，封存不可追加。
UniverseRepository生产/查询→M3分母/M4；membership业务日与父一致、系统时点继承父B04且被引用版本必须已可见。示意：`{universe_version_id:"DEMO-UNIVERSE-DV",instrument_id:"listing:DEMO:A",membership_status:"UNKNOWN",inclusion_reason:"NO_HISTORICAL_STATUS"}`。

### R01 market_breadth_versions

字段：`data_version_id TEXT! PK FK→B04; universe_version_id TEXT? FK→B14; market_key TEXT!; trade_date DATE!; advances INTEGER?; declines INTEGER?; flat INTEGER?; limit_up INTEGER?; limit_down INTEGER?; suspended INTEGER?; unavailable INTEGER?; missing INTEGER?; eligible_count INTEGER?; definition_version TEXT!`。
粒度=单日单源明确范围的宽度版本；I(market_key,trade_date)。计数非负；五计数可保存观察，认证分母必须同日B14；eligible=涨+跌+平+suspended+unavailable+missing；涨停≤上涨、跌停≤下跌的适用规则须按源定义验证，不悄悄套相反口径。无历史池/分区时分母NULL，不能用五计数和代替。
宽度适配/经核验逐股聚合→MarketResearchRepository→M3；时间/证据B04。示意：`{data_version_id:"DEMO-BREADTH-DV",market_key:"CN_A",trade_date:"2026-10-16",definition_version:"demo-breadth-v1"}`，没有任何真实家数。

### R02 market_amount_versions

字段：`data_version_id TEXT! PK FK→B04; universe_version_id TEXT? FK→B14; market_key TEXT!; trade_date DATE!; market_amount_cny REAL?; contributing_count INTEGER?; definition_version TEXT!`。
粒度=单日全市场额的单源版本；I(market_key,trade_date)。amount非负有限、贡献数非负且不超过相应池；范围不一致或未知不得入完整恐贪。与宽度分表是为了保留不同来源的独立时点，不是允许日期错拼。指数amount不可替代。
待接通全A源/合格汇总→MarketResearchRepository→M3；当前无已注册真实来源。示意：`{data_version_id:"DEMO-AMOUNT-DV",market_key:"CN_A",trade_date:"2026-10-16",definition_version:"demo-amount-v1"}`。

### R03 cffex_report_versions

字段：`data_version_id TEXT! PK FK→B04; exchange TEXT!; variety TEXT!; trade_date DATE!; format_version TEXT!; published_at TS?; earliest_session_date DATE?; calendar_version_id TEXT? FK→B10.data_version_id; row_count INTEGER!; rows_sha256 TEXT!; scope_evidence_id TEXT? FK→B02`。
粒度=一个品种/交易日完整源文件版本；exchange=CFFEX，variety=IF/IH/IC/IM；I(variety,trade_date)。published_at未知不补造；实际available必须由现有CFFEX时间规则+可见权威日历证明，缺失允许原始观察但不能构造正式可消费record。只有文件成功不认证member_scope/授权。
现有parse/版本校验适配→CffexRepository→M3；封存全文件与子行原子，contracts由真实子行推导。示意：`{data_version_id:"DEMO-CFFEX-DV",exchange:"CFFEX",variety:"IF",trade_date:"2026-10-16",format_version:"DEMO_CSV",row_count:1,rows_sha256:H}`。

### R04 cffex_rank_rows

字段：`report_version_id TEXT! FK→R03; contract TEXT!; side TEXT!; rank INTEGER!; member_label_raw TEXT!; member_key TEXT?; member_scope TEXT!; open_interest INTEGER?; open_interest_change INTEGER?; volume INTEGER?; volume_change INTEGER?`。
粒度=某份已封存报告的一个合约/方向/排名行。PK(report_version_id,contract,side,rank)，U(report_version_id,contract,side,member_label_raw,member_scope)，I(report_version_id,contract,member_key,member_scope)。side=long/short/volume；rank>0；member_scope=代客/自营/代客+自营/unknown；持仓/成交非负，变化可负；按side检查相应字段。member_key未知不自动规范合并；Top-N缺一侧=NULL不是0，不跨合约/代客自营加总“机构净仓”。
CffexRepository→现有select_visible_version/net_positions_at，时间全部属于父报告。示意：`{report_version_id:"DEMO-CFFEX-DV",contract:"DEMO_IF",side:"long",rank:1,member_label_raw:"示意会员",member_scope:"unknown",open_interest:1}`（不是实际持仓）。

### A01 input_snapshots

字段：`snapshot_id TEXT! PK; analysis_date DATE!; as_of TS!; mode TEXT!; scope_json JSON!; selection_policy_version TEXT!; manifest_sha256 TEXT!; item_count INTEGER!; check_count INTEGER!; checks_sha256 TEXT!; completeness TEXT!; blocking_reasons_json JSON!; created_at TS!`。
粒度=一次封存的、确切版本选择；ID为规范manifest哈希，U(manifest_sha256)，I(analysis_date,as_of)。mode沿用research/strict_backtest/paper_trade；completeness=COMPLETE/PARTIAL/BLOCKED；item_count≥0且等于A02总数，check_count/checks_sha256封存A17的质量和收据集合，created≥as_of。缺某必需数据集必须保留原因，0项BLOCKED快照可存，不伪造输入。完整性和正式认证不同。
快照构建→SnapshotRepository→所有分析；不能以`latest`别名重放。示意：`{snapshot_id:"DEMO-SNAPSHOT",analysis_date:"2026-10-16",as_of:C,mode:"research",scope_json:{index:"DEMO_INDEX"},selection_policy_version:"demo-select-v1",manifest_sha256:H,item_count:1,check_count:1,checks_sha256:H,completeness:"BLOCKED",blocking_reasons_json:["SYNTHETIC"],created_at:G}`。

### A02 input_snapshot_items

字段：`snapshot_id TEXT! FK→A01; role TEXT!; ordinal INTEGER!; data_version_id TEXT! FK→B04; expected_sha256 TEXT!; required BOOL!`。
粒度=某封存快照的一个角色/序号输入引用。PK(snapshot_id,role,ordinal)，U(snapshot_id,role,data_version_id)，I(data_version_id,snapshot_id)；role为版本化规则列举的price_row/calendar_row/universe/breadth/amount/status/factor等，ordinal≥0且role内连续。每条实际输入记录显式版本，不只记首尾日期；版本时间/业务日/源范围按角色检查。父封存后禁止加行。
SnapshotRepository生产/验证→回放；示意：`{snapshot_id:"DEMO-SNAPSHOT",role:"price_row",ordinal:0,data_version_id:"DEMO-DV",expected_sha256:H,required:1}`。

### A03 analysis_runs

字段：`analysis_run_id TEXT! PK; module TEXT!; analysis_date DATE!; as_of TS!; generated_at TS!; code_sha TEXT!; rules_version TEXT!; contract_version TEXT!; parameters_json JSON!; parameters_sha256 TEXT!; environment_json JSON!; environment_sha256 TEXT!; input_snapshot_id TEXT! FK→A01; status TEXT!; quality_status TEXT!; blocking_reasons_json JSON!; result_sha256 TEXT!; review_receipt_id TEXT? FK→B07; replay_of_run_id TEXT? FK→A03`。
粒度=一次已结束运行；module=M2/M3/M4/M5，status=SUCCESS/PARTIAL/BLOCKED/FAILED；quality=VALID/INVALID/UNKNOWN。I(module,analysis_date,as_of)，I(code_sha,rules_version,input_snapshot_id,parameters_sha256)。相同计算可有独立执行时刻/ID，不以UNIQUE误吞重跑；显式幂等写同run/hash返回既有，不同hash拒绝。generated≥as_of；status SUCCESS不自动授权交易。
分析编排→AnalysisRunRepository→结果页/审计/发布。失败也保留输入快照与原因，业务结果子项按模块可为空；完整运行事务封存。code_sha来自实际运行构建证明，不复制管线历史常量。environment_json只记实际Python/关键依赖版本、锁文件hash、时区/数值序列化政策，不保存完整环境变量；成功运行必须可核验，环境不同重放需披露，不保证数值字节相同。示意：`{analysis_run_id:"DEMO-M3",module:"M3",analysis_date:"2026-10-16",as_of:C,generated_at:G,code_sha:S,rules_version:"m3-core-rules-v1",contract_version:"m3-core-diagnostic-v1",parameters_json:{mode:"research"},parameters_sha256:H,environment_json:{python:"SYNTHETIC_UNKNOWN",dependencies:{},lock_sha256:H},environment_sha256:H,input_snapshot_id:"DEMO-SNAPSHOT",status:"BLOCKED",quality_status:"UNKNOWN",blocking_reasons_json:["SYNTHETIC"],result_sha256:H}`。

### A04 analysis_dependencies

字段：`analysis_run_id TEXT! FK→A03; role TEXT!; upstream_run_id TEXT! FK→A03; upstream_result_sha256 TEXT!; consumed_at TS!; gate_policy_version TEXT!`。
PK(analysis_run_id,role,upstream_run_id)，I(upstream_run_id)。粒度=下游对一个已封存结果的依赖；禁止自环/循环；role=stock_analysis/market_gate/backtest_input等，校验模块、日期、上游as_of≤下游as_of，且上游generated_at≤consumed_at≤下游generated_at。as_of是输入知识截止，不能误当结果实际生成时钟；默认同业务日/共同cutoff，滞后须明确政策及告警。在线信号最早可用不早于依赖与自身实际生成；旧日回测须逐会话匹配，不接受结束日快照或后来才产生的结果冒充历史已知。
编排器→AnalysisRunRepository→M4/M5/发布。示意：`{analysis_run_id:"DEMO-M4",role:"market_gate",upstream_run_id:"DEMO-M3",upstream_result_sha256:H,consumed_at:G,gate_policy_version:"demo-gate-v1"}`，DEMO-M4的generated_at须不早于G；不能声称该结果在C已算完。

### A06 m3_diagnostics

字段：`analysis_run_id TEXT! FK→A03; indicator TEXT!; input_snapshot_id TEXT! FK→A01; diagnostic_snapshot_id TEXT!; status TEXT!; admission TEXT!; calculated BOOL!; data_latest_date DATE?; diagnostic_json JSON!; strategy_admission_json JSON!`。
PK(analysis_run_id,indicator)，I(indicator,data_latest_date,admission)，I(diagnostic_snapshot_id)。粒度=一次M3运行的一项Diagnostic；成功完整M3包必须覆盖8个模块，BLOCKED也保存各自原因。diagnostic_json必须是原to_dict全量，包括request/source及认证收据/times/coverage/values/calculated/reasons/missing_fields/definitions_version/schema_version/data_snapshot_id/allowed_uses；不能用去values下载替代。外列与JSON逐一一致；indicator子快照只能是整批输入的明确子集且hash可重建。
核心输出适配→M3ResultRepository→展示/M4验证器；不由Repository提高admission，live_trading永远false。strategy_admission_json保留现有strategy_admission返回及其绑定review引用，不能用L1/普通SUCCESS开闸。示意：`{analysis_run_id:"DEMO-M3",indicator:"environment",input_snapshot_id:"DEMO-SNAPSHOT",diagnostic_snapshot_id:H,status:"SOURCE_UNAVAILABLE",admission:"BLOCKED",calculated:0,diagnostic_json:DEMO_DIAGNOSTIC,strategy_admission_json:{admission:"BLOCKED",strategy_allowed:false,live_trading:false,blocking_reasons:["STRATEGY_EVIDENCE_REQUIRED"]}}`。DEMO_DIAGNOSTIC完整结构如下，hash仅示意、不冒充真实核心重算摘要：

```json
{
  "indicator": "environment", "schema_version": "m3-core-diagnostic-v1",
  "definitions_version": "m3-core-rules-v1",
  "request": {"analysis_date":"2026-10-16","as_of":"2026-10-16T09:30:00.000000+00:00","symbol":"DEMO_INDEX","instrument_type":"INDEX","mode":"research"},
  "source": {"source":"synthetic:DEMO:v1","source_version":"DEMO-V1","lineage_refs":["synthetic:DEMO"],"verification":{"status":"UNKNOWN","refs":[]},"research_authorization":{"status":"UNKNOWN","refs":[]},"time_verification":{"status":"UNKNOWN","refs":[]},"evidence_kind":"synthetic","latest_source_date":null,"endpoint":null},
  "data_latest_date": null,
  "times": {"event_time":null,"observed_at":null,"ingested_at":null,"available_at":null},
  "coverage": {"valid_samples":0,"expected_samples":null,"ratio":null,"denominator":"UNKNOWN","denominator_refs":[],"missing_dates":[]},
  "values": {}, "calculated":false,"admission":"BLOCKED","status":"SOURCE_UNAVAILABLE",
  "reasons":[{"code":"SOURCE_UNAVAILABLE","detail":"SYNTHETIC示意，没有真实输入","next_action":"取得经批准的真实版本","blocks":["L2","L3"]}],
  "missing_fields":[],"data_snapshot_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "time_verification":{"status":"UNKNOWN","refs":[]},
  "allowed_uses":{"observation":false,"research":false,"strategy":false,"live_trading":false}
}
```

### A07 factor_values

字段：`analysis_run_id TEXT! FK→A03; indicator TEXT!; factor_key TEXT!; business_date DATE!; input_snapshot_id TEXT! FK→A01; raw_value REAL?; raw_unit TEXT!; normalized_value REAL?; normalization_version TEXT!; weight REAL?; contribution REAL?; status TEXT!; reasons_json JSON!`。
PK(analysis_run_id,indicator,factor_key,business_date)，复合FK(analysis_run_id,indicator)→A06，I(factor_key,business_date)。粒度=该M3运行某历史日/因子的原值、归一及贡献；权重[0,1]，未知不重分配；normalized范围按版本规则，缺任一必要因素总分NULL。指向真实输入子集，排除当前样本的历史分位窗口按原规则版本，不新增指标。
现有M3因子适配→M3ResultRepository→解释/重放，不能独立替代M3门禁。示意：`{analysis_run_id:"DEMO-M3",indicator:"fear_greed",factor_key:"market_turnover",business_date:"2026-10-16",input_snapshot_id:"DEMO-SNAPSHOT",raw_unit:"CNY",normalization_version:"demo-normalize-v1",status:"MISSING",reasons_json:["NO_FULL_A_AMOUNT"]}`。

### A17 input_snapshot_checks

字段：`snapshot_id TEXT! FK→A01; check_role TEXT!; ordinal INTEGER!; assessment_id TEXT? FK→B06; receipt_id TEXT? FK→B07; expected_sha256 TEXT!`。
PK(snapshot_id,check_role,ordinal)，U(snapshot_id,check_role,assessment_id)，U(snapshot_id,check_role,receipt_id)，I(assessment_id)、I(receipt_id)。粒度=快照所采用的一项质量决定或源/时间/许可/审核收据；恰一目标非NULL，role与目标类型/范围吻合，ordinal非负连续。严格可用快照只引用截止前可见的具体决定，封存后不能换“最新收据”；质量/收据缺失以快照blocking_reasons保留，不造PASS记录。A01的计数/哈希包含该集合。
SnapshotRepository保存/验证→M3/M4/M5/重放；示意：`{snapshot_id:"DEMO-SNAPSHOT",check_role:"source_authorization",ordinal:0,receipt_id:"DEMO-RECEIPT",expected_sha256:H}`，示意UNVERIFIED收据不能解除BLOCKED。

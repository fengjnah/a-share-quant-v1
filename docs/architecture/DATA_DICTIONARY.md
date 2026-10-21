# 字段级数据字典（既有七表 + PROPOSED 候选表）

本字典不是SQL迁移。基线及证据见[总设计](DATA_PERSISTENCE_ARCHITECTURE.md)。所有新增表、Repository名称、约束均为P，尚未实现；现有表为F。**下面所有示例均为SYNTHETIC设计示意，不能导入真实库、作为行情/收益/认证证据。**

## 0. 记法与所有候选表适用的规则

- `TEXT/INTEGER/REAL`为SQLite存储类型；`TS`=TEXT固定UTC微秒`YYYY-MM-DDTHH:MM:SS.ffffff+00:00`，`DATE`=TEXT合法上海业务日；`JSON`=TEXT且json_valid及指定对象/数组schema；`BOOL`=INTEGER且只能0/1。`!`=NOT NULL，`?`=允许NULL。无隐含新增字段。所有TEXT ID非空；SHA为64位hex，代码SHA为40位hex。REAL必须有限，未知使用NULL，不使用NaN/Infinity或0占位。
- PK列全部显式NOT NULL，复合PK不依赖SQLite隐含非空。`U(...)`=UNIQUE；`I(...)`=非唯一索引；`FK`默认RESTRICT、禁止CASCADE删除。未列其他FK即无其他物理FK。所有FK列配查询索引；PK/UQ的自动索引不重复建。
- 新表默认禁止UPDATE/DELETE，子表不能在其父批次封存后INSERT；复合对象（universe、CFFEX报告、输入快照、结果、发布批次）父子在单个事务内完整提交。父行含子项数量/哈希，禁止仅靠“append-only”却允许后来追加子项改变旧快照。允许失败的只是整个事务；后续状态另写事件或新版本。
- 所有业务版本通过`data_versions`取得来源/record_version/四时点/证据/结构质量，不在每个typed子表重复时间。`data_version_id`必须有且仅有对应dataset的一张typed子表或legacy链接；目录注册与typed行同事务，提交前枚举检查并校验哈希。FK本身不能保证跨表一对一完整性，需Repository封存校验/触发器，未来负例测试覆盖。
- 版本去重、supersedes、可见性、撤销与删除统一见[血缘规则](DATA_LINEAGE.md)。未注明业务时点的技术登记表没有行情event_time；它的registered/created/recorded时间不冒充available_at。
- 每张表下面给一个**示意模板**：`T=2026-10-16T07:00:00.000000+00:00`，`O=...09:00:00.000000+00:00`，`A=...09:01:00.000000+00:00`，`I=...09:02:00.000000+00:00`，`C=...09:30:00.000000+00:00`，`G=...10:00:00.000000+00:00`；日期均2026-10-16，H=64个a、S=40个f。模板中这些符号须展开为字符串才是JSON；不是可执行夹具。示例省略的`?`列一律NULL；所有`!`列必须在模板中出现。DEMO标识符不是真实证券/源/运行。

## 1. 现有七表：物理字段与保留决定

Schema账本由`db.initialize`单独创建；v1/v2定义分别见schema.py/reference_schema.py。v1 checksum=`c6d31829bdef4ad9c6f45279c7696cfe94ac6acb9ff016c59320298b8e8dc0bd`；v2=`a4a5c6b2bbf2008d1f452610ecc3213de3dc4fbfe62daa0f55c161e36ef88125`。这是源码/既有证据一致值，不是本次查库。

### E01 schema_migrations（账本，原样保留）

| 字段 | 类型/NULL | 实际语义 |
| --- | --- | --- |
| version | INTEGER PK；SQL未显式NOT NULL，rowid PK行为；CHECK >0 | 连续迁移号 |
| name | TEXT! | 迁移名 |
| checksum | TEXT! | 对(version,name,statements)的SHA256；DDL不验证长度 |
| applied_at | TEXT! | 实际应用时钟，DDL没有四时点格式约束 |

无FK/显式索引；粒度=一次已提交迁移。`Database.initialize()`读写/校验，M1–M4共享启动间接消费；没有行情来源、业务日期或版本修订。账本本身没有immutable触发器，不能误写为七表都受相同触发器保护。P：权限/备份审计保护，不改旧迁移。示意：`{version:1,name:"DEMO_MIGRATION",checksum:H,applied_at:G}`，不是正式账本记录。

### E02 instruments（v1，原样复用）

`instrument_id TEXT! PK`非空；`symbol TEXT!`，六位数字+`.SH/.SZ/.BJ`。U(instrument_id,symbol)，I=`idx_instruments_symbol(symbol)`，无FK。粒度=一个不可变上市身份锚点与唯一绑定代码，不以symbol全局唯一排除历史代码复用；UPDATE/DELETE均触发拒绝。

`SQLiteMarketDataRepository.write_many`及`SQLiteSecurityMaster._insert`建立/检查锚点；行情join、master resolve消费，M1/M2/M4及M3股票分支可达。无source/时点，不能单凭该行认证历史身份；不支持同一id改代码。P：新catalog只桥接，禁止为指数伪造此行。示意：`{instrument_id:"listing:DEMO:A",symbol:"999999.SH"}`（非真实证券）。

### E03 ingestion_runs（v1，保留并旁挂attempt）

`run_id TEXT! PK`非空；`recorded_at TEXT!`为事务记录时钟，DDL无时间格式CHECK。无FK/显式索引，禁UPDATE/DELETE。粒度=一次成功非空写批次命名空间；run_id重复即报错，不是幂等成功。

行情write_many/reference write_batch写，版本行FK引用；M0直接、其他模块以血缘间接用。失败/空批次回滚不留run；没有源、请求、状态、错误详情。P：新增ingestion_attempts记录失败与成功关联，不重建run表。示意：`{run_id:"DEMO-INGEST",recorded_at:I}`。

### E04 daily_bars（v1，保留）

`bar_id INTEGER PK`（rowid PK，SQL未显式NOT NULL）；`instrument_id TEXT! FK→instruments.instrument_id`；`trade_date DATE!`合法日期CHECK；`adjustment_method TEXT!`枚举none/qfq/hfq。U(instrument_id,trade_date,adjustment_method)，I=`idx_bars_date(trade_date,instrument_id)`，禁UPDATE/DELETE。

粒度=实体×日×复权口径，来源在版本表；write_many插入/查找business键，get_bar/read_bars join查询。M1/M2/M4及M3股票支路；不是指数表、不是OHLC数据本身。无source/available/ingested；由版本取得。示意：`{bar_id:1,instrument_id:"listing:DEMO:A",trade_date:"2026-10-16",adjustment_method:"none"}`。

### E05 daily_bar_versions（v1，保留，新增目录链接）

| 字段 | 类型/NULL | 约束/意义 |
| --- | --- | --- |
| version_id | INTEGER PK，rowid | 物理版本，不可跨库直接当全局ID |
| bar_id | INTEGER! FK→daily_bars | 业务对象 |
| source, source_version | TEXT! | source非空且匹配`*:*:*`；version非空 |
| open, high, low, close | REAL! | SQLite real/integer，正且有限上界，low≤O/C≤high |
| volume | INTEGER! | int64非负，单位股 |
| amount | REAL! | real/integer，非负有限，单位CNY |
| event_time, available_at, ingested_at | TS! | 固定格式；event≤available且event≤ingested |
| factor_version | TEXT? | 非空或NULL；none必须NULL，qfq/hfq必须有值 |
| quality_status | TEXT! | accepted/quarantined，仅结构质量 |
| supersedes_version | TEXT? | 前驱source_version，不能指向自己 |
| run_id | TEXT! FK→ingestion_runs | 成功写入批次 |

U(bar_id,source,source_version)、U(bar_id,source,supersedes_version)，复合自FK(bar_id,source,supersedes_version)→同表(bar_id,source,source_version)。部分唯一`idx_one_version_root(bar_id,source) WHERE supersedes_version IS NULL`；`idx_bar_visibility(bar_id,source,available_at,ingested_at)`、`idx_version_run(run_id)`。validate_bar_version要求复权键一致、修订available/ingested不倒退且二者max严格前进；禁UPDATE/DELETE。

write_many原子写；get_bar明确source/日期/口径，available与ingested≤as_of，按max二时点DESC LIMIT1；最新可见quarantine阻断严格模式，不复活旧accepted。返回run/version血缘，research可带quarantine告警。M0写、M1/M2/M4读、M3仅股票分支可达；没有observed_at/原始evidence_ref列。P：legacy链接保留缺失，不从ingested填observed。示意：`{version_id:1,bar_id:1,source:"synthetic:DEMO:v1",source_version:"DEMO-1",open:10,high:11,low:9,close:10,volume:100,amount:1000,event_time:T,available_at:A,ingested_at:I,quality_status:"accepted",run_id:"DEMO-INGEST"}`。

### E06 security_versions（v2，保留）

| 字段 | 类型/NULL | 语义/约束 |
| --- | --- | --- |
| version_id | INTEGER PK，rowid | 物理版本 |
| instrument_id, symbol | TEXT! | 联合FK→instruments(instrument_id,symbol) |
| exchange | TEXT! | SH/SZ/BJ且代码后缀一致 |
| security_type | TEXT! | 仅A_SHARE |
| quality_status | TEXT! | 仅accepted，不代表来源认证 |
| listing_date, delisting_date | DATE! / DATE? | 合法日期，上市<退市，生命周期半开 |
| periods_json | JSON! | 1..256有序不重叠名称段；每段恰有effective_from/name/effective_to；名称非空1..256，边界不越生命周期；允许缺口 |
| event_time, available_at, observed_at, ingested_at | TS! | event≤available、event≤observed≤ingested |
| source, record_version | TEXT! | 来源三段形式、版本非空 |
| evidence_kind, evidence_ref | TEXT! | synthetic/source_observation；引用非空，不是自动真实性认证 |
| supersedes_version, revision_reason | TEXT? | 根二者NULL；非根前驱及非空原因 |
| run_id | TEXT! FK→ingestion_runs | 批次 |

U(instrument_id,record_version)、U(instrument_id,supersedes_version)，复合自FK→(instrument_id,record_version)；`security_versions_root`部分唯一(instrument_id)，`security_versions_visibility`(instrument_id,available_at,ingested_at)、`security_versions_run`(run_id)、`security_symbol_lifetime`(symbol,listing_date,delisting_date)。revision触发器时点单调且max严格推进；security_periods校验上述JSON；security_code_lifetime拒绝双时态冲突代码复用；禁UPDATE/DELETE。

SQLiteSecurityMaster.write_many→write_batch整条时间线追加；get/resolve双时点取最新后验证valid_on与名称区间，歧义/缺失失败。M4使用历史身份/名称；M3目前不读取该表。ST/risk_status始终未知，不能从名称反推。示意：`{version_id:1,instrument_id:"listing:DEMO:A",symbol:"999999.SH",exchange:"SH",security_type:"A_SHARE",quality_status:"accepted",listing_date:"2020-01-01",periods_json:[{effective_from:"2020-01-01",effective_to:null,name:"示意证券"}],event_time:T,available_at:A,observed_at:O,ingested_at:I,source:"synthetic:DEMO:v1",record_version:"DEMO-S1",evidence_kind:"synthetic",evidence_ref:"DEMO-EVIDENCE",run_id:"DEMO-INGEST"}`。JSON列实际存文本。

### E07 calendar_versions（v2，保留，不能塞CFFEX）

`version_id INTEGER PK`；`exchange TEXT!`仅SH/SZ/BJ；`session_date DATE!`；`is_trading_day INTEGER?`；`quality_status TEXT!` accepted/source_error；`error_reason TEXT?`。另含与E06完全相同且同NULL性的11个meta字段：event_time/available_at/observed_at/ingested_at、source/record_version/evidence_kind/evidence_ref、supersedes_version/revision_reason、run_id。accepted→is_trading_day∈0/1且error_reason=NULL；source_error→is_trading_day=NULL且原因非空。

U(exchange,session_date,record_version)、U(exchange,session_date,supersedes_version)，相应三列复合自FK；run_id FK。`calendar_versions_root`部分唯一(exchange,session_date)，visibility(exchange,session_date,available_at,ingested_at)，run(run_id)；revision单调和immutable两触发器。粒度=单市场日的来源版本；日历event是公告事件，不是未来交易日收盘。

SQLiteTradingCalendar.write_many；get_day/trading_days/previous_known_trading_day按双时点、逐日版本读；research保留missing/errors告警，严格范围缺项拒绝，未知不当休市。M0端口/测试存在，M3/M4页面没有调用。示意：`{version_id:1,exchange:"SH",session_date:"2026-10-16",is_trading_day:1,quality_status:"accepted",event_time:T,available_at:A,observed_at:O,ingested_at:I,source:"synthetic:DEMO:v1",record_version:"DEMO-C1",evidence_kind:"synthetic",evidence_ref:"DEMO-EVIDENCE",run_id:"DEMO-INGEST"}`。

## 2. 基础层候选表（B01—B16，全部PROPOSED）

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

### B12 corporate_action_versions

字段：`data_version_id TEXT! PK FK→B04; instrument_id TEXT! FK→instruments; action_key TEXT!; action_type TEXT!; announcement_date DATE?; ex_date DATE?; cash_per_share REAL?; shares_ratio REAL?; currency TEXT!; details_json JSON!`。
粒度=一个公司行动事件修订，business_key含instrument/action_key；I(instrument_id,ex_date)。action_type/currency有版本字典，金额/比例字段按行动种类检查，公告日不能替代具体发布时间，未知公告/可用时间阻断严格回放。
未来公告适配→CorporateActionRepository→复权/M5；目前无真实源，不实施。示意：`{data_version_id:"DEMO-ACTION-DV",instrument_id:"listing:DEMO:A",action_key:"DEMO-ACTION",action_type:"CASH_DIVIDEND",currency:"CNY",details_json:{status:"SYNTHETIC_UNKNOWN"}}`。

### B13 adjustment_factor_versions

字段：`data_version_id TEXT! PK FK→B04; instrument_id TEXT! FK→instruments; factor_date DATE!; method TEXT!; factor REAL!; basis_date DATE!; action_version_id TEXT? FK→B12.data_version_id; definition_version TEXT!`。
粒度=实体/日期/前后复权/基准日/来源版本，method=qfq/hfq、factor正有限；I(instrument_id,factor_date,method,basis_date)。不是重算旧价格授权，未来因子不能覆盖历史版本；action未知保留NULL并阻断需要完整公司行动的执行回放。
未来复权适配→AdjustmentFactorRepository→特征/M5；不修改v1 factor_version字符串，后续新写适配须核对同一因子版本引用，不能凭文本相似自动关联。示意：`{data_version_id:"DEMO-FACTOR-DV",instrument_id:"listing:DEMO:A",factor_date:"2026-10-16",method:"qfq",factor:1,basis_date:"2026-10-16",definition_version:"demo-factor-v1"}`。

### B14 universe_versions

字段：`data_version_id TEXT! PK FK→B04; universe_key TEXT!; trade_date DATE!; definition_version TEXT!; eligible_count INTEGER?; member_count INTEGER!; members_sha256 TEXT!`。
粒度=一个历史日/明确市场范围的证券池完整版本；I(universe_key,trade_date)，count≥0；members_hash按B15有序完整集合计算。eligible_count未知仍可保存观察，但不能作为全A覆盖分母；完整成员与历史状态/日历的可见证据齐备才可认证。现有M4最多20股不是CN_A universe。
未来历史池构建→UniverseRepository→宽度/成交额/M4/M5。示意：`{data_version_id:"DEMO-UNIVERSE-DV",universe_key:"DEMO_A",trade_date:"2026-10-16",definition_version:"demo-universe-v1",member_count:1,members_sha256:H}`。

### B15 universe_members

字段：`universe_version_id TEXT! FK→B14.data_version_id; instrument_id TEXT! FK→instruments; membership_status TEXT!; security_version_id INTEGER? FK→security_versions; state_version_id TEXT? FK→B09.data_version_id; inclusion_reason TEXT!`。
PK(universe_version_id,instrument_id)，I(instrument_id,universe_version_id)。粒度=某池版本一个成员；status=ELIGIBLE/EXCLUDED/UNKNOWN，与历史身份/状态引用一致，缺证据不得ELIGIBLE。父行和全部成员同事务，封存不可追加。
UniverseRepository生产/查询→M3分母/M4；membership业务日与父一致、系统时点继承父B04且被引用版本必须已可见。示意：`{universe_version_id:"DEMO-UNIVERSE-DV",instrument_id:"listing:DEMO:A",membership_status:"UNKNOWN",inclusion_reason:"NO_HISTORICAL_STATUS"}`。

### B16 instrument_alias_versions（P2受限映射）

字段：`data_version_id TEXT! PK FK→B04; catalog_id TEXT! FK→B08; scheme TEXT!; code TEXT!; venue TEXT!; effective_from DATE!; effective_to DATE?`。
粒度=代码体系内一个实体别名有效段版本；I(scheme,code,effective_from,effective_to)，源内可见有效段不得歧义。指数/行业/期货标识不伪装A股代码。EQUITY改代码只能读映射，**现有DailyBar写端仍不支持同id改symbol**；批准新的身份/行情适配前必须拒绝这类写入，不另造上市id规避。
历史身份审核→AliasRepository→新版本解析器；现有三个Repository不自动切换。示意：`{data_version_id:"DEMO-ALIAS-DV",catalog_id:"DEMO-INDEX",scheme:"DEMO_PROVIDER",code:"DEMO_INDEX",venue:"DEMO",effective_from:"2026-10-16"}`。

## 3. 市场研究层候选表（R01—R06，全部PROPOSED）

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

### R05 sector_versions

字段：`data_version_id TEXT! PK FK→B04; catalog_id TEXT! FK→B08; taxonomy TEXT!; sector_code TEXT!; name TEXT!; effective_from DATE!; effective_to DATE?`。
粒度=分类体系/板块定义有效段版本；catalog必须SECTOR，I(taxonomy,sector_code,effective_from)。半开区间、体系不可混合，名称修改新版本，源/授权未知不当正式行业分类。
未来分类源→SectorRepository→M3行业/M4；目前无历史源/存储。示意：`{data_version_id:"DEMO-SECTOR-DV",catalog_id:"DEMO-SECTOR",taxonomy:"DEMO",sector_code:"D1",name:"示意行业",effective_from:"2026-10-16"}`。

### R06 sector_members

字段：`data_version_id TEXT! PK FK→B04; sector_version_id TEXT! FK→R05.data_version_id; instrument_id TEXT! FK→instruments; effective_from DATE!; effective_to DATE?; membership_status TEXT!`。
粒度=板块/上市实体有效成员段的来源版本；business_key含sector/instrument/effective_from；I(sector_version_id,instrument_id,effective_from,effective_to)。有效段必须与可见sector定义相容，status=IN/OUT/UNKNOWN；不能把当前IN填至历史。删除成员通过新的有效期/修订记录，不DELETE。
历史成分源→SectorRepository→M3/M4/M5。示意：`{data_version_id:"DEMO-SECTOR-MEMBER-DV",sector_version_id:"DEMO-SECTOR-DV",instrument_id:"listing:DEMO:A",effective_from:"2026-10-16",membership_status:"UNKNOWN"}`。

## 4. 分析结果与发布候选表（A01—A17，全部PROPOSED）

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

### A05 m2_snapshots

字段：`analysis_run_id TEXT! PK FK→A03; instrument_id TEXT! FK→instruments; latest_trade_date DATE?; row_count INTEGER!; price_basis TEXT!; technical_score REAL?; summary_json JSON!; risk_json JSON!; indicator_artifact_id TEXT? FK→B02`。
粒度=一次M2单股结果，module必须M2；I(instrument_id,latest_trade_date)。summary_json保持m2-research-v1字段：symbol/source/analysis_date/as_of/latest_trade_date/count/conditions/score/exclusions/signal_available_at及解释；risk_json保留两止损/最终值/依据/权益预算/股数的原输出，不篡改算法。指标frame可存私有artifact，必须hash并可从输入重算；NaN→null是序列化而非填0。
现有analyze的未来保存适配→M2ResultRepository→M4/详情/审计。示意：`{analysis_run_id:"DEMO-M2",instrument_id:"listing:DEMO:A",row_count:0,price_basis:"none",summary_json:{status:"SYNTHETIC_BLOCKED",score:null,conditions:{},exclusions:["NO_DATA"]},risk_json:{structure_stop:null,atr_stop:null,theoretical_shares:null}}`。

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

### A08 m4_evaluations

字段：`analysis_run_id TEXT! FK→A03; requested_symbol TEXT!; instrument_id TEXT? FK→instruments; m2_run_id TEXT? FK→A05.analysis_run_id; name_at_date TEXT?; research_score REAL?; rank INTEGER?; research_match BOOL?; eligible BOOL!; phase TEXT?; evaluation_json JSON!`。
PK(analysis_run_id,requested_symbol)，部分U(analysis_run_id,rank) WHERE rank IS NOT NULL，I(instrument_id,analysis_run_id)。粒度=每个被请求/扫描股票的结果，**含排除/查询失败股票**。排名仅合格候选、1..5且按后端排序；未选中rank=NULL。phase未有M2正式状态机保持NULL，不由UI猜S0–S6。evaluation_json必含满足/未满足/排除/数据完整性/模式/market_gate_ref/风险理由及最新日期；市场依赖通过A04，缺失必须eligible=0。
现有CandidateBatch适配→CandidateRepository→列表/详情/风险共用同run，不重算混用。requested_symbol允许失败输入保留，身份未知不能编造FK。示意：`{analysis_run_id:"DEMO-M4",requested_symbol:"999999.SH",eligible:0,evaluation_json:{exclusions:["IDENTITY_UNKNOWN"],market_gate_ref:null,data_status:"UNKNOWN",phase:null}}`。

### A09 trade_plans

字段：`plan_id TEXT! PK; analysis_run_id TEXT!; requested_symbol TEXT!; reference_entry REAL?; entry_condition TEXT!; structure_stop REAL?; atr_stop REAL?; final_stop REAL?; stop_reason TEXT!; price_unit TEXT!; risk_fraction REAL!; equity_minor INTEGER?; risk_budget_minor INTEGER?; quantity INTEGER?; lot_size INTEGER?; earliest_session_date DATE?; valid_until TS?; entry_allowed BOOL!; constraints_json JSON!`。
U(analysis_run_id,requested_symbol)，复合FK→A08；I(entry_allowed,earliest_session_date)。粒度=一个已评估股票的一份不可变研究计划，修改新run/plan。risk_fraction>0且≤0.01，权益/预算使用CNY分；预算向下取整不得超权益×风险比例，禁止未配置权益时填金额。研究价格单位CNY/share、双止损分别保留；final依据复用M2，不新增选择算法。quantity/lot必须同时已知且正、整手、资金与风险均满足；现有M4未验证可执行性，quantity与lot_size继续NULL，entry_allowed=0。
Risk/候选保存适配→TradePlanRepository→研究风险展示/M5计划参考，绝非订单。constraints_json显式列T+1/停牌/涨跌停/跳空/费用滑点/市场闸门的已知或未知及证据引用。示意：`{plan_id:"DEMO-PLAN",analysis_run_id:"DEMO-M4",requested_symbol:"999999.SH",entry_condition:"下一认证会话重新评估",stop_reason:"NO_VALID_STOPS",price_unit:"CNY/share",risk_fraction:0.01,entry_allowed:0,constraints_json:{market:"BLOCKED",execution:"UNKNOWN"}}`。

### A10 m5_runs

字段：`analysis_run_id TEXT! PK FK→A03; strategy_version TEXT!; start_date DATE!; end_date DATE!; initial_equity_minor INTEGER!; currency TEXT!; price_scale INTEGER!; cost_model_json JSON!; execution_policy_version TEXT!; experiment_split_json JSON!; benchmark_json JSON!; audit_status TEXT!`。
粒度=一次M5实验运行，module=M5；I(strategy_version,start_date,end_date)。initial>0、scale=10000表示价格万分之一元；成本版本/滑点/税费/撮合/持仓与可交易性政策必须具名，未知阻断，不补默认成功。split显式训练/验证/样本外日期，禁止事后混算。
未来回测编排→BacktestRepository→审计/发布，当前引擎缺失。示意：`{analysis_run_id:"DEMO-M5",strategy_version:"DEMO-NOT-IMPLEMENTED",start_date:"2026-10-16",end_date:"2026-10-16",initial_equity_minor:10000000,currency:"CNY",price_scale:10000,cost_model_json:{status:"UNKNOWN"},execution_policy_version:"DEMO-BLOCKED",experiment_split_json:{out_of_sample:null},benchmark_json:{status:"UNKNOWN"},audit_status:"BLOCKED"}`。

### A11 m5_trades

字段：`trade_id TEXT! PK; analysis_run_id TEXT! FK→A10; instrument_id TEXT! FK→instruments; event_sequence INTEGER!; order_ref TEXT!; signal_run_id TEXT? FK→A03; signal_at TS!; earliest_session_date DATE!; execution_at TS?; execution_snapshot_id TEXT? FK→A01; side TEXT!; order_status TEXT!; requested_quantity INTEGER!; filled_quantity INTEGER!; fill_price_scaled INTEGER?; commission_minor INTEGER?; tax_minor INTEGER?; slippage_minor INTEGER?; cash_after_minor INTEGER?; position_after INTEGER?; rejection_reason TEXT?`。
粒度=一次订单生命周期终态/成交事件，不伪造未成交fill；U(analysis_run_id,event_sequence)，I(analysis_run_id,instrument_id,execution_at)。side=BUY/SELL；status=FILLED/PARTIAL/REJECTED/CANCELLED；非负数量、filled≤requested；FILLED/成交部分必须有时点/真实对应回放价格/输入/费用，拒绝时fill及现金变动留NULL、filled=0。信号可用/下一认证会话/T+1/价格限制由固定执行器验证；跨会话不能按当前快照撮合。position_after/现金用于重放对账，不能从收益指标倒造。
未来执行回放→BacktestRepository→绩效/审计；不是真实账户。示意：`{trade_id:"DEMO-TRADE",analysis_run_id:"DEMO-M5",instrument_id:"listing:DEMO:A",event_sequence:0,order_ref:"DEMO-ORDER",signal_at:G,earliest_session_date:"2026-10-19",side:"BUY",order_status:"REJECTED",requested_quantity:100,filled_quantity:0,rejection_reason:"SYNTHETIC_NO_EXECUTION_EVIDENCE"}`。

### A12 m5_metrics

字段：`analysis_run_id TEXT! FK→A10; metric_key TEXT!; sample_split TEXT!; value REAL?; unit TEXT!; formula_version TEXT!; quality_status TEXT!; reasons_json JSON!`。
PK(analysis_run_id,metric_key,sample_split)，I(metric_key,sample_split)。粒度=同run/训练验证样本外的一项指标；sample_split固定字典，收益/回撤/胜率/成本不能跨split拼；指标只能从已封存现金/持仓/成交事件及有版本基准重算，分母0/未成交不可算则NULL附原因。不保存虚构收益作为正式回测。
未来统计器→BacktestRepository→M5/发布。示意：`{analysis_run_id:"DEMO-M5",metric_key:"total_return",sample_split:"out_of_sample",unit:"ratio",formula_version:"DEMO-v1",quality_status:"UNKNOWN",reasons_json:["NO_EXECUTIONS"]}`。

### A13 publication_batches

字段：`publication_id TEXT! PK; manifest_sha256 TEXT!; protocol_version TEXT!; analysis_date DATE!; as_of TS!; generated_at TS!; producer_code_sha TEXT!; renderer_contract TEXT!; target_key TEXT!; item_count INTEGER!; total_bytes INTEGER!; admission_summary_json JSON!; privacy_policy_version TEXT!`。
粒度=一份已封存、允许发送的结果包；U(target_key,manifest_sha256)，I(target_key,analysis_date,as_of)。ID为manifest规范摘要，大小/数目限额见发布契约；target只是允许的部署别名，无IP凭据/secret。只存结果和输入版本摘要，不存全库、原始行情、原始CSV或账户明文；对外展示许可未知则阻断数据值、最多发布获准的BLOCKED状态摘要。
本地发布构建→PublicationRepository→传输/EC2验证，时间是产物生成而非历史首次可得。示意：`{publication_id:"DEMO-PUB",manifest_sha256:H,protocol_version:"research-publication-v1",analysis_date:"2026-10-16",as_of:C,generated_at:G,producer_code_sha:S,renderer_contract:"DEMO-render-v1",target_key:"DEMO-PRIVATE",item_count:1,total_bytes:2,admission_summary_json:{strategy_allowed:false,live_trading:false},privacy_policy_version:"demo-private-v1"}`。

### A14 publication_items

字段：`publication_id TEXT! FK→A13; relative_path TEXT!; sha256 TEXT!; byte_size INTEGER!; media_type TEXT!; analysis_run_id TEXT? FK→A03; artifact_role TEXT!`。
PK(publication_id,relative_path)，I(analysis_run_id,publication_id)。粒度=包中一个文件；安全路径/后缀/字节限额/无多余文件；角色=result_json/index_html/style/receipt_summary；result_json必须绑定run及其result_sha，非结果资源可NULL。父manifest含完整项目有序清单，封存后不可加文件。
Publisher→PublicationRepository→云端校验/只读渲染。示意：`{publication_id:"DEMO-PUB",relative_path:"results/DEMO-M3.json",sha256:H,byte_size:2,media_type:"application/json",analysis_run_id:"DEMO-M3",artifact_role:"result_json"}`，2字节仅示意，不是合法结果包。

### A15 publication_events

字段：`event_id TEXT! PK; publication_id TEXT! FK→A13; event_sequence INTEGER!; phase TEXT!; recorded_at TS!; target_key TEXT!; observed_manifest_sha256 TEXT?; previous_publication_id TEXT? FK→A13; receiver_code_sha TEXT?; error_code TEXT?; verification_json JSON!`。
U(publication_id,event_sequence)，I(target_key,recorded_at)。粒度=发送/校验/激活/失败/回滚的一条回执；phase=BUILT/SENT/VERIFIED/ACTIVATED/FAILED/ROLLED_BACK。状态追加事件，不能UPDATE批次。ACTIVATED必须由允许目标的VERIFIED回执和实际current指针核对支持，失败不覆盖旧current；代码部署SHA和数据publication_id分别存，不混为一谈。
发送方/受认证接收方→PublicationRepository→本地运维/云端版本标签。示意：`{event_id:"DEMO-PUB-E1",publication_id:"DEMO-PUB",event_sequence:0,phase:"FAILED",recorded_at:G,target_key:"DEMO-PRIVATE",error_code:"NO_APPROVED_RENDERER",verification_json:{synthetic:true}}`。

### A16 m5_account_events

字段：`account_event_id TEXT! PK; analysis_run_id TEXT! FK→A10; event_sequence INTEGER!; event_kind TEXT!; event_at TS!; instrument_id TEXT? FK→instruments; trade_id TEXT? FK→A11.trade_id; action_version_id TEXT? FK→B12.data_version_id; input_snapshot_id TEXT! FK→A01; cash_delta_minor INTEGER!; quantity_delta INTEGER!; cash_after_minor INTEGER!; position_after INTEGER?; equity_minor INTEGER?; reasons_json JSON!`。
粒度=一次回放账户记账/估值事件；U(analysis_run_id,event_sequence)，I(analysis_run_id,event_at)。kind=FUNDING/FILL/DIVIDEND/SPLIT/VALUATION，按(kind,trade_id/action_id)验证所需FK及同run；FILL现金变动已含对应交易税费，不另重复扣费。FUNDING不伪造证券；DIVIDEND/SPLIT必须有当时可用公司行动；估值引用精确价格快照，缺价不能填0。事件按序重放与trade的cash_after/position_after一致；权益/指标只能从这条账链和可见价格重建。
未来账户账本→BacktestRepository→M5指标/审计，非实盘资金。示意：`{account_event_id:"DEMO-ACCOUNT-E1",analysis_run_id:"DEMO-M5",event_sequence:0,event_kind:"FUNDING",event_at:G,input_snapshot_id:"DEMO-SNAPSHOT",cash_delta_minor:10000000,quantity_delta:0,cash_after_minor:10000000,reasons_json:["SYNTHETIC_INITIAL_FUNDING"]}`。

### A17 input_snapshot_checks

字段：`snapshot_id TEXT! FK→A01; check_role TEXT!; ordinal INTEGER!; assessment_id TEXT? FK→B06; receipt_id TEXT? FK→B07; expected_sha256 TEXT!`。
PK(snapshot_id,check_role,ordinal)，U(snapshot_id,check_role,assessment_id)，U(snapshot_id,check_role,receipt_id)，I(assessment_id)、I(receipt_id)。粒度=快照所采用的一项质量决定或源/时间/许可/审核收据；恰一目标非NULL，role与目标类型/范围吻合，ordinal非负连续。严格可用快照只引用截止前可见的具体决定，封存后不能换“最新收据”；质量/收据缺失以快照blocking_reasons保留，不造PASS记录。A01的计数/哈希包含该集合。
SnapshotRepository保存/验证→M3/M4/M5/重放；示意：`{snapshot_id:"DEMO-SNAPSHOT",check_role:"source_authorization",ordinal:0,receipt_id:"DEMO-RECEIPT",expected_sha256:H}`，示意UNVERIFIED收据不能解除BLOCKED。

## 5. 嵌套JSON契约与未实现边界

JSON不是自由扩展逃生口：实施时对parameters/receipt claims/diagnostic/evaluation/constraints/cost/split/manifest各冻结独立schema_version，禁止额外秘密字段，新增字段走版本。M3复用已有JSON Schema与完整to_dict；其示例模板不能作为合法入库夹具。M2原summary/risk和M4原Evaluation必须保留已知/未知/失败区别，不能持久化时修复分数或算法。

本设计覆盖了39张候选表（B16、R6、A17）；这是分阶段物理模型，不是要求一次建齐。基础源/时间字段经B04引用，结果时间经A03引用，子项业务日期通过父行或显式DATE继承，不能把注册时间补成市场时间。所有示意跨行引用仅为模型说明；真正提交必须展开模板、验证FK/哈希/完整schema和信任门槛。没有一条示意记录获准进入正式分析。

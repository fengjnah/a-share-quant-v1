# M3 持久化结构缺口与后续迁移提案

TASK-M0-PRODUCTION-DB-001；**设计草案，未创建这些表、未发布新 Schema、未认证来源**。
依据 main `c4b682d12c7c8dc42f75e717b855238f635ce05b` 的 [数据契约](DATA_CONTRACT.md)、[接口契约](INTERFACE_CONTRACT.md)、[核心契约](M3_CORE_CONTRACT.md) 和 [真实来源验收](M3_CORE_SOURCE_ACCEPTANCE.md)。七表 v2 只覆盖 A 股日线身份锚点/批次/版本及日期级主数据/日历；不能表示下列整个领域。当前 M3 指数/宽度/CFFEX 观察文件仅供 L1 诊断，不是相应正式仓储。

## 建议数据集

以下名称和字段是后续 H 设计输入，不能作为已实现 API 使用。金额 CNY、比例的分子/分母、手/股及持仓统计口径必须逐字段有来源证据。

| 数据集候选 | 逻辑键 / 版本键 | 核心字段与约束 | 关联证据及用途 |
| --- | --- | --- | --- |
| source_evidence_versions | provider, endpoint, scope / record_version | adapter_version、payload_sha256、evidence_ref、license_ref、allowed_purposes、issuer、issued_at、quality_decision_ref；许可缺失 UNKNOWN | 来源真实性、个人研究/本地存储/自动采集/展示/再分发分别验收；不从 SDK 许可证推导行情授权 |
| market_universe_versions | universe_id, session_date / record_version | universe_definition_version、历史有效成员引用、eligible_count、身份/日历快照、上市/退市/ST/停牌及未知分区 | ALL_A 股票池分母必须有历史实体证据；不能使用当前列表倒填 |
| market_breadth_versions | scope=ALL_A, session_date, statistic_definition / record_version | advances/declines/flat/limit_up/limit_down、eligible_count、suspended/unavailable/missing、universe_snapshot_ref/date/available_at/ingested_at、market_amount_cny；有限、非负、整数家数；零保留 | 消费核心原字段：eligible=advances+declines+flat+suspended+unavailable+missing，覆盖分子为涨跌平+停牌；涨跌停不重复加入分区，UNKNOWN不能计零；成交额不能用指数/单股替代 |
| sentiment_factor_versions | scope, session_date, factor_id, definitions_version / record_version | trend/5条动量/20条收益波动/上涨比例/涨跌停比例/全A额比；raw_value、unit、numerator、denominator、input_snapshot_refs、computed_at | 价格3因子与全市场3因子独立；固定公式/窗口/权重消费现有核心，不另写准入算法；任一缺失完整 score=null |
| sentiment_diagnostic_versions（可选派生缓存） | request_hash, definitions_version, inputs_hash / record_version | 核心 m3-core-diagnostic-v1 白名单结果、完整输入引用、计算版本、as_of、模式；可删除缓存但不可改事实 | 价格代理与完整六因子分开；缓存不替代事实及收据，任何证据变化重算 |
| index_bar_versions | index_id, session_date, price_definition / record_version | OHLC、可选成交额/量及单位、指数编制/复权定义、源记录身份 | 指数不是 A 股上市实体，不放入 instruments/daily_bars 伪造证券身份 |
| futures_contract_versions | exchange, contract, effective_from / record_version | variety、到期月、乘数/单位、生效区间、合约状态和交易日历引用 | 品种/月份不混，不能从当前主力倒填历史换月 |
| futures_member_versions | exchange, member_id, effective_from / record_version | 会员标识、原始名称、有效期、别名证据 | 不根据相似名称合并会员；会员不是最终机构身份 |
| futures_ranking_versions | exchange, contract, member_id, session_date, rank_type, account_scope, statistic_at / record_version | rank、position_lots、change_lots、rank_population、top_n、publication_at、contract/member/calendar refs | volume/long/short 区分；self/client/combined/UNKNOWN 分开；榜外未知不是0；涨减值可负而持仓非负；不输出“真实机构净仓” |
| security_status_versions | instrument_id, effective_from, status_type / record_version | ST/停牌/退市/可交易状态、effective_to、公告证据、来源与错误状态 | v2 security_versions 已有身份/上市退市/名称版本，优先复用；新增状态不能篡改该历史或从名称推 ST |

## 所有事实共有的版本与时间字段

- 不可变 version_id、source、source_record_id、record_version、run_id、payload_hash、supersedes_version、revision_reason。复用 ingestion_runs；批次不能跨不相关操作复用。逻辑键之下单根/单后继，跨源修订必须明示前驱和理由，冲突拒绝而非自动取优。
- 分别保留 event_time、source_published_at、available_at、observed_at、ingested_at；缺证据为 NULL/UNKNOWN，不把本次采集时刻写作历史首次可得。统一 UTC；业务日期和交易所 Asia/Shanghai 日界单独保存。
- 查询同时限制 available_at 与 ingested_at <= as_of；仅接受明确逐记录质量决定。UNKNOWN/quarantined/rejected/source_error 分开，不经 Receipt 覆盖原始质量。L1 可保留有告警的观察；严格回测/模拟按现有核心阻断。
- 事实/统计口径与计算版本分离。quality_status、quality_reasons、quality_rule_version、decision_ref 可追溯；来源/授权/时间认证三个 Receipt 独立引用真实审查材料，不能由数据库成功插入自动升为 VERIFIED。
- calendar_versions 的 A 股/CFFEX 分开按交易所存，不用工作日或缺记录推休市。期货发布日期、开盘日历、统计时点未确认时综合方向保持阻断。
- CFFEX 严格保留现有 v2 的特殊规则：available_at 仍为实际采集后首个合格后续开盘时点，**不是 source_published_at**；两者独立保存。新表不得自行把发布时间变成准入时间。未知会员 scope、榜外一侧、日历或发布证据继续阻断核心方向。

## 后续迁移与验收顺序

1. 独立 H 确认每个数据集字段、主键/分区、来源许可和核心接口；来源不可用记 BLOCKED。冻结七表 v1/v2 定义/checksum。
2. 取届时 MIGRATIONS 下一个有序版本（本基线下一版为 v3，实施前重查 main，不能预占已被使用的版本）。独立迁移 TASK 添加表/索引/不可变/版本链触发器及严格类型/外键约束，先在隔离库验证升级、失败回滚、重复和漂移拒绝。
3. 仓储按现有 DataAccess/核心 Request/SourceEvidence/Diagnostic 适配；不在页面建立第二套算法/门禁。不把全部来源塞入 daily_bars，不从观察 JSON 自动导入。
4. 新库/旧库升级均须明确操作、备份、恢复验证及独立 H。真实入库另行授权有界请求或历史迁移；验证 as_of 反例、错误状态不回退、历史身份与分母、版本冲突、跨字段一致性和质量拒绝。
5. 真实来源、离线测试、浏览器、样本外分别验收。Schema 或代码通过不解除来源/研究/策略/实盘门禁。

建议后续 TASK（未自动创建）：M0-LEGACY-MIGRATION-REVIEW（旧1217样本证据与策略）、M3-STORAGE-DESIGN（上述契约冻结）、M3-STORAGE-MIGRATION（新有序迁移及仓储）、M3-DATA-CERTIFICATION（独立来源/时间/许可验收）。

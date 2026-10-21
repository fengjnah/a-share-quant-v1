# M0—M5 三层数据持久化架构（待审设计）

TASK-DATA-ARCHITECTURE-001，2026-10-21，**DESIGN / NOT IMPLEMENTED / independent H review pending**。代码基线main `c4b682d12c7c8dc42f75e717b855238f635ce05b`。本轮未连接/创建/初始化/复制SQLite，未采集或部署。正式Windows研究库路径仍UNKNOWN；不因此等待或建立替代库。

## 阅读入口

| 文档 | 负责的问题 |
| --- | --- |
| [关系模型](DATA_MODEL.md) | 三层ER、领域归属、公共引用与六条端到端路径 |
| [完整字段字典](DATA_DICTIONARY.md) | 七表现状；所有拟议表的物理字段、空值、PK/UQ/FK/索引、粒度、示例、生产消费端口 |
| [时间与发布血缘](DATA_LINEAGE.md) | 同一as_of选择、修订/幂等、M3重放、M4门禁、M5回测和EC2发布协议 |
| [迁移方案](DATA_MIGRATION_PLAN.md) | v3–v8建议依赖、原表兼容、备份/失败恢复、测试及旧代码限制 |
| [模块矩阵与路线](M0_M5_PERSISTENCE_MATRIX.md) | 来源实际状态、代码读写/出口、P0–P2任务与并行依赖 |

## 证据分类及固定引用

F=源码确认；E=既有实测证据（不是本轮重测）；P=设计建议；U=未知或未接通。整个字典的新表属于P，不能用P填F的缺口。

| 编号 | 固定证据 | 能证明 / 不能证明 |
| --- | --- | --- |
| F1 | main的[schema.py](../../src/ai_trade/storage/schema.py)、[reference_schema.py](../../src/ai_trade/storage/reference_schema.py)、[db.py](../../src/ai_trade/storage/db.py) | 七表DDL、追加/约束/迁移生命周期；不证明正式数据库路径或真实覆盖 |
| F2 | [行情Repository](../../src/ai_trade/data_access/repository.py)、[证券](../../src/ai_trade/security_master/repository.py)、[日历](../../src/ai_trade/trading_calendar/repository.py) | 有实际读写端口；重复版本拒绝、双时点过滤；不等于所有模块已接入 |
| F3 | [M3文件](../../src/ai_trade/market_analysis_data.py)、[适配](../../src/ai_trade/market_analysis_view.py)、[核心契约](../../src/ai_trade/market_analysis_contract.py)、[管线](../../src/ai_trade/m3_data_pipeline.py)、[显式脚本](../../scripts/verify_m3_pipeline.py) | 输入JSON保存、页面运行时结果、脚本完整bundle出口三者不同；baseline常量不能证明执行SHA |
| F4 | [M2](../../src/ai_trade/trading_analysis.py)、[M4数据](../../src/ai_trade/daily_candidates_data.py)、[M4页面](../../src/ai_trade/daily_candidates_page.py) | M2/M4计算及会话状态；M4默认MarketState未验证，不是M3结果消费 |
| E1 | [PR46审计报告@b217546](https://github.com/fengjnah/a-share-quant-v1/blob/b21754645741ce16aae126660ad6d4f7fad08283/docs/audits/TASK-M3-READONLY-TRACE-001.md)与同提交evidence.json | 已交付只读调用链/七表/出口证据；PR仍Draft/open，不是main内容/独立H通过 |
| E2 | [PR45路径审计@5ed318f](https://github.com/fengjnah/a-share-quant-v1/blob/5ed318f023194c6f0f9767168957f7b3a1b56fb5/docs/M0_DB_PATH_CONFIRM_REPORT.md) | 当时8524绑定临时Demo库、七表物理结构/五库只读hash；不代表正式归属已批准 |
| E3 | [PR44库存@79266f1](https://github.com/fengjnah/a-share-quant-v1/blob/79266f15a3ce05989955b85aef97feabc9153469/docs/M0_M3_LOCAL_INVENTORY.md) | 当时187/1217/2291股票样本、独立指数文件、未知状态；不是本轮扫描或正式入库 |
| E4 | [已合并管线报告](../M3_DATA_PIPELINE_REPORT.md)、[认证矩阵](../M3_DATA_CERTIFICATION_MATRIX.md)、[部署记录](../tasks/TASK-AWS-DEPLOY-M0-M5-001.md) | 既有受限源验证与当时EC2空库/代码部署事实；现在实时状态仍U |

旧临时样本中，1217行600000.SH覆盖2021-10-08～2026-10-15，187行覆盖2026-01-05～10-15，2291行600378.SH覆盖2016-10-17～2026-10-15。五个重点库security/calendar均0；E4云端当时账本2行、其余0。指数是3个独立版本的550行文件，最新旧样本截至10-19；四个文件位置不能算四份新增历史。以上均E，当前文件或云端是否变化U。本轮不重新开库或扫描磁盘。

## 当前实现的关键结论

1. 七表保留，不改名、不重建，不修改v1/v2 SQL/checksum。`instruments`是A股代码锚点，不能冒充已认证历史实体，更不能塞指数；`security_versions.periods_json`只有历史名称，不含ST/停牌。
2. `DailyHistoryIngestor`先保存输入/响应/结果证据，再经Repository原子写股票事实。`ingestion_runs`只在成功非空事务存在；失败可能只有文件。SDK响应不是原始HTTP载荷，二者必须分别登记。
3. M3输入JSON已持久化；页面Diagnostic没有持久run/generated_at；显式脚本能保存完整pipeline-bundle.json。脱敏下载去掉values，不能当完整重放快照。没有正式M3结果Repository。
4. M4有缓存/session_state，无候选/交易计划正式持久出口，也未读M3快照；M5引擎/页/结果仓储未实现。hash、to_dict、页面有数值不等于保存成功。
5. `AI_TRADE_READ_ONLY=1`仅禁采集按钮；共享页面启动仍`Database.initialize()`，不是物理只读。旧v2代码会拒绝v3以上账本；不能声称“仅新增表，旧版必然兼容”。
6. 已有EC2代码release/current机制不等于本地分析结果发布。本方案通过小型、经验证结果包让EC2展示指定批次，无需复制全库；现有Streamlit不会自动消费新协议，需独立接线任务。

## 采用决定与非目标

P：维持单机SQLite作为事实与结果审计库、私有内容寻址证据文件作为大载荷；新增轻量版本目录桥接旧整数version_id，不重键旧表。结果分为不可变输入清单、分析运行、模块结果、发布回执。市场输入与分析结果是两个领域，不将派生恐贪值写回原始宽度表。

P：写入仍单写者短事务；输入/结果批次在一个事务封存，子项封存后禁止追加。元数据可使用结构化JSON，但可过滤/连接的业务键、日期、单位和门禁字段独立列；不采用任意EAV替代行情或持仓模型。

拒绝：新建独立数据平台、另建平行正式库、重建七表统一命名、全A回补、当前状态回填历史、EC2拷贝数据库/在线全市场计算、引入未经验证回测框架。Parquet/DuckDB仅后续性能选项，不引入本轮依赖。

## 有界调研及限制

复用既有[架构](../ARCHITECTURE.md)/ADR001、数据契约、不可变版本代码与失败测试源码。2026-10-21补读SQLite官方[事务](https://www.sqlite.org/lang_transaction.html)（单写者/读事务快照）、[Online Backup](https://www.sqlite.org/backup.html)（在线一致性备份）、[PRAGMA](https://www.sqlite.org/pragma.html#foreign_key_check)（完整性/外键检查分开）。采用其设计约束，不复制实现；不引入新数据库或框架，未重新做依赖许可证审计。资料是动态官方文档，非冻结上游源码。没有行情端点请求。恢复/迁移仍需在未来隔离验收中证明，本轮没有执行SQL验证。

## 完成与批准边界

设计交付必须同时包含字段字典、关系/血缘、迁移与路线；正式库路径不作为设计阻塞。来源、许可、历史时点、独立核心H和生产门禁仍独立。Draft PR供独立H审查，批准设计不等于批准创建库/迁移/采集/发布。实际无数据库检查结果与Draft状态见[任务记录](../tasks/TASK-DATA-ARCHITECTURE-001.md)。

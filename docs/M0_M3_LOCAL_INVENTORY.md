# Windows 本地 M3 数据储备盘点

TASK-M0-M3-DATA-001；2026-10-21（Asia/Shanghai；精确UTC时刻见机器证据）。代码基线 `c4b682d12c7c8dc42f75e717b855238f635ce05b`。**阶段一盘点完成；正式 Windows 持久库路径 UNKNOWN，受控采集和正式入库 BLOCKED。没有创建替代数据库。**

## 1. 搜索、只读方法与数据库归属

实际扫描 `F:/codex-agnes/AI-trade*` 下数据库和 `m3-observations`，排除 `.git/.venv/node_modules` 与缓存目录；扫描系统 Temp 下 `a-share-quant-demo-*`、`a-share-health-*`、task003/004/008 相关目录，并检查旧 TASK-008 明示的库路径。不是全磁盘扫描，其他位置是否有库保持 UNKNOWN；没有连接 EC2。

- 项目路径发现 1362 个 SQLite 文件，其中 1361 个位于测试/tmp 目录，作为测试产物路径单列，不作为真实库存；另一个是 #40 的 `health.sqlite3` 隔离验收库。
- 对上述隔离库及 Temp 候选共 **613 个库**逐库读取所有表的名称、列、行数、日期/时间区间、来源、质量、批次和迁移；其中 396 个只有1条行情、206个0条，其余依次为1217条×1、187条×1、2291条×1、2条×6、6条×1、4条×1。1行或非空本身不是来源证明，不将这些候选统一认作真实库存。
- 使用原生 URI `mode=ro`、`query_only=ON`、有界只读事务，不调用 `Database.initialize()` 或会设置 journal 的应用连接入口。613 个库及当时存在的 WAL/SHM/journal 前后大小/hash全部相同。
- `QUANT_DB_PATH`、`QUANT_DB_ENV`、`AI_TRADE_DEMO_ROOT`、`AI_TRADE_WORKBENCH_ROOT` 在当前进程、User、Machine 作用域均未设置。原工作区及本任务工作区的默认 `data/sqlite/local.sqlite3` 均不存在；其他已扫描项目也未找到正式 `local.sqlite3/workbench.sqlite3`。
- 检测到本机 Streamlit Python 进程，但本任务无法从其启动命令证明进程继承的数据库根目录；当前运行页面实际所选 root 保持 UNKNOWN，不由历史文档或目录修改时间猜测。

| 存储 | 实际归属与结论 |
| --- | --- |
| 下列 Temp/demo.sqlite3 | 已有开发/研究演示库；存有可核对采集证据，仍位于系统临时目录，不能作为已确认正式持久库 |
| #40 live/tencent_stock/health.sqlite3 | `environment=test` 的临时写入/读回验收，2条，不是正式库 |
| 默认 `data/sqlite/local.sqlite3` | 契约默认配置，不存在，未初始化 |
| Windows 正式研究库 | 路径、负责人、进程绑定、备份/使用授权未确认，UNKNOWN；不能自行指定另一库替代 |
| EC2 `/var/lib/a-share-quant-workbench/workbench.sqlite3` | 云端路径，仅引用既有部署资料；本任务未登录、查询或改动，现有行数 UNKNOWN，不将旧“空库”报告当作今天实测 |

完整逐库/逐表目录在本机忽略文件 `artifacts/m0-m3-data-001/inventory.json`（约5.1MB）；原始价格未写入该文件。关键可提交摘要见 [机器证据](evidence/TASK_M0_M3_DATA_001_INVENTORY.json)，含完整本机清单的SHA256、关键表及来源证据。清单固定于盘点时刻；后续离线测试创建的新测试目录不属于这份历史库存。

## 2. 已核对真实采集证据的重点库存

以下用 `%TEMP%` 表示实际 `C:/Users/iyoyi/AppData/Local/Temp`。主来源均为 `akshare-tencent:akshare.stock_zh_a_hist_tx:task-008-v1+sdk-1.19.1`；价格CNY/股、volume股、amount CNY，不复权。

| ID / SQLite 实际路径 | 标的、行数与日期 | 批次与版本 |
| --- | --- | --- |
| A：`%TEMP%/a-share-quant-demo-m2-q_hbvuaj/demo.sqlite3` | 600000.SH；187条，2026-01-05～2026-10-15 | `m2-tencent-600000-20260101-20261015`；187个逐行source_version；ingested=2026-10-18T14:50:03.413500Z |
| B：`%TEMP%/a-share-quant-demo-5gu28e3m/demo.sqlite3` | 600000.SH；1217条，2021-10-08～2026-10-15 | `demo-fab1a9b6062641248b5d97ce97a9723f`；1217个逐行版本；ingested=2026-10-18T07:51:15.824265Z |
| C：`%TEMP%/a-share-quant-demo-tduod91y/demo.sqlite3` | 600378.SH；2291条，2016-10-17～2026-10-15 | `demo-26c7d533818b49a49f97827cc47e8471`；2291个逐行版本；ingested=2026-10-18T08:48:44.710869Z |
| D：`%TEMP%/task008-real-72un4ppq/real.sqlite3` | 600000.SH；2条，2026-10-14～15 | `task008-ca640f00390844d9904050432405a10c`；旧M0真实验收样本，非正式库 |
| E：`F:/codex-agnes/AI-trade-m3-data-pipeline-001/artifacts/m3-data-pipeline-001/live/pipeline-20261020T153923Z-c55591fd/tencent_stock/health.sqlite3` | 600000.SH；2条，2026-10-14～15 | `pipeline-20261020T153923Z-c55591fd:tencent_stock`；2版本，观察实体标签，不是历史身份认证 |

A/B/C 的 `evidence/request.json/result.json/response.json` 实际读取并核验：result内response hash与文件相符，result全部记录经既有 `validate_bar` 和 `SQLiteMarketDataRepository.get_bar` 精确读回分别 **187/187、1217/1217、2291/2291**；三库迁移版本/名称/checksum与当前代码完全一致，历史事件时刻作为as_of均被拒绝。HTTP状态旧证据为null，保持UNKNOWN。这是今天只读复核既有证据，不是本轮实网重新验收。

A与B重叠187个日期，OHLC、量、额逐字段 **187/187相同**；来源/采集/系统时间和批次仍分别保留，未合库、未去重、未重新下载。B比A覆盖长，并不表示可直接替换身份/来源版本或已认证完整历史。

## 3. 全部表（重点库 A/B/C）

| 实际表名 | A 行数 | B 行数 | C 行数 | 日期、来源与版本解释 |
| --- | ---: | ---: | ---: | --- |
| schema_migrations | 2 | 2 | 2 | v1 daily_bar_foundation、v2 security_master_and_calendar；checksum与代码一致；applied_at逐库见机器证据，不是行情日期 |
| instruments | 1 | 1 | 1 | 代码形式锚点 `cn-equity:*`；没有业务日期/source列，不证明真实上市身份历史 |
| ingestion_runs | 1 | 1 | 1 | 上表批次；recorded_at见机器证据，不是供应商发布时间 |
| daily_bars | 187 | 1217 | 2291 | 日期范围同上；原始不复权主键，无跨源合并 |
| daily_bar_versions | 187 | 1217 | 2291 | 腾讯源，全部结构accepted；逐行row-sha256版本，0修订父节点；完整版本manifest在本机只读日志目录 |
| security_versions | 0 | 0 | 0 | 日期/来源/版本均无；表存在不能认证历史身份、上市/退市或名称有效期 |
| calendar_versions | 0 | 0 | 0 | 日期/交易所/来源/版本均无；没有任何已存开市/休市事实 |

D、E同为7张表：`schema_migrations=2, instruments=1, ingestion_runs=1, daily_bars=2, daily_bar_versions=2, security_versions=0, calendar_versions=0`。其余候选的全部表、真实行数、最早/最新日期和批次也在完整本机清单，未因其为空或只有1行跳过。613个候选的 `security_versions` 和 `calendar_versions` 合计都为0；这不扩大为全电脑不存在历史参考数据的断言。

## 4. 沪深300观察文件与M3库存状态

未发现指数存入现有日线SQLite表：该表身份契约仅接受A股证券，不能为指数冒造上市实体。实际指数是既有内容寻址JSON观察，3个独立版本、4个文件位置，均550行；其中核心样本及其页面副本hash相同，不重复计算覆盖。

| 独立保存版本 | 实际范围 / 时点 | 限制 |
| --- | --- | --- |
| `c5d0dab6…3311`，A同目录的m3-observations | 2024-07-09～2026-10-16；observed=2026-10-18T23:24:26.358544Z | 缺ingested、available、逐行质量、认证日历和发布证据；旧格式原样保留 |
| `c7b55344…a849`，原工作区artifacts/m3-core-001及Temp/m3-remodel-002副本 | 2024-07-09～2026-10-16；observed=2026-10-19T15:54:06.478989Z；ingested=15:54:06.596523Z | available未知；两个文件不是两份新增历史 |
| `d9ff77ca…bfbf7`，#40 live/sina_index/m3-observations | 2024-07-10～2026-10-19；observed/ingested=2026-10-20T15:39:29.005654Z | 新于页面副本，但不在同一root，不自动拼接/同步或默认替换选定版本；available未知 |

所有真实550行文件的内容hash匹配文件名；另外发现的测试观察/故意损坏JSON与合成150行文件均排除真实库存。

以下主状态按“本地储备能否满足M3”判定；新鲜度、正式库及来源认证另列，不把行数充分当作完整或获准。

| M3数据 | 主状态 | 本次实际证据与缺口 |
| --- | --- | --- |
| 指数历史日线 | PARTIAL | 本地3个版本各550行，最新10-19；不在SQLite正式库；截至分析日10-20为旧日期，权威最近交易日/覆盖分母UNKNOWN，无历史available认证 |
| 全A每日上涨/下跌/平盘/涨跌停 | MISSING | 搜索范围无真实宽度观察/持久表/每日历史池；不把测试字段或单证券数据当全A |
| 全A成交额 | MISSING | 个股amount存在，不能充当market_amount_cny；无真实全A历史来源/口径/持久表 |
| 完整恐贪六因子输入 | PARTIAL | 指数价格仅能供部分价格因子；上涨比、涨停比、全A成交额缺失，完整score与分位保持null |
| CFFEX会员持仓 | MISSING | 无真实合格记录；旧源失败不等于0持仓；无已接线持久版本仓储 |
| A股交易日历 | MISSING | 已查613库calendar_versions总计0；旧日历载荷/调研不等于已入库带版本双时间会话 |
| CFFEX交易日历 | MISSING | 日期/开收盘/发布时间证据及仓储均未认证，不复制A股日历 |
| 历史证券身份、上市/退市 | MISSING | instruments有代码锚点；security_versions合计0，不能还原历史实体生命期 |
| 历史ST、停牌 | MISSING | 没有逐日明确状态/有效期/源；不能从名称、缺bar、零成交推断 |
| 个股基础行情（补充） | PARTIAL | A/B/C真实样本可只读回看，均截止10-15；分析日10-20时日期落后，是否最新应有会话UNKNOWN，长期覆盖/调整键/历史身份未认证 |

PRESENT要求有明确范围和相应完整性证据，本轮无数据集达到；STALE可作为已存在样本的核心诊断原因，但无日历时不声称精确漏采交易日数；正式持久库存归属为UNKNOWN。

## 5. SQLite质量与当前M3只读诊断

613库全部 `quick_check=ok`、外键检查0异常；现有行情数值有限/量额非负/OHLC关系/事件与可用和入库先后校验0异常，重复版本键和断链0。A/B/C逐字段读回与hash/迁移核对通过。这里的accepted、quick_check和严格读取只证明相应结构/可见性，**不认证来源、数据许可、历史身份、期望样本分母或L2/L3**。

四个真实指数文件位置以本轮实际as_of、分析日2026-10-20、无宽度/CFFEX/日历/Receipt，调用当前 `market_analysis_view.from_snapshots → diagnostic_bundle → 核心`。结果仅保存状态/日期/原因/许可，不提交价格值；详细机器结果见本机 `readback.json`。完整恐贪不能补全，综合不能获准，严格历史回放和正式研究仍保持阻断。

正常页面源码读取所选root内快照/SQLite，采集只在显式按钮触发；多个快照需选择，不默认最新。新root可能是空临时库；页面初始化仍调用 `Database.initialize()`，因此本次库存审计没有打开页面或经该入口访问原库。正常查看无行情请求，与“所有本地读都不产生SQLite初始化写入”是两个不同断言。真正永久本地库绑定、指数/全A/CFFEX持久化、跨数据集同一as_of选择及本机页面同源验收仍是接入差距，不能称阶段四通过。

## 6. 结论与继续条件

**阶段一已完成；阶段二交付有界草案；阶段三/四BLOCKED。** 请先确认实际Windows正式研究库路径/归属，或明确当前确实尚无正式库；在此之前不新建、复制、初始化或下载来替代盘点。另需取得所选来源对本地存储/自动采集/研究用途的许可证据，并明确缺失数据集的现有存储端口/需审查设计；这些前置均不能用用户知道URL或SDK MIT代替。

后续范围及每源请求预算草案见 [采集计划](M0_M3_COLLECTION_PLAN.md)，实际接口证据与未执行项见 [质量与接入报告](M0_M3_DATA_ACCEPTANCE.md)。不自动合并/部署/同步EC2，不解除核心#37或任何策略、生产门禁。

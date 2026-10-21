# TASK-M0-PRODUCTION-DB-001 交付报告

2026-10-21；执行配置 **gpt-6.1-sol / high**（本任务用户确认），H；无子代理/模型切换。费用未知，预算120分钟。实现与本地初始化/备份/恢复已完成，**Draft 待独立 H；不得据此解除数据、策略或生产门禁**。

## 基线、范围与文件

- 最新 GitHub main 实测 `c4b682d12c7c8dc42f75e717b855238f635ce05b`，开始和提交前 ls-remote 一致；fetch 成功。
- 独立工作区 `C:\Users\iyoyi\.codex\worktrees\m0-production-db-001\AI-trade`，分支 `codex/m0-production-db-001`；实现提交 **`4bcda30a8921c144185e4b7091f45df710b644ec`**。后续报告提交不改变已测试实现；最终 head 以 Draft PR 为准，不递归填写自身 SHA。
- 原目录 `F:\codex-agnes\AI-trade` HEAD `964a24007ab208d7b10e254a4e86548007c69c4f`、未跟踪 .worktrees/、两份 stash、全部旧 worktree 保留。新增正式文件在该原目录已忽略的 data/，没有改原目录 tracked 代码。
- PR44/45 均 Draft/open，base 同上述 main，head 分别 `79266f15a3ce05989955b85aef97feabc9153469` / `5ed318f023194c6f0f9767168957f7b3a1b56fb5`；复用其盘点范围，不依赖未合并实现。
- 实际读取规则/模型/契约/调研范围见[任务单](tasks/TASK-M0-PRODUCTION-DB-001.md)。全局 `C:/Users/iyoyi/.codex/AGENTS.md` 为空；没有额外下级规则。适用 G01–G12。用户明确授权本地新研究库初始化，未授权旧库写入/行情采集/迁移/部署。

改动范围：Database 连接模式；workbench 配置/诊断与创建备份 CLI；demo_app 接线；M2/M3按钮使用实际连接只读配置；固定启动和只读预览脚本；新生命周期/页面测试；指南、M3结构草案及本报告。**schema.py / reference_schema.py 与 main 完全相同，既有测试未修改。** 无新增依赖。

## 正式库与实测绑定

| 项目 | 实际结果 |
| --- | --- |
| 正式研究库 | `F:\codex-agnes\AI-trade\data\sqlite\workbench.sqlite3`；非交易生产库、非 EC2 |
| AI_TRADE_WORKBENCH_ROOT | `F:\codex-agnes\AI-trade\data\sqlite`；实际文件名 workbench.sqlite3 |
| QUANT_DB_PATH | 启动脚本设置为同一绝对文件，冲突配置会拒绝 |
| 归属 | 文件所有者 `DESKTOP-M3HG690\iyoyi`；正式归属来自本任务明确授权与初始化记录，不根据文件名猜测 |
| 创建前 | 正式父目录/文件不存在；正式文件、WAL/SHM/journal、备份、恢复目标均不存在，CLI再次检查并独占创建 |
| 创建后 | 147456字节，SHA256 `48511c2092d0e08c02e9384647e5d51365feb04232248f7b95e0df1b5c998f64`；无WAL/SHM/journal |
| SQLite 实连 | PRAGMA database_list 返回上述绝对路径；local / DELETE / mode=ro / query_only=1；foreign_keys/recursive_triggers 均开启 |
| 运行入口 | `scripts/start_workbench.ps1`；127.0.0.1:8524，监听 PID17620，父Python PID7212；命令指向本任务工作区 demo_app.py |
| 运行代码 | 启动诊断实际 SHA `4bcda30a8921c144185e4b7091f45df710b644ec`、dirty=false；报告后续修改不改变运行实现 |
| 行情 | 0逻辑日线 / 0版本 / 最新交易日 null；不把空库称为数据链路完成 |

普通刷新不会执行 initialize。formal 配置调用链为：

```text
start_workbench.ps1（显式 ROOT/QUANT_DB_PATH/STRICT=1/READ_ONLY=1）
 → workbench_cli diagnose → workbench_config → Database mode=ro
 → inspect_database（实际连接/迁移/物理DDL/完整性）
 → streamlit demo_app.py → get_components（再次校验，无迁移）
 → SQLiteMarketDataRepository / M1
 → analysis_page / M2、market_analysis_page / M3、daily_candidates_page / M4
```

M0 正式写入仍由既有 DailyHistoryIngestor 注入同一 Database/Repository，配置经 DatabaseConfig.from_env/workbench_config 解析；不重复实现数据底座。默认不允许写入；独立授权采集任务需要显式 READ_ONLY=0，使用 mode=rw（必须已存在）且先校验，不能普通打开就迁移。health_service 的 health.sqlite3 保持有意隔离验证用途，不算正式写入，不能用其成功冒充正式入库。本任务未执行任何真实 M0 采集；隔离合成测试验证仓储写入和非空版本备份恢复。

正式入口缺 ROOT、缺文件、配置冲突、v1/未来版本/checksum/物理DDL漂移、损坏或journal不符都停止。连接的 ro/rw URI 不会自动创建空库。ro 的 transaction/initialize 明确拒绝；直接 INSERT 实测被 SQLite 拒绝，非仅禁用按钮。M3读不到同期输入仍 UNKNOWN/BLOCKED，不读取 Temp 样本或推造完整指标。M3其他领域仍是正式根下观察目录接口，尚无认证后的关系型仓储。

用户指定源码树的忽略 data/sqlite 为本任务允许的专用目录，替代旧部署“必须代码目录外”的限制；不修改治理规则。旧 Demo 直接入口供教学/既有测试保留；**日常正式入口为严格脚本**，不会在失败时回退。没有改变全局系统环境或声称所有历史脚本被自动改写。指南见 [LOCAL_WORKBENCH](LOCAL_WORKBENCH.md)。

## 七表、约束与迁移验收

| 表 | 实际行数 | 主要键/用途 |
| --- | ---: | --- |
| schema_migrations | 2 | version PK；版本/名称/checksum/applied_at |
| instruments | 0 | instrument_id PK；instrument_id+symbol唯一身份锚点 |
| ingestion_runs | 0 | run_id PK；采集批次，不自动制造批次 |
| daily_bars | 0 | bar_id PK；instrument_id+trade_date+adjustment_method唯一；身份外键 |
| daily_bar_versions | 0 | version_id PK；源版本唯一、单根/后继；父版本/行情/批次外键 |
| security_versions | 0 | version_id PK；历史身份版本、父链、批次外键 |
| calendar_versions | 0 | version_id PK；exchange+session_date版本链、批次外键 |

实际36个显式DDL对象（7表+12索引+17触发器），另有10个自动唯一索引。SQL、table_info、index_list（含unique）、foreign_key_list完整清单在[机器证据](evidence/TASK_M0_PRODUCTION_DB_001.json)。物理DDL与由发布迁移直接生成的参考逐项比较，不仅检查ledger。

显式索引：calendar_versions_root/run/visibility；idx_bar_visibility、idx_bars_date、idx_instruments_symbol、idx_one_version_root、idx_version_run；security_symbol_lifetime、security_versions_root/run/visibility。

触发器：calendar_versions_revision、security_versions_revision、security_code_lifetime、security_periods、validate_bar_version，以及 instruments/ingestion_runs/daily_bars/daily_bar_versions/security_versions/calendar_versions 各自 immutable_*_update/delete 共12个。外键、唯一/单根约束和检查均保留 v2 定义。

| 迁移 | 名称 | 实际 checksum |
| --- | --- | --- |
| v1 | daily_bar_foundation | `c6d31829bdef4ad9c6f45279c7696cfe94ac6acb9ff016c59320298b8e8dc0bd` |
| v2 | security_master_and_calendar | `a4a5c6b2bbf2008d1f452610ecc3213de3dc4fbfe62daa0f55c161e36ef88125` |

applied_at 分别为 2026-10-21T14:43:53.601589Z / 14:43:53.603654Z。quick_check=[ok]、foreign_key_check=[]。明确初始化操作内再次执行迁移，ledger/DDL/行数等结果相同；普通页面无此操作。未填充行情、证券主数据、日历或M3合成结果。

## 备份与恢复

- SQLite Backup API 一致性备份：`F:\codex-agnes\AI-trade-local-state\m0-production-db-001\backups\workbench-initial.sqlite3`。
- 从备份经同一 API 恢复到独立目录：`F:\codex-agnes\AI-trade-local-state\m0-production-db-001\restore-check\workbench.sqlite3`；未覆盖正式库。
- 两者147456字节，SHA256均 `8c08c5e587a760f62d79ec00f3537bb1d6db3067895af64b54e3b00840f5b514`，均无侧车。与源库逐项比较结构/索引/触发器、迁移checksum/记录、七表计数、quick_check与FK检查一致。
- 不声称源库和备份字节hash相同。正式库演练是空业务表的结构恢复；隔离非空测试额外逐表比较了合成版本、批次和时间内容，不冒充真实历史恢复认证。备份过程有30秒上限，已有目标或侧车拒绝；失败保留诊断文件，不删除重试覆盖。
- 无周期备份/异地灾备/云同步配置；后续采集前仍需新的数据备份与恢复验证。

## 历史样本清单与迁移预览

本轮重新读取 PR44 现有清单613库、16个观察文件候选，非全盘重新扫描。全部627个原数据库/侧车文件hash与原清单一致（初始化后再核对）；16项中含合成/坏JSON，未冒充16个真实来源。逐库表行数、逐源/批次/逐source_version日期/质量/系统时点、SHA256与候选观察元数据保留本机 `F:\codex-agnes\AI-trade-local-state\m0-production-db-001\legacy-preview.json`（3693942字节，hash见机器证据）。该文件无OHLC原始价格/原始响应。

| 真实旧样本 | 行数 / 日期 | 来源 / 批次 / 质量 | 处理 |
| --- | --- | --- | --- |
| `C:\Users\iyoyi\AppData\Local\Temp\a-share-quant-demo-5gu28e3m\demo.sqlite3` | 600000.SH；1217；2021-10-08～2026-10-15 | 腾讯 stock_zh_a_hist_tx task-008-v1+sdk-1.19.1；demo-fab1a9b6062641248b5d97ce97a9723f；accepted | 原文件保留；SHA256 `20253cec31b7d7ad8fe79bfcf24f8f77eeefe9bad4b86f087943f4fd36ba2cfc` |
| `C:\Users\iyoyi\AppData\Local\Temp\a-share-quant-demo-m2-q_hbvuaj\demo.sqlite3` | 600000.SH；187；2026-01-05～2026-10-15 | 同腾讯适配器；m2-tencent-600000-20260101-20261015；accepted | 原文件保留；SHA256 `a5a502ae889e4ad26dee3993f689b22cb6555584b454d751f9514bf1524269ed` |
| `C:\Users\iyoyi\AppData\Local\Temp\a-share-quant-demo-tduod91y\demo.sqlite3` | 600378.SH；2291；2016-10-17～2026-10-15 | 同腾讯适配器；demo-26c7d533818b49a49f97827cc47e8471；accepted | 原文件保留；SHA256 `4152f78c18dfaa9473f76a33809d902c9af7cc73c9fcceedf6848b7c6d949bfb` |

沪深300为真实550行观察文件的3版本/4位置，来源新浪 stock_zh_index_daily；路径/hash/日期/时间缺口在机器证据与完整清单。未复制进入正式根，未塞入股票表；来源/授权/逐日可得时间和日历分母仍未认证。

1217样本预览在正式创建前执行：目标尚不存在、目标版本0；1217个候选新版本、相同/冲突既有版本均0、源重复版本键0。新正式库初始化后实际版本仍0，**未迁移**。与187样本有187重叠逻辑日期，OHLC/量/额/因子及质量差异0，批次或系统时间差异187；不能按价格相等丢弃血缘、混用或合并。后续迁移须重新基于届时目标计算差异，当前预览不是写入许可。

来源检查：已读取安装的 AKShare1.19.1 MIT LICENSE；这仅覆盖软件。腾讯/新浪数据本地长期存储、自动采集、研究、公开展示/再分发许可未见已批准证据，均 UNKNOWN，不作法律授权推断。accepted是结构质量，不是来源真实性或L2认证。旧1217记录available/ingested为2026-10-18系统时点，不得回填成2021年已可用。没有历史证券身份/完整日历证据，迁移准入 BLOCKED。

## 执行与验证证据

环境：既有 Python3.12.14、SQLite3.53.1、Streamlit1.66.0；解释器 `F:/codex-agnes/AI-trade-main-demo/.venv/Scripts/python.exe`，PYTHONPATH显式指本任务src。测试默认外网阻断、独立临时库，不改系统代理/TLS。

| 检查 | 命令/实际结果 |
| --- | --- |
| 首轮定向 | pytest -q tests/unit/test_workbench_storage.py tests/unit/test_db.py tests/unit/test_market_analysis.py；exit0，73 passed（初始候选实现） |
| 页面/存储定向 | pytest -q tests/unit/test_workbench_storage.py tests/manual/test_workbench_offline.py；exit0，19 passed，9.90s |
| 首轮完整 | pytest -q --junitxml=…/logs/full.xml；exit1，2888 passed / 2 failed / 1 skipped，286.69s；日志保留 |
| 局部修复后 | pytest -q tests/manual/test_m3_diagnostic_states.py tests/manual/test_project_progress_offline.py tests/manual/test_workbench_offline.py tests/unit/test_workbench_storage.py；exit0，22 passed，20.94s |
| 最终完整 | pytest -q --junitxml=…/logs/full-final.xml；**exit0，2890 passed / 1 skipped，267.70s**；覆盖实现提交4bcda30 |
| 依赖 | python -m pip check；exit0，No broken requirements found；无依赖变更 |
| 初始化/备份/恢复 | workbench_cli initialize-new --root … --backup … --restore … --report …；exit0；逐项检查通过 |
| 实际启动 | scripts/start_workbench.ps1；诊断先成功，再监听127.0.0.1:8524；SQLite实连路径见上表/启动日志 |
| 只读预览 | scripts/preview_legacy_data.py --previous-inventory … --target … --output …；exit0；613库，旧文件不变，0数据库写入/0行情请求 |
| diff/迁移保护 | git diff --check通过；v1/v2与main差异为空；正式库受.gitignore data/保护；运行产物不提交 |

首轮两项回归均是本次页面兼容性问题：旧M3调用方config只有path，没有read_only；Demo故障测试要求保留“初始化失败”提示。暂停初始化和扩大修改，仅局部修复调用方兼容与消息；旧断言未改、核心计算未改，随后相关22项和完整套件均通过。

其他诊断失败：预览遇到旧清单中的坏JSON条目无sha256（KeyError），保留UNKNOWN并记录当前hash后成功，未过滤异常；报告生成器直接比较内存tuple与JSON list导致AssertionError，只objects字段类型不同，规范化JSON后结果完全一致，库hash不变。这些失败不伪装成数据库损坏或测试成功。预览和报告元数据问题各1次修正，未重置失败次数。

日志/原始证据统一在源码树外 `F:/codex-agnes/AI-trade-local-state/m0-production-db-001/`：initialization.json、legacy-preview.json、process.json、logs/full(.xml/.log)、full-final(.xml/.log)、compatibility.log、initialization-console.log、streamlit.log。提交仅白名单元数据摘要，见[机器证据](evidence/TASK_M0_PRODUCTION_DB_001.json)。

## UI 与未验证事项

| 证据类型 | 状态与边界 |
| --- | --- |
| 离线测试 | PASS；上述最终完整2890/1；唯一skip为显式未启用的实网AKShare测试 |
| 实际SQLite/启动绑定 | PASS；正式path/数据库连接/Schema/空表/日志/进程对应，启动后源库hash及结构不变 |
| 隔离Streamlit AppTest | PASS；M1–M4同一路径、刷新不初始化、缺配置失败、只读按钮、UNKNOWN；无真实网络 |
| 用户人工浏览器验收 | **用户确认“没有问题”**：按本任务明确问题核对8524页面正式绝对路径、Schema2、业务表0行；这是用户提供的观察，非代理截图 |
| 自动浏览器 | ENV_BLOCKED；cua getTab 被URL policy拒绝、未取得观察权限；明确禁止替代浏览器/间接方式绕过。未重试，未伪造截图 |
| 真实行情网络 | NOT RUN；本任务行情GET/采集0；官方技术文档阅读不是行情验收 |
| 手机浏览器 / 样本外 / 实盘 | NOT RUN；无相应验收或授权 |

## 后续与门禁

1. TASK-M0-PRODUCTION-DB-001-REVIEW：独立H绑定最终PR head，重点审URI连接/不创建、初始化幂等与失败保护、Schema漂移、备份恢复、M0–M4配置和旧调用兼容。待指派，当前会话不充当自己的独立审查。
2. 旧1217样本：先独立确认来源/许可/时间/质量与可审计去重恢复策略，再创建迁移TASK；本任务无迁移许可。
3. M3新增结构/字段/键/版本/时间/来源证据及后续有序迁移设计见 [M3_STORAGE_GAPS](M3_STORAGE_GAPS.md)。草案尚待独立H；不改v1/v2，不把宽度/指数/CFFEX塞进daily_bars。
4. 后续有界真实数据来源、历史身份/日历/全A分母、研究L2/L3、样本外、策略/交易和AWS门禁继续保留。空正式库及代码通过不等于M0–M3数据链路、真实来源认证或策略有效性通过。

交付独立 Draft PR，等待独立H及用户决定；不合并、不部署、不连接账户、不修改AWS/认证/TLS/代理、不删除任何Demo/worktree/stash/日志/历史成果。

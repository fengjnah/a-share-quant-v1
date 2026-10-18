# TASK-015：多数据源健康检查与定时验收框架

执行日期 2026-10-18（Asia/Shanghai）。唯一执行模型 `gpt-6.1-sol / high`，沿用本会话用户最近确认的当前配置，并符合本任务推荐值；工具不独立暴露运行时型号，费用未知。风险等级 H，实际行情请求预算 **0**；不混用模型或子代理。适用 G01–G12，已实际读取 AGENTS、MODEL_ROUTING_POLICY v1.0、TASK_TEMPLATE、DECISIONS、数据/接口/验收契约及相关实现/测试/008/009 报告。实施范围是新健康模块、离线测试、文档与审计；不改既有适配器/采集器、Schema、时点契约、默认源、永久代理、生产数据库或 AWS。

## 基线与架构检查

GitHub API 与成功执行的 `git fetch origin main` 确认最新基线为 `31a575f6834067749ea006931282e62e8f666a18`，tree `ea7d91b0ecbef6a796335eb962d36b4838015588`。PR [#17](https://github.com/fengjnah/a-share-quant-v1/pull/17) 已合并为该提交，TASK-008 腾讯代码和 #13/#14 的局部修复均在 main。检查到仍开放 #11/#13/#14/#15/#16，未将它们当作新依赖、修改其状态或混入 #16 的诊断工具。

原 `F:\codex-agnes\AI-trade` 仍有 TASK-004 暂存/未暂存文件；指定的 `F:\codex-agnes\AI-trade-main-demo` 仍有 TASK-008 与其他任务的未提交材料。全部保留。使用新工作树 `F:\codex-agnes\AI-trade-task-015`、分支 `codex/task-015-source-health` 从 origin/main 精确提交开始。原两处 status、index/work diff 和文件哈希在 `artifacts/task-015/preserved-before.json` 保存并在交付前比对；未 reset/clean/删除工作树。复用已安装解释器只读运行工具，实际导入健康模块路径为新工作树 src。

| 检查项 | 实际状态与复用 |
| --- | --- |
| 数据源 | 现有 `akshare-eastmoney:stock_zh_a_hist:task-003-v1+sdk-1.19.1` 与腾讯 `akshare-tencent:akshare.stock_zh_a_hist_tx:task-008-v1+sdk-1.19.1`；新注册 ID 为 eastmoney/tencent，绑定真实接口和审核版本，腾讯 candidate 不变 |
| 采集状态 | success、empty_response、network_error、rate_limited、response_error、schema_error、validation_error、duplicate、conflict；复用而不改变含义 |
| 批次/审计 | run_id、独占 EvidenceStore 目录、SDK 帧摘要、完成状态、已提交异常标记；健康 check_id 同时作为采集 run_id |
| 存储 | Database 初始化/事务、SQLiteMarketDataRepository 批量写入和严格 as_of 读回，Schema v2；不新增核心迁移 |
| 证券/日历 | 已有 SecurityMaster/TradingCalendar 仓储及双时间可见性，但没有可默认信任的真实日历/证券历史覆盖；未知不能当休市或可交易 |
| Demo | 显式点击、rerun 去重、两源手选、失败未知行数和临时库已在 main；本轮不改页面或默认东方财富 |
| 已有健康/调度 | 没有统一健康结果、状态历史或调度入口；不重复建立行情采集/SQLite 实现 |

主要契约衔接：旧 IngestionResult 在未取得帧时仍有默认 returned_rows=0；健康包装只依据实际观察到的 DataFrame 决定 dataframe_rows，未取得必须 null，不修改旧接口。SDK 隐藏 HTTP/网络细节时不能仅凭异常名精确归因；真实日历缺失时不能编造 expected_data_date。

## 新增实现

| 文件 | 功能 |
| --- | --- |
| `src/ai_trade/market_data/health_models.py` | 全部要求字段、三种 check_type、十种状态、UTC 时间/计数/成功证据约束、受限脱敏详情和序列化 |
| `health_service.py` | 显式单源注册与配置检查、默认关闭的行情检查；复用 DailyHistoryIngestor；仅有效批次触发临时 SQLite 写入/严格读回；分别记录 HTTP/帧/质量/时效/DB 结果 |
| `health_transport.py` | 仅健康专用串行进程启用的发送边界预算、批准目标、HTTPS 验证、禁重试/重定向、重复 URL 阻断、缺省 timeout 补齐及 finally 恢复；不改变正常 Demo 采集行为 |
| `health_schedule.py` | 复用 EvidenceStore 的独占持久化；按源/检查类型报告状态和连续行情失败；严格日历适配、daily/weekly/monthly 计划及纯离线样本差异比较 |
| `health_cli.py` | OS 计划任务可调用的独立入口；默认 configuration_check，无网络开关不 fetch；只读报告和明确退出码，不安装任务 |
| `tests/unit/test_source_health.py`、`test_health_transport_schedule.py` | 49 个新增离线用例，模拟 HTTP/客户端，真实隔离 SQLite；不依赖实装 SDK 或网络 |
| `docs/SOURCE_HEALTH_CHECKS.md` | 参数、PowerShell 命令、状态语义、调度/预算/日历及进程边界 |
| `docs/evidence/TASK_015_AUDIT.json` | 本轮真实执行的 6 个离线配置/未启用检查及测试摘要，无供应商正文或凭据 |

健康摘要为独立 JSON，而不是新建核心健康表：当前 Schema 未定义该实体，先复用现有独占文件审计以避免为健康检查改行情迁移契约。配置检查不创建 SQLite；行情检查数据库显式指定系统临时路径和 test 环境，不调用 DatabaseConfig.from_env。既有生产路径仍未创建或修改。

## 证据语义与限制

- request_count 统计 Requests Adapter 发送尝试，包括腾讯起始日探测/分页；不是 SDK 调用次数，更不是上游收到请求的证明。另有 sdk_calls、request_state 和 HTTP 观察值；没有额外连接探针。
- connectivity_check 当前明确 not_run；不会为了实现此层偷偷发送 TLS/HTTP 请求。传输异常只定位到 sdk_fetch_transport，DNS/TCP/TLS 根因仍需独立证据。
- 无帧时 dataframe_rows=null。观察到 HTTP 200 且实际取得零行帧才是 empty_data；无 HTTP 证据的零行或解析异常为 unknown。HTTP 状态失败先于 SDK 解析识别，不把 403/429 误归为空行情。
- 质量失败不写库。成功批次经既有映射/校验、事务写入后，读回 bar/来源/run_id/as_of 一致并检查 SQLite 完整性；DB 已提交但本地审计失败时保留 committed，不盲目重试。
- 日历 unknown/source_error 与 stale_data 分开。默认没有已验收真实日历，CLI 即使验证了数据/DB，仍不会声称 freshness 成功。known 期望必须由可信调用方提供依据；日历适配器使用严格查询、拒绝 synthetic/缺失/源错误/未来日，不能按星期猜交易日。
- 配置成功不会清零行情失败计数。not_run/unknown 不计为已知失败，也不重置已知失败序列；当前报告仍明确 unknown，而非借用旧成功标成健康。质量失败、当前检查链路不可用、过期和生产未验收分别标记，下一步只是结构化人工复核建议，不发送外部通知或自动切源。
- 定时机制为可调用入口/配置和计划；周/月离线动作需由外部调度负责人显式串接测试与已保存样本比较，本轮没有安装 Windows/Codex/AWS 任务、自动执行历史审计或下载全市场。比较只报告差异/缺失，不静默选优。

## 实际执行与验收结果

解释器 `F:\codex-agnes\AI-trade-main-demo\.venv\Scripts\python.exe`，Python 3.12.14，AKShare 1.19.1、pytest 8.4.2、pandas 3.0.6、Requests 2.34.2、Streamlit 1.66.0。无依赖安装/升级，无重型服务。

```powershell
cd F:\codex-agnes\AI-trade-task-015
$env:PYTHONPATH = 'F:\codex-agnes\AI-trade-task-015\src'
& 'F:\codex-agnes\AI-trade-main-demo\.venv\Scripts\python.exe' -m pytest -q
& 'F:\codex-agnes\AI-trade-main-demo\.venv\Scripts\python.exe' -m pip check
git diff --check
```

| 验收类型 | 实际结果 |
| --- | --- |
| 新增离线测试 | 最终套件包含 **49 项通过**；配置成功/失败、传输/HTTP/解析/未知/空帧、时效、质量、DB、序列化、预算/重复发送/重定向/恢复、脱敏、报告与日历均覆盖 |
| 完整离线套件 | **412 passed、1 skipped in 20.35s**，退出码 0；唯一 skip 为需 --run-akshare-integration 的真实 AKShare 测试 |
| 依赖检查 | `No broken requirements found.`，退出码 0 |
| 本轮配置/入口实际验收 | 在 socket/Requests 发送被阻断的保护下运行两源 configuration、未启用 market、connectivity 共 6 次；网络尝试 0、HTTP 请求 0；配置 success，另两类 not_run；JSON 可重读、报告均为 current_status_unknown |
| 真实网络、浏览器 UI、生产适用性、样本外回测 | **未执行／未验收**；不能用本轮离线结果代替 |

测试过程中一个新增比较夹具误用两段 source，被既有三段 source 契约拒绝（47 passed、1 failed）；修正夹具为 synthetic:left:v1 / synthetic:right:v1 后通过，未放宽校验。日志保存在忽略目录 `artifacts/task-015/`，含相关测试初轮/最终输出、完整套件和 pip check。diff、文件范围、敏感信息、内部链接及原工作区保护复核在交付前执行并记录。

交付前保护复核已通过：TASK-004 工作树 37 个文件、TASK-008 工作树 77 个文件的哈希及 status/index/work diff 均未变。`git diff --cached --check` 退出码 0；有限围栏与 11 个内部文件链接检查通过；仓库未配置 Markdown lint，未为此新增工具。三处默认 local.sqlite3 路径均不存在。变更共 12 文件：5 个新健康模块、2 个新测试、实施/使用说明/审计 JSON，及 PROJECT_STATUS、LOCAL_MARKET_DEMO 两处文档索引；没有更改既有业务或存储实现。

## 当前数据源状态及后续

| 数据源 | 本地配置 | 本轮连接/行情/DB | 生产结论 |
| --- | --- | --- | --- |
| 东方财富 | 通过，审核 SDK 版本存在 | 未执行，当前可用性/真实行数/新鲜度未知 | 历史 TLS EOF / RemoteDisconnected 只是历史证据，不推断接口关闭或本次成功 |
| 腾讯 | 通过，仍是候选 | 未执行；不重复 TASK-008 真实请求 | 旧最小 2 行证据不能代表本轮真实成功，许可、原始复权键、SDK 去重前冲突、长期覆盖和限制仍未验收 |

模型/存储/入口与离线验收已实现；独立连接探针未实现（有意不增加网络请求），真实日历和生产准入仍未验收。健康包装补齐健康调用的 I/O timeout，但不修复旧 SDK 的所有内部机制，也不提供 OS DNS 的硬墙钟终止。只支持独立串行进程，不应嵌入并发联网页面；外部调度负责人需避免多个进程重叠。

建议下一项是独立 H 审查 TASK-015 最终 SHA，检查健康证据/预算与日历语义；审查通过后再单独授权一个源的小样本真实验收，不自动扩大预算、数据源或历史范围。本任务只创建 Draft PR，不合并/关闭旧 PR、不删分支、不部署。提交 SHA/PR 链接以交付消息和 PR 元数据为准，不在报告中自引用未来提交。

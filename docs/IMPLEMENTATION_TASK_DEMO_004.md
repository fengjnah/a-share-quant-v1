# TASK-DEMO-004：正式 AKShare 单次直连诊断

执行日期：2026-10-18（Asia/Shanghai）。唯一执行模型及档位：`GPT-6.1 Sol / Medium`，依据用户对本次会话界面显示值的明确确认；运行工具未独立暴露模型元数据。任务为受控真实来源验收，成本/实际费用未知，请求预算为**最多一次目标行情 GET**。适用 `AGENTS.md` G01–G12，已实际阅读 `docs/MODEL_ROUTING_POLICY.md` v1.0、`docs/LOCAL_MARKET_DEMO.md`、`docs/DATA_CONTRACT.md`、`docs/INTERFACE_CONTRACT.md`、`docs/ACCEPTANCE_TESTS.md` 及采集/存储实现。未改变时间语义、业务逻辑、生产数据库、系统代理或 TLS 验证。

## 基线与历史证据

GitHub API 于本次检查显示 `main=c65a3189daf72c1aa97b5930e3a22215bda3f1c8`。本机 `git fetch origin` 因 `Recv failure: Connection was reset` 失败，因此没有把本地远端跟踪引用当作本次最新状态的唯一证据。PR [#14](https://github.com/fengjnah/a-share-quant-v1/pull/14) 为未合并草稿，base `main@c65a3189…`，head `codex/task-demo-002-network-diagnostics@365a01ca3d6400225ea130188187655211a1cdd1`，改动采集器、相关测试和 TASK-DEMO-002 报告；head 对应离线 CI [成功](https://github.com/fengjnah/a-share-quant-v1/actions/runs/39052636700)。PR [#15](https://github.com/fengjnah/a-share-quant-v1/pull/15) 为未合并草稿，base 同一 main，远端 head `b7cbe9ef05623aa99e081b1141528f14817f553e`，仅改 TASK-DEMO-003 报告；head 对应离线 CI [成功](https://github.com/fengjnah/a-share-quant-v1/actions/runs/39087404130)。两者均未合入 main。本次独立工作树 `F:\codex-agnes\AI-trade-demo-004` 从 **PR #14 的精确 head** 建立，PR #15 的提交未混入；原 `F:\codex-agnes\AI-trade` 的 TASK-004 暂存、未暂存和未跟踪文件均未修改。PR #14 提供异常类型链改进，因而是本次正式采集器的实际执行基线。

逐项检查了前次文件：

| 文件 | 检查位置及结果 |
| --- | --- |
| `artifacts/task-demo-003/live_direct_acceptance.py` | 在 `F:\codex-agnes\AI-trade-demo-002` 存在；旧脚本先手写 HTTP GET，成功后才计划运行 SDK |
| `artifacts/task-demo-003/live-direct-audit.json` | 同上，存在；记录一次手写 GET、直连 `101.42.128.173:443`、`ConnectionError → ProtocolError → RemoteDisconnected`，未运行 AKShare |
| `artifacts/task-demo-003/direct-tls.json` | 同上，存在；另一次直连 `117.184.38.143:443` 的 TLS 1.3 握手成功，未发送行情 GET；SNI 从执行代码 `server_hostname=host` 核对，JSON 未单列 |
| `docs/IMPLEMENTATION_TASK_DEMO_003.md` | 不在 PR #14 工作树，在 `F:\codex-agnes\AI-trade-demo-003` 存在；已读取，不将报告写成旧工作树文件 |

## 离线请求路径核查

运行环境为 `F:\codex-agnes\AI-trade-main-demo\.venv\Scripts\python.exe`，Python 3.12.14、AKShare 1.19.1、Requests 2.34.2、urllib3 2.8.0。实际 SDK 模块为该虚拟环境的 `Lib\site-packages\akshare\stock_feature\stock_hist_em.py`。在阻断 socket 连接时导入该模块成功，未观察到导入时联网。项目 `AkshareDailyClient.fetch` 仅调用该模块 `stock_zh_a_hist(symbol=600000, period=daily, start_date=20261014, end_date=20261015, adjust="", timeout=10)`；`DailyHistoryIngestor.collect` 在此之前只做本地校验和证据目录预留，无股票列表接口请求。该 SDK 函数源码有且仅有一处 `requests.get`，然后调用 `r.json()` 并构造 DataFrame；没有显式 Session、重试、证书或自定义请求头设置。

旧探针与 SDK 使用同一域名 `push2his.eastmoney.com`、路径 `/api/qt/stock/kline/get`、`fields1/fields2/ut/klt/fqt/secid/beg/end` 参数值和 Requests 默认请求头/证书验证；两者均通过模块级 `requests.get` 创建临时 Session。旧探针显式 `allow_redirects=False`，SDK 原调用使用 Requests 默认重定向行为；旧探针在 HTTP 200 后只检查 JSON 顶层，正式 SDK 继续解析为 DataFrame，采集器再校验和写入。旧探针与本次子进程均设域名级 `NO_PROXY`，但不同请求实际解析到了不同 IP。差异是**可能影响的因素**，没有证据证明其导致前次断连。

本次诊断脚本 `tools/diagnose_akshare_direct.py` 通过项目正式 `AkshareDailyClient → DailyHistoryIngestor` 调用一次，不另发手写 HTTP GET。它仅在验收子进程设置 `NO_PROXY=push2his.eastmoney.com`，并在 `Session.send` 禁止跟随重定向、在 `HTTPAdapter.send` 核对固定参数与一次请求预算并把 urllib3 重试总数/连接/读取/重定向/状态重试设为零。这些是**诊断运行相对正常 SDK 的传输控制差异**；不改已准备请求的参数、请求头或响应内容。禁止第二次 Session/Adapter send 或不同目标。未固定 IP，未关闭证书/主机名验证。埋点按 `finally` 恢复；低层 `HTTPConnection.send` 完成仅表示本地函数返回，**不证明上游收到或处理请求**。

## 本次真实结果

运行命令（只在明确授权的单次验收中使用；再次执行会产生新的行情 GET）：

```powershell
$env:PYTHONPATH = 'F:\codex-agnes\AI-trade-demo-004\src'
& 'F:\codex-agnes\AI-trade-main-demo\.venv\Scripts\python.exe' tools/diagnose_akshare_direct.py --output artifacts/task-demo-004/live-audit.json
```

实测时间 `2026-10-18T01:52:35.815715Z`，耗时 0.844 秒，脚本退出码 2（采集失败）。`Session.send=1`、`HTTPAdapter.send=1`，没有被阻止的额外请求。原始本地审计位于忽略的 `artifacts/task-demo-004/live-audit.json`；已审查的脱敏提交版为 [审计 JSON](evidence/TASK_DEMO_004_AUDIT.json)，将机器临时路径替换为占位符，仅另加本地失败证据文件的名称、大小与 SHA-256。没有提交 SDK 响应正文、行情数据库、代理凭据或供应商敏感查询参数。

| 层级 | 状态 | 同一次正式请求的证据边界 |
| --- | --- | --- |
| DNS | **通过** | `push2his.eastmoney.com` 本次解析为 `117.184.38.143`；不代表地址长期固定 |
| TCP | **通过** | socket 连接 `117.184.38.143:443` 返回成功；实际是公网 IP 而非本机代理 |
| 代理 | **已观测直连** | 子进程 `NO_PROXY` 匹配、Requests 最终选中代理为 null，加上 socket 直连目标 IP；未修改 Windows 永久配置 |
| TLS | **通过** | 同连接 `server_hostname=push2his.eastmoney.com`、`CERT_REQUIRED`、`check_hostname=true`，TLS 1.3 握手完成 |
| HTTP 发送 | **本地调用完成** | `HTTPConnection.send` 返回；不能证明请求抵达上游或被处理 |
| HTTP 状态行/状态码/Content-Type | **失败／未取得** | `_read_status` 抛 `RemoteDisconnected`；没有状态码、Content-Type 或响应正文；失败在本地发送调用之后、状态行取得之前 |
| AKShare 解析 | **未执行到解析** | 正式 SDK 请求发生，但 `requests.get` 未返回；DataFrame、字段和真实返回行数均**未知**，不是 0 行 |
| SQLite 写入 | **未执行** | 采集器标记 `network_error`、`inserted_rows=0`；没有行情可写入 |
| SQLite 读回验收 | **未执行** | 临时测试库随后只读核查 `daily_bars=0`、`daily_bar_versions=0`、`ingestion_runs=0`、`PRAGMA integrity_check=ok`；这不代表成功行情读回 |

采集器失败证据位于本机临时目录 `C:\Users\iyoyi\AppData\Local\Temp\a-share-quant-demo-004-v0bq_pm8\evidence\5fa69e0e764038ea6cfecfa64655a7a93e39fd58d94f63557d9d9195c20ff64a`，实际只有 `request.json`、`result.json`，无 `response.json`。其 `result.json` 写有 `ConnectionError > OtherError > ProtocolError` 及默认 `returned_rows=0`；由于 `observed_at=null` 且没有 SDK 返回帧，**该字段不是已观察的真实返回行数**，提交审计将真实返回行数记为 null。低层状态行埋点另记录 `RemoteDisconnected`，但当前脱敏封装没有保留完整连续的上层异常链类型；不能将几处日志拼接成未经验证的完整原始链。未访问或创建默认 `data/sqlite/local.sqlite3`；本次只有隔离临时测试库。

本次可确定的最后成功阶段是**本地 HTTP 发送函数返回**。推断是连接在本机等待 HTTP 状态行时被对端或路径中的设备关闭，依据为 `RemoteDisconnected`；关闭者、请求是否到达上游、上游是否处理、是否与特定 IP/网络设备/服务策略相关均**未确认**。前次手写探针的同类异常提供重复现象线索，但不能确定同一根因。一次失败不证明东方财富接口关闭，也不证明历史行情为空。

## 离线验证与限制

使用同一 Python 解释器及本工作树 `src` 执行 `python -m pytest -q`：退出码 0，**333 passed、1 skipped in 14.00s**；跳过项为默认关闭的真实 AKShare 手工测试。新增 4 项覆盖一次 Adapter 发送及禁重定向、零重试、第二次/异目标阻断、异常后的埋点恢复、异常消息不进入类型链。`python -m pip check`：退出码 0，`No broken requirements found.`；`git diff --check` 通过。离线测试不能替代真实行情验收。本次未做 Streamlit UI、长期接口可用性、数据覆盖完整性或生产数据库验收。

下一步应由独立任务在网络路径/上游可观测性改善后再进行有界复测；若仍需要连续异常链，先增强只记**异常类型**的 Adapter 边界埋点并离线验证，再另行授权请求。不要对本次参数盲目重试、切换 IP 或降低 TLS 校验。PR #14 是本次代码基线依赖，合并前须保留此关系并独立审查，不将本诊断 PR 的提交视为 PR #14 已合入 main。

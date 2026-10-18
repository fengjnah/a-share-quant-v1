# TASK-DEMO-002：AKShare `network_error` 传输诊断

检查日期：2026-10-18（Asia/Shanghai）。执行模型 `gpt-6.1-sol / medium`，由用户确认当前会话界面；工具未独立暴露运行时型号。成本等级 M，实际费用未知。任务边界为只读证据核查、最小脱敏日志改进及离线验证；本任务真实行情请求次数 **0**。

## 基线与规则

已实际读取根目录 `AGENTS.md`、`docs/MODEL_ROUTING_POLICY.md` v1.0、`docs/LOCAL_MARKET_DEMO.md`、`docs/DATA_CONTRACT.md`、`docs/INTERFACE_CONTRACT.md`、`docs/ACCEPTANCE_TESTS.md` 以及 AKShare 适配器、采集器、证据仓储、Demo 和手工测试源码。适用 G01–G12，特别是工作区保护、单一模型、未知数据语义、网络显式启用、敏感信息和真实/离线验收区分。

`git fetch origin` 后 `origin/main=c65a3189daf72c1aa97b5930e3a22215bda3f1c8`。原工作区 `F:\codex-agnes\AI-trade` 位于 `codex/task-004-master-calendar@cd1b2b1`，有既存 TASK-004 暂存/未暂存及未跟踪文件；保持原样。先前 Demo 工作区 `F:\codex-agnes\AI-trade-main-demo` 位于 PR #13 的 `b31847f` 且干净。本任务从 `origin/main` 新建独立工作树 `F:\codex-agnes\AI-trade-demo-002` 和分支 `codex/task-demo-002-network-diagnostics`，不迁移 PR #13 的 UI 修复，也不改 main。

## 指定批次证据：已确认事实

指定目录：`C:\Users\iyoyi\AppData\Local\Temp\a-share-quant-demo-89864d96\evidence\76cf7af423b6f9ac1ac477becb652fed919b4e62a95142352485c47ef23ea064`。逐项检查结果：

| 项目 | 实际内容 |
| --- | --- |
| `request.json` | 存在，SHA-256 `8c4f238cd2e2e8d03bc1df69b2ad79874f44f12ab4c0dcfef9ec9204dcca2bd6`；`run_id=demo-a4ece99aa64b4b40a35b6aa3ba6d33bc`，AKShare 1.19.1，`600000.SH`，2026-10-14 至 15，日线，`adjust=""`，10 秒超时；`started_at=2026-10-17T16:57:29.407154+00:00` |
| `result.json` | 存在，SHA-256 `d37d9675c47bb64d645137d96f4e1bec4bc77d16580fa40bc4dcf908c2520d3f`；`network_error`，`ConnectionError: source transport failed`，`completed_at=2026-10-17T16:57:29.563434+00:00`，`observed_at=null`，`http_status=null`，`response_sha256=null`，插入 0 |
| `response.json` | 不存在；没有 SDK DataFrame 或原始 HTTP 响应证据 |
| 该批次原始异常链/连接日志 | 指定证据中不存在；不能据此判定 DNS、TCP、TLS 或 HTTP 子阶段 |
| 同目录临时 `demo.sqlite3` | 只读打开；`daily_bar_versions` 实际 0 行。未访问生产库 |

`result.json` 的 `returned_rows=0` 是采集器在尚未得到 SDK 响应时的初始化计数，**真实返回行数未知**；不能解释为供应商返回空行情。PR #13 的页面已在 `observed_at=null` 时显示“未知”，但这个旧批次的证据值仍是上述原貌，本任务未改核心数据契约。

## 调用链、代理字段和失败阶段

`AkshareDailyClient.fetch()` 只调用 AKShare 1.19.1 的 `stock_zh_a_hist`。已安装 SDK 对应源码调用 `requests.get()` 到 `push2his.eastmoney.com/api/qt/stock/kline/get`；适配器没有额外重试或代理 fallback。`DailyHistoryIngestor.collect()` 在 `client.fetch()` 发生 `RequestException`/连接错误时，原有代码只把异常类名和固定文案写入 `issues`。它没有重新抛出，故 `__cause__`、`__context__` 及底层类型未进入该批次的 `result.json`。`ConnectionError: source transport failed` 是**项目封装文案**，不是 SDK 原始异常文本。`HTTPError` 可从响应对象提取状态码；本批次没有可用 HTTP 状态，不能推断一定没有任何服务器响应，因为 SDK 也可能不暴露元数据。

Demo 的“行情域名走环境代理”来自 `requests.utils.get_environ_proxies(URL)` 的布尔值，只反映**启动页面的进程按当时环境和 `NO_PROXY` 规则解析出的配置**，不观察实际 TCP 连接路线。原页面显示“否”并非路由实测。本次只读检查时，Windows 当前系统代理启用、服务器已配置，当前进程无 `HTTP_PROXY`/`HTTPS_PROXY`/`ALL_PROXY`/`NO_PROXY` 环境变量；Requests 对该域名解析到本机 `127.0.0.1` 代理，`should_bypass_proxies=False`。这些是**当前进程**状态，不能倒推先前 Demo 批次；先前 PR #13 记录了其 Streamlit 子进程曾设置域名级 `NO_PROXY`，但指定批次没有逐连接路由证据。建议页面后续将字段明确写为“Requests 代理配置推断”，并保留“实际连接路线未知”，单独立项处理 UI 文案。

另一份既有手工验收审计 `F:\codex-agnes\AI-trade-main-demo\artifacts\task-local-reconcile-001\integration-audit.json` 记录过**不同请求**的 `ConnectionError → ProtocolError → RemoteDisconnected`，`requests.Session.send` 未返回 HTTP 状态；既有 TLS 诊断记录该域名经本地代理 CONNECT 200 后 TLS EOF，而直连 TLS 1.3 验证成功。这说明代理/TLS/上游路径都值得后续排查，但**不能把这些现象指定为本批次根因**。本批次最细的可证阶段是 `client.fetch()` 内传输失败、SDK DataFrame 尚未返回；DNS、TCP、TLS、HTTP 子阶段均为**证据不足**。未发现证书验证失败的本批次证据，也未证明真实行情为空。

## 最小日志改进与验证

原证据缺少关键异常链，因此仅修改 `src/ai_trade/market_data/ingestor.py`：保持 `network_error`、现有结果对象及证据文件结构，给 `issues` 增加最多 8 层的异常**类型名**，并明确 `failure_stage=sdk_fetch_transport; network_phase=undetermined`。只允许已知安全类型名，其他类标为 `OtherError`；不持久化异常消息、URL、请求查询串、代理用户名/密码、认证头或 Cookie。此改动帮助未来批次诊断，**不能补回指定旧批次的原始异常**。新增 `tests/unit/test_akshare_ingestion.py` 的离线测试，用含代理凭据和 token 的合成异常链检查写出的 `result.json` 保留类型而不泄露消息，并验证没有响应文件或 SQLite 行。

测试使用先前独立 Demo 工作区的 Python 3.12.14 虚拟环境，设置本任务 `src` 为 `PYTHONPATH`，未修改该环境。实际命令及结果：

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
& 'F:\codex-agnes\AI-trade-main-demo\.venv\Scripts\python.exe' -m pytest -q tests/unit/test_akshare_ingestion.py
# 退出码 0：72 passed in 2.81s
& 'F:\codex-agnes\AI-trade-main-demo\.venv\Scripts\python.exe' -m pytest -q
# 退出码 0：329 passed, 1 skipped in 11.87s；跳过显式启用的真实 AKShare 测试
& 'F:\codex-agnes\AI-trade-main-demo\.venv\Scripts\python.exe' -m pip check
# 退出码 0：No broken requirements found.
git diff --check
# 退出码 0
```

真实 AKShare 请求、实时路由抓包、Edge/Chrome 页面验收在本 TASK **未执行**。如用户稍后关闭系统代理，需在独立验收任务中用新进程、同一证券/日期/不复权参数，只发一次受限请求；记录该次异常链、实际返回/入库/SQLite 读回及证据摘要。若再次失败，按新证据分类，不重试直至另有明确理由。不关闭 TLS 验证，不创建生产数据库。

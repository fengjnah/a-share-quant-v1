# TASK-003B：AKShare 环境诊断与真实行情验收记录

检查日期：2026-10-17（Asia/Shanghai）。结论：**依赖安装已修复，离线测试通过；真实行情请求在 TLS 阶段失败，真实行情链路未通过验收。** 没有切换接口、降低 SDK 版本、放宽依赖、关闭 TLS 校验或以模拟结果冒充真实行情。

## 基线与修改范围

PR #1 仍 open、未合并：`main@125fd7e` → `feature/task-002-sqlite-foundation@4b73f8a`。PR #2 仍依赖 TASK-002 分支，本轮开始 head 为 `feature/task-003-akshare-adapter@3b0174e`。提交祖先关系已核实，本轮不修改 main、不合并、不部署、不连接账户。

只补强手工测试、增加其离线检查，并更新 README 和本文。`src/`、`pyproject.toml`、`tests/conftest.py` 均未修改。没有改变 SQLite、供应商业务逻辑、none 口径、依赖约束或默认网络阻断规则。

## 环境诊断与最小处理

本地 Windows 11 执行器，不是 Codex Cloud；本轮没有验证 Cloud 网络。Python 3.12.14，虚拟环境 `.venv`，pip 25.0.1，SQLite 3.53.1，pandas 3.0.6，requests 2.34.2，pytest 8.4.2。

- 项目可选依赖确为 `akshare==1.19.1`，客户端版本限制也为 1.19.1。PyPI 元数据确认该版本要求 Python >=3.11；原安装命令正确。
- 没有 HTTP_PROXY/HTTPS_PROXY/ALL_PROXY 环境变量，也没有发现 pip 配置文件或 PIP_* 环境变量。Python 仍读取到 Windows 系统代理 `127.0.0.1:7890`；有效代理不含凭证。**没有环境变量不等于没有代理。** 没有改动全局代理、注册表、CA 或 pip 永久配置。
- PyPI 和下载域名 DNS 解析成功；版本元数据 GET、AKShare wheel 地址 HEAD 均 HTTP 200。它们不证明行情域名也可达。
- 本轮第一次常规安装失败，pip 报 `No matching distribution found for tabulate>=0.8.6`。随后 PyPI Simple API 返回 38 个 Python 兼容文件，禁用缓存的 pip index 也确认存在兼容版本，因此没有证据支持删除约束或改 Python 版本。
- 一次有界 `--no-cache-dir` 安装随后成功，安装 AKShare 1.19.1 及其声明的传递依赖。每次安装使用 `--retries 0 --timeout 15`，外层最长 150 秒；没有无限重试。不能仅凭成功断言缓存损坏，间歇代理/索引链路问题仍可能存在。
- 前轮 ProxyError、此次 pip 候选查找失败、此次行情 SSLError 是不同的观察结果；不将其都泛称为 DNS 问题或包版本冲突。此次行情错误是 TLS EOF，不是已证明的证书验证失败；没有关闭验证来规避。

本轮实际成功安装命令：

```powershell
.\.venv\Scripts\python.exe -m pip --no-cache-dir install -e ".[test,akshare]" --retries 0 --timeout 15
.\.venv\Scripts\python.exe -m pip check
```

可选 SDK 的传递/二进制依赖许可未因此自动完成审核；软件许可不代表行情数据商用或再分发授权。

## 手工测试的补强

`tests/manual/test_akshare_daily_live.py` 仍必须同时设置输入并显式传入 `--run-akshare-integration`，只使用 pytest 临时目录：

1. 测试内包裹真实 `requests.Session.send`，记录受控端点、方法、非敏感参数、HTTP 状态/异常类别；然后调用原传输函数，不提供模拟响应。只允许一次传输尝试，禁止换源、自动重试或重定向。requests 当前默认重试总数另已核实为 0。
2. 供应商返回、领域对象、SQLite 版本数量及日期对应；字段逐项读回，检查 OHLC、量额、手转股、none 和空因子。请求日期只限定返回记录范围，不以两天范围就假定应返回两行。
3. `available_at`/`ingested_at` 对应真实观察/校验时点；所属历史事件时点、可得前一微秒、入库前一微秒均不可见，入库时点读回与领域对象一致。
4. request/response/result 证据存在且内容一致；response 文件 SHA-256 与结果一致。SDK JSON 快照仍不是 HTTP 原始字节证据。
5. 成功取得真实批次后，在另一个临时库重放该 SDK DataFrame，注入结果文件写入 OSError，要求 `database_committed=True` 且 SQLite 行数保留。这个步骤不再请求网络；本轮因 TLS 失败没有执行该真实批次重放。
6. 始终输出本地 `integration-audit.json`，保留有界、脱敏的原因链。完整 URL、相对 URL 查询参数及常见凭证字段均脱敏。网络失败时返回行数记 null，SDK 内部默认计数 0 单独保留，不冒充供应商空表。

新增 `tests/unit/test_manual_acceptance_checks.py` 共 9 项离线用例，覆盖绝对/相对 URL 脱敏、循环原因链、真实临时 SQLite 正常读回以及证据/数据库被故意破坏时验收断言会失败。这些用例使用合成数据，不是第二次真实行情验收。

## 唯一一次真实请求尝试

时间：2026-10-17 02:37 UTC 左右。使用实际安装的 AKShare 1.19.1，经原客户端调用 `stock_zh_a_hist`，测试内追踪实际传输入口：

| 项目 | 实际记录 |
| --- | --- |
| 证券与调用者研究实体 | 600000.SH；research:600000.SH:task003b |
| 请求范围与口径 | 2026-10-14 至 2026-10-15；none |
| 传输目标 | push2his.eastmoney.com /api/qt/stock/kline/get，GET |
| 安全参数子集 | secid=1.600000，beg=20261014，end=20261015，klt=101，fqt=0 |
| 真实传输尝试次数 | 1；没有再次请求 |
| HTTP 响应 | 无，不能证明请求已到达供应商应用服务 |
| 失败原因链 | requests SSLError → urllib3 MaxRetryError → SSL 层 SSLError；UNEXPECTED_EOF_WHILE_READING |
| 测试细分类 / 采集器状态 | tls_failure / network_error |
| 返回行数、实际交易日期 | 未取得（null）、无；不是已证实的供应商空结果 |
| 插入数量 | 0，SQLite 实际查询核实 |
| OHLC、量额、正常行情读回 | 无真实数据，未执行正向验收 |
| 证据文件 | request.json 与 result.json；无 response.json，response_sha256=null |

实际测试输出为 **1 failed in 2.65s**，退出码 1。没有 HTTP 状态，不能断言限流、非交易日、服务端空数据或证书链错误，也不能只凭 EOF 确定是代理还是源端关闭连接。按照环境阻断要求停止真实请求，没有设置 verify=False、直连绕过系统代理、修改 CA、换接口或以重试取得偶然成功。

临时库 Schema 版本 1；instruments、daily_bars、daily_bar_versions、ingestion_runs 四表均 0 行；`PRAGMA quick_check=ok`，`foreign_key_check` 无违规。空库完整性通过不能代替真实行情字段验收。

## 可复现命令

以下命令会产生真实请求。依赖安装成功后，在允许访问该行情域名的环境中显式运行；不要将本轮网络阻断写成通过：

```powershell
$env:AKSHARE_TEST_INSTRUMENT_ID = "research:600000.SH:task003b"
$env:AKSHARE_TEST_SYMBOL = "600000.SH"
$env:AKSHARE_TEST_START = "2026-10-14"
$env:AKSHARE_TEST_END = "2026-10-15"
$acceptanceTemp = Join-Path ([System.IO.Path]::GetTempPath()) ("a-share-task003b-" + [guid]::NewGuid().ToString("N"))
.\.venv\Scripts\python.exe -m pytest tests/manual/test_akshare_daily_live.py --run-akshare-integration --basetemp $acceptanceTemp --tb=short -q -s
```

`INTEGRATION_AUDIT=` 输出本地摘要路径。pytest 临时库及 SDK 证据位于该临时目录，不放入 Git。本轮调用日志、环境与依赖诊断、验收摘要及回归输出保存在本机已忽略的 `artifacts/task-003b/`，未提交；其中：

- `environment-diagnostics.json`：解释器、代理摘要、pip、DNS 和包站点探测。
- `dependency-install.log`、`dependency-install-no-cache.log`、`tabulate-index-diagnostic.json`、`pip-tabulate-index.log`：失败与成功安装、候选包诊断。
- `manual-integration-output.log`、`manual-integration-summary.json`：实际失败输出、请求参数、脱敏原因链、临时证据位置和完整依赖版本。
- `verification-summary.json`：空库实际检查、证据文件存在性及回归结果。
- `offline-tests.log`、`dependency-check.log`、`unit-network-guard.log`：实际离线输出。

真实请求后又完善了诊断的相对 URL 脱敏和无响应计数语义，并以离线用例验证；没有因此再请求行情接口。留存的首次审计文件已做脱敏和无响应计数归一化，单独注明 postprocessing，原 SDK 计数仍保留。

## 回归结果、状态与 PR #2 建议

```text
217 passed, 1 skipped in 6.38s
No broken requirements found.
1 passed in 0.94s  # 显式集成开关下，普通单元测试仍阻断网络
```

217 项包含原来的 208 项和新增 9 项；不是 217 个架构验收项目。真实测试在前述独立命令中失败；默认套件的 1 skipped 是正常的显式开关门禁，没有把真实失败改成跳过来伪造通过。

| 状态 | 对应事实 |
| --- | --- |
| 已通过 | 固定 SDK 安装、依赖检查、217 项离线测试、网络阻断规则检查；新验收助手的真实临时 SQLite/证据破坏检测 |
| 未执行 | 正常真实行情 OHLC/量额、实际日期覆盖、正常 SQLite 读回及响应摘要一致性；真实批次重放的提交后证据失败检查 |
| 被环境阻断 | 真实行情 TLS 连接；没有成功响应，真实链路与完整数据验收均未通过 |
| 存在缺陷 | 未复现生产数据逻辑缺陷；原手工测试缺少验收断言与详细诊断的问题已补强。源端/代理具体根因、日历/实体/授权等仍待验证 |

PR #2 建议继续等待真实源验收，不能以 SDK 安装成功或离线测试通过替代。TASK-002 PR #1 未合并，仍须先处理依赖顺序，再按实际合并方式核实 #2 的祖先关系、diff 和目标分支。本任务不自动执行合并、改 main 或部署。

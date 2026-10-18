# TASK-LOCAL-RECONCILE-001：本地基线与行情 Demo 验收记录

检查日期：2026-10-18（Asia/Shanghai）。执行模型：`gpt-6.1-sol / high`，由用户确认本会话界面；工具未独立暴露运行时型号。成本等级 H，实际费用未知。本报告记录已执行结果，不代表完整真实行情或 Edge/Chrome 验收通过。

## 基线与工作区保护

`git fetch origin` 成功，`origin/main=c65a3189daf72c1aa97b5930e3a22215bda3f1c8`。已读根目录 `AGENTS.md`、`MODEL_ROUTING_POLICY.md` v1.0、`PROJECT_STATUS.md`、`LOCAL_MARKET_DEMO.md`、`DATA_CONTRACT.md`、`INTERFACE_CONTRACT.md`、`ACCEPTANCE_TESTS.md`、`DECISIONS.md` 与 TASK-003C 报告；适用 G01—G12。新增工作树 `F:\codex-agnes\AI-trade-main-demo`，分支 `codex/task-local-reconcile-001`，直接基于该 main。未执行旧分支合并、reset、clean 或向 main 提交。

| 工作树/分支 | 检查时提交与状态 | 与 main 的关系 |
| --- | --- | --- |
| 原工作树 `F:\codex-agnes\AI-trade` / `codex/task-004-master-calendar` | `cd1b2b1`；16 个已跟踪文件有暂存/未暂存修改，另有未跟踪文件 | 旧 TASK-002 基线；实际主数据/日历代码内容已进入 main，原暂存状态保留 |
| `codex/task-004-master-calendar-resumed` | `bb596a9` | 与 main 中 TASK-004 squash 提交 `0578f9c` 的 Git tree 同为 `4d28793a0466e381a805cffa268a98074714666a`；提交 SHA 不同 |
| `codex/task-004a-source-review` | `39be058` | 独有 TASK-004A 研究提交不在 main；旧基线，未迁移 |
| `docs/model-routing-governance` | `b53e5b7`；工作树干净 | 与 main 中治理 squash 提交 `c65a318` 的 Git tree 同为 `4417b04d46892c6dd791ac10a800cc5c10598a87` |
| `docs/task-004a-report-only` | `b0a1ba1`；工作树干净 | 基于 `c65a318`，仅增加 TASK-004A 报告；不在 main，未迁移 |
| `.worktrees/local-demo-verify` | 分离 HEAD `b3e4e31`；工作树干净 | 旧 Demo 验证工作树，未修改 |
| 本任务工作树 | `c65a318`；创建前目标路径不存在 | 独立 `.venv` 和演示数据库，未迁入旧分支文件 |

原工作树逐文件内容比较（Git blob SHA 比较当前工作文件、暂存区与 `origin/main`；此表描述**文件内容**，不表示清除或改动暂存状态）：

| 文件 | 当前工作内容对 main | 处理 |
| --- | --- | --- |
| `README.md` | 不同，保留旧分支阶段的状态叙述，部分已过时 | 原样保留；以 main 的 README 为 Demo 基线 |
| `docs/DATA_CONTRACT.md` | 相同 | 不迁移 |
| `docs/IMPLEMENTATION_TASK_004.md` | 不同，含旧执行阶段记录 | 原样保留，不覆盖 main 的最终记录 |
| `docs/INTERFACE_CONTRACT.md` | 相同 | 不迁移 |
| `src/ai_trade/reference_data/__init__.py` | 相同 | 不迁移 |
| `src/ai_trade/reference_data/models.py` | 相同 | 不迁移 |
| `src/ai_trade/reference_data/repository_support.py` | 相同 | 不迁移 |
| `src/ai_trade/reference_data/validation.py` | 相同 | 不迁移 |
| `src/ai_trade/security_master/__init__.py` | 相同 | 不迁移 |
| `src/ai_trade/security_master/repository.py` | 相同 | 不迁移 |
| `src/ai_trade/storage/reference_schema.py` | 相同 | 不迁移 |
| `src/ai_trade/storage/schema.py` | 相同 | 不迁移 |
| `src/ai_trade/trading_calendar/__init__.py` | 相同 | 不迁移 |
| `src/ai_trade/trading_calendar/repository.py` | 相同 | 不迁移 |
| `tests/unit/test_db.py` | 相同 | 不迁移 |
| `tests/unit/test_reference_data.py` | 相同；暂存区仍是旧版本 | 原样保留暂存区，不迁移 |
| `docs/REFERENCE_PROJECT_REVIEW.md` | 原工作树未跟踪，main 无此文件 | 独有研究成果，保留原处，另行处理 |
| `.worktrees/local-demo-verify/`、`.worktrees/task-004a-report-only/` | 原工作树视为未跟踪目录，实际为 Git worktree | 保留，不作临时文件删除 |

新工作树的 `.venv/`、`.pytest_cache/`、`artifacts/` 均由 `.gitignore` 忽略。系统临时目录下的演示 `demo.sqlite3`、证据 JSON 及 pytest 测试数据库没有加入 Git。原工作树此前已有的 `artifacts/` 也未触碰。

## 环境、离线测试和页面

Windows `py` 启动器只列出 Python 3.9，不满足 `>=3.11`；从旧虚拟环境配置读取其 Python **基础运行时**位置，用该基础解释器创建本工作树自己的 `.venv`。没有调用旧工作树的 `.venv`。执行：

```powershell
& 'C:\Users\iyoyi\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[akshare,demo,test]"
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest -q
```

安装退出码 0；Python 3.12.14、AKShare 1.19.1、Streamlit 1.66.0、pandas 3.0.6、requests 2.34.2、pytest 8.4.2。`pip check` 退出码 0：`No broken requirements found.`。初始完整离线测试 **327 passed, 1 skipped in 11.74s**；UI 修复后的完整离线测试 **328 passed, 1 skipped in 13.10s**，退出码 0。跳过的是未显式启用的 `tests/manual/test_akshare_daily_live.py`。新离线 UI 测试单独执行 **1 passed in 2.37s**。该测试以模拟传输失败验证首次加载不采集、每次点击只采集一次、普通重运行不重复采集、失败时返回行数为“未知”。测试子进程只允许 Streamlit 测试器所需的本机回环 socket，禁止外部网络；原 `tests/conftest.py` 网络禁用夹具未改。

Streamlit 实际启动于 `http://127.0.0.1:8501/`。Codex 内置浏览器实际打开页面，初始显示 `600000`、`2026-10-14` 至 `2026-10-15`、不复权，已保存 0 行，SQLite 位于 `C:\Users\iyoyi\AppData\Local\Temp\a-share-quant-demo-7pso6hw0\demo.sqlite3`。重新启动后的新会话又显示单独临时路径及 0 行，未点击时没有新增采集证据。原页面热重载时曾意外再次触发采集，见下；本次用一次性点击编号修复。尝试启动本机 Edge 的命令遭自动审批拒绝，工具只给出 `blocked by policy`，未给出更详细理由；**Edge/Chrome 实际 UI 验收未完成**，内置浏览器结果不能替代。

## 真实行情请求与 SQLite 证据

请求均限定 `600000.SH`、2026-10-14 至 2026-10-15、日线、不复权 `adjust=""`（供应商 `secid=1.600000`、`klt=101`、`fqt=0`）。`NO_PROXY=push2his.eastmoney.com` 仅设置在 Streamlit 或手工测试子进程；没有更改系统永久代理或关闭 TLS 验证。

| 验收项 | 实际结果 |
| --- | --- |
| Demo 页面提交 | 首次明确点击后 `network_error`；无 HTTP 响应、无观察时间、无 SDK 响应摘要；未取得可确认的返回行数 |
| 意外热重载 | 修改运行中的页面文件触发第二次同范围 Demo 请求，仍为 `network_error`；发现后立即停止服务，增加提交编号去重，未继续热修改运行中服务 |
| 有界手工测试 | 为取得脱敏原因链另发一次同参数请求；只允许一次 `requests.Session.send`，退出码 1，`1 failed in 2.04s`；`proxy_configured=false`、证书验证开启，分类 `network_connection_failure`，原因链为 `ConnectionError → ProtocolError → RemoteDisconnected: Remote end closed connection without response`，没有 HTTP 状态 |
| 请求次数 | 本轮实际三次同范围 GET 尝试：Demo 两次（第二次为意外热重载）、独立手工测试一次；均失败。修复后未再发真实请求，等待用户关闭系统代理后的单独一次测试 |
| 返回/入库/读回 | 返回行数**未知**；插入 0，演示临时库 `daily_bar_versions` 实际读回 0，`quick_check=ok`、外键检查 0 项。手工测试临时库也读回 0 |
| 证据 | Demo 两个失败批次分别有 `request.json` 和 `result.json`，没有 `response.json`；首批次结果文件 SHA-256 为 `09faf6e3a0b8183755022d1912d6b420d8379c249b9164e894911ac00d70ba8a`。手工测试的脱敏审计见忽略目录 `artifacts/task-local-reconcile-001/integration-audit.json` |

现有 TLS 诊断工具进行了固定两主机、代理/直连共四次握手，**没有发送行情 GET**。行情域名经系统代理 CONNECT 200 后在 TLS 握手阶段 `SSLEOFError`；直连 TLS 1.3 且证书/主机名验证通过。`pypi.org` 两条路径均握手成功。直连 TLS 成功不保证 HTTP 请求成功；本次直连 GET 在响应前断开，不能把它判为真实空行情。新工作树默认 `data/sqlite/local.sqlite3` 不存在，未创建生产数据库。

## 修改、限制与后续验收

仅改 `src/ai_trade/demo_app.py`：用一次性表单点击编号阻止普通重运行再次请求；请求尚无响应时页面显示返回行数“未知”。新增 `tests/manual/test_streamlit_demo_offline.py`，默认有 Demo 依赖时本机离线运行；CI 仅安装 `.[test]` 时明确跳过。新增本报告。未修改 AKShare 适配器、数据契约、Schema、生产配置或默认网络禁用规则。

日志：`artifacts/task-local-reconcile-001/manual-integration.log`（失败输出）、`integration-audit.json`（脱敏链）、`tls-diagnostic.json`（握手证据）；均被忽略，不提交原始响应、行情值、数据库或凭据。离线 pytest 最终输出见任务执行记录，未另存完整日志。`git diff --check` 和提交前文件范围检查需在交付时复核。

当前分项状态：新环境与依赖 **通过**；离线测试 **通过**；内置浏览器页面启动及初始状态 **通过**；Edge/Chrome 浏览器 **未验收**（自动审批阻断）；真实 AKShare HTTP 与 SQLite 成功读回 **失败/环境阻断**；完整行情历史质量 **未验收**。用户计划稍后自行关闭系统代理；届时保持同证券、日期、口径，以一次明确页面点击单独复测，记录新批次的 HTTP、返回/入库/读回及证据摘要。本报告不把 2026-10-17 的另一环境成功结果充作本轮结果，不建议据此开启生产数据库。

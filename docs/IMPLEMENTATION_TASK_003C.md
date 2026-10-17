# TASK-003C：TLS 路径诊断、数据库配置审查与真实行情验收

检查日期：2026-10-17（Asia/Shanghai）。**指定批次最小真实行情验收通过；经系统代理访问行情域名的 TLS 故障仍可复现，责任点尚未定位到代理节点或上游出口策略。** 本轮采用有证据支持、仅限验收子进程的域名级 NO_PROXY，不关闭 TLS 验证，不修改已经通过测试的业务逻辑或永久配置。

## Git 与边界

从已确认的 PR #2 head `fc692e7ed0c1aeffa7c3db0eb5a8b0ac9be9ca8f` 创建独立分支 `codex/task-003c-tls-diagnostics`。PR #2 仍 open、未合并，base 为 `feature/task-002-sqlite-foundation@4b73f8a`；未假定 TASK-002 已合并。未修改 main，不自动合并，不部署、不连接账户、不重装 AKShare。

变更仅为诊断工具、诊断的离线测试、手工测试的证书验证/代理状态审计字段、README 和本文。`src/`、`pyproject.toml`、`tests/conftest.py` 均未修改；没有增加依赖、自动直连逻辑、股票策略或数据库迁移。

## 一、数据库配置与测试隔离审查

检查 `storage/db.py`、`tests/conftest.py`、现有手工测试和 TASK-003B 报告：

- QUANT_DB_ENV、QUANT_DB_PATH 均未设置；有效环境为 local，当前仓库工作目录下解析为 `data/sqlite/local.sqlite3`，本轮开始和结束均不存在。
- 默认相对路径基于**进程当前工作目录**解析，不是固定绑定仓库根目录。换目录执行时不能假定仍指向同一个文件。
- `.env.example` 仅为模板，不自动加载；production/test 的 `from_env` 必须显式指定路径，缺省会拒绝。环境标签不是操作系统权限隔离。
- 构造/解析 DatabaseConfig 仅处理配置，不连接或建库。数据库初始化会创建父目录和文件；直接调用 connection 在父目录存在时也可能创建空 SQLite 文件，因此只读配置检查没有调用它。
- 单元测试显式传 tmp_path 下的 test 路径；CLI 测试子进程显式设置临时路径。手工测试明确使用 tmp_path/manual.sqlite3 和 tmp_path/fault.sqlite3，未读取默认 local 配置。
- 本轮真实测试位于独立系统临时目录；本地默认库和生产库没有创建。两个有数据的临时库仍是测试库，不是生产数据库。

因此当前仍然**没有已确认的生产数据库路径，也没有创建生产数据库**。本轮成功后可单独讨论生产初始化：先确认独立存储位置和权限、显式 production 与绝对路径、备份/迁移审阅及执行人，再执行初始化；本任务不选择生产路径、不执行初始化。

## 二、只读环境与代理状态

实际使用 `.venv/Scripts/python.exe`：Python 3.12.14、AKShare 1.19.1、requests 2.34.2、urllib3 2.8.0、OpenSSL 3.5.8、certifi 2026.7.22。没有重复安装；证书包存在，没有证书路径覆盖环境变量。

HTTP_PROXY/HTTPS_PROXY/ALL_PROXY/NO_PROXY 环境变量原本均未设置，但 Python 读取 Windows 系统代理 `127.0.0.1:7890`；没有凭证。只读检查确认监听进程为 clash-meta；本地控制器报告 v1.16.0、global 模式、TUN 关闭。磁盘 YAML 的 TUN 值不同，不能以磁盘文件代替生效状态。控制器仅调用只读 GET，凭证只用于本机认证，没有写入日志或提交。

没有修改注册表、代理应用、全局环境变量、pip、CA 或 SDK。没有输出订阅/节点配置、代理口令或控制器凭证。

## 三、有界 TLS 对照：没有行情 GET

在确认代理仅为无认证本机 HTTP 代理后，允许两个固定主机、每个两条路径，共四次 TCP/TLS 连接：行情主机 push2his.eastmoney.com 与对照 pypi.org，分别经代理和直接 socket。代理只发送 CONNECT；TLS 完成后关闭连接，不发送 HTTP GET 或行情参数。每阶段最多 4 秒、工具总预算 45 秒，本轮另用外层进程 60 秒超时；没有扫描其他地址、端口或重复探测。

两种路径均使用 requests 默认 certifi 信任包、CERT_REQUIRED、SNI 和主机名验证。DNS 未报错，未命中 198.18.0.0/15 基准/fake-IP 地址段；直连仅选择一个解析地址，没有遍历所有地址。

| 目标 | 经系统代理 | 直接 socket |
| --- | --- | --- |
| push2his.eastmoney.com | CONNECT=200；随后 SSLEOFError / UNEXPECTED_EOF_WHILE_READING | 成功，证书与主机名验证通过，TLS 1.3 |
| pypi.org | CONNECT=200；证书与主机名验证通过，TLS 1.3 | 证书与主机名验证通过，TLS 1.3 |

结论及限制：

1. 代理监听和 CONNECT 阶段正常；不是单纯端口未启动或代理认证失败。
2. 同一 Python/OpenSSL/CA 对行情主机直连验证成功，且对照主机两路成功，排除了本轮的整体 DNS 失败、整体 TLS 栈失效或普遍 CA 不可信。
3. 差异定位到**代理出口到该行情主机的特定路径**。不能进一步断言是 clash-meta 缺陷、所选节点故障、出口被限制还是上游针对该出口断连；EOF 不是证书校验失败的证据。
4. 直连比较不证明所有运营网络路线，也不证明长期可用；没有通过关闭验证、降低 TLS 版本或换数据接口来制造成功。

## 四、唯一一次真实行情 GET 与结果

理由：代理路径 EOF 已复现，而同域名的直接、验证开启的 TLS 握手成功。只在**新的验收子进程**环境中追加 `NO_PROXY=push2his.eastmoney.com`，不改变父进程或系统设置。实际调用原 AKShare 1.19.1 `stock_zh_a_hist`；未重写请求或提供模拟响应。

| 项目 | 实际结果 |
| --- | --- |
| 时间 | 2026-10-17 02:52 UTC 左右 |
| 标的与请求范围 | 600000.SH，2026-10-14 至 2026-10-15 |
| 口径/参数 | none；adjust=""，fqt=0，klt=101，secid=1.600000 |
| 网络尝试 | 1 次真实 GET；proxy_configured=false，certificate_verification=true |
| HTTP/SDK | HTTP 200，JSON；采集结果 success，手工测试 1 passed in 2.16s |
| 返回/插入 | 2 行 / 2 行 |
| 实际日期 | 2026-10-14、2026-10-15，与请求范围对应 |
| 字段与单位 | OHLC 有限、为正且关系合法；量为非负整数股，逐行核对 SDK 手数 ×100；金额为非负元 |
| SQLite | 临时库实际读回全部领域字段一致；quick_check=ok，foreign_key_check 无违规 |
| 时间可见性 | 历史事件时点、available_at 前一微秒、ingested_at 前一微秒均不可见；入库时点读回一致 |
| 时间证据 | available_at、ingested_at 均为本次 2026-10-17 实际观察/校验时间，没有倒填到交易日期 |
| 采集证据 | request.json、response.json、result.json 均存在；SHA-256 与本次 SDK 快照和结果一致 |
| 提交后故障 | 在另一临时库重放本次 SDK 帧、只注入结果文件 OSError；database_committed=True，已提交 2 行保留，无第二次网络请求 |

真实行情值、数据库和 SDK 响应仅保留在系统临时目录；Git 中只提交验收元数据和方法，没有提交 OHLC、量额、原始载荷或数据库。具体临时路径和响应摘要见本机 `artifacts/task-003c/manual-integration-summary.json`、`verification-summary.json`。

这证明指定证券/日期/环境的一次最小真实链路通过；不证明完整历史覆盖、交易日历、所有证券实体、复权、首次发布时间证据、数据授权或生产就绪。默认代理路径仍失败，也没有自动回退为直连。

## 五、可复现命令与安全边界

默认只读检查，不发网络请求；输出文件不得覆盖，重跑应选新文件名：

```powershell
.\.venv\Scripts\python.exe tools/diagnose_akshare_tls.py --output artifacts/task-003c/runtime-new.json
```

显式允许相同的四次握手，不会请求行情；本例外层限制 60 秒。工具退出码 0 表示诊断已完成，逐项 success/failed 才代表对应握手结果：

```powershell
.\.venv\Scripts\python.exe -c "import subprocess,sys; sys.exit(subprocess.run([sys.executable,'tools/diagnose_akshare_tls.py','--probe-tls','--output','artifacts/task-003c/tls-new.json'],timeout=60).returncode)"
```

只有在上述直连证书验证成功且需要验收时，才再次显式运行下列命令。它会发出一次真实行情请求；NO_PROXY 仅传给子进程，测试明确开启网络且使用新临时库，不自动创建 local/production 文件：

```powershell
@'
import os, subprocess, sys, tempfile
from pathlib import Path
env = os.environ.copy()
previous = env.get("NO_PROXY") or env.get("no_proxy") or ""
env["NO_PROXY"] = ",".join(x for x in (previous, "push2his.eastmoney.com") if x)
if "no_proxy" in env:
    env["no_proxy"] = env["NO_PROXY"]
env.update(AKSHARE_TEST_INSTRUMENT_ID="research:600000.SH:task003c",
           AKSHARE_TEST_SYMBOL="600000.SH", AKSHARE_TEST_START="2026-10-14",
           AKSHARE_TEST_END="2026-10-15")
temporary = Path(tempfile.mkdtemp(prefix="a-share-task003c-")) / "pytest"
result = subprocess.run([sys.executable, "-m", "pytest", "tests/manual/test_akshare_daily_live.py",
                         "--run-akshare-integration", "--basetemp", str(temporary),
                         "--tb=short", "-q", "-s"], env=env, timeout=90)
raise SystemExit(result.returncode)
'@ | .\.venv\Scripts\python.exe -
```

本轮没有全局设置 NO_PROXY，也没有向 SDK 添加默认代理绕行；后续是否采用该进程级路由或修复代理节点，应由运行方明确选择，不应自动用于生产。

## 六、回归、证据与后续建议

完整离线回归和依赖检查实际结果：

```text
222 passed, 1 skipped in 5.52s
No broken requirements found.
1 passed in 0.91s  # 显式集成开关下，普通单元测试仍禁止网络
```

新增 5 项离线诊断工具测试：默认不联网/不建库、代理凭证脱敏、未知目标拒绝及不支持的代理安全跳过。真实手工测试是前述独立命令的 1 passed，不包含在 222 项内；默认跳过规则未修改。

本机已忽略目录 `artifacts/task-003c/` 保存初始只读状态、代理进程与控制器脱敏摘要、四次握手 JSON/日志、真实验收 JSON/日志、实际 SQLite/证据检查及全部回归输出。运行后父进程 NO_PROXY 仍未设置，系统代理仍为 127.0.0.1:7890，默认 local 库仍不存在。

| 状态 | 结论 |
| --- | --- |
| 已通过 | 指定批次真实连接、数据映射/质量、SQLite 读回、时间可见性、证据摘要和提交后故障重放；222 项离线测试及依赖检查 |
| 已确认故障 | 经当前全局代理访问行情主机的 TLS EOF；未修改该永久配置 |
| 尚未确认 | 代理节点/出口/上游具体责任、长期稳定性、其他证券/日期覆盖、完整历史证据、数据使用权限 |
| 未执行 | 生产路径选择与初始化、选股、回测、AWS 部署、PR 自动合并 |

后续无需重装 SDK 或修改业务校验。若希望系统代理路径恢复，可在用户管理的代理应用中检查当前全局节点和该域名的路由/连接日志，再选择一个明确的配置方案；本任务没有替用户切节点或修改规则。

本轮结果解除 PR #2 的“指定批次真实源未验收”问题，可进入人工审查；应结合 TASK-002/003 的既有范围和限制决定合并。仍需先处理 PR #1，再按实际 merge/squash 方式核实 #2 及本分支的基线；不得将一次成功当成完整数据验收或直接开始生产采集。没有执行任何合并。

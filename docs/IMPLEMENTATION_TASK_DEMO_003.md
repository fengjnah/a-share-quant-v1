# TASK-DEMO-003：单次真实行情链路复测前置诊断

执行日期：2026-10-18（Asia/Shanghai）。执行模型 `gpt-6.1-sol / medium`，依据用户在本会话对当前界面的确认；工具未独立暴露运行时型号。成本与实际费用未知。任务预算为最多一次行情请求，**实际行情请求 0 次**：当前所选网络路径在前置 TLS 检查失败，按任务要求停止。诊断不是完整行情验收。

## 代码基线与范围

已实际读取 `AGENTS.md`、`docs/MODEL_ROUTING_POLICY.md` v1.0、`docs/LOCAL_MARKET_DEMO.md`、`docs/IMPLEMENTATION_TASK_DEMO_002.md`、`src/ai_trade/market_data/ingestor.py`、`akshare_adapter.py`、`demo_app.py`，并检查相关数据/接口/验收契约。适用 G01–G12，尤其是基线、单一模型、未知数据、受控网络、生产数据隔离与证据交付。

`git fetch origin` 成功，`origin/main=c65a3189daf72c1aa97b5930e3a22215bda3f1c8`。PR [#13](https://github.com/fengjnah/a-share-quant-v1/pull/13) 仍为 open/draft、未合并，base `main@c65a3189`、head `b31847ff41e200d5b7cb8ef9193c785e1e3e16be`；只改 Demo 页面、UI 离线测试和报告；离线 CI [成功](https://github.com/fengjnah/a-share-quant-v1/actions/runs/39051447382)。PR [#14](https://github.com/fengjnah/a-share-quant-v1/pull/14) 仍为 open/draft、未合并，base 同上、head `365a01ca3d6400225ea130188187655211a1cdd1`；只改采集器、离线测试和 TASK-DEMO-002 报告；离线 CI [成功](https://github.com/fengjnah/a-share-quant-v1/actions/runs/39052636700)。两 PR 没有共同合入 main，不能称 GitHub `main` 已有其修复。

本任务的前置检查实际运行于干净的 `F:\codex-agnes\AI-trade-demo-002` 工作树 `codex/task-demo-002-network-diagnostics@365a01ca3d6400225ea130188187655211a1cdd1`，与 PR #14 远端 head、文件树一致；Python 实际导入的采集器及适配器均来自该工作树。它包含脱敏异常类型链改进，但不包含 PR #13 的页面修复，因此本任务选择正式适配器/采集器入口作为计划测试入口，**未做 Streamlit 页面点击验收**。原 `F:\codex-agnes\AI-trade` 仍在 `codex/task-004-master-calendar@cd1b2b1`，已有 TASK-004 暂存/未暂存及未跟踪内容，未触碰。另以 `origin/main` 建立本报告专用工作树 `F:\codex-agnes\AI-trade-demo-003`，仅提交本文件，不混入两个未合并 PR 的代码。

## 前置网络证据

固定计划参数：`600000.SH`、2026-10-14 至 2026-10-15、日线、不复权 `adjust=""`、AKShare 1.19.1 的 `stock_zh_a_hist`。Python 3.12.14，requests 2.34.2，urllib3 2.8.0。检查时 Windows 用户级系统代理启用、代理服务器已配置、PAC 未配置；进程内 `HTTP_PROXY`、`HTTPS_PROXY`、`ALL_PROXY`、`NO_PROXY` 均未设置。Requests 对目标 URL 的**配置解析结果**为 HTTP 代理 `127.0.0.1:7890`，`NO_PROXY` 不匹配。这不是对 SDK 实际路由的抓包或观测。

只对上述**当前选中路径**进行一次有界、无行情 GET 的前置诊断；没有直连回退，也未改代理或证书设置。脱敏机器日志在 `F:\codex-agnes\AI-trade-demo-002\artifacts\task-demo-003\preflight.json`（被 `.gitignore` 忽略）。

| 检查 | 实际结果 | 结论范围 |
| --- | --- | --- |
| 目标域名 DNS | 成功，本次解析为 `140.207.67.156` | 仅证明本机在检查时可解析；地址可能变化 |
| 选中路径 TCP | 连接本机 `127.0.0.1:7890` 成功 | 证明诊断 socket 到代理可达；未测试目标的直连 TCP 443 |
| 代理隧道 | 对目标 `:443` 的 CONNECT 返回 200 | 这是代理控制响应，不是行情接口 HTTP 响应 |
| TLS | 开启证书与主机名验证，握手抛出 `SSLEOFError: UNEXPECTED_EOF_WHILE_READING` | **当前选中诊断路径无法建立安全 TLS 连接**；未到行情 HTTP 请求或 SDK 解析 |

本次诊断实际使用仓库 `tools/diagnose_akshare_tls.py` 的 `proxy_info` 和 `tls_probe` 函数，仅调用选中路由一次。可在 PR #14 工作树中复现配置解析及同一路径的无 GET 握手（该命令会再次建立一条诊断连接，须按当时网络策略决定是否执行）：

```powershell
$env:PYTHONPATH = (Join-Path (Get-Location) 'src')
@'
import json, os, runpy, socket, time
import requests
ns = runpy.run_path('tools/diagnose_akshare_tls.py')
host = 'push2his.eastmoney.com'
url = 'https://' + host + '/api/qt/stock/kline/get'
proxy_url = requests.utils.select_proxy(url, requests.utils.get_environ_proxies(url))
route = 'proxy' if proxy_url else 'direct'
addresses = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
print(json.dumps({'proxy': ns['proxy_info'](proxy_url),
                  'no_proxy_match': requests.utils.should_bypass_proxies(url, os.environ.get('NO_PROXY')),
                  'probe': ns['tls_probe'](host, route, ns['proxy_info'](proxy_url), addresses,
                                           time.monotonic() + 20)}, ensure_ascii=False, indent=2))
'@ | & 'F:\codex-agnes\AI-trade-main-demo\.venv\Scripts\python.exe' -
```

## 验收状态与故障归因

| 项目 | 状态及证据 |
| --- | --- |
| GitHub/本地代码一致性 | **通过**：实际检查工作树等于 PR #14 head；不等于 `main`，且不包含 PR #13 UI 修复 |
| 代理配置解析 | **通过**：当前配置选择本机代理；实际 SDK 请求路线**未验证**，因为未执行 SDK 请求 |
| DNS / 选中路径 TCP / 代理 CONNECT | **通过**：见上表；目标直连 TCP **未执行** |
| 选中路径 TLS | **失败／环境阻断**：证书验证开启时 `SSLEOFError`；无法仅凭此判定是代理、隧道、上游还是中间设备的根因 |
| 真实 AKShare 行情请求 | **未执行**：前置安全连接失败即停止；请求次数 0；行情 HTTP 状态不适用，真实返回行数**未知** |
| SQLite 写入与读回 | **未执行**：没有行情响应或采集批次；插入数/读回数不适用，不能写成接口返回 0 行；未创建本任务测试数据库 |
| 历史 `network_error` 根因 | **未确认**：旧批次没有原始异常链；本次 TLS 失败只证明当前选中诊断路径的故障，不反推旧请求 |
| Streamlit、完整历史覆盖、长期接口稳定性 | **未执行／未验收** |

当前证据支持“选中代理路径的本次 TLS 握手失败”，证据强度为本机握手实测。它不支持“东方财富接口关闭”“代理一定有故障”或“行情为空”等判断。用户若自行关闭系统代理，后续应先重新解析配置、只检查新选中路径的 DNS/TCP/TLS，确认安全连接后才在独立验收中对固定参数发出最多一次行情 GET；记录真实 HTTP/异常链、返回/入库/读回和证据摘要。本任务不自动切换路径或重试。

验证：在 PR #14 工作树用该工作树 `src` 作为 `PYTHONPATH` 执行完整离线测试，退出码 0，**329 passed、1 skipped in 10.76s**；跳过项为需显式启用的真实 AKShare 测试。`python -m pip check` 退出码 0，`No broken requirements found.`。PR #14 工作树默认 `data/sqlite/local.sqlite3` 不存在，未访问或创建生产数据库。原工作树修改保持原样；本报告分支不修改业务代码、Schema、代理配置、TLS 或 main。

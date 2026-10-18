# TASK-009：GitHub PR 治理与腾讯 Demo 集成

日期：2026-10-18（Asia/Shanghai）。唯一执行模型 `gpt-6.1-sol / high`，用户确认本会话界面配置；工具未独立暴露运行时型号。风险等级 H，费用未知，真实行情请求预算 **0**。已读根目录 AGENTS、MODEL_ROUTING_POLICY v1.0、PROJECT_STATUS、LOCAL_MARKET_DEMO、数据/接口/验收契约及实际 TASK-008/A/B 文件，适用 G01–G12。不改变 Schema、时间可见性、默认东方财富源或生产数据库。

## 基线、工作树与保护

GitHub API 确认 main 为 `c65a3189daf72c1aa97b5930e3a22215bda3f1c8`。CLI fetch 低速超时，已记录，未伪报成功。基于同 SHA 的现有本地对象新建 `F:\codex-agnes\AI-trade-task-009`、分支 `codex/task-009-tencent-integration`；用 `git cherry-pick --no-commit` 提取 #13 `b31847f…`、#14 `365a01c…` 的 patch，没有合并旧分支。

| 已核查工作树 | HEAD 与工作区 | 处理 |
| --- | --- | --- |
| `F:\codex-agnes\AI-trade` | `cd1b2b1…`，TASK-004 分支；16 个暂存/未暂存 tracked 文件及未跟踪研究文件/工作树目录 | 原样保留，不复制到新集成 |
| `C:\Users\iyoyi\.codex\worktrees\task-004-resume\AI-trade` | `b53e5b7…`，治理分支，Git 干净 | 与 main 治理 tree 等价，未移除 |
| 原目录 `.worktrees/local-demo-verify` | detached `b3e4e31…`，Git 干净 | 未移除；Git 干净不证明 ignored 环境可丢弃 |
| 原目录 `.worktrees/task-004a-report-only` | `b0a1ba1…`，Git 干净，独有报告 | 保留 |
| `AI-trade-demo-002` | `365a01c…`，Git 干净 | 取 #14 已提交 patch |
| `AI-trade-demo-003` | `0172171…`，Git 干净 | 与 #15 远端 tree 相同，未混入报告 |
| `AI-trade-demo-004` | `6bb1ed0…`，Git 干净 | 与 #16 远端 tree 相同，未混入工具 |
| `AI-trade-main-demo` | `b31847f…`，4 个 tracked 修改，另有 008/A/B、005/006 报告/证据/测试/工具及未知文本 | 按下表选择性提取，原件及其余内容保留 |

提取前为两个有修改的工作树保存 status、index/work diff、文件 SHA-256 指纹，交付前复核；本地检查点为忽略目录 `artifacts/task-009/preserved-before.json`。没有 reset、clean、删除、改永久代理或虚拟环境安装。复用既有解释器只读运行工具，显式 PYTHONPATH 并核对导入模块来自新工作树，不执行旧 editable 路径中的业务实现。

## 实际提取与最小修正

| 来源 | 内容 | 处理 |
| --- | --- | --- |
| #13 | 点击编号去重、未知行数、原 AppTest、LOCAL-RECONCILE 报告 | 保留，腾讯共用点击门 |
| #14 | 白名单/有界异常链、保守失败阶段、2 个测试、DEMO-002 报告 | 保留，不用旧 TASK-008 ingestor 覆盖 |
| TASK-008 未提交文件 | tx_adapter、Demo/离线 UI 测试、腾讯 7 个原测试、指南、008/A/B 报告 | 选择性复制并作下述修正；历史报告副本追加校正，不改原件 |
| TASK-008 真实审计 | 成功状态、数量、时点、只读旧库核查摘要 | 提交脱敏摘要与文件哈希，不提交行情值、数据库或响应正文 |
| 005/006、008A 独立探针及其测试、未知文本文件 | 混在同工作区的其他任务材料 | 不纳入本集成，不删除 |

必要修正有四项：

1. **证据来源一致性**：原腾讯 source 已独立，但 manifest 的 provider/endpoint/symbol 仍误写东方财富。现在腾讯 fetch 与证据共用 `request_parameters`，正确写 `tencent`、`akshare.stock_zh_a_hist_tx`、`sh600000`；东方财富默认元数据及映射不变。旧 manifest 不追溯篡改。
2. **拒绝静默数值修复**：原 `int(volume)` 截断小数，`float` 接受布尔/文本。复用既有日期/数值守卫，要求非负 int64 股数、有限价格/金额，拒绝坏日期、OHLC、重复日期和字段漂移。腾讯 SDK 股/元值不二次乘除；仓储和 as_of 不改。
3. **页面诚实标记**：东方财富仍默认，腾讯需手动选择，失败不切源。代理字段改为“配置（推断）”，显示东方财富、腾讯行情及腾讯起始日探测域名的解析结果，未知保留未知，不显示凭据或声称观测到了 socket 路由。
4. **离线 CI 覆盖**：原 CI 只装 `[test]`，UI 会跳过，原腾讯测试又依赖实装 SDK。改为既有 `[test,demo]`，腾讯测试模拟版本/SDK 调用，不依赖 SDK 安装或网络，默认网络阻断不变。

## 复用的真实证据

本地原 `TASK_008_AUDIT.json` SHA-256：`2187bbe665ecfb4a449bb4a92b348b06f28d63e576a534ba4119d653841cae87`。它记录 `2026-10-18T05:31:33.635382Z` 的腾讯采集成功，返回/插入/读回 2/2/2。其临时库 `C:\Users\iyoyi\AppData\Local\Temp\task008-real-72un4ppq\real.sqlite3` 仍存在，本次以 URI `mode=ro` 检查：2 行，日期为 2026-10-14、2026-10-15，open/close/volume/amount 与原审计逐值一致，source 为腾讯、ingestion_runs=1、quick_check=ok。提交的 [脱敏摘要](evidence/TASK_008_AUDIT.json) 不含行情值，保留原文件和 request/response/result 的 SHA-256。

它仅证明旧版那次 SDK→SQLite 记录与现存旧库相符，**不证明本次新集成已通过真实网络**。原 SDK DataFrame 不证明原始调整键、HTTP 状态或完整 GET 数；008A 探针把 `request_count=1` 直接设为 SDK 调用次数，没有发送边界计数。旧报告中“1 次”不能当成已观察的一次 HTTP GET。本次没有重新采集。

## 执行命令与结果

Windows Python 3.12.14、pytest 8.4.2、pandas 3.0.6、Requests 2.34.2、Streamlit 1.66.0、AKShare 1.19.1；本任务未安装/升级依赖。

```powershell
cd F:\codex-agnes\AI-trade-task-009
$env:PYTHONPATH = 'F:\codex-agnes\AI-trade-task-009\src'
& 'F:\codex-agnes\AI-trade-main-demo\.venv\Scripts\python.exe' -m pytest -q
& 'F:\codex-agnes\AI-trade-main-demo\.venv\Scripts\python.exe' -m pip check
git diff --check
```

| 检查 | 实际结果与边界 |
| --- | --- |
| 相关采集/腾讯/UI 初轮 | 100 passed in 8.39s，退出码 0 |
| 最终完整离线套件 | **363 passed、1 skipped in 21.48s**，退出码 0；唯一 skip 为未显式启用的东方财富 live 手工测试 |
| 离线 Streamlit AppTest | **4 passed in 10.11s**，亦包含在最终套件；两源的启动/点击/rerun/新点击；模拟失败显示未知；模拟成功帧经真实临时 SQLite 读回与页面一致；production 哨兵路径未创建 |
| pip check | `No broken requirements found.`，退出码 0 |
| diff/文件范围/文档 | `git diff --check` 退出码 0；有限围栏与 14 个内部文件链接检查通过；无 Schema、生产数据库、原始行情响应或秘密。仓库无现成 Markdown lint，此有限检查不等于完整 lint |
| 本轮真实腾讯/东方财富请求 | **未执行，0 次**；复用旧证据，离线通过不等于真实链路通过 |
| 本轮 Edge/Chrome 实机 UI | **未执行**；AppTest 不等于浏览器端到端 |
| 生产适用性/生产数据库/样本外回测 | **未验收／未执行**；无生产初始化、部署、交易或策略实现 |

本机忽略日志：`artifacts/task-009/pytest-final.txt`、`pip-check.txt`。套件含 30 个腾讯单元用例、4 个 UI 用例；005/006/008A 探针测试未迁移，故本轮与旧工作区的 358 不是同一集合，不能直接据数量推断增减或回归。

交付前的保护复核实际通过：原 TASK-004 工作树检查 37 个文件、TASK-008 工作树检查 77 个文件，status、index diff、work diff 及文件哈希全部未变。输出保存在 `artifacts/task-009/preservation-check.json`。历史 008A/B 报告提及的审计原件留在旧工作树，本 PR 只提交 TASK-008 的已审查摘要，未将其他诊断原件冒充新证据。

实际变更文件共 18 个：`.github/workflows/offline-pytest.yml`；`src/ai_trade/demo_app.py`、`market_data/ingestor.py`、`market_data/tx_adapter.py`；`tests/manual/test_streamlit_demo_offline.py`、`tests/unit/test_akshare_ingestion.py`、`tests/unit/test_tx_adapter.py`；`docs/LOCAL_MARKET_DEMO.md`、`PROJECT_STATUS.md`、`IMPLEMENTATION_TASK_DEMO_002.md`、`IMPLEMENTATION_TASK_LOCAL_RECONCILE_001.md`、`IMPLEMENTATION_TASK_008.md`、`IMPLEMENTATION_TASK_008A.md`、`IMPLEMENTATION_TASK_008B.md`、`IMPLEMENTATION_TASK_009.md`、`PR_GOVERNANCE_TASK_009.md`、`evidence/TASK_008_AUDIT.json`、`evidence/TASK_009_GIT_AUDIT.json`。其中旧 PR 报告作为 patch 溯源保留，新报告不改写其历史结果。

## 剩余风险和交付边界

- SDK 实际先用 `get_tx_start_year` 探测（没有传入 timeout，且有额外起始日请求路径），再按年取数据；一次按钮/SDK 调用并非一个 GET，没有端到端总时限保证。本任务不改 SDK、不自动切源。
- SDK 在 `day` 缺失时可选 `hfqday/qfqday`，并先做 `drop_duplicates`；帧无法证明原始不复权键或去重前冲突。请求仍显式 `adjust=""`，但原始口径/冲突观测缺口是生产阻断项，需独立来源边界任务处理。
- 单位依赖固定 SDK 的归一化输出；只有旧 600000 最小样本有真实证据，不代表 SH/SZ 全市场、历史覆盖、ST/停牌、首次可得时刻/修订、授权或限流已验收。时点过滤无法补齐供应商证据。
- 新集成仍需独立 H 审查绑定最终 SHA。本次实现自检不冒称独立审查，治理矩阵/合并顺序/清理候选见 [治理报告](PR_GOVERNANCE_TASK_009.md)。

新 PR 目标 main、保持 Draft，自包含 #13/#14 patch 和 TASK-008；若用户先合并旧 PR，应更新基线、去除重复 patch 并重跑测试。提交 SHA/PR 链接以交付消息和 PR 元数据为准，避免自引用未来提交。没有合并/关闭旧 PR、删除分支或改 main，交付后停止等待审核。

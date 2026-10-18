# 项目状态与验收边界（2026-10-18）

## 当前 GitHub 状态（TASK-016 核验）

GitHub API 已确认最新 main 为 `693fab10fe7f88581fc326015556ddc0aa83c1ea`，PR [#18](https://github.com/fengjnah/a-share-quant-v1/pull/18) 已于 2026-10-18 合并，健康检查框架已进入 main；父提交为 `31a575f6834067749ea006931282e62e8f666a18`（PR [#17](https://github.com/fengjnah/a-share-quant-v1/pull/17)，TASK-009）。**代码合并不改变生产准入状态。** 本文件是当前状态索引；旧实施报告保留当时分支、测试和“待审”事实，不追溯改写。

本机没有 `refs/heads/main`。本轮 Git fetch 因 GitHub 443 连接失败，`origin/main` 缓存仍为 `31a575f…`，不能当作最新远端；最新 SHA 由成功的 GitHub API 确认。原仓库 `F:\codex-agnes\AI-trade` 的 TASK-004 修改和旧 Demo 的 TASK-008 修改全部保留。完整清单、SHA、哈希与整理方案见 [TASK-016 报告](IMPLEMENTATION_TASK_016.md) 和 [审计 JSON](evidence/TASK_016_BRANCH_AUDIT.json)。

## TASK-015：已合并，真实健康验收仍未完成

- 已实现并进入 main：独立健康模型/服务、请求预算、追加审计报告、CLI 与 daily/weekly/monthly 调度计划；默认离线，无自动切源。
- TASK-015 当时完整离线结果为 **412 passed、1 skipped**；TASK-016 在同一 main 文件树重新运行也是 **412 passed、1 skipped**（另有一条 pytest 缓存写入警告，测试退出码 0）。离线通过不能替代真实数据验收。
- **真实行情可用性尚未验收**；TASK-015/TASK-016 均未发起真实行情请求。独立连接探针未实现/未运行，connectivity_check 为 not_run。
- **真实交易日历和可信新鲜度尚未验收**。`health_cli.py` 目前没有输入已验证日历期望的参数，也没有向 `HealthService.check` 传入 `expectation`。服务 API 能显式接收 `CalendarExpectation`，但不等于 CLI 已接线；无日历时 expected_data_date / is_stale 保持 null，行情及 SQLite 成功也不能宣称 freshness 通过。
- 后续需独立审查日历来源、as_of、收盘截点和只读 CLI 接线；不得用星期推算、人工强制 known 或忽略未知来制造成功。
- **未安装操作系统计划任务**；周/月是可调用计划，仍需外部负责人串接。未初始化生产数据库、未部署。
- **腾讯仍为候选源，生产未获准**。许可、原始调整键、SDK 去重前冲突、历史覆盖、长期稳定性等缺口仍在。

详见 [TASK-015 历史实施报告](IMPLEMENTATION_TASK_015.md) 与 [健康检查说明](SOURCE_HEALTH_CHECKS.md)。本轮没有独立 H 审查通过的新增证据，不把用户合并或 CI 通过冒充该结论。

## TASK-009：集成已进入 main

PR #17 已合并为 `31a575f6834067749ea006931282e62e8f666a18`，腾讯候选适配器、来源元数据修正、数值校验及 #13/#14 的点击去重/未知行数/安全异常链修复均在 main。东方财富仍为默认源，腾讯手选，无自动故障转移。当时离线 **363 passed、1 skipped**；本次不重复旧网络请求。

旧 TASK-008 的最小两行成功证据已在 TASK-009 中复核并脱敏归档，不代表新集成或健康框架通过真实网络端到端验收。原报告的“1 次”仅能证明一次 SDK 采集调用，不能证明完整 HTTP GET 数；腾讯许可和口径/覆盖问题未解决。详见 [TASK-009 历史报告](IMPLEMENTATION_TASK_009.md) 与 [历史治理矩阵](PR_GOVERNANCE_TASK_009.md)，最新 PR 状态以 TASK-016 为准。

## GitHub 集成状态

- 已合并：#1（TASK-002）、#5（TASK-003）、#6（TLS）、#7（Demo）、#8（工程基线）、#9（归档）、#10（TASK-004）、#12（治理）、#17（TASK-009）、#18（TASK-015）。
- 已关闭且未合并：#2 / #3 / #4，由 #5 / #6 / #7 替代。
- 仍开放：#11（004A 报告及重复 TASK-004 代码）、#13 / #14（修复内容已随 #17 整合，PR 自身未合并）、#15（历史报告）、#16（诊断工具/报告，base 仍为 #14 分支）。不自动关闭或合并。
- TASK-004 模型/存储已经由 #10 合并；真实证券历史、ST、退市覆盖与完整可信日历尚未验收。004A 报告仍不在 main：历史主数据请求 TLS 失败，新浪日历有一次响应证据，真实参考数据 SQLite 验收未执行，不能当作完整通过。

## 代码与文档映射

| 功能 | 主要代码 | 相关文档 | 验收 |
| --- | --- | --- | --- |
| SQLite 初始化、事务、迁移 | `src/ai_trade/storage/db.py`, `schema.py` | `IMPLEMENTATION_TASK_002.md` | 离线单元测试覆盖 |
| 日线验证、追加版本、时点读取 | `src/ai_trade/data_access/` | `DATA_CONTRACT.md`, `IMPLEMENTATION_TASK_002.md` | 最小数据契约测试；不是完整多数据集服务 |
| 证券主数据、日期级日历 | `src/ai_trade/reference_data/`, `security_master/`, `trading_calendar/`, `storage/reference_schema.py` | `IMPLEMENTATION_TASK_004.md` | #10 已合并模型/存储及离线测试；真实来源、历史覆盖未验收 |
| AKShare 历史日线、证据、采集 | `src/ai_trade/market_data/` | `IMPLEMENTATION_TASK_003.md`, `IMPLEMENTATION_TASK_003B.md` | 离线测试；指定真实批次见 TASK-003C |
| TLS 诊断 | `tools/diagnose_akshare_tls.py` | `IMPLEMENTATION_TASK_003C.md` | 诊断单元测试及指定环境的历史验收 |
| 本地 Streamlit 演示 | `src/ai_trade/demo_app.py` | `LOCAL_MARKET_DEMO.md` | 已集成，真实 UI→网络→SQLite 端到端未验收 |
| CI | `.github/workflows/offline-pytest.yml` | 本文件 | Python 3.11 pytest；不等于线上集成验收 |

## 已知缺口

- TASK-004：main 已实现稳定实体身份、已知名称时间线、上市/退市边界、日期级日历、不可变版本与双时间可见性查询；真实历史来源/覆盖未验收，历史 ST/停牌、代码变更别名、完整交易会话与可重开快照仍未实现。本治理任务不运行 TASK-004A，也不新增数据源或更改这些功能状态。
- 未实现：全市场增量采集、复权及公司行为、市场宽度、期货持仓/恐贪、选股、择时、风控、回测、日报、AWS 发布。
- 离线测试通过不能证明 Streamlit 页面在用户 Windows PC 的代理/TLS 环境可正常采集；该验收必须使用实际 Windows 会话。
- Streamlit 临时 SQLite 是会话隔离的演示库，不能用来声称生产持久化已验收。
- 当前 CI 安装 `.[test,demo]`，包含离线 Streamlit AppTest；不安装 AKShare 可选依赖、不执行真实行情请求或 Edge/Chrome 实机 UI。

## 本地 Streamlit 端到端验收步骤

先从最新 `main` 拉取代码，按 `LOCAL_MARKET_DEMO.md` 安装 `.[akshare,demo]` 并启动。应在浏览器中人工完成：

1. 页面可启动、输入默认代码 `600000` 和指定日期；点击前不发送真实行情请求。
2. 点击“采集真实行情”后，核对真实请求结果、返回/入库行数、来源、观察时间和响应摘要；不以空表冒充成功。
3. 核对页面显示的会话临时 `demo.sqlite3` 路径，以及页面从同一 SQLite 数据库读回的行情。
4. 失败场景展示网络/TLS 错误，不关闭证书验证；不自动绕过组织代理政策。
5. 确认不会读取或写入 `QUANT_DB_PATH` 指向的业务数据库，不泄露证据文件或密钥。
6. 保存脱敏的执行时间、环境、请求参数、结果、行数、数据库读回证据和问题记录。未完成前保持“待验收”。

可在 Windows PowerShell 中执行：

```powershell
# 在从已核实 main SHA 建立的干净任务工作树中执行；
# 本机尚无本地 main，不在原 dirty 工作树中切换、覆盖或拉取。
.\.venv\Scripts\python.exe -m pip install -e ".[akshare,demo]"
$env:NO_PROXY = "push2his.eastmoney.com"  # 仅在组织网络策略允许直连时使用
.\.venv\Scripts\python.exe -m streamlit run src/ai_trade/demo_app.py
```

**验收状态：待用户 Windows 本地真实操作与证据。** GitHub 云端测试不等同于本机 GUI、代理与真实源端到端测试。

## 后续优先级

1. 以治理模板安排后续任务，并另行指派独立 H 治理审查；TASK-004 真实来源/历史质量继续独立验收，不因 #10 合并而视为通过。
2. 在 Windows 本地完成 Streamlit 真实端到端验收，记录缺陷。
3. 为主数据/日历选择有许可及发布时间证据的可靠来源，独立验收覆盖和缺口；不从当前列表倒推历史。
4. 在数据可得性与历史身份可靠后，推进市场状态、选股、回测。

## TASK-GOV-001：历史实施记录（规则已随 PR #12 合并）

这是 2026-10-17 新增制度，不追溯声称历史任务曾按此执行。五份规则文档已随 PR #12 进入 main；下文保留当时的执行记录。独立治理审查仍没有本轮可核实的完成证据，规则合并不等于审查通过：

| 文件 | 职责 |
| --- | --- |
| [根目录 AGENTS.md](../AGENTS.md) | 开始检查、规则读取、模型固定、数据/安全约束、阻断与证据交付 |
| [MODEL_ROUTING_POLICY.md](MODEL_ROUTING_POLICY.md) | L/H 分工、风险路由、2—4 项批次、独立审查与升级条件 |
| [TASK_TEMPLATE.md](tasks/TASK_TEMPLATE.md) | 强制填写唯一模型/推理档位及必读确认、范围、测试、批次/升级记录 |
| 本项目状态 | 当前治理状态与任务采用入口；不代替业务功能验收 |
| [对话归档新增章节](TRADING_SYSTEM_CONVERSATION_ARCHIVE_20261017.md#11-模型路由与成本治理新增决策) | 追加本轮决策，保留前十节历史内容 |

本任务执行记录：

- 唯一执行模型 **gpt-6.1-sol**，固定推理强度 **high**，分配等级 **H**（治理规则设计）；由用户于本轮确认当前界面所示配置，工具未提供独立运行时模型证明。不调用其他模型/子代理，不把本任务自检称为正式独立审查。费用/额度数值未知，未声称成本节省。
- 开始已读 PROJECT_STATUS、DECISIONS、对话归档及相关数据/接口/验收契约；新增文件后显式读取 AGENTS、模型路由制度及任务模板。适用 **G01—G12**：保护原工作区、固定模型、五文件范围、保留时间与未知语义、仅离线验证、独立审查另立任务。
- 前置检查未发现 AGENTS、MODEL_ROUTING_POLICY 或任务模板，目标分支本地/远端均不存在，无重复规则；现有 ADR 不变。原本地 TASK-004 的 16 个未提交文件、暂存状态及检查点均保留。
- Git CLI 两次获取 main 遇连接重置；通过 GitHub 连接器读取最新分支及已验证签名的提交对象，与本地现有树/父提交匹配并校验精确 SHA 后创建分支，没有以旧 origin/main 假冒最新基线，也没有修改 main。
- 允许范围仅五份文档；不修改生产代码、Schema、行情或默认网络阻断。可验证验收为五文件范围、内部链接/Markdown 有限检查、归档仅追加、完整离线套件、依赖检查及原工作区哈希/状态核对。诊断性修复最多两次；契约或核心测试失败立即按 G10 阻断。
- 实际测试：Windows 既有虚拟环境运行 `python -m pytest -q`，**327 passed, 1 skipped in 10.84s**，退出码 0；跳过既有需 `--run-akshare-integration` 显式开启的行情测试。`python -m pip check` 退出码 0，输出 `No broken requirements found.`。真实网络数据测试、本地 UI 端到端、样本外回测均未执行，本轮只有文档改动。
- 仓库未配置 Markdown lint 工具，未为本任务安装依赖；有限检查验证代码围栏/表格基本结构、**22 个内部链接及锚点**、归档原内容前缀完全保留、五文件范围及 Git diff 空白检查。此检查不等于完整 Markdown lint 或正式治理审查。本地输出位于忽略目录 `artifacts/task-gov-001/`，不提交运行产物。

采用方式：后续新 TASK 从模板开始，填好唯一模型/档位及实际核验来源，先显式阅读规则再实现；L 批次登记 TASK/PR/SHA 与审查计划，高风险另行 H 审查。治理制度本身待用户另行安排独立审查（建议编号 **TASK-GOV-002**，尚未创建/启动、H 模型/档位待指派），检查自洽性、绕过路径和 Codex 工作流兼容性；本任务不执行该审查。规则落库、独立审查通过、自动门禁落实是三个不同状态；本次没有新增运行时模型锁、CI 治理检查器或分支保护。

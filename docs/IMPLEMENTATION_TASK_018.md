# TASK-018：正式任务看板与动态进度管理实施记录

日期：2026-10-18（Asia/Shanghai）。状态：**PARTIAL，等待独立审查及用户合并**。代码、离线验证和实际浏览器观察分别记录；未启动其他业务 TASK。

## 执行与基线

- 唯一执行模型：`gpt-6.1-sol / high`，H。依据为本会话用户对当前界面的明确确认；工具未提供独立运行时型号/费用元数据，没有调用其他模型或子代理，也不将自检称作独立审查。
- 开始前实际读取：`AGENTS.md`、`docs/MODEL_ROUTING_POLICY.md`、`docs/tasks/TASK_TEMPLATE.md`、`docs/PROJECT_STATUS.md`，并核对架构、数据/接口契约、验收文档、TASK-004/004A/009/015/016/017 报告、实际代码和测试。基线均为下述 main 或明确标出的历史文件。未发现本任务子目录 override。
- G01/G02：成功执行 `git ls-remote origin refs/heads/main`、显式 fetch 并核对引用，得到 **`f1382c10f2c3d356be6e059aad5611d15d687a62`**；GitHub API 确认 PR #19/#20 均已合并。交付复核时又一次 ls-remote 被连接重置（curl 56），随后成功的 GitHub branches/main API 再次确认同一 SHA；没有把失败操作当作最新证据。
- G03/G04：本 TASK 固定上述模型/档位；边界为管理数据、展示、重算、验证与文档。G05/G12：治理规则/进度门槛必须另行独立 H 审查，本会话只做实现与普通自检。G06/G07：不改行情时间契约，未知、历史和当前验收分开。G08/G09：默认离线、隔离测试、不访问生产库或真实行情、不改 main。G10：未发现需要扩大业务修改的阻塞。G11：实际命令、输出与未验证项见下文。
- 独立工作区：`F:\codex-agnes\AI-trade-task-018`，分支 `codex/task-018-project-board`，起点精确为上述 SHA。未移动本地 main：`AI-trade-dev/main` 仍为 `6987ed1d1435e19067fdd218beb68763eaa76f83`，相对当前 origin/main 落后 2 个提交且干净。这是保留现场，不能把它称作已同步的最新开发基线。

冻结的 GitHub 状态依据见 [TASK_018_GITHUB.json](evidence/TASK_018_GITHUB.json)。#11/#13/#14/#15/#16 的开放状态、已随 #17 整合的代码、旧网络失败和未进入 main 的报告均按证据分别导入；不关闭或合并这些 PR。

## 数据与进度口径

正式源为 [TASK_METRICS.json](TASK_METRICS.json)，[JSON Schema](TASK_METRICS.schema.json) 使用 Draft 2020-12。两个 Markdown 视图由同一文件生成：[任务看板](TASK_BOARD.md)、[十阶段路线图](ROADMAP_V1_3.md)。Demo 和独立页面读取同一份数据，没有第二份硬编码任务列表。

本版 40 个 TASK，含 15 个仅建议立项的任务；建议任务保持 PLANNED，未创建、执行或完成。历史任务的实际模型/工时若无可靠记录则为 null；唯一指定型号中的续执行建议不冒充历史实际型号。工时范围是未经实测校准的估计，实际费用未知。

计算为：`Σ(阶段权重/100 × 阶段内任务权重/100 × 通过验收点权重/100) × 100%`。三层权重分别校验总和为 100；仅带匹配类型证据的 PASS 计分。PLANNED/REJECTED 计零，PARTIAL/BLOCKED 只计已通过点。历史诊断零权重避免同一成果反复加分；失败后保留旧快照，最新快照改变对应分数及下游依赖缺口。

七类初始权重 10/25/20/10/20/10/5 被细分为十阶段 **4/6/8/17/8/12/10/20/10/5**。这是待审的规划分配，不是客观工时完成率、收益概率或生产就绪率；未验收的未来业务仍占分母。阶段依赖描述整体退出顺序，具体任务只依据显式验收点依赖推荐，不能由阶段编号推断通过。

首次保守导入为 **18.79%**。实际完成本轮结构、计算器、离线回归及浏览器验证后，人工审阅完整反馈并追加第 41 条事件，重新计算为 **21.67%**；TASK-018 自身为 80%，独立审查及合并仍未通过。用户新增开源制度后又追加审查范围说明，分数不变，没有降低门槛或改写前 41 条事件。后续 PR 元数据也只能以新事件追加。

推荐下一项为 **TASK-018-REVIEW**，只是满足依赖的立项建议，没有创建或执行。审查应绑定最终提交 SHA，覆盖进度权重、历史证据真实性、依赖门禁、候选反馈、行情解耦及新开源制度/AGENTS/模板。正式策略回测仍依赖数据质量、历史可得时间、风险执行约束和独立未来函数审查。

## 实现及变更范围

| 路径 | 实际作用 |
| --- | --- |
| `src/ai_trade/project_progress/core.py` | 严格 JSON/Schema、权重/引用/DAG、时间顺序/哈希链、分数/依赖/推荐、只读候选反馈 |
| `src/ai_trade/project_progress/__main__.py` | 只读重算/失败模拟、一致性检查、独占新文件候选、显式生成两份 Markdown |
| `src/ai_trade/project_progress/render.py` | 从正式 JSON 生成任务看板与十阶段路线图 |
| `src/ai_trade/project_progress/page.py`、`app.py`、`__init__.py` | 只读 Streamlit 页面及独立入口，不导入行情或数据库模块 |
| `src/ai_trade/demo_app.py` | 顶部工作区选择；项目进度分支在导入行情/存储、初始化 Demo 数据库之前停止执行 |
| `tests/unit/test_project_progress.py` | 分数独立重算、无证据/错误类型/非法权重、历史前缀、依赖、CLI 只读/候选防覆盖、文档链接等 |
| `tests/manual/test_project_progress_offline.py` | 默认执行的离线 AppTest：阻断网络/库初始化、行情失败仍可打开看板 |
| `pyproject.toml` | 增加直接依赖 `jsonschema>=4,<5`，进行真实 Schema 校验；未引入其他数据库或服务 |
| `docs/TASK_METRICS.json`、`.schema.json`、`TASK_BOARD.md`、`ROADMAP_V1_3.md` | 结构数据、Schema 与两份可重生成视图 |
| `docs/evidence/TASK_018_GITHUB.json`、`TASK_018_ACCEPTANCE.json`、`TASK_018_FINAL_CHECKS.json` | 冻结的 GitHub、浏览器与最终验证摘要；旧证据不随新结果覆盖 |
| `docs/PROJECT_STATUS.md`、`docs/LOCAL_MARKET_DEMO.md` | 当前基线/待审边界、只读页启动和操作说明 |
| `docs/OPEN_SOURCE_RESEARCH_POLICY.md`、`AGENTS.md`、`docs/tasks/TASK_TEMPLATE.md` | 用户追加的调研制度、执行入口和开始记录要求 |
| 本报告 | 实际执行、证据、限制与交付说明 |

JSON 重复键、NaN、非法状态/字段、循环依赖、无证据通过、将代码冒充独立审查/生产/合并均会拒绝。反馈只能追加同一计划版本的事件/证据；需要修改权重、TASK 定义或验收标准时，另建人工计划修订 PR 并保留旧版本依据。仅哈希链不防止整链重算，必须同时使用可信旧文件 `--baseline` 和 Git diff 审查。文件 SHA256 是一致性凭据，不是内容真实性或许可证认证。

## 用户追加：开源调研制度

本轮按用户“将开源调研制度写入仓库”的明确要求新增 R01—R08；不是对 TASK-REF-001 的历史记录追溯改写。制度要求实现前检查现有研究，对新模块/重要接口/依赖/数据源及高风险设计有界阅读实际源码、测试、许可证和数据授权，保留采用/适配/拒绝/延后的依据与固定版本。纯文字/Git 现场保护等可记录具体不适用理由，不机械全面调研。

专项包括财务发布时间、历史实体/成分、复权版本、停牌/涨跌停、信号/成交时点及未知数据；软件许可与数据许可分列。RQAlpha 非商业条款、Backtrader GPL-3.0 为**需按拟用版本重新核实的议题**，本任务没有进行新的外部许可证核验、源码引入或真实数据调研。新制度和根规则入口待独立 H 审查，原 TASK-REF-001 本地材料仍待审。没有安装调研定时任务或调用另一个执行模型。

## 环境、测试与可复现命令

实际解释器是已有验证环境 `F:\codex-agnes\AI-trade-main-demo\.venv\Scripts\python.exe`，通过显式 PYTHONPATH 加载本任务工作树代码。未声称本任务新建/安装了独立 .venv，也未修改旧环境依赖。Python 3.12.14、pytest 8.4.2、jsonschema 4.26.0、Streamlit 1.66.0、pandas 3.0.6、Requests 2.34.2、AKShare 1.19.1；pip check 退出码 0。jsonschema 已安装，未运行依赖升级。干净环境仍按项目 `pip install -e ".[test,demo]"` 安装；本轮不是一次全新环境重装验收。

```powershell
Set-Location F:\codex-agnes\AI-trade-task-018
$taskPython = 'F:\codex-agnes\AI-trade-main-demo\.venv\Scripts\python.exe'
$env:PYTHONPATH = 'F:\codex-agnes\AI-trade-task-018\src'
& $taskPython -m ai_trade.project_progress --check-docs
& $taskPython -m ai_trade.project_progress
& $taskPython -m ai_trade.project_progress --simulate TASK-002 offline FAIL
& $taskPython -m pytest -q
& $taskPython -m pip check
git diff --check
```

完成任务后，人工从最新快照制作完整 feedback.json，填实际证据而非自动抓取结果：

```powershell
& $taskPython -m ai_trade.project_progress --propose feedback.json --candidate candidate-new.json
# 审阅候选差异，以独立 PR 接纳，保留所有历史前缀；不自动替换正式文件。
& $taskPython -m ai_trade.project_progress --baseline trusted-old-metrics.json --check-docs
# 正式数据经过人工修改后，显式重新生成两个 Markdown：
& $taskPython -m ai_trade.project_progress --render
```

实际验证记录：

| 检查 | 实际结果与范围 |
| --- | --- |
| 首轮相关测试 | 25 passed；之后追加反例测试 |
| 第一轮完整回归 | 442 passed、1 skipped，退出码 0 |
| 补充反例后的完整回归 | 444 passed、1 skipped，46.84 秒，退出码 0；冻结摘要见 TASK_018_ACCEPTANCE.json |
| 新制度入口和最终文档回归 | **445 passed、1 skipped，40.87 秒，退出码 0**；`pytest-delivery.txt`，不覆盖前述冻结证据 |
| 历史追加后的最终回归 | **445 passed、1 skipped，40.47 秒，退出码 0**；`pytest-after-history.txt`。中间单元复查曾 1 failed、30 passed：夹具把最后事件误当规划任务；改为按 SUGGESTION 身份定位，未放宽校验，再跑完整套件通过 |
| 依赖检查 | `No broken requirements found.`，退出码 0 |
| JSON/Schema/文档/历史前缀 | `--check-docs --baseline` 退出码 0；项目/阶段/任务权重合法，文档从同源生成 |
| 失败动态重算 | TASK-002 的 offline 模拟 FAIL，21.67% → 20.65%，显示 TASK-003/TASK-004 等依赖缺口；不写正式 JSON |
| 独立审查/PR 合并/生产 | 未执行/未合并/未准入，不计相关通过点 |

唯一跳过项是需显式开启的 AKShare 真实集成测试，本任务禁止发真实行情请求，不能称其通过。默认全套测试保持网络阻断；合成夹具只验证行为。

## 实际浏览器观察与安全边界

本轮使用 Codex 工具库存中可用的 **ChatGPT 内置浏览器**，实际打开 `http://127.0.0.1:8518/?view=progress`：观察初始 18.7900%、十阶段进度、七种状态统计、40 项详情；切换行情工作台触发预设数据库初始化失败，再切回项目进度正常展示。选择 TASK-004A，实际显示 BLOCKED、历史主数据 FAIL、SQLite/审查 UNVERIFIED、PR #11 OPEN。人工追加验收后重新加载，实际显示 21.6700% 和推荐 TASK-018-REVIEW。

截图与 AX 观察在本任务会话中，未虚构磁盘截图路径。该工具没有提供 Edge/Chrome，所以**没有验证 Windows Edge/Chrome**。本机测试启动器只监听 loopback、禁用遥测，额外阻断外部 socket/Requests 发送和数据库初始化；保护日志中 Requests/外网 socket 尝试均为 0，只有主动切换行情页造成的 1 次被阻断初始化。指向不存在临时路径的 production sentinel 未创建；不是生产库验收。实际源码没有把这些诊断钩子写入业务逻辑。

常规查看命令（未包含测试启动器的故障注入）：

```powershell
& $taskPython -m streamlit run src/ai_trade/demo_app.py --server.address 127.0.0.1
# 打开启动日志给出的本地地址，加 ?view=progress；或使用独立页：
& $taskPython -m streamlit run src/ai_trade/project_progress/app.py --server.address 127.0.0.1
```

本轮未点击真实采集，未运行真实接口、样本外回测、生产初始化/部署或计划任务。离线 UI 行情错误由明确标记的测试钩子/合成失败造成，不当作供应商当前真实失败证据。

浏览器测试服务已在验收后停止。Streamlit 输出有 `use_container_width` 弃用提示；另观察到一次 Windows asyncio 连接重置回调日志，页面随后重新加载仍正常展示。未将其写成行情网络错误，也没有为处理警告修改现有行情功能；未来 UI 兼容性维护应另行验证支持的最低版本。

## 现场保护、风险与交付复核

外部日志目录：`C:\Users\iyoyi\AppData\Local\Temp\task-018-20261018`。包含 before/post 状态、暂存/未暂存补丁、文件哈希、pytest 日志、依赖输出、候选反馈、重算结果和 browser-guards.jsonl；原始工作区补丁不提交仓库，以免带入未审内容。

原 13 个工作树、942 个纳入清单的文件逐项比较：HEAD/分支、完整状态、索引内容、暂存/未暂存补丁、未跟踪清单和文件哈希均保持。原 TASK-004 的 README/报告/测试改动及旧 Demo 的 TASK-008 内容没有移动或复制；没有删除分支、目录或 worktree。清单排除了 .venv、字节码、pytest 缓存等可重建运行产物，不声称对整个磁盘完成审计。

交付复核：Git 2.53.0.windows.3；`git diff --check` 退出码 0。对本任务 Markdown 做了代码围栏配对和本地文件链接存在性检查，另检查常见凭据模式/禁止的数据库等产物，均无命中；仓库未配置 Markdown 专项 linter，不能把有限检查称作完整格式、法律或秘密审计。复核脚本曾因旧 detached HEAD 的正常 symbolic-ref 退出码 1 停止，改为显式接受该只读状态后完成，并非旧工作树损坏。

未解决事项：首版权重和历史证据导入需独立审核；历史模型/实际工时仍有缺失；历史真实源证据不证明今天可用；TASK-004A/可信日历/新鲜度、腾讯原始口径和许可、后续业务及生产准入仍未验收。治理规则本身待独立 H 审查，不等于已部署强制 CI 门禁。

交付仅独立 Draft PR，不合并；PR/提交信息由实际创建结果提供。推荐下一步是对冻结 SHA 执行独立 TASK-018-REVIEW，用户未批准前不启动。

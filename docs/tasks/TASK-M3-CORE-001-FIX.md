# TASK-M3-CORE-001-FIX：H1/H2/M1 修复与交接

## 1. 身份、目标与实际基线

- 类型：implementation；H，涉及身份、质量状态和诊断准入。只修复独立审查 H1/H2/M1，不批准旧 PR，不部署、不接账户、不解除 M3 页面/策略门禁。
- 审查对象：`edff6ed0dc0093f1b531b0f3d52a087212516a2c`；原 base：`f46347bb492fd8474e38f5fa786a8c81a47c8a6d`。
- 阶段0远端实际状态：PR #32 已于 2026-10-19T16:47:39Z 合并，head 未改变；Issue #33 仍 open。本任务没有执行合并或关闭 Issue。用户提供的“PR 尚未合并”已与当前事实不符，不能沿用旧分支发布假设。
- 最新 main / 本修复基线：`2e36434a9a5d3ce540a58c04869bcd2e3c17ffd3`，由 GitHub branch 与 Git commit API 独立确认。父提交 `954cc78cc173f99d6ccc89e3cf75f1c97a4324c3` 仅增加 AWS 资源清单；与被审文件树相比也仅多出 `docs/operations/AWS_RESOURCE_INVENTORY.md`，不修改它。
- Git HTTPS ls-remote/fetch 连接失败。通过 API 读取公开 Git 对象、导入唯一缺失 blob，按原始签名载荷重现 main；所有 blob/tree/commit 的 Git SHA 逐字节匹配才建立 `codex/m3-core-001-fix`。main 签名 verified=true；父提交为 unsigned，未冒称有签名。导入脚本/原始 API 数据仅在本机临时目录。
- 初始 tracked 干净，未跟踪 `.worktrees/`、两条 TASK-004 stash、16 个 worktree 保留。不 reset/clean，不清理或覆盖其他工作区。

## 2. 唯一执行配置与预算

- OpenAI / Codex Desktop，唯一模型 `gpt-6.1-sol`，固定推理 `high`。
- 证据：本会话运行日志 `turn_context`，2026-10-19T16:53:43.550Z。旧 REVIEW 的 `xhigh` 已结束，不混记为本 FIX；本任务中不切换、不委派、不调用外部模型。
- 用户要求额度不足前交接、未完明早继续。本轮初始共享5小时窗口已用86%（剩余14%），周窗口已用69%（剩余31%）；由宿主 usage 工具核验。剩余约5%前保存交接，不购买或使用重置额度；实际费用未知，不能把共享变化归因于本任务。
- 同一验收问题最多两次不同诊断性修复；非预期核心回归失败暂停扩大范围。已知审查反例的修复前红测是预先声明的复现，不掩盖为通过。

## 3. 已读、规则与范围

- 实际读取：根 AGENTS.md、MODEL_ROUTING_POLICY v1.0、TASK_TEMPLATE、OPEN_SOURCE_RESEARCH_POLICY v1.0、PROJECT_STATUS、DECISIONS、DATA_CONTRACT、INTERFACE_CONTRACT、M3_CORE_CONTRACT、M3_CORE_SOURCE_ACCEPTANCE、原任务记录、M3 核心实现/契约/测试，以及既有 text_field 和 ReferenceResult。
- 适用 G01—G12：实际基线、固定配置、保留 UNKNOWN 与时间语义、离线验证、生产/Git边界、有限修复和绑定新 SHA 的独立审查。无适用子目录 AGENTS/override；不改治理制度。
- 调研：复用既有研究；本次是已定位的校验漏洞修复，不增加数据源/依赖/算法框架。复用现有 `data_access.validation.text_field` 与原因码，既有 Qlib/Pandera 采用记录不扩大为新来源/授权认证；不重复全面外部调研。
- 允许：`market_analysis_core.py`、必要的核心回归测试/夹具、M3 候选契约说明及本任务记录。若无需新枚举则不改 JSON Schema。禁止 SQLite/ReferenceResult/CFFEX底层版本链、时间口径、旧页面/策略、生产或 AWS 变更。
- 本聊天曾执行旧 REVIEW；现在明确执行独立编号 FIX，不将修复自检称为独立复核。后续复核必须由新的独立审查上下文承担，本实现会话不批准自己的新 SHA。

## 4. 修复约定与验收

- H1：所有可见参与记录的 source，以及价格/显式提供的 symbol，逐行按既有 text_field 校验：字符串、非空、首尾无空白、最多256字符、无控制字符；不自动 strip/coerce/fill/drop，必须精确匹配声明身份。错误 INVALID_DATA/BLOCKED。
- H2：逐行显式 accepted 才可 L2；显式非法/拒绝/隔离状态 INVALID_DATA/BLOCKED。未提供或空质量状态保持 UNKNOWN，research 仅 L1，strict_backtest/paper_trade 阻断，不从 Receipt 默认 accepted。CFFEX 已有模型无质量字段，核心包装入口需显式传质量状态，默认 UNKNOWN；不改底层模型或认证边界。
- M1：存在 market_amount_cny 列时，所有参与值须为非布尔、有限、非负实数；None/NaN/字符串/无穷/非法类型返回带字段、日期、标识的 INVALID_DATA/BLOCKED。真实0保留。整列缺失仍属于必要因子缺失，不补零。
- 先跑针对性红测，再修实现、定向回归、M3/CFFEX/时间/全A/L1-L3回归，最后完整离线 `pytest -q -p no:cacheprovider`、pip check、diff check。所有测试绑定当前仓库 src，不采用其他 checkout 的旧 editable 代码。
- 解释器：现有 `F:/codex-agnes/AI-trade-main-demo/.venv/Scripts/python.exe`；命令显式设置 `PYTHONPATH=F:/codex-agnes/AI-trade/src`、PYTHONUTF8/PYTHONIOENCODING；网络默认阻断、临时数据库。无行情网络请求。

## 5. 初始状态与交接检查点（历史，当前见第7节）

- 状态：IN_PROGRESS，尚无修复提交/PR，不是 READY_FOR_INDEPENDENT_REVIEW。
- 已完成：工作区/远端核验、精确 main 对象恢复、创建修复分支、确认 H1/H2/M1 对应现有代码。
- 待办：新增红测；最小修复与调用方/夹具适配；定向和完整离线验证；更新本记录实际结果；提交新 SHA；新 PR；核验 CI；交给独立 H 复核。
- 允许网络仅 GitHub 代码/提交/CI证据和 PR 发布；真实行情网络/UI端到端/OOS均未执行，不部署、不接账户。
- Issue #33 保持开放；PR #32 已合并是外部状态，不表示审查通过。修复 PR 仍须等待绑定新 SHA 的独立 H 审查，M3 改造门禁保持。
- 若额度不足：保留当前分支、diff、失败次数和日志；记录精确下一条命令，再安排 Asia/Shanghai 明早恢复。恢复必须重新核验同一模型/强度、Git与远端，不重写已完成工作、不清零失败计数。

## 6. 额度交接：2026-10-20 凌晨（历史，当前见第7节）

- 状态：BLOCKED（额度收束，非代码验收通过）；共享5小时窗口已用96%、剩余约4%，周已用70%。未使用重置额度。保存现场后按用户要求明早继续。
- 已创建本聊天一次性续接 automation `m3`：2026-10-21 09:00（Asia/Shanghai），ACTIVE；从本记录恢复，若已交付READY则不重复执行，不把自动续接当独立审查。首次创建因缺destination和含DTSTART被参数校验拒绝，随后以thread目的地及限定10月21日的一次性规则创建成功。
- 当前分支 `codex/m3-core-001-fix`，HEAD 仍是基线 `2e36434a9a5d3ce540a58c04869bcd2e3c17ffd3`；尚无修复提交、新 SHA、远端修复分支或新 PR，不得标 READY_FOR_INDEPENDENT_REVIEW。
- 未提交范围仅5个任务文件：core.py、原核心测试（为合法夹具显式补 accepted，不降低断言）、新增 test_market_analysis_core_validation.py、M3_CORE_CONTRACT.md、本任务记录。原 `.worktrees/` 和 stash 不动。
- H1：复用 text_field 逐行校验所有参与身份；H2：原始质量 UNKNOWN 不默认 accepted、拒绝/隔离立即阻断、CFFEX 包装入口显式 quality_status 默认 None；M1：所有参与成交额先校验类型/有限性/非负，不跳过 None/NaN；市场失败原因和缺失字段向恐贪传递。新增码/Schema/依赖/底层存储均未改。
- 修复前预期红测：`python -m pytest -q -p no:cacheprovider tests/unit/test_market_analysis_core_validation.py::test_review_counterexamples_fail_closed --junitxml=artifacts/m3-core-001-fix/before.xml`，退出1，4 failed（H1-source/H1-symbol/H2-quality/M1-turnover），日志 before.log。不是未说明的回归失败。
- 第一次修复后定向：`python -m pytest -q -p no:cacheprovider tests/unit/test_market_analysis_core_validation.py tests/unit/test_market_analysis_core.py --junitxml=artifacts/m3-core-001-fix/targeted.xml`，退出0，1463 passed，64.90秒；日志 targeted.log。含1421个新增参数化实例和42个原核心测试；覆盖三个模式、各入口、首/中/末行、序列化Schema、合法对照及原时间/分母/L3断言。
- 无非预期失败或第二次诊断性修复；不重置失败计数。当前实现仍需完整回归和普通 diff 自检，定向绿灯不等于独立审查通过。
- 已执行 `python -m pip check`，退出0，No broken requirements found；`git diff --check`退出0。artifacts/m3-core-001-fix 已由 git check-ignore 证实忽略。原测试输出未覆盖。
- 实际解释器 F:/codex-agnes/AI-trade-main-demo/.venv/Scripts/python.exe，Python3.12.14；pandas3.0.6、pytest8.4.2、jsonschema4.26.0、Streamlit1.66.0、AKShare1.19.1。实际导入 `F:/codex-agnes/AI-trade/src/ai_trade/market_analysis_core.py`，工作目录 F:/codex-agnes/AI-trade。
- 完整离线、另列CFFEX回归、真实网络、真实浏览器UI和OOS：本 FIX 尚未执行；没有新 CI。旧707/1skip仅属于旧SHA，不能继承。

### 恢复的下一步（顺序不得跳过）

1. 读取本记录和实际diff，确认当前模型仍 gpt-6.1-sol/high；核验 Git、远端main/Issue33、新修改及额度。若模型/档位变化，按G04保存并另立升级任务，不自动切换。本任务没有独立复核资格。
2. 设置当前src并先核验父/子进程导入路径；使用已有解释器，不安装新依赖。运行完整离线并保留新的日志：

```powershell
$env:PYTHONPATH='F:/codex-agnes/AI-trade/src'
$env:PYTHONDONTWRITEBYTECODE='1'
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
& F:/codex-agnes/AI-trade-main-demo/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider --junitxml=artifacts/m3-core-001-fix/full-offline.xml *> artifacts/m3-core-001-fix/full-offline.log
```

3. 检查完整结果、CFFEX/全A/时间/六因子/L1-L3回归、Schema及实际消费者。出现非预期核心失败先暂停扩大范围并诊断，遵守两次修复上限；不得删旧测试或改低断言。尚未配置专门静态类型工具，不为修复新增依赖。
4. 普通diff自检、必要文档链接/语法检查、pip check、git diff --check；更新本记录完整结果。只暂存本任务5个文件，不 add .worktrees/ 或日志。
5. 提交修复、新PR到main，保留Issue33；Git传输若仍失败可用GitHub API发布，但必须确认测试tree与远端发布tree完全相同，并记录最终完整SHA。没有新SHA不得READY。
6. 核验新PR CI真实最终状态，最终报告READY_FOR_INDEPENDENT_REVIEW或BLOCKED；新独立上下文绑定新SHA复核H1/H2/M1及A—E，不自行批准/合并、不恢复页面改造、不部署。

## 7. 2026-10-20 早晨恢复与实际验证

- 当前实施状态：代码、回归与普通 diff 自检完成；独立 H 复核 PENDING。交付结论只在新 SHA 发布后标 READY_FOR_INDEPENDENT_REVIEW；最终 SHA、PR 和 CI 由修复 PR 的 head 与最终交付绑定，避免在提交内循环记录自身 SHA。
- 恢复运行元数据：2026-10-19T23:42:15.714Z，仍为 gpt-6.1-sol / high；未切换、委派或调用其他模型。恢复时共享5小时剩余100%、周剩余29%，实际费用未知。继续遵守用户最多45分钟的单轮工作预算；凌晨额度交接与本次恢复分别记录，不伪装连续运行。
- 重新实际读取根 AGENTS.md、MODEL_ROUTING_POLICY v1.0、TASK_TEMPLATE、本文及实际实现/测试 diff、DATA/INTERFACE/M3 契约；适用G01—G12，无新 override。远端 main 仍为2e36434a9a5d3ce540a58c04869bcd2e3c17ffd3；PR32 merged、Issue33 open；修复远端分支查询为空。全部原 worktree/stash/未跟踪目录保留。
- 解释器、依赖版本、工作目录与凌晨一致；父/子进程实际导入均为 `F:/codex-agnes/AI-trade/src/ai_trade/market_analysis_core.py`。日志 `artifacts/m3-core-001-fix/resume-environment.log`；每条测试命令显式设置当前 PYTHONPATH，另设 PYTHONDONTWRITEBYTECODE=1、PYTHONUTF8=1、PYTHONIOENCODING=utf-8。
- 完整离线命令：`python -m pytest -q -p no:cacheprovider --basetemp <系统临时目录/m3-fix-full-随机UUID> --junitxml=artifacts/m3-core-001-fix/full-offline.xml`，退出0，**2128 passed / 1 skipped / 0 failed / 0 errors，141.73秒**。日志 `artifacts/m3-core-001-fix/full-offline.log`，JUnit同名xml；唯一skip为实网AKShare测试，需显式--run-akshare-integration。本次未启用。
- 完整套件包含原核心42项、新增1421项、旧market_analysis22项、CFFEX high_assurance96项及rankings26项；完整覆盖既有全A身份/分区、时间因果性、六因子、L1/L2/L3、批准时间、ReferenceResult与调用方回归。数量来自实际JUnit，不沿用旧707结论。没有新增失败或第二次修复。
- 本次 `python -m pip check`：退出0，No broken requirements found，日志 `artifacts/m3-core-001-fix/resume-pip-check.log`。`git diff --check`：退出0，日志 `artifacts/m3-core-001-fix/resume-diff-check.log`。普通自检核对全部5文件及实际消费者；无单独配置的静态类型命令，不新增依赖；导入、现有类型/Schema/调用方测试已在完整套件执行。
- 反例矩阵：身份空值/NaN/空白/非法类型/控制字符/过长/混源混标的，质量quarantined/rejected/未知/非法类型/缺失，成交额字符串/None/空串/bool/NaN/±inf/负值/非法类型；均覆盖首中末行及research/strict_backtest/paper_trade，各诊断入口和组合传播。拒绝结果校验INVALID_DATA/BLOCKED/calculated=false/空值/全部allowed_uses=false与JSON Schema；合法accepted、整数/浮点/真实0仍通过。Receipt不能覆盖拒绝状态；既有L3/实盘门禁保留。
- Git HTTPS有界重试仍失败：curl28低速超时；采用GitHub API发布本地暂存blob和tree，只有tree精确一致才创建提交/修复分支。最终本地分支导入同一API提交并核验SHA，保持已测代码与远端一致；不reset、不改main、不覆盖工作文件。
- 独立复核交接：新TASK/新干净审查上下文绑定修复PR最终完整SHA，重验H1/H2/M1及原A—E范围（契约/接口与Schema、核心计算及时间/身份/质量、全A与CFFEX、L1/L2/L3及调用链、回归与交付证据，以原报告原文为准）。本记录与测试是开发证据，不是独立审查通过；Issue33继续开放、页面改造门禁保留。
- 剩余未验证：独立H审查；真实数据源/历史证券身份/CFFEX口径认证；真实网络、真实浏览器端到端、样本外回测、生产/AWS。离线AppTest不等于真实浏览器验收。CI发布前尚未触发，发布后以同SHA运行链接/实际结果交付，失败不得冒称通过。
- 额度续接automation `m3` 在交付后停用，避免已完成实现被次日重复执行；独立复核需另行指定任务，不能由续接自动批准。

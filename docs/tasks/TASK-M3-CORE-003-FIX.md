# TASK-M3-CORE-003-FIX：R1–R4 修复记录

## 1. 身份、目标与基线

- 类型：implementation；H。执行 Issue #35，只修复身份控制字符、数值支持/构帧边界和等价时区；不执行 M3 页面改造、来源认证、生产数据库、下单或部署。
- 最新 main / 本任务起点：`79e715e54c29b274f57914313abcb3b992d43894`；GitHub branch API 于2026-10-20实际核验。
- PR #32：merged，base `f46347bb492fd8474e38f5fa786a8c81a47c8a6d`，head `edff6ed0dc0093f1b531b0f3d52a087212516a2c`，合并 `2e36434a9a5d3ce540a58c04869bcd2e3c17ffd3`。
- PR #34：merged，base `2e36434a9a5d3ce540a58c04869bcd2e3c17ffd3`，head/被审 SHA `01d0878c753371883cc408b83a265f1c5b18a80b`，合并为上述 main。Issue #33/#35 均 open；旧 PR 描述的 Draft/open/unmerged 已过期，不作为当前状态。
- main 与被审 SHA 的 tree 同为 `ac6baf3e61d5b260af0504119bfa111fd0a7f354`，差异为空；两者因 squash 并非祖先关系，共同祖先为 `2e36434a9a5d3ce540a58c04869bcd2e3c17ffd3`。
- 开始分支 `codex/m3-core-001-fix`，tracked 干净，仅原有 `?? .worktrees/`。stash/其他 worktree/审查 artifacts 保留，不 reset/clean/覆盖。独立分支 `codex/m3-core-003-fix` 从精确 main 建立，PR base=main。
- Git HTTPS ls-remote 连接重置。GitHub API 的签名载荷按 Git 原始格式恢复 main 对象，计算 SHA 精确匹配后才写入对象库并建分支；首个签名换行候选哈希不符未写入，保留末尾换行后匹配。没有改变 main ref 或工作文件。

## 2. 唯一执行配置

- OpenAI / Codex Desktop；唯一执行模型 **gpt-6.1-sol**，固定推理强度 **xhigh**。
- 实际证据：当前聊天 rollout `turn_context`，2026-10-20T14:33:31.874Z，thread `01a159bb-169a-7151-8c94-4eea6a5116b0`，cwd=本仓库。全局配置也为此值，但仅运行元数据作为实际执行依据；项目无 .codex/config.toml。
- H：身份完整性、数值拒绝和既有时间语义修复。工具兼容已由当前 Git/文件/连接器实际调用确认；费用、额度和单任务账单未知，不宣称节省。
- 工作预算：本轮90分钟；同一验收问题最多两次不同诊断性修复，核心非预期回归失败立即暂停扩大修改。预先声明的 R1–R4 修复前红测单列，不冒称通过。不调用其他模型、子代理或 fallback，不切换档位。

## 3. 已读与开始报告

- 实际读取（main 与被审树一致）：AGENTS.md；MODEL_ROUTING_POLICY v1.0；TASK_TEMPLATE；OPEN_SOURCE_RESEARCH_POLICY v1.0；PROJECT_STATUS；DECISIONS；DATA_CONTRACT；INTERFACE_CONTRACT；ACCEPTANCE_TESTS；M3_CORE_CONTRACT；M3_CORE_SOURCE_ACCEPTANCE；TASK-M3-CORE-001-FIX 记录；M3 core/contract/旧计算器、共享 validation、CFFEX models、现有核心测试与 conftest/CI。
- 完整审查依据：Issue #35、`artifacts/m3-core-002-review/REPORT.md`、probes.py、probes.json、probes.log，均仅本机读取并保留。报告为 FAIL，52组探针19符合预期/33不符合预期；不是本轮测试输出。
- 适用 G01—G12：基线/现场保护、实际阅读/固定模型、H独立复核、时间/UNKNOWN不变量、离线临时数据库、生产/Git边界、失败升级和可复查证据。
- 全局 AGENTS.md 为空；父目录、根及适用 src/tests/docs 路径未发现 override/子规则。其他旧 worktree 的 AGENTS 不适用。无规则修改。Issue #35 的“创建Issue后不要自动执行”是任务定义时的限制，本轮用户明确要求执行修复，按当前授权实施。
- 开源调研：不适用全面外部调研。这是已定位反例的现有校验修复，无新模块、数据源、依赖或外部代码采用。已检查现有本地契约、旧任务的Qlib/Pandera设计参考记录及实际失败路径，不重新采集行情/认证许可；若需改变时间契约或引入设计则停止另立H任务。

## 4. 修改边界

- 允许：`src/ai_trade/market_analysis_core.py`、对应核心回归测试、`docs/M3_CORE_CONTRACT.md`、本记录、PROJECT_STATUS 的当前M3交付索引。
- R1 采用 M3 局部统一标识校验，声明和记录使用同一规则；保持共享存储 validator/CFFEX底层不变。综合传播 INVALID_DATA 并清空不可信值。
- R2/R3 明确支持 Python/NumPy 整数与浮点标量；拒绝 Fraction/Decimal/字符串/布尔/复数等。在 DataFrame 重建之前逐标量校验，价格/成交额受控转换为有限 float64；计数保留精确非负整数。禁止 coerce/drop/补零。
- R4 只规范计算副本的时区表示；UTC绝对时刻比较及 Asia/Shanghai 交易日不变，available_at/ingested_at/observed_at/as_of 门禁不放宽，不覆盖输入或历史版本。
- 禁止 main提交/自动合并、治理/依赖/Schema/SQLite/ReferenceResult/旧页面/策略/AWS/账户修改。真实行情网络未授权；仅GitHub元数据/发布及官方文档读取。

## 5. 验收与验证计划

| 验收 | 命令与断言 | 实际结果 |
| --- | --- | --- |
| AC-01 / R1 | 新回归：全部C0/DEL/C1，声明/记录相同、三个模式及五条诊断链，INVALID_DATA/BLOCKED/空值/无许可 | 通过，完整离线覆盖；65个控制字符逐一循环 |
| AC-02 / R2 | 支持类型合法对照；Fraction等不支持标量带日期/字段/范围结构化拒绝 | 通过，Python及NumPy各整数/浮点宽度对照；Fraction/Decimal/复数/布尔拒绝 |
| AC-03 / R3 | 10**400、OHLC/成交额/宽度/分区字段，在公开入口不得逸出OverflowError | 通过，4个OHLC、成交额、9个宽度/分区计数字段及综合失败传播 |
| AC-04 / R4 | price/fear_greed同一UTC时刻的不同offset输出相等；未来/naive时间门禁保留 | 通过，-12/-10/0/+8/+14 offset完整诊断/快照相等，晚采集仍排除，输入不变 |
| AC-05—06 | 既有核心/CFFEX/组合/L1—L3与负向准入回归，Schema+严格JSON序列化 | 通过，原测试不改弱，所有完整套件通过 |
| AC-07 | `python -m pytest -q -p no:cacheprovider`；`python -m pip check`；`git diff --check` | 退出0，2834 passed/1 skipped；依赖与差异检查通过，见第8节 |
| AC-08—10 | PR/任务记录/项目状态据实际GitHub数据更新，最终SHA另立独立H复核任务；不认证来源/策略/生产 | 代码交付等待独立H；最终SHA/PR/复核Issue由实际发布记录绑定，AC-08尚未独立通过 |

解释器：既有 `F:/codex-agnes/AI-trade-main-demo/.venv/Scripts/python.exe`；显式 PYTHONPATH=当前仓库/src，PYTHONDONTWRITEBYTECODE=1，PYTHONUTF8=1，PYTHONIOENCODING=utf-8。沿用conftest全局阻网、不启用实网开关；临时文件/数据库使用独立新目录。

| 验证类型 | 状态与范围 |
| --- | --- |
| 离线测试 | 通过，2834 passed/1 skipped，exit 0，368.85秒；唯一skip为未开启的实网AKShare测试 |
| 真实行情网络/来源认证 | 未执行，本任务不需要 |
| 真实浏览器UI端到端 | 未执行，不改页面；离线AppTest不等同真实浏览器 |
| 样本外回测 | 未执行，不改变策略或执行引擎 |

## 6. 交付与日志

- 日志、JUnit、环境与脱敏基线：`artifacts/m3-core-003-fix/`（Git忽略，交付前检查）；原独立审查产物不覆盖、不提交。
- 最终SHA/PR以交付时实际对象绑定，避免提交内循环记录自身SHA。仅暂存允许文件；无密钥、SQLite、原始行情或未审原始响应。
- 当前状态：代码及本地验证完成，修复PR最终SHA发布后进入 READY_FOR_INDEPENDENT_REVIEW；实际SHA/PR及复核Issue在发布交付中绑定，不在提交内循环记录自身SHA。不是独立审查通过。

## 7. 独立复核与门禁

- 本任务为H，不等待L批次。计划新独立任务 `TASK-M3-CORE-004-REVIEW`，冻结修复PR最终SHA，核对R1—R4、原H1/H2/M1及A—E、失败路径和实际验证证据。
- 复核必须新独立会话/干净上下文，自己的唯一H模型/档位实际确认后方可执行；只出问题/结论，不改实现。实现会话不自审，不把测试/CI称为独立通过。
- 完成实现后创建GitHub复核任务/计划，模型/档位未指派前保持待指派。Issue #33保持开放；独立复核通过前不建议解除核心/M3页面/策略门禁，不合并/部署。
- 契约冲突、范围扩大、非预期核心测试失败立即阻断；同一验收项两次诊断修复仍失败不清零；现场和复现证据保存于上述日志目录与本记录。

## 8. 实际修复、验证与交付证据

5个交付文件：`src/ai_trade/market_analysis_core.py`（唯一实现文件）、`tests/unit/test_market_analysis_core_boundaries.py`（新增706个参数化实例，另含逐字符/位置循环）、`docs/M3_CORE_CONTRACT.md`（数值/身份边界与既有时区语义说明）、`docs/PROJECT_STATUS.md`（当前M3状态与历史基线分开）、本任务记录。不修改共享validator、原测试断言、JSON Schema、依赖清单或下游页面/策略。

| 发现 | 根因与修改 | 修复前后行为 |
| --- | --- | --- |
| R1 | text_field只拒绝C0；M3局部_identity补DEL/C1，声明及可见记录使用同一规则，CFFEX会员/合约检查及environment传播INVALID_DATA | 相同非法声明/记录原可L2；现在所有模式INVALID_DATA/BLOCKED、空values/calculated=false/所有用途false |
| R2 | Real允许Fraction但pd.to_numeric不接受；_number明确Python/NumPy标量集合并在调用前规范化 | Fraction原逸出TypeError；现在带字段/实际日期/标的或ALL_A范围结构化拒绝；合法标量保持L2对照 |
| R3 | pd.DataFrame隐式推断先于数值校验；现在先检查原始标量，再object构帧，已验证数量显式设类型 | 10**400原逸出OverflowError；现在逐字段INVALID_DATA/BLOCKED；缺失/零/计数分区语义保留 |
| R4 | UTC验证后的原offset字符串仍传入旧计算器；现在计算副本统一Shanghai，聚合仍UTC | -10 offset原误按上一日期抛ValueError；现在price/fear_greed全诊断与快照相等，不放宽任一可见性条件 |

实际环境：Python3.12.14，pandas3.0.6 / NumPy2.5.4 / pytest8.4.2 / jsonschema4.26.0 / Streamlit1.66.0；解释器和父/子进程实际core导入路径已核验，见 `environment.json`。所有命令沿用第5节显式UTF-8及当前src环境；没有新增安装或永久配置变更。

以下 `python` 均为第5节绝对解释器，工作目录为本仓库；日志前缀统一 `artifacts/m3-core-003-fix/`。

| 检查 | 实际命令与输出 |
| --- | --- |
| 预声明修复前反例 | `python -m pytest -q -p no:cacheprovider tests/unit/test_market_analysis_core_boundaries.py::test_review_regressions --basetemp=artifacts/m3-core-003-fix/red-tmp --junitxml=artifacts/m3-core-003-fix/before.xml`；exit1，7 failed，13.01秒，before.log/xml |
| 首轮扩展 | `python -m pytest -q -x -p no:cacheprovider tests/unit/test_market_analysis_core_boundaries.py tests/unit/test_market_analysis_core.py tests/unit/test_market_analysis_core_validation.py --basetemp=artifacts/m3-core-003-fix/targeted-tmp --junitxml=artifacts/m3-core-003-fix/targeted.xml`；exit1，49 passed/1 failed，26.04秒。新增夹具的可选symbol列未创建，set_cell抛KeyError；仅补ALL_A列，无断言放宽 |
| 定向复跑 | 上述命令，basetemp及JUnit改为targeted-2-tmp/targeted-2.xml；exit0，2055 passed，164.41秒，targeted-2.log/xml |
| 补充边界 | `python -m pytest -q -x -p no:cacheprovider tests/unit/test_market_analysis_core_boundaries.py -k "supported_numeric or invalid_numeric_components or numpy_missing or future_acquisition" --basetemp=artifacts/m3-core-003-fix/additional-tmp --junitxml=artifacts/m3-core-003-fix/additional.xml`；exit0，198 passed/508 deselected，29.03秒 |
| 完整离线 | `python -m pytest -q -p no:cacheprovider --basetemp=artifacts/m3-core-003-fix/full-offline-tmp --junitxml=artifacts/m3-core-003-fix/full-offline.xml`；exit0，**2834 passed/1 skipped/0 failed/0 errors，368.85秒**；full-offline.log/xml。默认socket阻网、临时数据库，未开启实网开关 |
| 依赖 | `python -m pip check`；exit0，`No broken requirements found.`，pip-check.log |
| 差异与文档 | `git diff --check`及暂存差异检查；19个本地文档链接/代码围栏通过，document-check.json。无已配置独立静态类型/Markdown lint命令，不安装新工具；数值类型/时区/Schema测试已实际执行 |

原复核probes.py/json/log/REPORT保留，SHA256记录在document-check.json；不运行会覆盖旧输出的历史脚本。旧探针对Fraction原期望L2，本任务根据Issue #35明确选择结构化拒绝，新的回归测试表达该决定，不改历史证据。新增NumPy NaN质量对照保留UNKNOWN，未将缺失默认为accepted。

无非预期核心回归失败；首轮失败属于新增测试夹具初始化，修复后通过，没有用换编号清零失败计数。辅助文档脚本首读PowerShell快照误选UTF-16，改用实际UTF-8后通过；基线导入/编码诊断记录在check-notes.txt，不隐去失败。旧stash和.worktrees保留，审查日志/SQLite/原始行情不提交。

本地完整离线通过不代表CI、独立H、真实网络、来源认证、真实浏览器UI或样本外通过。CI以发布后实际run/head/result单独报告。新独立H复核Issue将绑定最终完整SHA及PR，未指派模型/档位前不启动；Issue #33/#35保留开放，所有阶段/生产门禁保持。

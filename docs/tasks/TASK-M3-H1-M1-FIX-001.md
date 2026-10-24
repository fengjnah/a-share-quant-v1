# TASK-M3-H1-M1-FIX-001

类型：implementation；优先级 P0；风险 H（来源用途授权与失败证据审计）。

## 开始记录（2026-10-24）

- 唯一执行模型：OpenAI `gpt-6.1-sol` / `high`；依据为本会话用户对当前界面的明确确认，当前任务继续同一配置。无子代理或外部模型；实际费用未知。执行预算上限 90 分钟（含验证及交付）；同一问题最多两次有不同诊断依据的修复，额度不足提前保存交接。
- 基线及最新远端 main：`b1252e03584887c84186a0700aa90de4e749b8eb`，由本次 `git ls-remote` 核实。PR #51 已合并，merge SHA 同上，head `1e2b2c3e8cbab09c226ff0edc739ff08511eb67e`，base `04e530871e2c8b4889c60027ac8d1ec4275009a2`，由 GitHub PR API 实际核实。
- 独立工作区：`C:\Users\iyoyi\.codex\worktrees\m3-h1-m1-fix-001\AI-trade`；分支 `codex/m3-h1-m1-fix-001`；创建时干净。原工作区、stash、其他 worktree 保留。
- Agnes：`F:\codex-agnes\AI-trade-m3-collector-001` / `codex/m3-collector-001`，开始时干净、HEAD 同基线。本任务只修改自己的 worktree；`m3_store_market.py` 的 CFFEX 入口存在潜在集成重叠，后续按提交集成，不能覆盖 Agnes 修改。
- 已实际阅读（上述基线）：根 `AGENTS.md`、`docs/MODEL_ROUTING_POLICY.md` v1.0、`docs/tasks/TASK_TEMPLATE.md`、`docs/OPEN_SOURCE_RESEARCH_POLICY.md` v1.0、`docs/PROJECT_STATUS.md`、`docs/DECISIONS.md`、`docs/DATA_CONTRACT.md`、`docs/INTERFACE_CONTRACT.md`、`docs/M3_CORE_CONTRACT.md`、`docs/architecture/M3_CORE_DATA_MODEL_DICTIONARY.md` B07/A01/A17 及相关生产代码/测试；另读原 H 报告 `TASK-M3-DB-SCHEMA-V5-H-001-REVIEW.md`。只找到根规则，无下级规则/override。
- 适用 G01–G12。G10 的五项已知搬迁夹具失败按用户本任务要求保留为独立阻断项，不扩大修改，不称全套通过。G09 不写正式库；G12 必须另有独立 H 审查后才可合并/启用。
- 开源调研：已定位现有实现的小修复，不新增模块、依赖、来源或设计；复用本项目现有收据用途检查（聚合写入要求 research+storage）、不可变尝试及证据存储，不引入外部代码。无需全面外部调研；不认证任何供应商许可。

## 定位表（生产代码修改前）

| 编号 | 实际缺陷 / 触发 | 文件与函数 | 影响 | 最小方案 |
|---|---|---|---|---|
| H1 | VERIFIED 但仅 display 的收据仍可封存为 COMPLETE，结果写入也只核对引用/claim/decision | `m3_store_snapshots.py::_check_record`；`m3_store_results.py::_diagnostics` | 三种模式可能将未获研究/存储用途的数据当作已认证研究输入 | 缺 research+storage 时记录用途原因；research 保留 PARTIAL 观察，严格模式 BLOCKED；结果消费者再核对用途，旧快照不改写 |
| M1 | raw 已保存，解析/后续校验失败的 FAILED 尝试 evidence_id 为空 | `m3_store_market.py::save_cffex`；`m3_store_catalog.py::_write` 的失败审计 | 无法从失败尝试追溯确切响应，重试复用 ID 可混淆证据 | 以实际存档 ID 绑定前置及事务失败；已失败/阻断的 attempt 必须使用新 ID 重试，保留旧证据 |

## 范围与验收

允许：上述四个生产文件的最小修复，新增针对性测试、本任务单及结果报告。禁止：Schema/迁移 checksum、核心评分/解析器/时间语义、页面、真实采集、正式数据库、AWS、Agnes 工作区。

正式库只读取文件 SHA256 作为保护证据：`F:\codex-agnes\AI-trade-data\sqlite\workbench.sqlite3`，修复前 `2d38f34d3a6a26026d576e24896f117ef68e017deae286a6293b5faba4ac333f`。测试只用 pytest 临时库、默认禁网，不打开正式库连接。

执行：先新增回归测试复现，再修复；运行两个新增测试文件及 M3 存储相关组、完整 `python -m pytest -q`、`python -m pip check`、`git diff --check`。使用现有 Python 3.12 测试环境，PYTHONPATH 明确绑定本 worktree/src。日志在 Git 外 `F:\codex-agnes\AI-trade-local-state\m3-h1-m1-fix-001`。

验收包括用途矩阵/结果消费者/冻结与可得边界；CFFEX 失败、空响应、部分成功、不同批次、重试、事务回滚及真实零/缺会员区别。默认不做真实网络、UI 或样本外回测。

交付独立 Draft PR（base main），不合并。独立 H 计划：`TASK-M3-H1-M1-FIX-001-REVIEW`（待用户指派独立会话/唯一执行配置），绑定最终修复 SHA，覆盖 H1/M1 端到端和兼容性；实施自检不构成该审查。M3 业务保持 `PENDING_INDEPENDENT_REVIEW`，其他五项失败及来源认证/发布门禁保留。

实际交付：[Draft PR #57](https://github.com/fengjnah/a-share-quant-v1/pull/57)；测试、CI 额外阻断及证据路径见[结果报告](../../TASK-M3-H1-M1-FIX-001-RESULT.md)。修复代码 SHA `46be463c198cc3065a6271bb464b85dab2f43c4b`，本地相关 210 项通过，完整套件仍 FAIL；最终文档提交不改 src/tests，整体验收和 M3 业务继续等待独立审查。

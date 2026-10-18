# TASK-022A-H：仓库冗余与证据保护审计

2026-10-18（Asia/Shanghai）。只读盘点先行；执行模型沿用本会话用户确认的 GPT-6.1 Sol / High。审计基线为 PR #22 的 `33e33c8e0583b70e1864ca7fb40e94152a338b6c`，main 为 `2a5332448b32083ddbedc6b16ea0cf49057e3cb8`。本清单在业务修复前单独提交，**本任务删除文件数为 0**。

完整逐文件清单、基线 SHA256、引用计数和保护结果见 [TASK_022A_FILE_INVENTORY.json](TASK_022A_FILE_INVENTORY.json)：106 个跟踪文件、107 个相关任务的只读证据文件。精确字节重复组为 0；不能据此声称不存在语义重复。引用计数只作为线索，不作为删除证据。原工作树的路径/索引/未提交差异哈希保存在本机外部日志，不能当作其他开发环境可用的项目链接。

## 候选分类与操作

| 相对路径或范围 | 分类 | 依据 / 替代入口 | 本轮操作与风险 |
| --- | --- | --- | --- |
| `AGENTS.md`、`docs/*CONTRACT.md`、`ARCHITECTURE.md`、`DECISIONS.md`、`ACCEPTANCE_TESTS.md`、模型/开源治理制度 | KEEP | 权威契约与行为边界；历史实现不能替代 | 不删除，不为适配器私自改正式 Schema/交易契约 |
| `docs/TASK_022A_REPORT.md` | KEEP | PR #22 原始交付与当时声明，含本轮确认有误的结论 | 保留原文；新审查报告列勘误，不能改写成当时已修复 |
| TASK-022 的 `docs/IMPLEMENTATION_TASK_022.md`、`docs/research/*.md`；TASK-022-REVIEW 的 `docs/reviews/TASK-022_INDEPENDENT_REVIEW.md` | KEEP | 独有分支中的正式历史报告；尚未进入本任务基线 | 只读，不整枝合并、搬移或删除。Git SHA/状态在新审查报告登记 |
| `docs/PROJECT_STATUS.md` 与 `TASK_BOARD.md` / `TASK_METRICS.json` 的历史/当前状态说明 | MERGE | 存在状态叙述重叠；看板为有截止时间的证据快照 | 本轮不改权重/状态或旧证据。未来由独立治理 PR 建权威索引，保留旧报告链接 |
| `src/ai_trade/market_data/cffex_rankings.py` 中 standalone/mixed named 解析 | MERGE | 同一具名行/字段校验重复，混合分支更宽松 | 只在原模块内复用共同校验；不删除文件，需双格式反例回归 |
| `tests/unit/test_cffex_rankings.py` 的机器专属 fixture 查找 | MERGE | CI/干净克隆找不到兄弟目录就跳过；关键断言可能未执行 | 改为明确标注的合成离线夹具；真实证据另行只读重放。不能把合成夹具称为真实来源验收 |
| `tests/fixtures/`、版本链与 as_of 测试 | KEEP | 边界与回归证据；文件名相近不代表重复 | 保留，严禁用降低断言或无条件跳过隐藏问题 |
| `tools/diagnose_akshare_tls.py` 与相关诊断单测/历史报告 | KEEP | 可复现独有诊断行为与预算边界 | 不能因 CFFEX 不引用就删除 |
| `docs/evidence/*.json`、TASK-016/018 审计与哈希格式记录 | KEEP | 管理验收与历史前缀引用 | 不更新旧文件来伪造新验收，不删除 |
| 相关旧任务 `artifacts/task-022/` CSV/JSON/ZIP/HTML/探针、`artifacts/review-022/` | ARCHIVE | 原始 CFFEX 响应、哈希、复算与失败证据；脚本无引用也可能是唯一复现手段 | 107 个证据文件只读登记并保护。不提交未经授权的完整响应，不清理其他 worktree |
| 新工作区 `.pytest_cache/` | DELETE_CANDIDATE | 本轮基线 pytest 可再生缓存，不是源证据 | **未删除**；未来需在目标根目录核实 resolved path / Git ignored / 无验收证据后单独处理 |
| 新工作区 `**/__pycache__/` | DELETE_CANDIDATE | 可再生字节码 | **未删除**；不得把通配符扩展为跨 worktree 递归清理 |
| 未穷举的旧工作区 ignored 临时输出、本地日志、原始响应 | NEEDS_OWNER_DECISION | 是否唯一证据及保留期未确认 | 保持现场；本清单不批准删除或公开分发 |

## 恢复与复核

本轮没有删除/移动，所以无需恢复文件。将来若治理 PR 拟删除重要文档，必须先列替代路径、迁移全部引用、冻结被删内容的 Git SHA，并验证 `git show <SHA>:<path>` 可恢复。对 ignored 原始证据，Git 历史不提供恢复保证，必须经所有者确认并有可验证归档，不能仅凭“可再生成”删除。

本任务不清理任何分支、旧目录或工作树，不修改生产数据库；没有使用 `reset --hard`、`clean` 或批量 cherry-pick/rebase/merge。审计完成不等于文件已经获准清理；未确认项继续保留。

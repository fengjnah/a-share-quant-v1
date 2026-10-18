# TASK-016：本地分支、Worktree 与 GitHub main 差异审计

检查日期：2026-10-18，Asia/Shanghai。类型为只读审计及当前状态文档修正，P0/H；唯一执行模型 `gpt-6.1-sol / high`，依据本会话用户最近的界面确认，工具不独立暴露运行时型号，费用未知。未切换模型、委派或安排另一个模型审查。真实行情请求预算 **0**。本报告中的整理操作均为建议，未删除文件、分支或工作树，未关闭/合并旧 PR、重建本地 main、部署或操作生产数据库。

## 1. 开始检查、证据与范围

已实际读取 `AGENTS.md`、`MODEL_ROUTING_POLICY.md` v1.0、任务模板、PROJECT_STATUS、DECISIONS、TASK-015 实施/健康说明、TASK-009 实施/治理矩阵、TASK-004/008/008A/008B 报告和数据/接口/验收契约。先从 TASK-015 工作树读取规则，再核对其文件树与最新 main 相同；新工作树采用该 main 的根规则，没有新增 override。适用 G01–G12：核实基线、保护 staged/unstaged/untracked、固定模型、时间与未知语义不变、默认离线、凭据/数据库禁入库、仅任务文档、真实结果及独立审查边界。

原 `F:\codex-agnes\AI-trade` 缺少 AGENTS、模型制度、模板、PROJECT_STATUS、TASK-009/015 等后加文件；这是旧工作树的实际状态，不表示 GitHub main 缺少这些文件。原目录存在 DECISIONS、TASK-004 实施报告及未跟踪的开源研究报告。TASK-004A 报告在 report-only 工作树和 #11，**不在最新 main**。

Git 版本为 **2.53.0.windows.3**。任何同步/修改前，逐一记录原有 10 个工作树的以下命令与退出码，保存 staged/unstaged 二进制 patch、index 哈希、HEAD/index blob、文件 SHA-256；原始补丁只保存在本机，不提交可能包含敏感内容的全文：

```powershell
git rev-parse --show-toplevel
git status --short --branch --untracked-files=all
git branch -avv
git worktree list --porcelain
git log --oneline --decorate -20
git diff --stat
git diff --cached --stat
git ls-files --others --exclude-standard
```

本地证据目录：`C:\Users\iyoyi\AppData\Local\Temp\task-016-audit-20261018-144057`。其中 `snapshot-before.json`、`workspace-00` 至 `workspace-09` 下的 staged/unstaged.patch、`branches.json`、`files-vs-main.json`、`supplemental-ignored.json`、GitHub 查询摘要、测试日志用于复核。临时目录不是长期备份，后续清理前需由用户另行指定长期归档位置；本次未自动搬移旧文件。

提交的 [审计 JSON](evidence/TASK_016_BRANCH_AUDIT.json) 记录 **10 个旧工作树、710 个文件条目、51 个本地/缓存/API 引用、27 个不同 head、54 个不在 main 祖先链中的提交身份**，及逐文件 main 比较、82 组内容重复映射。扫描涵盖受跟踪/非忽略未跟踪文件，以及 `src/ai_trade/`、tests、tools、docs（含 evidence）、artifacts；另补录 15 个忽略的 egg-info 文件。文件数包含同一内容在不同工作树的副本，不是 710 项独有成果。

`.venv`、pytest/bytecode 缓存没有逐文件哈希，仅记录存在性及排除数量；不能因此宣称整个环境无独有手工文件。原始字节 SHA-256 与仅统一 CRLF 的 LF SHA-256 分列，避免 Windows 换行差异被误判为新实现。每项保留 HEAD、Git 跟踪/index 归属与文件大小；未将正文、代理凭据、数据库或行情样本纳入提交。

## 2. 最新 main 与本地引用

| 项目 | 实际核验结果 |
| --- | --- |
| [GitHub main](https://github.com/fengjnah/a-share-quant-v1/commit/693fab10fe7f88581fc326015556ddc0aa83c1ea) | **693fab10fe7f88581fc326015556ddc0aa83c1ea** |
| main tree | `e39d81fbaee7477ecbafbdf61ae3c37eaa9aa049` |
| main 父提交 | `31a575f6834067749ea006931282e62e8f666a18` |
| [PR #18](https://github.com/fengjnah/a-share-quant-v1/pull/18) | 已合并，`merged_at=2026-10-18T06:35:46Z`；merge_commit_sha 等于上述 main |
| 本地 `refs/heads/main` | **不存在**；`git show-ref --verify refs/heads/main` 退出码 128；不能报告为一致、落后或分叉 |
| 本地 `origin/main` | 仍为 `31a575f…` 的缓存，相对 API 核实的 main 落后 1、超前 0 |
| 原目录当前 HEAD | `cd1b2b1412e4dbe345e4eac09330b94977211372`，TASK-004 分支；相对最新 main 祖先链落后 9，叠有未提交修改 |

本轮实际执行 `git -c credential.interactive=never -c http.lowSpeedLimit=1 -c http.lowSpeedTime=15 fetch origin`，失败为 `Failed to connect to github.com port 443 after 21061 ms: Could not connect to server`，Git 退出码 128。后面的查询命令成功不能覆盖这个失败；没有把旧 origin/main 宣称为最新，也未修改永久代理或追加行情探针。

成功的 GitHub API 读取了 main、全部 19 个远端分支、18 个 PR；对重点 PR 另读实际 files、mergeability 与 workflow runs。为建立精确基线，从 GitHub Git commit API 的签名 payload/signature 还原 main 对象字节，**写对象前核对完整 Git SHA 为 693fab10…**；其签名 API 状态 valid，tree 已存在于本地 TASK-015。对 API 发布而本地缺少的 009/015/DEMO-003/004 提交及 DEMO-003 父提交采用同样的 SHA 校验后只补入对象库。27 个 head 的对象图检查无缺失。

这不是 fetch 成功，没有移动 `main` 或 `origin/main`。基于已核实的 **完整 SHA** 新建 `F:\codex-agnes\AI-trade-task-016` / `codex/task-016-branch-worktree-audit`；未整支合并或复制任何旧工作树。网络恢复后仍需重新 fetch 并比较 API 最新值。

## 3. 正式仓库与所有工作树

**正式 Git 管理仓库是 `F:\codex-agnes\AI-trade`，共享管理目录为其 `.git`。** 其余均由 `.git` 指针和 common-dir 核实为该仓库的 linked worktree，包含 C 盘 Codex 工作树；不是独立克隆，也不是可以随意复制回主目录的快照文件夹。当前主目录工作副本是保留现场，不能作为最新 main 的运行基线。

分类：A 正式保留；B 需要另 PR 整合；C 历史归档；D 二次复核并获批准后可清理；E 暂不处理。父目录为 E 不妨碍其中某个文件属于 B/C。

| 目录（F 盘前缀均为 `F:\codex-agnes\`） | HEAD / 分支 | 工作区和独有成果 | 分类 |
| --- | --- | --- | --- |
| `AI-trade` | `cd1b2b1` / codex/task-004-master-calendar | 16 项 tracked 的暂存/工作区修改；研究报告未跟踪，两个嵌套 worktree 在外层显示为未跟踪；33 个范围内忽略历史产物，另有 5 个 egg-info | E；管理仓库 A |
| `C:\Users\iyoyi\.codex\worktrees\task-004-resume\AI-trade` | `b53e5b7` / docs/model-routing-governance | tracked 干净；22 个忽略的 TASK-004/004A/GOV 日志/探测/交付证据 | C，保留唯一证据 |
| `AI-trade\.worktrees\local-demo-verify` | detached `b3e4e31` | 42 个 tracked 文件；无未提交/非忽略未跟踪；仅 5 个可重建 egg-info，完整 tree 等于 main 祖先 74536e0 | D 候选，必须按第 7 节复核 |
| `AI-trade\.worktrees\task-004a-report-only` | `b0a1ba1` / docs/task-004a-report-only | tracked 干净；唯一增量是 004A 报告，尚未合并 | B，保留 |
| `AI-trade-demo-002` | `365a01c` / codex/task-demo-002-network-diagnostics | tracked 干净；4 个忽略的 DEMO-003 TLS/HTTP 审计和脚本在这里 | C，不能因 #14 内容被整合而删除 |
| `AI-trade-demo-003` | `0172171` / codex/task-demo-003-single-probe | tracked 干净；tree 与远端 #15 相同，报告未进入 main | C，等待报告归档 |
| `AI-trade-demo-004` | `6bb1ed0` / codex/task-demo-004-akshare-direct | tracked 干净；#16 四项独有交付，另有 ignored live-audit | C，保留 |
| `AI-trade-main-demo` | `b31847f` / codex/task-local-reconcile-001 | **4 个 tracked 修改、17 个未跟踪**；8 个忽略产物含临时 SQLite，另有 5 个 egg-info、既有 .venv | E，内部有 B/C 成果 |
| `AI-trade-task-009` | `079565b` / codex/task-009-tencent-integration | tracked 干净；tree 等于 main@31a575f；5 个忽略的测试/保护日志 | C |
| `AI-trade-task-015` | `59367bd` / codex/task-015-source-health | tracked 干净；**80 个 tracked 文件全部与最新 main 一致**；18 个忽略的离线/保护/测试产物 | C，合并前后证据保留 |
| 新 `AI-trade-task-016` | 起点 `693fab1` / codex/task-016-branch-worktree-audit | 本次三份文档，独立任务工作树 | A |

原主目录 staged/unstaged 的细节必须保留：README 为 MM；TASK-004 报告和 reference_data 测试为 AM；其余新增/修改已暂存。工作区 reference_data 测试额外的网络阻断用例已存在于 main，但其旧 index 版本仍不同，**不能以工作文件相同就丢掉暂存现场**。16 项中 14 项的工作文件内容与 main 一致；README 和旧实施报告是历史版本。未跟踪 `docs/REFERENCE_PROJECT_REVIEW.md` 为 60,846 字节，尚未进入 main，需单独内容/引用/许可证复核后决定是否另建文档 PR。

## 4. TASK 与 PR 追溯矩阵

| TASK / PR | 是否在最新 main | 独有内容及真实验收边界 |
| --- | --- | --- |
| TASK-002 / #1 | 已合并，cd1b2b1 | SQLite 基础；旧 head 与该 main 祖先全树相同 |
| TASK-003 / #2、#5 | #2 关闭未合并，#5 已合并 a102ac9 | 原 fc692e7 与 a102ac9 全树相同；适配器在 main，不再需要重做 |
| TASK-003C / #3、#6 | #3 关闭，#6 已合并 804a331 | 旧 #3 与对应集成树仅 README/CI 存差异，src/tests/tools/docs 内容已保留；历史实测不保证当前连通 |
| TASK-004 / #10 | 已合并 0578f9c | 模型、Schema v2、版本链、as_of 和测试已在 main；原工作区实现重复，旧报告/现场继续保留 |
| TASK-004A / #11、report-only | **尚未进入 main** | 独有报告 blob `40ff735f1423b670000055a9c63c3fcaa96652b2` 两处相同；不是已实现真实采集。历史主数据 TLS 失败；新浪 8,797 日期响应只证明那次来源响应，未做真实主数据/日历入库、版本或覆盖验收 |
| TASK-008 / 008A / 008B | 主要实现和审查副本随 #17 进入 main | 原 dirty 工作树仍有未提交旧实现、原始审计、额外探针。旧最小腾讯样本 2 行及旧 SQLite 证据由 TASK-009 复核；不是当前健康链路或生产验收 |
| TASK-009 / #17 | 已合并 31a575f | 腾讯手选、#13/#14 修复、来源和数值守卫在 main；无自动切源，东方财富仍默认 |
| TASK-015 / #18 | **已合并 693fab1** | 健康模型/服务、预算、报告、CLI、调度计划全部在 main；离线 412/1，真实健康/连接探针/可信日历/计划任务安装未验收或未执行 |

### 重点 PR 最新状态

以下状态来自本轮 GitHub API，不沿用 TASK-009 历史矩阵。open PR 的 `merge_commit_sha` 可能只是测试合并对象，只有 merged_at 非空及实际祖先证据才算合并。

| PR | head / base | 状态与 CI | 内容与建议 |
| --- | --- | --- | --- |
| [#11](https://github.com/fengjnah/a-share-quant-v1/pull/11) | 39be058 / main | open，非 draft，dirty；head 无 workflow run | TASK-004 核心代码/测试/契约/README 与 main 相同，独有 004A 报告。先独立保留报告，勿整支合并；关闭需用户确认 |
| [#13](https://github.com/fengjnah/a-share-quant-v1/pull/13) | b31847f / main | open draft，**dirty**；[历史 CI success](https://github.com/fengjnah/a-share-quant-v1/actions/runs/39051447382) | 点击去重、未知行数、报告已随 #17 整合；旧 CI 不能消除当前冲突。建议人工核对后按被替代 PR 关闭，不重复合并 |
| [#14](https://github.com/fengjnah/a-share-quant-v1/pull/14) | 365a01c / main | open draft，clean；[历史 CI success](https://github.com/fengjnah/a-share-quant-v1/actions/runs/39052636700) | 安全异常类型链及测试/报告已随 #17 保留；建议人工按被替代关闭；先处理 #16 对它的 base 依赖 |
| [#15](https://github.com/fengjnah/a-share-quant-v1/pull/15) | b7cbe9e / main | open draft，clean；[历史 CI success](https://github.com/fengjnah/a-share-quant-v1/actions/runs/39087404130) | 仅 DEMO-003 报告不在 main。建议合并历史报告归档，不能当作功能/网络验收 |
| [#16](https://github.com/fengjnah/a-share-quant-v1/pull/16) | d4701c8 / #14 分支 | open draft，clean；该 head 无 workflow run | 独有诊断工具、4 个离线控制测试、报告/审计。应另行 retarget 到最新 main、复核重叠健康控制后跑 CI；本轮不操作 |
| [#17](https://github.com/fengjnah/a-share-quant-v1/pull/17) | 74d0a18 / main | 已合并 31a575f；[CI success](https://github.com/fengjnah/a-share-quant-v1/actions/runs/39102616647) | 腾讯候选及局部修复已在 main，不能再写“待集成” |
| [#18](https://github.com/fengjnah/a-share-quant-v1/pull/18) | 15eb0f1 / main | 已合并 693fab1；[CI success](https://github.com/fengjnah/a-share-quant-v1/actions/runs/39104406525) | 健康框架已在 main；不改变真实验收和生产资格 |

其余 PR：#1/#5/#6/#7/#8/#9/#10/#12 已合并；#2/#3/#4 已关闭未合并。全部 18 个 PR 的完整 head/base/merge SHA 及重点文件清单位于审计 JSON。

## 5. 所有分支：提交身份与内容的区别

每个 ref 的相对 main 提交数、54 个非祖先提交的完整 SHA/说明/逐提交文件清单、merge-base、直接快照差异、引入差异及 patch 等价提示均在 JSON。直接 `git diff main old_head` 包含旧分支缺少的新模块，**不等于旧分支打算删除它们**；`git log main..branch` 中的 squash 前 SHA 也不等于未合并功能。没有基于名称或提交说明判定覆盖。

下列 head 与 main 祖先 **完整 tree 相同**，包括早期未被 TASK-009 完全确认的原 TASK-003 分支：

| 分支（本地/远端存在性见 JSON） | head → main 等价祖先 | 分类/约束 |
| --- | --- | --- |
| docs/p0-architecture-contracts | fda15d3 → 125fd7e | C；架构与 README 成果不丢失 |
| feature/task-002-sqlite-foundation | 4b73f8a → cd1b2b1 | C |
| feature/task-003-akshare-adapter | fc692e7 → a102ac9 | C；#2 被 #5 替代 |
| feature/task-003-akshare-adapter-rebased | 08388c5 → a102ac9 | C |
| feature/task-003c-tls-rebased | 9df3660 → 804a331 | C |
| feature/local-market-demo-rebased | b3e4e31 → 74536e0 | C；关联 detached 工作树另列 D 候选 |
| chore/project-baseline-20261017 | 0ab86e1 → 824d634 | C |
| docs/trading-system-conversation-archive-20261017 | b7113d1 → d09a259 | C |
| codex/task-004-master-calendar-resumed | bb596a9 → 0578f9c | C |
| docs/model-routing-governance | b53e5b7 → c65a318 | C；工作树含独有忽略证据 |
| codex/task-009-tencent-integration | 本地079565b / 远端74d0a18 → 31a575f | C；相同 tree，API 发布导致提交元数据不同 |
| codex/task-015-source-health | 本地59367bd / 远端15eb0f1 → 693fab1 | C；相同 tree，全部业务成果在 main |

其余逐项结论：

- `codex/task-004-master-calendar` 的 HEAD 本身是 main 祖先 cd1b2b1，无独有已提交功能，但工作树有原始 TASK-004 现场，**E**。
- `codex/task-003c-tls-diagnostics`、`codex/local-market-demo` 的旧全树与对应集成祖先只差 README 和新增 CI，业务/测试/报告已保留，**C：被后续实现替代**，不再整支合并。
- `codex/task-004a-source-review`、`docs/task-004a-report-only`，**B：同一独有报告**；其他旧功能重复。
- `codex/task-local-reconcile-001`，#13 已提交内容被整合，但关联 TASK-008 dirty 工作树与未知文本保留，**E**。
- `codex/task-demo-002-network-diagnostics`，#14 内容已进入 main，独有 DEMO-003 原始证据不在 Git，**C**。
- `codex/task-demo-003-single-probe`，本地0172171 / 远端b7cbe9e 的 tree 同为 `3132465477c70b7cf5b4074593b92360335df460`；**C：开放报告归档 PR**。
- `codex/task-demo-004-akshare-direct`，本地6bb1ed0 / 远端d4701c8 的 tree 同为 `977b9f2371a1823f74357f15b66e6e877a7aced1`；**C：开放诊断归档 PR**，工具未进入 main。
- `github/main` 与本次任务分支起点，**A**。缓存 origin refs 仅作为本地记录，不宣称仍代表远端最新；本轮 API 的 19 个分支均已逐项列入 JSON。

上述 C 类分支可进入后续整理候选清单，但 **本任务不将具有 squash 前独有 SHA 的分支直接列为“无独有提交、可立即删除”**。若要删除，先批准长期保留这些原始 SHA 的归档 ref、关联证据和 PR，再二次核验；tree 等价只证明最终文件内容，不抹除提交溯源价值。

## 6. 重复文件、独有成果和证据

| 位置/内容 | 实际比较与归类 |
| --- | --- |
| 原 TASK-004 `reference_data/`、security_master、trading_calendar、reference_schema/schema、两份测试及契约 | 工作文件与 main 一致，C 历史实现；不复制。README/旧实施报告不同是历史衔接内容，继续归档，保留 staged 与 unstaged 两层 |
| 原 `docs/REFERENCE_PROJECT_REVIEW.md` | main 无此路径，B 待审文档成果；本轮仅记录文件/哈希与用途，不替它执行内容验收 |
| `AI-trade-main-demo` 的 tx_adapter、ingestor、Demo/UI 测试、指南 | 与 main 有实际差异，不能称完全重复。main 额外保留 #14 安全异常链、修正腾讯 provider/endpoint/symbol、拒绝小数股数及非法数值、标记代理为配置推断。原版本被后续修正替代，C；覆盖回 main 会回退修复 |
| 原 TASK-008/008A/008B 报告 | main 为追加了 TASK-009 校正、去除行情值的审查副本；原件仍有历史价值，C。旧审计原件与 main 脱敏摘要的哈希不同是有意保留边界，不能当相同文件删除 |
| 原 `tools/diagnose_no_proxy_market_get.py`、`diagnose_tx_market_get.py` 及对应两份 unit 测试 | main 没有，B：需独立安全/预算/日志审查后决定归档或小范围 PR；不能因为有新健康模块就断言完全替代 |
| 原 DEMO-005/006 报告、008A/B、005/006 审计 | main 没有这些原路径，C 证据归档；不得未经审查复制完整 JSON 或原始响应 |
| 原 `新建 文本文档.txt` | 未跟踪，E：用途尚未确认，记录哈希、保留原件，不纳入本 PR |
| demo-002 的 artifacts/task-demo-003 | direct-tls、live-direct-audit、live_direct_acceptance、preflight 四个文件只在此；C，保留独立握手与失败请求的证据差别 |
| demo-004 的 live-audit 与 #16 交付 | C，正式 SDK 单次诊断记录，与手写探针不同；没有证据证明故障根因已定位或网络验收通过 |
| 原主目录/C 盘 TASK-004 工作树的 artifacts | TASK-003A/B/C、004/004A/GOV 历史安装、测试、TLS、数据源探测、保护日志；不同运行的同名日志不得按文件名删除 |
| task-009/task-015 的 artifacts | 测试/保护日志、6 次默认离线健康检查的 request/result 对；C，合并后仍是唯一运行证据 |
| `artifacts/task-008a/temp-sqlite/task008a.sqlite3` | 仅本地隔离测试产物，147,456 字节，SHA-256 `d3630aa9d53035007f3c3a3922910a7d253ed5b816ccfd823edc4b33c78dba4b`；本轮只做文件哈希，不打开业务/生产数据库，不提交该文件 |
| `.venv`、egg-info、pytest/bytecode 缓存 | 环境/可重建产物与证据区分；只对补录 egg-info 逐文件哈希，其他 runtime 未做内容验收，不整目录宣称可删 |

JSON 对每个条目保留相对路径、原始/LF 哈希、tracked/untracked/ignored、HEAD/index blob、所属 HEAD、main blob、相同/差异/不在 main 以及整理类别。完全相同的副本可通过 duplicate_file_groups 追溯；不同文件必须逐项审查，不仅依赖是否叫 demo 或是否较旧。

## 7. 安全清理建议与删除前复核

**本轮实际删除数量为 0。** 原主仓库、main-demo、C 盘工作树、demo-002/003/004、task-009/015 及 report-only 均继续保留。没有任何 dirty 工作区、未跟踪研究/未知文件、唯一证据或开放 PR 的独有交付被列为立即可删。

目前仅 `F:\codex-agnes\AI-trade\.worktrees\local-demo-verify` 工作目录列为 **D 候选**：detached HEAD 为 b3e4e31，tree 与已合并 PR #7 的 main 祖先完全一致；原 head 也由仍存在的远端 `feature/local-market-demo-rebased` 保留；没有独有提交或手写文件，只有 5 个构建生成 egg-info。二次核验如下，任何失败/新文件/状态变化即转 E，且仍须用户明确批准后才能实际清理：

```powershell
$candidate = 'F:\codex-agnes\AI-trade\.worktrees\local-demo-verify'
git -C $candidate rev-parse --show-toplevel
git -C $candidate rev-parse HEAD
git -C $candidate status --porcelain=v1 --untracked-files=all
git -C $candidate ls-files --others --exclude-standard
git -C $candidate ls-files --others --ignored --exclude-standard
git -C $candidate diff --exit-code
git -C $candidate diff --cached --exit-code
git -C $candidate rev-parse 'HEAD^{tree}'
git -C $candidate rev-parse '74536e020b04bc264c41d1ea4302e9583fd51266^{tree}'
git -C $candidate ls-remote origin refs/heads/feature/local-market-demo-rebased
git -C $candidate worktree list --porcelain
```

预期：HEAD b3e4e31，两个 tree 同为 `01e411a75ff364d9b5b7ea72fb0cd7a821d41c95`，diff/status/非忽略未跟踪为空，远端 ref 未变；ignored 只允许本次记录的 5 个 `src/a_share_quant_v1.egg-info/` 文件，并逐一重新核对 JSON 的哈希/内容为可重建元数据。另确认无运行进程或 editable 环境依赖该目录、无新嵌套仓库/文件和未保留提交。`git ls-remote` 网络失败不算通过，不能直接用缓存替代。以上仅只读命令，没有提供或执行删除命令。

第 5 节 tree 等价的 C 类分支是**后续可整理候选**，不是本轮已满足 D 条件：必须先保留 squash 前 SHA/PR/必要日志的长期索引，逐分支 `git ls-remote origin refs/heads/<branch>`、`git rev-parse <head>^{tree}`、与表内祖先 tree 比较，检查 `git log <verified-main>..<branch>` 中每项提交的内容/归档位置及所有关联 worktree 的 staged/unstaged/untracked/ignored；没有明确归档 ref、head 已变化或存在唯一证据则继续 C/E。当前不删除任何这些本地或远端分支。

## 8. PROJECT_STATUS 修正及 CLI 缺口

原 PROJECT_STATUS 的顶层仍称 TASK-015 “未进入 main”、TASK-009 “待集成”，GitHub 总表仍停在治理基线，并称 CI 未安装 Demo，已经过时。本分支修正当前索引：#17/#18 已合并、健康框架在 main、离线 412/1、真实健康未知、连接探针未运行、真实日历/可信 freshness 未验收、无操作系统调度安装、腾讯候选/非生产、#11/#13–#16 实际仍开放；CI 已安装 `[test,demo]` 并含离线 AppTest，不是实机浏览器/真实接口测试。

对 TASK-004 仍明确“模型/存储已实现；真实来源/历史质量未通过”；对 TASK-008 只沿用旧最小证据且披露 SDK 调用数不等于 HTTP 次数。**没有修改任何历史 IMPLEMENTATION 报告或对话归档。** 此修正只有在本 PR 合并后才进入 GitHub main；原工作树同名文件均未覆盖。

实际读取 `health_cli.py`：其 argparse 没有 verified-calendar/expectation 输入，`HealthService().check(...)` 未传 `expectation`；`health_service.py` 的 API 可接收 `CalendarExpectation`，`health_schedule.py:calendar_expectation` 可复用已注入的严格日历查询，但 CLI 没有调用链。因此现有 CLI 无法提供已认证日历预期，不能用它宣称新鲜度通过。默认 null/unknown 是正确保守结果。

建议独立任务：先验收来源/历史覆盖/版本发布时间与收盘截点，再设计只读的已验证日历输入及 expectation 接线，补 as_of、未知/源错误、未收盘、跨交易所与 CLI 离线/真实测试，另立 H 审查。不能只加“强制 known”开关、按星期推算或在报告中省略 unknown。本审计不修业务代码。

## 9. 实际验证、保护复核与交付

本次在新工作树显式 `PYTHONPATH=...task-016\src`，只读复用已安装的 Python 3.12.14 解释器；没有安装或升级旧环境。本轮完整离线套件仍使用默认网络阻断和临时数据库：

```powershell
cd F:\codex-agnes\AI-trade-task-016
$env:PYTHONPATH = 'F:\codex-agnes\AI-trade-task-016\src'
& 'F:\codex-agnes\AI-trade-main-demo\.venv\Scripts\python.exe' -m pytest -q
& 'F:\codex-agnes\AI-trade-main-demo\.venv\Scripts\python.exe' -m pip check
git diff --check
```

| 检查 | 本轮实际结果 |
| --- | --- |
| 完整离线 | **412 passed、1 skipped、1 warning in 27.90s**，退出码 0；skip 为未传 `--run-akshare-integration` 的真实 AKShare 用例 |
| 缓存警告 | PytestCacheWarning / WinError 5，创建新工作树 .pytest_cache 时目录重命名被拒；测试断言没有失败，不通过虚报“无警告”掩盖环境限制 |
| 依赖 | `No broken requirements found.`，退出码 0 |
| GitHub 访问 | API 通过；Git CLI fetch 环境连接失败，二者分别记录 |
| 真实行情/主数据/日历请求 | **未执行，0 次** |
| 实机 Edge/Chrome UI、样本外回测 | **未执行**；离线 AppTest 不替代 |
| 文档/JSON/差异和原工作树保护 | 交付前实际检查结果见审计 JSON 的 `delivery_checks` / `preservation_check`；无业务代码或历史报告变更 |

本任务仅新增本报告和审计 JSON，修改 PROJECT_STATUS。原始 patch、行情/SQLite、原始网络响应、凭据和测试日志均不提交。提交 SHA/PR 链接以交付消息及 PR 元数据为准，避免报告自引用尚未生成的 SHA；本次普通 diff 自检不充当独立 H 审查。建议后续单独治理审查绑定最终 SHA，未启动后续任务。

## 10. 后续统一开发建议与待确认事项

1. GitHub `main@693fab10fe7f88581fc326015556ddc0aa83c1ea` 是本轮已核实基线；下次必须重新 API/fetch 核实，不能永久钉住这个旧 SHA。当前没有名为 main 的本地 checkout，也没有把原目录修成 main。
2. `F:\codex-agnes\AI-trade` 继续作为共享仓库和 TASK-004 现场保护根。后续在用户认可后，建议固定一个干净开发目录，例如 **`F:\codex-agnes\AI-trade-dev`（尚未创建）**，从重新核实的最新 main SHA 建独立 `codex/<TASK>` 分支/worktree；不要默认使用名字含 main 的旧 Demo 目录。
3. 当前可审阅本任务的目录是 `F:\codex-agnes\AI-trade-task-016`；它包含三个文档改动，不是已完成配置的正式行情运行环境。后续运行环境采用自己的 .venv，显式核对导入路径；不把此次只读借用解释器变成正式运行依赖。
4. 先审核本 PR 的状态修正/审计，再决定 #11 报告拆分、#13/#14 被替代关闭（注意 #16 base）、#15 报告归档、#16 retarget/独立审查。再审查本地研究/探针和未知文本；最后才讨论清理，不批量合并旧树。
5. 独立 H 审查与真实源/日历/生产许可没有新增通过证据；Git 网络仍阻断，缓存未更新，临时证据尚未形成长期备份，runtime 内部未逐文件检查。这些是明确的剩余限制，不通过代码合并消除。

任务完成后停止，等待用户审核整理方案；本次不自动进行上述后续动作。

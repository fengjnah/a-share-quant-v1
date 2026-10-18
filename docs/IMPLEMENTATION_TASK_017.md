# TASK-017：干净的本地 main 与统一开发工作区

执行日期：2026-10-18，Asia/Shanghai。**结果：PASS（本报告核验时点）**。正式 Git 管理仓库仍是 `F:\codex-agnes\AI-trade`；后续推荐的干净基线目录为 **`F:\codex-agnes\AI-trade-dev`，检出本地 main，跟踪 origin/main**。原目录及全部旧工作树继续保留。

## 1. 执行配置与规则

- 唯一执行模型：`gpt-6.1-sol`，固定推理强度 `high`，H。依据本会话用户最近对当前界面 GPT-6.1 Sol / High 的确认，与本任务推荐配置一致；工具未提供独立运行时型号证明，费用未知。未换模型、调用外部模型或委派子代理。
- 已实际读取：AGENTS、MODEL_ROUTING_POLICY v1.0、TASK_TEMPLATE、PROJECT_STATUS。原正式仓库四文件均缺失，已明确记录；实际读取位置为 `F:\codex-agnes\AI-trade-task-016`。新 main 创建后逐字节核对这四份文件与已读版本完全一致，没有以历史摘要代替读取。
- 适用 G01–G12：核实远端/PR 与基线、保护原工作区、固定模型、数据/未知语义不变、真实证据分类、无生产数据库或交易、隔离报告/测试、不直接提交 main、如实记录结果；普通自检不称为独立 H 审查。
- 本任务用户约束优先：只在成功的 `ls-remote` 和 fetch 核实后建立正式基线；若失败即停止，不采用 API 补对象、旧缓存或关闭 TLS 的替代方案。本轮两个 Git 操作均成功，不需要触发该阻断。
- 修改边界：新增本报告；允许创建指定的 main 工作树及独立报告分支。未改业务、Schema、契约、旧文件或永久代理/TLS 配置；无真实行情请求。报告独立提交/仅报告 PR 按任务第九节授权交付，不操作其他 PR，不自动合并。

## 2. 原始现场与前置安全判断

起始正式仓库：`F:\codex-agnes\AI-trade`，HEAD **`cd1b2b1412e4dbe345e4eac09330b94977211372`**，当前分支 `codex/task-004-master-calendar`。本地 main 不存在（show-ref 退出 128，branch --list 为空）；`AI-trade-dev` 不存在，也没有工作树占用 main。起始 `origin/main` 缓存为 `693fab10fe7f88581fc326015556ddc0aa83c1ea`，未将其直接当作最新远端。

在任何 fetch/创建之前，为全部 **11 个既有工作树**记录：

```powershell
git rev-parse --show-toplevel
git status --short --branch --untracked-files=all
git branch -avv
git worktree list --porcelain
git rev-parse HEAD
git diff --stat
git diff --cached --stat
git ls-files --others --exclude-standard
```

另保存各自 staged/unstaged 二进制补丁、index 字节 SHA-256、完整 ls-files --stage、工作文件 SHA-256 和分支/根目录。原目录 16 项 tracked 的暂存/工作区修改全部保留，其中重点三文件为：

| 文件 | 原状态 | 原工作文件 SHA-256（前后相同） | 原 index blob（前后相同） |
| --- | --- | --- | --- |
| README.md | MM | `2b50ec88b85b73700ccd2ebc34418124993f5865cb826525fa2bce31f17c107b` | `30ef2473efd3569e32cf3a8851e13f482ce7005f` |
| docs/IMPLEMENTATION_TASK_004.md | AM | `37c60d5425ed3f73b8757bd522aa4fa9066eca0e2b55303715958892966df34c` | `e1aacb0de0618b1ff8792590481a02785d1aad1b` |
| tests/unit/test_reference_data.py | AM | `d4fec8142e0a1033e7738d246e8a8d48cab3e39cbf65d93eb96c16818da775f1` | `78c1f5ea0ec1fa811f0fa7f278d52ac124658c0a` |

未跟踪的 REFERENCE_PROJECT_REVIEW 报告和嵌套 worktree 指针/目录保留；main-demo 的 4 个 tracked 修改和 17 个未跟踪文件也保持不变。没有因为 TASK-004/008 部分内容已进入 main 就丢弃其原始 index 或工作文件。

| 原有工作树 | 起始 HEAD | 保护结果 |
| --- | --- | --- |
| `F:\codex-agnes\AI-trade` | cd1b2b1 | 原分支、16 项 staged/unstaged、未跟踪及历史产物保留 |
| `C:\Users\iyoyi\.codex\worktrees\task-004-resume\AI-trade` | b53e5b7 | HEAD、index、文件不变 |
| 原目录 `.worktrees/local-demo-verify` | b3e4e31，detached | 保留，未执行上轮清理建议 |
| 原目录 `.worktrees/task-004a-report-only` | b0a1ba1 | 独有报告与分支保留 |
| `AI-trade-demo-002` | 365a01c | 保留 |
| `AI-trade-demo-003` | 0172171 | 保留 |
| `AI-trade-demo-004` | 6bb1ed0 | 保留 |
| `AI-trade-main-demo` | b31847f | TASK-008 和其他未提交材料保留 |
| `AI-trade-task-009` | 079565b | 保留 |
| `AI-trade-task-015` | 59367bd | 保留 |
| `AI-trade-task-016` | d3edd50 | 保留，未将本报告写入该工作树 |

上述简称路径除 C 盘和嵌套目录外，前缀均为 `F:\codex-agnes\`。完整 SHA、命令输出和保护数据保存在本地证据中。

## 3. 远端核实与 PR #19

本轮不沿用 TASK-016 的网络失败结论；以下均为这次实际执行：

```powershell
git -C F:\codex-agnes\AI-trade ls-remote origin refs/heads/main
# 6987ed1d1435e19067fdd218beb68763eaa76f83  refs/heads/main

git -C F:\codex-agnes\AI-trade fetch origin refs/heads/main:refs/remotes/origin/main
# From https://github.com/fengjnah/a-share-quant-v1
#    693fab1..6987ed1  main -> origin/main

git -C F:\codex-agnes\AI-trade rev-parse origin/main
# 6987ed1d1435e19067fdd218beb68763eaa76f83
```

`ls-remote` 于 **15:06:17 +08:00** 完成，退出码 0，约 0.97 秒；fetch 于 **15:06:43 +08:00** 完成，退出码 0，约 1.75 秒。成功查询到的 SHA 与更新后的 origin/main 完全相同；没有失败重试、强制 fetch、改代理或使用未经核实的缓存。

GitHub API 另外核实 [PR #19](https://github.com/fengjnah/a-share-quant-v1/pull/19)：closed、merged=true，`merged_at=2026-10-18T07:00:13Z`，**实际合并提交为 `6987ed1d1435e19067fdd218beb68763eaa76f83`**，PR head 为 `0340c21c7b970bf62968acf41e6b444c7d17338d`，base 为 `693fab10…`。本次为合并提交，不将 PR head、本地 TASK-016 提交或旧 squash 基线混为新 main。

创建后于 **15:08:59 +08:00** 再成功执行一次 ls-remote，仍返回 6987ed1…；不是通过无限重试取得结果。Git 没有显式禁用 http.sslVerify，GIT_SSL_NO_VERIFY 未启用；未修改这些配置。读取未配置的 http.sslVerify 返回 1 表示未设置，不是网络或证书失败。

## 4. 创建干净 main 与隔离报告

创建前再次确认目标目录不存在、本地 main 不存在、无其他工作树占用，并确认 origin/main 与已核实 SHA 相同，才执行：

```powershell
git -C F:\codex-agnes\AI-trade worktree add -b main F:\codex-agnes\AI-trade-dev origin/main
# branch 'main' set up to track 'origin/main'.
# HEAD is now at 6987ed1 Merge pull request #19 ...
```

Git 自动建立 upstream，未变更原目录分支/index，也未复制任何未提交修改。新目录的 `.git` 是关联工作树指针，共享管理目录仍位于原正式仓库；不是独立 clone，**不能删除原仓库的 .git 来“整理”新目录**。

报告采用独立工作树 `F:\codex-agnes\AI-trade-task-017`、分支 `codex/task-017-main-workspace`，起点也为 6987ed1…，仅新增 `docs/IMPLEMENTATION_TASK_017.md`。正式 dev 目录始终保留 main，不为报告或测试切换分支/写文件。工作树总数由 11 增至 13，没有移除旧工作树。

## 5. 八项验收

| 验收 | 实际结果 | 状态 |
| --- | --- | --- |
| 成功远端操作核实最新 main | 两次 ls-remote 返回 6987ed1…；fetch 成功 | PASS |
| origin/main 与远端相同 | rev-parse 为同一完整 SHA | PASS |
| dev 的本地 main 与 origin/main 相同 | HEAD/main 均为 6987ed1…；rev-list 左右计数 `0 0` | PASS |
| 新工作区干净 | status --porcelain=v1 --untracked-files=all 输出为空 | PASS |
| 本地 main 跟踪 origin/main | main@{upstream} = origin/main | PASS |
| 原三个重点文件差异保留 | MM/AM/AM 不变，工作哈希、index blob、staged/unstaged patch 均相同 | PASS |
| 原旧分支、工作树、索引及未跟踪保护 | 11 个旧工作树复核通过；777 个文件条目及原始 index/补丁不变；16 个原本地分支指向与起始记录吻合 | PASS |
| PR #19 合并提交在新历史中 | merge-base --is-ancestor 6987ed1… HEAD 退出 0；HEAD 本身即该合并提交 | PASS |

关键核验命令及输出：

```powershell
git -C F:\codex-agnes\AI-trade-dev status --short --branch
# ## main...origin/main
git -C F:\codex-agnes\AI-trade-dev rev-parse --show-toplevel
# F:/codex-agnes/AI-trade-dev
git -C F:\codex-agnes\AI-trade-dev rev-parse HEAD
git -C F:\codex-agnes\AI-trade-dev rev-parse origin/main
# 两条均为 6987ed1d1435e19067fdd218beb68763eaa76f83
git -C F:\codex-agnes\AI-trade-dev rev-parse --abbrev-ref 'main@{upstream}'
# origin/main
git -C F:\codex-agnes\AI-trade-dev rev-list --left-right --count main...origin/main
# 0  0
git -C F:\codex-agnes\AI-trade-dev branch -vv
git -C F:\codex-agnes\AI-trade worktree list --porcelain
```

保护比较允许的预期元数据变化只有：origin/main/FETCH_HEAD 更新、新 main 与报告分支/工作树登记、旧分支因 origin/main 更新而变化的 ahead/behind 表头。旧 HEAD、实质状态条目、index 原始字节/条目、未跟踪列表、补丁和受检文件内容均未改变。没有重新暂存、格式化、reset、clean、rename、删除或切换原目录。

## 6. 验证与本地证据

本地证据目录：`C:\Users\iyoyi\AppData\Local\Temp\task-017-20261018-150551`。其中 before.json、workspace-*-staged/unstaged.patch、ls-remote.json、fetch.json、pr19.json、post/before.json、preservation-check.json、verification.json、pytest.txt、pip-check.txt 保存原始命令/退出码和复核结果。补丁、原始证据及日志不纳入公开提交；临时目录不是永久备份，本任务也不清理旧长期证据。

按 G11，在报告工作树实际运行完整离线套件，不在正式 dev 目录制造 pytest/bytecode 缓存：

```powershell
cd F:\codex-agnes\AI-trade-task-017
$env:PYTHONPATH = 'F:\codex-agnes\AI-trade-task-017\src'
$taskPython = 'F:\codex-agnes\AI-trade-main-demo\.venv\Scripts\python.exe'
& $taskPython -m pytest -q -o cache_dir=C:/Users/iyoyi/AppData/Local/Temp/task-017-20261018-150551/pytest-cache
& $taskPython -m pip check
git diff --check
```

结果：**412 passed、1 skipped in 20.91s，退出码 0**；跳过既有需 `--run-akshare-integration` 显式启用的真实 AKShare 测试；本轮无 pytest 缓存警告。依赖检查 `No broken requirements found.`，退出码 0。解释器仅只读复用，未安装/升级任何环境；实际被测业务代码来自 task-017/src，与新 main 的业务文件相同。本任务不声称 dev 已有自己的 Python 环境。

报告在交付前进行单文件范围、diff 空白、围栏及内容/凭据有限检查；不新增 Markdown lint 依赖、不虚称完整 lint 或独立审查通过。真实行情测试、浏览器 UI、样本外回测、生产数据库初始化和部署均**未执行**；Git 远端核验成功不代表这些功能验收通过。

报告发布的 CLI push 单次尝试退出 128：`Cannot prompt because user interactivity has been disabled` / `unable to get password from user`。这是非交互 Git 写入凭据不可用，不是 ls-remote/fetch 失败，不影响已建立的 main 基线。未启用交互提示、修改凭据配置或重试推送；后续若经已连接 GitHub API 交付，仅发布相同报告文件并核对完整 tree，远端/本地提交元数据差异在最终交付中披露。原始结果保存在本地 publish.json，未包含任何密码。PR 链接和实际发布结果以最终交付为准。

## 7. 后续采用方式与限制

- **推荐目录/分支：`F:\codex-agnes\AI-trade-dev` / `main`**，作为干净基线入口。正式 Git 管理目录仍是 `F:\codex-agnes\AI-trade\.git`；旧 TASK-004/TASK-008 工作区继续保护，不在其上拉取覆盖。
- main 保持干净；后续实现任务从重新核实的最新 origin/main 创建独立 `codex/<TASK>` 分支/工作树，实施代码不直接提交 main。新任务开始仍须读规则、核实 HEAD/status/远端，不能因为此报告 PASS 就跳过检查。
- 后续用户合并其他 PR 后，本地 main 不会自动更新。确认 dev 干净、无独有提交且 fetch 成功后，才采用人工受控 fast-forward 同步；如有分叉、独有提交或目录冲突则停止报告，不强制重建。
- 新 dev 未创建 .venv、未装依赖、未启动 Demo、未初始化生产数据库；可另立环境准备任务，在 dev 自己的环境中验证依赖和导入路径。不要把本次测试对旧解释器的只读借用变成正式运行依赖。
- PROJECT_STATUS 的 TASK-016 段落保留的是当时“无本地 main/缓存过时”的现场，本报告给出此后实际变化；未为同步本机状态而修改 main 上的历史记录。后续任务应同时读取本报告，不能把旧审计快照当成当前机器状态。
- 没有已知阻断八项验收的问题。未逐文件检查 .venv/pytest/bytecode 的所有内部内容；未迁移旧未提交代码、清理目录或验证生产能力，这些不在本轮范围。

报告提交 SHA、交付 PR 链接以交付消息为准，不在文件中自引用尚未生成的提交。若发布报告，不会改变 dev/main 或 origin/main 的基线；用户合并报告后应再次按上述流程核验同步。本任务到此停止，不启动 TASK-018，不删除旧目录、分支或工作树。

# Streamlit 正式工作台一键启动说明

## 1. 当前版本与代码来源

- GitHub 仓库：`fengjnah/a-share-quant-v1`
- 当前实现分支：`codex/m0-production-db-001`
- 交付 PR：[#47](https://github.com/fengjnah/a-share-quant-v1/pull/47)
- 本次交付记录的实现提交：`4bcda30a8921c144185e4b7091f45df710b644ec`
- PR 记录的最终 head：`fd140b048444d11f54229bfdac6c36d573da8666`
- PR 状态：Draft、尚未合并。合并前，`main` 分支不保证包含这些文件。

请以 GitHub PR 页面显示的最新 head SHA 为准；若 PR 有后续提交，上述 SHA 仅代表当前文档编写时记录的版本。

## 2. 文件放置位置

以下路径均相对于仓库根目录：

- 一键启动脚本：`scripts/start_workbench.ps1`
- 日常使用指南：`docs/LOCAL_WORKBENCH.md`
- 本文档：`docs/LOCAL_STREAMLIT_STARTUP.md`
- Streamlit 应用入口：`src/ai_trade/demo_app.py`
- 数据库诊断 CLI：`src/ai_trade/storage/workbench_cli.py`

Codex 本次任务记录中的工作树路径为：

`C:\Users\iyoyi\.codex\worktrees\m0-production-db-001\AI-trade`

如果该工作树在当前电脑上不存在，请使用你本地克隆仓库的实际根目录；不要把另一个 worktree 的路径直接当成本机路径。

## 3. 当前正式数据库和 Python 环境

启动脚本默认绑定：

- SQLite 正式研究库：`F:\codex-agnes\AI-trade\data\sqlite\workbench.sqlite3`
- Python 解释器：`F:\codex-agnes\AI-trade-main-demo\.venv\Scripts\python.exe`
- 本地监听地址：`127.0.0.1`
- 默认端口：`8524`
- 浏览器地址：`http://127.0.0.1:8524/?view=market`

这些路径是脚本中的当前默认值，不是自动探测出来的通用路径。如果项目移动、虚拟环境重建或数据库位置变更，应显式传入参数或经代码审查更新脚本；不能让脚本悄悄回退到 Demo 数据库。

## 4. 一键启动步骤

### 推荐方式：PowerShell

先进入包含 `scripts` 目录的仓库根目录，然后运行：

```powershell
.\scripts\start_workbench.ps1
```

若 PowerShell 的执行策略阻止本地脚本，可只对当前启动进程使用：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_workbench.ps1
```

这不会永久修改系统执行策略。不要通过关闭 Windows 安全机制解决路径或权限问题。

启动成功后，在浏览器打开：

```text
http://127.0.0.1:8524/?view=market
```

结束服务时回到运行脚本的终端，按 `Ctrl+C`。

### 可选：显式指定路径和端口

```powershell
.\scripts\start_workbench.ps1 `
  -Python 'F:\codex-agnes\AI-trade-main-demo\.venv\Scripts\python.exe' `
  -Root 'F:\codex-agnes\AI-trade\data\sqlite' `
  -Port 8524
```

端口被占用时，可以临时改为例如 `8525`，然后访问 `http://127.0.0.1:8525/?view=market`。

## 5. 启动脚本做什么

脚本会在启动 Streamlit 前：

1. 设置当前进程的 `PYTHONPATH`、UTF-8 和正式工作台配置。
2. 将 `QUANT_DB_PATH` 明确绑定到指定根目录下的 `workbench.sqlite3`。
3. 设置 `AI_TRADE_STRICT_WORKBENCH=1` 和 `AI_TRADE_READ_ONLY=1`。
4. 移除当前进程中的 `AI_TRADE_DEMO_ROOT`，防止正式入口意外读临时 Demo。
5. 调用 `ai_trade.storage.workbench_cli diagnose`，核验真实连接路径、Schema/checksum、DDL 和 SQLite 完整性。
6. 只有诊断成功才启动 Streamlit；失败则停止，不创建替代数据库、不自动初始化、不回退 Demo。

默认工作台是只读的。这个脚本不负责行情采集、历史样本迁移或数据库初始化。

## 6. 确认当前运行的代码版本

在仓库根目录执行：

```powershell
git branch --show-current
git rev-parse HEAD
git status --short
```

预期分支在 PR 未合并时为 `codex/m0-production-db-001`。记录 `git rev-parse HEAD` 的输出，用于确认实际运行版本；如果工作区有未提交改动，`git status --short` 会显示出来。

PR 合并后，若希望改为运行 main，应先确认 PR 已合并，再执行：

```powershell
git switch main
git pull --ff-only
git rev-parse HEAD
```

只有确认 main 已包含 `scripts/start_workbench.ps1` 和相关数据库代码后再启动。不要在 PR 未合并时假定 main 已包含该功能；也不要在存在未提交修改时直接切换分支或覆盖工作区。

## 7. 故障处理与安全边界

- **找不到 Python**：确认默认虚拟环境路径是否存在；必要时通过 `-Python` 指定有效解释器。
- **数据库不存在**：停止并确认正式数据库路径。日常启动脚本不会自动创建空库。
- **Schema、checksum、DDL 或完整性检查失败**：停止启动，保存错误输出，交由独立任务调查；不要删除数据库、侧车文件或备份后重试。
- **端口被占用**：使用另一个端口启动，避免终止不明进程。
- **页面没有行情**：当前正式库已报告为 Schema v2、业务表为空。数据库结构和只读连接验收通过不代表已经采集行情；页面没有真实行情时，不应以 Demo 数据冒充。
- **页面的 M3 非股票研究输入**：现有观察数据仍有独立来源/目录边界；七张表并不等于所有 M3 输入都已入库。不要把页面可打开误判为 M0→M3 真实数据闭环完成。
- **不要提交到 Git**：`workbench.sqlite3`、备份、日志和原始行情属于本地状态，不应提交进仓库。

## 8. 验收记录的边界

PR #47 的报告记录了离线测试、SQLite 结构/完整性、备份与隔离恢复等结果，并说明自动浏览器核验被安全策略阻断。因此，不应把这些记录表述为自动浏览器 UI 验收通过。启动脚本的实际运行结果应以本机终端输出和页面实际连接诊断为准。

更多数据库初始化与架构说明见 [LOCAL_WORKBENCH.md](LOCAL_WORKBENCH.md) 和 [M0_PRODUCTION_DB_REPORT.md](M0_PRODUCTION_DB_REPORT.md)。

# Windows 本地 Streamlit 正式工作台一键启动

## 1. 固定规则

- 仓库：`fengjnah/a-share-quant-v1`
- 唯一日常工作区：`F:\codex-agnes\AI-trade-dev`
- 唯一允许的运行分支：`main`
- 启动脚本：`scripts/start_workbench.ps1`
- Python 环境：`F:\codex-agnes\AI-trade-dev\.venv\Scripts\python.exe`
- 新入口数据根：`AI_TRADE_DATA_ROOT=F:\codex-agnes\AI-trade-data`
- 切换后正式 SQLite：`F:\codex-agnes\AI-trade-data\sqlite\workbench.sqlite3`
- 默认监听：`127.0.0.1:8524`
- 浏览器：`http://127.0.0.1:8524/?view=market`

`AI-trade-dev` 是代码工作区，数据根在Git仓库之外。**目录迁移仍待独立H/人工合并/停写与正式迁移验收，当前旧库仍在AI-trade\data\sqlite，8524未切换。** 见[迁移记录](audits/TASK-M0-DATA-DIRECTORY-RELOCATION-001.md)。不能仅设置新变量后创建空库冒充迁移，不能删除旧库。

## 2. 当前 PR 与版本管理

旧路径接线已随 [PR #47](https://github.com/fengjnah/a-share-quant-v1/pull/47) 合并；本期独立目录修订使用 `codex/m0-data-directory-relocation-001` 交付Draft PR，独立H和人工合并前不进入main。开发分支只用于交付，不是日常运行分支。

本期PR合并前，`AI-trade-dev\main` 仍使用已合并的旧路径脚本。审查/人工合并后，先记录并停止已确认的旧服务和全部读写者，再于维护窗口确认本地工作区并快进更新；不要让运行服务在文件监视器下自动混用新代码与旧配置：

```powershell
Set-Location 'F:\codex-agnes\AI-trade-dev'
git status --short
git branch --show-current
git pull --ff-only origin main
git rev-parse HEAD
```

只有在工作区干净、当前分支为 `main` 时才执行更新。若 `git status --short` 有输出，先检查并自行保存修改；不要用 reset、clean、强制切换或覆盖操作处理。

## 3. 一键启动

在 PowerShell 中：

```powershell
Set-Location 'F:\codex-agnes\AI-trade-dev'
.\scripts\start_workbench.ps1
```

目录路径本身不是启动命令；先用 `Set-Location` 进入目录，再运行上面的 `.ps1`。
该脚本包含中文，编辑时须保存为 **UTF-8 with BOM**，兼容 Windows PowerShell 5.1；
无 BOM 的 UTF-8 可能被误读并出现乱码、字符串未结束等解析错误。
PowerShell 7 可直接读取无 BOM 的 UTF-8；尚未取得编码修复时，可从已安装的 PowerShell 7 执行：

```powershell
pwsh -NoProfile -File 'F:\codex-agnes\AI-trade-dev\scripts\start_workbench.ps1'
```

首次使用且 `.venv` 不存在时，先在该工作区创建独立环境并安装项目已声明的依赖：

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e '.[demo,test]'
```

若 8524 已有工作台服务，请继续使用现有页面；不要重复启动或终止不明进程。

如当前 PowerShell 执行策略阻止脚本，可仅对这次进程使用：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File 'F:\codex-agnes\AI-trade-dev\scripts\start_workbench.ps1'
```

启动成功后打开：

```text
http://127.0.0.1:8524/?view=market
```

停止服务：回到运行脚本的终端按 `Ctrl+C`。如需临时更换端口，可运行 `.\scripts\start_workbench.ps1 -Port 8525`，然后打开 `http://127.0.0.1:8525/?view=market`。

## 4. 脚本强制执行的检查

脚本会在启动前验证：

1. 脚本确实来自 `F:\codex-agnes\AI-trade-dev`，不是 Codex worktree 或其他克隆目录。
2. 当前 Git 分支必须是 `main`；不会自动切换分支。
3. Git 工作区必须干净；如存在未提交或未跟踪文件，脚本停止，避免误运行未经确认的代码。
4. Python 必须是该工作区的 `.venv\Scripts\python.exe`；不存在就停止，不会回退到 `AI-trade-main-demo` 或其他环境。
5. 正式数据库文件必须已存在；脚本不会创建、初始化或迁移数据库。
6. 启动前运行 `ai_trade.storage.workbench_cli diagnose`，核验连接路径、Schema/checksum、DDL 和 SQLite 完整性。
7. 显式设置正式工作台根目录、`QUANT_DB_PATH`、严格模式和只读模式，移除该进程的 Demo 根变量。
8. 只有诊断成功才启动 Streamlit；失败则停止，不会回退到 Demo。

路径改造审查并合并、正式迁移完成后，脚本默认数据根为 `F:\codex-agnes\AI-trade-data`；可用AI_TRADE_DATA_ROOT或-DataRoot显式指定。继承的AI_TRADE_WORKBENCH_ROOT/QUANT_DB_PATH必须分别等于该根/sqlite和该根/sqlite/workbench.sqlite3，否则停止，建议使用新PowerShell窗口。该选择不依赖worktree或cwd，不自动扫描数据库，也不修改系统/用户环境。

启动时终端会输出工作区、分支、提交 SHA、Python 路径和数据库路径，方便记录实际运行版本。

## 5. 故障处理

- **提示分支不是 main**：停止；不要在脚本中自动切换。确认 PR 已合并，再更新干净的本地 `main`。
- **提示工作区不干净**：运行 `git status --short` 检查。先备份或提交自己的修改，不能让脚本自动清理。
- **找不到 Python**：在 `AI-trade-dev` 工作区按项目依赖说明建立/修复 `.venv`；不要更换为其他目录的解释器。
- **正式数据库不存在**：停止并核实正式路径；不要创建替代库。
- **Schema、checksum、DDL 或完整性检查失败**：保留错误信息，交由独立任务处理；不要删除数据库、备份或 SQLite 侧车文件后重试。
- **端口被占用**：使用另一个端口，不要终止不明进程。
- **页面没有行情**：正式数据库初始化报告显示业务表为空。页面可打开不代表真实行情已采集；不能用 Demo 行情填充显示。
- **M3 数据不足**：七张基础表并不包含所有指数、市场宽度、情绪和 CFFEX 研究输入。空缺应如实显示，不能将结构验收当作 M3 数据闭环验收。

## 6. 重要边界

- 该脚本只启动本地只读工作台，不采集行情、不迁移历史样本、不写入数据库、不部署 AWS。
- 不提交 `workbench.sqlite3`、备份、运行日志或原始行情。
- PR #47 的既有离线测试和数据库初始化证据不等于本次脚本修订已在你的 PC 上执行验收。
- 自动浏览器验收曾被安全策略阻断，不得描述为自动 UI 验收通过。

数据库初始化及架构详情见 [LOCAL_WORKBENCH.md](LOCAL_WORKBENCH.md) 和 [M0_PRODUCTION_DB_REPORT.md](M0_PRODUCTION_DB_REPORT.md)。

# Windows 正式研究工作台

## 固定日常工作区

- 代码工作区：F:\codex-agnes\AI-trade-dev
- 日常分支：main
- 日常 Python：F:\codex-agnes\AI-trade-dev\.venv\Scripts\python.exe
- 新入口数据根：AI_TRADE_DATA_ROOT（未设置时，Windows启动脚本使用已审计的固定候选 F:\codex-agnes\AI-trade-data）
- 迁移后的正式数据库：F:\codex-agnes\AI-trade-data\sqlite\workbench.sqlite3
- 启动脚本：scripts/start_workbench.ps1

日常入口与旧临时 Demo 明确分开。研究库不连接交易账户或 EC2，不代表交易生产数据库。新数据根在Git仓库之外、不纳入版本管理；旧目录的忽略保护仍保留，备份和运行日志保存在源码树外。

**切换尚未执行。** 本PR仅交付配置/隔离迁移工具；现有8524仍指向旧正式库 `F:\codex-agnes\AI-trade\data\sqlite\workbench.sqlite3`。新入口必须在独立H审查、用户人工合并、停写/备份恢复/迁移确认后使用，见[分阶段记录与回滚](audits/TASK-M0-DATA-DIRECTORY-RELOCATION-001.md)。旧库保留为显式回滚来源，不自动回退、不重跑初始化。

启动脚本只允许从固定工作区的干净 main 分支运行，并且只使用该工作区的虚拟环境。若分支错误、工作区不干净、解释器不存在或正式数据库不存在，脚本直接停止；不会自动切换分支、清理修改、创建数据库或回退 Demo。

## 首次创建（历史记录，仅在目标尚不存在时使用）

正式数据库已按 TASK-M0-PRODUCTION-DB-001 创建。下面命令仅记录首次初始化流程，不是日常启动命令，也不要对已有数据库重跑。**仅当目标库、同名目录、WAL/SHM/journal、备份及恢复目标均不存在且另有明确授权时才允许；存在即拒绝，不自动迁移或覆盖。** 失败产物保留，不能直接重试覆盖。

~~~powershell
Set-Location 'F:\codex-agnes\AI-trade-dev'
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
& 'F:\codex-agnes\AI-trade-dev\.venv\Scripts\python.exe' -m ai_trade.storage.workbench_cli initialize-new `
  --root 'F:\codex-agnes\AI-trade\data\sqlite' `
  --backup 'F:\codex-agnes\AI-trade-local-state\m0-production-db-001\backups\workbench-initial.sqlite3' `
  --restore 'F:\codex-agnes\AI-trade-local-state\m0-production-db-001\restore-check\workbench.sqlite3' `
  --report 'F:\codex-agnes\AI-trade-local-state\m0-production-db-001\initialization.json'
~~~

该命令两次明确调用 Database.initialize() 验证幂等；不会填充行情或主数据。使用 SQLite Backup API 分别创建新备份、隔离恢复文件；对照 DDL/索引/触发器、七表计数、迁移 checksum、quick_check、foreign_key_check。空库演练只能验证结构恢复；非空版本/时间内容恢复另有隔离合成测试。

## 日常启动与诊断

在 PowerShell 中：

~~~powershell
Set-Location 'F:\codex-agnes\AI-trade-dev'
.\scripts\start_workbench.ps1
~~~

默认绑定 127.0.0.1:8524。脚本固定核验工作区路径、main 分支和干净状态，使用 AI-trade-dev\.venv，设置正式 ROOT/QUANT_DB_PATH、local、DELETE、STRICT_WORKBENCH=1、READ_ONLY=1，并去除该进程的 Demo 根。启动前输出实际 Git SHA、Python/数据库路径，检查实际 SQLite 连接、Schema/checksum、DDL 和完整性；失败即退出，不启动页面、不回退临时库。

新入口以 `AI_TRADE_DATA_ROOT` 为唯一数据根，将WORKBENCH_ROOT派生为其sqlite子目录、QUANT_DB_PATH派生为同一workbench.sqlite3；如果已继承的别名不一致则报错，不覆盖冲突配置。可在新的PowerShell进程中明确设置该变量，或传 `-DataRoot 'F:\codex-agnes\AI-trade-data'`。不写User/Machine环境或依赖cwd。缺根、缺sqlite子目录、缺DB、链接越界、仓库/Temp目录均停止，不自动创建。Python配置解析没有旧路径默认；Windows严格模式无DATA_ROOT也会停止。

浏览器地址：http://127.0.0.1:8524/?view=market。端口占用时可通过 -Port 指定另一个端口。

页面侧栏“正式研究库连接诊断”可检查实际连接。M1、M2、M3、M4 共用 get_components → workbench_config → Database → Repository；M3 非股票数据仍读取该根下的既有观察目录，不是已入七表。正式空库不会悄悄展示别的 Temp 观察或旧行情。

普通打开/刷新只校验，不初始化或迁移。严格连接使用 SQLite URI mode=ro（默认）或明确写入模式 mode=rw，后者也不能创建文件。ro 同时设置 query_only，仓储 transaction/initialize 明确拒绝；既有库不隐式切换 journal。用户误配路径、缺失库、v1/新版本/checksum/DDL 漂移或损坏均停止。

M0 正式写入必须复用本配置显式构造 Database(DatabaseConfig.from_env())，注入既有 DailyHistoryIngestor 与仓储；需要写入时由独立授权任务设置 AI_TRADE_READ_ONLY=0，先以 inspect_database 校验，不能调用 initialize。该环境与 M1–M4 读取路径必须相同；不把 QUANT_DB_PATH 存在误当作连接证明。健康检查的 health.sqlite3 是有意隔离的验证库，不是正式 M0 写入目标，其成功不表示正式入库。

本任务的日常启动脚本固定只读，不提供自动采集。需要采集/迁移时另立明确来源、许可、范围、预算及备份恢复的任务；不能靠改一个环境变量冒充获得来源或交易授权。

旧 demo_app.py 未使用正式配置直接启动时保留原有 Demo 教学/测试行为；**正式日常入口必须使用上述严格脚本**。它不是启动失败后的回退路径。外部进程若完全绕开正式入口及配置，仍可能读自己的隔离库，不能声称已全局改写所有历史脚本或操作系统配置。

## 旧数据及升级

[任务报告](M0_PRODUCTION_DB_REPORT.md) 和本机 legacy-preview.json 给出旧样本清单/差异。原文件不动，1217样本许可/历史可得性和迁移策略待独立审查，不执行入库。后续 M3 结构见 [M3_STORAGE_GAPS](M3_STORAGE_GAPS.md)；新增有序迁移不得改 v1/v2 定义/checksum。正式库不是以空数据通过 M0–M3 验收，独立 H/真实来源/历史身份/日历/样本外门禁继续保留。

# TASK-002：SQLite 数据基础设施实施记录

## 前置检查

状态：**前置问题已解决，已完成最小数据层实现；138 项离线测试通过。** 本文记录 TASK-002 的实现边界与使用方法；README 已同步当前状态、目录及运行入口。

- 工作目录：`F:\codex-agnes\AI-trade`。
- 检查时分支：`docs/p0-architecture-contracts`，提交 `fda15d3`（`docs: add V1.3 project README and development guide`）。
- 实施分支：`feature/task-002-sqlite-foundation`，从最新 `origin/main` 的 `125fd7e` 创建。
- 检查前工作区干净；仓库只有 README 和七份架构文档，没有源代码、测试、依赖清单或 Python 版本约束。
- 已审查 `ARCHITECTURE.md`、`DATA_CONTRACT.md`、`INTERFACE_CONTRACT.md`、`ACCEPTANCE_TESTS.md`、`P0_IMPLEMENTATION_PLAN.md`，并核对 README 与 `DECISIONS.md`。
- 最初没有远端；用户随后提供 `https://github.com/fengjnah/a-share-quant-v1/`。GitHub 核实默认分支名为 `main`，但仓库为空。已将原有 TASK-001 README 和七份文档按原内容建立为默认分支基线，拉取后再创建实施分支；没有在默认分支加入本次业务代码。
- 本机 Git HTTPS 推送认证失败，改用已连接的 GitHub 工具完成远端写入；不写入或导出认证凭据。
- 无既有 Python 版本约束；本次明确最低 Python 3.11，实际在全新虚拟环境的 Python 3.12.14 / SQLite 3.53.1 / pytest 8.4.2 上验证。运行时仅用标准库及 Windows 时区数据库 `tzdata`；pytest 是测试依赖。

## 阻塞问题及最小修订建议

### B-001：无法核实默认分支及其最新提交（已解决）

任务要求从默认分支最新提交创建 `feature/task-002-sqlite-foundation`，并创建指向默认分支的 PR。当前没有远端地址或默认分支证据，不能把现有文档分支假定为默认分支，也无法创建可核实的 PR。

用户提供仓库后，按上述空仓库初始化过程解决。本地旧文档分支保留；初始化远端只复制已有文档，内容与 `fda15d3` 相同，提交哈希因通过 GitHub 创建基线而不同。

### B-002：三元组唯一与历史版本（已解决）

用户已明确确认：**“同意逻辑对象唯一、历史版本追加”。** 下面的两层设计据此作为 TASK-002 的实施决定，数据契约不再存在此项阻塞。

任务要求同一证券、同一交易日期、同一调整口径不能产生重复行情记录。现有 `DATA_CONTRACT.md` 则将原始日线业务主键定义为 `instrument_id, trade_date, source_version`，并要求历史修订不覆盖旧版本、按 `as_of` 返回当时可见版本。如果只在存储所有版本的行情表上施加三元组唯一约束，将无法追加同一行情的历史修订。

已确认的最小澄清为：

> 同一证券实体、日期、调整口径仅有一个逻辑行情对象；来源和修订版本作为不可覆盖的子记录保留。同一来源版本重复提交须按明确的幂等/冲突规则处理，不允许自动覆盖或自动选择来源。

将采用两层结构：逻辑行情表对 `(instrument_id, trade_date, adjustment_method)` 唯一，版本表对 `(bar_id, source, source_version)` 唯一。标准化 `symbol` 与独立 `instrument_id` 同时保留，避免未来证券代码复用混同实体。查询显式限定来源、调整口径、`as_of` 和模式，不跨来源自动择优；修订关联及其时间顺序必须验证。

此决定保留 ADR-002 的历史可见性语义，不采用限制为单一物理记录的方案。

## 已实现范围与文件

沿用 README 建议的 `src/ai_trade/` 包名，将数据库管理、Schema 迁移放在 `storage/`，数据校验与行情仓储放在 `data_access/`；不另建平行的 `quant` 包。只新增本任务文件并更新 README，七份架构文档不变。README 写入权限曾受限，用户放开权限后已同步更新，没有擅自修改文件权限或覆盖其他工作。

| 新增文件 | 职责 |
| --- | --- |
| `pyproject.toml` | Python 版本、打包、最少依赖、pytest 配置 |
| `.env.example` / `.gitignore` | 非敏感配置模板；排除环境、凭据、数据库和产物 |
| `src/ai_trade/__init__.py` 及两个子包的 `__init__.py` | 包入口 |
| `src/ai_trade/storage/db.py` | 文件配置、连接上下文、事务、初始化、迁移校验 |
| `src/ai_trade/storage/schema.py` | 不可变迁移定义、表、索引、外键与审计保护触发器 |
| `src/ai_trade/storage/__main__.py` | 数据库初始化/升级命令，不执行数据下载 |
| `src/ai_trade/data_access/models.py` | 领域对象、结果及明确的错误类型 |
| `src/ai_trade/data_access/validation.py` | 结构化字段校验与时间规范化 |
| `src/ai_trade/data_access/repository.py` | 最小日线端口、SQLite 批量写入及按时点读取 |
| `tests/conftest.py` | 合成数据、每例独立临时数据库、禁止网络连接 |
| `tests/unit/test_db.py` | 初始化、连接释放、迁移、配置和 SQL 约束 |
| `tests/unit/test_market_data_repository.py` | 批量事务、冲突、来源/复权隔离、修订及查询 |
| `tests/unit/test_data_validation.py` | 非法字段、时间、OHLC 和数值边界 |
| `docs/IMPLEMENTATION_TASK_002.md` | 本实施与验收记录 |

修改文件：`README.md`，同步已实现/待实现边界、实际目录和初始化/测试命令。

## 最小 Schema 与唯一性

| 表 | 字段及约束 |
| --- | --- |
| `schema_migrations` | `version` 主键、迁移名称、SHA-256 checksum、应用时间；当前版本 1 |
| `instruments` | `instrument_id` 主键、标准化 `symbol`；同代码的不同上市实体可用不同 ID，不按当前代码合并历史 |
| `ingestion_runs` | `run_id` 主键、实际批次登记时间 `recorded_at` |
| `daily_bars` | `bar_id` 主键、证券实体外键、交易日期、调整口径；唯一键 `(instrument_id, trade_date, adjustment_method)` |
| `daily_bar_versions` | `version_id` 主键、逻辑行情外键、来源/来源版本、OHLC、量额、三个时间字段、因子版本、质量状态、前版本、运行批次外键；唯一键 `(bar_id, source, source_version)` |

版本的父键是同一逻辑对象、同一来源的 `supersedes_version`，通过复合外键引用；每个来源只有一个根版本，每个父版本最多一个后继，不允许分叉或跨来源/调整口径修订。后继的两个可见时间都不能倒退，且两者较晚者必须严格推进，避免时点查询出现同刻歧义。

按证券/日期/口径、来源与可见时间、交易日期、运行批次、代码建立索引。所有核心数据必填字段有 `NOT NULL`；OHLC、有限数值、非负量额、日期、调整口径和版本关系具有数据库约束。审计业务表禁止 UPDATE/DELETE；启用递归触发器，避免 `INSERT OR REPLACE` 绕过删除保护。迁移账本管理 Schema 历史，不作为业务更新入口。

完整证券主数据历史、改名/ST/退市、日历和公司行为仍待后续任务建设；`instruments` 仅是稳定实体标识映射，不能宣称已经实现 `SecurityMaster`。调用方必须提供可信的实体 ID。

## 实施假设与字段规则

这些补充仅细化本任务存储行为，不改变既有 ADR，也不确认数据源许可或策略规则：

- `symbol` 必须已规范化为六位 ASCII 数字加 `.SH`、`.SZ` 或 `.BJ`；不自动补后缀、不猜交易所。仅校验格式，不能证明证券实际上市、属于股票或该日可交易。
- 价格与成交金额单位为人民币元；成交量为整数股，范围 `0..2^63-1`。适配器未来必须先转换手/万元等外部单位。OHLC 必须有限且大于 0，满足 `low <= open/close <= high`；金额有限且非负，拒绝布尔值、数值字符串、NaN、Infinity、缺失值与超范围整数。不因看似合理而修正价格；量额为零可以保留，不据此推断停牌。
- `trade_date` 只接受真实日历日期 `YYYY-MM-DD`。三个时间必须显式传入带时区的 ISO 8601，统一存为固定微秒精度 UTC 字符串；用 `Asia/Shanghai` 解释行情所属交易日期。事件的上海日期必须与 `trade_date` 一致，可得与入库时间不得早于完整日线事件时间。
- `event_time` 是所属会话收盘事件；`available_at` 是该来源完整版本实际可用的时间；`ingested_at` 是系统成功获得并校验该事实的时间。调用方必须保留时间依据，数据库不能验证外部证据真伪，不会用当前时间或报告期补造历史可得时间；`recorded_at` 单独记录此次写入登记时间。没有历史入库证据时不得声称新下载的数据在过去已入库。
- 尚无交易日历，因此只校验事件所属市场日期，不认证节假日、特殊收盘时刻、停牌或盘中数据完整性；这些能力不能以本任务测试通过为由视为已具备。
- `adjustment_method` 只能为 `none`（不复权）、`qfq`（前复权）、`hfq`（后复权）。前/后复权必须提供非空 `factor_version`，不复权必须为空；本任务只保存已计算值与口径，不计算复权，不证明因子来源正确。
- `source` 约定为 `provider:endpoint:adapter_version`，不接受只有 `AKShare` 的名称。`source_version` 由来源适配器标识，作为不可重复的版本 ID，不靠字符串大小判定先后。更正必须显式指定前版本，禁止自动择优。
- 质量状态为 `accepted` 或 `quarantined`；结构非法数据两者均拒绝。隔离状态只用于结构合格但尚待质量确认的记录，不能靠标记绕过校验。

## 写入、读取与错误策略

`write_many(bars, run_id=...)` 使用单一 `BEGIN IMMEDIATE` 事务。逐项校验后写入，全部成功才提交；校验失败、唯一键/外键/修订冲突、输入迭代器异常或中断都回滚，包括此前新增的证券映射、逻辑对象、版本和批次。每次使用新连接，结束即关闭，不共享全局连接。

重复 `run_id` 或重复来源版本（即使价格完全相同）均显式抛 `DuplicateRecordError`；不使用覆盖、更新或静默跳过。逻辑对象可以被多个版本引用，仅此身份创建使用精确唯一键的冲突复用，不会吞掉版本冲突。本任务没有重复采集的成功去重和失败运行日志服务，因此不能宣称完整 AT-012 已通过。

非法字段抛 `ValidationError`，携带 `issues` 和批内记录索引；实体或版本矛盾抛 `IntegrityError`。无当时可见记录、或严格模式下最新可见版本被隔离时抛 `DataUnavailableError`，不回填零、不返回未来版本、不偷偷恢复较旧有效值。数据库锁、文件权限等运行故障仍保留底层明确异常，不伪装成功。

`get_bar(...)` 必须指定 `instrument_id`、`trade_date`、`source`、`adjustment_method`、`as_of` 和 `mode`。三个模式都同时执行 `available_at <= as_of` 与 `ingested_at <= as_of`，再沿无分叉版本顺序选最新可见版本。`strict_backtest` / `paper_trade` 仅允许最新版本为 accepted；research 可返回隔离记录但明确告警，也不放宽未来时间。

返回领域对象及 `as_of`、模式、定义版本、告警、运行/记录血缘和 `data_snapshot_id`。此 ID 以 `observation:sha256:` 开头，**只是所选不可变单条记录的内容摘要，不是完整数据库快照或可按 ID 重开的实验快照**；命名快照、范围/横截面查询和多数据集统一 DataAccess 未实现。

## 连接、配置与迁移操作

- `DatabaseConfig` 显式区分文件路径与 `local` / `test` / `production` 标签。production/test 从环境配置创建时必须提供路径，不静默回退本地库；标签本身不是 OS 权限隔离，实际文件权限仍由运行者管理。
- 默认启用 `foreign_keys=ON`、`recursive_triggers=ON`、5 秒 busy timeout、WAL 和 `synchronous=FULL`。可显式配置 DELETE 日志模式；本次只验证本机临时文件系统，未认证网络共享盘的 WAL 兼容性。
- `Database.connection()` 负责关闭连接，不提供批次提交语义；数据写入应使用 `transaction()`，不要在裸连接里组织多步写入。
- 初始化创建所需父目录，迁移与账本写入处于同一事务，逐条执行 SQL，避免 `executescript` 隐式提交。重复执行保持数据不变；拒绝历史版本缺口、checksum 漂移、应用不认识的未来版本和无版本的非空旧库。
- 新版本只能追加 `Migration`；已发布迁移不可修改。尚未提供降级命令。生产升级前须独立备份与审阅新迁移，本任务没有运行生产迁移。

新环境安装和运行（项目根目录，PowerShell；先确保 `python` 对应 Python 3.11+ 的真实解释器）：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
$env:QUANT_DB_ENV = "local"
$env:QUANT_DB_PATH = "./data/sqlite/local.sqlite3"
$env:QUANT_DB_JOURNAL = "WAL"
.\.venv\Scripts\python.exe -m ai_trade.storage
.\.venv\Scripts\python.exe -m ai_trade.storage
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pip check
```

Linux/macOS 使用 `.venv/bin/python` 代替 Windows 路径，通过 `export QUANT_DB_ENV=local` 等设置同名变量。本次实际验证平台为 Windows，未声称已在其他平台执行。

`.env.example` 是非敏感模板，**不自动加载**；不会引入 dotenv 依赖。安装依赖可能需要网络；安装后核心单元测试完全离线。测试使用 pytest `tmp_path`，每例新库，不使用环境变量中的本地/生产数据库；命令行测试也显式指向临时路径。不要把真实数据、数据库、凭据、虚拟环境提交 Git。

最小接口示例（纯合成事实，固定时间仅供演示，不是历史行情证据）：

```python
from pathlib import Path
from ai_trade.storage.db import Database, DatabaseConfig
from ai_trade.data_access.models import DailyBar
from ai_trade.data_access.repository import SQLiteMarketDataRepository

db = Database(DatabaseConfig(Path("data/sqlite/example.sqlite3"), "local"))
db.initialize()
repo = SQLiteMarketDataRepository(db)
bar = DailyBar(
    instrument_id="listing:synthetic:1", symbol="600000.SH", trade_date="2026-10-16",
    open=10, high=12, low=9, close=11, volume=1000, amount=11000,
    source="synthetic:daily:v1", source_version="observation-1",
    event_time="2026-10-16T15:00:00+08:00",
    available_at="2026-10-16T15:30:00+08:00",
    ingested_at="2026-10-16T15:31:00+08:00", adjustment_method="none",
)
repo.write_many([bar], run_id="example-1")
result = repo.get_bar(
    instrument_id=bar.instrument_id, trade_date=bar.trade_date, source=bar.source,
    adjustment_method="none", as_of="2026-10-16T16:00:00+08:00", mode="strict_backtest",
)
print(result.bar.close, result.lineage_refs)
```

示例数据第二次写入会按设计报重复错误；初始化可重复不代表写入接口会忽略重复。真实采集器尚未实现，也不应复制示例时间到真实记录。

## 测试与验收结果

实际执行 `python -m pytest -q`：**138 passed in 3.16s**；`python -m pip check`：**No broken requirements found**。测试运行时禁止 socket 网络连接；没有 AKShare 下载、真实交易接口调用或个人数据库依赖。

| TASK-002 验收项 | 对应实际验证 |
| --- | --- |
| 1 新环境初始化 | 干净虚拟环境安装；首次初始化；项目目录外运行 CLI |
| 2 重复初始化安全 | 重复初始化保留已有行情和账本；CLI 连续运行两次 |
| 3 不产生重复逻辑行情 | 数据库三元组唯一键；重复来源版本、批内重复均拒绝 |
| 4 拒绝非法数据 | 字段参数化用例与绕过仓储的 SQL 约束测试 |
| 5 批次完整性 | 后续校验/冲突失败、输入流异常、事务中断后无残留 |
| 6 时间语义 | 缺失/无时区/错日期拒绝；入库延迟边界；修订前后 as_of 可见性 |
| 7 自动化测试 | 138 项全部通过；迁移新增、失败 DDL 回滚、重复、漂移、未来版本及资源释放 |
| 8 离线隔离 | 每例临时文件，禁网络；来源与三种复权显式区分 |
| 9 范围控制 | 只有数据基础设施、配置、测试与本文；无采集、策略或 AWS 实现 |

138 项包含参数化展开后的数量，不是 138 个架构验收编号。日线延迟测试覆盖 AT-011 的对应基础行为；财务数据、真实采集幂等、策略执行、周线、成本、日报等尚未实现，**不宣称完整 AT-001 至 AT-022 或 P0 通过**。

## 未实现与保留限制

没有行情下载、完整主数据/日历、原始载荷归档、完整数据快照、策略、回测引擎、选股、交易信号、自动任务、云端计算或 AWS 部署；未引入付费服务、API Key、账号密码或交易连接。IEEE 浮点用于行情研究存储，不是精确现金账本；未来成交/现金模块须独立决定数值精度。

无未解决的数据层验收失败。尚未认证网络盘或跨平台运行。PR、分支和最终提交摘要以本任务最终汇报及 GitHub 实际状态为准，不在测试之前预写提交或 PR 成功结论。

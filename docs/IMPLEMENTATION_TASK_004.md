# TASK-004：证券主数据与交易日历基础

检查日期：2026-10-17（Asia/Shanghai）。本任务完成模型、Schema v2、事务存储、业务有效日期与 as_of 查询及离线测试；**未导入真实主数据/日历，未验收任何完整历史覆盖**。此前 TASK-003C 的两日日线采集成功不作为本任务数据源验收依据。

## Git 前置检查

任务开始时 GitHub 与本地提交逐项核对，三个 PR 当时均 open、未合并：

| 对象 | base | head | 文件差异 |
| --- | --- | --- | --- |
| main | — | 125fd7e4152b5c41ef361e39731301a81b0e2d2f | 仍为 TASK-001 文档基线 |
| PR #1 | main@125fd7e | feature/task-002-sqlite-foundation@4b73f8a4b23ec3a474a51d2850f31ba2f4678155 | 18 文件：SQLite、领域校验/仓储、配置、测试及文档 |
| PR #2 | TASK-002@4b73f8a | feature/task-003-akshare-adapter@fc692e7ed0c1aeffa7c3db0eb5a8b0ac9be9ca8f | 14 文件：采集、证据、离线/手工测试与文档 |
| PR #3 | TASK-003@fc692e7 | codex/task-003c-tls-diagnostics@80b5a8ec4c509e1e482daadfacae14c610911f8a | 5 文件：TLS 工具、测试、README 与验收记录 |

已读取 GitHub 全部 changed filenames，对照本地三段 git diff --stat 和实际代码；merge-base --is-ancestor 三段均成功。已审查 ARCHITECTURE、DATA_CONTRACT、INTERFACE_CONTRACT、DECISIONS、ACCEPTANCE_TESTS、P0_IMPLEMENTATION_PLAN 以及现有 Schema、连接/事务、领域模型、校验和测试。

开始时 main 没有数据基础设施，先从 #3 的可运行链头 80b5a8e 创建 `codex/task-004-master-calendar`；该链基线测试为 222 passed, 1 skipped in 6.90s。**提交前再次检查发现远端在任务期间发生变化，故停止原发布流程并重新核对：**

| 对象 | 提交前确认状态 |
| --- | --- |
| main / PR #1 | #1 已 squash 合并为 cd1b2b1412e4dbe345e4eac09330b94977211372，父提交为 125fd7e |
| PR #2 | closed、未合并，head 仍 fc692e7，base 已为 main；GitHub 合并基点差异显示 29 文件 |
| PR #3 | open、未合并，head 仍 80b5a8e，base 仍为 TASK-003 分支 |

实际 fetch 最新 main 后，确认 cd1b2b1 与原 4b73f8a 的文件树完全相同（tree=7a4bb379ae6c6f7513602f129d8f31d43f8e0ba6），但旧 4b73f8a 并非 squash 后 main 的祖先。TASK-004 只依赖该 SQLite 基础设施，因此保留 Git 检查点，将本任务重放到**最新 main@cd1b2b1**；只有 README 发生衔接冲突，按 main 当前内容重写本任务状态。没有改动 main，也没有复制旧 SQLite 或带入未合并的采集代码。

上一轮准备直接以 cd1b2b1 为基线创建指向 **main** 的 PR，但尚未提交/创建就中断。该基线曾实际通过 243 项（原数据层 138 + 本任务 105）；旧链上的 326 项属于不同范围。这些是历史结果，不作为本轮最终结果。本任务没有关闭、合并或修改其他 PR。

### 2026-10-17 续执行现场与最终基线

恢复时原工作区为 `F:\codex-agnes\AI-trade`，分支 `codex/task-004-master-calendar`，HEAD=cd1b2b1；16 个 TASK-004 文件已有暂存/未暂存修改，未创建 TASK-004 PR。逐项读取实际模型、Schema、仓储、校验、测试和文档后继续，没有从头重写。原 Git 检查点及全部工作区修改保留；恢复时 `docs/REFERENCE_PROJECT_REVIEW.md` 不存在，本任务未恢复、删除或纳入该文件。

重新读取 GitHub PR/分支并 fetch 后，最新 main 为 **d09a259ec34fec8e587baa54b63706ba96c3b9af**：#1 已合并；#2/#3 关闭且未合并，由已合并的 #5/#6 替代；#7 演示、#8 工程基线、#9 讨论归档也已合并。#1/#2/#3 的原 head SHA 和依赖见上表，恢复时均未改变；#2 base 为 main@cd1b2b1，#3 base 仍为 TASK-003。没有假定原 PR 自动合并。

`git diff cd1b2b1 d09a259 -- src/ai_trade/storage src/ai_trade/data_access docs/DATA_CONTRACT.md docs/INTERFACE_CONTRACT.md tests/unit/test_db.py` 为空，证明依赖的基础设施/契约没有变动。最新 main 额外包含已合并采集/TLS/演示及文档/CI，无接口冲突或基础设施阻断。

为不覆盖原工作区，从 d09a259 创建独立工作树和分支 **codex/task-004-master-calendar-resumed**，对已有 TASK-004 差异先 `git apply --check` 再应用；原 16 文件内容/暂存状态以本机哈希快照核对。只将 README 衔接最新 main，并补充 PROJECT_STATUS；业务模块没有重复开发，也没有修改已有日线采集、演示或 SQLite 连接模块。新 PR 直接指向 main。

| 对照项 | 恢复时状态与续执行 |
| --- | --- |
| 主数据模型/存储、身份约束 | 已有实现；复核后保留 |
| 上市/退市、名称有效期、版本链 | 已有实现；以原测试验证边界和合法修订 |
| as_of、未来信息隔离 | 已有双截止查询；复核 SQL 与真实临时库断言 |
| 日历开市/休市/缺失/错误 | 已有接口；复核有界区间和最近已知日语义 |
| 迁移、事务、约束及回滚 | 已有 v2 及测试；复用 v1，校验和不变 |
| 隔离与离线测试 | 已有 105 项新增用例；在最新 main 重新执行相关及完整套件 |
| 来源、README、实施报告 | 来源仅文档/源码审查；续执行修正过时分支与状态描述 |
| 提交/PR | 恢复时未完成；续执行验收后提交独立 PR，不合并 |
| 阻断 | 当前没有代码/依赖阻断；真实来源许可与覆盖验证留给后续任务 |

## 实施决定与数据模型

### 稳定身份与完整已知时间线

`SecuritySnapshot` 包含 instrument_id、symbol、exchange、security_type、listing_date、delisting_date、已知名称有效期 periods、provenance 和结构质量状态。模型仅支持显式 A_SHARE；SH/SZ/BJ 格式和后缀一致性通过校验，不凭代码格式证明真实证券类型或上市身份。

复用不可变 instruments 锚点，ID 必须由调用方的实体登记过程提供，不能直接使用任何标准证券代码。不同上市实体可复用同一代码，但生命期在同时可见时不得冲突。同一 ID 改代码/跨所迁移不在本次范围，写入明确拒绝；不会自动生成新 ID 来掩盖该限制。

名称区间采用左闭右开 `[effective_from,effective_to)`，上市生命期同为 `[listing_date,delisting_date)`。退市日定义为首次不再上市的日期，null 表示未记录退市事实。未知名称历史保留缺口，不把当前名称倒填至上市日；有生命期但名称缺失抛 SecurityDataMissingError，明确在生命期外抛 SecurityNotActiveError。

每个实体版本原子保存一个完整的**已知**名称时间线（1–256 段），不承诺覆盖完整上市历史。用 JSON 存于不可变单行，SQLite JSON 约束/触发器验证字段、日期、生命期和区间互斥，避免新增子记录改变已提交旧版本。新证据须追加完整版本、supersedes_version、revision_reason，不能 UPDATE 关闭旧区间。

来源不并列产生多条冲突根链；每个实体/日历日只有一条确认链。不同来源的修订必须显式关联前驱与依据，系统不自动择优。版本唯一、单根、单后继和前驱外键禁止重复/分叉。

代码复用约束同时检查业务生命期与系统可见区间，包含历史上尚未被修订替代的版本。例如：A 的“尚无退市记录”版本在系统时点 T2 仍有效，T3 才补记退市；即使最新版本已闭合，不能插入会在 T2 与 A 冲突的 B。只有在可见时间也一致时才能登记 B。批次中须先追加必要的闭合修订，再登记新实体，任何一步冲突会整批回滚。

ST 等风险历史**未实现**；SecurityAtDate.risk_status 始终 None 并告警，即使名称包含 ST 也不推断正常/风险状态。本任务不认证停牌、可买卖状态或证券别名。

### 日历事实与缺失

`CalendarDay` 包含 exchange、session_date、is_trading_day、provenance、quality_status、error_reason。accepted 要求显式 bool；source_error 必须以 None 表示未知并附原因，不能存为 false。

- get_day：已知 true/false 分别表示开市/休市；无可见记录抛 CalendarDataMissingError；可见源错误抛 CalendarSourceError。
- trading_days：区间两端包含，最多 36600 日；research 返回已知开市对象，并披露 missing_dates、source_error_dates、complete 和 warnings。严格/纸面模式拒绝任何不完整或错误区间。
- previous_known_trading_day：必须传 search_start 和不包含的 before；只搜索有界区间。research 有缺口时保留不完整标记，不把“最近已知”伪装成“实际紧邻上一日”。完全无可用日时区分源错误、缺失和已知区间全休市。

不使用 weekday 判断开市，不用缺失补休市，不在交易所间复制日历。测试中的周日开市是明确标记的合成场景，用来检测工作日推断错误，不代表真实市场安排。开收盘时刻、临时半日市和分钟会话尚未实现。

### 时间与证据

Provenance 强制 source、record_version、event_time、available_at、observed_at、ingested_at、evidence_kind、evidence_ref。synthetic 与 source_observation 必须显式选择；合成记录在所有模式读取时保留告警。source_observation 是调用方声明，不是系统自动验收徽章。

event_time 是本参考版本描述的事实/公告事件时间；已公布的未来日历使用版本发布事件，与未来 session_date 分开。缺乏事件时间依据时不能伪造历史发布时间。event <= available、event <= observed <= ingested，全部标准化为 UTC 固定微秒精度。没有时间字段默认值。

三种模式均同时过滤 available_at 和 ingested_at；修订 available/observed/ingested 不倒退，二者较晚的可见时间严格推进。未来才入库/可用的版本不回填过去。先选可见版本，再查询业务有效日期；缺口不回退旧版本补齐。晚入库的历史事实也不能直接用于其历史时点的严格查询。

ReferenceResult 包含领域值、as_of、mode、观测摘要、定义版本、告警及运行/版本血缘。摘要包含查询范围和所用血缘；不是完整数据库或可按 ID 重开的实验快照。ST 历史、真实来源认证、历史时间证据真伪与完整快照均未实现。

## 存储、迁移与依赖

| 表 | 关键约束 |
| --- | --- |
| security_versions | 复合外键复用 instruments(id,symbol)；(instrument_id,record_version) 唯一；单根/单后继；生命期、JSON 有效段、代码复用时空冲突和不可变保护 |
| calendar_versions | (exchange,session_date,record_version) 唯一；单根/单后继；bool/源错误互斥、日期、可见时间和不可变保护 |

两表都引用现有 ingestion_runs，事务复用 Database.transaction。批次的登记、锚点、版本和校验均在同一事务中；坏行、重复、SQL 约束或输入生成器异常不残留半批次。run_id 与行情仓储共享唯一命名空间；没有跨两个仓储的一体事务 API。

Schema v2 通过现有迁移注册表追加。v1 校验和仍为 `c6d31829bdef4ad9c6f45279c7696cfe94ac6acb9ff016c59320298b8e8dc0bd`，发布过的 v1 语句不变；测试包含从 v1 原行情数据升级、v2 失败回滚、重复迁移和完整性检查。旧测试版本期望更新为当前注册表长度，扩展迁移使用下一个版本号，未取消原检查。

没有新增第三方依赖或配置文件。沿用 Python >=3.11 和 .env.example；SQLite 需具备 JSON 函数与窗口函数，v2 首条语句先检查这两项能力，本轮 Windows SQLite 3.53.1 已验证。不支持时迁移失败回滚，不能宣称初始化成功。其他 SQLite 构建/操作系统的兼容性未认证。

## 候选来源审查：仅文档/源码，不是实测验收

审查官方文档和已安装 AKShare 1.19.1 的对应实现，没有发起这些数据集的 API 请求，没有复制解析源码或全市场下载。

| 候选 | 检查到的能力 | 不足与更新边界 |
| --- | --- | --- |
| stock_info_a_code_name | 聚合沪深京列表，仅 code/name | 无历史 as_of、实体永久 ID、退市/ST 有效期；不能还原历史证券池 |
| stock_info_sh_name_code / stock_info_sz_name_code | 分类当前列表，包含代码、名称、上市日期等 | 不构成完整历史名称/退市状态；SDK 有进程级 lru_cache，未给出可靠发布时间或刷新 SLA |
| stock_info_bj_name_code | 北交所分页列表，含代码、简称、上市日期及报告日期等 | 报告日期不等于系统观察/可用时间；没有独立验收其历史覆盖 |
| tool_trade_date_hist_sina | 解码 trade_date 列，源码手工补入 1992-05-04 | 无交易所字段、明确休市行或版本发布时间；文档覆盖文字与示例终点不一致，不能声称覆盖 2026，更不能把缺失补为休市 |

证据：

- [官方股票列表文档](https://akshare.akfamily.xyz/data/stock/stock.html)：本轮核对上述四类列表的输入/字段。
- [stock_info.py 固定源码](https://github.com/akfamily/akshare/blob/fe10d1decb705e5f43cc8ca3339ca39e580fb8f4/akshare/stock/stock_info.py)：已实际检查函数起始行 20、122、185、440，包括缓存、来源域名、分页和聚合丢弃字段。
- [官方日历文档](https://akshare.akfamily.xyz/data/tool/tool.html)：覆盖文字终点 2024-12-31，示例到 2025-12-31，未提供统一更新保障。
- [日历固定源码](https://github.com/akfamily/akshare/blob/fe10d1decb705e5f43cc8ca3339ca39e580fb8f4/akshare/tool/trade_date_hist.py#L19)：单列开市日期、手工补日、无发布/修订证据字段。

已安装源码文件 SHA-256 保存在本机 verification-summary.json，便于复核实际阅读对象。软件 MIT 不赋予交易所或新浪数据再分发/商业使用权，具体数据条款仍待确认。本任务没有新增真实来源适配器、下载数据、历史 ST 规则或主数据自动登记流程。

## 接口与安全复现

公共端口位于 security_master/repository.py、trading_calendar/repository.py；共享领域对象位于 reference_data/models.py。业务调用者不接触 SQLite 行或供应商列名。详细签名及边界已补充至 DATA_CONTRACT、INTERFACE_CONTRACT。

完整离线检查（续执行工作树复用 `F:\codex-agnes\AI-trade\.venv\Scripts\python.exe`，Python 3.12.14；干净环境先 `python -m pip install -e ".[test]"`，无需安装 AKShare/demo 即可运行离线套件）：

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pytest -q tests/unit/test_reference_data.py tests/unit/test_db.py
.\.venv\Scripts\python.exe -m pip check
git diff --check
```

完全合成示例，仅用自动清理的临时库，不创建 local/production 数据库、不访问网络：

```python
from pathlib import Path
from tempfile import TemporaryDirectory
from ai_trade.storage.db import Database, DatabaseConfig
from ai_trade.reference_data.models import Provenance, SecurityPeriod, SecuritySnapshot, CalendarDay
from ai_trade.security_master.repository import SQLiteSecurityMaster
from ai_trade.trading_calendar.repository import SQLiteTradingCalendar

with TemporaryDirectory(prefix="task004-example-") as folder:
    db = Database(DatabaseConfig(Path(folder) / "fixture.sqlite3", "test"))
    assert db.initialize() == 2
    metadata = Provenance("synthetic:example:v1", "v1", "2026-10-10T00:00:00Z",
                          "2026-10-16T00:00:00Z", "2026-10-16T00:00:00Z",
                          "2026-10-16T00:01:00Z", "synthetic", "fixture:example")
    master, calendar = SQLiteSecurityMaster(db), SQLiteTradingCalendar(db)
    fixture = SecuritySnapshot("fixture:entity:one", "600000.SH", "SH", "A_SHARE",
                               "2026-01-01", None,
                               (SecurityPeriod("2026-01-01", None, "Synthetic only"),), metadata)
    master.write_many([fixture], run_id="fixture-master")
    calendar.write_many([CalendarDay("SH", "2026-10-16", True, metadata)], run_id="fixture-calendar")
    result = master.get(instrument_id=fixture.instrument_id, valid_on="2026-10-16",
                        as_of="2026-10-16T00:01:00Z", mode="research")
    assert result.value.risk_status is None
    assert any("synthetic" in warning for warning in result.warnings)
```

生产库未初始化，默认本地库仍不存在；本例的代码/日期/名称全是夹具事实，不能导入真实研究库。本任务不改变日线采集的实体分配或自动将 instruments 的锚点补成主数据。

## 文件变更

| 文件 | 变更内容 |
| --- | --- |
| src/ai_trade/reference_data/__init__.py、models.py、validation.py、repository_support.py | 共享领域对象、严格校验、原事务上的批量与结果辅助 |
| src/ai_trade/security_master/__init__.py、repository.py | 证券时间线写入、实体/代码按时点查询 |
| src/ai_trade/trading_calendar/__init__.py、repository.py | 日期级日历版本、范围与最近已知日查询 |
| src/ai_trade/storage/reference_schema.py | 新增 v2 SQL 约束、索引、版本与不可变触发器 |
| src/ai_trade/storage/schema.py | 追加 v2 注册，v1 不变 |
| tests/unit/test_reference_data.py | 合成记录与实际临时 SQLite 的 105 项参数化用例 |
| tests/unit/test_db.py | 既有迁移测试适配 Schema v2，保留失败/漂移/重复检查 |
| docs/DATA_CONTRACT.md、docs/INTERFACE_CONTRACT.md | 细化本任务已实现契约及限制 |
| README.md、docs/PROJECT_STATUS.md、docs/IMPLEMENTATION_TASK_004.md | 更新真实状态、最新基线、续执行记录、运行说明、来源与本报告 |

## 实际验收与未解决事项

本轮最新 main 基线实际完整离线结果：**327 passed, 1 skipped in 11.62s**（既有 222 + 本任务 105）；相关主数据/日历和迁移测试为 **139 passed in 5.32s**。跳过的是既有真实 AKShare 手工测试，原因是未显式传 `--run-akshare-integration`，默认网络阻断规则未改。本任务没有请求真实主数据、日历或行情。`pip check` 输出 No broken requirements found，新增网络阻断用例确认默认 socket 规则仍有效；合成临时库文档示例实际执行退出码 0。最终完整输出、相关测试、文档示例和环境/保护检查留在续执行工作树本机已忽略的 artifacts/task-004/，没有提交运行日志、数据库或原始数据。当前 Windows 实测 Python 3.12.14 / SQLite 3.53.1；Python 3.11 的 Linux CI 结果需另看 PR 检查，不能以本机结果替代。

新增测试覆盖迁移失败全回滚/旧行情保留、重复初始化、身份锚点、代码复用的两种时间、名称有效期/生命期边界、未来修订隔离、ST 未知、重复与分叉、换源显式修订、源错误阻断旧版本、开市/休市/缺失区别、区间和最近已知日、批次与生成器失败、数据库直接绕过校验时的外键/唯一/JSON/不可变约束及完整性。所有默认测试继承 socket 网络阻断。

| 状态 | 本任务结论 |
| --- | --- |
| 模型与存储实现 | 完成此处列明的最小子集；不是完整 SecurityMaster/TradingCalendar 产品能力 |
| 离线测试 | 通过，全部使用隔离临时 SQLite 和合成事实 |
| 真实数据来源验证 | 只完成候选文档/源码审查，接口与字段未做实测接入验收 |
| 历史覆盖与质量验收 | 未完成；没有真实历史主数据、ST 或全交易所日历可以宣称已验收 |

下一步优先：选择并授权可追溯来源，确定永久实体登记与代码变更政策；分别验收历史上市/退市/改名/日历覆盖及发布时间；建立缺口报告，再接入全市场行情采集。ST、停牌/涨跌停、交易会话、公司行为仍需独立任务。当前不开发市场宽度/选股/回测、不初始化生产库、不部署 AWS，不自动合并任何 PR。

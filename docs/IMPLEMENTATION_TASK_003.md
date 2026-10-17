# TASK-003：AKShare 历史日线采集适配器

## 前置检查与 Git 基线

检查日期：2026-10-17（Asia/Shanghai）。检查前分支 `feature/task-002-sqlite-foundation`，本地 HEAD 与远端分支/PR #1 的 head 均为 `4b73f8a4b23ec3a474a51d2850f31ba2f4678155`。远端为 `https://github.com/fengjnah/a-share-quant-v1.git`，GitHub 默认分支 `main` 的实际提交仍为 `125fd7e`，尚未包含 TASK-002。

已核查 GitHub 分支列表及 PR #1：TASK-002 PR 仍 open、未合并。因此从已确认的 TASK-002 提交创建 `feature/task-003-akshare-adapter`；TASK-003 PR 暂指向 `feature/task-002-sqlite-foundation`，只展示适配器增量。TASK-002 合并后需要按实际合并方式重新核实基线并调整 PR，不能假定 squash 后的提交祖先关系不变。本任务不合并任何 PR。

工作区原有未提交的 `docs/REFERENCE_PROJECT_REVIEW.md`，本次原样保留，不纳入 TASK-003 提交。检查了现有 README、数据/接口契约、TASK-002 实施说明、数据库管理/Schema、领域模型、校验、仓储及测试。基线测试本轮实际为 `138 passed in 2.57s`。没有改写 SQLite、Schema、数据模型、仓储或原有数据层测试。

用户指定 GPT-6 High；当前对话没有切换自身模型配置的工具，未声称已切换模型，也未据此创建其他聊天或子代理。

## 核实的唯一接口与证据

唯一调用：`akshare.stock_zh_a_hist`，实际模块 `akshare.stock_feature.stock_hist_em`。SDK 固定为 **AKShare 1.19.1**，不接受未经审查的其他版本；当前官方文档、源码版本声明与 PyPI 1.19.1 发布元数据均已核对。未安装 AKShare，未运行真实行情请求；这里的“核实”指文档、源码和发布元数据检查，真实接口连通性留给显式手工测试。

- [官方历史日线文档](https://akshare.akfamily.xyz/data/stock/stock.html#id20)：接口、周期、日期、复权参数和输出字段；当日完整收盘数据须收盘后获取。
- [固定提交的实现](https://github.com/akfamily/akshare/blob/fe10d1decb705e5f43cc8ca3339ca39e580fb8f4/akshare/stock_feature/stock_hist_em.py#L952)：供应商请求参数、空表返回及字段数值转换。
- [版本声明](https://github.com/akfamily/akshare/blob/fe10d1decb705e5f43cc8ca3339ca39e580fb8f4/akshare/_version.py)、[PyPI 1.19.1](https://pypi.org/pypi/akshare/1.19.1/json)：SDK 版本、Python >=3.11 和 MIT 元数据。
- [实际 LICENSE](https://github.com/akfamily/akshare/blob/fe10d1decb705e5f43cc8ca3339ca39e580fb8f4/LICENSE)、[README 数据用途声明](https://github.com/akfamily/akshare/blob/fe10d1decb705e5f43cc8ca3339ca39e580fb8f4/README.md#statement)、[依赖声明](https://github.com/akfamily/akshare/blob/fe10d1decb705e5f43cc8ca3339ca39e580fb8f4/pyproject.toml)。

AKShare 将东方财富 K 线端点解析为 DataFrame。本项目通过 SDK 调用，不复制上游解析实现、不直接请求另一行情接口、不探测实时接口。固定调用参数为：

| 项目输入 | SDK 参数 | 约束 |
| --- | --- | --- |
| `symbol` 如 `600000.SH` | `symbol="600000"` | 明确沪深后缀与 A 股代码前缀；不猜市场，不含 ETF/北交所 |
| 日线 | `period="daily"` | 不接受分钟、周、月或实时行情 |
| ISO 开始/结束日期 | `start_date/end_date="YYYYMMDD"` | 起止有序，结束日严格早于实际上海日期 |
| `adjustment_method="none"` | `adjust=""` | 必填，不给默认口径；qfq/hfq 明确拒绝 |
| 超时秒数 | `timeout=10.0`（可配置） | 必须有限且为正，不沿用 SDK 无超时默认 |

最小覆盖为当前已知沪深 A 股格式：SH 的 600/601/603/605/688/689，SZ 的 000/001/002/003/300/301 前缀。前缀检查仅限格式范围，不证明实际上市实体、历史有效期或当时证券类型；`instrument_id` 必须由调用方明确提供，完整证券主数据尚未实现。

虽然 SDK 文档声称覆盖沪深京，本适配器没有验证北交所端点映射，因此暂不接受 BJ。即使盘后也不采当日数据，避免把更新未完成的行情作为完整日线；这比 SDK 支持范围更保守。

## 字段映射与校验

供应商列名只出现在适配层与离线夹具中；上层使用 `DailyHistoryRequest`、`DailyBar` 和 `IngestionResult`，不直接读取中文列名。

| DataFrame 字段 | 领域字段 | 映射/限制 |
| --- | --- | --- |
| 日期 | trade_date | 真实 YYYY-MM-DD；允许 date 或无时区的零时 datetime；必须在请求范围内 |
| 股票代码 | symbol | 必须为与请求相同的六位字符串；后缀取显式请求，不把整数补零冒充正确代码 |
| 开盘 | open | 有限数值，复用既有正价格和 OHLC 校验 |
| 最高 | high | 同上 |
| 最低 | low | 同上 |
| 收盘 | close | 同上 |
| 成交量 | volume | 官方单位为手；以 Decimal 精确乘 100 转成整数股，拒绝负数、非整数股或 int64 溢出 |
| 成交额 | amount | 人民币元，有限且非负，不擅自换成万元 |
| 振幅、涨跌幅、涨跌额、换手率 | 不进入最小 DailyBar | 可以存在并保留在 SDK 快照；不用于评分或派生策略 |

八个必需列缺失/改名、未知列新增、重复列名或非 DataFrame 返回均为 schema_error。四个已知非必需列可缺省。SDK 的零行零列表是已核实的空结果形态；零行且含异常列结构仍判 schema_error。

记录不进行数值字符串自动转换、不填零、不裁剪 OHLC、不丢弃坏行。任意一行校验失败都不写入整批；乱序仅按日期稳定排序，不修改值。同日重复无论同值还是冲突值均拒绝，禁止选择“更合理”一条。

## 时间、版本与证据语义

1. `started_at`：本次 SDK 调用开始前的实际 UTC 时间。
2. `observed_at`：SDK 成功返回 DataFrame 后的实际 UTC 时间；不是交易日、公告时间或供应商首次发布时间。
3. `available_at=observed_at`：接口没有可靠的历史发布时间字段，因此仅声明“本次实际观察到该版本”的保守可用时间，不猜测历史最早可用时间。
4. `validated_at`：完成整批转换/校验后的实际时间；持久化领域记录的 `ingested_at` 使用该时间，不能按历史交易日倒填。
5. `event_time`：交易日的常规 15:00 Asia/Shanghai，按既有日线会话约定生成，并保留到 UTC；不是供应商提供的精确事件时间。本任务没有交易日历，不能认证特殊历史收盘时刻、休市、停牌或数据完整性。
6. `completed_at`：批次结束时间。沿用 SQLite 自身批次登记时间 `recorded_at`，不替换数据库实现。

因此，今天取得的历史行情不能在其历史日期的 strict_backtest 查询中可见。完整历史审计回测需要另有经过批准和可验证的历史时间证据政策；本任务不放宽原严格模式。

`source` 包含提供商、接口、适配器版本和实际 SDK 版本。`source_version` 是规范化单条日期、代码、OHLC、量额和口径的 SHA-256；不包含本次观察时间或 run_id，保证同一事实再次采集会碰到既有重复检测，而非偷偷追加成新历史。

每次 `run_id` 在显式指定的本地证据根目录下创建哈希命名子目录，禁止覆盖；即使 ID 包含路径分隔符，也不会用其构造外部路径。目录包含：

- `request.json`：请求、run_id、来源/SDK、真实调用参数、开始时间、可得时间与事件时间政策。
- `response.json`：校验前 SDK DataFrame 的列、dtype 和 split JSON 快照，带格式说明；结果保留其 SHA-256。**这是 SDK 解析后快照，不是 HTTP 原始字节**。NaN/NaT/None 等在 JSON 中可能合并为 null，且浮点序列化有精度限制，不能作为完整字节级原始载荷证明。
- `result.json`：状态、实际时间、返回/插入数量、错误、告警、领域结果和证据摘要。网络失败没有成功返回的 DataFrame，因而没有 response 文件；request/result 仍保留。

校验和用于发现内容意外变化，未提供签名或防恶意篡改保证。原始 HTTP 响应归档与持久化时钟可信性认证仍是后续能力。

## 状态、重复与失败边界

| 状态 | 含义 | 数据库行为 |
| --- | --- | --- |
| success | 返回记录整批转换、校验并提交 | 只表示返回批次成功，不表示请求区间无缺失 |
| empty_response | 零行 DataFrame，不能判明无交易/停牌/供应商问题 | 不调用写入接口，不算成功 |
| network_error | 可识别的超时/连接错误、非 429 HTTPError | 不写入，不自动重试 |
| rate_limited | 异常明确带 HTTP 429，可记录 Retry-After | 不写入，不自动重试；不把其他状态猜为限流 |
| response_error | SDK JSON/载荷解析或调用签名错误，缺少足够 HTTP/字段证据 | 不写入，不冒称已确定限流或字段变化 |
| schema_error | 返回类型/列结构与审查的 SDK schema 不符 | 不写入，保留可归档响应 |
| validation_error | 日期、代码、单位换算、数值、OHLC 或时间不合规 | 整批拒绝 |
| duplicate | 响应内同日重复或既有来源版本重复 | 明确报告，不覆盖、不按成功跳过 |
| conflict | 新载荷与同一逻辑对象已有根版本等完整性约束冲突 | 复用原仓储事务回滚，等待人工修订决策 |

非法请求、未支持口径或缺少 run_id 在联系 SDK 前抛明确 ValidationError；缺 SDK/版本不符在客户端构造时抛带修复说明的 RuntimeError。同一 run_id 再用时抛 DuplicateRecordError，不覆盖已保存证据。

**SDK 的 HTTP 可观测性限制：** 已检查的函数没有统一调用 raise_for_status，可能在内部解析时丢失 429/403 或其他 HTTP 信息。只有带明确 HTTPError.response.status_code 的情况可判为 rate_limited；若 429 最终表现成 HTML/坏 JSON，则为 response_error；若被 SDK 折成空表，则只能记 empty_response。固定测试验证已知错误分类，不证明所有真实限流都可识别。当前不全局 monkeypatch SDK/requests，也不以模糊字符串匹配猜限流。

**证据和数据库不是跨资源原子事务：** 请求/响应证据持久化失败时不进入写库；如果数据库已提交而 result.json 写入失败，抛 `EvidenceWriteError(database_committed=True)`，明确要求先检查数据库再恢复，不能声称已回滚。意外程序异常不伪装成成功或网络错误，可能留下只有请求/响应的中断批次。没有实现自动恢复、跨资源两阶段提交或原始载荷去重服务。

同值重新采集使用新 run_id：数据库明确报 duplicate，但两次证据目录都保留。不同价格的新版本不自动寻找 supersedes_version，返回 conflict；本任务没有授权自动确认供应商修订。不能据此宣布完整 AT-012 或整个 P0 已通过。

## 新增与修改文件

| 文件 | 职责 |
| --- | --- |
| `src/ai_trade/market_data/__init__.py` | 新包，避免默认导入 SDK |
| `src/ai_trade/market_data/models.py` | 请求/结果/状态、最小写入端口与错误 |
| `src/ai_trade/market_data/akshare_adapter.py` | 唯一客户端、参数限制、供应商映射 |
| `src/ai_trade/market_data/evidence.py` | 独占批次证据文件和响应摘要 |
| `src/ai_trade/market_data/ingestor.py` | 采集编排与已有仓储调用 |
| `tests/fixtures/akshare_daily.json` | 两条完全合成的固定响应，不是下载行情 |
| `tests/unit/test_akshare_ingestion.py` | 离线采集/映射/失败边界测试 |
| `tests/manual/test_akshare_daily_live.py` | 默认跳过的真实接口手工集成测试 |
| `tests/conftest.py` | 显式手工选项；仅被标记且显式启用的测试解除网络阻断 |
| `pyproject.toml` | 测试用 pandas/requests；AKShare 1.19.1 可选 extra 与 marker |
| `README.md` | 更新实际采集子集和运行说明 |
| `docs/IMPLEMENTATION_TASK_003.md` | 本文：证据、映射、使用、结果和风险 |

`storage/` 与 `data_access/` 无修改；无数据库迁移、选股、回测、财务、期货、实时接口或 AWS 代码。

## 安装与使用

Python >=3.11。已有虚拟环境可复用；新环境先 `python -m venv .venv`。SQLite 核心运行依赖仍保持原有标准库/tzdata；供应商依赖按需安装，不要求使用数据层的调用者安装 AKShare。

仅安装离线测试所需依赖，并运行默认测试：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m pytest -q
```

需要实际采集时，另行安装 SDK：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[test,akshare]"
```

本任务测试环境只安装了 test extra，没有安装 AKShare。数据依赖安装可能需要网络，但默认测试全部使用模拟响应；SDK 仅在显式构造真实客户端并 fetch 时延迟加载。

最小调用方式（以下会产生真实网络请求，只有确认来源使用权限并明确需要时才运行）：

```python
from pathlib import Path
from uuid import uuid4
from ai_trade.storage.db import Database, DatabaseConfig
from ai_trade.data_access.repository import SQLiteMarketDataRepository
from ai_trade.market_data.akshare_adapter import AkshareDailyClient
from ai_trade.market_data.evidence import EvidenceStore
from ai_trade.market_data.ingestor import DailyHistoryIngestor
from ai_trade.market_data.models import DailyHistoryRequest

db = Database(DatabaseConfig(Path("data/sqlite/local.sqlite3"), "local"))
db.initialize()
service = DailyHistoryIngestor(
    AkshareDailyClient(), SQLiteMarketDataRepository(db),
    EvidenceStore(Path("data/raw/akshare")),
)
# 此 ID 仅示意调用者管理的研究标识；正式使用应来自核实的证券实体映射。
request = DailyHistoryRequest("research:600000.SH:manual", "600000.SH", "2026-10-14", "2026-10-15", "none")
result = service.collect(request, run_id="manual-" + uuid4().hex)
print(result.status, result.inserted_rows, result.evidence_directory)
```

另提供真实接口手工测试，只使用 pytest 临时库和临时证据目录，不访问个人本地/生产数据库。必须设置全部输入并显式开启：

```powershell
$env:AKSHARE_TEST_INSTRUMENT_ID = "research:600000.SH:manual"
$env:AKSHARE_TEST_SYMBOL = "600000.SH"
$env:AKSHARE_TEST_START = "2026-10-14"
$env:AKSHARE_TEST_END = "2026-10-15"
.\.venv\Scripts\python.exe -m pytest tests/manual/test_akshare_daily_live.py --run-akshare-integration -q
```

默认 pytest 会跳过该测试，即使机器已经安装 AKShare；只设置环境变量不会解禁网络。显式开关也不会解除未标记单元测试的网络阻断。手工测试遇网络错误、空响应或源不可用会失败并报告实际状态，不会把不可用当作通过。

## 测试结果与未解决风险

本轮完整相关测试实际结果：**208 passed, 1 skipped in 5.16s**（原数据层 138 项 + 本任务 70 项离线测试；1 项真实接口测试按设计跳过）。另以 `--run-akshare-integration` 仅选择网络阻断单元测试执行，结果 **1 passed in 0.77s**，确认开关不会解除普通单元测试的网络限制。`pip check` 通过。本轮没有执行真实接口测试，也没有真实行情下载、数据库生产迁移、账户连接或部署。

新增测试覆盖字段/日期/代码映射、深圳前导零、手转股、时区与实际观察/入库时间、历史 as_of 拒读、稳定版本摘要、重复 run、重复响应、既有版本冲突、非法数值及后续坏行整批拒绝、空响应、字段增删/改名/重复、网络/明确 429/其他 HTTP/未知响应分类、证据失败前后数据库状态、提交后时钟异常、口径拒绝、SDK 缺失/版本不符和唯一 SDK 调用参数。

仍未解决或未验证：

1. 实际行情连通性、数据质量、缺失覆盖和服务限流；手工测试未运行，不能宣称真实源接入已验收通过。
2. SDK 未暴露的 HTTP 状态无法准确还原；空表既不能证明无交易，也不能排除供应商拒绝服务。
3. 常规 15:00 会话约定、实体 ID 与代码范围没有完整历史主数据/日历验证；不认证特殊历史场景或市场规则。
4. qfq/hfq 缺可核查因子版本，因此暂不支持；上游价格复权参数并不等于已取得 PIT 因子证据。
5. 只有 SDK 层 JSON 快照，无原始 HTTP 字节、首次发布时间、历史入库证明、签名或自动故障恢复。
6. 软件 MIT 许可不代表东方财富数据的批量抓取、商用、长期缓存或对外再分发许可。AKShare README 对数据用途另有声明，实际来源条款仍须确认；手工调用不引入自动绕过、换源或无限重试。
7. 可选 AKShare 依赖包含平台相关原生组件，本任务没有把所有传递/二进制依赖许可视为已完成审核，也没有安装这些组件。未复制其源码。
8. TASK-002 PR 未合并；TASK-003 当前为依赖分支上的增量 PR，合并顺序和后续基线调整需单独处理。

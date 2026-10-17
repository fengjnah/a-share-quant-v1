# 模块接口契约

## 共同约定

所有业务模块通过领域对象和端口交互，不直接调用第三方 SDK 或拼接 SQLite SQL。所有读取入口必须显式接收：`as_of`、市场/标的范围、`mode`（`research`、`strict_backtest` 或 `paper_trade`）和可选 `data_snapshot_id`。所有写入入口必须接收 `run_id`、来源元数据与校验结果。

每个结果对象至少携带 `as_of`、`data_snapshot_id`、`definitions_version`、`warnings` 和 `lineage_refs`。错误分为：`ValidationError`（输入或契约不合法）、`DataUnavailableError`（严格模式缺少可得数据）、`SourceTransientError`（可重试采集失败）、`SourceSchemaError`（源字段变化）、`IntegrityError`（版本/主键/时间矛盾）和 `ExecutionConstraintError`（订单不可成交）。错误不得被静默降级为零值、空信号或成功。

## 端口清单

| 端口 | 输入 | 输出 | 依赖 | 错误处理与测试标准 |
| --- | --- | --- | --- | --- |
| `MarketDataIngestor` | 数据源配置、标的、会话范围、`run_id` | 原始载荷引用、标准化记录、质量报告 | 源适配器、日历、证券主数据、归档 | 字段漂移中止批次；可重试网络失败；测试重复抓取幂等、缺失会话与价格边界 |
| `TradingCalendar` | 市场、日期/时点 | 会话状态、上一/下一会话、开收盘时点 | 日历存储 | 未知日期显式失败；测试节假日、临时休市、时区 |
| `SecurityMaster` | 标识符、`as_of` | 历史有效的证券身份、ST/上市/退市状态 | 主数据存储 | 歧义代码失败；测试改名、代码复用、ST 状态变更 |
| `DataAccess` | 数据集、键/范围、`as_of`、模式 | 经版本和可得性过滤的领域记录 | SQLite 实现；未来可替换实现 | 严格模式拒绝无可得时间数据；测试同一快照可复现 |
| `CorporateActionService` | 标的、日期范围、因子口径、`as_of` | 原始/调整价格映射和公司行为 | 数据访问、证券主数据 | 口径不匹配失败；测试除权前后收益连续性及版本选择 |
| `FeatureEngine` | 特征定义、标的/横截面、`as_of` | 带证据与可用时点的特征集 | 数据访问、日历、派生缓存 | 依赖不可得即失败；测试不读未来 bar、周线未完成拒绝 |
| `MarketRegimeService` | 市场范围、规则版本、`as_of` | 市场状态、恢复条件、解释项 | 特征、历史成分 | 缺失覆盖率告警/失败；测试等权权重与连续下跌窗口 |
| `GlobalRiskService` | 代理序列、规则版本、`as_of` | 风险状态、证据等级、缺失说明 | 数据访问、时区映射 | 数据过期拒绝或显式中性规则；测试海外时差与假日 |
| `SectorAnalysisService` | 分类体系、范围、`as_of` | 历史板块归属、强弱/广度特征 | 成分历史、特征 | 无历史映射不可严谨回测；测试成分变更不回填 |
| `StockSelector` | 股票池规则、评分版本、`as_of` | 候选排名、逐项分数、排除原因 | 特征、板块、主数据、风险门控 | 阈值定义缺失失败；测试 ST/市值/停牌排除和稳定排序 |
| `TimingService` | 候选、规则版本、`as_of` | 信号、有效期、最早执行会话 | 日/周特征、日历 | 本周未完成失败；测试周五后最早下周成交 |
| `RiskService` | 信号、组合状态、风控参数、`as_of` | 目标权重、止损/退出约束、拒绝理由 | 市场/全球风险、可交易性 | 参数冲突失败；测试集中度、止损、恢复门控 |
| `BacktestEngine` | 策略版本、期间、初始资金、成本模型、快照 | 订单/成交/持仓/净值/审计报告 | 所有上游服务、执行模拟器 | 缺失可得数据失败；测试 next-session 成交、停牌、涨跌停、费用和可复现性 |
| `DailyReportBuilder` | 已审核的输出快照、模板版本、发布日期 | 静态 HTML/JSON、manifest、校验和 | 选择/风险/回测读模型 | 输入非审计则明显标注；测试 schema、移动端 JSON 和无敏感数据 |
| `StaticPublisher` | 已校验目录、发布目标、版本 | 发布回执、文件哈希 | 传输适配器 | 只允许白名单静态文件；测试原子切换、回滚与不上传 SQLite |

## 策略与回测输入输出边界

策略只返回“意图”，至少包括 `instrument_id`、方向、信号时间、`earliest_execution_session`、失效时间、理由、所用证据和规则版本；它不得生成成交价格。执行模拟器根据会话、订单类型、可交易性与成本模型产生订单状态和成交记录。组合记账只以成交记录改变持仓与现金。

`BacktestEngine` 至少提供两种可比较的投资状态策略：`always_invested`（在允许交易范围内持续维持定义的目标暴露）与 `cash_capable`（允许由规则转为现金）。二者必须共享股票池、数据快照、成交时点、成本、滑点和再平衡规则；报告须分开列示空仓天数、实际暴露、换手、成本、最大回撤、收益及缺失数据处理，禁止只比较收益率。

## 存储实现契约

SQLite 实现负责事务、约束、索引、迁移和只读快照；上层不得依赖 SQLite 专有返回类型。推荐单写多读、采集批次短事务、WAL 模式（实施时验证网络盘兼容性）。未来 `ParquetDuckDBDataAccess` 必须通过同一契约，保持相同 `as_of` 可见性和版本选择，不能以“列式读取性能”为由跳过血缘或可得性过滤。

## TASK-004 已实现的最小端口

完整端口规划继续有效，下列只是日期级模型/存储/查询子集，不接入真实来源，不代表完整主数据、ST 历史、交易会话或可交易性服务。

| 实现 | 方法 | 语义 |
| --- | --- | --- |
| `SQLiteSecurityMaster` / `SecurityMaster` Protocol | `write_many(records, run_id=...)` | 事务写入不可变 SecuritySnapshot；重复、分叉、冲突明确失败，空批次拒绝 |
| 同上 | `get(instrument_id=..., valid_on=..., as_of=..., mode=...)` | 先选择系统时点可见的完整版本，再按业务日期取名称有效段；生命期外与有效段缺失用不同错误 |
| 同上 | `resolve(symbol=..., valid_on=..., as_of=..., mode=...)` | 按当时有效上市实体解析代码；不按当前代码合并历史，歧义显式失败 |
| `SQLiteTradingCalendar` / `TradingCalendar` Protocol | `write_many(records, run_id=...)` | 明确存储 CalendarDay 的开市、休市或源错误，不根据缺失合成休市 |
| 同上 | `get_day(exchange=..., session_date=..., as_of=..., mode=...)` | 返回带元数据的领域日历对象；value.is_trading_day 为判断结果，未知与错误抛不同异常 |
| 同上 | `trading_days(exchange=..., start=..., end=..., as_of=..., mode=...)` | 返回日期排序的已知开市对象；research 显式披露缺失/错误，严格模式拒绝不完整区间 |
| 同上 | `previous_known_trading_day(exchange=..., before=..., search_start=..., as_of=..., mode=...)` | 搜索有界且不含 before；缺失不被跨越后悄悄宣称“实际上一交易日” |

`ReferenceResult[T]` 统一包含 value、as_of、mode、data_snapshot_id、definitions_version、warnings、lineage_refs，以及日历查询的 missing_dates/source_error_dates/complete。ST/risk_status 始终未知并告警；尚未提供独立风险状态端口。合成数据告警在所有模式保留，测试通过不认证真实来源。

所有查询必须显式传 mode/as_of。观察可见性过滤和版本选择在一个 SELECT 内完成，范围查询不会逐日开启连接拼出混合快照。前一已知日的血缘/摘要覆盖完整搜索区间。所有写入复用已有 Database.transaction；run_id 与日线仓储共用 ingestion_runs 命名空间，不可跨独立批次复用。本任务不提供跨主数据/日历两个仓储的一体事务 API。

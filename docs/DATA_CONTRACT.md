# 数据契约与时间可得性规范

M3 补充候选诊断契约见 [M3_CORE_CONTRACT](M3_CORE_CONTRACT.md) 及 [JSON Schema](M3_DIAGNOSTIC_V1.schema.json)。该扩展不修改现有存储、时间或历史版本语义，未认证来源不因诊断可计算而获得研究/策略准入；独立 H 审查前不作为稳定下游依赖。

## 强制元数据

每一条可进入特征、信号、回测或日报的数据记录，均必须有以下字段。时间统一存储为带时区的 ISO 8601；A 股市场日界定使用 `Asia/Shanghai`。

| 字段 | 含义 | 不允许的替代 |
| --- | --- | --- |
| `source` | 具体来源、端点/文件标识及适配器版本 | 仅写“AKShare” |
| `event_time` | 事实发生或市场数据所属时点 | 用下载时间代替行情时间 |
| `available_at` | 系统按规则可合法使用该版本的最早时间 | 用报告期末、当前网页时间代替 |
| `ingested_at` | 本系统成功取得并校验的时间 | 用事件时间代替 |

建议同时保存 `source_record_id`、`source_published_at`、`payload_hash`、`schema_version`、`quality_status`、`supersedes_id` 与 `run_id`。`available_at` 的计算规则及其输入必须可追溯。若 `ingested_at` 晚于理论 `available_at`，严谨回测应取两者较晚者，除非有证据说明历史运行环境当时确实已获得该记录。

## 时间查询规则

严谨模式的查询谓词为：`event_time` 位于请求区间、`available_at <= as_of`、`ingested_at <= as_of`、记录未被更早可得版本替代，且 `quality_status = accepted`。请求方必须传入 `as_of` 和模式：

| 模式 | 用途 | 未带 `available_at` 的数据 |
| --- | --- | --- |
| `research` | 探索、数据质量调查 | 可返回，但结果必须标记非审计 |
| `strict_backtest` | 策略比较和审计回测 | 拒绝 |
| `paper_trade` | 纸面实盘流程 | 拒绝，并记录数据延迟 |

历史更正不可覆盖旧版本。数据访问接口必须在指定 `as_of` 返回当时可见版本，支持复现实验；“最新修订版”只能用于当前研究，不能倒灌入历史回测。

## 领域数据集

| 数据集 | 业务主键 | 时间与可得性规则 | 特殊要求 |
| --- | --- | --- | --- |
| `security_master` | `instrument_id, effective_from` | 上市、改名、ST、退市等均为有效期记录 | 代码复用时不得混同实体 |
| `trading_sessions` | `market, session_date` | 会话日历应有版本与来源 | 不用工作日替代 |
| `daily_bars_raw` | `instrument_id, trade_date, source_version` | `event_time` 为所属会话收盘；`available_at` 为供应商完整数据可用时点 | 保留原始 OHLCV |
| `daily_bar_status` | `instrument_id, trade_date` | 与行情同样版本化 | 停牌、涨跌停、异常、可卖/可买状态分开 |
| `corporate_actions` | `instrument_id, action_id, version` | 除权除息事件和公布/可用时间均保存 | 原始价与复权价并存 |
| `adjustment_factors` | `instrument_id, factor_date, factor_version` | 因子版本与计算来源可审计 | 禁止静默使用后复权重写历史 |
| `financial_disclosures` | `instrument_id, announcement_id, revision` | 报告期、公告发布时间、抓取时间分离；默认 `available_at >= published_at` | 修订公告创建新版本 |
| `index_memberships` | `index_id, instrument_id, effective_from` | 入选/剔除生效日、公告时间、可用时间均保留 | 查询历史时按历史成分 |
| `sector_memberships` | `taxonomy, sector_id, instrument_id, effective_from` | 概念/行业映射有版本和来源 | 不能用当前映射回填 |
| `market_cap` | `instrument_id, trade_date, definition` | 定义明确为总/流通市值，数据时点可得 | 100 亿元阈值采用可得值 |
| `global_risk_series` | `series_id, event_time, source_version` | 全球市场收盘时差与本地可得时点明确 | 节假日和缺失有规则 |
| `futures_rankings` | `exchange, contract, member, trade_date, rank_type` | 只保存公开字段及发布日期 | 不推导最终机构净持仓 |

## 行情、复权与可交易性

原始 OHLCV 是供应商事实；复权序列是派生数据，必须声明 `adjustment_method`（例如前复权、后复权或不复权）和因子版本。信号计算可选择一个固定口径，成交模拟必须使用与交易所实际规则一致的未复权价格、除权除息现金/股份处理和可成交限制。报告须同时披露信号价格口径与成交价格口径。

订单在会话 `S` 仅当证券当日上市、未退市、未停牌且方向符合涨跌停可交易规则时才可成交。无法成交的订单必须按配置取消、挂起或到期，绝不能以同日收盘价强行成交。最小交易单位、价格精度、佣金、税费、过户费和滑点均为带版本的成本参数。

## 公告、财务、成分与周线规则

1. `event_time`：财务报告期末或公告实际发布时间；`available_at`：公告公开且被本系统成功取得、通过校验的最晚时间。保守默认取 `max(source_published_at, ingested_at)`。
2. 没有可靠发布时间时，记录质量降级；严谨回测拒绝使用，或使用书面批准的保守滞后并在报告中提示。
3. 指数/行业/概念成分按 `as_of` 及有效期查询。未获得历史快照前，该因子不得作为严谨回测过滤条件。
4. `weekly_bar` 由已关闭日线聚合。周线 `available_at` 不早于该周最后一个交易日完整日线的可用时间；未结束周只能提供标记为 `partial` 的研究数据，严谨信号不可读。

## 机构与代理指标证据等级

| 等级 | 定义 | 可展示措辞 | 禁止措辞 |
| --- | --- | --- | --- |
| A：直接可验证 | 有公开原始字段、发布日期和可复查记录，且字段本身表示该事实 | “交易所公开会员多/空持仓排名” | 将会员直接等同最终机构 |
| B：公开代理 | 可复查数据计算出的市场代理，口径明确 | “前 20 会员净多代理”“北向/成交结构代理”（取决于来源可用性） | “机构净持仓” |
| C：不可验证 | 缺乏稳定公开字段或无法追溯主体 | “不可验证，未纳入模型” | 估计为真实机构净持仓 |

任何日报、评分或回测字段都应携带 `evidence_grade` 和 `definition`。A/B 等级也不构成投资建议。

## TASK-004：主数据与日历的最小落地契约

以下细化有效时间和版本语义，不放宽以上时间可得性要求；不代表真实来源和历史覆盖已验收。

### 证券身份与有效期

- `instrument_id` 由调用方的实体登记过程提供，禁止直接使用六位代码或带交易所的代码作为 ID。代码复用须创建不同上市实体的 ID，不能合并历史。
- 复用 TASK-002 的不可变 `instruments` 身份锚点。同一 ID 的改代码/跨交易所迁移本任务明确拒绝，不能自动另造 ID 伪装为已支持；后续需独立设计代码别名和迁移方案。
- 证券模型支持 SH/SZ/BJ、显式 `A_SHARE`；仅校验代码形式和交易所后缀一致，不以代码前缀证明真实证券类型。ETF、指数、B 股等暂不接受。
- 上市生命期为 `[listing_date, delisting_date)`；退市日定义为首次不再上市的日期，null 仅表示没有已记录的退市事实，不证明永不退市。
- 名称有效期为 `[effective_from, effective_to)`，有效期允许缺口，缺口必须报未知，不能把当前名称填至上市日。ST/风险历史未实现，返回 `risk_status=None` 和告警，不能从名称推断 ST 或正常状态。

### 不可变时间线版本

`security_versions` 每个版本原子保存一个实体的完整“已知名称有效期”时间线；JSON 中 1–256 个有序、不重叠区间可以不覆盖全部生命期。逻辑上的 `instrument_id,effective_from` 仍界定有效段，物理上作为不可变版本的一部分保存，避免关闭旧有效段时 UPDATE 历史。整个版本单行写入，不存在事后追加子记录改变旧版本的问题。

每个实体只有一条已确认版本链，版本唯一键为 `(instrument_id, record_version)`，单根、单后继、父版本外键，禁止分叉。不同来源不能并列成为互相冲突的根版本；换源必须显式指定前驱版本和 `revision_reason`，系统不自动选优。代码相同的不同实体，其生命期在系统可见区间相交时也不得重叠；检查包含被后续修订替代前的历史版本。

新证据需要修订时，调用方提供完整已知时间线、前驱与依据；旧版本不覆盖。`quality_status=accepted` 仅代表结构校验通过，不代表来源真实性、完整性或历史证据已认证。其他主数据质量状态暂不接收。

### 来源、事件与系统时间

两类数据均要求显式 `source`、`record_version`、`event_time`、`available_at`、`observed_at`、`ingested_at`、`evidence_kind` 和 `evidence_ref`。来源为 `provider:endpoint:adapter_version`；证据种类只能是 `synthetic` 或 `source_observation`，前者读取时始终告警，后者是调用方的来源声明，不是系统自动认证结果。

这里 `event_time` 表示参考数据版本描述的事实/公告事件时点；对于预先发布的日历，是日历版本发布事件，不是未来交易日收盘时刻。它与业务有效日期分开。缺乏该时间的来源不能被自动补造为历史发布事件。`event_time <= available_at`、`event_time <= observed_at <= ingested_at`，统一 UTC 固定微秒精度；允许实际可用时间晚于观察/入库（如另有使用限制），但查询仍等待两个截止条件。

所有模式都同时限制 `available_at <= as_of`、`ingested_at <= as_of`。修订三项 available/observed/ingested 时间不得倒退，`max(available_at,ingested_at)` 必须严格推进。业务有效日期可早于或晚于观察日期；不能让今天才观察到的修订出现在过去的 as_of。

### 交易日历

日历按 `(exchange, session_date)` 建立唯一版本链，版本键再含 `record_version`；不同交易所不互相复制。accepted 必须明确布尔 `is_trading_day`；source_error 必须为空状态并附错误说明。source_error 版本不允许回退读取旧 accepted 版本。

单日查询区分：已知开市 true、已知休市 false、缺失 CalendarDataMissingError、源错误 CalendarSourceError。没有记录绝不等于 false。

区间为两端包含，最多 36600 个日期。research 返回已知开市记录，并显式给出 missing_dates、source_error_dates、complete 和告警；严格/纸面模式遇任一缺失或错误则失败。最近已知交易日查询必须给出 search_start 和不包含的 before；research 可返回带不完整标记的最近已知开市日，不承诺它是实际紧邻上一交易日。无可用日时依次保留源错误、缺失或“已知区间无开市日”的错误类别。

本任务仅支持日期级状态，不提供开收盘时刻、临时半日市、停牌/涨跌停或日内可交易性。单条/查询结果的 data_snapshot_id 是带查询范围和血缘的观测摘要，不是可重开的全库或完整实验快照。

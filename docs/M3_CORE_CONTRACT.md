# M3 核心诊断契约 v1（候选，独立 H 审查前冻结门禁）

对应 Issue #30 / TASK-M3-CORE-001。schema=`m3-core-diagnostic-v1`，计算版本=`m3-core-rules-v1`。这是既有数据契约的附加纯计算接口，不修改旧 `m3-research-v1` 页面、ReferenceResult、SQLite 或 CFFEX v2 语义。没有默认升级 M4 MarketState 的逻辑。未经独立审查，不作为 TASK-M3-REMODEL-001 的稳定依赖。

## 调用与输出

入口为 `ai_trade.market_analysis_core` 的 `price_diagnostics`、`breadth_diagnostic`、`fear_greed_diagnostic`、`cffex_diagnostic`、`environment_diagnostic`；返回 `market_analysis_contract.Diagnostic`，统一用 `to_dict()` 序列化。页面只消费结果，不自行把 UNKNOWN 变成通过。

```python
from ai_trade.market_analysis_contract import Request, SourceEvidence
from ai_trade.market_analysis_core import price_diagnostics

request = Request("2026-10-16", "2026-10-19T15:00:00Z", "sh000300")
source = SourceEvidence("actual-provider:endpoint:version", "actual-version", ("actual-snapshot-ref",))
diagnostics = price_diagnostics(actual_prices, request=request, source=source)
payload = diagnostics["daily_trend"].to_dict()
# 缺少认证时只可能 L1/BLOCKED；不能因为计算返回值便认定 L2。
```

| 字段 | 含义及失败语义 |
| --- | --- |
| indicator / schema_version / definitions_version | 唯一指标、结构和计算版本；跨版本不混算历史分位 |
| request | analysis_date、UTC as_of、symbol、INDEX/STOCK/ALL_A/CFFEX、research/strict_backtest/paper_trade |
| source | 来源、源版本、血缘引用、来源/研究授权/时点三个独立 Receipt、证据种类、可选最新源日期及端点 |
| data_latest_date | 截止 as_of 实际可见数据日期；不是请求日期的别名；无数据为 null |
| times | event_time、observed_at、ingested_at、available_at：可见输入的各字段最大值；任一所需输入缺该字段时该项 null |
| coverage | valid_samples、expected_samples、ratio、denominator、denominator_refs、missing_dates；未知分母为 null，不能由现有行数推导完整性 |
| values / calculated | 有限数或 null；true zero 保留；能计算不等于获准研究。格式错误清空计算结果 |
| status / admission | 主状态及独立准入级别；主状态有优先序，所有并发问题仍保留在 reasons |
| reasons / missing_fields | 稳定原因码、具体限制、下一步、阻断 L2/L3；不以一条“数据不足”覆盖所有诊断 |
| data_snapshot_id | SHA256(request/source/times/coverage/values/计算版本)，用于审查绑定；不是原始行情仓储或数据真实性证明 |
| allowed_uses | observation / research / strategy，live_trading 永远 false |

UNKNOWN 使用 JSON null 或显式 UNKNOWN 枚举；不以 0、正常、休市、可交易或布尔 True 替代。`Receipt(VERIFIED, refs)` 是受信任调用方的带引用声明，本库只校验结构及一致性，不认证签发者。引用必须指向可审的实际材料；手工构造 VERIFIED 不是来源验收。离线夹具声明不能作为真实验收。`evidence_kind=synthetic` 自动阻断 L2/L3。

### TASK-M3-CORE-001-FIX：身份、质量与成交额校验

所有实际参与的可见记录逐行校验 `source`；价格记录以及显式提供 `symbol` 的市场记录同时逐行校验标的。TASK-M3-CORE-003-FIX 在 M3 局部统一标识规则：必须为非空字符串、首尾无空白、最多256字符，拒绝 C0（U+0000–U+001F）、DEL（U+007F）及 C1（U+0080–U+009F），随后与调用方声明精确匹配。诊断入口对声明的 symbol/source/source_version 和实际参与记录使用同一规则；CFFEX 同时校验请求会员及选中版本的已公布会员/合约标识。声明对象只是输入载体，构造成功不代表准入通过；格式拒绝由公开诊断返回结构化结果。保留共享 `text_field` 及存储调用方行为，不自动 strip、转换、填充或丢弃。身份格式/一致性错误使用 `INVALID_DATA` 原因及状态、`BLOCKED` 准入，清空值、calculated=false，所有 allowed_uses=false。综合诊断传播组件的 INVALID_DATA 并清空整个综合结果，不能以其他合格组件覆盖非法输入。

`quality_status` 是逐记录的质量决定，与来源/授权/时点 Receipt 独立。全部记录显式为 `accepted` 才能通过质量这一项；quarantined、rejected、其他未知状态字符串、空字符串或非法类型均 INVALID_DATA/BLOCKED。整列缺失或值为 None/NaN 保持 UNKNOWN，记录 `EVIDENCE_MISSING` 和 `missing_fields=quality_status`；research 至多 L1，strict_backtest/paper_trade 阻断。不从已认证来源或 Receipt 默认 accepted。全 A 因子的质量/身份失败原因和缺失字段传递至完整恐贪，不能被包装层隐藏。

CFFEX 既有 `CffexRankingsRecord` 没有质量字段；核心 `cffex_diagnostic(..., quality_status=None)` 新增可选关键字，默认 UNKNOWN，调用方必须提供实际质量决定。即使其他 Receipt 全部通过，质量未知仍无 L2、direction=null。底层 CFFEX 版本链、ReferenceResult、日历和来源认证语义不变。此声明本身也不是外部真实性认证。

完整恐贪输入若提供 `market_amount_cny` 列，则所有参与日期必须是非布尔、有限、非负数；真实0合法。R2/R3 明确核心数值边界只接受 Python `int`/`float` 及 NumPy `integer`/`floating` 标量，拒绝 Fraction（即使是整数值）、Decimal、复数、布尔、字符串和其他对象。OHLC 与成交额先检查原始标量，再受控转换为有限 float64；OHLC必须大于0，成交额允许0。转换溢出、非零下溢为0及非有限结果均拒绝；计数还须为非负整数，转换范围检查后仍以精确 Python int 保留，不经浮点重写计数。全部检查在 DataFrame 重建之前进行；构帧使用 object 防止未消费列触发隐式推断，再显式设置已验证价格/成交额的float64类型。

None、NaN、空/非法字符串、正负无穷、`10**400` 等超范围输入均返回带字段/日期/标的或ALL_A范围的 INVALID_DATA/BLOCKED，不 coerce、不跳过、不补零、不复用旧结果。宽度计数原有缺失值/缺列仍为 FACTOR_MISSING，整列成交额没有提供仍为必要因子缺失，完整 score=null；存在的成交额列内缺失值仍是非法样本。以上修复不改变公式、序列化外形或已有原因码；JSON Schema 无需新增枚举。旧来源验收记录保留当时的事实，不回写 accepted。

状态：SOURCE_UNAVAILABLE、HISTORY_INSUFFICIENT、FACTOR_MISSING、STALE、TIME_UNCERTIFIED、INVALID_DATA、EVIDENCE_CONFLICT、OBSERVATION_ONLY、RESEARCH_ALLOWED、STRATEGY_ALLOWED、BLOCKED。全部枚举及原因码以 Python 契约为唯一机器定义；JSON Schema 校验其序列化外形。SOURCE_UNAVAILABLE 描述没有输入，接口错误由独立来源验收保留具体 HTTP/TLS/超时分类。

## 时间、覆盖与阈值

所有时间必须是显式带时区 ISO 时间；规范化 UTC 比较，交易日期用上海日期。只选 trade_date≤analysis_date 且所有已知实际时点≤as_of 的记录；晚采集不能回放到采集前。R4 将通过验证的已知时间在计算副本中统一表示为 Asia/Shanghai，再传入旧计算器；同一UTC时刻的合法offset表达得到相同诊断及快照，输入帧和历史记录不修改。聚合时间仍输出规范UTC。缺 available_at/ingested_at/event_time 的旧快照保留 UNKNOWN。采集时间不冒充历史首次可得时间，完整日线事件不能晚于观察/入库/可得时点。当前实现要求调用方先选择单来源、单标的、单日唯一的可见版本；重复日期不擅自选最新版。

L2 日期分母来自**独立可见、已认证、明确范围的 CN_A/CFFEX 日历查询**，逐日对比实际输入，不能用工作日算法或行情日期本身当分母。全部所需日期必须齐备（100% 是“不允许缺项”的工程条件，不是预测可靠性阈值）。新鲜度为请求日必须真实有数据，容忍滞后为 0 个认证交易日；非交易日请求返回实际截止和 STALE，不猜休市。日历缺失时无法判断完整性，只能 L1。

| 指标 | 最低有效历史 | 依据、口径与失败 |
| --- | --- | --- |
| daily_trend | 60 日样本 | C>MA20>MA60 偏多；C<MA20<MA60 偏空；其余中性；不足60不计算方向 |
| weekly_structure | 20 个完整已结束周 | 周一至周日分组，OHLC=首/最大/最小/末；排除分析日所在整周；日历未覆盖完整首周时排除首周。末周收盘相对20周均值；周内缺日仍阻断 L2 |
| wave | 60 日样本 | 复用简化候选情景/斐波那契，不声称唯一正确计数；低置信研究解释；日线均线方向不等于确认反转 |
| price_proxy | 最早第41条 | 20条收益波动需要21价，再需此前20个有效波动值；前3因子权重除0.65。个股也仅独立代理 |
| fear_greed | 最早第41条且当日6项全有 | 价格3因子+同日全A宽度2因子+全A成交额；指数/个股自身成交额不得替代全市场额 |
| market_breadth | 当日1条+对应历史股票池证据 | 只声明当日覆盖，不声明具备历史全A；连续序列仍需逐日认证 |
| cffex_position | 当日1个可见完整版本 | 单合约/会员/代客或自营；没有一份榜单不等于仓位0，不外推完整机构/最终客户 |

以上最低值是公式成立条件，不是预测训练所得样本量。完整历史覆盖、认证和质量条件独立于样本数。周线即便样本够、但日历或时点未知，也只能标记观察。

## 六因子与历史分位

复用 `market_analysis.WEIGHTS` 和 `fear_greed` 的固定公式：趋势=.25×clip(50+500×(C/MA20−1),0,100)；5条动量权重.20；低波动权重.20；上涨/(上涨+下跌+平盘)×100权重.20；涨停/(涨停+跌停)×100权重.10；成交额比值权重.05。动量、20条收益总体标准差、当日全A额/此前20条全A均额，用此前最多60条有效值的中位秩分位（至少20条），低波动取100−分位。分母0为 UNKNOWN。

六项任一缺失，完整 score=null，**不重分配完整权重，不填零**；price_proxy 独立输出。完整分数/代理的历史分位各自只用此前最多252个同定义有效值，至少20个，排除当日及未来。序列只接收单源/单标的/声明的同版本；调用方必须保证该版本血缘覆盖整个序列，不能混入不可追溯修订。分数标记 experimental=true，无预测能力或胜率宣称。本任务不报告极端后收益或样本外验证。

## 全 A 股票池与覆盖

每个日期必须有：五种公开计数，以及 eligible_count、suspended、unavailable、missing、universe_snapshot_ref、universe_date、universe_available_at、universe_ingested_at。Universe Receipt 必须覆盖每个 ref，引用的材料需证明当日有效证券身份、上市/退市范围及停牌状态；本库不从最新股票池回填。日期必须相等，快照时点必须≤as_of。

分区：eligible = advances+declines+flat+suspended+unavailable+missing。有效覆盖分子=有明确涨跌平数据的证券数+明确停牌证券数；分母=当日符合股票池口径的证券数。停牌不算平盘，宽度比率的分母单列 quoted_denominator=涨+跌+平。缺失/不可用不并入已覆盖。100%分区且证据、日期完整才声明 all_a_scope_verified；少量股票即便上涨比例可算，也不能提供全A研究因子。乐咕当前聚合快照没有这些证据，不能据其数值认证全A历史。

## 波浪、CFFEX 和综合

左右各3条严格极值，右3条已可见后才有转折。每个点记录 trade_date、confirmed_date、7条 confirmation_input_dates、first_usable_at（7条的实际观察/入库/可得时点最大值；缺任一则 null）。分析日/as_of 截断后才找点；不能把事后确认回标为当时信号。多候选同时保留，各有支持/失效条件，unique_wave_count=false。

CFFEX 复用已审 `select_visible_version/net_positions_at`：调用方提供完整版本链、权威 CFFEX 日历，available_at 仍是采集后第一个符合条件的后续开盘，**不改为发布时间**。净仓=同日同合约同会员同范围多−空；净变动=两侧公开持仓变动之差，不等于经过修订比较的历史净仓差。成交量与持仓分开。单侧榜外为 null；真实两侧0给net=0。代客+自营、UNKNOWN口径不合并。合约YYMM仅显示到期月份，准确到期日/换月标记 UNKNOWN；跨合约聚合未实现。发布时间或口径认证或日历未具备时 direction=null，不能参与综合。席位不是国家队或最终客户。

综合要求同分析日、as_of、计算版本，波浪和恐贪使用相同指数；3类分别先获 L2，才可参与。方向取 CFFEX已认证净仓符号、趋势均线方向、完整恐贪>60偏多/<40偏空/其余中性。先保留已合格证据的冲突，再检查3项是否齐全；齐全一致时≥2项同向标偏强/偏弱，否则震荡。此为公开解释规则，不相加、不生成概率。冲突阻断L2，全部原始诊断/快照仍可追溯；缺项结论数据不足。

## 准入与失败诊断

| 级别 | 必须条件 | 失败、升级与用途 |
| --- | --- | --- |
| BLOCKED | 无可见观察、格式错误、作用域非法，或严格模式缺必要门槛 | 不提供可用数值；保留原因与下一步 |
| L1_OBSERVATION | 可追溯明确来源/版本/引用的有效观察 | 可显示限制下的真实/派生值；来源/授权/时点未知、历史不足、过期或缺因子均不能升级 |
| L2_RESEARCH | 非合成，来源/研究授权/时点认证；全部所需字段、最小历史、完整日历覆盖、准确请求日、作用域及各指标特定条件通过 | 可复现研究输入；不是统计验证、策略或实盘许可 |
| L3_STRATEGY | L2 + `strategy_admission`匹配最终实现40位SHA、计算版本、data_snapshot_id、独立H审查引用、执行约束引用、样本外验证引用、已知批准时间≤as_of | 只校验受信任外部审批凭据一致性；当前真实数据均未满足，无默认L3，不连接下单 |

例如：550条价格但 available_at=null → TIME_UNCERTIFIED/L1；5个计数但分母未知 → UNIVERSE_UNKNOWN/L1；缺全A额 → FACTOR_MISSING且完整分数null；单侧会员 →净仓null；无发布时间证据 → direction=null；合格多空矛盾 → EVIDENCE_CONFLICT；历史采集在as_of之后 →不进入输入。`reasons[].next_action`是最小补充操作，不是自动补数或下单请求。

实现、真实来源、离线结果和独立审查状态参见 [任务记录](tasks/TASK-M3-CORE-001.md) 及 [来源验收](M3_CORE_SOURCE_ACCEPTANCE.md)。

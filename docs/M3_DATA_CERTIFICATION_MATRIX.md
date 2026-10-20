# M3 数据认证矩阵：TASK-M3-DATA-PIPELINE-001

基线 `94cdd487bfd4633ecc2f002aad014f98dec961a5`；真实批次 `pipeline-20261020T153923Z-c55591fd`。依据[接口报告](M3_DATA_PIPELINE_REPORT.md)、[机器证据](evidence/TASK_M3_DATA_PIPELINE_001.json)和现有[M3核心契约](M3_CORE_CONTRACT.md)。本矩阵列证据/缺口，**不实现第二套准入规则**；状态、数值和allowed_uses只来自核心。接口PASS与研究认证BLOCKED可以同时成立。

## 1. 来源、字段、单位、历史和真实性

| 数据集 / 接口验收 | 完整必要字段与单位 | 实际覆盖 / 分母 | 时间、历史状态和认证缺口 | 当前核心 / 研究认证及升级条件 |
| --- | --- | --- | --- | --- |
| 新浪指数 **PASS** | trade_date；symbol/source/version；OHLC=指数点；adjustment_method；逐行quality_status；event/observed/ingested/available时间；血缘 | 550行，2024-07-10～2026-10-19；认证应有日数UNKNOWN | 实际observed/ingested已记录；event/available、调整定义、质量决定、历史首发/日历、供应商授权UNKNOWN | 趋势/周/波浪/代理L1；研究**BLOCKED**。补齐源/授权/时间Receipt及独立完整日历，按实际每行质量校验；核心H门禁先关闭 |
| 东方财富个股 **FAIL** | 日期/代码/OHLC=CNY每股；成交量源手→股精确×100；amount=CNY；instrument_id/source/row_version/quality/times/adjustment | 本次未取得帧，实际条数/范围UNKNOWN；请求仅600000.SH、10-14～15 | SSL传输错误；HTTP未知，不能推断休市；结构字段清单来自已读映射，不冒称实际响应 | 未有可交核心的观察；认证**BLOCKED**。先诊断可信证书/源访问，再单独授权同范围重验；另核实真实历史身份和许可 |
| 腾讯个股 **PASS** | date/OHLC=CNY每股；SDK已将主板volume规范为股、amount规范为元；原始行版本/批次；event/available/ingested；逐行accepted仅结构质量 | 实际2行10-14、10-15；临时写2/读2；应有日数UNKNOWN | 实际采集/验证时刻已记录；available沿用今天观察时刻，不能回放至10-14/15；原始day键/去重前冲突、历史身份/ST/停牌/授权未认证 | L1（请求日10-19时STALE且历史不足）；研究**BLOCKED**。不能把2行扩写成完整历史；需认证原始键/口径、足够历史、日历、实体与授权 |
| 乐咕宽度 **FAIL** | advances/declines/flat/limit_up/limit_down=证券家数；逐行source/symbol/quality/times；eligible/suspended/unavailable/missing=家数；universe_ref/date/visible times | 本次条数/日期UNKNOWN；SDK仅当前快照；真实全A分母UNKNOWN | 未收到任何真实聚合；即使收到5个家数，也没有当日历史证券池/分区/逐实体证据 | core SOURCE_UNAVAILABLE/BLOCKED；研究**BLOCKED**。不可用当前列表倒填，须取得逐日真实池证据及完整分区 |
| 全A成交额 **BLOCKED** | market_amount_cny=CNY；单日全A口径；同日source/version/quality/times；每个参与样本受核心数值校验 | 无注册历史来源，分母/日期/行数UNKNOWN | 单指数或个股amount不代表全市场；未知、非法金额不填0/不drop | 完整恐贪缺该因子；研究**BLOCKED**。先明确并审核来源、范围/单位及历史可得时间，再有界接入 |
| CFFEX会员榜 **FAIL** | exchange/variety/trade_date/contract/member/member_scope/rank/side；volume/volume_change与OI/OI_change分开，均供应商合约计数；版本链/来源/发布时间/观察/入库/可用时刻/quality | 本次IF/2026-10-16无已验收行；实际条数UNKNOWN；未请求其他品种 | TLS错误、HTTP未知；权威CFFEX日历/会话、实际publication、代客/自营口径、源/授权证据均缺。raw CSV不等于CffexRankingsRecord | SOURCE_UNAVAILABLE/BLOCKED，direction=null；研究**BLOCKED**。先认证日历/时间及完整版本链，用既有ingest/read端口生成记录，不能手工补next-session或零仓位 |
| CN_A日历 **BLOCKED** | exchange/session_date/is_trading_day；record_version/event/observed/available/ingested；evidence_kind/ref；complete/missing/source_error | 存储支持SH/SZ/BJ日期级版本；无已认证真实来源，本轮0请求 | 缺失!=休市；不能从行情日期或工作日推断分母；日期级日历不足以证明特殊开收盘会话 | 未传CalendarEvidence，核心CALENDAR_UNKNOWN；研究**BLOCKED**。提供可见、完整、明确范围及授权的真实查询结果 |
| CFFEX日历 **BLOCKED** | CFFEX/session_date/is_trading_day/opens_at/closes_at及可见来源证据 | RankingCalendar仅端口，无正式来源/仓储；本轮0请求 | 不复制SH日历；需能在真实采集时刻证明未来首个合格开盘，所有中间日未知即阻断 | CFFEX方向/研究**BLOCKED**。独立补证/设计任务，保持既有next-session available_at语义 |
| 历史证券身份 **BLOCKED** | instrument_id=上市实体锚点；symbol/exchange；名称有效区间；listing_date/delisting_date；完整版本链及双时间 | SQLiteSecurityMaster已实现存储/查询，但无已认证历史源/范围 | 本轮样本instrument_id是观察标签；未解析成经过证明的历史上市实体，不能处理假定代码复用或当前名称回填 | 全A历史身份认证**BLOCKED**。先取得当时可见上市实体/变更/生命周期证据 |
| 历史ST **BLOCKED** | 每个instrument_id的显式风险状态/有效期/来源/实际可得时刻 | 无接入来源，risk_status仍UNKNOWN | 名称含ST或当前不含ST都不能倒填历史 | 研究过滤**BLOCKED**。独立定义/验收历史风险端口及证据，不把UNKNOWN当普通股 |
| 停牌 **BLOCKED** | instrument_id/trade_date/suspended及source/version/quality/times；计入全A分区的明确停牌数 | 无认证逐日来源，实际覆盖UNKNOWN | 缺bar不能认定停牌，也不能当作平盘或可交易 | 研究/交易可用性**BLOCKED**。补逐日明确状态及历史池，不填缺失计数 |
| 退市 **BLOCKED** | instrument_id/listing_date/delisting_date及当时可见版本；[上市日,退市日)生命周期 | 现有参考模型支持生命周期；真实历史退市证据未接入 | null退市日仅无已知事实，不证明永久上市；不能只用现存股票列表 | 生存者偏差防护认证**BLOCKED**。独立验收历史实体范围、退市日期定义和版本可见性 |
| 六因子恐贪 **BLOCKED** | 价格趋势/动量/低波动；上涨比/涨停比；全A成交额；全部同日/同源版本与实际时间 | 指数价格550行可算独立代理；全A三项来源不齐，分母UNKNOWN | 任一因子缺失完整分数和完整分位均null；不重新分配完整权重 | core L1诊断、calculated=false、score=null；研究**BLOCKED**。仅消费core同日完整因子，补证后重新计算，不用代理顶替 |

## 2. 统一认证维度和证据规则

| 维度 | 本轮证据 / 缺口 | 升级规则来源 |
| --- | --- | --- |
| 字段语义/单位 | 源码/映射清单已读，两个成功源取得实际字段；未知调整键/全A统计范围不推断 | 既有adapter、DATA_CONTRACT及M3 scope检查；结构通过不认证供应商事实 |
| 来源及授权 | HTTP/载荷hash是本次观察；个人研究/本地存储/自动采集/商业/公开展示/再分发权限均UNKNOWN | SourceEvidence三种Receipt仍UNKNOWN；SDK MIT不升级数据许可 |
| 样本和分母 | 实际550/2与日期可追溯；独立日历/全A池分母缺失，因此ratio=null | core Coverage；禁止以样本数充当预期数 |
| 新鲜度/历史 | 请求分析日10-19与实际最新日期分列；腾讯样本截止10-15，core如实STALE；预期最新交易日UNKNOWN | core请求日/实际日期、认证日历；0容忍规则不等于已证明市场当日开市 |
| 缺失/异常/一致性 | 现有core逐行身份、OHLC、数值/质量、跨字段检查；下游不覆盖显式坏行身份，不静默drop | 只消费INVALID_DATA/BLOCKED、missing_fields/reasons，合法零保留 |
| 历史状态/日历 | 每项缺口单列；当前名称/池/ST不能回填；未知不能当停牌/休市/可交易 | DATA_CONTRACT证券生命期、双时间及日历查询语义 |
| 时间约束 | observed/ingested是实际本次系统时刻；缺event/available原样null；历史回放同时受available/ingested/as_of限制 | 既有核心、仓储及CFFEX版本端口；不改采集可见性或历史版本 |
| 版本/批次/复现 | 指定main基线、core规则版本、run_id、HTTP/SDK帧hash、每条诊断data_snapshot_id、代码文件hash | 快照digest只是观察摘要，不是可重开全库/来源真实性证明 |
| L1/L2/L3 | 实际成功源最多L1，研究/策略/实盘均未批准；源失败及综合BLOCKED | 核心Diagnostic/strategy_admission唯一准入来源；独立H、执行约束、样本外、SHA/快照/批准时间另行核验 |

工程阈值只引用既有契约：60日日线/波浪、20完整周、价格代理/完整分数最早41条、完整会话/全A分区不允许缺项、右3条确认、此前历史分位。它们是公式/完整性要求，不是统计可靠性阈值；本任务没有新设容忍缺失比例、胜率或生产阈值。请求次数、字节数和超时仅是本次资源预算。

## 3. 认证状态结论

**真实接口验收部分通过；真实研究准入整体BLOCKED。** 不存在由“接口200”自动升级到L2的路径；本任务不签发VERIFIED Receipt，也不执行L3审批。核心独立H Issue #37及本候选证据桥的独立审查仍须完成，不能凭合并/离线/本矩阵解除M3页面、M4或生产/实盘门禁。

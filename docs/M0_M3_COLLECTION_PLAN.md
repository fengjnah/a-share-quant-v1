# M0/M3 有界采集计划（待前置条件）

TASK-M0-M3-DATA-001；基线 `c4b682d12c7c8dc42f75e717b855238f635ce05b`。根据[实际库存盘点](M0_M3_LOCAL_INVENTORY.md)制定，**不是采集执行许可或已落实能力**。本轮新行情请求0、已有库写入0。用户补充确认现有7张表，尚未给出Windows正式SQLite文件路径；不能凭迁移定义确认物理库。

## 1. 开启条件、顺序与范围

先确认正式Windows研究库的完整绝对路径、归属/非生产性质、当前应用绑定和备份机制；只读核对v1/v2迁移checksum。未确认不创建、复制、初始化或迁移库。然后确认来源对本地保存、个人研究和自动采集的实际许可；商业、公开展示和再分发分别判断，未知用途保持UNKNOWN。本任务不作法律授权认定。

顺序为：可信日历/时间证据 → 既有个股增量及指数存储兼容 → 全A池、宽度/成交额、证券状态 → 完整六因子及CFFEX。每一步只在对应来源/字段/时间/存储契约已具备时执行，不能为追求顺序完成补造缺失元数据。

| 批次草案 | 选定数据和日期 | 请求/资源硬上限 | 当前可执行性 |
| --- | --- | --- | --- |
| C0 日历 | 首次只验证SH/SZ/BJ分别2026-10-14～20；要回填全部历史需按独立已授权版本另定范围 | 本轮0；待正式接口确定才设置每交易所≤1次、≤2MB、连接/读取5/5秒、worker30秒、0重试的上限 | BLOCKED：无正式来源/许可/发布证据，不运行未有接口的计划 |
| C1 基础个股 | 已有600000.SH来源固定腾讯；仅缺口2026-10-16～20、不复权；600378已有2291行不重下 | 后续草案最多2个HTTPS发送：起始年探测1+2026年行情页1；每响应≤8MB、5/5秒、worker45秒、0重试；整个任务只允许1个该小批次 | BLOCKED：库路径/授权未明确；日历未知不能把空行解释为休市；范围变化须重算预算 |
| C2 指数 | 已有沪深300550行应先复用；实际最新10-19，初批只核验缺口10-20 | 本轮0；如未来确需新浪请求最多1次、8MB、5/5秒、worker30秒、0重试；该端点返回历史载荷，无法保证只下载缺口 | BLOCKED：既有7表不接受指数实体；无已审查持久接口、授权及available规则；不重复下载550行或借股票ID强塞 |
| C3 宽度/全A额/身份状态 | 第一阶段只验同一日2026-10-20；股票池必须包含当日历史实体/停牌/退市/缺失分区；完整恐贪至少41条同期输入后才可能计算 | 0请求；来源、全A范围与正式接口待确认后另给逐源预算，不执行全市场循环 | BLOCKED：无完整数据/持久化端口；当前乐咕接口只是当前快照，不是历史API |
| C4 CFFEX | 最小IF、2026-10-16、单CSV；先具备权威日历/开收盘及发布时间/会员scope证据 | 本轮0；后续草案最多1次、2MB、5/5秒、worker30秒、0重试；不扩至IH/IC/IM | BLOCKED：历史SSL未诊断、授权/完整版本存储/日历缺失；先完成独立来源任务 |

后续预算草案不是把旧失败次数清零的许可。#40东方财富/乐咕/CFFEX已各一次SSL失败；先有独立诊断证据，再决定是否允许复验。429/403、超时、TLS/解析/校验错误立即终止相应源，不重试、不自动换源/代理、不关闭TLS。等待Retry-After并不授权本任务重发；断点续采另次显式运行再核对批次和预算。

## 2. 来源、实际接口、字段与许可清单

以下接口来自当前仓库和本机固定AKShare1.19.1实际源码，不宣称上游今天可用。官方发布方与现有候选供应商分开；没有实际注册接口的项目保持UNKNOWN，不编造URL。与既有[#40来源矩阵](M3_DATA_CERTIFICATION_MATRIX.md)一致。

| 数据 / 来源 | 当前实际接口与端点 | 字段、单位和历史限制 | 存储复用 / 当前状态 |
| --- | --- | --- | --- |
| 个股主源：东方财富 | `AkshareDailyClient → stock_zh_a_hist`；`https://push2his.eastmoney.com/api/qt/stock/kline/get` | OHLC CNY/股，源volume手经适配器×100为股，amount CNY；显式SH/SZ、日期、不复权 | `DailyHistoryIngestor → SQLiteMarketDataRepository`，现有4张行情/批次表；近期SSL失败，未选作本轮自动备用 |
| 个股候选：腾讯 | `TxDailyClient → stock_zh_a_hist_tx`；`https://proxy.finance.qq.com/ifzqgtimg/appstock/app/newfqkline/get`；起始日期探测`https://web.ifzq.gtimg.cn/other/klineweb/klineWeb/weekTrends` | SDK将已验收主板量转股、额转元；适配器不再×100/×10000。日线不复权；SDK按年份请求两年窗、640参数，再本地裁剪，2个目标不是2行网络返回；探测为空时SDK还有同域额外GET路径，必须由硬预算阻止第三次发送并将该批次标记失败，不能无限探测 | 同一既有Ingestor/EvidenceStore/版本仓储；不扩至BJ/ETF、复权/公司行为或全市场认证 |
| 指数候选：新浪 | `stock_zh_index_daily(sh000300)`；`https://finance.sina.com.cn/realstock/company/sh000300/hisdata/klc_kl.js`；SDK固定d=2020_2_4 | date/OHLC指数点；既有采集只保留最近550行OHLC；现存观察无全A额/质量决定/历史available | 现有`save_snapshot/snapshots`内容寻址JSON可读；不能写入只支持A股身份的daily_bars，新增指数持久模式须另经H设计 |
| 宽度候选：乐咕 | `stock_market_activity_legu()`；`https://legulegu.com/stockdata/market-activity` | 当日统计日期、涨/跌/平/涨停/跌停=证券家数；无逐日历史股票池、完整分区或全A额 | 现有观察JSON/核心输入；没有正式历史宽度仓储，不能回填历史或据5个计数认证分母 |
| 全A成交额 | 正式提供方/实际接口UNKNOWN | `market_amount_cny` CNY，全部参与样本有限且非负，合法0保留；单证券/指数额不能替代；应明确是否含BJ/退市整理等 | 7表无该统计数据集；0请求，待有界来源研究及正式持久设计 |
| A股日历 | 正式证据应来自各交易所明确发布的会话/休市资料；现有接入接口UNKNOWN | SH/SZ/BJ逐日显式开/休市、版本、发布日期/观察/入库/可用时间；没有记录不等于false | 复用`SQLiteTradingCalendar/CalendarDay → calendar_versions`；旧历史开市日期列表不足以填写所有休市日或版本发布时间 |
| CFFEX日历 | 权威CFFEX会话资料；现有真实接口UNKNOWN | session_date、is_trading_day、opens_at/closes_at及时点证据；不能复制股票日历 | `RankingCalendar`端口；现有calendar_versions仅SH/SZ/BJ，不能直接写CFFEX，需另经H设计 |
| 证券身份/上市/退市 | 正式提供方/实际历史接口UNKNOWN | instrument_id应为上市实体；symbol、exchange、name intervals、listing_date/delisting_date、版本和真实可得时间 | 复用`SQLiteSecurityMaster → security_versions`；当前instruments代码标签不等于实体认证；当前名录不回填历史 |
| 历史ST/停牌 | 正式提供方/实际接口UNKNOWN | 实体、显式状态、有效期/交易日、源/版本/发布时间；零量/缺bar/当前名称不能替代状态 | 7表无独立历史风险/逐日交易状态实现；risk_status仍UNKNOWN，不能往名称JSON偷加另一套语义 |
| 六因子 | 派生，`market_analysis_core.fear_greed_diagnostic` | 价格trend/momentum/low_volatility；全A advancing/limit_ratio；turnover_factor。同期、认证分母、版本/as_of约束沿用核心 | 不另采“现成恐贪分数”，不重新分配缺项权重；价格代理分开，任一必要项缺失完整分数null |
| CFFEX持仓 | `CffexRankingsClient/parse`；`https://www.cffex.com.cn/sj/ccpm/202610/16/IF_1.csv` | 合约/会员/日期/排名/多空、OI及OI变化、成交量及变化，单位合约计数；自营/代客明确分开 | 复用既有解析/版本/时间端口；7表无持久榜单实现；CSV观察不能冒充通过时栅的排名记录 |

上述供应商个人研究、本地保存、自动采集、商业使用、对外展示/再分发的许可证据均未在本任务取得，保持UNKNOWN/BLOCKED；不能因旧请求成功而推定获准。SDK软件MIT许可与数据权利分开。

## 3. 数据库写入、重复和恢复规则

仅在正式路径已确认且属于本地非生产研究存储时，先由同一既有Ingestor/校验/仓储在独立测试库执行一次固定小批次、完整读回/约束检查，再将已确认的真实记录及原始时点按同一契约写入正式本地库；不得重新联网以获得一份“第二次验证”或把测试入库时间回填为历史首次可得。测试与正式run_id分别记清、共享同一来源证据，正式ingested_at必须反映其实际校验/成功写入流程。未设计好跨库证据引用/提交后证据失败处理时先阻断，不擅改已有Ingestor接口。

现有机制不是静默幂等upsert：

- `EvidenceStore.begin`和结果/响应文件create-only；同run_id拒绝。`SQLiteMarketDataRepository.write_many`对同批次/同逐行source_version明确抛DuplicateRecordError，整批回滚；不能写成“重复采集自动忽略成功”。
- 写前按明确实体/来源/不复权/日期查询已存覆盖；仅提交未采缺口，不反复把187/1217全历史交写端。SDK即使返回完整年度页，适配器只接受请求范围；服务器大范围载荷仍计入资源证据。
- 已存同日期内容相同应在明确的预检计划中记“已有合格版本，未请求/未写入”。版本冲突不覆盖旧行、不自动选优；修订必须显式前驱、理由和推进的系统可见时点。腾讯当前mapper没有自动修订策略，不能把冲突当追加新根。
- 采集进程在数据库已提交而result.json未完成时，按`EvidenceWriteError.database_committed`调查实际run/版本，不能盲目重发。成功范围由事务与最终证据共同确认，不只依赖退出码或最后一条命令。
- 证券/日历仓储共享ingestion_runs命名空间，独立子批次必须独立run_id；当前没有跨两仓储的一体事务，不能承诺原子全数据集快照。单写者短事务，已有库/原始文件不覆盖。

## 4. 历史时间、M3接入与验收

`event_time`遵守已有数据集含义；腾讯历史行情的available_at沿用真实观察时点，是今天取得历史的保守可见时间，不证明历史当天已获得。严格读取同时限制available/ingested≤as_of；本轮三份样本在事件时刻均不可见。指数旧观察缺ingested/available保持null，不从mtime/下载时刻补历史首发。证券/日历公告版本事件与业务有效日期分别保留。

页面只消费同一选定版本/来源的本地诊断，不以某个源成功解锁完整M3。验收需分别验证：正常查看0行情请求、相同as_of/版本读回相同、增量写入/重复拒绝/失败整批回滚、精确字段与单位、真实期望会话分母、缺数据仍null/UNKNOWN及来源/权限门禁。CFFEX available_at仍按既有权威日历的采集后后续合格开盘时栅，不改为直接发布时间。

现有 `verify_m3_pipeline.py` 是限定隔离验收入口，不支持正式目标库和任意增量范围；不能放宽它的artifacts保护来当正式采集器。应复用现有库/适配器/版本端口，在正式根路径和许可确认后明确最小接线，不创建另一套存储/准入算法。

后续建议（尚未创建/派发）：库路径/所有权确认；三源TLS可信证书诊断及许可核验；日历与历史实体来源验收；指数/全A/状态/CFFEX现有7表之外的契约缺口H设计；最后本地页面同库验收。所有云端同步、部署、策略样本外和实盘授权独立立项。

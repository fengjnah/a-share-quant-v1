# M3 数据接口接通报告：TASK-M3-DATA-PIPELINE-001

2026-10-20（Asia/Shanghai）；代码基线 `94cdd487bfd4633ecc2f002aad014f98dec961a5`。本轮取得 **2 个接口 PASS、3 个 FAIL、8 个 BLOCKED** 的限定证据；没有真实 L2/L3。PASS 仅表示本次受限传输/解析取得样本，不是来源授权、完整历史、研究准入或预测能力认证。

任务配置、A/B/C 负责人/范围、规则和预算见[任务记录](tasks/TASK-M3-DATA-PIPELINE-001.md)。真实与离线证据分开；机器摘要见 [TASK_M3_DATA_PIPELINE_001.json](evidence/TASK_M3_DATA_PIPELINE_001.json)，数据认证见[矩阵](M3_DATA_CERTIFICATION_MATRIX.md)，页面兼容与后续工作见[交接](M3_DATA_PIPELINE_HANDOFF.md)。

## 1. 实际执行及限制

工作区 `F:/codex-agnes/AI-trade-m3-data-pipeline-001`，分支 `codex/m3-data-pipeline-001-work`；原 M3 页面分支不切换、不修改。一个执行者 `gpt-6.1-sol / high`，H；未委派、未执行独立 H 自审。PR #36 已合并，Issue #37 仍待独立复核；核心门禁继续保留。

显式命令（仅本次执行一次）：

```powershell
$env:PYTHONPATH = 'F:/codex-agnes/AI-trade-m3-data-pipeline-001/src'
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONDONTWRITEBYTECODE = '1'
& F:/codex-agnes/AI-trade-main-demo/.venv/Scripts/python.exe scripts/verify_m3_pipeline.py --enable-live --analysis-date 2026-10-19 --output-dir artifacts/m3-data-pipeline-001/live
```

批次 `pipeline-20261020T153923Z-c55591fd`，北京时间23:39开始。每个固定端点最多1次，总计**6次发送尝试、3个HTTP200响应**，零重试；腾讯起始日与行情页分别计数，未自动替东方财富切换源。HTTPS/TLS验证开启，正常环境代理不变，禁止重定向；I/O 5/5秒、独立worker 45秒墙钟上限，8MB响应上限（CFFEX2MB）。发送尝试不等于上游确认收到；未取得HTTP状态时保留null，不推测DNS/TCP/证书链具体根因。

总命令退出0表示证据报告生成成功，**不是五个来源全部成功**。默认去掉 `--enable-live` 时无worker、无行情请求，来源为NOT RUN；没有注册来源的项目仍BLOCKED。无生产路径参数，所有原始观察/SDK帧/SQLite仅在本工作区忽略的artifacts下；没有读取生产数据库或QUANT_DB_PATH。

## 2. 逐来源真实结果

| 来源 / 实际接口 | 固定参数 / 次数 / 本地时间 | HTTP / 解析 / 返回 | 实际范围及限制 | 结论 |
| --- | --- | --- | --- | --- |
| 新浪，经AKShare1.19.1 `stock_zh_index_daily`；`finance.sina.com.cn/realstock/company/sh000300/hisdata/klc_kl.js` | sh000300，SDK参数d=2020_2_4；1次；23:39:25–27 | HTTP200；100,910字节；解析成功；保留550行 | 2024-07-10～2026-10-19。端点返回历史载荷，客户端只保留最多550个已结束日期；不声称服务器只返回550行。未认证权威日历、历史首发/可得时间、调整口径与逐行质量决定 | **PASS：接通/解析；认证BLOCKED，核心L1** |
| 东方财富，经 `AkshareDailyClient/stock_zh_a_hist`；`push2his.eastmoney.com/api/qt/stock/kline/get` | 600000.SH，2026-10-14～15，daily/none；1次；23:39:31 | SSLError；HTTP=null，未取得SDK帧，返回条数=null，解析NOT RUN | 现有批次保留network_error；未写数据库。不把传输失败解释为空行情、休市或不存在该证券 | **FAIL：本次传输** |
| 腾讯，经 `TxDailyClient/stock_zh_a_hist_tx` | 600000.SH，2026-10-14～15，adjust=""；2次；23:39:34–36 | `web.ifzq.gtimg.cn/.../weekTrends` HTTP200/33,021字节；`proxy.finance.qq.com/.../newfqkline/get` HTTP200/60,981字节；解析及已有映射校验成功 | 返回2行，日期10-14、10-15；隔离SQLite插入2行，按源/标的/as_of严格读回2行相同。请求会先探测起始日并取年度页，不能声称服务器只返回2行。样本instrument_id仅观察标签，不是认证历史上市实体 | **PASS：接通/批次/隔离读回；认证BLOCKED，核心L1** |
| 乐咕，经 `stock_market_activity_legu`；`legulegu.com/stockdata/market-activity` | 当前公开快照；1次；23:39:39 | SSLError；HTTP=null；行数=null；解析NOT RUN | 本轮未取得真实家数/统计日期；参考SDK只提供当前聚合，不提供历史全A分母/分区/成交额 | **FAIL：本次传输** |
| CFFEX，经 `CffexRankingsClient/parse`；`www.cffex.com.cn/sj/ccpm/202610/16/IF_1.csv` | CFFEX / IF / 2026-10-16；1次；23:39:40 | RankingTransportError，链内SSLError；HTTP=null；行数=null；解析NOT RUN | 仅此IF日期尝试，未请求IH/IC/IM；原始CSV即使成功也不是已具备时间/日历/版本链的可读排名记录 | **FAIL：本次传输** |
| 全A成交额、CN_A日历、CFFEX日历、历史证券身份、历史ST、停牌、退市、完整恐贪 | 无追加网络 | 没有已认证来源或必要输入；请求次数0；行数/范围未知，不能写0行数据 | 各项字段/来源缺口及升级条件见认证矩阵；完整恐贪为派生接口，不另造网络端点 | **8项BLOCKED** |

真实观察时间与本地入库时间来自本次实际运行，ISO UTC原值保留在机器证据；没有用它们回填过去的首次可得时间。腾讯映射沿用既有 `available_at=observed_at` 的保守实际采集可见性，`ingested_at` 为实际验证后入库时刻；今天取得的10月14–15日记录不能回放到当时。指数缺失的event_time/available_at/quality_status/adjustment_method保持UNKNOWN，没有填15:00或accepted。

源码字段/单位的完整静态清单在机器证据 `source_inventory`；`actual_fields`仅表示本次确实取得的SDK/适配后字段。没有取得帧的来源不把静态字段列表写成实际响应事实。覆盖率分母与缺失日期列表没有独立日历时均为null；未宣称550/550或2/2覆盖率100%。

## 3. 复用、调研与授权边界

复用现有公共指数/乐咕worker、CFFEX客户端/解析器、东方财富/腾讯DailyHistoryClient、DailyHistoryIngestor、EvidenceStore、HealthTransport、SQLiteMarketDataRepository和测试环境ScratchWriter。没有新建正式表、修改迁移/批次语义、复制算法或引入依赖。新脚本只编排这些端口，附加每端点一次发送、响应大小/散列/HTTP证据及worker期限。

实际读取安装包 AKShare1.19.1 的直接相关源码/单位转换/失败路径；固定文件SHA256：

| 本地包路径 | SHA256 / 核验 |
| --- | --- |
| `akshare/index/index_stock_zh.py`，实际 `stock_zh_index_daily/get_tx_start_year` | `fc217076e71ce6a4a70f8344de0f4c0332b4b4cfa77a71e2ca3bc8a428e39d0a` |
| `akshare/stock_feature/stock_hist_tx.py` | `aa9199665d356ba3a054297004e349d3926fa83026abfd2d50c4b7f832226d84` |
| `akshare/stock_feature/stock_market_legu.py` | `ea07f4f3ac82c1cf2febf93f23b20d34ea5a3f45f44e82f888e667af0c25323e` |
| `akshare-1.19.1.dist-info/licenses/LICENSE` | MIT，`d1c84fbaccd5fdbc75cd12ab9a05f4f791d89ee266569bc976c8b0befafc2d65` |

SDK腾讯存在coerce、去重及非day键fallback分支，既有DataFrame边界无法证明原始调整键/去重前冲突；不把本轮成功记为这些问题已认证。新浪/乐咕SDK也有类型转换/表格清洗；核心仍逐条检查消费到的记录。采用决定为**复用既有适配/批次与诊断，拒绝引入新下载框架或容忍缺失阈值**；供应商原始语义、授权及历史缺口延后独立认证。

软件MIT不证明供应商数据权利。本轮有界读取[新浪数据中心](https://finance.sina.com.cn/data/)，该页面不足以证明本端点的研究/自动采集/存储/公开展示/商业/再分发许可；中金所官网文档抓取超时、乐咕首页文档抓取403，也不形成授权证据。以上文档访问与本机受限行情请求分列；不能用浏览服务的403/超时替代本机行情HTTP结论。腾讯、东方财富具体数据许可未核实。各用途统一保留UNKNOWN，不作法律授权结论，不在本任务对外发布行情。

## 4. 当前诊断与真实性边界

- 指数趋势、117个已结束聚合周、波浪候选及价格代理可计算，但均 `TIME_UNCERTIFIED / L1_OBSERVATION`；周分母未知、不是117个完整认证周。
- 腾讯样本仅2条，实际截止10-15；针对请求分析日10-19，核心主状态STALE，另有历史不足、日历/来源/授权/时点未认证等原因，均L1，未获研究用途。
- 完整恐贪 `calculated=false`、score/percentile=null，价格代理独立存在。主状态沿用核心的SOURCE_UNAVAILABLE优先序，reasons仍保留FACTOR_MISSING/UNIVERSE_UNKNOWN，不自行改写主状态。
- 宽度/CFFEX/综合均BLOCKED。综合coverage分母3表示三类证据，不是交易日或全A证券数。
- 只消费 `Diagnostic.to_dict()`，不另算L1/L2/L3、不签发Receipt，不调用strategy_admission伪造审批；所有live_trading=false。源接通PASS不会改变认证矩阵的研究BLOCKED。

## 5. 验证与后续

相关离线19项通过，包含默认禁网、TLS/重复端点/超限响应、Schema序列化、未知/坏数据/历史as_of、原始CFFEX隔离与完整恐贪空值。曾在自检中发现旧price_frame会覆盖显式行身份，新证据桥仅对缺列应用批次元数据，并用object帧保留原始标量交核心校验；未修改共享函数或降低断言。完整离线、依赖及diff最终结果由任务记录追加；新代码哈希保存在机器证据中。

真实来源认证整体仍BLOCKED；核心独立H、真实全A与历史证券状态/日历、供应商许可、浏览器/手机UI和样本外均未通过。本任务没有部署/AWS/生产/交易账户操作。下一步清单及最小输入见交接文档；修复TLS或取得数据授权后另行授权定向验收，本轮预算不重试。

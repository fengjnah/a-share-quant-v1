# 时间可见性、结果复现与本地发布契约

本文件为待审设计，不改变[现有数据契约](../DATA_CONTRACT.md)或核心准入规则。表名见[字典](DATA_DICTIONARY.md)，实际实现状态见[矩阵](M0_M5_PERSISTENCE_MATRIX.md)。

## 1. 六类时间不能互换

| 字段 | 定义与限制 |
| --- | --- |
| business_date / trade_date / analysis_date | 上海业务日；行情所属日、分析请求日与实际latest_date分别展示；无认证日历不猜最近交易日 |
| event_time | 行情收盘事实或参考数据公告事件；预先公布日历的事件可以早于未来session_date，不能强制改成未来收盘 |
| available_at | 该版本按既有规则最早可合法使用时刻；没有来源/时间依据即NULL并阻断严格消费，绝不以文件mtime补造 |
| observed_at | 实际取得/观察源或原始响应时刻；旧DailyBar没有此字段，桥接仍NULL；不能取ingested代替 |
| ingested_at | 实际校验入库/归档时刻；与业务日期分开；旧JSON缺失不补当前或observed |
| as_of | 输入数据选择的共同知识截止，不是生成时间；所有严格输入必须在截止前实际可见 |
| generated_at / consumed_at | 结果实际算完、下游实际读入的时钟，不能倒填为历史as_of；结果在线最早可消费不早于生成 |

TS一律规范UTC微秒再比较，业务日由显式市场时区换算。时点缺失可以保存观察状态，但不能声称已做历史回放/正式开闸。known zero与unknown分开；数据存在、结构accepted、来源认证、许可、严格可见、L2/L3是独立条件。

## 2. 一致快照与版本选择

拟SnapshotRepository接受：`scope, analysis_date, as_of, mode, required_datasets, selection_policy_version, explicit_source_versions`，返回封存manifest或明确BLOCKED原因。

1. 固定选择政策和所需角色，包括价格历史窗口、历史池、日历、来源/时间/授权收据。源选择显式，不按“哪个有数据”自动fallback。
2. 在同一只读事务中取得候选行及元数据；每一条价格/参考/市场事实单独验证业务日期/口径及`event_time, available_at, ingested_at <= as_of`。需要observed的核心也要求已知且≤as_of。日历公告事件不是交易日OHLC事件，按其领域规则检查。
3. 同一business key/source取截止前可见链最新版本；最新可见quarantined/FAIL会阻断，不能退回较早PASS。源内多根、缺前驱、重复日、不合法数值拒绝；其他来源冲突单列EVIDENCE_CONFLICT，不取平均或静默drop。
4. 认证收据也须在截止前可见、符合范围、未过期/撤销。A17封存当时选择的质量决定与收据ID/hash，不能重放时改查“最新决定”。今天的审核不自动成为历史当天的许可事实。用于当前研究的证据回顾与历史真实可用性分别标注。
5. 宽度/额/池必须同一业务日和兼容定义；eligible池、停牌/缺失分区、全A金额单位与历史版本全部可追。过去窗口的每一天也要逐日匹配，不能只验证当日聚合。
6. 外部文件先校验内容hash/范围/单位/最大尺寸并读取到固定内容地址；SQL封存前再次核对hash。目录无文件或文件变化阻断；不能把跨文件读当SQLite事务自动隔离。
7. manifest保存每条data_version_id、expected hash、角色/序号和政策。构建父及全部子行单事务提交，内容hash不含created_at等运行时字段；空/缺数据可封存BLOCKED结果，必需角色缺失原因不能被0项清单隐去。

manifest日期规则按角色定义：当日聚合必须等于analysis_date；滚动价格窗口允许≤analysis_date；已完成周排除当前周并使用可见日历；公告/有效期参考按valid_on及可见版本，不将未来范围日历当未来行情。

反例：指数D日、宽度D−1日、某个D+1才下载的ST状态，虽然现在都存在，不能叫D日同期快照。拒绝并保存三种不同原因；不会通过把日期标签统一改成D解决。

## 3. 修订、幂等、失效与删除

- 现有write_many的重复run/版本仍抛DuplicateRecordError；不修改为INSERT OR REPLACE。新适配可先按完整业务键/版本/hash确认已提交，返回外层DUPLICATE回执；hash不一致必须冲突，不重复发网请求。
- 每次真实尝试独立attempt，失败也可记，没有成功run不能伪造FK。现有EvidenceStore文件与SQL不具有分布式原子性；以manifest/质量决定表达部分失败，并在恢复时只补可核实的证据索引，不重新写行情冒充首次。
- 同一来源同一对象修订必须有前驱、理由、严格推进的知识时间；同payload当前重观测留attempt/evidence，不强造市场修订。修订为较旧相同价格但理由/时间不同仍是新版本，不能按任意历史payload相同误判重复。
- 业务有效期半开；状态源未完整覆盖的段保持UNKNOWN。不存在通用“把上一条effective_to UPDATE为今天”的操作。
- 失效/撤销写新质量或receipt事件，历史as_of仍选当时可见版本。分析更正新run并replay_of/依赖，不覆盖原候选/止损/收益。发布回滚追加回执，不改旧manifest。
- 默认不硬删除审计事实、版本、被引用证据。保留策略先检查法务/授权和引用，再另立归档任务；必须移除载荷时保留带原因/时点/哈希的缺失墓碑并阻断受影响重放。当前没有自动清理任务。

## 4. 分析运行与模块结果

### 4.1 保存与读取

输入快照ID、实际code_sha、规则/参数/序列化版本和实际运行环境指纹在开始时冻结；源码脏工作树不得仅填HEAD冒充执行字节，应拒绝正式封存或另记build tree并保持非正式状态。环境只记录Python/关键依赖版本、锁文件hash、时区与数值政策，禁止全量环境变量/secret。run在计算结束后连同模块结果完整提交；失败保存FAILED/BLOCKED及输入引用，不把异常改空SUCCESS。

外部大artifact先原子写临时文件、校验内容地址，再事务登记和引用；SQL失败的未引用文件进入待核对孤儿清单，不由本轮删除。result_sha覆盖固定输出（排除实际generated_at等非确定性运行字段），完整输出保留独立artifact哈希；JSON float/Decimal/NULL规范按contract_version固定。不能用核心clean把非法输入转NULL来绕过核心校验。

读取API：`get_run(run_id)`取原封存对象；`find_runs(module,date,as_of,scope)`只列明确版本，不默认最新当历史。重放API：`replay(run_id, frozen_build)`读取精确输入与规则，生成新run；比较稳定计算payload/hash及每项差异，实际generated_at不同不回写旧记录。依赖/信任收据变化必须另记，不声称hash相同就认证相同。

### 4.2 M3

保留全部8项：daily_trend/weekly_structure/wave/market_breadth/fear_greed/price_proxy/cffex_position/environment；以实际契约indicator名为准，保存前检验全套对应。完整Diagnostic含source的各认证Receipt、coverage分母与引用、values、calculated、所有原因与allowed_uses；页面去values下载不能作为保存输入。因子历史的raw/normalized/weight/contribution逐日关联确切输入，不重复实现六因子算法。

M3研究结果存储只保存核心输出，不签发收据。`strategy_admission`另行原样调用并保存，不以admission enum或数据库存在性取代review。现有收据检查绑定implementation_sha、rules_version、data_snapshot_id、approved_at、执行约束和样本外证据；任何不足仍strategy_allowed=false/live_trading=false。

### 4.3 M4

拟`ValidatedMarketSnapshot`适配端口只接受明确M3 run，校验：module= M3、environment存在、业务日一致、同共同输入cutoff或批准且公开的滞后政策、输入/结果hash、上游生成与实际consumed_at、scope=相应市场、来源时点/新鲜度、固定核心strategy_admission结果及其收据。优先同一as_of，拒绝看似同期的旧结果；政策若允许滞后，UI同时展示两cutoff和滞后原因，不能改日期标签。

as_of是数据知识截止，generated/consumed是现实处理时钟：可以在盘后用同一cutoff顺序算M3再算M4，下游生成不早于上游消费；这不表示结果在cutoff前已经生成。任何在线/纸面计划的signal_available_at必须不早于自身/依赖实际生成和输入可用时刻，最早执行仍受现有下一可交易会话规则限制。

市场缺失、过期、证据冲突、strategy_allowed=false或收据未核验时，仍保存每个M2研究评估及风险，但候选/开仓准入关闭。严格/趋势模式、评分/止损复用现有定义，phase不从独立形态推断。列表/详情/风险只读同一run的结果；不能每次点击另取“最新”M2或M3。1%只约束有效研究预算，不补权益或可执行股数。

### 4.4 M5

M5尚未实现，以下为执行前验收约束。一次回测保存输入全集manifest是为了可复现，**不授权执行器直接读取所有未来行**。每个虚拟decision time都经同一严格选择器、历史身份/日历/状态/因子版本过滤；当前下载的历史数据若ingested晚于该time，在保守契约下不可用，不能宣称已完成严谨回测。

实际generated_at是今天跑回测的时钟，虚拟signal_at/decision time是模拟时钟，二者不相等且不得倒填。不能把今天生成的持久M3结果当作历史已知结果：要么该原结果确实在虚拟时点前生成且输入可见，要么在回测中用冻结规则对虚拟时点可见输入重新计算，并明确标注counterfactual replay；仍不能伪造历史源许可、时点或L3审查收据。历史源证据不够就BLOCKED，不用“重算”消除缺失。

未来执行器必须校验下一认证会话/停牌/涨跌停/T+1/交易单位/跳空、费用滑点、公司行动；信号和成交分离。订单拒绝不产生虚假fill；现金/持仓事件与成交逐条对账，权益按该时点可见价格估值，指标在明确split上重算。无样本外记录就标未验证，不发布假收益。

## 5. 最小本地→EC2结果发布协议：research-publication-v1

**P0只传已审结果与显示资源，不传SQLite、WAL、原始响应、原始排名、未授权行情历史、账户权益或凭据。** 现有deploy脚本只处理代码，不能当本协议实现；本阶段不修改EC2或现有/quant/。后续先实现离线打包/验证，再单独批准接收与viewer接线。

### 5.1 manifest字段契约

`manifest.json`是UTF-8规范JSON（固定字段排序/数字/换行政策，无NaN、重复键和动态时间占位）。内容字段如下；自身sha/publication_id不参与自身哈希，传输外层pin期望摘要。

| 字段 | 类型 / NULL | 验证 |
| --- | --- | --- |
| protocol_version | string! | 精确research-publication-v1，未知拒绝 |
| analysis_date, as_of, generated_at | date!/TS!/TS! | 日期/cutoff/真实生成时间，显示最新行情和来源截止另列 |
| producer_code_sha, renderer_contract | SHA40!/string! | 实际构建证明；接收端允许renderer协议范围，不能把GitHub最新SHA当实际生产SHA |
| target_key, privacy_policy_version | string! | 已批准私有目标及字段白名单版本，无密码 |
| input_versions | array! | `{data_version_id,sha256,dataset_key,business_date,available_at,ingested_at}`；后两TS可NULL但必须保留阻断标志；仅必要摘要，不带原始行 |
| input_checks | array! | 快照选定的assessment/receipt ID、hash、role、decision、issued/available时点及无秘密authority引用；与A17封存集合一致，未知不填VERIFIED |
| runs | array! | 每项run_id/module/date/as_of/generated_at/code_sha/rules_version/environment_sha256/input_snapshot_id/result_sha256/status/quality/blocking_reasons及上游run/hash |
| admission_summary | object! | 原研究/策略许可、live_trading=false及原因；禁止接收端自行补认证 |
| display_authorization_refs | array! | 各公开字段/范围/目标的展示或再分发许可证据；研究许可不能自动视为展示许可 |
| items | array! | 完整有序`relative_path,sha256,bytes,media_type,artifact_role,run_id?`，与A14一致 |
| item_count, total_bytes | integer! | 正确总和、无负数、资源限额符合目标 |

清楚标注的示意：`{protocol_version:"research-publication-v1",analysis_date:"2026-10-16",as_of:C,generated_at:G,producer_code_sha:S,renderer_contract:"DEMO",target_key:"DEMO",privacy_policy_version:"demo-v1",input_versions:[],input_checks:[],runs:[],admission_summary:{strategy_allowed:false,live_trading:false,blocking_reasons:["SYNTHETIC"]},display_authorization_refs:[],items:[],item_count:0,total_bytes:0}`。仅结构说明，不是获准发送的包。

### 5.2 构建、传输、验证、激活

1. 从指定run_id导出，不用最新查询。仅白名单字段：日期、来源、研究状态、获准显示的数值、完整阻断原因和版本。未获展示许可的值不导出；允许展示的BLOCKED元数据仍保留限制，不能消失成正常0。
2. 本地以创建专用批次目录固化manifest和文件，逐文件hash、schema、隐私/许可/时点检查，通过后登记BUILT。P0建议≤100文件、≤5MiB总量、单JSON≤2MiB；这是工程初始上限、待实际页面验收，不是已压测容量。大图历史按需减量，不能为通过限额删除必要血缘。
3. 复用已授权SSH、固定host key与受限上传账号传至`incoming/<publication_id>`；不增加公网端口，不用公开存储桶。包名/相对路径验证，禁止`..`、绝对路径、symlink、压缩炸弹/多余文件；P0可传普通目录避免危险自动解压。
4. 接收方验证期望manifest摘要、target、协议、所有文件/数目/大小、run/输入依赖、字段许可、原始门禁、无秘密、可接受renderer版本。内容hash只证明完整性，不证明来源认证；上传者身份来自既有SSH认证与服务端写权限，不能只凭包自报issuer可信。收据须符合另经批准的信任根/授权范围；目标无可信收据验证能力或对应批准索引时保持BLOCKED，只能显示获准的状态元数据，不能信任包自带validated布尔值。
5. VERIFIED后才以同文件系统临时指针→原子rename激活数据current；保留旧发布目录。Nginx/Streamlit代码current与data current分开；viewer先固定一个publication_id再读其全部文件，不每张卡片独立取latest。HTML/文本转义，JSON不能注入任意HTML或脚本。
6. 验证失败记录FAILED和脱敏错误，保持旧current；成功回传publication_id/manifest_sha/实际receiver_code_sha/验证及激活时间，登记ACTIVATED；断网超时是状态UNKNOWN，发送端先查目标回执再重试，不能宣称成功或重复覆盖。
7. 同ID同hash重发幂等返回既有回执；同ID不同hash拒绝。回滚只指向已VERIFIED旧包并记录ROLLED_BACK，不恢复/覆盖云端数据库。所有目录保留策略后续批准，本轮不清理。

现有HTTPS Basic Auth继续由原入口保护；协议不会自动开放公开数据或新增服务。P0先做独立只读静态viewer/现有viewer适配的本地验证，是否接入现有`/quant/`必须另验认证、路由和资源；设计不等于已部署。

### 5.3 展示必须能回答

当前publication_id/manifest hash、分析日、每数据集实际截止、as_of/生成/激活时间、生产与接收代码版本、数据缺失/过期/来源失败/准入原因；指定历史批次必须只读该批次。没有已验证包时展示“尚无已验证发布”，不能返回临时Demo库或旧缓存伪装当前结果。

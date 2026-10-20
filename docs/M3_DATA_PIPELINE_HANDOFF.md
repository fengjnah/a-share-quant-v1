# M3 数据接口、核心和页面交接

TASK-M3-DATA-PIPELINE-001，基线 `94cdd487bfd4633ecc2f002aad014f98dec961a5`。页面任务 [TASK-M3-REMODEL-002 / #38](https://github.com/fengjnah/a-share-quant-v1/issues/38) 独立维护页面；本任务没有修改其文件。核心独立H [#37](https://github.com/fengjnah/a-share-quant-v1/issues/37) 未完成，以下为**候选兼容提案**，不能冒充已获稳定依赖批准。

## 1. 唯一计算/准入链

```text
显式采集worker → 既有vendor adapters / ingest / 本机证据
                 ↓ 一源一个明确选定的观察/完整版本，不自动选优
ai_trade.m3_data_pipeline.build_bundle
                 ↓ 只调用现有market_analysis_core各diagnostic
核心Diagnostic.to_dict()原样 → 本地pipeline-bundle.json
                 ↓ 页面读取，不发请求、不改status/admission/allowed_uses
TASK-M3-REMODEL-002：总览、详情、UNKNOWN及阻断原因
```

中间层只补“缺列”的实际批次元数据，不覆盖显式行source/symbol/时间/质量。旧快照缺ingested/event/available/quality仍缺；没有全A池、日历或Receipt时不造值。股票沿用既有批次/每行版本/SQLite，原始CFFEX CSV只留传输事实；没有认证日历/完整排名版本时传入核心的是无合格记录，不能自行生成available_at。

无第三套状态或准入算法：接口验收PASS/FAIL/BLOCKED/NOT RUN是传输/解析证据，`certification_status=BLOCKED`表示本任务未出真实认证；指标的状态/级别/许可始终取核心结果。不得用任意一个来源PASS作为整个M3成功。

## 2. 候选调用与数据位置

`ai_trade.m3_data_pipeline.build_bundle(observations, *, analysis_date, as_of, mode='research', run_id)` 是纯计算/证据组合入口；不联网、不写库、不刷新、不调用L3审批。observations按来源ID传一份已明确选定的观察。若本地有多次采集，应由权威读端按as_of/版本链选择；不要先从多个来源挑“最新成功”混为同一快照。

| 来源键 | 输入形状 / 前置来源 | 保留限制 |
| --- | --- | --- |
| sina_index | 既有公共worker观察：source/symbol/trade_date/prices/实际observed及可选ingested/available | prices最多550行是客户端留样，不证明日历完整；未知质量不默认accepted |
| eastmoney_stock / tencent_stock | 已有IngestionResult成功批次的records、实际observed、batch_id、source/date | 逐行source_version和accepted来自实际映射/校验；不是源/实体/时间真实性认证 |
| legu_breadth | 单日统计date/breadth及实际元数据 | 只有5个计数不能认证全A范围；不把最新快照倒填每天 |
| cffex_rankings | 既有collect_cffex原始观察 | 展示可用性/解析事实；本任务不把它伪装成具备日历、双时间和版本链的排名记录 |

输出外层schema_version=`m3-pipeline-evidence-v1`；包含run_id/baseline_sha、core_contract_version=`m3-core-diagnostic-v1`、calculation_version=`m3-core-rules-v1`、request、core_review（PENDING，绑定#37/head）、requirements和diagnostics。`diagnostics[key]`为未经改写的核心序列化对象，原JSON Schema可单独校验。指数/宽度/完整恐贪/CFFEX/综合共8项；个股仅在实际有批次时以 `tencent_stock:daily_trend` 等名称附加，避免混标。

`pipeline-bundle.json`含本地派生历史值，不能直接作为公开分发物。`summary.json`/仓库脱敏证据剔除全部values及原始价格/CSV/SDK帧，只用于审计报告，**不是可替代Diagnostic的页面值对象**。页面的传输状态详情可读取同一run的source result元数据；不会自动读取生产库或任意外部JSON路径。

## 3. 页面字段映射（不修改核心）

| 页面需要 | 唯一输入字段 | 显示/兼容约束 |
| --- | --- | --- |
| 单项主状态/级别 | diagnostic.status / admission / calculated | 不由数值非空推导“可研究”；主状态优先序不隐藏reasons |
| 数据实际日期 | request.analysis_date / data_latest_date | 保留分析日与实际截止差异；未收到为UNKNOWN，不标休市 |
| 来源/源版本/血缘 | source.source / source_version / lineage_refs；data_snapshot_id | 不把来源标签或散列当认证证明 |
| 时间 | times；source.time_verification；request.as_of | JSON null显示UNKNOWN，不填采集时刻为历史首发 |
| 样本/覆盖 | coverage.valid_samples/expected_samples/ratio/denominator/denominator_refs/missing_dates | 预期分母null时百分比UNKNOWN；综合分母3是证据类型 |
| 缺失/补救 | missing_fields；reasons[].code/detail/next_action/blocks | 并列保留多个原因，不只显示“数据不足” |
| 值及用途 | values；allowed_uses | INVALID_DATA/BLOCKED不显示可交易值；六因子score=null不顶替价格代理；live_trading恒false |
| HTTP/解析可用性 | 同run sources[].status/http_trace/parse_status/returned_rows | PASS只描述这次接口观察，HTTP/条数未知不能显示0或200 |
| 核心稳定性 | envelope.core_review | 独立H未完单列说明；不得用界面通过解锁稳定契约 |

当前提案不让页面同时改本模块/核心契约。若页面需要额外错误类型、持久化版本选择或真实Receipt输入，先共同明确新增兼容边界，另立任务；不在两个会话并发修改market_analysis_core、contract、Schema或页面数据模块。

## 4. 后续任务清单（建议，未自动启动）

| 顺序 / 建议负责人 | 最小输入与工作 | 输出/升级门禁 |
| --- | --- | --- |
| 1：独立H，核心#37 | 冻结d60fa880完整SHA及实际PR/main tree；新独立会话按任务要求覆盖R1–R4/H1/H2/M1/A–E | 绑定SHA的正式结论；本数据实施会话不自审，不因已合并跳过 |
| 2：来源/环境负责人 | 三次SSL失败的类型/时间/端点证据；只读核对受信任CA/代理/供应商条件，不永久改代理或关闭TLS | 明确根因与单独授权的小范围复验；不得自动消耗更多请求 |
| 3：历史参考数据负责人 | 已有SQLiteSecurityMaster/TradingCalendar/RankingCalendar端口，真实历史身份/ST/停牌/退市、日历来源与授权材料 | 有界来源调研、真实样本/历史覆盖/双时间证明及独立H；无证据维持UNKNOWN |
| 4：全A统计负责人 | 逐日历史池及上市/退市/停牌分区，完整统计口径，全A成交额单位/历史时间 | 同日可见分母及6因子输入；不能以指数/个股额或当前池补齐 |
| 5：CFFEX负责人 | 权威CFFEX会话、发布时间、会员scope、完整版本链和源/使用许可 | 经既有time_fence/ingest/read端口形成真实记录，质量显式决定；不可用则direction=null |
| 6：页面任务#38 | 核心正式契约与本提案字段映射、同run实际传输元数据；明确共享文件所有权 | 只消费核心；实际桌面/窄屏E2E另做，不能冒充手机或来源认证 |
| 7：独立H，数据证据桥 | 本PR最终SHA、离线/真实受限日志及机器摘要；检查预算、时间/未知/身份、原始证据与公开摘要分离 | 正式独立审查后由用户决定是否合并；不能由本会话普通自检替代 |
| 8：策略/执行负责人 | 冻结策略实现/数据快照、真实授权、执行约束、样本外验证、独立批准时间 | 按核心strategy_admission分别审核；本任务不执行或批准L3/实盘 |

未变更正式TASK_METRICS权重/验收积分。机器证据的structured_feedback记录本次实际来源状态和阻断，不给未知项加分；共享看板/页面正式接线应在各自负责人确认后处理。无自动化、定时采集、提醒、合并或部署。

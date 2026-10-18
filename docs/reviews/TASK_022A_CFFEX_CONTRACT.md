# TASK-022A-H：CFFEX 设计/离线端口与未实现边界

适用代码：`cffex_rankings*.py`，适配器版本 `task-022a-h-v2`。这是对正式数据/接口契约的局部细化，不修改 SQLite Schema、交易策略或其他行情口径。

## 请求、字段和异常

`CffexRankingsRequest` 必须显式 CFFEX、IF/IH/IC/IM、有效 `YYYY-MM-DD`；只有 `https://www.cffex.com.cn/sj/ccpm/YYYYMM/DD/VAR_1.csv` 一个目标。客户端采用 Requests 正常代理解析和证书验证，不设置永久代理，不自动降级 HTTP、不跟重定向/重试；连接/读取各使用显式有限 timeout，默认 20 秒，允许 (0,120] 秒；这是分阶段超时，不是精确端到端总耗时 SLA。响应有 2MB 字节上限并释放连接。非 200、HTML/JSON Content-Type、超长、截断流分别报错，不输出正文或凭据。

解析支持严格 GBK 和显式 UTF-8 BOM。具名两行表头、旧类别单行表头及 mixed 中的段切换均须完整匹配；不能凭字段数猜表头。每个具名合约排名必须恰好 1—20，无重复排名/同侧会员；旧类别必须各一条“期货公司/非期货公司”。混合文件两部分的合约范围一致。日期、品种、合约 YYMM 月份、列数、整数、数量非负及空值关系均校验。空行可忽略，单字段垃圾/坏编码/截断/重复段头不能忽略。

`RankingRow.side=volume` 使用 `volume`、`volume_change`；其 open_interest/change 为 null、known=false。long/short 使用持仓数量与变化，volume 字段为 null。保留供应商整数计数，不做 A 股“手转股”或额外乘数。数量 0 是已知 0；空值是未知，不补零。裸会员名保持 UNKNOWN；(代客)/(自营) 分开，旧类别不生成具体会员身份。

`IngestionOutcome`：success / duplicate_payload / unavailable / no_session / network_error / response_error / schema_error / validation_error / calendar_error / version_error。仅 success 带新记录。404 或含站点“页面未找到”的正文默认 **unavailable：原因不确定**；只有可见的 CFFEX 日历明确 closed 才 no_session。开市日的 404 也不能证明一定未发布，不能排除路径/服务故障，所以本版不自动生成 unpublished。HTML 首页/空响应/源格式漂移不当作零行成功。http_status 只在确实由客户端暴露时记录；裸字节解析不知道 HTTP 状态。

## CFFEX 日历与时间

已调查 `SQLiteTradingCalendar`、`CalendarDay`、reference validation 与 Schema v2：当前只支持 SH/SZ/BJ、日期级状态，没有 CFFEX 或开闭市时刻。**没有可靠 CFFEX 日历实现或真实来源验收**，本轮不扩正式表结构、不复制 SH 日历。

新增只读 `RankingCalendar.get_day(exchange, session_date, as_of)` 端口，返回 `RankingSessionDay`：CFFEX、日期、显式开/休市布尔、真实会话开/收盘时刻（closed 必须为 null）、available_at/ingested_at、来源、证据引用和 evidence_kind。端口本身不是数据源；返回的来源声明不构成系统认证。日历时间必须在采集截止时已可见，不能使用未来修订。合成日历会使记录标 synthetic，只用于离线研究，严格回测/纸面路径拒绝。

事件时间为该交易会话的收盘，不能是抓取时刻。明确记录 observed_at 与 ingested_at，要求 event <= observed <= ingested。真实 publication_time 若未知则保持 null，若传入则 event <= publication <= observed，不能把“约 16:30”写成精确历史首发证据。

available_at 为：交易日期之后，且不早于实际 ingested_at 的首个已知会话开盘。搜索从 `max(trade_date+1, ingested_at 的本地日期)` 起，最多查至起点+31天；每个可能合格的中间日期都必须有可见日历记录，未知/源错立即阻断。早于采集本地日的日期不可能容纳采集之后的开盘，跳过它们不代表断言其休市。晚到盘中数据保守等待下一会话开盘；没有 CFFEX 日历时返回 calendar_error，不生成可用于策略的记录。没有星期规则、节假日硬编码或从 OI=0 推断休市。

## 修订、幂等与实际读时过滤

payload_sha256 是**原始字节**哈希，source_version 为 `payload-sha256:<digest>`，run_id 是观察批次标识，三者不能替代登记账本。

本轮实现的是纯函数契约：

- `compare_revision(previous, candidate)`：同一交易所/品种/日期/来源；同载荷返回 duplicate_payload，不覆盖原可见时刻。不同内容必须显式 supersedes_version/revision_reason，观察/入库/可见时间不能倒退，可见截点严格推进，不能复用旧 run_id。
- `ingest(previous=...)`：调用方明确提供已确认前驱时比较；重复结果不返回一个“今天重写的旧版本”。没有 previous 时无法知道持久库是否已有相同载荷，**不声称实现幂等登记**。内容 A→B→A 不支持通过重复 digest 的版本键直接回滚，必须交给后续仓储契约审查，不自动择优。
- `select_visible_version(records, as_of, mode)`：调用方提供完整单根单后继链，缺父、分叉、重复版本等拒绝；实际执行 available_at<=as_of AND ingested_at<=as_of，再按当时可见的最新版本返回 ReferenceResult。携带 as_of、mode、快照摘要、definitions_version、warnings、lineage_refs。只读函数不是全库快照。
- `net_positions_at(records, as_of, mode, contract, scope)`：通过上述过滤再计算；直接 `net_positions(record, ...)` 也强制显式 as_of/mode 并校验可见性，不能无视时间字段。调用方若只提供不完整历史而隐瞒后继，纯端口无法发现，必须由未来权威仓储保证完整性。

**尚未实现** futures_rankings 正式物理表、持久版本/唯一约束、事务批次写入、跨进程幂等登记、run 审计账本、原始证据持久归档、断点/调度/生产采集器。SQLite v2 的现有表和迁移保持原样；DATA_CONTRACT 中的 futures_rankings 是领域契约，不能称为已经创建的表。也没有实现/接入 BacktestEngine、日报、选股或执行逻辑；本轮“读时过滤通过”只覆盖上述端口与离线反例，不是策略回测验收。

## 单合约净额

必须指定该记录内的合约，以及单一已知 MemberScope。只配对同一会员、同一范围、同一交易日、同一合约的 long/short；任一侧未知，net=null。旧类别不参与具名净额，UNKNOWN 与代客/自营不合并。输出带 contract、trade_date、expiry_month（仅合约 YYMM 标记，不是推断的实际到期日）、rollover_flag=null、B 级与完整 definition。OI=0 不证明换月，跨合约净额、换月连续序列和实际到期日规则均**未实现并拒绝默认汇总**。

## 合并与生产门禁

只有结构/离线样本与合成反例经过本轮验证。真实 CFFEX 日历/历史可得性、完整仓储版本链、数据授权 R04 与 HTTPS 生产网络尚未验收；不能凭测试绿灯接入正式策略、自动采集或部署。旧 HTTP 样本可以离线重放，不代表今天 HTTPS 可达，也不构成商业/再分发授权。下一步先完成独立 H 复核和这些前置契约，再另立采集/持久化任务。

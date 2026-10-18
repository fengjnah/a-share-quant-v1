# TASK-008B：腾讯备用行情源生产适用性审查

检查日期：2026-10-18（Asia/Shanghai）。工作树 `F:\codex-agnes\AI-trade-main-demo`，分支 `codex/task-local-reconcile-001`。

## 执行纪律遵守

- 只读审查，未修改业务代码、东方财富/腾讯适配器、数据库 schema 或生产配置。
- 本任务**未发送任何真实行情 GET**（`network_requests_sent_this_task=0`）；未创建生产数据库。
- 未访问 GitHub、未创建/合并 PR、未提交代码。
- 保留 TASK-008 工作区现场（含未跟踪与已修改文件），未 reset/clean。

## 环境与离线检查（真实执行）

| 命令 | 结果 |
| --- | --- |
| `.\.venv\Scripts\python.exe -m pytest -q` | `358 passed, 1 skipped in 15.99s`（跳过为未启用开关的东财实时手工测试） |
| `.\.venv\Scripts\python.exe -m pip check` | `No broken requirements found.` |
| `git diff --check` | 退出码 0 |

环境：Python 3.12.14、AKShare 1.19.1、requests 2.34.2、urllib3 2.8.0、certifi 2026.7.22。

## 官方授权来源可访问性

探测（非行情端点，仅判断条款页是否存在）：

| 目标 | 可达 |
| --- | --- |
| `gu.qq.com` 首页 | 可达（200） |
| `proxy.finance.qq.com`（kline API 主机） | 可达（200） |
| `tencent.com` 条款索引（猜测 URL） | 404，未找到稳定官方条款页 |
| `gu.qq.com/news` | 403 |

**结论：未找到腾讯官方数据再分发许可或 API 服务条款文本，按"未确认"处理，不自行认定已获授权。** 这是进入生产前必须补齐的首要证据。

## A. 数据授权

| 维度 | 结论 |
| --- | --- |
| 个人研究与本地历史存储 | 未确认 |
| 自动化采集 | 未确认 |
| 对外展示 | 未确认 |
| 商业使用 | 未确认 |
| 数据再分发 | 未确认 |

证据：无官方条款文本；接口本身（`proxy.finance.qq.com/.../newfqkline/get`）未附带许可声明。不得以"接口可达"推断获准商用或再分发。

## B. 长历史与分页（源码事实，非实测）

- **按年循环**：`stock_zh_a_hist_tx` 以 `range(range_start, range_end)` 逐年发一次 GET（每页 640 交易日）；跨多年度会发多次请求。这是源码可证实的事实，但**完整历史覆盖/逐页成功未在本任务实测**。
- **日期边界**：SDK 先用 `get_tx_start_year` 探测上市起始年并钳制 `start_date`；最终 `big_df[start_date:end_date]` 闭区间切片。
- **合并/去重/排序**：`pd.concat` → `drop_duplicates(ignore_index=True)` → 按日期 `sort_index` → 切片。停牌日若无记录会缺失，零成交量日可能保留，均无停牌标志列。
- **复权**：`day`/`hfqday`/`qfqday` 键，`adjust=""` 取 `day`。
- **异常处理缺失**：`stock_zh_a_hist_tx` 内**无 try/except、无重试、无退避**；任一年份页失败会中断整个调用。`timeout` 仅透传给单次 `requests.get`。
- **封 IP/速率限制**：无官方文档；本任务未实测。

## C. 数据质量与回测（区分系统能力 vs 数据源缺口）

- **单位**：源码确认主板 volume 已 ×100（手→股）、amount 已 ×10000（万元→元）；`tx_adapter` 不重复乘除——**无双重转换风险**。
- **停牌日/ST 历史**：接口均不提供；属**数据源缺口**，需配合其他来源或政策。
- **首次可得时间/修订/历史快照**：接口不提供；系统**无法审计某历史值是否事后被修订**。
- `available_at`/`ingested_at`/`as_of` 防未来函数：属**系统侧已有能力**——`get_bar` 全模式强制 `available_at<=as_of AND ingested_at<=as_of`，schema `CHECK(event_time<=available_at AND event_time<=ingested_at)`，`strict_backtest` 额外要求 `quality_status=accepted`。只要数据源提供了 bar，这些机制即可防止前视偏差；但它们**不能补齐数据源本身缺失的字段**。

## D. 架构适配（只读核对）

- 契约符合：`TxDailyClient` 暴露 `fetch/check_frame/map_frame`；`ingestor` 用 `getattr` 优先取客户端自带方法、东财默认兜底，东财路径字节等价（TASK-008 已验证，本任务复核）。
- 来源标识完整：`source_label()` = `akshare-tencent:stock_zh_a_hist_tx:task-008-v1+sdk-1.19.1`；每批次保留 `run_id`/证据目录。
- 未来双源校验：需按 `(instrument_id, trade_date, source)` 出对照报表与冲突裁决策略——本任务不实现。

## E. 生产接入结论（三选一）

**建议 2：需要补齐指定证据后再审查。**

依据：代码与架构已达标（离线测试通过、契约符合、无双重转换、防未来函数机制就位），且 TASK-008 已有一次 2 行成功 + SQLite 读回证据；但生产适用的关键外部证据缺失——**授权条款未确认、长历史覆盖未实测、封 IP 阈值未知、ST/停牌/首次可得时间字段缺失**。一次成功请求不足以支撑生产接入。

未解决问题：

1. 数据再分发/商用授权（首要阻断）。
2. 多年度按年分页的完整性与失败韧性（无重试 = 单页失败即中断）。
3. 停牌/ST 数据政策。
4. 首次可得时间与修订审计能力。

下一步验收标准（满足后方可进入正式适配器审查）：

1. 取得并归档官方腾讯数据条款/许可，或书面授权；否则明确商用/再分发禁用边界。
2. 一次有界多年度覆盖测试（如 3 年），逐年核对行数与日期连续性。
3. 定义停牌/ST 判定政策并映射到 `quality_status`。
4. 确认首次可得时间/修订政策，才能声称可审计历史快照。

## 证据分层说明

| 类型 | 内容 |
| --- | --- |
| 源码事实 | 按年分页、无重试、单位归一、去重/排序、复权键 |
| 已有测试证据 | 358 passed；TASK-008 单次 2 行成功 + SQLite 读回 2/2 |
| 外部文件证据 | `gu.qq.com`/`proxy.finance.qq.com` 可达；条款索引 404（未定位官方文本） |
| 未验证假设 | 长历史完整性、封 IP 阈值、授权范围、ST/停牌/首次可得时间字段 |


## TASK-009 集成时补记（2026-10-18）

这是本地历史记录的审查副本，原工作树文件保持原样。当前基线、实际代码修正、测试和证据限制以 [TASK-009 报告](IMPLEMENTATION_TASK_009.md) 为准。原报告中的 SDK 调用次数不能证明 HTTP GET 总数；SDK 存在起始日探测、多年度请求和调整键回落，timeout 不覆盖起始日探测。旧腾讯证据 manifest 的 provider/endpoint 曾误标东方财富，本任务只修正后续证据生成，不篡改旧文件。生产许可、原始口径、历史覆盖和 SDK 去重前冲突尚未验收；系统时点过滤不能补齐这些来源证据。历史测试数量保留为当时记录，不冒充本任务新执行结果。

# 数据源健康检查与调度入口

健康状态独立于生产准入；注册的东方财富仍是现有默认源，腾讯仍是候选。本入口必须显式选择一个 source，不会替另一源请求、重试或自动切源。新接口可通过 `HealthSource` 注册工厂、审核版本、HTTP 目标和日期列；新浪/网易/商业源未实现或默认注册。

## 默认离线的入口

以下使用本次实际解释器及工作树。合并后应改为采用新代码的项目目录/解释器；不要在旧工作树上误运行新模块。

```powershell
cd F:\codex-agnes\AI-trade-task-015
$env:PYTHONPATH = Join-Path (Get-Location) 'src'
$taskPython = 'F:\codex-agnes\AI-trade-main-demo\.venv\Scripts\python.exe'
& $taskPython -m ai_trade.market_data.health_cli --source eastmoney --audit-root .\artifacts\source-health
& $taskPython -m ai_trade.market_data.health_cli --source tencent --audit-root .\artifacts\source-health
& $taskPython -m ai_trade.market_data.health_cli --source tencent --audit-root .\artifacts\source-health --report-only
```

前两条只检查本地注册、接口和 SDK 版本，默认不执行 fetch。配置通过不能证明可连接、返回数据或健康；报告的行情状态仍未知。缺少 AKShare 1.19.1 时返回配置 unknown，而非网络失败。结果按独立 check_id 追加到指定 JSON 证据目录，使用现有 EvidenceStore 的独占目录/文件机制，不创建健康表或迁移主 Schema。报告命令不联网；若审计不完整或损坏，报 unknown 要求人工复核，不自动忽略坏记录。

入口使用项目既有 pandas/Requests 依赖及可选 AKShare；请采用已有 `[akshare]` 依赖安装方式，不需要新的服务或依赖组。本 TASK 使用现有虚拟环境，未安装或升级依赖。

| 参数 | 默认与边界 |
| --- | --- |
| `--source` | 必填，当前仅 eastmoney / tencent |
| `--check-type` | 默认 configuration_check；另有 connectivity_check / market_data_check |
| `--audit-root` | 必填，健康 JSON 目录；不读取 QUANT_DB_PATH |
| `--enable-network` | 默认 false；只有 market_data_check + 此开关才可能 fetch |
| `--max-requests` | 默认 0；真实检查必须显式给 1–3，按 HTTP Adapter 发送边界计数 |
| `--start-date / --end-date` | 显式历史日期，固定 600000.SH、不复权、最多 7 个日历日 |
| `--cadence` | daily / weekly / monthly 计划标签，默认 daily；不安装计划任务或自动执行计划动作 |

configuration 成功退出码 0；检查失败、unknown、not_run 返回 2；report-only 正常读取返回 0。退出码 0 的含义取决于 check_type，不能仅靠进程退出码认定行情源健康。

## 三层检查与证据

- `configuration_check`：只验证注册与审核版本，不建 SQLite、不联网。
- `connectivity_check`：当前没有另行批准的独立探针，明确返回 not_run；不会为这一层额外发送 DNS/TLS/HTTP 探针，也不把 TLS 成功当行情成功。
- `market_data_check`：显式启用后，经现有 DailyHistoryIngestor、源映射/校验、SQLite 仓储执行。只有已验证批次触发隔离临时 SQLite 初始化/写入，随后按 source、as_of 和 run_id 读回并检查完整性；不读取或修改生产库。

在健康检查专用、串行进程内，临时限制 Requests：仅允许审核域名/路径的 HTTPS GET，证书验证保持开启，禁止重定向，urllib3 重试为零；相同 URL 再次发送也会阻断。每次 SDK 内部 GET（包括腾讯起始日探测）都计入预算，并为遗漏 timeout 的请求设置本次 10 秒 I/O timeout。现有 Demo/业务适配器正常调用不受这些控制改变。超时不等于硬性总墙钟期限：OS DNS、依赖运行和本地 IO 仍有独立时延。

嵌套/并行健康上下文在同一进程内被阻断，埋点在异常后恢复。不要将真实健康检查嵌入同时联网的 Streamlit 进程；用独立子进程串行运行，外部调度器负责避免多个进程重叠。框架不启动并行检查，不自动改代理或切换网络路径。

`request_count` 是 Adapter 发送尝试数，**不是上游接收/处理的证明**。`request_state` 分别记录 not_attempted、send_attempt_observed、http_response_observed；DNS/TCP/TLS 等传输异常只记录脱敏类型链和保守的 sdk_fetch_transport 阶段，不仅凭异常类名推断根因。HTTP 状态未知保持 null。

未取得 DataFrame 时 dataframe_rows=null；0 仅表示实际取得零行帧。empty_data 还要求观察到 HTTP 200，否则为 unknown。HTTP 错误在 SDK 解析前记录，解析失败只有获得响应的证据时才标 parse_error；字段/日期/数值错误为 quality_error。DB 写入/读回单独记录，失败不会伪装为空行情；已提交后审计失败仍保留 committed 标记，不自动重试。

## 新鲜度与日历

默认没有已验收真实日历，所以 CLI 的 expected_data_date / is_stale 为 null。即使获得有效行情并读回成功，缺少新鲜度证据时整体也为 unknown，不归咎于行情源。配置成功不会清零连续行情失败次数。

服务 API 可接受 `CalendarExpectation`；只有有依据的已关闭交易日才能标 known。`calendar_expectation` 复用已注入的 SQLiteTradingCalendar 严格 as_of、有界查询，要求调用方确认真实来源验收及收盘截点，拒绝 synthetic 告警、缺失、源错误、未来日期或尚未正常收盘的当日；不按工作日推算交易日。日期级日历不支持特殊会话认证。日历已确认休市时可预期上一已知交易日，缺日历则保持未知。

## 交给外部调度器的计划

本 TASK 未安装 Windows 计划任务、Codex 自动化或 AWS 调度。

| 周期 | 建议外部动作 | 本框架实际提供 |
| --- | --- | --- |
| 交易日收盘后 | 先配置检查；有独立网络授权/预算/真实日历依据时再小样本验收 | 可调用上述 CLI；schedule_plan 输出未知/休市/交易日的计划元数据，不自动发请求 |
| 每周 | 运行离线契约测试，对人工保留的合法固定样本做跨源比较 | 可测试入口与纯离线 `compare_saved_records(left, right)`；只报缺失/字段差异，不填零、不选冲突胜者，不自动抓数据 |
| 每月 | 审查历史覆盖、许可、质量和来源证据 | monthly 审计计划；不自动下载历史、执行回测或宣称完整覆盖 |
| 非交易日/日历未知 | 已验证日历决定是否应有新数据；日历缺失需人工复核 | `expect_new_market_data` 为 false / null，不能因此把行情源写成失败或把缺日视作休市 |

`--cadence weekly/monthly` 输出的是计划，不会在应用中自动运行 pytest、读取行情快照或安装系统任务。外部调度负责人需显式串接离线命令/已保存样本；本任务的周/月计划不是已部署验收服务。

若未来人工批准一次真实检查，必须再明确股票/日期/源/总预算，并使用 market_data_check、--enable-network 和正预算；本任务没有执行该命令。腾讯的起始日探测及按年分页可能消耗多个 GET，预算不足返回 unknown/request_policy，不跳过计数或隐式追加预算。CLI 当前缺少真实日历配置，成功数据也不能冒充完整 freshness 成功。

审计摘要可经 `HealthResult.to_dict()`、`source_report()` 交给 Demo 只读展示；本轮没有新增页面自动检查或运行真实浏览器验收。详细实施与限制见 [TASK-015 报告](IMPLEMENTATION_TASK_015.md)。

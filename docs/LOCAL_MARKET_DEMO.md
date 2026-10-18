# 本地行情展示页（最小版）

健康检查采用独立、默认离线的 [TASK-015 入口](SOURCE_HEALTH_CHECKS.md)，不会在页面启动或 rerun 时自动执行。可只读展示其序列化报告；配置成功不代表真实行情健康。本轮没有改变 Demo 默认数据源、请求逻辑或生产数据库配置。

## 功能

- 使用现有 `AkshareDailyClient`（东方财富主源）与 `TxDailyClient`（腾讯备用候选，TASK-008A）通过同一 `DailyHistoryIngestor` 与 `SQLiteMarketDataRepository`。
- 默认表单预填 `600000`、`2026-10-14` 至 `2026-10-15`、不复权；这只是查询参数，不代表已查询数据。
- 只有用户点击“采集真实行情”才会发起请求。
- 展示实际采集状态、返回/入库行数、来源、观察时间、证据摘要、错误信息，以及从隔离 SQLite 数据库重新查询的行情表。
- 数据源默认仍为东方财富；腾讯选项为备用候选，页面明确标注“尚未通过生产适用性验收”。
- 不读取 `QUANT_DB_PATH`，不调用生产数据库路径，不会自动初始化 `local.sqlite3`。
- 每个 Streamlit 会话使用操作系统临时目录下独立的 `demo.sqlite3`；页面显示实际路径。

## Windows PowerShell 启动步骤

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[akshare,demo]"

# 只对当前 PowerShell 会话及其启动的 Streamlit 进程生效。
# 仅在网络策略允许且明确选择东方财富直连时使用；配置本身不保证请求成功。
$env:NO_PROXY = "push2his.eastmoney.com"

.\.venv\Scripts\python.exe -m streamlit run src/ai_trade/demo_app.py
```

浏览器打开 Streamlit 启动日志中显示的本地地址（通常为 `http://localhost:8501`）。

## 操作方法

1. 保持默认股票代码和日期，或输入支持的沪深 A 股代码。数据源默认“东方财富（主源）”；腾讯只能显式手动选择，失败不会自动切换。
2. 点击“采集真实行情”。这一步会进行真实网络请求。
3. 成功时，页面显示实际返回行数、入库行数、来源和 SQLite 读回数据。
4. 失败时，页面显示错误状态，不会用示例行情填充表格。若出现网络/TLS 错误，请保留错误信息，不要关闭 TLS 验证。
5. “清空本演示数据”用于切换到新的会话临时数据库；临时文件最终由操作系统清理机制处理。

## 安全与验收边界

- 此页面是本地开发演示，不是生产服务，不提供认证或多用户访问控制。
- 不创建、不读取生产数据库；临时数据在 Streamlit 会话中隔离。
- 不把数据库、响应快照、证据目录、日志或密钥提交到 Git。
- 成功展示仅证明该次请求及本次临时库读回成功，不证明完整历史覆盖、全部证券、持续可用性或策略盈利能力。
- 如果代理配置不允许直连该域名，请遵循组织网络策略；不要关闭 TLS 证书验证或擅自添加自动直连回退。
- 页面代理字段仅表示 Requests 配置推断，不证明实际 socket 路由。腾讯 SDK 会访问 `web.ifzq.gtimg.cn` 探测起始日、再访问 `proxy.finance.qq.com` 按年获取数据；一次点击/SDK 调用可能包含多次 HTTP GET，且起始日探测没有传入 timeout。Demo 不修改这些域名的系统代理。
- 腾讯 SDK 会去重，并在 `day` 缺失时选择 `hfqday/qfqday`；仅凭 SDK DataFrame 无法核验原始响应所选口径或去重前冲突。当前请求明确使用 `adjust=""`，但原始口径证据仍是生产使用阻断项，不能把该候选用于已验收的严格历史研究。
- TASK-009 只复用 TASK-008 的历史 2 行成功及只读 SQLite 核对，没有再次请求真实行情。当前集成测试是离线合成夹具和 Streamlit AppTest，不代表本轮真实 UI→网络→SQLite 通过。详见 [集成与治理报告](IMPLEMENTATION_TASK_009.md)。

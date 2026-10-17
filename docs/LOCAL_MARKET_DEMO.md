# 本地行情展示页（最小版）

## 功能

- 使用现有 `AkshareDailyClient`、`DailyHistoryIngestor`、`SQLiteMarketDataRepository`。
- 默认表单预填 `600000`、`2026-10-14` 至 `2026-10-15`、不复权；这只是查询参数，不代表已查询数据。
- 只有用户点击“采集真实行情”才会发起请求。
- 展示实际采集状态、返回/入库行数、来源、观察时间、证据摘要、错误信息，以及从隔离 SQLite 数据库重新查询的行情表。
- 不读取 `QUANT_DB_PATH`，不调用生产数据库路径，不会自动初始化 `local.sqlite3`。
- 每个 Streamlit 会话使用操作系统临时目录下独立的 `demo.sqlite3`；页面显示实际路径。

## Windows PowerShell 启动步骤

在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[akshare,demo]"

# 只对当前 PowerShell 会话及其启动的 Streamlit 进程生效。
# 这与此前真实验收成功的域名级 NO_PROXY 方式一致，不修改 Windows 永久代理。
$env:NO_PROXY = "push2his.eastmoney.com"

.\.venv\Scripts\python.exe -m streamlit run src/ai_trade/demo_app.py
```

浏览器打开 Streamlit 启动日志中显示的本地地址（通常为 `http://localhost:8501`）。

## 操作方法

1. 保持默认股票代码和日期，或输入支持的沪深 A 股代码。
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

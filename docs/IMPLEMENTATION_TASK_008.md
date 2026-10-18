# TASK-008：腾讯备用行情适配器接入与本地 Demo 展示

检查日期：2026-10-18（Asia/Shanghai）。工作树 `F:\codex-agnes\AI-trade-main-demo`，分支 `codex/task-local-reconcile-001`，基于 `origin/main=c65a318`。

## 一、本地项目与工作区检查

- Git 状态干净，仅含 005/006/008A 遗留的未跟踪文件；未 reset/clean/覆盖。
- 核对 TASK-008A 报告与 `docs/evidence/TASK_008A_AUDIT.json`：接口存在、单位（volume=股、amount=元，主板已 ×100/×10000）与"2 行成功"结论与本地源码一致。008A 的成功是**历史**结果，本次重新执行了独立真实请求。
- 现有 Demo 入口：`src/ai_trade/demo_app.py` → `AkshareDailyClient`（东方财富）→ `DailyHistoryIngestor` → `SQLiteMarketDataRepository`；数据源此前在 `DailyHistoryIngestor` 构造函数内**硬编码**为东方财富。

## 二、腾讯适配器实现

新增 `src/ai_trade/market_data/tx_adapter.py`（`TxDailyClient`），与东方财富适配器共用同一 `DailyHistoryClient` 协议，但独立实现：

- 通过已安装的 `ak.stock_zh_a_hist_tx`（AKShare 1.19.1）取数，URL 为 `https://proxy.finance.qq.com/.../newfqkline/get`，与东方财富完全独立。
- **不做任何重复单位转换**：SDK 已对主板把 volume 由手×100、amount 由万元×10000 归一为股/元，适配器只校验与映射，不二次乘除。
- 股票代码映射：`600000.SH → sh600000`、`000001.SZ → sz000001`；不复权 `adjust=""`。
- 暴露独立的 `check_frame`/`map_frame`，供 ingestor 按数据源路由（见下）。
- 未修改东方财富适配器 `akshare_adapter.py`，未引入自动故障转移。

`DailyHistoryIngestor` 的最小改动（非破坏性）：原来写死调用东方财富的 `check_frame`/`map_frame`。改为优先使用客户端自带的 `check_frame`/`map_frame`（若存在），否则回落到东方财富默认函数。东方财富客户端未提供这些方法，路径**字节等价于改动前**；腾讯客户端提供自己的方法，走独立 schema 门与行映射。

## 三、本地 Demo 修改

- `demo_app.py` 新增"行情数据源"选择控件：`东方财富（主源）`（默认）/ `腾讯（备用候选）`。默认仍为东方财富，未悄悄改默认行为。
- 选择腾讯时改用 `TxDailyClient`，其余调用链、隔离临时 SQLite、点击去重（`collect_click_id`）逻辑不变。
- 成功/失败各状态、请求与返回摘要、行情表、SQLite 验收摘要、来源说明分区显示；腾讯批次额外标注"尚未通过生产适用性验收"。

## 四、离线测试

- 新增 `tests/unit/test_tx_adapter.py`（7 项）：代码映射、qfq/未知后缀拒绝、正常映射、越界日期、缺列。
- 新增 Streamlit 离线用例 `test_demo_tencent_source_once_per_click_and_no_auto_request`（`tests/manual/test_streamlit_demo_offline.py`）：页面启动 0 次请求、点击 1 次、rerun 不重复、二次点击 1 次，且全程禁止外部网络（仅回环）。
- 全量离线套件：`358 passed, 1 skipped in 16.19s`（跳过项为未启用开关的实时东方财富手工测试）。`pip check`：无破损依赖。`git diff --check`：通过（仅 CRLF 规范化提示，退出码 0）。

## 五、真实请求（一次，受控）

通过项目正式 ingestor 调用链执行**一次**腾讯真实请求（600000.SH，2026-10-14~15，不复权）：

| 项 | 实际结果 |
| --- | --- |
| 状态 | `success` |
| 返回行数 | 2（未取 DataFrame 时为 null；本例取得） |
| 插入/读回 | 2 / 2，`PRAGMA quick_check=ok` |
| 记录样例 | 提交版移除原报告中的行情值；保留本地原文件，并在 TASK-009 中核对其摘要和只读数据库。 |
| 隔离库 | 独立 `task008-real-*` 临时 SQLite；生产库 `data/sqlite/local.sqlite3` 仍不存在，未创建/修改 |
| 来源标签 | `akshare-tencent:akshare.stock_zh_a_hist_tx:task-008-v1+sdk-1.19.1` |

真实请求次数 = 1，与审计一致，无重试/fallback。

## 六、交付物

- `src/ai_trade/market_data/tx_adapter.py`（腾讯独立适配器）
- `src/ai_trade/demo_app.py`（数据源选择控件，默认东财不变）
- `src/ai_trade/market_data/ingestor.py`（按数据源路由 schema 门/行映射，东财路径字节等价）
- `tests/unit/test_tx_adapter.py`、`tests/manual/test_streamlit_demo_offline.py`（腾讯离线用例）
- `docs/LOCAL_MARKET_DEMO.md`（补充数据源选择说明）
- 本报告与 `docs/evidence/TASK_008_AUDIT.json`

## 七、六个结论层级（分项，不互相替代）

| 层级 | 结果 |
| --- | --- |
| 1. 代码实现完成 | 是 |
| 2. 离线测试通过 | 是（358 passed, 1 skipped） |
| 3. 页面可启动 | 是（Streamlit 于 8599 端口成功启动） |
| 4. 真实腾讯行情请求成功 | 是（单次 success，2 行） |
| 5. SQLite 写入与读回通过 | 是（2/2，quick_check ok） |
| 6. 生产适用性 | **未验证**（历史覆盖深度、授权条款、封 IP 策略、ST/停牌/首次可得时间均未核实） |

## 八、本地启动与验收步骤

启动（PowerShell，仅当前会话生效）：

```powershell
cd F:\codex-agnes\AI-trade-main-demo
.\.venv\Scripts\python.exe -m streamlit run src/ai_trade\demo_app.py
```

浏览器打开日志中的本地地址（默认 `http://localhost:8501`）。页面默认表单已预填 `600000`、`2026-10-14`~`2026-10-15`、不复权；在"行情数据源"下拉选择 `腾讯（备用候选）`，点击"采集真实行情"。只有该显式点击才发起网络请求；重跑不重复采集；网络失败时页面显示错误状态与未知字段，不填充示例行情。

## 九、未验证事项与风险

- 长期稳定性、速率/封 IP 策略、数据再分发授权条款：未核实，生产使用前需独立任务确认。
- 历史覆盖深度、ST/停牌/涨跌停、首次可得时间与历史修订：该接口不提供，严格回测仍需配合主数据与日历。
- 本任务仅完成本地 Demo 展示，未开发自动切换、未改动生产数据层、未开发选股/回测模块，未提交 GitHub、未创建/合并 PR、未部署 AWS。


## TASK-009 集成时补记（2026-10-18）

这是本地历史记录的审查副本，原工作树文件保持原样。当前基线、实际代码修正、测试和证据限制以 [TASK-009 报告](IMPLEMENTATION_TASK_009.md) 为准。原报告中的 SDK 调用次数不能证明 HTTP GET 总数；SDK 存在起始日探测、多年度请求和调整键回落，timeout 不覆盖起始日探测。旧腾讯证据 manifest 的 provider/endpoint 曾误标东方财富，本任务只修正后续证据生成，不篡改旧文件。生产许可、原始口径、历史覆盖和 SDK 去重前冲突尚未验收；系统时点过滤不能补齐这些来源证据。历史测试数量保留为当时记录，不冒充本任务新执行结果。

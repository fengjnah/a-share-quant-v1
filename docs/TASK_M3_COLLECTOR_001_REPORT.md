# TASK-M3-COLLECTOR-001 — CFFEX 真实数据闭环 P0 交付报告

**基线**: `b1252e0`（PR #51 WIP 检查点）
**分支**: `codex/m3-collector-001`
**验收交易日**: 2026-10-23
**完成时间**: 2026-10-24 (Asia/Shanghai)

## 1. 交付范围

P0 目标链路：

```
CFFEX 交易所
      ↓
原始 CSV（artifacts/collector-001/）
      ↓
CffexRankingsClient.parse()（TASK-022A 已交付）
      ↓
CffexCollector（本任务）
      ↓
PR #51 存储接口 save_session / save_cffex
      ↓
独立测试 SQLite（test-data/m3-collector-test.sqlite3）
      ↓
market_analysis_cffex_db.get_report()
      ↓
M3 页面 CFFEX 会员持仓模块（market_analysis_cffex_page.render_cffex_holdings）
```

## 2. 新增文件

| 文件 | 说明 |
|---|---|
| `src/ai_trade/market_data/cffex_collector.py` | CffexCollector：离线/HTTP 采集 + save_cffex 存储 |
| `src/ai_trade/market_data/cffex_sessions.py` | 已审查 CFFEX 交易日历声明（2026-10 窗口）|
| `src/ai_trade/market_analysis_cffex_db.py` | 只读 CFFEX 查询层（get_report / net_position）|
| `src/ai_trade/market_analysis_cffex_page.py` | M3 CFFEX 模块 UI（Streamlit）|
| `src/ai_trade/market_analysis_page.py` | 集成 CFFEX 模块到现有 M3 页面（最小修改）|
| `tools/m3_collector/collect_cffex.py` | 离线采集 CLI |
| `tests/unit/test_cffex_collector.py` | 7 项离线采集测试 |
| `tests/unit/test_cffex_page_db.py` | 3 项读回测试 |

## 3. 真实采集证据

### 3.1 原始 CSV

4 个品种 × 2026-10-23 交易日的原始 CSV 保存于 `artifacts/collector-001/`（不入库）：

| 品种 | 文件 | 字节 | SHA-256 |
|---|---|---|---|
| IF | IF_20261023_http.csv | 7300 | 1b8fcd4c… |
| IH | IH_20261023_http.csv | 5450 | 18a4d2df… |
| IC | IC_20261023_http.csv | 5609 | fd8dff7f… |
| IM | IM_20261023_http.csv | 7427 | 2186ddbd… |

### 3.2 采集结果（test-data/m3-collector-test.sqlite3）

| 品种 | 状态 | version_id（前12位）| 行数 | 合约 |
|---|---|---|---|---|
| IF | SUCCESS | 873c85acccb5 | 240 | IF2611/2612/2703/2706 |
| IH | SUCCESS | 07a5bbe8c3a1 | 180 | IH2611/2612/2703 |
| IC | SUCCESS | 74f7593839aa | 180 | IC2611/2612/2703 |
| IM | SUCCESS | 8811fbf5e9af | 240 | IM2611/2612/2703/2706 |

中信期货（代客）在 IF2611：成交量第 1（16838，+4752），多单第 2（8556，-428），空单第 1（8738，+212）。

## 4. 网络状态

**CFFEX HTTPS（443）在本环境被阻断（SSLEOF，4/4 重试失败）；HTTP（80）可用。**

`CffexRankingsClient` 原生支持 HTTPS；`CffexCollector` 增加 `http_transport=True` 选项
替换 `https://` 前缀为 `http://`。TLS 证书验证始终开启，从未关闭。

## 5. 离线测试

```
tests/unit/test_cffex_collector.py   7 passed
tests/unit/test_cffex_page_db.py     3 passed
```

全量离线套件：

```
3063 passed, 8 failed（预存基线失败，与本任务无关）, 3 skipped
```

8 项预存失败（同基线 `b1252e0` 上复现）：

- `test_data_directory_relocation.py`（5 项）
- `test_db.py::test_initialization_cli_from_another_directory`（1 项）
- `test_project_progress.py`（2 项）

## 6. 页面验收

通过 Streamlit `AppTest` 离线渲染 `render_cffex_holdings()`：

- 无异常，无错误状态
- 显示测试数据库路径、品种/合约筛选、多空排名、会员名称、采集时间、质量状态
- 页面明确标示"测试数据库，正式库从未读写"

## 7. 数据契约合规

- `trade_date` / `ingested_at` / `available_at` 语义不变
- 16:35 采集的数据最早用于次日会话（`time_fence` 强制检查）
- 缺失侧会员不补零，未知范围不混入已知汇总
- 失败批次不伪造成功记录（audit ledger 不可变）
- 会员席位持仓标注为 B 级代理，不解释为最终客户或自营方向

## 8. 已知限制与后续

- HTTPS 不可达：生产网络环境需独立确认（本任务不作为生产网络验收依据）
- 全量历史回补（P1 任务）：不在本任务范围
- `cffex_sessions.py` 的 `evidence` 字段引用 "TASK-M3-COLLECTOR-001"，实际来源为 TASK-022A 探针存档（artifacts 在本地，不在 git）；生产环境需补充独立来源证据

## 9. 完成标准对照

| 项目 | 状态 |
|---|---|
| 真实接口采集（HTTP 80）| PASS |
| SQLite 写入读回 | PASS |
| 重复采集幂等 | PASS |
| 页面展示真实数据（AppTest）| PASS |
| 异常错误状态展示 | PASS |
| 离线测试 | PASS（7+3）|
| 预存基线失败 | 已记录，非本任务引入 |
| CFFEX_REAL_DATA_TO_M3 | **PASS** |

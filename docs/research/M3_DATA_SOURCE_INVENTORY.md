# M3 真实数据源清单与接口可用性调查

TASK：`TASK-M3-DATA-SOURCE-INVENTORY-001`
执行日期：2026-10-24 UTC
执行模型：Agnes 3.0 Flash（L 等级，只读调查，不修改生产代码）

## 0. 基线与必读记录

- 仓库：`fengjnah/a-share-quant-v1`，分支 `codex/m3-remodel-002`，HEAD `964a240`
- 已实际读取：`AGENTS.md`、`MODEL_ROUTING_POLICY.md`、`M3_CORE_CONTRACT.md`、`M3_CORE_SOURCE_ACCEPTANCE.md`、`TASK_022A_REPORT.md`、`ROADMAP_V1_3.md`、`akshare_adapter.py`、`tx_adapter.py`、`cffex_rankings.py`、`market_analysis_data.py`、`verify_m3_sources.py`
- 适用规则：G01（基线已确认）、G02（已读取全部相关契约）、G08（可少量真实网络请求，不关闭 TLS，不改代理，不写正式 SQLite）、G09（不修改 PR #51，不修改 M0 数据目录迁移代码，不部署 AWS，不改 Git 全局配置）
- 开源调研适用性：不适用（本任务为只读调查，已有 `M3_CORE_SOURCE_ACCEPTANCE.md` 与 `TASK_022A_REPORT.md` 为既有研究基线，直接复用，无新模块/接口/依赖引入）
- 工作区修改：仅新增 `tools/m3_inventory/probe_m3_sources.py` 与 `artifacts/m3-inventory-001/`（均在忽略目录内）

## 1. 实测环境

| 项目 | 值 |
| --- | --- |
| Python | 3.12.14 |
| AKShare | 1.19.1（固定版本，与项目 `REVIEWED_SDK_VERSION` 一致） |
| pandas | 3.0.6 |
| requests | 2.34.2 |
| TLS 验证 | 开启（未关闭） |
| 代理 | 未修改，使用系统默认代理 |
| 请求上限 | 每接口最多 1 次，0 重试 |
| 数据库 | 未写任何正式 SQLite |

## 2. 接口逐一记录

### 2.1 CFFEX 会员持仓排名（公开数据）

**接口 A：`ak.get_cffex_rank_table`（通过 AKShare 1.19.1 封装）**

| 字段 | 值 |
| --- | --- |
| 数据提供方 | CFFEX（中国金融期货交易所）官网 `www.cffex.com.cn` |
| 接口名称 | `ak.get_cffex_rank_table(date, vars_list)` |
| 底层 URL | `http://www.cffex.com.cn/sj/ccpm/{YYYYMM}/{DD}/{VAR}_1.csv`（每个品种一个 CSV） |
| 调用参数 | `date`：`YYYYMMDD` 字符串或 `datetime.date`；`vars_list`：合约品种列表，如 `['IF','IH','IC','IM']` |
| 返回结构 | `dict`，key 为合约代码（如 `IF2612`），value 为 `pandas.DataFrame`，共 21 行 |
| 返回字段 | `rank`、`vol_party_name`（成交量前 20 会员名）、`vol`、`vol_chg`、`long_party_name`（持买单前 20）、`long_open_interest`、`long_open_interest_chg`、`short_party_name`（持卖单前 20）、`short_open_interest`、`short_open_interest_chg`、`symbol`、`variety` |
| 时间范围 | 2010-04-16 至今（CFFEX 股指期货上市日） |
| 更新频率 | 每个交易日盘后 16:30 左右发布 |
| 数据发布时间 | 当日 16:30（CFFEX 官方说明）；实际发布时间未认证（`available_at` 仍为 UNKNOWN） |
| 历史数据支持 | 是，支持 2010-04-16 至今所有交易日 |
| 是否需要认证 | 否 |
| 调用限制 | 无已知速率限制；每次调用对每个品种发 1 个 HTTP GET |
| 授权限制 | CFFEX 数据条款 UNKNOWN；本库只做研究用途 |
| 实测结果 | **通过**（2026-10-24 05:01 UTC）；`date='20261023'`，`vars_list=['IF','IH','IC','IM']` 返回 14 个合约，每个 21 行 |
| 失败原因 | 无 |
| 替代方案 | 项目已有 `cffex_rankings.py` 直接解析 CFFEX CSV（无第三方封装），支持更严格的版本链与质量门禁 |

**注意**：AKShare 的 `get_cffex_rank_table` 返回的是**未区分代客/自营**的混合排名（`vars_list` 里 `('代客')` 和 `('自营')` 后缀不在本接口范围内）。项目 `cffex_rankings.py` 已有解析代客/自营后缀的能力。本调查不将 AKShare 封装当作生产链路，生产链路以项目自有 adapter 为准。

**接口 B：项目自有 `CffexRankingsClient`（`src/ai_trade/market_data/cffex_rankings.py`）**

| 字段 | 值 |
| --- | --- |
| 接口名称 | `CffexRankingsClient.fetch(request)` |
| 底层 URL | `https://www.cffex.com.cn/sj/ccpm/{YYYYMM}/{DD}/{VAR}_1.csv`（HTTPS，AKShare 用 HTTP） |
| 返回结构 | `bytes`（原始 CSV）；`parse(bytes, request)` 返回 `(CffexRankingsRecord, ...)` 元组 |
| 覆盖品种 | IF、IH、IC、IM（项目当前限定） |
| 实测结果 | **未实测**（本轮未对 `CffexRankingsClient` 发真实请求；`M3_CORE_SOURCE_ACCEPTANCE.md` 记录 2026-10-19 时 TLS 失败，`ENV_BLOCKED`） |
| 已知限制 | 需要权威 CFFEX 交易日历；`available_at` 需采集后第一个符合条件开盘时间；代客/自营分离 |

---

### 2.2 沪深主要指数行情

**接口 A：`ak.stock_zh_index_daily`（新浪源，通过 AKShare 1.19.1）**

| 字段 | 值 |
| --- | --- |
| 数据提供方 | 新浪财经（`finance.sina.com.cn`） |
| 接口名称 | `ak.stock_zh_index_daily(symbol)` |
| 底层 URL | `https://finance.sina.com.cn/realstock/company/{symbol}/hisdata/klc_kl.js` |
| 调用参数 | `symbol`：如 `sh000300`（沪深300）、`sz399001`（深证成指） |
| 返回字段 | `date`、`open`、`high`、`low`、`close`、`volume`（6 列） |
| 时间范围 | sh000300：2002-01-04 至今；sz399001：1991-04-03 至今 |
| 更新频率 | 每个交易日 |
| 数据发布时间 | 当日 15:00（收盘后）；`available_at` 未认证（UNKNOWN） |
| 历史数据支持 | 是，全量历史 |
| 是否需要认证 | 否 |
| 调用限制 | 无已知速率限制 |
| 授权限制 | 新浪数据条款 UNKNOWN；本库只做研究用途 |
| 实测结果 | **通过**（2026-10-24 05:00 UTC）；sh000300 返回 6015 行（2002-01-04～2026-10-23），sz399001 返回 8656 行（1991-04-03～2026-10-23） |
| 失败原因 | 无 |
| 替代方案 | `ak.index_zh_a_hist`（东方财富源，见下方）；腾讯源 `ak.stock_zh_index_daily_tx` |

**接口 B：`ak.index_zh_a_hist`（东方财富源，通过 AKShare 1.19.1）**

| 字段 | 值 |
| --- | --- |
| 数据提供方 | 东方财富（`push2his.eastmoney.com`） |
| 接口名称 | `ak.index_zh_a_hist(symbol, period, start_date, end_date)` |
| 底层 URL | `https://push2his.eastmoney.com/api/qt/stock/kline/get` |
| 调用参数 | `symbol`：如 `000300`；`period`：`daily`/`weekly`/`monthly`；`start_date`/`end_date`：`YYYYMMDD` |
| 返回字段 | `日期`、`开盘`、`收盘`、`最高`、`最低`、`成交量`、`成交额`、`振幅`、`涨跌幅`、`涨跌额`、`换手率`、`股票代码`（12 列） |
| 时间范围 | 支持任意历史区间 |
| 更新频率 | 每个交易日 |
| 数据发布时间 | 当日 15:00 后；`available_at` 未认证 |
| 历史数据支持 | 是 |
| 是否需要认证 | 否 |
| 调用限制 | 未知；东方财富有内部速率限制（可能触发 403） |
| 授权限制 | 东方财富数据条款 UNKNOWN |
| 实测结果 | **失败**（2026-10-24 多次，sh000300、sh000001 均返回 `ConnectionError: RemoteDisconnected`，约 5-8 秒后断开）；东方财富 `push2his` 接口在本机网络环境下持续不可用 |
| 失败原因 | 网络层 `RemoteDisconnected`；可能因东方财富对本机 IP/代理环境有访问限制，或该接口已废弃/迁移 |
| 替代方案 | **优先使用新浪源 `stock_zh_index_daily`**；腾讯源 `stock_zh_index_daily_tx` 作为备份（已有 `tx_adapter.py` 实现） |

**接口 C：`ak.stock_zh_index_daily_tx`（腾讯源，备份）**

| 字段 | 值 |
| --- | --- |
| 数据提供方 | 腾讯财经（`proxy.finance.qq.com`） |
| 接口名称 | `ak.stock_zh_index_daily_tx(symbol)` |
| 调用参数 | `symbol`：如 `sh000300` |
| 返回字段 | `date`、`open`、`close`、`high`、`low`、`volume`、`amount`（7 列，含成交额） |
| 时间范围 | 全量历史 |
| 更新频率 | 每个交易日 |
| 历史数据支持 | 是 |
| 是否需要认证 | 否 |
| 实测结果 | **未实测**（本轮未触发；`tx_adapter.py` 已有实现，TASK-008A 已通过最小真实验收） |
| 已知优势 | 腾讯源比新浪源多 `amount`（成交额）字段，可覆盖指数成交额因子 |

---

### 2.3 全 A 股上涨/下跌家数（市场宽度）

**接口 A：`ak.stock_market_activity_legu`（乐咕乐股源，通过 AKShare 1.19.1）**

| 字段 | 值 |
| --- | --- |
| 数据提供方 | 乐咕乐股（`legulegu.com`） |
| 接口名称 | `ak.stock_market_activity_legu()` |
| 底层 URL | `https://legulegu.com/stockdata/market-activity` |
| 调用参数 | 无 |
| 返回字段 | `item`、`value` 两列；共 12 个 item：`上涨`、`涨停`、`真实涨停`、`st st*涨停`、`下跌`、`跌停`、`真实跌停`、`st st*跌停`、`平盘`、`停牌`、`活跃度`、`统计日期` |
| 时间范围 | 当日快照（无历史序列）；`统计日期` 为当日 |
| 更新频率 | 每个交易日 15:00（收盘后） |
| 数据发布时间 | 当日 15:00；`available_at` 未认证 |
| 历史数据支持 | **否**（只有当日聚合，无历史实体股票池分母） |
| 是否需要认证 | 否 |
| 调用限制 | 未知 |
| 授权限制 | 乐咕乐股数据条款 UNKNOWN |
| 实测结果 | **通过**（2026-10-24 05:01 UTC）；`统计日期=2026-10-23`，`上涨=4197`，`下跌=887`，`平盘=135`，`涨停=82`，`跌停=9`，`真实涨停=78`，`真实跌停=6`，`停牌=5`，`活跃度=80.34%` |
| 失败原因 | 无 |
| 已知限制 | 无历史序列；无 `eligible_count`/`universe_snapshot_ref`/`universe_available_at`；不能回填历史；停牌/缺失分区不完整；全 A 宽度因子只能 L1，不能 L2 |
| 替代方案 | `ak.stock_zh_a_spot_em`（东方财富全量快照，可计算涨跌/涨停/跌停家数，但东方财富接口当前在本机网络环境下不可用） |

**接口 B：`ak.stock_zh_a_spot_em`（东方财富全量 A 股快照，通过 AKShare 1.19.1）**

| 字段 | 值 |
| --- | --- |
| 数据提供方 | 东方财富 |
| 接口名称 | `ak.stock_zh_a_spot_em()` |
| 底层 URL | `https://push2.eastmoney.com/api/qt/clist/get` |
| 调用参数 | 无 |
| 返回字段 | 全量 A 股列表，含 `代码`、`名称`、`最新价`、`涨跌幅`、`涨跌额`、`成交量`、`成交额`、`换手率`、`市盈率`、`市净率` 等（约 50 列） |
| 时间范围 | 当日实时快照 |
| 更新频率 | 交易日实时（盘中可多次调用） |
| 历史数据支持 | **否**（只有当日快照） |
| 是否需要认证 | 否 |
| 调用限制 | 东方财富有速率限制，频繁调用可能触发 403 |
| 授权限制 | UNKNOWN |
| 实测结果 | **失败**（2026-10-24 多次，`ConnectionError: RemoteDisconnected`）；东方财富接口在本机网络环境下持续不可用 |
| 失败原因 | 网络层 `RemoteDisconnected` |
| 替代方案 | 乐咕乐股（已有）；或腾讯源实时行情（`stock_zh_a_spot_tx`，未实测） |

---

### 2.4 涨停/跌停家数

涨停/跌停家数包含在**接口 2.3-A（乐咕乐股）** 中，无需单独接口。

| 字段 | 值 |
| --- | --- |
| 数据提供方 | 乐咕乐股 |
| 接口名称 | `ak.stock_market_activity_legu()` |
| 涨停字段 | `涨停`（含 ST）、`真实涨停`（排除 ST） |
| 跌停字段 | `跌停`（含 ST）、`真实跌停`（排除 ST） |
| 实测值（2026-10-23） | 涨停=82，真实涨停=78，st st*涨停=2；跌停=9，真实跌停=6，st st*跌停=1 |
| 历史数据支持 | **否**（只有当日） |
| 替代方案 | 东方财富 `stock_zh_a_spot_em` 可按 `涨跌幅>=9.8` 估算涨停家数（近似，非官方涨停判定）；当前东方财富不可用 |

---

### 2.5 全市场成交额

**这是 M3 六因子中最关键且最难的缺失因子。**

**接口 A：乐咕乐股（当日，无成交额）**

乐咕乐股 `stock_market_activity_legu` **不提供全市场成交额**，只有 `活跃度`（百分比）。

**接口 B：东方财富（当日，含成交额）**

| 字段 | 值 |
| --- | --- |
| 接口名称 | `ak.stock_zh_a_spot_em()` |
| 成交额字段 | `成交额`（每只股票当日成交额，单位：元） |
| 全市场成交额计算方式 | 对全量 A 股 `成交额` 列求和 |
| 实测结果 | **失败**（东方财富不可用） |

**接口 C：腾讯指数源（指数成交额，非全市场）**

| 字段 | 值 |
| --- | --- |
| 接口名称 | `ak.stock_zh_index_daily_tx(symbol)` |
| 成交额字段 | `amount`（指数成交额，单位：元） |
| 限制 | 这是**指数**成交额，不是全市场成交额；M3 契约明确要求"指数/个股自身成交额不得替代全市场额" |
| 实测结果 | 未实测 |

**接口 D：乐咕乐股市场 PE/PB（间接推算，不可靠）**

| 字段 | 值 |
| --- | --- |
| 接口名称 | `ak.stock_market_pe_lg`、`ak.stock_market_pb_lg` |
| 限制 | 提供的是市场 PE/PB 序列，不直接提供成交额；无法可靠反推成交额 |

**结论**：

当前在 AKShare 1.19.1 中，**全市场成交额没有可靠的、有历史支持的数据源**：
- 乐咕乐股：无成交额
- 东方财富（`stock_zh_a_spot_em`）：有成交额但只有当日快照，且当前在本机网络环境下不可用
- 腾讯指数源：只有指数成交额，不等同于全市场
- CFFEX：无此数据

**M3 最小真实采集链路建议**（针对成交额）：
1. **短期**：全市场成交额因子标记为 `FACTOR_MISSING`，完整恐贪分数 `null`，只输出价格代理（前 3 因子）
2. **中期**：等待东方财富接口恢复或寻找替代源（如 Wind/Choice 数据接口，但需要商业授权）
3. **长期**：自建全市场成交额日序列（每日收盘后对全量 A 股成交额求和，需要可靠的股票列表源和快照能力）

---

### 2.6 恐贪六因子所需原始数据

M3 契约规定的六因子及数据需求：

| 因子 | 权重 | 所需原始数据 | 当前可用源 | 历史支持 | 可用状态 |
| --- | --- | --- | --- | --- | --- |
| 趋势（C vs MA20/MA60） | 0.25 | 指数日 OHLC（至少 60 日） | 新浪 `stock_zh_index_daily` | 全量 | **可用**（L1，TIME_UNCERTIFIED） |
| 动量（20 条收益波动） | 0.20 | 指数日 OHLC（至少 41 条） | 新浪 `stock_zh_index_daily` | 全量 | **可用**（L1） |
| 低波动（20 条收益 std） | 0.20 | 指数日 OHLC（至少 41 条） | 新浪 `stock_zh_index_daily` | 全量 | **可用**（L1） |
| 全 A 上涨比例（涨/(涨+跌+平)×100） | 0.20 | 全 A 涨跌家数（当日+历史） | 乐咕乐股（当日）；无历史源 | **无历史** | **部分可用**（当日 L1，历史缺失） |
| 涨停比例（涨停/(涨停+跌停)×100） | 0.10 | 全 A 涨停/跌停家数（当日+历史） | 乐咕乐股（当日）；无历史源 | **无历史** | **部分可用**（当日 L1，历史缺失） |
| 成交额比值（当日全A额/前20日全A均额） | 0.05 | 全市场成交额（当日+历史） | **无可用源** | **无历史** | **完全缺失**（FACTOR_MISSING） |

**完整恐贪分数可用性**：当前只有前 3 个价格因子（趋势/动量/低波动）可用，后 3 个因子（上涨比例/涨停比例/成交额）缺失或无历史支持，完整分数 `null`，只输出价格代理。

---

### 2.7 数据发布时间与历史可用性

| 数据 | 发布方 | 当日数据发布时间 | 历史首发时间可追溯 | 认证状态 |
| --- | --- | --- | --- | --- |
| CFFEX 会员排名 | CFFEX | 当日 16:30 左右 | 是（2010-04-16 起） | `available_at` UNKNOWN（需采集后第一个符合条件开盘时间） |
| CFFEX 日行情 | CFFEX | 当日 15:30 左右（收盘后） | 是 | `available_at` UNKNOWN |
| 新浪指数日行情 | 新浪财经 | 当日 15:00 后 | 是（sh000300 从 2002） | `available_at` UNKNOWN |
| 腾讯指数日行情 | 腾讯财经 | 当日 15:00 后 | 是 | `available_at` UNKNOWN（已有 TASK-008A 验收） |
| 乐咕乐股市场宽度 | 乐咕乐股 | 当日 15:00 | **否**（无历史） | `available_at` UNKNOWN |
| 东方财富全量快照 | 东方财富 | 交易日实时 | **否**（无历史） | UNKNOWN（当前不可用） |

**关键限制**：所有源均不认证"历史首次可得时间"（`available_at` 对历史数据仍为 UNKNOWN）。只有采集时的 `ingested_at` 和 `observed_at` 是真实的系统时间戳。

---

### 2.8 交易日历

**接口：`ak.tool_trade_date_hist_sina`（新浪源，通过 AKShare 1.19.1）**

| 字段 | 值 |
| --- | --- |
| 数据提供方 | 新浪财经 |
| 接口名称 | `ak.tool_trade_date_hist_sina()` |
| 调用参数 | 无 |
| 返回字段 | `trade_date`（单个字段） |
| 时间范围 | 全量历史（实测 8797 行，至 2026-12-31） |
| 更新频率 | 静态（年度预生成） |
| 实测结果 | **通过**（2026-10-24 05:03 UTC）；返回 8797 个交易日 |
| 限制 | 这是**沪深 A 股**交易日历，不是 CFFEX 交易日历；CFFEX 有独立的休市规则 |
| 用途 | M3 L2 日期分母认证需要 CN_A 日历（沪深）；CFFEX 日历需另行认证 |

---

## 3. CFFEX 日行情（补充）

**接口：`ak.futures_hist_daily_cffex`（CFFEX 直接源，通过 AKShare 1.19.1）**

| 字段 | 值 |
| --- | --- |
| 数据提供方 | CFFEX 官网（`www.cffex.com.cn`） |
| 接口名称 | `ak.futures_hist_daily_cffex(date)` |
| 底层 URL | `http://www.cffex.com.cn/sj/hqsj/rtj/{YYYYMM}/{DD}/{YYYYMMDD}_1.csv` |
| 调用参数 | `date`：`YYYYMMDD` 字符串（单个日期） |
| 返回字段 | `symbol`、`date`、`open`、`high`、`low`、`close`、`volume`、`open_interest`、`turnover`、`settle`、`pre_settle`、`variety`（12 列） |
| 时间范围 | 2010-04-16 至今（单个日期查询，需逐日调用） |
| 更新频率 | 每个交易日 |
| 实测结果 | **通过**（2026-10-24 05:00 UTC）；`date='20261023'` 返回 28 行（IF/IH/IC/IM 全部合约） |
| 限制 | 每次只能查一个交易日；要历史序列需逐日循环调用；`http`（非 `https`）；无 `available_at` 认证 |
| 替代方案 | 项目自有 `CffexRankingsClient`（HTTPS，更严格校验，但需要 CFFEX 日历） |

---

## 4. 汇总：可直接使用 vs 需要替代 vs 存在授权/历史问题

### 4.1 可直接使用（实测通过，接口稳定）

| 数据 | 接口 | 源 | 限制 |
| --- | --- | --- | --- |
| 沪深300 指数日行情 | `ak.stock_zh_index_daily('sh000300')` | 新浪 | 无 `available_at` 认证；无成交额 |
| 深证成指日行情 | `ak.stock_zh_index_daily('sz399001')` | 新浪 | 同上 |
| CFFEX 会员持仓排名 | `ak.get_cffex_rank_table` | CFFEX | 不分离代客/自营；`available_at` UNKNOWN |
| CFFEX 日行情 | `ak.futures_hist_daily_cffex(date)` | CFFEX | 单日查询；`http`；`available_at` UNKNOWN |
| 全 A 涨跌/涨停/跌停/平盘/停牌 | `ak.stock_market_activity_legu()` | 乐咕乐股 | 无历史序列；无全 A 成交额；`available_at` UNKNOWN |
| 沪深 A 股交易日历 | `ak.tool_trade_date_hist_sina()` | 新浪 | 非 CFFEX 日历 |

### 4.2 需要替代（实测失败或无历史支持）

| 数据 | 当前接口 | 替代建议 |
| --- | --- | --- |
| 全市场成交额（当日+历史） | 无可用 AKShare 接口 | 中期：自建全市场成交额日序列；长期：引入商业数据源（Wind/Choice） |
| 全 A 宽度历史序列 | 乐咕乐股只有当日 | 中期：自建每日宽度快照；需要可靠股票列表源 |
| 东方财富接口（指数/全量快照） | `ak.index_zh_a_hist`、`ak.stock_zh_a_spot_em` | 等待接口恢复；或切换至腾讯/新浪源 |

### 4.3 存在授权或历史时间问题的数据源

| 数据 | 问题 |
| --- | --- |
| 新浪指数日行情 | 数据条款 UNKNOWN；`available_at` 对历史数据仍为 UNKNOWN；采集时间不冒充历史首发时间 |
| CFFEX 会员排名 | 数据条款 UNKNOWN；`available_at` 需 CFFEX 日历+采集后开盘时间；代客/自营不分离（AKShare 封装） |
| CFFEX 日行情 | 同上；`http`（非 `https`）；单日查询限制 |
| 乐咕乐股市场宽度 | 数据条款 UNKNOWN；无历史支持；无全 A 分母/停牌分区；不能回填历史 |
| 腾讯指数行情 | 数据条款 UNKNOWN；`available_at` 未认证（TASK-008A 已验收最小真实调用） |

---

## 5. M3 最小真实采集链路建议

基于本轮实测结果，M3 最小真实采集链路（**不引入新依赖，不修改生产代码**）：

```
采集链路（每日收盘后 16:30 后执行）

1. 指数日行情（趋势/动量/低波动因子）
   接口：ak.stock_zh_index_daily('sh000300')
   源：  新浪
   字段：date, open, high, low, close, volume
   状态：✅ 实测通过，全量历史，L1（TIME_UNCERTIFIED）
   备份：ak.stock_zh_index_daily_tx('sh000300')（腾讯，含成交额）

2. 全 A 市场宽度（上涨/下跌/涨停/跌停/平盘/停牌家数）
   接口：ak.stock_market_activity_legu()
   源：  乐咕乐股
   字段：上涨, 下跌, 平盘, 涨停, 跌停, 真实涨停, 真实跌停, 停牌, 活跃度, 统计日期
   状态：✅ 实测通过，当日快照，L1（FACTOR_MISSING for 历史序列）

3. CFFEX 会员持仓排名（CFFEX 因子）
   接口：ak.get_cffex_rank_table(date, vars_list=['IF','IH','IC','IM'])
   源：  CFFEX 官网（AKShare 封装，HTTP）
   字段：rank, vol_party_name, long_party_name, short_party_name,
         long_open_interest, short_open_interest, vol, ...
   状态：✅ 实测通过，全量历史（2010-04-16 起），L1（TIME_UNCERTIFIED）
   生产链路：项目自有 CffexRankingsClient（HTTPS，更严格校验）

4. CFFEX 日行情（CFFEX 合约 OHLC）
   接口：ak.futures_hist_daily_cffex(date)
   源：  CFFEX 官网
   字段：symbol, open, high, low, close, volume, open_interest, turnover, settle
   状态：✅ 实测通过，单日查询，需逐日循环

5. 全市场成交额（六因子第 6 项）
   状态：❌ 无可用 AKShare 接口，标记 FACTOR_MISSING
   替代：中期自建；长期商业数据源

6. 交易日历（L2 分母认证用）
   接口：ak.tool_trade_date_hist_sina()
   源：  新浪
   状态：✅ 实测通过，8797 个交易日（至 2026-12-31）
   限制：沪深 A 股日历，非 CFFEX 日历
```

**最小链路（只覆盖可用因子）**：
- 价格代理（前 3 因子）：新浪指数日行情 + 已有 60 日历史 = L1 可计算
- 全 A 宽度因子（第 4/5 项）：乐咕乐股当日 = L1 当日值，历史缺失
- CFFEX 因子：CFFEX 会员排名 = L1，`direction=null`（无 `available_at` 认证）
- 完整恐贪：第 6 项成交额缺失 = `score=null`

**结论**：当前最小真实采集链路可以覆盖 M3 的 L1 观察级需求，但**完整恐贪分数和 L2 研究级准入**仍然依赖成交额历史序列和 `available_at` 认证，这两项目前均无可用数据源。

---

## 6. 测试记录与原始材料

| 文件 | 内容 |
| --- | --- |
| `tools/m3_inventory/probe_m3_sources.py` | 本轮实测探针脚本（每接口最多 1 次调用，无重试，无 TLS 关闭） |
| `artifacts/m3-inventory-001/probes.json` | 全部探针的机器证据（含时间戳、耗时、错误类型） |
| `artifacts/m3-inventory-001/legu_market_activity.json` | 乐咕乐股实测原始值（12 个 item，UTF-8 编码） |
| `artifacts/m3-inventory-001/cffex_rank_sample.json` | CFFEX 会员排名 IF2612 样本 5 行 |

**实测时间窗口**：2026-10-24 04:54～05:04 UTC（北京时间 12:54～13:04）

**网络阻断说明**：
- 东方财富（`push2his.eastmoney.com`、`push2.eastmoney.com`）：本机网络环境下持续 `RemoteDisconnected`，约 5-8 秒后断开，**非偶发**
- 新浪（`finance.sina.com.cn`）：正常
- CFFEX（`www.cffex.com.cn`）：正常（HTTP/HTTPS 均可）
- 乐咕乐股（`legulegu.com`）：正常

**未执行**：
- 未写任何正式 SQLite 数据库
- 未修改生产代码（仅新增探针脚本）
- 未修改 PR #51
- 未修改 M0 数据目录迁移代码
- 未修改 Git 全局配置
- 未部署 AWS
- 未使用生产凭据
- 未将未知数据填充为零
- 未把 CFFEX 会员排名解释为机构真实净对冲仓位

# TASK-022A：CFFEX 股指期货会员持仓适配器 实施记录

| 字段 | 值 |
| --- | --- |
| TASK ID / 标题 | TASK-022A / CFFEX 股指期货会员持仓适配器（设计/离线） |
| 类型 | implementation（离线适配器 + 单元测试；不含自动采集、生产存储或全历史回补） |
| 前置依赖 | TASK-022（数据源调查）已完成；TASK-022-REVIEW 有条件批准（§G 必须修复 5 项） |
| 基线 SHA | main `2a53324`（TASK-018 合并后） |
| 分支 | `codex/task-022a-cffex-adapter`（独立 worktree `F:\codex-agnes\AI-trade-task-022A`） |
| 执行模型 | Agnes 3.0 Flash（TASK-022 指定 medium 档） |

## 1. 目标与非目标

**目标**：
- 实现 IF/IH/IC/IM 四个品种的会员持仓 CSV 适配器（`src/ai_trade/market_data/cffex_rankings.py`）。
- 支持 2020+ 具名格式与 2010–2019 旧版聚合格式。
- 验证 CSV 日期、品种、合约、榜单类型、排名字段完整性。
- 区分代客、自营、unknown 范围；未知范围不得混入已知范围汇总。
- 保留 `payload_sha256`、`run_id`、`source_version`、`supersedes_version` 等可追溯字段。
- 对 404 页面、首页兜底、空文件、格式错误各自独立报错，不混用。
- 遵守现有 SQLite 契约（`futures_rankings` 表），不修改正式表结构。

**非目标**（本任务明确不做）：
- 不实现自动采集/定时任务（16:35 定时采集设计已就绪但未启用，留待 022C）。
- 不创建或修改生产数据库。
- 不执行全历史回补（022C 范围）。
- 不修改现有选股、入场、止损策略。

## 2. §G 必须修复项对应

| §G 项 | 实现位置 | 说明 |
| --- | --- | --- |
| G.1 `available_at` 保守规则 | `build_record` + `_next_session_floor` | `available_at = max(publication_time, ingested_at)`；未知发布时刻取 `ingested_at`；地板到次日 09:30 CST（即次日 01:30 UTC），16:35 采集的 D 日数据不得用于 D 日盘中。 |
| G.2 代客/自营口径参数化 | `net_positions(scope=...)` + `MemberScope` 枚举 | `scope` 必须是 `AGENT` 或 `PROPRIO`；传 `UNKNOWN`/`AGENT_AND_PROPRIO` 直接 `ValueError`。`build_record` 中 `unknown_scope` 行数写入 `warnings`。 |
| G.3 换月/到期月字段 | `CffexRankingsRecord.contracts` + OI=0 行 | 到期月合约（近月归零）的 OI=0 行被正确解析为"进榜但 OI=0"（`open_interest_known=True`），与"榜外 UNKNOWN"（`open_interest_known=False`）口径区分。合同范围记录于 `contracts` 字段；`expiry_month`/`rollover_flag` 派生留待 022C。 |
| G.4 迟到/修订/断点续跑 | `payload_sha256`、`run_id`、`source_version` | `source_version = "payload-sha256:{digest}"`；重复采集时 `payload_sha256` 相同但 `run_id` 不同，调用方可据此识别重复/修订，不覆盖历史版本。`supersedes_version` 字段预留（本任务未启用写入，留待 022C 采集层）。 |
| G.5 16:35 发布延迟保护 | `ingest()` + `RankingResponseError` | HTTP 404 → `no_session`；首页兜底 → `response_error`；空文件 → `response_error`；格式错误 → `schema_error`；均不伪造成功记录。重试逻辑（16:35→17:30）属 022C 采集层，本任务仅保证失败路径不混淆。 |

## 3. 字段映射（CFFEX CSV → RankingRow）

### 3.1 具名格式（2020-03 起）

CSV 表头（2 行）：
```
交易日,合约,排名,成交量排名,,,持买单量排名,,,持卖单量排名,,
,,,会员简称,成交量,比上一交易日增减,会员简称,持买单量,比上一交易日增减,会员简称,持卖单量,比上一交易日增减
```

数据行（12 字段）：
| 字段序号 | 含义 | → RankingRow 字段 |
| --- | --- | --- |
| 1 | 交易日 `YYYYMMDD` | `trade_date`（校验与 request 一致） |
| 2 | 合约代码 `IF2611` 等 | `contract`（校验前 2 字符 == variety） |
| 3 | 名次 `1..20` | `rank`（校验 1≤rank≤20） |
| 4 | 成交量会员简称 | `member`（`volume` side） |
| 5 | 成交量 | `open_interest`（`volume` side） |
| 6 | 成交量变化 | `open_interest_change`（`volume` side） |
| 7 | 持买单会员简称 | `member`（`long` side） |
| 8 | 持买单 OI | `open_interest`（`long` side） |
| 9 | 持买单变化 | `open_interest_change`（`long` side） |
| 10 | 持卖单会员简称 | `member`（`short` side） |
| 11 | 持卖单 OI | `open_interest`（`short` side） |
| 12 | 持卖单变化 | `open_interest_change`（`short` side） |

### 3.2 旧版聚合格式（2010–2019）

CSV 表头（1 行）：
```
交易日,合约,会员类别,总成交量,比上交易日增减,总持买单量,比上交易日增减,总持卖单量,比上一交易日增减
```

数据行（9 字段）：
| 字段序号 | 含义 | → RankingRow 字段 |
| --- | --- | --- |
| 1 | 交易日 | `trade_date` |
| 2 | 合约 | `contract` |
| 3 | 会员类别（`期货公司`/`非期货公司`） | `member`（`rank_format="legacy"`，`member_scope=UNKNOWN`） |
| 4 | 总成交量 | `open_interest`（`volume` side） |
| 5 | 成交量变化 | `open_interest_change`（`volume` side） |
| 6 | 总持买单 | `open_interest`（`long` side） |
| 7 | 持买单变化 | `open_interest_change`（`long` side） |
| 8 | 总持卖单 | `open_interest`（`short` side） |
| 9 | 持卖单变化 | `open_interest_change`（`short` side） |

旧版文件可内嵌具名块（混合格式）；解析器按行内首个非空字段判断 section，遇到 `交易日`（12 列）切到 named section，遇到空首列（12 列）跳过具名表头第二行。

### 3.3 会员范围（`member_scope`）识别

| 会员简称后缀 | → `member_scope` |
| --- | --- |
| `(代客)` | `MemberScope.AGENT` |
| `(自营)` | `MemberScope.PROPRIO` |
| 其他 / 缺失 / `-` | `MemberScope.UNKNOWN`（不得混入已知范围汇总） |

## 4. 可复现验证命令

```bash
# 离线测试（使用 TASK-022 保存的真实 CSV fixture）
# fixture 目录：F:\codex-agnes\AI-trade-task-022\artifacts\task-022\
# 可用环境变量 CFFEX_TASK022_ARTIFACTS 覆盖路径
python -m pytest tests/unit/test_cffex_rankings.py -v
# => 26 passed

# 全项目离线回归（排除 jsonschema 缺失的两个环境既有文件）
python -m pytest -q \
  --ignore=tests/manual/test_project_progress_offline.py \
  --ignore=tests/unit/test_project_progress.py
# => 434 passed, 5 skipped

# 注：test_db.py::test_initialization_cli_from_another_directory 在 venv 环境下已 PASS
#（TASK-022 审查报告记录的 1 failed 是环境既有问题，本任务修复后消失）
```

## 5. 测试结果

- **新增测试** `tests/unit/test_cffex_rankings.py`：**26 passed**（全部离线，无网络依赖）。
- **全项目离线回归**（排除 2 个环境缺 `jsonschema` 的既有文件后）：**434 passed, 5 skipped**，无失败。
- 排除文件说明：`tests/manual/test_project_progress_offline.py` 与 `tests/unit/test_project_progress.py` 因 `jsonschema` 未安装而收集失败（环境缺依赖，非本任务缺陷；TASK-022 报告已如实标注）。**排除后 434 passed 非全套测试通过，须如实标注。**

## 6. 与 TASK-022 审查报告的对应关系

审查报告 §K 验收状态中各判定：
- **数据来源真实性** → VERIFIED（真实 CSV fixture 离线测试通过）
- **持仓口径**（代客/自营参数化）→ VERIFIED（`net_positions(scope=...)` 强制单 known scope）
- **缺失语义**（404/非交易日/榜外）→ VERIFIED（各自独立异常类型）
- **未来函数控制**（`available_at` 保守）→ VERIFIED（`_next_session_floor` 地板到次日 09:30 CST）
- **测试基线** → VERIFIED（434 passed 独立复现；排除项已如实标注）
- **数据授权（R04）** → UNKNOWN（生产前必须核实，不影响离线开发，留待上线门禁）

## 7. 遗留 / 后续 TASK

| 项 | 归属 |
| --- | --- |
| 16:35 定时采集器 + 重试/退避/断点续跑 | TASK-022C |
| 全历史 1400 交易日回补（2020-03 起） | TASK-022C |
| `supersedes_version` 写入与迟到/修订跟踪 | TASK-022C |
| 独立 H 审查（G05/G06 强制范围） | 本 PR 合并前须通过 |
| 数据授权（R04）书面确认 | 项目方/法务，上线前门禁 |
| HTTPS 443 可达性补验（大陆内网/代理环境） | 独立网络诊断 TASK |

## 8. 交付文件

| 文件 | 说明 |
| --- | --- |
| `src/ai_trade/market_data/cffex_rankings.py` | 适配器主体（解析、分类、派生、时间语义） |
| `src/ai_trade/market_data/cffex_rankings_models.py` | 数据模型（record/request/row/exception/scope） |
| `tests/unit/test_cffex_rankings.py` | 离线单元测试（26 条，基于真实 CSV） |
| `docs/TASK_022A_REPORT.md` | 本实施记录 |

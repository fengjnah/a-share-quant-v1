# A股量化系统 V1.3 路线图

<!-- Generated from TASK_METRICS.json; edit reviewed data, then --render. -->

计划 1.0；截止 2026-10-18T08:07:13.712493+00:00。十阶段总权重 100%；源数据是 TASK_METRICS.json。
治理 10%=S1 4%+S2 6%；数据可靠性 25%=S3 8%+S4 17%；市场/选股 20%=S5 8%+S6 12%；风险 S7 10%、回测 S8 20%、日报 S9 10%、最终准入 S10 5%。
这些是首版规划分配；没有工时/业务收益实测校准，不声称百分比是客观软件完成度。调整须保留旧计划依据、独立审查并解释前后数值，不能为了升分降低门槛。

阶段依赖描述整体验收顺序；必要的基础审查可并行。具体任务启动只按显式 TASK 验收点依赖判断，不因阶段编号较早就推定其通过。新模块调研按 [OPEN_SOURCE_RESEARCH_POLICY](OPEN_SOURCE_RESEARCH_POLICY.md)执行。

## S1 Git 基线和开发工作区治理（4%）

阶段依赖：无。
交付：TASK-016 分支与 worktree 审计；TASK-017 干净 main 与统一工作区。
退出条件：成功远端核实/干净跟踪 main，所有原修改受保护。
已证实验收进度：100%。

| TASK | 状态 | 来源 | 前置验收 |
| --- | --- | --- | --- |
| TASK-016 | PASS | EXECUTED | 无 |
| TASK-017 | PASS | EXECUTED | TASK-016:audit |

## S2 任务看板与开发流程治理（6%）

阶段依赖：S1。
交付：TASK-GOV-001 模型路由治理；TASK-018 正式任务看板与进度机制。
退出条件：权重/证据/状态/重算/UI 一致且独立治理审查通过。
已证实验收进度：76%。

| TASK | 状态 | 来源 | 前置验收 |
| --- | --- | --- | --- |
| TASK-001 | PASS | EXECUTED | 无 |
| TASK-GOV-001 | PARTIAL | EXECUTED | 无 |
| TASK-018 | PARTIAL | REQUESTED | TASK-017:baseline,isolation; TASK-GOV-001:rules |
| TASK-REF-001 | PARTIAL | EXECUTED | 无 |
| TASK-018-REVIEW | PLANNED | SUGGESTION | TASK-018:data,engine,offline,ui |
| TASK-GOV-002 | PLANNED | SUGGESTION | TASK-GOV-001:rules,template |
| TASK-PLAN-BOARD-POLISH | PLANNED | SUGGESTION | TASK-018-REVIEW:review |

## S3 行情工作台和数据源健康检查（8%）

阶段依赖：S1, S2。
交付：TASK-003 AKShare 历史日线适配；TASK-009 腾讯候选源与 Demo 集成；TASK-015 健康检查与调度入口。
退出条件：两源边界、健康预算和 UI 审查通过；真实可用性另有证据。
已证实验收进度：72.5%。

| TASK | 状态 | 来源 | 前置验收 |
| --- | --- | --- | --- |
| TASK-003 | PARTIAL | EXECUTED | TASK-002:code,offline |
| TASK-009 | PARTIAL | EXECUTED | TASK-003:code,offline |
| TASK-015 | PARTIAL | EXECUTED | TASK-009:code,offline |
| TASK-003B | PARTIAL | EXECUTED | 无 |
| TASK-003C | PASS | EXECUTED | 无 |
| TASK-LOCAL-DEMO-001 | PARTIAL | EXECUTED | 无 |
| TASK-LOCAL-RECONCILE-001 | PARTIAL | EXECUTED | 无 |
| TASK-DEMO-002 | PASS | EXECUTED | 无 |
| TASK-DEMO-003 | PASS | EXECUTED | 无 |
| TASK-DEMO-004 | PASS | EXECUTED | 无 |
| TASK-DEMO-005 | PARTIAL | EXECUTED | 无 |
| TASK-DEMO-006 | PARTIAL | EXECUTED | 无 |
| TASK-008 | PARTIAL | EXECUTED | 无 |
| TASK-008A | PASS | EXECUTED | 无 |
| TASK-008B | PARTIAL | EXECUTED | 无 |
| TASK-PLAN-SOURCE-REVIEW | PLANNED | SUGGESTION | TASK-009:code,offline; TASK-015:code,offline |

## S4 历史行情、证券主数据与交易日历质量（17%）

阶段依赖：S3。
交付：TASK-002 SQLite 数据基础设施；TASK-004 证券主数据与日历最小存储；TASK-004A 真实主数据与日历验收；TASK-PLAN-DATA-QUALITY 历史行情/实体/日历/复权质量验收。
退出条件：真实主数据/日历/历史行情/复权/许可与可得时间可靠且缺口明确。
已证实验收进度：43%。

| TASK | 状态 | 来源 | 前置验收 |
| --- | --- | --- | --- |
| TASK-002 | PARTIAL | EXECUTED | 无 |
| TASK-004 | PARTIAL | EXECUTED | TASK-002:code,offline |
| TASK-004A | BLOCKED | EXECUTED | TASK-004:code,offline |
| TASK-003A | PARTIAL | EXECUTED | 无 |
| TASK-PLAN-FOUNDATION-REVIEW | PLANNED | SUGGESTION | TASK-002:code,offline; TASK-004:code,offline |
| TASK-PLAN-DATA-QUALITY | PLANNED | SUGGESTION | TASK-PLAN-FOUNDATION-REVIEW:review; TASK-004A:master_response,sqlite,review |

## S5 全 A 市场宽度与市场过滤（8%）

阶段依赖：S4。
交付：TASK-PLAN-BREADTH 全 A 市场宽度与过滤。
退出条件：已验收历史证券池上的全市场覆盖、过滤与缺失门禁通过。
已证实验收进度：0%。

| TASK | 状态 | 来源 | 前置验收 |
| --- | --- | --- | --- |
| TASK-PLAN-BREADTH | PLANNED | SUGGESTION | TASK-PLAN-DATA-QUALITY:全部强制 |

## S6 选股策略与评分（12%）

阶段依赖：S4, S5。
交付：TASK-PLAN-SELECTION 版本化选股规则与评分。
退出条件：评分口径/历史输入/排序解释与样本外规则冻结。
已证实验收进度：0%。

| TASK | 状态 | 来源 | 前置验收 |
| --- | --- | --- | --- |
| TASK-PLAN-SELECTION | PLANNED | SUGGESTION | TASK-PLAN-BREADTH:全部强制; TASK-PLAN-DATA-QUALITY:全部强制 |

## S7 风险管理与交易执行约束（10%）

阶段依赖：S4, S6。
交付：TASK-PLAN-RISK 风控与交易执行约束。
退出条件：停牌/涨跌停/可交易性/仓位/费用滑点及现金持仓约束通过。
已证实验收进度：0%。

| TASK | 状态 | 来源 | 前置验收 |
| --- | --- | --- | --- |
| TASK-PLAN-RISK | PLANNED | SUGGESTION | TASK-PLAN-DATA-QUALITY:全部强制; TASK-PLAN-SELECTION:全部强制 |

## S8 历史回测与无未来函数审查（20%）

阶段依赖：S4, S6, S7。
交付：TASK-PLAN-BACKTEST 历史回测执行与样本外测试；TASK-PLAN-BACKTEST-REVIEW 独立回测正确性与无未来函数验收。
退出条件：执行/记账/成本可复现，前置与事后独立未来函数审查及样本外测试通过。
已证实验收进度：0%。

| TASK | 状态 | 来源 | 前置验收 |
| --- | --- | --- | --- |
| TASK-PLAN-TIME-REVIEW | PLANNED | SUGGESTION | TASK-PLAN-DATA-QUALITY:全部强制; TASK-PLAN-RISK:design |
| TASK-PLAN-BACKTEST | PLANNED | SUGGESTION | TASK-PLAN-TIME-REVIEW:review; TASK-PLAN-SELECTION:全部强制; TASK-PLAN-RISK:全部强制 |
| TASK-PLAN-BACKTEST-REVIEW | PLANNED | SUGGESTION | TASK-PLAN-BACKTEST:implementation,offline |

## S9 每日报告与自动化运行（10%）

阶段依赖：S8。
交付：TASK-PLAN-REPORT 每日报告与静态产物；TASK-PLAN-AUTOMATION 人工批准的本地自动化运行。
退出条件：日报 schema/无敏感静态发布边界/人工批准调度及失败告警通过。
已证实验收进度：0%。

| TASK | 状态 | 来源 | 前置验收 |
| --- | --- | --- | --- |
| TASK-PLAN-REPORT | PLANNED | SUGGESTION | TASK-PLAN-BACKTEST:全部强制; TASK-PLAN-BACKTEST-REVIEW:review |
| TASK-PLAN-AUTOMATION | PLANNED | SUGGESTION | TASK-PLAN-REPORT:全部强制; TASK-015:review,live,calendar |

## S10 V1.3 端到端验收（5%）

阶段依赖：S9。
交付：TASK-PLAN-END-TO-END V1.3 全链路与生产准入。
退出条件：冻结版本和数据快照的端到端验收及人工生产准入批准；不自动接交易账户。
已证实验收进度：0%。

| TASK | 状态 | 来源 | 前置验收 |
| --- | --- | --- | --- |
| TASK-PLAN-END-TO-END | PLANNED | SUGGESTION | TASK-PLAN-AUTOMATION:全部强制; TASK-PLAN-BACKTEST-REVIEW:review; TASK-PLAN-DATA-QUALITY:全部强制 |

建议立项不代表任务已经创建。正式策略回测必须通过数据时点、主数据/日历/复权、执行约束及独立未来函数门禁；默认不发真实请求、不部署或接交易账户。

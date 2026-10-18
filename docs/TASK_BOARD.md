# V1.3 正式任务看板

<!-- Generated from TASK_METRICS.json; edit reviewed data, then --render. -->

数据截止：2026-10-19T07:09:15+08:00；计划版本 1.0。
**按首版规划口径的已证实完成率：21.8500%**；不是生产就绪率。

公式：Σ阶段权重 × Σ阶段内任务权重 × Σ有类型匹配证据的 PASS 验收点权重；三层均除以 100。
PLANNED/REJECTED 计零；PARTIAL/BLOCKED 仅计已有通过点。历史诊断任务权重为 0，避免反复修复增加项目分母或重复计分。
未验证与失败均不计分；代码、离线、真实源、UI、独立审查、PR、生产资格分列。所有旧结果是有日期的历史证据，不代表本轮实时可用。

模型列的指定值为唯一分配/续执行建议；actual=null 表示历史模型未知，绝不追溯伪造。实际工时未知保持 null；未来工时范围是未经实测的首版估计。
SUGGESTION 表示仅建议立项，尚未创建、执行或完成；READY 只表示已经批准且依赖满足。状态来自人工快照，重算不改变状态。
新模块/重要接口/依赖/高风险变更按[开源调研制度](OPEN_SOURCE_RESEARCH_POLICY.md)先检查已有研究及实际源码/测试/许可证；历史 TASK-REF-001 尚未自动获得通过结论。

## 下一项与阻塞

推荐：**TASK-018-REVIEW**（SUGGESTION）：先独立审查已交付治理/看板，绑定最终 SHA，避免未审规则继续扩散。

## 近期交付与实际能力

以下为当前快照引用、绑定提交的交付证据，不是新增正式任务或生产准入；原计划与权重保持不变。

- TASK-M2 研究交易分析 · PR #25 已合并：腾讯600000 / 2026-01-05～10-15真实187行，写入/读回均187，内置浏览器已展示MA5/10/20/60、ATR14、量比、研究评分与止损参考；CI 617 passed、1 skipped。研究评分40、正式候选0、市场数据不足；不等于正式策略/样本外回测/生产准入。（E-DELIVERY-25；提交 `5adfacdace69396d88b57b9a7a88b36aa7175c4a`）
- M1 行情工作台 · PR #24 已合并：本地查询与主动采集分开，价格/成交量图和明细共用SQLite数据。复用真实2行样本，刷新仍1批次/2版本，无新行情请求；CI 581 passed、1 skipped。仅临时演示库，不代表生产存储。（E-DELIVERY-24；提交 `fa2ac20152170719d35bb42b5dc694398a59ce15`）
- TASK-022A-H / M0 · PR #23 已合并：CFFEX 限定离线修复经独立复核，CI 568 passed、1 skipped；M0 腾讯600000 / 2026-10-14～15真实返回、写入、读回各2行，内置浏览器实际验收。CFFEX真实日历、持久仓储、R04和生产HTTPS仍未验收。（E-DELIVERY-23；提交 `a579f033b0ccb01efdc2855a577f1c2e6567d510`）
- TASK-018：PR #21 已合并，正式看板及开源调研制度已在 main；独立治理/看板审查仍未验证，不改写历史待审报告。（E-PROGRESS-21；提交 `2a5332448b32083ddbedc6b16ea0cf49057e3cb8`）

## 状态总表

| TASK / 名称 | 类型/优先级 | 唯一指定模型 / 实际模型 | 估计小时 / 实际小时 | 状态 / 验收率 | 前置条件 | 审查 / PR / 生产 |
| --- | --- | --- | --- | --- | --- | --- |
| TASK-001 · 七份架构与契约文档 [EXECUTED] | implementation/P0 | gpt-6.1-sol / 未知 | 未知 / 未知 | PASS / 100% | 无 | UNVERIFIED / 无/未创建 / NOT_RUN |
| TASK-GOV-001 · 模型路由治理 [EXECUTED] | implementation/P0 | gpt-6.1-sol / gpt-6.1-sol | 未知 / 未知 | PARTIAL / 70% | 无 | UNVERIFIED / #12 MERGED / NOT_RUN |
| TASK-016 · 分支与 worktree 审计 [EXECUTED] | implementation/P0 | gpt-6.1-sol / gpt-6.1-sol | 未知 / 未知 | PASS / 100% | 无 | UNVERIFIED / #19 MERGED / NOT_RUN |
| TASK-017 · 干净 main 与统一工作区 [EXECUTED] | implementation/P0 | gpt-6.1-sol / gpt-6.1-sol | 未知 / 未知 | PASS / 100% | TASK-016:audit | UNVERIFIED / #20 MERGED / NOT_RUN |
| TASK-018 · 正式任务看板与进度机制 [REQUESTED] | implementation/P0 | gpt-6.1-sol / gpt-6.1-sol | 6–12 / 未知 | PARTIAL / 85% | TASK-017:baseline,isolation; TASK-GOV-001:rules | UNVERIFIED / #21 MERGED / NOT_RUN |
| TASK-002 · SQLite 数据基础设施 [EXECUTED] | implementation/P0 | gpt-6.1-sol / 未知 | 未知 / 未知 | PARTIAL / 80% | 无 | UNVERIFIED / #1 MERGED / NOT_RUN |
| TASK-003 · AKShare 历史日线适配 [EXECUTED] | implementation/P0 | gpt-6.1-sol / 未知 | 未知 / 未知 | PARTIAL / 80% | TASK-002:code,offline | UNVERIFIED / #2 CLOSED, #5 MERGED / NOT_RUN |
| TASK-004 · 证券主数据与日历最小存储 [EXECUTED] | implementation/P0 | gpt-6.1-sol / 未知 | 未知 / 未知 | PARTIAL / 80% | TASK-002:code,offline | UNVERIFIED / #10 MERGED / NOT_RUN |
| TASK-004A · 真实主数据与日历验收 [EXECUTED] | acceptance/P0 | gpt-6.1-sol / 未知 | 未知 / 未知 | BLOCKED / 35% | TASK-004:code,offline | UNVERIFIED / #11 OPEN / NOT_RUN |
| TASK-009 · 腾讯候选源与 Demo 集成 [EXECUTED] | implementation/P0 | gpt-6.1-sol / gpt-6.1-sol | 未知 / 未知 | PARTIAL / 80% | TASK-003:code,offline | UNVERIFIED / #17 MERGED / NOT_RUN |
| TASK-015 · 健康检查与调度入口 [EXECUTED] | implementation/P0 | gpt-6.1-sol / gpt-6.1-sol | 未知 / 未知 | PARTIAL / 65% | TASK-009:code,offline | UNVERIFIED / #18 MERGED / NOT_RUN |
| TASK-REF-001 · 开源架构对标 [EXECUTED] | implementation/P0 | gpt-6.1-sol / 未知 | 未知 / 未知 | PARTIAL / 40% | 无 | UNVERIFIED / 无/未创建 / NOT_RUN |
| TASK-003A · SQLite/适配器审查与真实验收准备 [EXECUTED] | acceptance/P0 | gpt-6.1-sol / 未知 | 未知 / 未知 | PARTIAL / 40% | 无 | UNVERIFIED / 无/未创建 / NOT_RUN |
| TASK-003B · 环境与 TLS 阻塞诊断 [EXECUTED] | implementation/P0 | gpt-6.1-sol / 未知 | 未知 / 未知 | PARTIAL / 50% | 无 | UNVERIFIED / 无/未创建 / NOT_RUN |
| TASK-003C · TLS 路径与指定批次验收 [EXECUTED] | acceptance/P0 | gpt-6.1-sol / 未知 | 未知 / 未知 | PASS / 100% | 无 | UNVERIFIED / #3 CLOSED, #6 MERGED / NOT_RUN |
| TASK-LOCAL-DEMO-001 · 本地环境与 Demo 启动 [EXECUTED] | implementation/P0 | gpt-6.1-sol / 未知 | 未知 / 未知 | PARTIAL / 40% | 无 | UNVERIFIED / 无/未创建 / NOT_RUN |
| TASK-LOCAL-RECONCILE-001 · 本地/远端基线与点击去重 [EXECUTED] | implementation/P0 | gpt-6.1-sol / gpt-6.1-sol | 未知 / 未知 | PARTIAL / 50% | 无 | UNVERIFIED / #13 OPEN / NOT_RUN |
| TASK-DEMO-002 · network_error 安全异常链 [EXECUTED] | implementation/P0 | gpt-6.1-sol / gpt-6.1-sol | 未知 / 未知 | PASS / 100% | 无 | UNVERIFIED / #14 OPEN / NOT_RUN |
| TASK-DEMO-003 · 单次探针失败归因记录 [EXECUTED] | implementation/P0 | gpt-6.1-sol / gpt-6.1-sol | 未知 / 未知 | PASS / 100% | 无 | UNVERIFIED / #15 OPEN / NOT_RUN |
| TASK-DEMO-004 · 正式 SDK 单次直连诊断 [EXECUTED] | implementation/P0 | gpt-6.1-sol / gpt-6.1-sol | 未知 / 未知 | PASS / 100% | 无 | UNVERIFIED / #16 OPEN / NOT_RUN |
| TASK-DEMO-005 · 额外网络诊断本地材料 [EXECUTED] | implementation/P0 | gpt-6.1-sol / 未知 | 未知 / 未知 | PARTIAL / 40% | 无 | UNVERIFIED / 无/未创建 / NOT_RUN |
| TASK-DEMO-006 · 后续诊断本地材料 [EXECUTED] | implementation/P0 | gpt-6.1-sol / 未知 | 未知 / 未知 | PARTIAL / 40% | 无 | UNVERIFIED / 无/未创建 / NOT_RUN |
| TASK-008 · 腾讯备用候选 Demo [EXECUTED] | implementation/P0 | gpt-6.1-sol / 未知 | 未知 / 未知 | PARTIAL / 80% | 无 | UNVERIFIED / 无/未创建 / NOT_RUN |
| TASK-008A · 腾讯单批次最小真实验收 [EXECUTED] | acceptance/P0 | gpt-6.1-sol / 未知 | 未知 / 未知 | PASS / 100% | 无 | UNVERIFIED / 无/未创建 / NOT_RUN |
| TASK-008B · 腾讯生产适用性研究 [EXECUTED] | implementation/P0 | gpt-6.1-sol / 未知 | 未知 / 未知 | PARTIAL / 40% | 无 | UNVERIFIED / 无/未创建 / NOT_RUN |
| TASK-018-REVIEW · 看板权重/证据/独立页面审查 [SUGGESTION] | acceptance/P0 | gpt-6.1-sol / 未知 | 2–5 / 未知 | PLANNED / 0% | TASK-018:data,engine,offline,ui | UNVERIFIED / 无/未创建 / NOT_RUN |
| TASK-GOV-002 · 独立模型路由治理审查 [SUGGESTION] | acceptance/P0 | gpt-6.1-sol / 未知 | 2–5 / 未知 | PLANNED / 0% | TASK-GOV-001:rules,template | UNVERIFIED / 无/未创建 / NOT_RUN |
| TASK-PLAN-FOUNDATION-REVIEW · 数据库/主数据/时点独立审查 [SUGGESTION] | acceptance/P0 | gpt-6.1-sol / 未知 | 4–10 / 未知 | PLANNED / 0% | TASK-002:code,offline; TASK-004:code,offline | UNVERIFIED / 无/未创建 / NOT_RUN |
| TASK-PLAN-SOURCE-REVIEW · 双源适配与健康预算独立审查 [SUGGESTION] | acceptance/P0 | gpt-6.1-sol / 未知 | 4–10 / 未知 | PLANNED / 0% | TASK-009:code,offline; TASK-015:code,offline | UNVERIFIED / 无/未创建 / NOT_RUN |
| TASK-PLAN-DATA-QUALITY · 历史行情/实体/日历/复权质量验收 [SUGGESTION] | acceptance/P0 | gpt-6.1-sol / 未知 | 24–60 / 未知 | PLANNED / 0% | TASK-PLAN-FOUNDATION-REVIEW:review; TASK-004A:master_response,sqlite,review | UNVERIFIED / 无/未创建 / NOT_RUN |
| TASK-PLAN-BREADTH · 全 A 市场宽度与过滤 [SUGGESTION] | implementation/P1 | gpt-6.1-sol / 未知 | 16–40 / 未知 | PLANNED / 0% | TASK-PLAN-DATA-QUALITY:全部强制 | UNVERIFIED / 无/未创建 / NOT_RUN |
| TASK-PLAN-SELECTION · 版本化选股规则与评分 [SUGGESTION] | implementation/P1 | gpt-6.1-sol / 未知 | 20–50 / 未知 | PLANNED / 0% | TASK-PLAN-BREADTH:全部强制; TASK-PLAN-DATA-QUALITY:全部强制 | UNVERIFIED / 无/未创建 / NOT_RUN |
| TASK-PLAN-RISK · 风控与交易执行约束 [SUGGESTION] | implementation/P1 | gpt-6.1-sol / 未知 | 24–60 / 未知 | PLANNED / 0% | TASK-PLAN-DATA-QUALITY:全部强制; TASK-PLAN-SELECTION:全部强制 | UNVERIFIED / 无/未创建 / NOT_RUN |
| TASK-PLAN-TIME-REVIEW · 数据可得性/未来函数规则前置审查 [SUGGESTION] | acceptance/P1 | gpt-6.1-sol / 未知 | 8–20 / 未知 | PLANNED / 0% | TASK-PLAN-DATA-QUALITY:全部强制; TASK-PLAN-RISK:design | UNVERIFIED / 无/未创建 / NOT_RUN |
| TASK-PLAN-BACKTEST · 历史回测执行与样本外测试 [SUGGESTION] | implementation/P1 | gpt-6.1-sol / 未知 | 40–100 / 未知 | PLANNED / 0% | TASK-PLAN-TIME-REVIEW:review; TASK-PLAN-SELECTION:全部强制; TASK-PLAN-RISK:全部强制 | UNVERIFIED / 无/未创建 / NOT_RUN |
| TASK-PLAN-BACKTEST-REVIEW · 独立回测正确性与无未来函数验收 [SUGGESTION] | acceptance/P1 | gpt-6.1-sol / 未知 | 16–40 / 未知 | PLANNED / 0% | TASK-PLAN-BACKTEST:implementation,offline | UNVERIFIED / 无/未创建 / NOT_RUN |
| TASK-PLAN-REPORT · 每日报告与静态产物 [SUGGESTION] | implementation/P1 | gpt-6.1-sol / 未知 | 12–30 / 未知 | PLANNED / 0% | TASK-PLAN-BACKTEST:全部强制; TASK-PLAN-BACKTEST-REVIEW:review | UNVERIFIED / 无/未创建 / NOT_RUN |
| TASK-PLAN-AUTOMATION · 人工批准的本地自动化运行 [SUGGESTION] | implementation/P1 | gpt-6.1-sol / 未知 | 12–30 / 未知 | PLANNED / 0% | TASK-PLAN-REPORT:全部强制; TASK-015:review,live,calendar | UNVERIFIED / 无/未创建 / NOT_RUN |
| TASK-PLAN-END-TO-END · V1.3 全链路与生产准入 [SUGGESTION] | implementation/P1 | gpt-6.1-sol / 未知 | 16–40 / 未知 | PLANNED / 0% | TASK-PLAN-AUTOMATION:全部强制; TASK-PLAN-BACKTEST-REVIEW:review; TASK-PLAN-DATA-QUALITY:全部强制 | UNVERIFIED / 无/未创建 / NOT_RUN |
| TASK-PLAN-BOARD-POLISH · 低风险文档与展示改进 [SUGGESTION] | implementation/P0 | Agnes 3.0 Flash / 未知 | 2–6 / 未知 | PLANNED / 0% | TASK-018-REVIEW:review | UNVERIFIED / 无/未创建 / NOT_RUN |

## 逐项目标与验收

### TASK-001 · 七份架构与契约文档

目标：七份架构与契约文档；仅限所列验收范围。阶段 S2；阶段内权重 0%。
结果依据：由实际文档与 PR 状态导入，未证实项目保守保留；只计本任务范围（2026-10-18T07:37:07.731648+00:00）；快照序号 1。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| docs · 架构/数据/接口/决策/验收/计划/审计文档存在 | 100% | True | PASS | E-001 |

阻塞：无已记录阻塞；未通过验收点仍须完成。
后续候选（仍须满足其全部依赖）：按路线图人工规划，不自动创建。

### TASK-GOV-001 · 模型路由治理

目标：模型路由治理；仅限所列验收范围。阶段 S2；阶段内权重 40%。
结果依据：由实际文档与 PR 状态导入，未证实项目保守保留；只计本任务范围（2026-10-18T07:37:07.731648+00:00）；快照序号 2。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| rules · 规则与路由制度已落库 | 40% | True | PASS | E-GOV |
| template · 模板与开始纪律 | 20% | True | PASS | E-GOV |
| review · 独立治理审查 | 30% | True | UNVERIFIED | 无 |
| merge · 治理 PR 合并 | 10% | True | PASS | E-PR |

阻塞：无已记录阻塞；未通过验收点仍须完成。
后续候选（仍须满足其全部依赖）：TASK-018, TASK-GOV-002

### TASK-016 · 分支与 worktree 审计

目标：分支与 worktree 审计；仅限所列验收范围。阶段 S1；阶段内权重 40%。
结果依据：由实际文档与 PR 状态导入，未证实项目保守保留；只计本任务范围（2026-10-18T07:37:07.731648+00:00）；快照序号 3。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| audit · 审计与逐文件证据交付 | 50% | True | PASS | E-016 |
| preserve · 原现场保护 | 30% | True | PASS | E-016 |
| merge · 报告合并 | 20% | True | PASS | E-PR |

阻塞：无已记录阻塞；未通过验收点仍须完成。
后续候选（仍须满足其全部依赖）：TASK-017

### TASK-017 · 干净 main 与统一工作区

目标：干净 main 与统一工作区；仅限所列验收范围。阶段 S1；阶段内权重 60%。
结果依据：由实际文档与 PR 状态导入，未证实项目保守保留；只计本任务范围（2026-10-18T07:37:07.731648+00:00）；快照序号 4。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| baseline · 成功 ls-remote/fetch 核实 | 40% | True | PASS | E-017 |
| isolation · 干净 main/upstream/隔离 | 30% | True | PASS | E-017 |
| preserve · 原现场保护 | 20% | True | PASS | E-017 |
| report · 报告交付 | 10% | True | PASS | E-017 |

阻塞：无已记录阻塞；未通过验收点仍须完成。
后续候选（仍须满足其全部依赖）：TASK-018

### TASK-018 · 正式任务看板与进度机制

目标：正式任务看板与进度机制；仅限所列验收范围。阶段 S2；阶段内权重 60%。
结果依据：重新核实PR #21已合并，补记merge验收；引用后续M0/M1/M2及CFFEX交付证据，不新建正式任务、不改计划权重，研究Demo不计作正式策略通过。独立审查仍未验证。（2026-10-19T07:09:15+08:00）；快照序号 45。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| data · 结构化权重/文档一致 | 25% | True | PASS | E-018-code |
| engine · 重算/历史/依赖/候选反馈 | 25% | True | PASS | E-018-code |
| offline · 完整离线回归与隔离 | 15% | True | PASS | E-018-portable-offline |
| ui · 真实浏览器离线进度页 | 15% | True | PASS | E-018-ui |
| review · 独立审查最终 SHA | 15% | True | UNVERIFIED | 无 |
| merge · 看板 PR 合并 | 5% | True | PASS | E-PROGRESS-21 |

阻塞：独立治理/看板审查尚无通过证据；PR #21已合并不替代该门槛。
后续候选（仍须满足其全部依赖）：TASK-018-REVIEW

### TASK-002 · SQLite 数据基础设施

目标：SQLite 数据基础设施；仅限所列验收范围。阶段 S4；阶段内权重 20%。
结果依据：由实际文档与 PR 状态导入，未证实项目保守保留；只计本任务范围（2026-10-18T07:37:07.731648+00:00）；快照序号 6。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| code · 迁移/事务/版本/双时间实现 | 40% | True | PASS | E-002-code |
| offline · 真实临时 SQLite 离线测试 | 30% | True | PASS | E-002-offline |
| review · 独立正确性审查 | 20% | True | UNVERIFIED | 无 |
| merge · SQLite PR 合并 | 10% | True | PASS | E-PR |

阻塞：无已记录阻塞；未通过验收点仍须完成。
后续候选（仍须满足其全部依赖）：TASK-003, TASK-004, TASK-PLAN-FOUNDATION-REVIEW

### TASK-003 · AKShare 历史日线适配

目标：AKShare 历史日线适配；仅限所列验收范围。阶段 S3；阶段内权重 25%。
结果依据：由实际文档与 PR 状态导入，未证实项目保守保留；只计本任务范围（2026-10-18T07:37:07.731648+00:00）；快照序号 7。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| code · 字段映射与不复权采集 | 30% | True | PASS | E-003-code |
| offline · 离线契约/异常/事务测试 | 20% | True | PASS | E-003-offline |
| live · 历史指定批次真实请求（非当前版本认证） | 20% | True | PASS | E-003C-live |
| review · 独立适配边界审查 | 20% | True | UNVERIFIED | 无 |
| merge · 集成 PR 合并 | 10% | True | PASS | E-PR |

阻塞：无已记录阻塞；未通过验收点仍须完成。
后续候选（仍须满足其全部依赖）：TASK-009

### TASK-004 · 证券主数据与日历最小存储

目标：证券主数据与日历最小存储；仅限所列验收范围。阶段 S4；阶段内权重 25%。
结果依据：由实际文档与 PR 状态导入，未证实项目保守保留；只计本任务范围（2026-10-18T07:37:07.731648+00:00）；快照序号 8。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| code · 稳定身份/Schema v2/as_of 最小实现 | 40% | True | PASS | E-004-code |
| offline · 迁移/版本/未来隔离测试 | 30% | True | PASS | E-004-offline |
| review · 独立身份/时点审查 | 20% | True | UNVERIFIED | 无 |
| merge · 基础实现合并 | 10% | True | PASS | E-PR |

阻塞：无已记录阻塞；未通过验收点仍须完成。
后续候选（仍须满足其全部依赖）：TASK-004A, TASK-PLAN-FOUNDATION-REVIEW

### TASK-004A · 真实主数据与日历验收

目标：真实主数据与日历验收；仅限所列验收范围。阶段 S4；阶段内权重 20%。
结果依据：由实际文档与 PR 状态导入，未证实项目保守保留；只计本任务范围（2026-10-18T07:37:07.731648+00:00）；快照序号 9。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| research · 来源研究与覆盖说明 | 20% | True | PASS | E-016 |
| calendar_response · 仅历史新浪日历单次响应 | 15% | True | PASS | E-004A-live |
| master_response · 主数据真实字段响应 | 15% | True | FAIL | E-004A-live |
| sqlite · 真实参考数据写入/读回/版本 | 30% | True | UNVERIFIED | 无 |
| review · 时间/完整性独立验收 | 20% | True | UNVERIFIED | 无 |

阻塞：主数据历史探测 TLS 失败；真实事件/名称有效期、日历发布时刻与覆盖证据不足；不能倒填或从缺失推休市
后续候选（仍须满足其全部依赖）：TASK-PLAN-DATA-QUALITY

### TASK-009 · 腾讯候选源与 Demo 集成

目标：腾讯候选源与 Demo 集成；仅限所列验收范围。阶段 S3；阶段内权重 25%。
结果依据：PR #17的集成实现已在main；后续M0/M1/M2已分别验证腾讯真实样本和临时SQLite/UI（历史2行及187行），不是健康CLI或完整历史质量验收。独立集成边界审查、腾讯原始口径/授权等仍未知。（2026-10-19T07:09:15+08:00）；快照序号 46。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| code · 腾讯候选/来源/数值及 #13/#14 整合 | 40% | True | PASS | E-009-code |
| offline · 双源离线/SQLite/rerun 回归 | 30% | True | PASS | E-009-offline |
| review · 独立集成边界审查 | 20% | True | UNVERIFIED | 无 |
| merge · 集成 PR 合并 | 10% | True | PASS | E-PR |

阻塞：无已记录阻塞；未通过验收点仍须完成。
后续候选（仍须满足其全部依赖）：TASK-015, TASK-PLAN-SOURCE-REVIEW

### TASK-015 · 健康检查与调度入口

目标：健康检查与调度入口；仅限所列验收范围。阶段 S3；阶段内权重 50%。
结果依据：PR #18健康框架已合并；后续Demo真实成功不经过健康CLI，不能将live/calendar或freshness验收补为PASS；无独立连接探针/可靠日历expectation接线、未装OS计划任务的限制仍保留。（2026-10-19T07:09:15+08:00）；快照序号 47。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| code · 健康模型/预算/报告/CLI | 30% | True | PASS | E-015-code |
| offline · 默认离线与 412/1 回归 | 25% | True | PASS | E-015-offline |
| review · 独立证据与预算审查 | 20% | True | UNVERIFIED | 无 |
| merge · 框架 PR 合并 | 10% | True | PASS | E-PR |
| live · 当前健康路径真实验收 | 10% | True | UNVERIFIED | 无 |
| calendar · 可信日历/freshness CLI 验收 | 5% | True | UNVERIFIED | 无 |

阻塞：当前真实健康未知；无独立连接探针/已验收日历，CLI 尚无已验证 expectation 输入；未安装 OS 任务
后续候选（仍须满足其全部依赖）：TASK-PLAN-SOURCE-REVIEW, TASK-PLAN-AUTOMATION

### TASK-REF-001 · 开源架构对标

目标：开源架构对标；仅限所列验收范围。阶段 S2；阶段内权重 0%。
结果依据：只确认本地未跟踪研究报告存在；引用/许可证内容尚待独立审查，未进入 main（2026-10-18T07:37:07.731648+00:00）；快照序号 12。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| artifact · 已有交付或审计记录可追溯（非完整功能验收） | 40% | True | PASS | E-016 |
| acceptance · 剩余范围与独立验收 | 60% | True | UNVERIFIED | 无 |

阻塞：无已记录阻塞；未通过验收点仍须完成。
后续候选（仍须满足其全部依赖）：按路线图人工规划，不自动创建。

### TASK-003A · SQLite/适配器审查与真实验收准备

目标：SQLite/适配器审查与真实验收准备；仅限所列验收范围。阶段 S4；阶段内权重 0%。
结果依据：由实际文档与 PR 状态导入，未证实项目保守保留；只计本任务范围（2026-10-18T07:37:07.731648+00:00）；快照序号 13。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| artifact · 已有交付或审计记录可追溯（非完整功能验收） | 40% | True | PASS | E-016 |
| acceptance · 剩余范围与独立验收 | 60% | True | UNVERIFIED | 无 |

阻塞：无已记录阻塞；未通过验收点仍须完成。
后续候选（仍须满足其全部依赖）：按路线图人工规划，不自动创建。

### TASK-003B · 环境与 TLS 阻塞诊断

目标：环境与 TLS 阻塞诊断；仅限所列验收范围。阶段 S3；阶段内权重 0%。
结果依据：该批次 TLS 失败，不改写成成功；后续003C有另一批成功，不代表今天网络（2026-10-18T07:37:07.731648+00:00）；快照序号 14。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| environment · 依赖环境修复 | 25% | True | PASS | E-003B |
| offline · 补强验收断言与离线测试 | 25% | True | PASS | E-003B-offline |
| live · 该历史批次真实链路 | 50% | True | FAIL | E-003B |

阻塞：无已记录阻塞；未通过验收点仍须完成。
后续候选（仍须满足其全部依赖）：按路线图人工规划，不自动创建。

### TASK-003C · TLS 路径与指定批次验收

目标：TLS 路径与指定批次验收；仅限所列验收范围。阶段 S3；阶段内权重 0%。
结果依据：历史任务限定范围完成；单次成功不代表当前版本、长期网络或生产资格（2026-10-18T07:37:07.731648+00:00）；快照序号 15。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| diagnostic · 有界 TLS/代理诊断记录 | 20% | True | PASS | E-003C |
| offline · 历史诊断离线回归 | 20% | True | PASS | E-003C-offline |
| sample · 当时指定批次 HTTP/SDK/SQLite | 60% | True | PASS | E-003C-live |

阻塞：无已记录阻塞；未通过验收点仍须完成。
后续候选（仍须满足其全部依赖）：按路线图人工规划，不自动创建。

### TASK-LOCAL-DEMO-001 · 本地环境与 Demo 启动

目标：本地环境与 Demo 启动；仅限所列验收范围。阶段 S3；阶段内权重 0%。
结果依据：由实际文档与 PR 状态导入，未证实项目保守保留；只计本任务范围（2026-10-18T07:37:07.731648+00:00）；快照序号 16。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| artifact · 已有交付或审计记录可追溯（非完整功能验收） | 40% | True | PASS | E-LOCAL |
| acceptance · 剩余范围与独立验收 | 60% | True | UNVERIFIED | 无 |

阻塞：无已记录阻塞；未通过验收点仍须完成。
后续候选（仍须满足其全部依赖）：按路线图人工规划，不自动创建。

### TASK-LOCAL-RECONCILE-001 · 本地/远端基线与点击去重

目标：本地/远端基线与点击去重；仅限所列验收范围。阶段 S3；阶段内权重 0%。
结果依据：历史范围按报告导入，独立审查/生产资格仍单独未知（2026-10-18T07:37:07.731648+00:00）；快照序号 17。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| baseline · 基线/差异与点击修复报告 | 30% | True | PASS | E-LOCAL |
| offline · 离线回归 | 20% | True | PASS | E-LOCAL-offline |
| ui · 实机浏览器完整验收 | 25% | True | UNVERIFIED | 无 |
| live · 当前代码真实链路 | 25% | True | UNVERIFIED | 无 |

阻塞：无已记录阻塞；未通过验收点仍须完成。
后续候选（仍须满足其全部依赖）：按路线图人工规划，不自动创建。

### TASK-DEMO-002 · network_error 安全异常链

目标：network_error 安全异常链；仅限所列验收范围。阶段 S3；阶段内权重 0%。
结果依据：历史范围按报告导入，独立审查/生产资格仍单独未知（2026-10-18T07:37:07.731648+00:00）；快照序号 18。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| code · 安全异常链与证据核查 | 40% | True | PASS | E-DEMO002-code |
| offline · 离线回归 | 40% | True | PASS | E-DEMO002-offline |
| report · 故障证据边界报告 | 20% | True | PASS | E-DEMO002 |

阻塞：无已记录阻塞；未通过验收点仍须完成。
后续候选（仍须满足其全部依赖）：按路线图人工规划，不自动创建。

### TASK-DEMO-003 · 单次探针失败归因记录

目标：单次探针失败归因记录；仅限所列验收范围。阶段 S3；阶段内权重 0%。
结果依据：诊断记录限定范围交付，行情采集和根因未验收；开放报告PR不冒充已合并（2026-10-18T07:37:07.731648+00:00）；快照序号 19。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| report · 代理/TLS及手写GET实际证据 | 70% | True | PASS | E-016 |
| boundary · 未执行/未知/失败边界记录 | 30% | True | PASS | E-016 |

阻塞：无已记录阻塞；未通过验收点仍须完成。
后续候选（仍须满足其全部依赖）：按路线图人工规划，不自动创建。

### TASK-DEMO-004 · 正式 SDK 单次直连诊断

目标：正式 SDK 单次直连诊断；仅限所列验收范围。阶段 S3；阶段内权重 0%。
结果依据：有界诊断本身交付；真实请求RemoteDisconnected，无SDK帧/SQLite成功，根因未确认（2026-10-18T07:37:07.731648+00:00）；快照序号 20。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| report · 正式单次SDK请求审计 | 40% | True | PASS | E-016 |
| offline · 预算/重试/重定向/恢复控制测试 | 30% | True | PASS | E-DEMO004-offline |
| boundary · 最后成功阶段与证据边界 | 30% | True | PASS | E-016 |

阻塞：无已记录阻塞；未通过验收点仍须完成。
后续候选（仍须满足其全部依赖）：按路线图人工规划，不自动创建。

### TASK-DEMO-005 · 额外网络诊断本地材料

目标：额外网络诊断本地材料；仅限所列验收范围。阶段 S3；阶段内权重 0%。
结果依据：由实际文档与 PR 状态导入，未证实项目保守保留；只计本任务范围（2026-10-18T07:37:07.731648+00:00）；快照序号 21。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| artifact · 已有交付或审计记录可追溯（非完整功能验收） | 40% | True | PASS | E-016 |
| acceptance · 剩余范围与独立验收 | 60% | True | UNVERIFIED | 无 |

阻塞：无已记录阻塞；未通过验收点仍须完成。
后续候选（仍须满足其全部依赖）：按路线图人工规划，不自动创建。

### TASK-DEMO-006 · 后续诊断本地材料

目标：后续诊断本地材料；仅限所列验收范围。阶段 S3；阶段内权重 0%。
结果依据：由实际文档与 PR 状态导入，未证实项目保守保留；只计本任务范围（2026-10-18T07:37:07.731648+00:00）；快照序号 22。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| artifact · 已有交付或审计记录可追溯（非完整功能验收） | 40% | True | PASS | E-016 |
| acceptance · 剩余范围与独立验收 | 60% | True | UNVERIFIED | 无 |

阻塞：无已记录阻塞；未通过验收点仍须完成。
后续候选（仍须满足其全部依赖）：按路线图人工规划，不自动创建。

### TASK-008 · 腾讯备用候选 Demo

目标：腾讯备用候选 Demo；仅限所列验收范围。阶段 S3；阶段内权重 0%。
结果依据：原实现有后续009修复，样本成功不消除原始调整键和元数据问题；生产未验收（2026-10-18T07:37:07.731648+00:00）；快照序号 23。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| code · 腾讯候选 Demo 实现 | 30% | True | PASS | E-008-code |
| offline · 历史离线测试 | 20% | True | PASS | E-008-offline |
| sample · 旧 SDK 帧写入/读回样本 | 30% | True | PASS | E-008-live |
| boundary · 原始口径/来源/完整性后续复核 | 20% | True | UNVERIFIED | 无 |

阻塞：无已记录阻塞；未通过验收点仍须完成。
后续候选（仍须满足其全部依赖）：按路线图人工规划，不自动创建。

### TASK-008A · 腾讯单批次最小真实验收

目标：腾讯单批次最小真实验收；仅限所列验收范围。阶段 S3；阶段内权重 0%。
结果依据：仅历史最小样本验收通过；HTTP总数/原始调整键/许可/生产并未认证（2026-10-18T07:37:07.731648+00:00）；快照序号 24。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| sample · 历史腾讯 SDK 两行帧 | 40% | True | PASS | E-008-live |
| sqlite · 当时临时SQLite写入读回 | 30% | True | PASS | E-008-live |
| offline · 该报告记录的离线检查 | 30% | True | PASS | E-008A-offline |

阻塞：无已记录阻塞；未通过验收点仍须完成。
后续候选（仍须满足其全部依赖）：按路线图人工规划，不自动创建。

### TASK-008B · 腾讯生产适用性研究

目标：腾讯生产适用性研究；仅限所列验收范围。阶段 S3；阶段内权重 0%。
结果依据：由实际文档与 PR 状态导入，未证实项目保守保留；只计本任务范围（2026-10-18T07:37:07.731648+00:00）；快照序号 25。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| artifact · 已有交付或审计记录可追溯（非完整功能验收） | 40% | True | PASS | E-008B |
| acceptance · 剩余范围与独立验收 | 60% | True | UNVERIFIED | 无 |

阻塞：腾讯许可、原始调整键、去重前冲突、长期覆盖与时点证据未验收；不是生产通过
后续候选（仍须满足其全部依赖）：按路线图人工规划，不自动创建。

### TASK-018-REVIEW · 看板权重/证据/独立页面审查

目标：看板权重/证据/独立页面审查；仅限所列验收范围。阶段 S2；阶段内权重 0%。
结果依据：用户新增开源调研制度、AGENTS及任务模板入口，纳入后续独立H审查范围；审查任务仍只是建议，未创建/未执行（2026-10-18T07:56:07.816059+00:00）；快照序号 42。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| design · 契约/边界与可复核规则 | 20% | True | UNVERIFIED | 无 |
| implementation · 限定范围交付 | 30% | True | UNVERIFIED | 无 |
| offline · 隔离回归与失败路径 | 20% | True | UNVERIFIED | 无 |
| review · 独立审查/验收 | 30% | True | UNVERIFIED | 无 |

阻塞：无已记录阻塞；未通过验收点仍须完成。
后续候选（仍须满足其全部依赖）：TASK-PLAN-BOARD-POLISH

### TASK-GOV-002 · 独立模型路由治理审查

目标：独立模型路由治理审查；仅限所列验收范围。阶段 S2；阶段内权重 0%。
结果依据：仅建议立项，尚未创建或执行（2026-10-18T07:37:07.731648+00:00）；快照序号 27。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| design · 契约/边界与可复核规则 | 20% | True | UNVERIFIED | 无 |
| implementation · 限定范围交付 | 30% | True | UNVERIFIED | 无 |
| offline · 隔离回归与失败路径 | 20% | True | UNVERIFIED | 无 |
| review · 独立审查/验收 | 30% | True | UNVERIFIED | 无 |

阻塞：无已记录阻塞；未通过验收点仍须完成。
后续候选（仍须满足其全部依赖）：按路线图人工规划，不自动创建。

### TASK-PLAN-FOUNDATION-REVIEW · 数据库/主数据/时点独立审查

目标：数据库/主数据/时点独立审查；仅限所列验收范围。阶段 S4；阶段内权重 0%。
结果依据：仅建议立项，尚未创建或执行（2026-10-18T07:37:07.731648+00:00）；快照序号 28。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| design · 契约/边界与可复核规则 | 20% | True | UNVERIFIED | 无 |
| implementation · 限定范围交付 | 30% | True | UNVERIFIED | 无 |
| offline · 隔离回归与失败路径 | 20% | True | UNVERIFIED | 无 |
| review · 独立审查/验收 | 30% | True | UNVERIFIED | 无 |

阻塞：无已记录阻塞；未通过验收点仍须完成。
后续候选（仍须满足其全部依赖）：TASK-PLAN-DATA-QUALITY

### TASK-PLAN-SOURCE-REVIEW · 双源适配与健康预算独立审查

目标：双源适配与健康预算独立审查；仅限所列验收范围。阶段 S3；阶段内权重 0%。
结果依据：仅建议立项，尚未创建或执行（2026-10-18T07:37:07.731648+00:00）；快照序号 29。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| design · 契约/边界与可复核规则 | 20% | True | UNVERIFIED | 无 |
| implementation · 限定范围交付 | 30% | True | UNVERIFIED | 无 |
| offline · 隔离回归与失败路径 | 20% | True | UNVERIFIED | 无 |
| review · 独立审查/验收 | 30% | True | UNVERIFIED | 无 |

阻塞：无已记录阻塞；未通过验收点仍须完成。
后续候选（仍须满足其全部依赖）：按路线图人工规划，不自动创建。

### TASK-PLAN-DATA-QUALITY · 历史行情/实体/日历/复权质量验收

目标：历史行情/实体/日历/复权质量验收；仅限所列验收范围。阶段 S4；阶段内权重 35%。
结果依据：仅建议立项，尚未创建或执行（2026-10-18T07:37:07.731648+00:00）；快照序号 30。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| design · 契约/边界与可复核规则 | 20% | True | UNVERIFIED | 无 |
| implementation · 限定范围交付 | 30% | True | UNVERIFIED | 无 |
| offline · 隔离回归与失败路径 | 20% | True | UNVERIFIED | 无 |
| review · 独立审查/验收 | 30% | True | UNVERIFIED | 无 |

阻塞：TASK-PLAN-FOUNDATION-REVIEW:review；TASK-004A:blocked/rejected
后续候选（仍须满足其全部依赖）：TASK-PLAN-BREADTH, TASK-PLAN-SELECTION, TASK-PLAN-RISK, TASK-PLAN-TIME-REVIEW, TASK-PLAN-END-TO-END

### TASK-PLAN-BREADTH · 全 A 市场宽度与过滤

目标：全 A 市场宽度与过滤；仅限所列验收范围。阶段 S5；阶段内权重 100%。
结果依据：仅建议立项，尚未创建或执行（2026-10-18T07:37:07.731648+00:00）；快照序号 31。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| design · 契约/边界与可复核规则 | 20% | True | UNVERIFIED | 无 |
| implementation · 限定范围交付 | 30% | True | UNVERIFIED | 无 |
| offline · 隔离回归与失败路径 | 20% | True | UNVERIFIED | 无 |
| review · 独立审查/验收 | 30% | True | UNVERIFIED | 无 |

阻塞：TASK-PLAN-DATA-QUALITY:mandatory
后续候选（仍须满足其全部依赖）：TASK-PLAN-SELECTION

### TASK-PLAN-SELECTION · 版本化选股规则与评分

目标：版本化选股规则与评分；仅限所列验收范围。阶段 S6；阶段内权重 100%。
结果依据：仅建议立项，尚未创建或执行（2026-10-18T07:37:07.731648+00:00）；快照序号 32。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| design · 契约/边界与可复核规则 | 20% | True | UNVERIFIED | 无 |
| implementation · 限定范围交付 | 30% | True | UNVERIFIED | 无 |
| offline · 隔离回归与失败路径 | 20% | True | UNVERIFIED | 无 |
| review · 独立审查/验收 | 30% | True | UNVERIFIED | 无 |

阻塞：TASK-PLAN-BREADTH:mandatory；TASK-PLAN-DATA-QUALITY:mandatory
后续候选（仍须满足其全部依赖）：TASK-PLAN-RISK, TASK-PLAN-BACKTEST

### TASK-PLAN-RISK · 风控与交易执行约束

目标：风控与交易执行约束；仅限所列验收范围。阶段 S7；阶段内权重 100%。
结果依据：仅建议立项，尚未创建或执行（2026-10-18T07:37:07.731648+00:00）；快照序号 33。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| design · 契约/边界与可复核规则 | 20% | True | UNVERIFIED | 无 |
| implementation · 限定范围交付 | 30% | True | UNVERIFIED | 无 |
| offline · 隔离回归与失败路径 | 20% | True | UNVERIFIED | 无 |
| review · 独立审查/验收 | 30% | True | UNVERIFIED | 无 |

阻塞：TASK-PLAN-DATA-QUALITY:mandatory；TASK-PLAN-SELECTION:mandatory
后续候选（仍须满足其全部依赖）：TASK-PLAN-TIME-REVIEW, TASK-PLAN-BACKTEST

### TASK-PLAN-TIME-REVIEW · 数据可得性/未来函数规则前置审查

目标：数据可得性/未来函数规则前置审查；仅限所列验收范围。阶段 S8；阶段内权重 0%。
结果依据：仅建议立项，尚未创建或执行（2026-10-18T07:37:07.731648+00:00）；快照序号 34。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| design · 契约/边界与可复核规则 | 20% | True | UNVERIFIED | 无 |
| implementation · 限定范围交付 | 30% | True | UNVERIFIED | 无 |
| offline · 隔离回归与失败路径 | 20% | True | UNVERIFIED | 无 |
| review · 独立审查/验收 | 30% | True | UNVERIFIED | 无 |

阻塞：TASK-PLAN-DATA-QUALITY:mandatory；TASK-PLAN-RISK:design
后续候选（仍须满足其全部依赖）：TASK-PLAN-BACKTEST

### TASK-PLAN-BACKTEST · 历史回测执行与样本外测试

目标：历史回测执行与样本外测试；仅限所列验收范围。阶段 S8；阶段内权重 60%。
结果依据：仅建议立项，尚未创建或执行（2026-10-18T07:37:07.731648+00:00）；快照序号 35。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| design · 契约/边界与可复核规则 | 20% | True | UNVERIFIED | 无 |
| implementation · 限定范围交付 | 30% | True | UNVERIFIED | 无 |
| offline · 隔离回归与失败路径 | 20% | True | UNVERIFIED | 无 |
| review · 独立审查/验收 | 30% | True | UNVERIFIED | 无 |

阻塞：TASK-PLAN-TIME-REVIEW:review；TASK-PLAN-SELECTION:mandatory；TASK-PLAN-RISK:mandatory
后续候选（仍须满足其全部依赖）：TASK-PLAN-BACKTEST-REVIEW, TASK-PLAN-REPORT

### TASK-PLAN-BACKTEST-REVIEW · 独立回测正确性与无未来函数验收

目标：独立回测正确性与无未来函数验收；仅限所列验收范围。阶段 S8；阶段内权重 40%。
结果依据：仅建议立项，尚未创建或执行（2026-10-18T07:37:07.731648+00:00）；快照序号 36。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| design · 契约/边界与可复核规则 | 20% | True | UNVERIFIED | 无 |
| implementation · 限定范围交付 | 30% | True | UNVERIFIED | 无 |
| offline · 隔离回归与失败路径 | 20% | True | UNVERIFIED | 无 |
| review · 独立审查/验收 | 30% | True | UNVERIFIED | 无 |

阻塞：TASK-PLAN-BACKTEST:implementation；TASK-PLAN-BACKTEST:offline
后续候选（仍须满足其全部依赖）：TASK-PLAN-REPORT, TASK-PLAN-END-TO-END

### TASK-PLAN-REPORT · 每日报告与静态产物

目标：每日报告与静态产物；仅限所列验收范围。阶段 S9；阶段内权重 60%。
结果依据：仅建议立项，尚未创建或执行（2026-10-18T07:37:07.731648+00:00）；快照序号 37。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| design · 契约/边界与可复核规则 | 20% | True | UNVERIFIED | 无 |
| implementation · 限定范围交付 | 30% | True | UNVERIFIED | 无 |
| offline · 隔离回归与失败路径 | 20% | True | UNVERIFIED | 无 |
| review · 独立审查/验收 | 30% | True | UNVERIFIED | 无 |

阻塞：TASK-PLAN-BACKTEST:mandatory；TASK-PLAN-BACKTEST-REVIEW:review
后续候选（仍须满足其全部依赖）：TASK-PLAN-AUTOMATION

### TASK-PLAN-AUTOMATION · 人工批准的本地自动化运行

目标：人工批准的本地自动化运行；仅限所列验收范围。阶段 S9；阶段内权重 40%。
结果依据：仅建议立项，尚未创建或执行（2026-10-18T07:37:07.731648+00:00）；快照序号 38。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| design · 契约/边界与可复核规则 | 20% | True | UNVERIFIED | 无 |
| implementation · 限定范围交付 | 30% | True | UNVERIFIED | 无 |
| offline · 隔离回归与失败路径 | 20% | True | UNVERIFIED | 无 |
| review · 独立审查/验收 | 30% | True | UNVERIFIED | 无 |

阻塞：TASK-PLAN-REPORT:mandatory；TASK-015:review；TASK-015:live；TASK-015:calendar
后续候选（仍须满足其全部依赖）：TASK-PLAN-END-TO-END

### TASK-PLAN-END-TO-END · V1.3 全链路与生产准入

目标：V1.3 全链路与生产准入；仅限所列验收范围。阶段 S10；阶段内权重 100%。
结果依据：仅建议立项，尚未创建或执行（2026-10-18T07:37:07.731648+00:00）；快照序号 39。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| design · 契约/边界与可复核规则 | 20% | True | UNVERIFIED | 无 |
| implementation · 限定范围交付 | 30% | True | UNVERIFIED | 无 |
| offline · 隔离回归与失败路径 | 20% | True | UNVERIFIED | 无 |
| review · 独立审查/验收 | 30% | True | UNVERIFIED | 无 |

阻塞：TASK-PLAN-AUTOMATION:mandatory；TASK-PLAN-BACKTEST-REVIEW:review；TASK-PLAN-DATA-QUALITY:mandatory
后续候选（仍须满足其全部依赖）：按路线图人工规划，不自动创建。

### TASK-PLAN-BOARD-POLISH · 低风险文档与展示改进

目标：低风险文档与展示改进；仅限所列验收范围。阶段 S2；阶段内权重 0%。
结果依据：仅建议立项，尚未创建或执行（2026-10-18T07:37:07.731648+00:00）；快照序号 40。

| 验收点 | 权重 | 强制 | 实际状态 | 证据 ID |
| --- | --- | --- | --- | --- |
| design · 契约/边界与可复核规则 | 20% | True | UNVERIFIED | 无 |
| implementation · 限定范围交付 | 30% | True | UNVERIFIED | 无 |
| offline · 隔离回归与失败路径 | 20% | True | UNVERIFIED | 无 |
| review · 独立审查/验收 | 30% | True | UNVERIFIED | 无 |

阻塞：TASK-018-REVIEW:review
后续候选（仍须满足其全部依赖）：按路线图人工规划，不自动创建。

## 证据登记

| ID / 类型 | 固定来源 | 摘要及边界 |
| --- | --- | --- |
| E-PR / pr | docs/evidence/TASK_018_GITHUB.json | 本轮 API 核实 #1–#20；不代表独立审查或生产资格；SHA256 77b999ea109cbdd6baa2cf0e95ffb3292d9ab64e543e1634539d95e84184b633 |
| E-001 / report | docs/ARCHITECTURE.md | 历史已提交报告/文档，按其实际范围导入；未在本任务重做真实接口或独立审查；SHA256 3630604aefb67a983602cc9daf227658437d157d37f2cd38ae846810f4b48b3a |
| E-002 / report | docs/IMPLEMENTATION_TASK_002.md | 历史已提交报告/文档，按其实际范围导入；未在本任务重做真实接口或独立审查；SHA256 42811389e580de2be0d38a9cd50817215fbb548fb6816cfba9bf903626af7d00 |
| E-002-code / code | docs/IMPLEMENTATION_TASK_002.md | 历史报告所记录的code结果；不是本轮重新执行或生产认证；SHA256 42811389e580de2be0d38a9cd50817215fbb548fb6816cfba9bf903626af7d00 |
| E-002-offline / offline | docs/IMPLEMENTATION_TASK_002.md | 历史报告所记录的offline结果；不是本轮重新执行或生产认证；SHA256 42811389e580de2be0d38a9cd50817215fbb548fb6816cfba9bf903626af7d00 |
| E-003 / report | docs/IMPLEMENTATION_TASK_003.md | 历史已提交报告/文档，按其实际范围导入；未在本任务重做真实接口或独立审查；SHA256 c3b459598586d286c90c889caa63f83daec7282e8aa21404677ca5f58dc6d9fc |
| E-003-code / code | docs/IMPLEMENTATION_TASK_003.md | 历史报告所记录的code结果；不是本轮重新执行或生产认证；SHA256 c3b459598586d286c90c889caa63f83daec7282e8aa21404677ca5f58dc6d9fc |
| E-003-offline / offline | docs/IMPLEMENTATION_TASK_003.md | 历史报告所记录的offline结果；不是本轮重新执行或生产认证；SHA256 c3b459598586d286c90c889caa63f83daec7282e8aa21404677ca5f58dc6d9fc |
| E-003B / report | docs/IMPLEMENTATION_TASK_003B.md | 历史已提交报告/文档，按其实际范围导入；未在本任务重做真实接口或独立审查；SHA256 c8ec86e8c6f0efa9fe5dc60683364e26f51903fc59d5850c74ceffaa24f99718 |
| E-003B-code / code | docs/IMPLEMENTATION_TASK_003B.md | 历史报告所记录的code结果；不是本轮重新执行或生产认证；SHA256 c8ec86e8c6f0efa9fe5dc60683364e26f51903fc59d5850c74ceffaa24f99718 |
| E-003B-offline / offline | docs/IMPLEMENTATION_TASK_003B.md | 历史报告所记录的offline结果；不是本轮重新执行或生产认证；SHA256 c8ec86e8c6f0efa9fe5dc60683364e26f51903fc59d5850c74ceffaa24f99718 |
| E-003C / report | docs/IMPLEMENTATION_TASK_003C.md | 历史已提交报告/文档，按其实际范围导入；未在本任务重做真实接口或独立审查；SHA256 85dbf4f350c26be97e668af766f8f1a3fec327ee2d7653763c009f98b891b901 |
| E-003C-code / code | docs/IMPLEMENTATION_TASK_003C.md | 历史报告所记录的code结果；不是本轮重新执行或生产认证；SHA256 85dbf4f350c26be97e668af766f8f1a3fec327ee2d7653763c009f98b891b901 |
| E-003C-offline / offline | docs/IMPLEMENTATION_TASK_003C.md | 历史报告所记录的offline结果；不是本轮重新执行或生产认证；SHA256 85dbf4f350c26be97e668af766f8f1a3fec327ee2d7653763c009f98b891b901 |
| E-004 / report | docs/IMPLEMENTATION_TASK_004.md | 历史已提交报告/文档，按其实际范围导入；未在本任务重做真实接口或独立审查；SHA256 13d435a30a0f71daa54ae37aa7fecdca9787558699683d8547417aed8de748e2 |
| E-004-code / code | docs/IMPLEMENTATION_TASK_004.md | 历史报告所记录的code结果；不是本轮重新执行或生产认证；SHA256 13d435a30a0f71daa54ae37aa7fecdca9787558699683d8547417aed8de748e2 |
| E-004-offline / offline | docs/IMPLEMENTATION_TASK_004.md | 历史报告所记录的offline结果；不是本轮重新执行或生产认证；SHA256 13d435a30a0f71daa54ae37aa7fecdca9787558699683d8547417aed8de748e2 |
| E-008 / report | docs/IMPLEMENTATION_TASK_008.md | 历史已提交报告/文档，按其实际范围导入；未在本任务重做真实接口或独立审查；SHA256 a8d81bc536dc2123ea2e950fe753b629f043012c4d449bd8cfd417583ad2100d |
| E-008-code / code | docs/IMPLEMENTATION_TASK_008.md | 历史报告所记录的code结果；不是本轮重新执行或生产认证；SHA256 a8d81bc536dc2123ea2e950fe753b629f043012c4d449bd8cfd417583ad2100d |
| E-008-offline / offline | docs/IMPLEMENTATION_TASK_008.md | 历史报告所记录的offline结果；不是本轮重新执行或生产认证；SHA256 a8d81bc536dc2123ea2e950fe753b629f043012c4d449bd8cfd417583ad2100d |
| E-008A / report | docs/IMPLEMENTATION_TASK_008A.md | 历史已提交报告/文档，按其实际范围导入；未在本任务重做真实接口或独立审查；SHA256 745a074456a2d36f4b8a9ce7a727febe575d330143fac40a1140c4a1cc6f84bd |
| E-008A-code / code | docs/IMPLEMENTATION_TASK_008A.md | 历史报告所记录的code结果；不是本轮重新执行或生产认证；SHA256 745a074456a2d36f4b8a9ce7a727febe575d330143fac40a1140c4a1cc6f84bd |
| E-008A-offline / offline | docs/IMPLEMENTATION_TASK_008A.md | 历史报告所记录的offline结果；不是本轮重新执行或生产认证；SHA256 745a074456a2d36f4b8a9ce7a727febe575d330143fac40a1140c4a1cc6f84bd |
| E-008B / report | docs/IMPLEMENTATION_TASK_008B.md | 历史已提交报告/文档，按其实际范围导入；未在本任务重做真实接口或独立审查；SHA256 320430623284616e6957cdeda987c90a67b4413473fd450aa0a7d774fb16c65c |
| E-009 / report | docs/IMPLEMENTATION_TASK_009.md | 历史已提交报告/文档，按其实际范围导入；未在本任务重做真实接口或独立审查；SHA256 e319aa8fad63f18ce715b2bb2dad6f4bd412662186ec80c2dfefecad6bc0c342 |
| E-009-code / code | docs/IMPLEMENTATION_TASK_009.md | 历史报告所记录的code结果；不是本轮重新执行或生产认证；SHA256 e319aa8fad63f18ce715b2bb2dad6f4bd412662186ec80c2dfefecad6bc0c342 |
| E-009-offline / offline | docs/IMPLEMENTATION_TASK_009.md | 历史报告所记录的offline结果；不是本轮重新执行或生产认证；SHA256 e319aa8fad63f18ce715b2bb2dad6f4bd412662186ec80c2dfefecad6bc0c342 |
| E-015 / report | docs/IMPLEMENTATION_TASK_015.md | 历史已提交报告/文档，按其实际范围导入；未在本任务重做真实接口或独立审查；SHA256 552b336625812dcede2d9d86dd5fab5524bf4faf8944ca7a5bbc2dc76a7d65d6 |
| E-015-code / code | docs/IMPLEMENTATION_TASK_015.md | 历史报告所记录的code结果；不是本轮重新执行或生产认证；SHA256 552b336625812dcede2d9d86dd5fab5524bf4faf8944ca7a5bbc2dc76a7d65d6 |
| E-015-offline / offline | docs/IMPLEMENTATION_TASK_015.md | 历史报告所记录的offline结果；不是本轮重新执行或生产认证；SHA256 552b336625812dcede2d9d86dd5fab5524bf4faf8944ca7a5bbc2dc76a7d65d6 |
| E-016 / report | docs/IMPLEMENTATION_TASK_016.md | 历史已提交报告/文档，按其实际范围导入；未在本任务重做真实接口或独立审查；SHA256 a170ffe1b686a9644e0e18777a5aeeadc342193857150cce3f2413a2b3680ab3 |
| E-016-code / code | docs/IMPLEMENTATION_TASK_016.md | 历史报告所记录的code结果；不是本轮重新执行或生产认证；SHA256 a170ffe1b686a9644e0e18777a5aeeadc342193857150cce3f2413a2b3680ab3 |
| E-016-offline / offline | docs/IMPLEMENTATION_TASK_016.md | 历史报告所记录的offline结果；不是本轮重新执行或生产认证；SHA256 a170ffe1b686a9644e0e18777a5aeeadc342193857150cce3f2413a2b3680ab3 |
| E-017 / report | docs/IMPLEMENTATION_TASK_017.md | 历史已提交报告/文档，按其实际范围导入；未在本任务重做真实接口或独立审查；SHA256 421ecfd990f005c15762bcd6ae1f98aeab661464ae40fd3ddaf803d9ccc7ec43 |
| E-017-code / code | docs/IMPLEMENTATION_TASK_017.md | 历史报告所记录的code结果；不是本轮重新执行或生产认证；SHA256 421ecfd990f005c15762bcd6ae1f98aeab661464ae40fd3ddaf803d9ccc7ec43 |
| E-017-offline / offline | docs/IMPLEMENTATION_TASK_017.md | 历史报告所记录的offline结果；不是本轮重新执行或生产认证；SHA256 421ecfd990f005c15762bcd6ae1f98aeab661464ae40fd3ddaf803d9ccc7ec43 |
| E-DEMO002 / report | docs/IMPLEMENTATION_TASK_DEMO_002.md | 历史已提交报告/文档，按其实际范围导入；未在本任务重做真实接口或独立审查；SHA256 ce45ce43bf7de87d7e3c782d2a71c8a0de154222b35253a1dced25f2d3c86961 |
| E-DEMO002-code / code | docs/IMPLEMENTATION_TASK_DEMO_002.md | 历史报告所记录的code结果；不是本轮重新执行或生产认证；SHA256 ce45ce43bf7de87d7e3c782d2a71c8a0de154222b35253a1dced25f2d3c86961 |
| E-DEMO002-offline / offline | docs/IMPLEMENTATION_TASK_DEMO_002.md | 历史报告所记录的offline结果；不是本轮重新执行或生产认证；SHA256 ce45ce43bf7de87d7e3c782d2a71c8a0de154222b35253a1dced25f2d3c86961 |
| E-LOCAL / report | docs/IMPLEMENTATION_TASK_LOCAL_RECONCILE_001.md | 历史已提交报告/文档，按其实际范围导入；未在本任务重做真实接口或独立审查；SHA256 38efd295214134c28a8ac0b63d7eca36aef29557530526a182bb1ac01eb658cd |
| E-LOCAL-code / code | docs/IMPLEMENTATION_TASK_LOCAL_RECONCILE_001.md | 历史报告所记录的code结果；不是本轮重新执行或生产认证；SHA256 38efd295214134c28a8ac0b63d7eca36aef29557530526a182bb1ac01eb658cd |
| E-LOCAL-offline / offline | docs/IMPLEMENTATION_TASK_LOCAL_RECONCILE_001.md | 历史报告所记录的offline结果；不是本轮重新执行或生产认证；SHA256 38efd295214134c28a8ac0b63d7eca36aef29557530526a182bb1ac01eb658cd |
| E-GOV / report | docs/MODEL_ROUTING_POLICY.md | 历史已提交报告/文档，按其实际范围导入；未在本任务重做真实接口或独立审查；SHA256 d001488ebfbd6a1ba6de1cfd3d4f92d26ac03bbc1d69ab1a22ffb44d0170e57f |
| E-003C-live / live | docs/IMPLEMENTATION_TASK_003C.md | 仅 TASK-003C 当时指定批次 HTTP/SDK/SQLite 成功；不能认证现在的连接或代码版本；SHA256 85dbf4f350c26be97e668af766f8f1a3fec327ee2d7653763c009f98b891b901 |
| E-008-live / live | docs/evidence/TASK_008_AUDIT.json | TASK-009 复核过的旧腾讯 2 行样本；SDK 调用计数不等于 GET 数，原始调整键/授权未知；SHA256 92ee1d61b7ca63a5bd982bb6ff6a4e609f00dc7fa3b97a3b1d471a4297c9a6ae |
| E-004A-live / live | docs/IMPLEMENTATION_TASK_016.md | 审计记录：004A 新浪一次响应 8797 日期，主数据 TLS 失败；参考数据真实入库未执行；SHA256 a170ffe1b686a9644e0e18777a5aeeadc342193857150cce3f2413a2b3680ab3 |
| E-DEMO004-offline / offline | https://github.com/fengjnah/a-share-quant-v1/blob/d4701c826ca1eed65074b48ffc6da90e6ff908ad/docs/IMPLEMENTATION_TASK_DEMO_004.md | 已实际读取原报告：333 passed/1 skipped，四项控制测试；并非当前main已集成或本轮真实源成功；SHA256 6bca8a2f1ff3f05e1006ee48e06aea5d18d572a1456c0cb6535700b2569d505b |
| E-018-code / code | docs/evidence/TASK_018_ACCEPTANCE.json | 本任务结构/引擎/只读候选功能完成并通过检查，非独立审查；SHA256 659ecf7100b519564002a76fe5e47a86b4e0316ac245afdad2f977da56cbfef6 |
| E-018-offline / offline | docs/evidence/TASK_018_ACCEPTANCE.json | 实际完整 444 passed/1 skipped 与默认网络阻断、隔离验证；非真实行情；SHA256 659ecf7100b519564002a76fe5e47a86b4e0316ac245afdad2f977da56cbfef6 |
| E-018-ui / ui | docs/evidence/TASK_018_ACCEPTANCE.json | 实际 Codex 内置浏览器进度页/行情故障隔离/任务详情，非 Edge 或 Chrome 系统浏览器认证；SHA256 659ecf7100b519564002a76fe5e47a86b4e0316ac245afdad2f977da56cbfef6 |
| E-018-oss-policy / report | docs/OPEN_SOURCE_RESEARCH_POLICY.md | 用户在TASK-018明确增加的开源调研制度：实际源码/测试/许可/数据授权/时点风险/采用决定；已写入规则与模板，待独立H审查；没有新增外部调研或许可证验收；SHA256 d60326ae866ed0f71c064d53363513732b3f1a5768bc6ef7b329072548eb9246 |
| E-018-final-offline / offline | docs/evidence/TASK_018_FINAL_CHECKS.json | 新增制度入口及最终代码实际445 passed/1 skipped，pip check/Schema/历史前缀/有限链接检查通过；不是独立审查或真实源验收；SHA256 1e21539aed22f2ea205155cd3e6e3b6aaa7555f127a4e9b6108c8f713a942fad |
| E-018-delivery-pr / pr | docs/evidence/TASK_018_DELIVERY.json | 实际创建Draft PR #21，OPEN/未合并；快照早于本次追加提交，不冒充审查或合并通过；SHA256 8b4a14640bf5c5d9e8e69f3ba6171a5b697e50f4936bef893e8a747b06de8224 |
| E-018-portable-offline / offline | docs/evidence/TASK_018_DELIVERY.json | 最终完整离线446 passed/1 skipped、44.44秒，明确包含中间失败及修复；不是实际Linux或真实行情验收；SHA256 8b4a14640bf5c5d9e8e69f3ba6171a5b697e50f4936bef893e8a747b06de8224 |
| E-018-hash-format / report | docs/evidence/TASK_018_HASH_FORMAT.json | 显式保留50条原始Windows CRLF字节哈希，新证据默认UTF-8 LF；只重建已记录换行，不忽略其他内容；SHA256 f350b7792e272da3d4c44564a214677aaccd095086e8fec1f656286965498a77 |
| E-PROGRESS-21 / pr | docs/evidence/PROJECT_PROGRESS_20261019.json | TASK-018：PR #21 已合并，正式看板及开源调研制度已在 main；独立治理/看板审查仍未验证，不改写历史待审报告。；SHA256 16711947f427f2d5d9e4a653a94bde39805858a7e8c81707ef3c3f5e1ffa2953 |
| E-DELIVERY-23 / pr | docs/evidence/PROJECT_PROGRESS_20261019.json | TASK-022A-H / M0 · PR #23 已合并：CFFEX 限定离线修复经独立复核，CI 568 passed、1 skipped；M0 腾讯600000 / 2026-10-14～15真实返回、写入、读回各2行，内置浏览器实际验收。CFFEX真实日历、持久仓储、R04和生产HTTPS仍未验收。；SHA256 16711947f427f2d5d9e4a653a94bde39805858a7e8c81707ef3c3f5e1ffa2953 |
| E-DELIVERY-24 / pr | docs/evidence/PROJECT_PROGRESS_20261019.json | M1 行情工作台 · PR #24 已合并：本地查询与主动采集分开，价格/成交量图和明细共用SQLite数据。复用真实2行样本，刷新仍1批次/2版本，无新行情请求；CI 581 passed、1 skipped。仅临时演示库，不代表生产存储。；SHA256 16711947f427f2d5d9e4a653a94bde39805858a7e8c81707ef3c3f5e1ffa2953 |
| E-DELIVERY-25 / pr | docs/evidence/PROJECT_PROGRESS_20261019.json | TASK-M2 研究交易分析 · PR #25 已合并：腾讯600000 / 2026-01-05～10-15真实187行，写入/读回均187，内置浏览器已展示MA5/10/20/60、ATR14、量比、研究评分与止损参考；CI 617 passed、1 skipped。研究评分40、正式候选0、市场数据不足；不等于正式策略/样本外回测/生产准入。；SHA256 16711947f427f2d5d9e4a653a94bde39805858a7e8c81707ef3c3f5e1ffa2953 |
| E-M2-LIVE / live | docs/evidence/PROJECT_PROGRESS_20261019.json | PR #25 收尾记录与本机脱敏摘要交叉核对：腾讯187/187/187，响应SHA256和时间见快照；HTTP状态及GET总数未观测。本轮仅复核既有证据，不重发行情请求。；SHA256 16711947f427f2d5d9e4a653a94bde39805858a7e8c81707ef3c3f5e1ffa2953 |
| E-M2-UI / ui | docs/evidence/PROJECT_PROGRESS_20261019.json | M0/M1/M2 的内置浏览器历史操作见PR #23～25；M2指标及候选/排除/止损参考实际展示。未验证Edge/Chrome；不能把历史界面观察视为本轮页面验收。；SHA256 16711947f427f2d5d9e4a653a94bde39805858a7e8c81707ef3c3f5e1ffa2953 |
| E-M2-OFFLINE / offline | docs/evidence/PROJECT_PROGRESS_20261019.json | PR #25 head c76c09e 的CI39138829139为617 passed、1 skipped；本地完整同数量。只记录历史回归，不冒充本次修改后的测试。；SHA256 16711947f427f2d5d9e4a653a94bde39805858a7e8c81707ef3c3f5e1ffa2953 |

## 反馈与重算操作

使用 `python -m ai_trade.project_progress --check-docs` 验证 JSON Schema、权重、依赖图、事件链和两份 Markdown 一致性。
`python -m ai_trade.project_progress` 只读重算，退出码 0 仅代表管理数据合法，不代表业务通过。
手工结束任务后，将完整新快照及新证据写入 feedback.json，使用 `--propose feedback.json --candidate <新路径>` 生成独占候选文件；不改变正式 TASK_METRICS 或任何状态。
审查差异并通过独立 PR 接纳候选，保留旧 events/evidence 为完全相同前缀；再显式 `--render` 生成两个 Markdown。权重/任务定义/验收门槛变更需独立计划修订及审查，不由反馈命令放宽。
使用 `--baseline <可信旧版 TASK_METRICS.json>` 核对历史前缀；仅哈希链不能防止整链被重算，没有可信旧版时仍必须审查 Git diff。计划修订需在单独人工 PR 中保留旧计划/Git SHA 和审查依据；普通反馈入口只允许同版本追加。
候选反馈结构为 `{"event": <完整快照，不含 seq/hash/previous_hash>, "new_evidence": [...]}`；可从最新对应快照复制，填写 at/state/results/blockers/reason/basis/工时/审查/PR/生产，不复用未适用的通过证据。
只读 `--simulate TASK-ID ACCEPTANCE-ID FAIL` 展示验收点失败后的分数和下游阻塞，不写文件或发网络。新证据需记录来源、SHA256、类型、时点和适用范围；证据内容真实性仍需人工/独立审查，Schema 不是真实性认证。
未知模型/工时/许可证/真实可用性不会自动补齐，GitHub 不会被页面后台轮询。首版阶段和任务分配是规划参数，不是开发耗时或收益预测。

文本证据新 SHA256 按 UTF-8 LF 计算；既有 Windows CRLF 哈希的明确 ID 清单见 [TASK_018_HASH_FORMAT](evidence/TASK_018_HASH_FORMAT.json)，核验时只重建已记录换行，不忽略其他字节。

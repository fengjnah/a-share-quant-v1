# TASK-M3-CORE-DATA-MODEL-001

类型：H implementation，P0；当前仅完成阶段1与阶段2—4方案，实施待批准，整体未完成。

唯一执行配置：OpenAI / Codex Desktop **gpt-6.1-sol / high**。本会话turn_context `2026-10-21T23:11:29.694Z`实测；无子代理或其他模型；费用UNKNOWN。阶段1预算90分钟，单项最多两次有不同依据的修复，契约冲突按G10只读记录/停止相关实施。

GitHub main基线 `04e530871e2c8b4889c60027ac8d1ec4275009a2`；PR49已合并，head `0de70e19bd6ed006dd74b3ea8942dd3691f26d31`、base `603715b08b40dfa33ff75987bd21f5d193f7e5a1`、merge `31279e92a2baeb24a2785b383da26a35e67c1b7f`。独立分支 `codex/m3-core-data-model-001`，工作区 `F:/codex-agnes/AI-trade-m3-core-data-model-001`。原AI-trade/AI-trade-dev、2条stash与所有旧worktree保留。

已读AGENTS、MODEL_ROUTING_POLICY v1、TASK_TEMPLATE、PROJECT_STATUS、DECISIONS、DATA/INTERFACE/M3_CORE契约、OPEN_SOURCE_RESEARCH_POLICY v1、架构六文档、正式工作台/七表源码及Repository、M3输入/核心/页面/管线、CFFEX解析/模型/时间/版本及相关现有测试。无下级AGENTS/override。适用G01—G12；本期字段字典沿用PR49 B/R/A；不把合并/CI当独立H或来源认证。

允许：只读源码/配置/已确认库的mode=ro检查；新增方案、字典摘录、机器证据。用户要求先核验并提交最小方案、实现经批准模型，故未获本期方案确认前不新增SQL/迁移/业务/测试。禁止正式库写入/初始化/迁移、旧数据回填、行情请求、应用启动/刷新、AWS/EC2/代理/TLS/生产配置、自动合并/清理。

调研：适用，复用PR49/本地版本/事务与失败测试；仅补读4份SQLite官方事务/外键/备份/PRAGMA文档，无新库/框架或上游源码采用，无新增依赖，数据授权仍UNKNOWN。采用/拒绝与具体缺口见审计。

交付：

- [只读审计与实施方案](../audits/TASK-M3-CORE-DATA-MODEL-001.md)。
- [本期24表完整字段契约](../architecture/M3_CORE_DATA_MODEL_DICTIONARY.md)，原字典片段逐字固定，不重命名/删字段。
- [只读数据库/源码/字段证据](../evidence/TASK_M3_CORE_DATA_MODEL_001_AUDIT.json)。
- 本任务记录。没有实现24表、Schema升级、Repository或来源接入。

本轮D：2026-10-22 07:16:13+08:00只读实连正式workbench.sqlite3，v2/账本2/六业务表0；quick_check ok、FK空、物理DDL与已发布SQL一致，v1/v2 checksum一致；文件和侧车前后未变。不是用历史样本数量推断当前库。现有旧pipeline-bundle仅以JSON/hash只读核对，12个诊断不算正式库或页面已消费。

发现：R04与legacy rank0/空会员UQ存在真实适配差异；A07缺raw逐日trace；B15/A01有B09/A17硬依赖；新registry直接安装会破坏现有v2严格入口。方案保留这些差异与最小处理，不改源/测试期望绕过。

验收：本阶段仅静态字典/引用/基线/范围及只读DB检查；pytest/迁移/备份恢复/新Repository测试NOT RUN，批准后在独立临时库执行。真实接口/UI/样本外/发布NOT RUN。Draft PR使用[skip ci]避免方案阶段主动执行会建临时库的实现测试；不改变workflow或合并要求，不宣称CI通过。实际静态结果记录在机器证据，最终SHA/PR绑定在PR正文。

本轮静态结果：24节字段契约逐字匹配、15表延期、10个本地链接和7个固定源码行号锚点检查通过；69份基线文件匹配；JSON/Markdown围栏与git diff检查通过。`python -m pip check`：No broken requirements found / exit0。仅4份docs文件；这些检查不是迁移执行或新模型自动化测试。

独立H计划：`TASK-M3-CORE-DATA-MODEL-001-REVIEW`，待单独指派唯一配置；先审24表/范围/因子trace/兼容契约，实施后绑定最终SHA再审迁移/封存/时间/失败/重放。架构、核心与正式库既有H状态仍披露，未独立通过不解除门禁。正式库迁移、真实来源小样本/许可、页面指定run接线、EC2发布分别另批。

下一步最小动作：用户确认方案与C1—C5处理范围，完成所需独立设计复核，再在同一固定模型配置下实施批准的隔离模型。不把本阶段方案交付标成全TASK完成。

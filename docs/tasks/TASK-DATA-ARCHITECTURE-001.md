# TASK-DATA-ARCHITECTURE-001：三层持久化设计

## 执行配置与基线

| 项目 | 已核验值 |
| --- | --- |
| 类型 / 等级 | architecture design / H，涉及版本、时点、迁移与发布边界；只设计、不实施 |
| 唯一执行配置 | OpenAI / Codex Desktop `gpt-6.1-sol`，固定 `high`；2026-10-21 本会话 rollout 的最后 turn_context 实际核验；费用/额度 UNKNOWN，不委派、不调用其他模型 |
| 预算 / 失败上限 | 一轮有界源码复核及文档交付；同项最多两次不同诊断修复，核心矛盾停止依赖设计；不将未知预算当无限调用许可 |
| 最新 main | 恢复时GitHub API核实`c4b682d12c7c8dc42f75e717b855238f635ce05b`，tree `df7280c74a3468b41e1ca08c3e1d7bb87bca2a92`。交付前main更新为`603715b08b40dfa33ff75987bd21f5d193f7e5a1`，tree `7e3c29ca8013605dfe9c519403bc339ea6719e09`，实际Git/API一致；最终以新main为基线 |
| 依赖证据 | PR46恢复时Draft/open/unmerged；交付前API确认closed/merged，head仍`b21754645741ce16aae126660ad6d4f7fad08283`，merge=`af6d92ff3aef035546e065c32d4c205cac611a33`，审计base仍c4。固定审计提交可复用，合并不等于独立H通过 |
| 其他审计 | PR44 head `79266f15a3ce05989955b85aef97feabc9153469`、PR45 head `5ed318f023194c6f0f9767168957f7b3a1b56fb5`，恢复时Draft/open、交付前均已合并；PR47 head `149c2df1ee880ef60500031751ddc38deffa3351`合并为最终main，新增正式工作台；#40管线已在main |
| 现场保护 | 原主目录 `codex/m3-remodel-002@964a240`，仅未跟踪`.worktrees/`，两条stash和所有旧worktree保留；中断前复用区的空设计分支也不删除 |
| 新工作区 | 用户恢复指令明确要求独立worktree：`C:/Users/iyoyi/.codex/worktrees/data-architecture-001/AI-trade`；`codex/data-architecture-001-design`，从精确c4创建，初始干净；后续普通merge同步603，保留初稿提交15e34ed，不reset/rebase/强推 |

## 实际阅读与适用纪律

已读根AGENTS、MODEL_ROUTING_POLICY v1.0、OPEN_SOURCE_RESEARCH_POLICY v1.0、TASK_TEMPLATE、PROJECT_STATUS、DECISIONS、ARCHITECTURE、DATA_CONTRACT、INTERFACE_CONTRACT、M3_CORE_CONTRACT、M3认证矩阵/管线任务及上述三个固定审计；核对Schema v1/v2、db、三个Repository、reference辅助写入、ingestor/EvidenceStore、M2/M3/M4页面与计算、M3文件出口和CFFEX版本端口、相关测试源码。主线更新后补读workbench.py/workbench_cli.py、启动脚本、正式库报告/指南及新增测试源码，核对整个基线diff：七表DDL/M2/M3核心/M4逻辑未变，生命周期已改变；没有执行任何新入口。无适用子目录AGENTS/override。最终源码事实绑定603；新增设计不覆盖正式契约。

适用G01–G12：固定模型、保护现场、未知不补造、不可变迁移、H待独立审查、证据分列。冲突：G11默认完整离线套件会创建临时SQLite；用户本轮明确禁止创建/初始化/复制SQLite，优先遵守用户边界，不运行pytest、应用、初始化CLI、采集脚本或任何数据库连接。只做文本/AST/Git/JSON/链接等无数据库检查及pip check。远端已有CI不冒充本次测试；Draft PR也不主动触发建库工作流。

## 调研与采用

R01适用，复用现有SQLite/不可变版本/内容寻址文件/只读产物发布设计，拒绝为命名统一重建七表。补充有界阅读SQLite官方事务、Online Backup、PRAGMA文档，仅文档请求，不请求行情源；细节与采用/拒绝理由见[总设计](../architecture/DATA_PERSISTENCE_ARCHITECTURE.md)。没有复制外部实现、引入依赖或重新认证SDK/数据许可证，官方文档是2026-10-21动态版本，不冒充冻结源码审计。

## 交付边界与验收

仅新增本任务记录和`docs/architecture/`六份设计：总设计、关系模型、字段字典、时间/发布血缘、迁移方案、M0—M5矩阵/路线。所有候选表均为PROPOSED，示例全部SYNTHETIC；迁移编号是建议顺序、不是注册结果。

验收：七表字段/约束/读写/消费者/既有真实数据证据；三层ER；每张候选表字段/空值/键/索引/粒度/示例/Repository；跨层可见性、可复现M3/M4/M5；发布manifest/云端验证/失败语义；v1/v2保留、升级/恢复与旧代码拒绝新库；P0–P2依赖和门槛。恢复时路径UNKNOWN不阻断设计；新main已有正式路径/空库E证据后更新该事实，但本任务不查库确认当前状态，实施仍需核验。

禁止修改src/tests/deploy/Schema/治理文件，不开SQLite，不读行情载荷，不复制旧库，不发行情/EC2请求，不改变策略、准入、生产配置或AWS；不自动合并/部署。独立H计划`TASK-DATA-ARCHITECTURE-001-REVIEW`待指派，绑定Draft最终SHA后只读审阅；当前自检不等于独立审查。等待批准后另立Schema实施任务。

## 验证与交付状态

设计文档已交付，等待独立H审查与用户批准进入实施。新增7个Markdown文件：本任务记录、总设计、关系模型、完整字典、血缘/发布、迁移、模块/来源/路线；无业务/测试/Schema/配置修改。39个候选表是分阶段设计，不是已创建表；现有七表均保留。M3示意明确synthetic且blocked，结构校验不认证其hash/真实数据。

| 本轮验证 | 实际结果 / 证据 |
| --- | --- |
| 文本/AST/Git检查 | `python -` stdlib脚本，初稿读取18个实际源码AST/Git blob；更新后核验22个新main相关源码AST/字节（含workbench/CLI），与603逐一匹配，未import项目/调用数据库。相关测试源码只读，包括test_db、test_reference_data、test_market_data_repository、M3边界/管线与M4、workbench测试，没有执行 |
| 字典/关系/路线检查 | `python -`文档检查：39个唯一候选表、必填字段示例、粒度/PK/索引、所有FK目标可解析、迁移顺序有覆盖；7个文档代码围栏闭合、37个本地链接存在；最终exit0 |
| 示意JSON | 既有jsonschema Draft202012Validator + 本地M3_DIAGNOSTIC_V1.schema.json，对一个明确SYNTHETIC/BLOCKED示意结构校验；PASS/exit0，非核心重算hash或来源认证 |
| 依赖 | 现有解释器`F:/codex-agnes/AI-trade-main-demo/.venv/Scripts/python.exe -m pip check`，exit0，No broken requirements found.；未安装/升级依赖 |
| Git范围 | 最终对603基线的src/tests/deploy/AGENTS/原DATA与INTERFACE契约diff为空；`git diff --check`通过；PR只包含7个任务文档，无SQLite、原始行情或秘密 |
| 首轮文档检查 | exit1：检查器未识别带中文后缀的表标题/“例”标签，另缺两个明确粒度说明；修正只读检查器并补文档。复查发现A06“示意行”与统一标签不一致，统一为“示意”后最终通过。保留两次诊断输出，不修改业务/测试期望或隐去失败 |
| 主线漂移保护 | 第一次准备创建PR前API断言检测到main变603，exit1并停止创建PR。只读分析新合并实际改动，普通merge保留已有设计提交后更新路径/生命周期/PR状态事实；新Schema实施、行情和AWS未执行。没有沿用过时审计结论 |
| 完整离线pytest | NOT RUN（0项本轮执行）；按用户明确禁止创建/初始化SQLite优先于G11通用要求。旧2871项结果不是本轮结果 |
| 迁移/FK SQL/备份恢复/性能 | NOT RUN；本轮没有连接、初始化、写入、复制或迁移任何SQLite；文档的FK检查只检查设计目标引用，不冒充SQLite执行测试 |
| 真实行情网络/UI/样本外/AWS | NOT RUN；行情请求0，应用未启动/刷新，AWS未连接/配置；仅必要GitHub基线/PR与3页SQLite官方文档请求 |
| Mermaid渲染/独立H | NOT RUN；提供ER/依赖图源码并自检，未实际渲染或换角色独立审查；待审查者复核关系/完整性 |

本地脱敏日志（不进入Git）：`C:/Users/iyoyi/AppData/Local/Temp/TASK-DATA-ARCHITECTURE-001-validation.json`、`-validation-v2.json`、`-validation-final.json`；同步新main后的最终结果是`TASK-DATA-ARCHITECTURE-001-validation-603715b.json`。最终版本清单由发布检查绑定Git blob，避免任务单自引用自身提交SHA。日志不包含行情载荷、数据库内容、凭据或完整环境。

Draft交付采用现有CI的`[skip ci]`提交说明，避免本只读任务主动运行会建SQLite的流水线；不改workflow/分支保护，不自动合并。自动CI是否跳过/待检查以实际GitHub状态为准，不能写成CI通过。审查前不能进入Schema实施；正式库、来源许可、核心H及云端接线均为实施前置，设计已单独交付。最终提交/Draft PR链接在PR和对话交付记录中绑定。

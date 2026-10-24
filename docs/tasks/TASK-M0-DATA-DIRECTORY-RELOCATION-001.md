# TASK-M0-DATA-DIRECTORY-RELOCATION-001

H implementation / P1，基础设施路径与数据迁移；**PARTIAL**：阶段A已只读核验，阶段B实现/离线自检完成待独立H，阶段C/D正式迁移及main工作台验收未执行。

唯一执行：OpenAI / Codex Desktop **gpt-6.1-sol / medium**。本会话turn_context `2026-10-24T04:22:52.104Z`实际核验；用户随后明确回复“本任务固定使用当前 medium 实施”，覆盖任务单的High建议，不切档、不委派。预算120分钟；费用UNKNOWN；同一验收最多两次有不同诊断依据的修复，核心失败/契约冲突按G10停止。

基线 main `04e530871e2c8b4889c60027ac8d1ec4275009a2`，GitHub branches/main与AI-trade-dev/main一致且干净。PR47已合并：base `c4b682d12c7c8dc42f75e717b855238f635ce05b`、head `149c2df1ee880ef60500031751ddc38deffa3351`、merge `603715b08b40dfa33ff75987bd21f5d193f7e5a1`。PR51仍Draft/open、head `29d11241b8f33f7d12214d1ea100bc8e504fc07d`、base 04e5308；本任务不引入其v3—v5或修复其失败。

独立分支 `codex/m0-data-directory-relocation-001`，工作区 `F:/codex-agnes/AI-trade-m0-data-directory-relocation-001`。原AI-trade的.worktrees/、AI-trade-main-demo的既有修改/未跟踪文件、两个stash及25个原worktree全部保留。

已实际读取：AGENTS、MODEL_ROUTING_POLICY v1、TASK_TEMPLATE、OPEN_SOURCE_RESEARCH_POLICY v1、PROJECT_STATUS、DECISIONS、DATA_CONTRACT、INTERFACE_CONTRACT、DATA_MIGRATION_PLAN、LOCAL_WORKBENCH、LOCAL_STREAMLIT_STARTUP、旧路径审计/只读进程探针，以及storage db/workbench/workbench_cli/schema、demo_app配置入口、启动脚本及相关测试。版本为04e5308；无下级AGENTS/override。适用G01—G12，无治理文件修改。

调研适用：复用PR47的SQLite backup_new/模式ro/严格DDL与隔离恢复实现及测试；补读SQLite官方Backup API和PRAGMA文档，不引入外部库/代码或数据源。Windows Restart Manager资源登记官方文档说明登记有写操作，阶段A没有调用；全系统其他DB持有者未排除。数据源许可/算法与本任务无关，不新增行情请求。

允许：阶段B配置/启动路径、必要的Backup API create-only迁移工具、隔离测试、当前操作文档及审计证据；不改SQL迁移、七表、Repository语义、M3算法、AWS/deploy配置，不改正式环境或数据库，不启动/停止现有8524。阶段C必须独立H审查通过、人工合并并快进main、停写/持有者窗口确认后才执行；当前不自动合并。

验收：新根路径派生、别名冲突/缺失/链接/仓库/Temp拒绝、启动脚本PS5.1/7解析、缺库不创建/刷新不initialize/默认ro、非空v2隔离备份恢复/无覆盖/失败保全、完整离线pytest/pip check/diff。离线与正式迁移/UI/真实网络/样本外分列，实际结果记录于报告；不冒用旧测试。

独立H：`TASK-M0-DATA-DIRECTORY-RELOCATION-001-REVIEW`，配置/独立会话待指派，绑定最终SHA；合并/阶段C前审配置兼容、停写窗口、备份恢复与失败路径。当前实现者不充当独立审查。交付Draft PR供人工处理，正式迁移未执行时状态必须PARTIAL。

审计、路径矩阵、迁移/回滚步骤及后续结果见 [任务报告](../audits/TASK-M0-DATA-DIRECTORY-RELOCATION-001.md)。

测试冻结SHA `6e5f2d6432461bc30064ca55382c02759cf3095a`；完整离线exit0 / 2931 passed / 4 skipped / 292.69s，skip实网1和Windows symlink权限3；真实junction通过。定向首轮92/3、补充子集42/3，均exit0；pip check/diff/保护路径检查exit0。日志/JUnit及源码hash见[机器证据](../evidence/TASK_M0_DATA_DIRECTORY_RELOCATION_001.json)。后续仅文档/证据变更不冒称重新运行。CI、最终SHA和Draft PR绑定见PR正文；原生push认证失败，连接器交付需验证同树且不强推。

# TASK-LOCAL-GIT-GITHUB-SYNC-001

类型 implementation（本地Git环境修复与报告），H（认证与网络边界）。唯一执行OpenAI/Codex **gpt-6.1-sol / high**，沿用本会话用户确认配置，无模型切换、子代理或fallback；费用未知。预算90分钟、最多40次有界探测动作（非底层HTTP请求数）；Git命令25秒，fetch最多60秒，无无界重试；同一验收项两次不同依据修复仍失败升级，凭据/安全冲突停止。

目标 F:/codex-agnes/AI-trade-dev；开始main/HEAD/origin/main均 `04e530871e2c8b4889c60027ac8d1ec4275009a2`，status空。remote为用户指定GitHub HTTPS。两个stash、全部旧worktree保留，不直接提交main、不覆盖修改。独立文档分支 codex/local-git-github-sync-001，工作区 C:/Users/iyoyi/.codex/worktrees/local-git-github-sync-001/AI-trade，同一main基线。

已读根AGENTS、MODEL_ROUTING_POLICY v1、TASK_TEMPLATE、OPEN_SOURCE_RESEARCH_POLICY、DECISIONS、PROJECT_STATUS，未发现适用下级AGENTS；适用G01-G05/G08-G12。业务数据/接口未触及，G06/G07不改变。环境排障不引入业务模块、依赖、数据源或迁移，R01不启动量化开源调研；仅有界阅读Git/GCM/Microsoft官方配置/环境文档，动态未冻结链接和限制见报告。

允许：只读配置/环境/代理协议/TLS/GCM检查；限定GitHub的worktree代理及现有账号选择；备份后追加User PATH；fetch、受保护的已同步no-op pull、权限/策略检查后的push dry-run；SourceTree实际Fetch。使用computer-use技能，仅已定位SourceTree/选文件夹对话框；不自动化终端、登录、密码或安全设置。
禁止：业务/SQLite/Schema/依赖/策略/AWS/代理软件/TLS设置修改，凭据删除或导出/复制，真实业务push，强制/丢弃/reset/clean/stash/worktree清理，未经确认的安装/卸载。永久修改先记录原值、备份、影响与回滚；没有全局Git配置变更或软件重装。

实际边界：两个worktree专用GitHub项、User PATH一项追加；原值/回滚/备份在本机私有任务目录。旧GCM与Codex GCM保留，通过现有账号选择而非搬移token修复认证。普通新PowerShell真实执行版本/ls-remote/fetch/no-op pull/push dry-run，GUI实际Fetch，202文件hash/HEAD/main/状态/stash保护通过。

验收结果：新PowerShell exit0（6.41秒）；旧Git仍2.35.1，runtime Git仍2.53.0；main=origin/main=04e5308；GitHub现有账号API200，pull/push权限与main规则已查；SourceTree3.4.6 Fetch通过且无prune/tags/merge/push；全局/系统/Codex/共享Git配置hash不变。pip check exit0；报告diff、链接、脱敏检查见最终交付。完整业务pytest NOT RUN，因任务限定Git且不处理SQLite，未改应用/测试/依赖；明确记录G11未执行项，不虚报业务回归。

交付3份文档：[报告](../LOCAL_GIT_GITHUB_SYNC_REPORT.md)、[机器证据](../evidence/TASK_LOCAL_GIT_GITHUB_SYNC_001.json)、本任务单。初始网络失败、无效默认凭据、缺PATH及create-only日志保存错误如实保留。完整私有证据根 C:/Users/iyoyi/AppData/Local/AITrade/GitDiagnostics/TASK-LOCAL-GIT-GITHUB-SYNC-001/。
独立H计划 TASK-LOCAL-GIT-GITHUB-SYNC-001-REVIEW（待指派；冻结最终Draft head后审scope/凭据保护/回滚/实际验收），不在实现会话换角色审自己，不自动合并、不解除业务门禁。

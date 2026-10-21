# TASK-M0-PRODUCTION-DB-001

类型 implementation；H（数据库连接生命周期、显式初始化与正式研究边界）。
唯一执行配置 OpenAI / Codex / **gpt-6.1-sol / high**，用户于本会话明确确认；费用未知。
预算 120 分钟；不调用子代理/其他模型；行情请求 0；同一验收项最多两次有不同依据的修复，核心契约失败立即停止依赖开发。

基线 main `c4b682d12c7c8dc42f75e717b855238f635ce05b`，git ls-remote 与 fetch 实测。
工作区 `C:/Users/iyoyi/.codex/worktrees/m0-production-db-001/AI-trade`，分支 `codex/m0-production-db-001`。
原目录 HEAD `964a24007ab208d7b10e254a4e86548007c69c4f`，未跟踪 .worktrees/、两份 stash 和全部旧 worktree 原样保留。
前置证据 PR44 head `79266f15a3ce05989955b85aef97feabc9153469`、PR45 head `5ed318f023194c6f0f9767168957f7b3a1b56fb5`，均 Draft/open、base 同 main；不依赖其未合并实现。

已读：根 AGENTS、MODEL_ROUTING_POLICY v1、OPEN_SOURCE_RESEARCH_POLICY v1、任务模板、PROJECT_STATUS、DECISIONS ADR001–006、DATA_CONTRACT、INTERFACE_CONTRACT、M3_CORE_CONTRACT、M3_PAGE_DIAGNOSTICS，以及 storage/db/schema/reference_schema、demo_app/demo_data 和生命周期/页面测试。没有适用下级 AGENTS。
适用 G01–G12；用户明确授权创建新的本地正式研究库及现有 v2 初始化，覆盖 G09 的默认禁止未授权建库；不授权写入任何既有库、行情采集或旧数据迁移。
用户建议的源码树下 data/sqlite 是已忽略的数据专用目录，允许该明确目录；不把持久目录必须在源码树外的旧部署限制误称为全部满足。

调研：适用、复用现有仓储/迁移与 PR45/44 证据，补足 SQLite URI/Backup API。最多 8 个官方页面，不引入依赖/复制外部源码。
已读 CPython v3.12.14 Modules/_sqlite/connection.c、Lib/test/test_sqlite3/test_backup.py、LICENSE；采用现成标准库 backup/URI 接口，拒绝文件复制实时数据库和并行数据管线。Python PSF 及 sqlite 模块头部许可已核，SQLite 交付库 public domain；不据此推断行情使用许可。源码链接见实施报告；动态 sqlite.org 页面未冻结版本，未声称外部测试已执行。

允许：storage 连接配置与严格诊断、新 workbench 操作 CLI、本地固定启动脚本、demo_app 正式接线、必要反例测试、报告。
禁止：v1/v2 定义/checksum、M3 算法/准入、AWS/TLS/代理/策略、旧数据库/样本/目录/stash、真实行情 GET。
目标 `F:/codex-agnes/AI-trade/data/sqlite/workbench.sqlite3`，开始检查文件和父目录不存在；正式初始化前再次检查侧车、归属和备份位置。
备份/日志置于源码树外 `F:/codex-agnes/AI-trade-local-state/m0-production-db-001/`；不提交 SQLite、原始载荷或运行日志。

验收：定向生命周期/配置/损坏/只读/幂等/备份恢复测试；完整 `python -m pytest -q`；`python -m pip check`；`git diff --check`；正式库清单、quick_check/FK/checksum、实际 Streamlit 绑定证据、旧库 hash 不变、迁移预览和 M3 后续结构设计。
真实网络/样本外：NOT RUN；本任务只做本地空库和 UI，不声称 M0–M3 数据链路完成。
独立 H 计划 TASK-M0-PRODUCTION-DB-001-REVIEW（待指派，冻结交付 SHA 后审连接/初始化/备份/回退反例）；审查前不合并、不解除阶段或来源门禁。
最终命令、退出码、发现、提交和 PR 见 `docs/M0_PRODUCTION_DB_REPORT.md`。

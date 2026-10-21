# TASK-M0-DB-PATH-CONFIRM-001：正式SQLite路径与应用绑定

## 执行配置与基线

- 类型：acceptance，只读配置/运行进程/文件/SQLite核验；等级H（数据库归属、真实性、生产隔离及历史准入边界），不是独立H代码审查。
- OpenAI / Codex Desktop，唯一模型 `gpt-6.1-sol`、固定 `high`；2026-10-21运行rollout `turn_context` `01a15bb9-8d17-78c0-9a23-8189641c4251`实际核验。费用/额度未知；预算90分钟，行情/EC2/账户请求0，数据库写入0，禁止自动重试/提权/换模型或子代理。
- 最新GitHub main和本任务基线：`c4b682d12c7c8dc42f75e717b855238f635ce05b`（API与fetch一致）；原工作区 `codex/m3-remodel-002@964a24007ab208d7b10e254a4e86548007c69c4f`，未跟踪`.worktrees/`、两条stash及其他worktree保留。
- 独立工作区 `F:/codex-agnes/AI-trade-m0-db-path-confirm-001`；分支 `codex/m0-db-path-confirm-001`。不修改旧任务分支。
- 前置PR #44仍Draft/open/unmerged，head `79266f15a3ce05989955b85aef97feabc9153469`、base为上述main；只是只读证据参考，不依赖其文档合并。核心#37不因本任务而解锁。

## 实际阅读与采用范围

已读AGENTS、MODEL_ROUTING_POLICY v1.0、TASK_TEMPLATE、OPEN_SOURCE_RESEARCH_POLICY v1.0、PROJECT_STATUS、DECISIONS、DATA_CONTRACT、INTERFACE_CONTRACT、现有SQLite连接/两迁移定义、demo_app/demo_data、market_analysis数据/页面/证据/健康采集入口及相关启动配置。本基线无下级AGENTS/override。适用G01–G12，重点为只读连接、固定模型、未知归属/时间不补造、数据与生产边界、证据及Draft待独立H。

调研：不引入业务模块/来源/依赖/数据库设计；复用现有库存证据，仅补运行进程真实绑定、DDL和备份差异。当前环境无psutil，不安装依赖；为只读检查指定应用PID的工作目录和数据库相关环境变量，核对Microsoft ReadProcessMemory/NtQueryInformationProcess/PEB官方说明及phnt的RTL参数布局。仅本机一次性诊断，不导入外部软件或复制框架。该布局属Windows内部结构，必须限制x64、核验命令/映像与CIM相符；失败保留UNKNOWN，不提权、不注入、不写内存。只保存白名单数据库/root/PYTHONPATH配置，不保存完整环境或进程内存。

## 修改与操作边界

只允许新增本任务单、脱敏报告/机器摘要，以及忽略artifacts内的一次性只读诊断工具/日志。禁止修改业务、Schema、测试期望、准入、任何既有数据库及侧车、启动配置/环境、系统代理/TLS；不启动/刷新可能初始化数据库的页面，不采集/重放、不复制/迁移库，不连接EC2/账户，不合并/部署。

SQLite仅用原生URI mode=ro、query_only、只读SELECT/PRAGMA；不调用Database.connection/initialize或可修改journal的应用入口。不使用现有文件名或目录含义作为正式归属证据；当前运行应用绑定、磁盘样本、迁移结构和用户正式指定分别记录。

## 验收与交付

| 项 | 必须证据 |
| --- | --- |
| AC-01 路径与绑定 | 正式库完整路径及依据，或“尚未确认”；CIM/监听PID/进程实际cwd与白名单环境/源码分支对应；配置缺失不等于库不存在 |
| AC-02 实际库与迁移 | 候选库表/行数/日期/来源/批次/归属；七表实际DDL、列/索引/触发器/外键与当前v1/v2定义核对；只读hash前后相同 |
| AC-03 侧车与备份 | WAL/SHM/journal、明确备份候选路径/格式/是否可认证，保持原文件；无扫描范围外不存在的断言 |
| AC-04 可复用与前置 | 真实股票/指数文件与批次/time/质量边界；不把样本认作正式入库，不自动开始采集 |
| AC-05 验证与发布 | 无数据库初始化的只读断言、pip check、diff/脱敏/文件边界检查；独立Draft PR绑定最终SHA；CI结果按实际另列 |

独立H计划 `TASK-M0-DB-PATH-CONFIRM-001-REVIEW`，待指派、未自动创建/执行。需复核进程证据链、内部布局限制、配置优先级、DDL/checksum、只读证明与未知项。当前会话不换角色自称独立审查；最终用户决定，不解锁数据认证/策略/生产门禁。

规则边界：G11默认要求完整离线套件，而本次更具体要求“不得初始化数据库或运行可能创建表、修改journal模式的应用连接入口”。现有完整套件会初始化临时库，因此本轮不手动运行该套件；按本次明确只读要求优先，只执行无初始化/写入的核验和依赖检查。历史同代码基线结果与本PR自动CI分别标记，不能伪称本轮本地全套通过。不为该冲突请求修改权限或放宽只读边界。

后续只建议明确正式目录/归属/备份/来源授权及存储缺口；不在本任务建立新库。实际命令、结果、失败与未执行项在报告/PR追加。

## 实际交付与证据

结论：**只读核验完成；正式持久研究SQLite尚未确认。** 当前8524服务实际配置为 `C:/Users/iyoyi/AppData/Local/Temp/a-share-quant-demo-5gu28e3m/demo.sqlite3`，test/DELETE、只读UI标志1；已确认进程自己的cwd/root/PYTHONPATH，不再把检查者环境误当应用配置。1217条真实行情属于已保存Demo；当前root内指数观察0个，未搬移其他目录的550行JSON。

仅新增3个文档/证据文件：本任务单、[核验报告](../M0_DB_PATH_CONFIRM_REPORT.md)、[机器摘要](../evidence/TASK_M0_DB_PATH_CONFIRM_001.json)。不修改业务、Schema、测试、依赖或共享权重。原工作区、两个stash、旧任务PR44及所有已有数据保持原样。

| 实际命令/检查 | 结果与日志 |
| --- | --- |
| Get-CimInstance / netstat | 8524由PID1952监听，父PID29704；另8525为http.server，不是采集端；命令/工作目录/数据库白名单与源码对应 |
| `python artifacts/db-path-confirm-001/process_probe.py` | exit0；3个相关进程只读观测，64KB/进程环境上限，无完整环境/内存dump；process-binding.json |
| `python artifacts/db-path-confirm-001/audit.py` | 最终exit0；2260个SQLite候选路径；5重点库各7表、36个显式DDL对象和迁移checksum均与main一致、quick_check=ok/外键0异常；库/侧车前后hash不变；audit-v2.json |
| 旧库存hash复核 | 613库及其侧车实际变化0；7个active源码文件与main一致；4处真实指数文件hash一致；没有由hash相同升级为来源认证 |
| 环境/归属/备份 | windows-config.json；User/Machine相关变量为空，进程独立配置明确；Owner为本机用户；范围内无备份候选/匹配Startup、任务或服务；不宣称全电脑无备份 |
| `python -m pip check` | exit0，No broken requirements found.，pip-check.log；无安装/升级依赖 |
| 只读断言 | exit0；五库DDL/迁移/hash/外键、父子root一致、7个源码和4个观察hash；assertions.json。不是pytest数量或独立H结论 |
| 本轮本地完整pytest | NOT RUN；按当前明确“不得初始化”优先，未用旧2871项冒充本轮执行。PR自动CI按实际结果另记，不手动启动初始化或重放 |
| Git/链接/脱敏 | 发布前确认仅上述3文件，git diff --check；检查无原始行情、响应、凭据、完整环境或内存地址/dump，必要本地链接有效；delivery-checks.json |

解释器为现有 `F:/codex-agnes/AI-trade-main-demo/.venv/Scripts/python.exe`，3.12.14，PYTHONPATH指本任务src，UTF-8且PYTHONDONTWRITEBYTECODE=1；schema导入仅生成纯SQL定义/checksum，未调用任何初始化/应用连接入口。进程探针仅QUERY_INFORMATION/VM_READ；数据库仅URI mode=ro/query_only及只读事务。

诊断记录：首版audit的文件状态使用bytes键而旧清单用size，导致元数据形状比较错误；保留audit.json，统一键后生成audit-v2.json，验证实际SHA变化0，未改变业务/数据/断言。一次备用模板不存在和带空格Startup目录未引用的只读命令失败，已按实际路径和LiteralPath核对；没有数据库修改或需要修复的业务测试失败。

无新增行情HTTP、采集重放、库写入/复制/迁移/侧车处理、浏览器UI/手机、样本外或EC2/账户操作。报告、文件owner、迁移匹配、已合并代码或当前服务配置都不等于正式数据库指定、来源认证或研究准入。后续仍需用户决定正式归属/持久目录/备份策略及独立H，不自动执行。

发布后精确提交/tree及Draft PR由本机交付记录和PR说明绑定，避免提交内自引用循环；独立H待指派，当前会话不自审、不合并。

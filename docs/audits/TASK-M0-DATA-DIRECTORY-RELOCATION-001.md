# TASK-M0-DATA-DIRECTORY-RELOCATION-001

状态：**PARTIAL**。阶段A只读完成；阶段B实现和离线自检完成、尚待独立H；阶段C/D正式切换未执行。执行gpt-6.1-sol/medium（实际元数据及用户确认见任务单），H；main基线04e530871e2c8b4889c60027ac8d1ec4275009a2。测试代码SHA `6e5f2d6432461bc30064ca55382c02759cf3095a`，后续仅文档/证据提交不改变测试源码。

## 阶段A实测（2026-10-24，Asia/Shanghai）

12:25使用stdlib sqlite3 URI `mode=ro`、query_only=1，对已确认的 `F:/codex-agnes/AI-trade/data/sqlite/workbench.sqlite3` 执行只读检查。没有调用initialize、创建数据库或写文件。

| 项目 | 实测 |
| --- | --- |
| 正式库 | 147456字节；SHA256 `48511c2092d0e08c02e9384647e5d51365feb04232248f7b95e0df1b5c998f64`，前后相同 |
| Schema | v2；七表、12显式索引、17触发器；36个SQL对象与main已发布定义规范空白后逐一相同 |
| 计数 | schema_migrations=2；instruments/ingestion_runs/daily_bars/daily_bar_versions/security_versions/calendar_versions各0 |
| 完整性 | integrity_check=ok；foreign_key_check空；journal=DELETE；无WAL/SHM/journal |
| 新目录 | F:/codex-agnes/AI-trade-data尚不存在；旧sqlite目录仅有正式DB，无m3-observations |
| 8524 | 当前运行，监听PID19676，父Python19440；命令/映像/cwd指向AI-trade-dev；只读PEB白名单核验两者均WORKBENCH_ROOT=旧sqlite、QUANT_DB_PATH=旧库、READ_ONLY=1、STRICT=1、DELETE，DATA_ROOT未设置 |
| 连接/写者边界 | 进程配置不是所有活跃句柄的证明；未完整枚举非Python持有者，停写窗口UNKNOWN。未停止服务、不宣称可立即切换 |
| 环境 | 审计进程/User/Machine白名单DB变量均未设置；不能由此否定运行服务的独立环境 |
| Git | AI-trade-dev干净main与远端04e5308一致；PR47已合并，PR51仍Draft/未合并；原25个worktree/2个stash保留，AI-trade-main-demo既有修改不动 |

只读进程核验复用旧探针经审阅的QUERY_INFORMATION/VM_READ方法，在内存中去掉其历史文件输出、改为当前PID与9个配置白名单；不注入/提权/写内存、不保存完整环境。Windows内部布局的证据限制仍保留。资源登记接口可能写注册表，未在只读阶段用其枚举。

## 路径依赖矩阵与最小方案

| 分类 | 真实位置/调用 | 本期处理 |
| --- | --- | --- |
| 必改运行配置 | scripts/start_workbench.ps1:13旧绝对根；运行19440/19676继承旧绑定 | 脚本改用DATA_ROOT/sqlite，主main干净/固定Python/默认ro仍保留；实际服务只在阶段C审查后切换 |
| 必改解析 | storage/workbench.py::workbench_config/persistent_root；db.py::from_env | 新根为本地正式配置来源，旧root/QUANT路径同时给出必须匹配；缺失/冲突/越界失败，不扫描/创建/回退；保留严格DDL/checksum |
| 必改页面配置接线 | demo_app::get_demo_root/get_components、只读判断/路径诊断 | 仅识别新正式配置，继续共用既有Database；不改M3指标/评分/准入 |
| 必改测试 | test_db/test_workbench_storage/test_start_workbench_encoding；manual/test_workbench_offline | 增加新根、冲突、缺失、链接、只读、刷新、隔离迁移恢复测试；原低层和旧显式接口保护不降低 |
| 当前文档 | LOCAL_WORKBENCH、LOCAL_STREAMLIT_STARTUP、README及.env.example | 发布后入口与尚未切换状态分开；历史初始化命令明确历史，不替换历史DB证据 |
| 不动历史证据 | M0_PRODUCTION_DB_REPORT、M0_DB_PATH_CONFIRM_REPORT、docs/evidence旧快照、PR49架构历史路径、旧worktree文档 | 保留原路径/时点，不全局替换字符串 |
| 其他worktree | data-architecture、local-git-github-sync、production-db、core-data-model、windows-startup均含旧脚本 | 不批量改写；正式脚本仍只允许AI-trade-dev/main。并行采集任务实际停写另核验 |
| PR51输入存储 | m3_store_catalog.CatalogRepository构造器显式接收Database/evidence_root，没有要求旧数据库绝对路径；其启动脚本仍含旧路径 | 不合入/改写其代码或证据，未来重基线后由独立任务接新路径；v3—v5不迁移 |
| EC2 | deploy/workbench.service.example及update-workbench.sh使用显式WORKBENCH_ROOT | 不修改；保留非Windows显式legacy配置兼容，不连接AWS |

没有实际使用SQLITE_PATH/DATABASE_PATH的新配置，不凭名字再造一套DAO。AI_TRADE_DATA_ROOT是数据根；AI_TRADE_WORKBENCH_ROOT在新入口仅为派生sqlite子目录的兼容断言，QUANT_DB_PATH仅为同一文件的兼容断言，不能任选其一。

新根要求绝对路径、仓库和Temp之外、无链接越界。Windows严格入口缺DATA_ROOT明确停止；原非严格/非Windows显式WORKBENCH_ROOT接口不被当作静默fallback，也不能用来宣称完成本地正式切换。外部程序可绕开本项目配置直接打开旧文件，因此唯一正式库仍须运行清单/停写窗口验证，不能仅靠文件名或环境变量证明。

## 阶段C操作计划（未执行）

1. 独立H通过最终代码SHA；用户人工合并后，只在干净AI-trade-dev/main快进更新。当前不改main，也不自动合并。
2. 记录/停止已确认8524进程和全部写入者，核查任务计划/后台任务及DB持有者；不能确认则停止。保留原配置用于回滚。
3. 再只读核验源库路径、v2精确DDL/迁移checksum、逐表内容hash/计数、完整性/FK、SHA和侧车；禁止v3—v5。源变化则用新证据重新审查，不沿用空库结论。
4. 使用已有SQLite Backup API create-only生成 `AI-trade-data/backups/<唯一批次>.sqlite3`，再由备份恢复到独立路径核验全部内容/结构/完整性。目标/备份/恢复任何文件或侧车存在即拒绝，失败产物保留。
5. 只有备份和恢复比对成功才从已验证副本通过Backup API建立 `AI-trade-data/sqlite/workbench.sqlite3`，不运行Schema迁移或初始化；源库保留。原始raw目录仅预留，不填样本。
6. 新进程显式DATA_ROOT与派生root/DB，默认只读。从已合并的main启动8524；页面路径/状态、只读、刷新hash、缺失不创建和M3功能分别验收。没有这些实证不得标PASS。
7. 回滚演练停止新服务，以记录的旧配置/配套旧main启动只读旧库；不覆盖/删除新旧库。新脚本不提供自动旧路径fallback，旧配置恢复是人工显式回滚，不冒充迁移成功。

本期阶段B只在隔离临时库运行工具/回滚演练；正式库操作必须等以上门禁。工具的review引用和停写参数是操作者声明，不是自动完成独立H或全系统写者认证。

正式操作命令模板如下，**尚未执行**；只能在审查通过并人工合并的main、停写确认后用当次重新核验的SHA及真实审查引用替换占位符。当前不要运行：

```powershell
$env:PYTHONPATH = 'F:\codex-agnes\AI-trade-dev\src'
& 'F:\codex-agnes\AI-trade-dev\.venv\Scripts\python.exe' -m ai_trade.storage.relocation `
  --source 'F:\codex-agnes\AI-trade\data\sqlite\workbench.sqlite3' `
  --data-root 'F:\codex-agnes\AI-trade-data' `
  --batch-id 'APPROVED_UNIQUE_BATCH' `
  --expected-sha256 'REPLACE_WITH_NEW_AUDIT_SHA256' `
  --review-ref 'REPLACE_WITH_INDEPENDENT_H_REVIEW' `
  --confirm-stopped ALL_WRITERS_AND_READERS_STOPPED
```

工具保留七表逐行有序内容hash、迁移元数据、DDL、表计数、integrity/FK和源文件状态；三个API阶段均验证源未变及副本等价。目标/备份/恢复及其侧车已存在即拒绝；异常保留中间文件而不是删除重试。数据目录预留raw/market、raw/cffex、raw/evidence、exports。工具不启动服务/设置环境/切换路径，不调用initialize，不能把COPIED_VERIFIED_NOT_SWITCHED当作完整迁移验收。

当前main的回滚配置应原样保存。切换后若需回滚，先停新服务，在独立进程用已记录旧代码SHA `04e5308` 及旧WORKBENCH_ROOT/QUANT_DB_PATH/STRICT=1/READ_ONLY=1运行旧库；不强制重置dev/main、不修改新脚本使之自动回退，也不覆盖两库。源码树/配置成对回滚须审查并在维护窗口执行，具体main回滚方式由人工决定；本任务只验证隔离库可以重新只读打开旧状态，未把它冒充正式工作台回滚演练。

## 阶段B实现与初步测试

- `storage/workbench`：data_root/is_workbench/workbench_root统一解析，保留workbench_config严格校验；Windows严格入口要求新根，非Windows显式legacy配置保留。
- `storage/db.from_env`：新根进入同一正式配置端口；Database连接、事务、initialize和已发布迁移均未修改。
- `demo_app`：仅替换正式配置识别与路径派生，原Sidebar显示实际DB/Schema/只读状态继续复用；M3算法和页面文件未变。
- `start_workbench.ps1`：新根/派生别名一致性、默认新绝对路径及保留main/干净/解释器/缺库门禁；UTF-8 BOM仍在，PS5.1/7仅解析测试，不运行日常服务。
- `storage/relocation`：Backup API create-only维护工具；只在合成临时v2库运行，含非空数据恢复、覆盖/侧车/异常/并发变化/显式旧库读取测试。

首轮定向 `pytest test_data_directory_config.py test_data_directory_relocation.py test_workbench_storage.py test_db.py test_start_workbench_encoding.py tests/manual/test_workbench_offline.py -q`：**92 passed / 3 skipped，12.35s，exit0**。随后为补足本机链接权限限制，新增实际Windows junction测试并运行相关子集：**42 passed / 3 skipped，6.44s，exit0**。三项skip均为Windows符号链接权限1314；junction根/子目录越界两项实际通过，未提权或改系统策略。实际Streamlit AppTest仅隔离库，覆盖M1—M4、刷新不initialize、缺失不创建、按钮禁用和实际路径；不是现有8524的浏览器/main新路径验收。

## 调研与验证边界

采用PR47已存在的backup_new/create-only/ro/inspect，不新增SQLite库或迁移系统。参考 [SQLite Backup API](https://www.sqlite.org/backup.html) 与 [PRAGMA完整性](https://www.sqlite.org/pragma.html#pragma_integrity_check)；完整性与外键检查分开。拒绝活动库的普通文件复制、删除侧车、空库替代和PR51未合并迁移。Windows [资源登记](https://learn.microsoft.com/en-us/windows/win32/api/restartmanager/nf-restartmanager-rmregisterresources) 有写操作，不用于阶段A。

完整离线 `python -m pytest -q --junitxml=artifacts/m0-data-directory-relocation-001/offline.xml`：**2931 passed / 0 failed / 4 skipped，292.69s，exit0**，绑定6e5f2d6。skip=未启用真实AKShare 1项、Windows symlink权限1314 3项；实际junction 2项通过。`python -m pip check`：exit0 / No broken requirements found。diff/保护路径检查exit0，七表DDL及已发布迁移、DataAccess、M3算法/页面文件、deploy均无差异。日志/JUnit、测试源码hash和正式库前后核对见[机器证据](../evidence/TASK_M0_DATA_DIRECTORY_RELOCATION_001.json)。

原生Git推送因Invalid username or token失败（shell exit1），不读取/更改凭据、Git全局、代理或TLS；通过已连接GitHub以相同Git树交付，远端冻结SHA及tree等价核验写入PR正文。本地测试提交和后续证据提交都保留，不强推覆盖。

| 最终报告字段 | 本轮实际状态 |
| --- | --- |
| 分支 / 代码 | codex/m0-data-directory-relocation-001 / 测试6e5f2d6，最终待审SHA见Draft PR正文 |
| 旧库 / 新库 | 旧F:/codex-agnes/AI-trade/data/sqlite/workbench.sqlite3保留；新F:/codex-agnes/AI-trade-data/sqlite/workbench.sqlite3 **未创建** |
| Schema/计数 | 正式库仍v2、账本2/六业务表0；正式迁移后N/A，不能用隔离非空测试代替 |
| integrity / FK | 阶段A正式只读ok/空；隔离复制/恢复均通过；正式迁移备份/恢复NOT RUN |
| 8524实际绑定 | 阶段A只读进程核验仍旧库；本任务未重启/切换，没有新路径main浏览器证据 |
| 正式库 / dev main / AWS修改 | 均否；正式DB SHA/大小未变，无侧车；dev/main仍04e5308且干净 |
| 离线 / CI | 本地2931/0/4；GitHub CI由PR记录实际状态，不能由本地通过推断 |
| 回滚 | 源库保留；隔离旧/新库只读重开通过；正式服务成对代码/配置回滚未演练 |
| 阻断与后续 | 独立H审查、人工合并main、确认所有读写者停止后才允许阶段C；当前PARTIAL |

正式迁移/新路径main工作台/真实浏览器/回滚：NOT RUN，等待独立H/人工合并和停写确认。真实行情网络/样本外/AWS：NOT RUN且不在范围内。没有以阶段B自检代替独立H或阶段C/D验收。

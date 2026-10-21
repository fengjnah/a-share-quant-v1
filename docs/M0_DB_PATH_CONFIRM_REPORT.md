# 正式SQLite路径与应用绑定核验

TASK-M0-DB-PATH-CONFIRM-001；2026-10-21（Asia/Shanghai，精确UTC时刻见[机器证据](evidence/TASK_M0_DB_PATH_CONFIRM_001.json)）。main基线 `c4b682d12c7c8dc42f75e717b855238f635ce05b`。

**结论：Windows正式持久研究库尚未确认。当前8524页面服务的配置绑定已确认，是已有的临时Demo库：**

```text
C:\Users\iyoyi\AppData\Local\Temp\a-share-quant-demo-5gu28e3m\demo.sqlite3
```

该库有600000.SH、不复权、2021-10-08～2026-10-15共1217条行情。当前应用把它配置为`environment=test`、`journal_mode=DELETE`；实际文件所有者为`DESKTOP-M3HG690\iyoyi`。这些证据确认本机应用使用关系与文件所属账户，不代表用户已经将临时库指定为正式持久研究库。没有创建/复制/迁移/重命名/写入任何既有数据库，没有开始采集或正式入库。

## 1. 运行进程→代码→文件的证据链

| 实际观察 | 结果与限定 |
| --- | --- |
| TCP监听 | `netstat -ano -p tcp`：127.0.0.1:8524 LISTENING，PID1952；不是依据历史文档中的8502端口 |
| CIM进程 | PID1952父PID29704；两者2026-10-21 06:53:02（北京时间）启动，命令匹配`streamlit … src/ai_trade/demo_app.py … --server.port 8524` |
| 可执行文件 | 父进程为既有venv `F:/codex-agnes/AI-trade-main-demo/.venv/Scripts/python.exe`；实际子进程使用宿主Python运行时。可执行文件所在目录不能代替进程工作目录 |
| 进程自己的cwd | 父、子均为 `F:/codex-agnes/AI-trade/.worktrees/local-demo-verify/`；工作区HEAD `1be04e7542cb60927563ad015de2bd73e6aa90f0`，tracked干净 |
| 进程自己的配置 | 两者`AI_TRADE_DEMO_ROOT=C:/Users/iyoyi/AppData/Local/Temp/a-share-quant-demo-5gu28e3m`，`AI_TRADE_READ_ONLY=1`，`PYTHONPATH=F:/codex-agnes/AI-trade/.worktrees/local-demo-verify/src` |
| 不存在的进程配置 | 两者`AI_TRADE_WORKBENCH_ROOT`、`QUANT_DB_PATH/ENV/JOURNAL`均未设置；与检查者PowerShell或用户/系统环境分开核验 |
| 源码路径分支 | active `demo_app.py:get_demo_root/get_components`：无WORKBENCH_ROOT时使用已配置DEMO_ROOT，并构造`root/demo.sqlite3`、test/DELETE；M1/M2/M3/M4共用传入的root/db |
| 磁盘代码与main | demo_app、demo_data、market_analysis_page、market_analysis_data、storage/db、schema、reference_schema共7个文件SHA256一致；已查两入口文件mtime早于进程启动。没有声称读取了Python已加载模块内存或浏览器session_state |
| 8525服务 | PID27184为独立`http.server`，cwd相同但没有数据库root配置；它不是SQLite采集/存储进程 |

进程信息通过只读x64 `NtQueryInformationProcess + ReadProcessMemory`核验，句柄权限只含QUERY_INFORMATION/VM_READ，不提权、不注入、不写内存；每进程环境块读取上限64KB，先验证命令和映像，再只保留7个数据库/root/PYTHONPATH白名单键。没有保存完整环境、完整命令或内存dump。探针无需安装psutil或其他依赖。

Windows内部布局可能随版本变化，方法依据见[Microsoft PEB](https://learn.microsoft.com/en-us/windows/win32/api/winternl/ns-winternl-peb)、[NtQueryInformationProcess](https://learn.microsoft.com/en-us/windows/win32/api/winternl/nf-winternl-ntqueryinformationprocess)、[ReadProcessMemory](https://learn.microsoft.com/en-us/windows/win32/api/memoryapi/nf-memoryapi-readprocessmemory)；参数布局对照[phnt固定版本ntrtl.h](https://github.com/winsiderss/phnt/blob/53fbbdc5b5d2b08761db1c7b26bfa8c820924356/ntrtl.h)，对应[MIT许可](https://github.com/winsiderss/phnt/blob/53fbbdc5b5d2b08761db1c7b26bfa8c820924356/LICENSE)实际读取。这里只用作本机诊断布局参考，不引入外部库、业务代码或新的管线；CIM/映像/cwd/源码相互核对后才给出上述配置绑定结论。

本轮没有打开、刷新或操作页面，因为启动/重跑`get_components()`会调用`Database.initialize()`。因此确认的是**当前服务配置及对应源码确定的数据库路径**，不是本轮逐会话UI端到端验收，也不保证进程将来的配置不变。

## 2. 各入口分别绑定什么

| 入口 | 实际/设计路径 | 当前证据和归属 |
| --- | --- | --- |
| 当前8524的M1/M2/M4及M3个股 | 上述Temp/demo.sqlite3；按查询显式来源、日期、版本/as_of读取 | 已确认进程配置；非正式持久库；1217行不等于每个页面窗口都读取全部1217行 |
| 当前8524的M3指数/宽度/CFFEX观察 | `C:/Users/iyoyi/AppData/Local/Temp/a-share-quant-demo-5gu28e3m/m3-observations/` | 实际0个JSON；其他root里的指数不会自动进入该目录或自动被选择 |
| 页面手动采集写端 | 若获准启用，会向同一个db/EvidenceStore(root/evidence)写入 | 当前READ_ONLY=1禁用采集按钮。本轮未点击/调用；该标志不等于SQLite连接本身mode=ro，页面仍有initialize入口 |
| `python -m ai_trade.storage` | 显式QUANT_DB_PATH；未配置时为执行cwd下`data/sqlite/local.sqlite3` | 只是初始化/迁移CLI。未执行；`.env.example`不自动加载；该配置不控制Demo入口 |
| 健康采集CLI/HealthService | 审计结果写显式`--audit-root`；实际采集写`Temp/a-share-health-*/health.sqlite3` | 代码使用临时_ScratchWriter，environment=test；不是正式行情落库位置，未运行CLI |
| #40 verify_m3_pipeline | 各独立run/source的artifacts目录；腾讯样本写`…/tencent_stock/health.sqlite3` | 旧真实批次路径核对见下表；入口禁止脱离本工作区artifacts，不能把它当正式目标库配置 |
| 持久工作台分支 | 显式AI_TRADE_WORKBENCH_ROOT下`workbench.sqlite3`，要求仓库/Temp之外 | 当前Windows服务未配置该变量；未在已扫项目路径发现该正式文件 |
| EC2工作台 | 现有部署资料/模板路径`/var/lib/a-share-quant-workbench/workbench.sqlite3` | Linux云端独立库；本轮未连接、查询、确认其行数/备份，也没有同步 |

## 3. 配置、启动与候选范围

本次扫描`F:/codex-agnes/AI-trade*`以及Temp下a-share-quant-demo、a-share-health、task003/004/008相关目录，排除.git/.venv/node_modules/缓存；共索引 **2260个SQLite候选文件**，包括自动化测试和隔离样本，不能将总数解释为2260份真实行情或正式库。完整路径目录只保留在本机忽略`artifacts/db-path-confirm-001/audit-v2.json`。并非全电脑搜索，未知目录中的库与备份仍UNKNOWN。

- 当前进程绑定所指的文件真实存在；除此之外没有在已扫范围找到非Temp、非artifacts、非测试路径的可确认本地正式库。
- User/Machine的QUANT_DB_PATH/ENV/JOURNAL及AI_TRADE_DEMO_ROOT/WORKBENCH_ROOT/READ_ONLY均未设置；应用进程仍有其独立继承配置，不能用前者否定后者。
- 项目内发现的是`.env.example`模板，没有真实`.env`或Windows启动ps1/bat/cmd候选；文档中的启动命令不是已部署配置。部署`deploy.env.example/workbench.service.example`为Linux模板，不证明Windows绑定。
- 当前/公共Startup文件夹没有名称匹配quant/AI-trade/a-share的条目；计划任务查询成功，无匹配名称/动作参数；Windows服务无匹配路径。本检查不证明不存在使用任意别名、不同启动机制或任务脚本的配置。

## 4. 五个重点库的实际结构与库存

以下临时路径均用实际 `%TEMP%=C:/Users/iyoyi/AppData/Local/Temp` 展开；机器摘要保留完整绝对路径、hash、表结构、来源和批次。

| 库 | 用途/实际数据 | 七表行数（按下表顺序） |
| --- | --- | --- |
| 当前绑定 `%TEMP%/a-share-quant-demo-5gu28e3m/demo.sqlite3` | 真实Demo样本600000.SH，2021-10-08～2026-10-15；批次`demo-fab1a9b6062641248b5d97ce97a9723f` | 2 / 1 / 1 / 1217 / 1217 / 0 / 0 |
| `%TEMP%/a-share-quant-demo-m2-q_hbvuaj/demo.sqlite3` | 真实保存样本600000.SH，2026-01-05～10-15；批次`m2-tencent-600000-20260101-20261015`；当前服务未绑定 | 2 / 1 / 1 / 187 / 187 / 0 / 0 |
| `%TEMP%/a-share-quant-demo-tduod91y/demo.sqlite3` | 真实保存样本600378.SH，2016-10-17～2026-10-15；批次`demo-26c7d533818b49a49f97827cc47e8471`；当前服务未绑定 | 2 / 1 / 1 / 2291 / 2291 / 0 / 0 |
| `%TEMP%/task008-real-72un4ppq/real.sqlite3` | 旧M0真实验收，600000.SH，2026-10-14～15；临时验收库 | 2 / 1 / 1 / 2 / 2 / 0 / 0 |
| `F:/codex-agnes/AI-trade-m3-data-pipeline-001/artifacts/m3-data-pipeline-001/live/pipeline-20261020T153923Z-c55591fd/tencent_stock/health.sqlite3` | #40隔离验收2条，600000.SH，10-14～15；观察身份标签，不是正式实体认证 | 2 / 1 / 1 / 2 / 2 / 0 / 0 |

源为腾讯候选适配器`akshare-tencent:akshare.stock_zh_a_hist_tx:task-008-v1+sdk-1.19.1`，结构accepted、价格CNY/股、量股、额CNY、不复权；逐行row-sha256版本。当前绑定库的available=2026-10-18T07:51:15.688495Z、ingested=07:51:15.824265Z，不能回放为2021～2026历史当天已知。accepted/代码形式锚点不认证来源、授权、历史身份或覆盖完整性。

### 七表实物结构

公共参考元数据R为：event_time、available_at、observed_at、ingested_at、source、record_version、evidence_kind、evidence_ref、supersedes_version、revision_reason、run_id。完整原始DDL、列类型/非空/PK、外键和索引信息见机器证据，以下是精简读法。

| 顺序/表 | 实际列与约束 |
| --- | --- |
| 1 schema_migrations | version PK、name、checksum、applied_at；迁移账本，不是行情覆盖 |
| 2 instruments | instrument_id PK、symbol；联合唯一(instrument_id,symbol)，代码形式SH/SZ/BJ；不是已认证的上市实体历史 |
| 3 ingestion_runs | run_id PK、recorded_at；追加批次命名空间 |
| 4 daily_bars | bar_id PK、instrument_id FK、trade_date、adjustment_method；实体/日期/复权口径唯一 |
| 5 daily_bar_versions | version_id PK、bar_id FK、source/source_version、open/high/low/close、volume/amount、event/available/ingested时间、factor_version、quality_status、supersedes_version、run_id FK；来源版本唯一、单根/单后继、版本前驱FK和追加不可改触发器 |
| 6 security_versions | version_id PK、instrument_id/symbol联合FK、exchange、security_type、quality_status、listing_date/delisting_date、periods_json及R；实体/record_version唯一、生命期/时间线/单根/前驱/系统可见推进校验；当前0行 |
| 7 calendar_versions | version_id PK、exchange、session_date、is_trading_day、quality_status、error_reason及R；SH/SZ/BJ日期版本唯一；accepted必须明确开/休市，source_error为空状态并附原因；当前0行，不支持直接写CFFEX日历 |

五库均直接读取`sqlite_master`并与main的SQL定义规范空白后比较：**36个显式表/索引/触发器对象全部一致**，不是只看账本或表名；自动索引、列及FK同时原样记录。全部quick_check=ok、外键检查0异常。

| 迁移 | 实际checksum（五库均与当前代码匹配） |
| --- | --- |
| v1 daily_bar_foundation | `c6d31829bdef4ad9c6f45279c7696cfe94ac6acb9ff016c59320298b8e8dc0bd` |
| v2 security_master_and_calendar | `a4a5c6b2bbf2008d1f452610ecc3213de3dc4fbfe62daa0f55c161e36ef88125` |

没有执行CREATE、迁移或初始化来验证这些结构；只执行mode=ro/query_only下SELECT及只读PRAGMA。五库与存在侧车前后hash相同；再与旧库存清单613库/侧车hash核对，实际变化0。

## 5. WAL/SHM、备份和可复用性

- 当前绑定库及187/2291样本、#40隔离库均无WAL/SHM/journal侧车；观察到journal_mode=DELETE，仅查询没有设置。
- 旧TASK-008 `real.sqlite3`已有 **0字节WAL、32768字节SHM**，保留不动；主文件和两侧车hash前后完全相同，没有checkpoint/清理/搬移。侧车不是已认证备份。
- 在已扫项目/相关Temp范围未找到`.bak/.backup`或备份目录中的SQLite/zip/7z候选；没有可确认的备份清单、计划、保留或还原演练证据。未知位置/任意名称文件及EC2备份未核验；不声称不存在全部备份。
- 187行库和1217行库是不同采集批次，不能仅因重叠行情相同视为互相的正式备份。只读记录和文件hash不等于完整可恢复快照认证。

现存个股可继续供本地L1历史观察；本轮重新确认其文件/结构/批次/日期，旧TASK-M0-M3-DATA-001逐字段读回结果只作为已存在证据引用，未重放写入。不可直接认定正式储备、历史股票池/ST/停牌/退市认证、完整研究或策略许可。

沪深300真实JSON为3个独立版本、4处文件，各550行，范围分别2024-07-09～2026-10-16或2024-07-10～2026-10-19；内容hash匹配。位置为187行Demo根、Temp的M3页面验收根、原工作区m3-core-001、#40新浪验收根（后两处核心/页面副本同hash不加总）。当前8524根没有这些JSON。旧观察缺available/部分ingested/逐行质量保持UNKNOWN；不能自动复制到当前根或强塞A股日线表，也不能据此补齐全A因子。

## 6. 命令、检查结果与剩余前置

| 检查 | 实际执行/结果 |
| --- | --- |
| Git/GitHub | status、remote、stash、worktree、fetch/main及PR44实际head/base/状态；只新增独立任务工作区，不动原分支/两条stash |
| 配置与进程 | Get-CimInstance、netstat、白名单进程参数探针、User/Machine GetEnvironmentVariable、Get-Acl、计划任务/服务/Startup只读查询；证据链如上 |
| 文件与SQLite | `python artifacts/db-path-confirm-001/audit.py`，最终exit0，2260候选路径，5重点库DDL/迁移/quick_check/hash通过；完整本机输出audit-v2.json |
| 依赖 | 既有Python3.12.14 `python -m pip check`，exit0：No broken requirements found.；无依赖安装/升级 |
| 本轮本地完整pytest | **未执行**：本任务明令禁止初始化，完整套件会初始化新测试库。按本次具体要求优先于G11默认全套；没有用旧结果冒称本轮执行 |
| 差异/证据 | JSON/只读断言、无原始行情/凭据/完整环境/内存dump、内部链接和git diff检查；最终输出及提交/PR在发布记录绑定 |
| 新行情/浏览器/样本外/EC2 | 均未执行；不启动/刷新页面，不请求健康端点、不改配置、不接账户 |

一次工具性元数据比对最初将`bytes`键与旧清单`size`键直接比较，错误地把旧库列为变化；没有实际数据库变化。保留audit.json中间证据，统一键后生成create-only audit-v2.json，613库实际hash变化0。另有不存在的备用模板文件及未引用带空格Startup路径的只读命令失败，已用真实deploy.env.example和LiteralPath重新核对；没有数据库操作、业务/测试修改或断言降级。

验收结果：**本任务只读核验已完成，正式研究库结论为“尚未确认”**。应用配置路径、七表及迁移、临时样本归属和备份证据边界已明确；这不是正式数据库建设或来源认证完成。

后续正式入库仍需：用户明确指定正式持久研究目录/库的归属与应用/采集共同绑定；如确实尚无，另行批准建立方案、数据保护/备份与回滚；核对真实来源保存/自动采集/研究许可；解决指数/全A/CFFEX/历史状态存储与时间契约缺口；独立H审查本报告及后续高风险变更。上述任何一步都不在本任务自动执行，不解除核心#37、真实研究、M4/策略或生产门禁。

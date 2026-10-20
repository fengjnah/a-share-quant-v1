# TASK-AWS-DEPLOY-M0-M5-001：既有 EC2 统一页面部署

## 身份、基线与授权

- 类型 implementation / H：既有生产运行、凭据及回滚边界；不改变策略、数据契约或数据库结构。
- 唯一执行配置：OpenAI / Codex Desktop `gpt-6.1-sol`，固定 `high`。2026-10-21 会话 turn_context 实际核验；费用/额度未知；不调用其他模型或代理。同项最多两次不同诊断修复，核心失败停止依赖操作。
- GitHub API 与 EC2 fetch 均确认 main=`6ff4331d8008d47b36df323f9ed4ec283778c419`，main CI test=success。PR39 head=`964a24007ab208d7b10e254a4e86548007c69c4f`，merge=`90dfec6442c188d9e6263be12d90aea58a6dff91`；PR40 head=`88088b0ccda6a5752f7e14c383307d1041006c62`，merge=`26554612e03900749e637e8696e59c56bf7baaa6`；PR42 head=`455894426181b3c20b43e4acbd8c89ac11b7bb5e`，merge=当前 main；三者均已合并。
- 主目录原分支 `codex/m3-remodel-002` / `964a240` 保留，仅未跟踪 `.worktrees/`；两个 stash、全部 worktree 不动。复用干净 `.worktrees/local-demo-verify`，从实际 main 建立 `codex/aws-deploy-m0-m5-001`，没有新建 worktree。
- 用户本任务明确授权现有 EC2 受控部署，优先于 G09/ADR003 的通用不部署/静态发布限制；不自动合并、不增加 AWS 资源、不启用采集、不连接交易账户。用户补充允许资源不足时暂停 Java/节省文件；当前磁盘充足，不删既有备份，不停止 Java。
- G05/G12：H 独立审查待指派，当前自检、部署运维检查及 CI 不冒充独立阶段验收。既有 M3 核心审查/来源认证门禁保持，部署仅受保护的研究展示。

## 实际阅读与范围

已读本基线根 AGENTS.md（无子目录规则）、MODEL_ROUTING_POLICY v1.0、OPEN_SOURCE_RESEARCH_POLICY v1.0、TASK_TEMPLATE、PROJECT_STATUS、DECISIONS、DATA_CONTRACT、INTERFACE_CONTRACT、M3_CORE_CONTRACT、LOCAL_MARKET_DEMO、operations/AWS_RESOURCE_INVENTORY、TASK-M4-UI-002、demo_app、demo_data、storage/db、M3/M4 页面及 deploy 文件。适用 G01–G12，时点、未知状态、认证和数据门禁不变。

调研：复用既有发布目录、symlink、systemd、Nginx/TLS、SQLite backup 设计和历史部署记录；额外只读参考 `codex/aws-001-deploy-safety:deploy/README.md` 和更新脚本，不将未合并代码作为 main 部署。没有新依赖/供应商/核心设计，不启动外部框架调研。网络仅 GitHub、既有 SSH/HTTPS 与必要依赖检查；不调用行情源，不关闭 TLS。

## 恢复与只读检查（2026-10-21 北京时间）

| 项目 | 实测状态 |
| --- | --- |
| EC2 | ubuntu@54.95.115.109，固定 SSH host key 校验成功；Ubuntu26.04 x86_64、2CPU、908MiB RAM、无swap |
| 资源 | root6.7GiB，已用4.7GiB，剩余2.0GiB；MemAvailable180MiB；Java RSS约269MiB |
| 当前版本 | `/opt/a-share-quant-workbench/releases/59ce53999477ad898a2428679f19694b48f03005`，current symlink；DEPLOYED_SHA一致 |
| 服务 | a-share-quant-workbench.service active/running，NRestarts0；127.0.0.1:8513，baseUrlPath quant，只读；MemoryMax240MiB、CPUQuota20% |
| Python/依赖 | Python3.14.4；现有 venv pip check exit0，无破损依赖 |
| Nginx/TLS | nginx配置通过；443受保护/quant/；80原Java入口；Let's Encrypt YE1证书，2026-10-25 15:17:40UTC到期；renew.timer已存在 |
| 认证 | Nginx Basic Auth，认证文件640 root:www-data；health.curl600；严格TLS未认证401、认证200 |
| 数据 | `/var/lib/a-share-quant-workbench/workbench.sqlite3` 147456bytes，quick_check=ok；现有两份147456bytes备份保留 |
| 代码获取 | 本地github git fetch两次失败（reset/连接超时），认证API成功；EC2 fetch成功，随后通过已授权固定hostkey SSH读取Git对象，不降低TLS |
| 发布差异 | main与旧SHA的storage/deploy/pyproject无diff；main更新脚本仍硬限Python3.12，不直接运行不兼容脚本 |

## 验收、备份与回滚计划

只部署实际 main 文件。先校验运行目录与旧Git树的差异、SQLite逐表计数/最近日期和迁移指纹；一致性备份与私有配置归档。新目录准备代码及已验证依赖，不覆盖旧release。隔离副本运行导入、pip check、离线套件与Streamlit AppTest，拒绝生产schema迁移。

切换仅current symlink并重启既有服务；失败立即切回旧symlink并重启，数据库不自动覆盖。旧release、配置和SQLite备份保留。逐项验证本机健康、认证HTTPS、页面WebSocket、实际数据库不变、日志、桌面及窄屏。M0数据状态并入M1；M5无实际页面时报告缺口，不制造路由/回测。

密码仅在已验证HTTPS条件下处理，随机8字符、不写仓库/日志/CLI；更新前备份认证文件，验证未登录/错密码401和正确凭据200。私有凭据文件仅在原有私有位置保存。公网HTTP不得发送或接受量化认证凭据。

## 实际结果

2026-10-21 07:24北京时间实测：现有实例 `i-0b15f62b4e0398d71` / t3.micro / ap-northeast-1（IMDSv2只读核验）。部署运行SHA与本轮核验main一致：**`6ff4331d8008d47b36df323f9ed4ec283778c419`**，Git树`0549eff1e1226ff2d68628ea3ce7829ae72da08c`。发布目录169个Git文件逐一blob匹配；旧release的跟踪文件也与旧Git树完全一致。没有修改应用源文件、服务资源限制、Nginx路由、数据库结构或AWS资源。

新release复制旧venv，保留独立可回滚依赖副本；使用新release的python和PYTHONPATH，不执行带旧路径的console-script。57项锁定依赖逐项匹配；没有安装或升级软件包。Python3.14.4、Streamlit1.66.0、pandas3.0.6、Altair6.3.0、AKShare1.19.1、pytest8.4.2。没有运行main中不兼容Python3.14的旧更新脚本，也没有部署PR29未合并保护实现。

服务启动入口仍为：

```text
/opt/a-share-quant-workbench/current/.venv/bin/python -m streamlit run src/ai_trade/demo_app.py --server.address 127.0.0.1 --server.port 8513 --server.baseUrlPath quant --server.headless true --browser.gatherUsageStats false --server.fileWatcherType none
```

切换后MainPID412495，`/proc/412495/cwd`确认为新release，active/running、NRestarts0。页面操作后MemoryCurrent约135.5MiB、峰值155.8MiB，仍低于240MiB限制；全机MemAvailable154MiB，无swap。磁盘余1.3GiB（82%使用，切换前2.0GiB）；Java PID26015保持运行，没有清理既有文件/备份。未测压力和多用户并发，不将单会话结果外推容量。

### 线上入口与实际页面

| 模块 | HTTPS URL / 导航 | 实际边界 |
| --- | --- | --- |
| M0 | `/quant/`中运行环境、SQLite查询和数据状态 | 没有独立M0页面；保留既有嵌入展示 |
| M1 | https://54.95.115.109/quant/ | 行情查询、真实存储读回；当前0行，不画虚构K线 |
| M2 | https://54.95.115.109/quant/?view=analysis | 现有研究分析；实际操作显示“分析日期之前没有行情” |
| M3 | https://54.95.115.109/quant/?view=market | 新诊断及本地文件入口；来源缺失，SOURCE_UNAVAILABLE / TIME_UNCERTIFIED / BLOCKED，在线查询按钮禁用 |
| M4 | https://54.95.115.109/quant/?view=candidates | 页面选择器包含总览、六阶段、精选、详情、指定股票和风险；市场数据不足、未获准新增多头、0候选 |
| 进度 | https://54.95.115.109/quant/?view=progress | 实际已有进度页面，不称M5回测 |
| M5 | 无已实现页面/路由 | NOT RUN：main无正式回测/持仓服务，未新增假页面或模拟收益 |

M4六个子视图通过现有会话选择器访问，没有伪造独立URL。M2/M3/M4业务和时点门禁不变，`AI_TRADE_READ_ONLY=1`。已有提示文案仍写“数据授权与受保护HTTPS入口核验完成前”，本轮HTTPS已验证，但采集授权/认证继续受限；未为文字更新扩大应用diff。

### 数据与备份

- 云端权威路径 `/var/lib/a-share-quant-workbench/workbench.sqlite3`，147456bytes；7张表，schema_migrations=2，其余6表均0行，行情起止日NULL。未上传本地demo、未开启采集或补数据。
- SQLite Backup API从只读连接生成一致性备份：`/var/lib/a-share-quant-workbench/backups/20261020T231517Z-pre-m0-m5-6ff4331d8008.sqlite3`，147456bytes、600。源/备份quick_check均ok，逐表SQL内容相同；全部线上页面操作后再次比对仍一致。
- 配置/认证私有归档：`/opt/a-share-quant-workbench/validation/TASK-AWS-DEPLOY-M0-M5-001-20261020T231517Z/configs.tar.gz`，600 ubuntu:ubuntu，包含Nginx、认证文件、systemd主配置及drop-in、原有私有健康检查配置。归档有秘密，不上传Git，不在报告展开。
- 原release完整保留：`/opt/a-share-quant-workbench/releases/59ce53999477ad898a2428679f19694b48f03005`。隔离页面测试只用validation目录中的数据库副本。

### 认证与TLS

实际为Nginx Basic Auth，不是Streamlit应用账号。现有Let's Encrypt IP证书严格校验通过，签发者YE1；证书到期`2026-10-25 15:17:40 UTC`。现有quant-cert-renew.timer保持启用；历史最近续期检查成功不冒充实际完成新证书续签。HTTPS `/quant`→308 `/quant/`；HTTP `/quant/`返回404，不在HTTP提供登录，原HTTP Java入口保留。

已将唯一既有账号密码替换为8位随机大小写字母/数字/安全符号组合；保留SHA512-crypt盐化哈希方式，认证文件仍640 root:www-data。认证前先做备份；正确凭据200、错误凭据401、无凭据401。没有移除认证、开放端口或写明文到命令行/仓库/日志。原有用户私有文件已更新：`C:/Users/iyoyi/.config/a-share-quant-workbench/phone-access.txt`和`health.curl`，ACL仅当前用户；服务器对应文件600。旧本地凭据另存私有时间戳副本。报告不含密码。

有限日志检查未发现新密码明文；只检查本次工作台journal及最近1000行quant访问/错误日志，不声称完成全机秘密审计。8位随机密码不能替代后续防暴力尝试控制；本轮未添加限流、MFA或新认证服务。

### 实测验收表

| 断言 | 状态 | 证据 |
| --- | --- | --- |
| 最新main/运行SHA一致 | PASS | 认证GitHub API、EC2 fetch、169个Git blob及实际进程cwd |
| 服务启动、持续运行、原端口/路径 | PASS | active、NRestarts0、1个Streamlit进程；127.0.0.1:8513，/quant/ |
| Nginx及认证HTTPS | PASS | nginx -t exit0；公网页/health200、无凭据/错误凭据401、WSS101及streamlit子协议 |
| 已实现入口/静态资源 | PASS | 5个页面URL及health200；真实index.DucWPHXi.js 200/未登录401，454196bytes |
| 服务器隔离页面冒烟 | PASS | 5个入口+M4六视图11通过/0失败/0跳过、exit0；外网连接阻断、独立数据库副本 |
| 实际EC2浏览器交互 | PASS（隧道范围） | 通过SSH本机转发操作真实服务：M1查0行、M2空数据错误、M3阻断、M4六视图及指定600000/000001保留失败原因 |
| 桌面/窄屏 | PASS（浏览器尺寸） | 1280×900、390×844；关键表单、导航与0候选可用；截图保存本地 |
| 手机公网实机登录 | NOT RUN | 浏览器Basic Auth自动登录不可用；公网TLS/Auth/资源/WSS另由本机真实网络测试通过。隧道UI不冒充公网手机验收 |
| 真实云端SQLite/空数据 | PASS | 路径、结构、只读计数和备份内容核对；未制造行情 |
| 有行情图表、过期行情、来源API失败 | BLOCKED / NOT RUN | 云端无行情且采集禁用；只验证缺失/未认证状态，未发真实行情请求 |
| 不放宽市场准入 | PASS | M3 BLOCKED、M4未获准新增多头/0候选 |
| 日志/重复进程 | PASS（有限范围） | 应用关键异常0；Nginx2条预期密码错误、1条大静态文件临时缓冲warn，无连接失败/超时；1个Streamlit进程 |
| 备份/回滚准备 | PASS | SQLite双边quick_check及内容一致、配置600、完整旧release保留；实际故障回滚演练NOT RUN |
| M5真实回测、样本外/实盘许可 | NOT RUN | 本轮未实现引擎/来源认证/独立核心审查，不改变准入 |
| AWS安全组全量/账单/并发压力 | NOT RUN | 无AWS账户级查询；只核验既有实例IMDS、监听与应用，不增加资源 |

公网测试从用户本机直接请求公网IP、保持TLS校验；页面交互经临时本机loopback SSH转发访问实际EC2。两种证据分开，不将localhost UI当作公网端到端登录。

### 自动化命令与证据

代码测试绑定main `6ff4331d8008d47b36df323f9ed4ec283778c419`；本任务仅追加文档，不修改被测源码。

| 检查 | 实际命令/结果 |
| --- | --- |
| 首次完整离线 | `PYTHONPATH=src python -m pytest -q`，Windows：2869pass/2fail/1skip，exit1，241.68s。两个project_progress CLI子进程默认编码与UTF8读取不一致，UnicodeDecodeError；保留失败日志，不改expected |
| 失败诊断复核 | `PYTHONUTF8=1 PYTHONPATH=src python -m pytest -q tests/unit/test_project_progress.py::test_cli_read_only_simulation_and_candidate_exclusive_creation tests/unit/test_project_progress.py::test_rejected_scenario_does_not_subtract_credit_twice`：2pass/0fail/0skip，exit0，3.47s |
| 最终完整离线 | 同一Python及源码，`PYTHONUTF8=1 PYTHONPATH=src python -m pytest -q`：**2871pass/0fail/1skip，exit0，285.07s**。skip为未显式启用的AKShare live test |
| 依赖 | 本地及EC2新release `python -m pip check` exit0；服务器import新M3/M4 exit0；57项lock匹配 |
| 服务器隔离 | 固定hostkey plink传入Python AppTest脚本，外网socket拒绝、validation副本；11pass/0fail/0skip、exit0；验证期间只短暂停工作台释放RAM，finally恢复旧服务后再独立切版 |
| 公网 | Python requests严格TLS + websockets.sync，12项pass/0fail、exit0；真实静态JS另验证200/401，exit0 |
| Git | `git diff --check` exit0；当前新增仅本任务记录 |

本地日志：`C:/Users/iyoyi/AppData/Local/Temp/aws-deploy-m0-m5-001-offline.log`（首次失败）、`aws-deploy-m0-m5-001-utf8-recheck.log`、`aws-deploy-m0-m5-001-offline-utf8.log`（最终通过）。脱敏服务器JSON、截图位于同一Temp下`aws-deploy-m0-m5-001/`；公网JSON为Temp下`aws-deploy-m0-m5-001-public.json`。不提交原始SQLite、秘密或行情。

服务器完整运维证据目录：`/opt/a-share-quant-workbench/validation/TASK-AWS-DEPLOY-M0-M5-001-20261020T231517Z/`，含`preparation.json`、`server-isolated-smoke.log`、`deployment-result.json`、`authentication-result.json`、`postdeployment-result.json`、`log-check.json`。配置归档仍私有，不作为可公开附件。

### 回滚命令（已准备，未故障演练）

仅回滚代码与依赖，保留当前认证及数据库；在现有Ubuntu操作者账号执行：

```bash
set -e
cd /opt/a-share-quant-workbench
test "$(readlink -f current)" = /opt/a-share-quant-workbench/releases/6ff4331d8008d47b36df323f9ed4ec283778c419
test -f releases/59ce53999477ad898a2428679f19694b48f03005/DEPLOYED_SHA
test ! -e current.rollback-m0-m5-001
ln -s /opt/a-share-quant-workbench/releases/59ce53999477ad898a2428679f19694b48f03005 current.rollback-m0-m5-001
mv -Tf current.rollback-m0-m5-001 current
sudo systemctl restart a-share-quant-workbench.service
curl --fail --silent --show-error http://127.0.0.1:8513/quant/_stcore/health
curl --fail --silent --show-error --config /home/ubuntu/.config/a-share-quant-workbench/health.curl https://54.95.115.109/quant/_stcore/health
```

配置归档`sudo tar -tzf .../configs.tar.gz`可列出；仅在对应配置损坏时逐文件恢复，先检查nginx -t。不要整个归档盲目覆盖。SQLite没有迁移，代码回滚无需恢复/覆盖数据库；数据库异常时先停止写入并单独制定恢复方案。切版脚本实际包含失败恢复旧symlink和restart分支，本次健康成功未触发。

### 未完成项与后续条件

1. 云端无真实行情，不能展示非空候选、真实价格图表或行情过期验收；后续需用户明确的数据授权/受控导入任务，不能复制临时demo冒充生产事实。
2. M5回测页面/引擎、M2六阶段状态机/退出与真实持仓接口尚未交付；本轮仅部署已有代码。
3. M3独立核心H审查、全A历史/身份/日历、CFFEX发布与授权证据、来源正式准入仍受阻；展示部署不解除这些门禁。
4. 需用户手机网络实机登录确认；本次没有真实手机设备。短周期证书后续续签应持续核验，当前timer保持。
5. main旧部署脚本Python3.12限制与现有服务器不一致；后续由PR29保护改造审查处理，本轮未擅自合并或复制未合并实现。
6. 本H运维变更及认证轮换应交独立H审查（计划TASK-AWS-DEPLOY-M0-M5-001-REVIEW，待指派/待冻结证据审阅）；本会话不自称独立审查或正式阶段验收。只提交交付文档PR，不自动合并。

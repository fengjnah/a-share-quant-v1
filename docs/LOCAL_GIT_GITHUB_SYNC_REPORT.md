# TASK-LOCAL-GIT-GITHUB-SYNC-001 诊断与修复记录

2026-10-22（Asia/Shanghai）。目标 `F:\codex-agnes\AI-trade-dev`，远端 `https://github.com/fengjnah/a-share-quant-v1.git`。**实际 Git 网络、认证、普通 PowerShell 与 SourceTree Fetch 验证通过；没有推送业务提交、合并或部署。** 文档 Draft 仍待独立 H，当前实现会话不自称独立审查。

## 基线与执行边界

- 实际 main/HEAD/origin/main 均为 `04e530871e2c8b4889c60027ac8d1ec4275009a2`，初始与验收工作区均干净。开始记录了 remote、branch、toplevel、stash、worktree、配置来源及202个已跟踪文件的SHA256。
- 唯一模型 **gpt-6.1-sol / high**，沿用本会话用户确认的配置；H（认证/本地网络边界），不调用其他模型或子代理。费用未知，预算90分钟；探测有超时上限，无无界重试。此处“探测”指命令/检查操作，未抓包，不能声称精确的底层HTTP请求总数。
- 根 AGENTS、MODEL_ROUTING_POLICY、任务模板、OPEN_SOURCE_RESEARCH_POLICY、DECISIONS、PROJECT_STATUS 已实际读取。适用 G01–G05/G08–G12。只修复 Git 环境，不涉及业务/数据接口；没有修改业务代码、依赖、SQLite、M0/M3、AWS、Nginx、部署、策略或交易账户。
- 独立文档工作区 `C:\Users\iyoyi\.codex\worktrees\local-git-github-sync-001\AI-trade`，分支 `codex/local-git-github-sync-001`，以同一 main SHA 创建；仅提交本报告、任务单与脱敏证据3个文件，不在main提交。
- 原两个stash及所有旧worktree路径均保留。另一个活跃M3工作树的HEAD在核验期间由10c6f2c变为611d2e5，本任务未对它执行checkout/commit/reset；不把并发工作误报为本任务修改，也不宣称其他会话内容完全未变。

## 实际原因与分层结果

| 层次 | 实际证据 | 结论 |
| --- | --- | --- |
| Git安装 | 系统Git2.35.1.windows.2，Codex Git2.53.0.windows.3，均可正常运行 | 没有安装损坏或必须重装的证据 |
| DNS/直连 | github.com解析为20.205.243.166；一次TCP443探测超时；旧Git直连报schannel握手失败，新Git直连报443连接失败 | 本轮两套Git默认连接都失败，不能沿用“Codex此刻直连一定成功”的历史假设 |
| 直连限制 | Windows curl一次直接HEAD返回200，而上述Git与TCP检查失败 | 不能断言所有直连永久封锁；未定位到ISP/中间设备级原因，也不把单次curl成功等同Git可靠 |
| 系统代理 | Windows WinINET ProxyEnable=1、ProxyServer=127.0.0.1:7890；clash-meta PID14372实际监听7890，应用Clash Verge运行 | 确认当前端口，未凭历史值猜测，未改代理软件或系统代理 |
| 协议/TLS | HTTP代理HEAD返回200 Connection established和200 OK；socks5h代理也返回200；Git临时HTTP代理多次返回同一main SHA | 7890支持本轮实测的HTTP/SOCKS；选HTTP CONNECT，TLS验证保持开启 |
| Git代理 | 当前Codex进程、User/Machine重建环境无代理变量；system/global/local/worktree无Git代理项 | Windows系统代理开启没有在本次Git有效配置中体现；为Git明确配置可用代理解决连接故障 |
| TLS配置 | 旧Git系统默认openssl，但全局schannel覆盖；Codex默认schannel；没有sslVerify=false或GIT_SSL_NO_VERIFY | 不盲改CA、SSL backend，不关闭证书验证；代理路径下两版本Git均成功 |
| 认证 | 旧GCM默认取出的现有PAT向GitHub API返回401；Codex GCM现有账号凭据返回200 | 公开仓库ls-remote/fetch成功不证明认证可写；另有默认凭据选择问题 |
| 账号选择 | 临时 `credential.https://github.com.username=fengjnah` 后，**同一个旧GCM**读出现有有效凭据，API返回200及pull/push权限 | 选择正确账号即可，不用复制token、更换助手、删除凭据或重新登录 |
| 新终端PATH | 用User+Machine环境新建PowerShell时找不到git；两级PATH没有Git可执行目录，只有系统PATH中的TortoiseGit目录 | 这是额外的日常新终端问题，不是已能执行git的旧终端发生443超时的原因；追加既有Git cmd目录解决 |

源因拆分：**连接故障是Git没有明确使用当前可用代理、默认直连不可靠；写入认证还有错误的默认凭据条目；新终端另缺持久Git PATH。** 版本差异不是已经证明的根因。没有无依据重装或更新任何软件。

两套Git对照：

| 项目 | 普通Git | Codex Git |
| --- | --- | --- |
| 原确认路径 | `C:\Program Files\Git\mingw64\bin\git.exe` | `C:\Users\iyoyi\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe` |
| 版本 | 2.35.1.windows.2 | 2.53.0.windows.3 |
| 凭据助手 | manager-core，2.0.632+478753bbb7 | manager，2.7.3+5fa7116896c82164996a609accd1c5ad90fe730a |
| 系统配置 | `C:/Program Files/Git/etc/gitconfig` | 运行时native/git/etc/gitconfig |
| 全局/共享仓库 | 同一用户.gitconfig / 原仓库.git/config，前后hash均不变 | 同左，未永久改写Codex配置 |
| 网络对照 | 当前继承环境与重建普通环境都失败；临时代理成功 | 本轮也失败；相同临时代理成功 |
| 认证对照 | 默认现有条目401，明确账号后200 | 原有账号200，未改其凭据库 |

“普通环境”实测采用Windows PowerShell5.1 `-NoProfile -NonInteractive`，从User/Machine注册表重建PATH及相关Git/代理设置，去掉Codex进程专属网络覆盖。四个PowerShell profile候选均不存在。不是声称读取了某个已打开用户终端的全部环境。初始同环境对照还使用了两套Git绝对路径，避免PATH混淆。

## 最小永久修复、原值与备份

修改前已有 `extensions.worktreeConfig=true`，未更改扩展开关。Git默认local配置由多个worktree共享，因此没有把代理写入共享local或全局。只新增：

| 配置 | 原值 | 新值 | 影响范围 |
| --- | --- | --- | --- |
| `http.https://github.com/.proxy` | 无；config.worktree文件原本不存在 | `http://127.0.0.1:7890` | 仅AI-trade-dev工作树、HTTPS github.com；example.com无匹配项 |
| `credential.https://github.com.username` | 无 | `fengjnah` | 仅该工作树的GitHub凭据账号选择；manager-core保持原样 |
| HKCU\Environment\Path | 原5项、REG_EXPAND_SZ，未含Git目录 | 末尾追加 `C:\Program Files\Git\cmd`，共6项 | 当前Windows用户后续新进程；系统PATH及现有Codex进程PATH不变 |

工作树文件：`F:\codex-agnes\AI-trade\.git\worktrees\AI-trade-dev\config.worktree`。其他worktree不会继承这两个工作树项。新增文件之前记录了“原文件不存在”，并在第二项修改前建立私有备份 `config-worktree-before-auth.bak`。Git配置没有凭据URL、密码或token。

PATH修改前以create-only方式保存了原始值与注册表类型到 `user-path-before.json`，并保存新旧hash和作用范围。保留全部原条目及REG_EXPAND_SZ，不使用会截断/重写整个PATH的setx；向shell发送Environment变更通知成功。已有终端仍可能保留旧环境，用户应重新打开终端；若其父进程仍继承旧环境，也需重启对应终端宿主。未重启/注入用户终端。

私有备份、计划、诊断脚本及结果根目录：
`C:\Users\iyoyi\AppData\Local\AITrade\GitDiagnostics\TASK-LOCAL-GIT-GITHUB-SYNC-001\`。
修改前的fix-plan.json、auth-fix-plan.json、path-fix-plan.json与备份均保留，未覆盖旧证据。报告仅提交白名单元数据；不提交原始环境、完整用户PATH、认证响应头或凭据。

## 实际验收

| 验收 | 实际结果 |
| --- | --- |
| 普通Git ls-remote | exit0，main=`04e530871e2c8b4889c60027ac8d1ec4275009a2` |
| 普通Git fetch | `git fetch --no-tags origin` exit0，修复后约1.33秒；无prune/reset/工作区写入 |
| pull初步验证 | `git pull --dry-run --ff-only --no-tags origin main` exit0 |
| 新普通PowerShell全流程 | exit0，6.41秒；where找到`C:\Program Files\Git\cmd\git.exe`，版本仍2.35.1；ls-remote、fetch成功 |
| 实际pull | 先确认工作区干净且HEAD=origin/main，再 `git pull --ff-only --no-rebase --no-tags origin main`，返回 **Already up to date**；无新提交或业务文件变化 |
| push权限与策略 | 先检查现有凭据的API权限及main策略：pull/push=true；main protected=false，有效规则列表为空（核验时点快照，不代表授权推main） |
| 安全push验证 | `git push --dry-run --porcelain origin HEAD:refs/heads/main` exit0、up to date；**没有实际更新远端main或推送业务提交** |
| Codex | 同目标工作树下运行时Git ls-remote exit0；运行时路径/版本仍2.53.0；GitHub connector元数据读取成功；原系统/全局/共享配置hash不变 |
| Git GUI | computer-use技能实际操作SourceTree3.4.6；Ctrl+O选择AI-trade-dev；只Fetch origin，不获取所有远端、不prune、不获取全部标签；完成后对话框自动关闭且无错误，刷新AX确认main与origin/main同为04e5308，待定文件0 |
| GUI保护 | 发现用户遗留的旧Pull失败提示；关闭结果并取消Pull对话框，未执行GUI Pull/Merge/Commit/Push/Checkout；没有自动化登录或凭据对话框 |
| 文件/状态 | **202个已跟踪文件SHA256全部相同**；HEAD、main、origin/main、干净状态和两个stash的ID全部相同；旧worktree路径均在 |
| 配置保护 | 用户.gitconfig、系统Git配置、Codex系统配置、共享.git/config四个文件hash均相同（配置修复/验收阶段）；只增加上述工作树文件及User PATH |
| 依赖/diff | 诊断所用既有Python环境pip check exit0，无依赖变更；报告diff/本地链接/脱敏断言单独执行 |

SourceTree GUI证据是实际原生Windows操作和返回的界面/可访问性状态，不是仅从配置推断；没有保存截图文件或提交界面中的其他仓库内容。GUI配置读取显示GitSystemPath=`C:\Program Files\Git`、GitWhichOne=1、ProxyServerMode=OperatingSystem；没有更改GUI Git安装路径或认证设置。

## 回滚

仅撤销本任务两项Git配置，保留其他后来添加的内容（文件可留空，无需删除）：

```powershell
& 'C:\Program Files\Git\cmd\git.exe' -C 'F:\codex-agnes\AI-trade-dev' config --worktree --unset-all 'http.https://github.com/.proxy'
& 'C:\Program Files\Git\cmd\git.exe' -C 'F:\codex-agnes\AI-trade-dev' config --worktree --unset-all 'credential.https://github.com.username'
```

User PATH精确回滚使用已保存原值和类型，并在发现后续PATH变更时拒绝覆盖：

```powershell
& 'F:\codex-agnes\AI-trade-main-demo\.venv\Scripts\python.exe' 'C:\Users\iyoyi\AppData\Local\AITrade\GitDiagnostics\TASK-LOCAL-GIT-GITHUB-SYNC-001\rollback_user_path.py'
```

回滚会撤销本次可用性修复；未在成功的日常环境上实际执行回滚。回滚后重新打开终端继承环境，禁止覆盖后续用户PATH配置。没有备份/导出Windows全部凭据库，也没有清空、删除或手工改写凭据；正常Git/GCM的内部缓存维护未单独审计，不宣称逐字节未变。没有被本任务显式删除的凭据需要恢复。

## 失败记录与可验证限制

- 原始两套Git失败均保留在network-before.json；不能把当前Codex也失败的事实隐藏成只旧版本有问题。
- 旧Git不支持将show-origin/show-scope与get-urlmatch组合；写入已成功，改用支持的get-regexp及单独get-urlmatch读取确认，没有据此重复改配置。
- 首次新PowerShell找不到git，发现持久PATH缺口后补齐；原失败结果保留。一次后续运行因create-only证据文件已存在拒绝保存，未覆盖失败文件，也不把未知输出当成功；最终使用新文件名完整重跑并获得exit0。
- 诊断摘要生成器有一次缺括号SyntaxError，发生在读取/写入之前；修正后生成成功，不涉及配置或业务文件更改。
- 网络验证是有界时点检查，未做长期监控；依赖Clash继续运行在已验证端口7890及账号凭据继续有效。没有认证条款、凭据过期日期或ISP级路由诊断的完整结论。
- 完整交易系统pytest **NOT RUN**：任务未改业务/测试/依赖，且明确只处理Git、不得处理SQLite数据；本轮以实际Git/认证/GUI/文件保护检查验收，不创建应用测试库。未把历史业务测试绿灯冒充本轮执行；G11的未运行项在此明示。手机、行情实网、样本外、AWS和实盘均不适用/未执行。

完整脱敏摘要及结果/备份文件hash见 [TASK_LOCAL_GIT_GITHUB_SYNC_001.json](evidence/TASK_LOCAL_GIT_GITHUB_SYNC_001.json)，执行配置与门禁见[任务单](tasks/TASK-LOCAL-GIT-GITHUB-SYNC-001.md)。本轮不需要重新安装Git或升级SourceTree。独立H计划 TASK-LOCAL-GIT-GITHUB-SYNC-001-REVIEW 待指派，只审本次scope/回滚/脱敏/验收，不合并本Draft或解除交易系统门禁。

参考资料（只核对配置语义，不引入外部源码/新依赖）：[Git http.proxy](https://git-scm.com/docs/git-config#Documentation/git-config.txt-httpproxy)、[worktree专用配置](https://git-scm.com/docs/git-worktree#_configuration_file)、[GCM账号选择](https://github.com/git-ecosystem/git-credential-manager/blob/main/docs/multiple-users.md)、[GCM配置](https://github.com/git-ecosystem/git-credential-manager/blob/main/docs/configuration.md)、[Windows进程环境继承](https://learn.microsoft.com/en-us/windows/win32/procthread/environment-variables)、[环境变更通知](https://learn.microsoft.com/en-us/windows/win32/winmsg/wm-settingchange)。动态文档访问于2026-10-22，未冻结外部源码版本；操作正确性以上述本机实测为准。

# TASK-022A-H：高强度审查、阻断修复与验收记录

执行日期：2026-10-18（Asia/Shanghai）。本报告先记录开始时问题，后续按实际输出追加修复和复核结果。

## 任务单与规则

- 编号：TASK-022A-H。已搜索任务登记、文档及分支，未发现同名任务；TASK-022、TASK-022-REVIEW、TASK-022A 分别在独立分支，不假定已进 main。
- 唯一实现/主审模型：GPT-6.1 Sol / High，H；依据本会话用户对当前配置的明确确认，工具没有独立运行时型号/费用字段，不声称测得实际费用。本轮不切换模型/档位。
- 已实际阅读：根 AGENTS、MODEL_ROUTING_POLICY、TASK_TEMPLATE、OPEN_SOURCE_RESEARCH_POLICY、DATA_CONTRACT、INTERFACE_CONTRACT、ACCEPTANCE_TESTS、DECISIONS、TASK-022/022-REVIEW/022A 报告及相关源码/测试。G01—G12 均适用：保护现场、同一执行配置、时间与未知语义、默认离线、真实证据分列、无生产/合并/部署、绑定冻结提交的独立复核。
- 用户本任务明确授权审查后最小修复，并要求独立上下文最终复核；这覆盖仓库“review TASK 只读”的一般范围限制。主会话的实现自检不冒充独立审查；最终复核使用单独编号/干净上下文、同一具体 H 型号，不做异模型交叉验证声明，不委派实现。
- main/API 已核实 `2a5332448b32083ddbedc6b16ea0cf49057e3cb8`；PR #22 OPEN/Draft，base 同 main，head 精确为 `33e33c8e0583b70e1864ca7fb40e94152a338b6c`。启动时 CI run `39131008639` success，reviews 0，1 条初步评论列出 G.1/G.3/G.4/G.5 问题；CI 绿灯不等于独立验收。
- 新工作树 `codex/task-022a-high-review` 从该 head 创建；原 17 个工作树、1581 个纳入清单文件先保存状态/索引/差异/文件哈希。原 TASK-022/A/REVIEW 工作树均未修改。
- 开源调研：复用 TASK-022 `2b5223954c90b9d99f1e0798990946a982736ed7` 和 TASK-022-REVIEW `2a01a24ec1b2d71faace91490418523c2a95d5d9` 的研究与原样本；不引入项目源码或新依赖，不进行真实 CFFEX/AKShare 重试。旧报告把 404 等同休市、把契约数据集当物理表等结论需勘误，不能继承为已验证。R04 数据授权与 HTTPS 生产可达性保持独立未知/未验收。
- 允许：两个 CFFEX 模块、必要的独立契约/读时过滤与离线测试、审查报告/清单；禁止：正式 Schema/交易策略/主分支/生产库、旧证据改写、未经证明的删除或真实采集。每一失败项仅按不同诊断依据做最小修复，不扩大依赖实现；核心契约冲突保持阻断。

## 起始证据与问题清单

已在未修改的指定 head 实际运行完整离线套件：**472 passed、1 skipped，43.43 秒，退出码 0**。使用已有验证虚拟环境，显式 PYTHONPATH 指向本工作树；没有排除 project_progress 文件，也未安装/升级依赖。本机恰好有兄弟工作树真实 CSV，所以原 26 个测试实际执行；这不能证明干净 CI 会执行这些 fixture 测试。

基线独立复现：重复一行排名仍解析为 243 行；周五数据 available_at 为周六 `2026-10-17T01:30:00Z`；event_time 为观察时间 `08:35Z`；省略合约返回 39 个聚合会员；记录没有 supersedes_version；HTTP 404 被归为 no_session。原始复现 JSON 位于本机外部日志，不提交原始 CSV。

| ID / 严重度 | 根因与影响 | 最小修复与契约边界 |
| --- | --- | --- |
| F01 BLOCKER | `_next_session_floor` 只是日历日加一，凌晨抓取还可能落到当天；无交易日历/时段证据 | 注入有时点与来源的 CFFEX 日历；逐日验证周末/假日/未知，缺少则失败关闭。现有 SQLite 只支持 SH/SZ/BJ，不能复制 SH 日历冒充 CFFEX |
| F02 HIGH | 404/异常字符串匹配推断 no_session，把未发布/路径故障当休市 | 结构化传输/响应状态；只有明确日历休市证据才 no_session；404 保持不确定，不从响应推断未发布原因 |
| F03 HIGH | `contract=None` 汇总不同到期月份，某合约多/另一合约空可以配成假净额 | 要求显式单合约，输出合约/到期年月/交易日/范围；不凭 OI=0 推断换月，跨合约/到期日/换月保持未实现 |
| F04 HIGH | 文档称保留 supersedes_version，模型却无该字段；哈希/run_id 不是持久幂等登记 | 实现明确的修订比较/可见版本读契约，重复与更正分开；不建第二套数据库或声称已持久化，正式持仓仓储仍阻断 |
| F05 HIGH | named set 去重只检查 ranks 1..20，重复行仍参与求和；mixed 缺少相同完整性校验 | 统一两个解析路径，严格重复排名/会员键/类别/合约/日期及完整榜单校验 |
| F06 HIGH | volume side 也塞进 open_interest/change 字段 | 分开 volume/volume_change 与持仓字段，净额只消费 long/short，不重复转换手数 |
| F07 HIGH | GBK decode(ignore)、混合表头按字段数猜测、任意单字段行被跳过 | 严格编码/完整表头/列数/数字/日期/合约月份，拒绝 HTML/截断/漂移/非法字节；不伪造来源事实 |
| F08 HIGH | 测试依赖其他工作树，缺失就跳过；“存在单侧”的断言没有验证 actually found | 默认使用已标注合成夹具，反例不依赖个人路径；真实证据作为显式离线重放单独报告 |
| F09 MEDIUM | requests.get 默认允许重定向，网络/HTTP 错误混用；timeout 无边界校验 | 显式无自动重试/重定向、有限 timeout，异常分类和无敏感错误摘要 |
| F10 HIGH | event_time 直接用 observed_at，事实时间与系统时间混淆，缺少真实读时过滤 | 事实时点来自该交易会话收盘；as_of 同时检查 available/ingested/版本链，不实现回测引擎 |
| F11 MEDIUM | 原报告称 futures_rankings 已有物理表及未来函数等 VERIFIED，与代码不符 | 保留历史报告，在本报告给出勘误/当前范围；未创建正式 futures 表，不擅自迁移 |

## 冗余审计

见 [冗余审计](TASK_022A_REDUNDANCY_AUDIT.md) 和 [逐文件清单](TASK_022A_FILE_INVENTORY.json)。先提交审计后才修复；本轮删除 0 个文件，未知与唯一证据均保留。

## 修复、接口及勘误

实际修复与 [局部契约](TASK_022A_CFFEX_CONTRACT.md) 对应：统一 named/legacy/mixed 校验；拒绝重复排名/同侧会员/残缺段；严格编码与数值；volume 独立字段；显式单合约与 as_of；CFFEX 会话端口和不可用门禁；结构化 404/HTTP/网络分类；载荷比较及调用方完整链的可见版本读取。未新增第三方依赖。

| 问题 | 代码范围验收 | 仍未完成的集成门禁 |
| --- | --- | --- |
| F01 / F10 时间 | 已验证：会话收盘 event_time、未知发布时间保留 null、周末/合成假日/迟到/盘前边界、日历知识截止及实际 available/ingested 过滤 | 真实 CFFEX 日历、历史发布时间与权威持久读路径未验收；不能批准接入正式回测 |
| F02 404 | 已验证：响应不证明休市/未发布，只有独立可见 closed 日历才能 no_session；保留 HTTP 状态（若可取得） | 没有自动判断 unpublished 的证据，也未部署真实发布监控 |
| F03 汇总 | 已验证：缺合约/错误合约拒绝；同会员/范围/合约/日期两侧匹配，缺侧 null、零值已知，legacy/UNKNOWN 不混用 | 跨合约净额、真实到期日和换月规则未实现；expiry_month 仅 YYMM 标记，rollover_flag=null |
| F04 版本 | 已验证：显式前驱/修订依据、不可倒退的时间、重复载荷不重写旧记录、缺父/分叉/重复版本拒绝、按 as_of 选可见版本 | **尚无持久幂等登记、版本账本、事务写入或权威完整历史**；纯函数不是仓储，G.4 不算整体完成 |
| F05 / F07 解析 | 已验证：两路径共同校验、重复/格式漂移/编码/截断/空段失败；独立复核首次发现的残留 HIGH 已在新 SHA 修复 | 结构校验不能证明源数据真实性/完整合约宇宙/所有历史格式 |
| F06 字段 | 已验证：volume/change 与 OI/change 分开；供应商整数原值保留，无二次单位转换 | 未开展新的真实数据字段或持仓所有权验收 |
| F08 测试 | 已验证：默认使用标注合成夹具，无个人目录/缺失即跳过路径；单侧场景确实存在 | 合成通过不等于真实来源验收 |
| F09 传输 | 已验证：HTTPS 域名、证书验证、有限连接/读取超时、一次 GET、无自动重定向/重试、响应大小和资源释放、异常链保留但不输出秘密 | 没有当前 HTTPS 生产请求或端到端时延 SLA 验收 |
| F11 文档 | 本报告勘误，旧报告保留；Schema v2 / SQLite / 策略代码未改 | futures_rankings 只是契约数据集，正式物理表与回测引擎均未实现 |

另有实际样本勘误：旧报告将 2010/2019 笼统写为“无具名、仅类别”，但保存件实际是类别段加具名段；裸会员名的代客/自营范围仍 UNKNOWN。这不支持任意年份的完整具名覆盖，更不能证明最终客户身份。旧报告的 VERIFIED 字样不适用于本次完整验收。

13 份旧 CSV 在最终代码 `72b176aac256f1f6dd2eb6ce9f2a864919c21711` 上再次离线重放，全部 parse 成功：2010 三份各 66 个领域行、2019 一份 198 行（均 mixed），2020/2024/2025/2026 九份各 240 行（named）。这是每个 CSV 数据行展开三榜单后的数量，不是新 HTTP 返回行数。哈希、日期、合约及限制见 [样本重放摘要](TASK_022A_SAMPLE_REPLAY.json)。0 次真实请求；因真实 CFFEX 日历和正式仓储缺失，没有 build/入库/生产读回验收。未提交原始 CSV/ZIP/正文。

## 独立上下文复核

TASK-022A-H-VERIFY 以单独空白上下文、显式 GPT-6.1 Sol / High 做只读复核，根会话未委派实现。它核对冻结 SHA `0f7cb1cca96dc8ccac66f5501c485c1fc6bd2d12`，实际找到了首轮代码残留 HIGH：mixed 声明某段后删除该段全部数据会静默降级。原复现分别返回 legacy/6 行及 named/60 行，ingest=success。根会话只增加空声明段拒绝与两个精确反例，再冻结为 `72b176aac256f1f6dd2eb6ce9f2a864919c21711`。

原独立上下文在新的 detached 工作树重新阅读差异、执行相关及完整回归，结论为：**该 SHA 的限定离线修复范围通过，未发现剩余 BLOCKER/HIGH；生产与真实数据验收不在通过范围**。完整边界见 [独立复核记录](TASK_022A_INDEPENDENT_VERIFICATION.md)。后续报告/元数据提交不扩大这个结论的代码范围；任何源码再变更须重新复核，不能沿用旧批准。

## 实际测试与可复现命令

实际解释器：已有验证 venv，Python 3.12.14；pytest 8.4.2、jsonschema 4.26.0、Streamlit 1.66.0、pandas 3.0.6、Requests 2.34.2、AKShare 1.19.1。没有安装、重建或升级环境；原报告缺 jsonschema 的环境未被假装修过。本轮环境已包含声明的依赖，pip check 实际退出 0。

| 执行上下文 / 版本 | 实际输出 | 退出码 |
| --- | --- | --- |
| 主会话：未修改 33e33c8 基线全套 | 472 passed, 1 skipped，43.43s | 0 |
| 主会话：首批新增反例（两 CFFEX 文件） | 111 passed，0.64s | 0 |
| 主会话：第一轮全套 | 557 passed, 1 skipped，40.54s | 0 |
| 主会话：冻结首版全套 | 566 passed, 1 skipped，39.95s | 0 |
| 独立复核：首版定向 | 120 passed，0.77s | 0 |
| 独立复核：首版完整首次 | **2 failed, 564 passed, 1 skipped**，37.37s | 1 |
| 独立复核：首版仅设置进程 UTF-8 重跑 | 566 passed, 1 skipped，41.73s | 0 |
| 主会话：空段修复后定向 | 122 passed，0.78s | 0 |
| 主会话：新冻结 SHA 完整 | **568 passed, 1 skipped**，43.35s | 0 |
| 独立复核：新冻结 SHA 定向 / 完整 | **122 passed / 568 passed, 1 skipped**，0.82s / 42.99s | 0 / 0 |
| 两上下文依赖检查 | No broken requirements found. | 0 |

独立首次的两个全套失败来自既有 project_progress 子进程输出：Windows 本地编码被测试按 UTF-8 解码，出现 UnicodeDecodeError / stdout=None；只设置当前进程 PYTHONUTF8/PYTHONIOENCODING 后原样重跑通过。没有排除文件、改测试期望或把失败抹掉。唯一跳过项是未显式启用的真实 AKShare 集成，不计通过。根会话从开始就设置了 PYTHONIOENCODING，因此未出现该环境错误。

以下是在已安装项目声明依赖的环境中、从仓库根目录可复现的命令（不依赖个人工作树路径）：

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
python -m pytest -q tests/unit/test_cffex_rankings.py tests/unit/test_cffex_high_assurance.py
python -m pytest -q
python -m pip check
git diff --check
```

干净环境按 `python -m pip install -e ".[test,demo]"` 安装已有声明；本轮未实际重装，也没有引入新服务或依赖。未配置 mypy/专用 lint/漏洞扫描工具，本轮未安装它们，不能称为完成全依赖许可或漏洞审计。

实际完整输出、基线复现 JSON、前后现场哈希和独立挑战日志保存在**本机外部日志目录**（不作为项目依赖链接）：`task-022a-h-20261018`。关键文件名：baseline-pytest.txt、baseline-reproductions.json、full-first.txt、full-final.txt、full-after-independent-fix.txt、verify-adversarial.log、verify-full.log、verify-full-utf8.log、verify-v2-focused.log、verify-v2-full.log、verify-pip-check.log。仓库只提交脱敏摘要/哈希，原始响应及其他任务补丁不提交。

## 最终分域状态与未解门禁

[脱敏测试/日志哈希/代码 blob 证据](TASK_022A_TEST_EVIDENCE.json)保留两个上下文的真实输出和首次失败。结束时逐项比较原 17 个工作树、1581 个清单文件：HEAD/分支/状态、索引、暂存和未暂存差异哈希、文件字节均未变；没有删除旧工作树。新增修复及两个冻结审查树保留，不清理。被审源码/测试相对独立复核 SHA 没有后续改动；后续只追加审查文本和脱敏摘要。

| 域 | 状态 | 准确范围 / 下一步 |
| --- | --- | --- |
| 代码质量验收 | VERIFIED（限定代码/离线范围） | 新冻结 SHA 经独立上下文实际复核，未发现剩余代码 BLOCKER/HIGH |
| 未来函数与时间语义 | PARTIAL | 注入日历及读时门禁已验；真实 CFFEX 日历和权威历史数据路径仍阻断正式回测 |
| 数据缺失与会员范围 | VERIFIED（限定解析/派生范围） | 单合约、UNKNOWN、零值、404 原因不确定等离线反例通过；不证明原始数据真实完整 |
| 版本链与幂等 | PARTIAL | 纯比较与调用方链读取可测；正式持久约束、全局去重、事务/审计账本未实现 |
| 仓库冗余治理 | VERIFIED（本轮审计范围） | 清单先提交、0 删除；未知/唯一证据保留，未清理其他 worktree |
| 测试与 CI | 本地 VERIFIED；新 PR CI 以实际运行结果单列 | 完整两次上下文回归如上，不能把原 PR #22 CI 当新 PR CI |
| 数据授权 R04 | UNKNOWN | 本轮未新增授权/法律确认；生产/商业/再分发仍为未解门禁 |
| HTTPS 生产可达性 | UNKNOWN（本轮未执行） | 旧 443 失败是历史线索，本轮没有连接探针或真实行情请求 |
| 真实网络 / UI / 样本外回测 / 生产部署 | 未执行 | 不以离线绿灯或旧 HTTP 文件替代 |

**整体 PARTIAL，不批准生产或正式策略接入**。仍未解的高风险集成条件是可靠 CFFEX 日历/历史可得性、持久仓储版本/幂等、R04 与 HTTPS；这些不是本次被伪造关闭的验收项。后续分别立独立 H 契约/来源/仓储验收任务，再决定采集器与调度，不能直接开始全历史回补。

交付独立 Draft PR，关联原 #22；原 PR/评论和历史分支保持。没有自动合并、部署、清理或更改选股/入场/止损/仓位逻辑。分支和最终提交以 PR 实际 head 为准；报告中的 SHA 精确绑定接受复核的源码版本。

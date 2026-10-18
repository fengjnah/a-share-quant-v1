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

## 验收记录（执行中）

修复、测试与独立复核尚未完成；不能以本报告存在或基线 472 passed 宣称修复通过。后续在本节追加实际命令、失败/通过及未验证项。

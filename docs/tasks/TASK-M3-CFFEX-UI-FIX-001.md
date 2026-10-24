# TASK-M3-CFFEX-UI-FIX-001（正式数据库版）

## 身份、模型与基线

2026-10-24；implementation / H（正式库只读边界、来源质量展示）。用户已明确授权当前 `gpt-6.1-sol / high` 执行，覆盖任务初稿的“Agnes”；单一模型，不调用子代理/API，费用未知。预算 90 分钟；同项两次不同诊断修复仍失败即停止，核心失败不扩大范围。

实际 dev/main 与远端 main：`8450531b9ccba497b0a5b7b4a4b15604c2c5cf79`。PR57 head `40ff4ffc1bb4f102b1bc0e3f399c2a11ae2ed034`，merge `0dc0b152fedd9d8ec9b15893dfd16468e25969e2`；PR58 head `5d77a5e62f9f3e7e3a7201a4b7d1abc282781ddf`，merge 为本 main。GitHub API 与 git ls-remote 实际核实。

dev/main 保持干净。本任务使用从该 main 创建的独立 worktree `C:\Users\iyoyi\.codex\worktrees\m3-cffex-ui-fix-001\AI-trade`，分支 `codex/m3-cffex-ui-fix-001`；不改 main、不覆盖其他工作区/未跟踪文件/stash。现有 8524：dev/main 的 demo_app.py，parent5456/listener7508，正式库只读，未设置测试库变量。

用户最新要求“真实数据，分支 main”：8524 **保持 dev/main**，不切换修复分支，不接测试库。修复仍按原任务 Draft PR 交付、不自动合并；未合并的修复只能在隔离回归中验收，不能冒充 main 已修好。两项要求按“main 作为正式运行分支，独立 PR 作为待审修复”处理，明确披露这一边界。未解除正式门禁则不写库、不用样本替代。

后续明确授权覆盖上述本 TASK 默认限制：用户再次指令“正式库添加 CFFEX 持仓”，并明确确认仅对 2026-10-23 IF/IH/IC/IM 原始观察数据给予一次正式入库例外，其余认证/研究/策略门禁保留；随后明确指令“页面修复合并应用到 main”，覆盖原任务不自动合并限制。没有独立 H 结论，不伪称原 G12 已满足；仅按用户指令合并页面，不解除业务门禁。

执行期间 main 又合入 PR29/52，变为 `d10b281b84dd6950188aa010f3b9e6977f25d1bd`。首次安全快进因分叉停止，未覆盖文件；在任务分支整合该新基线为 `a57e6f3a9eb6a77b98d49382ace89a1c19a3d472`，三个页面/查询文件与已测 `031824f6204385a10cd86fc59452bed2de483677` 完全相同，再快进本地 dev/main 并只重启 8524。未操作 AWS；新增主线部署文件仅继承，非本 PR 差异。

## 已读与规则

根 AGENTS、MODEL_ROUTING_POLICY v1.0、TASK_TEMPLATE、OPEN_SOURCE_RESEARCH_POLICY v1.0、M3_CORE_CONTRACT、M3_CORE_SOURCE_ACCEPTANCE、DATA_CONTRACT/INTERFACE_CONTRACT（沿用时间、未知与认证）、数据字典及 PR57 结果报告；实际阅读页面、只读查询层、collector/session、存储入口和对应测试。无下级 AGENTS。适用 G01–G12，尤其 G06–G10 不改时点/状态、不绕过门禁、无正式写入前先核验。

外部调研不适用：已定位现有路由小修复，复用工作台连接、原查询/存储与 UI，不新增依赖、来源、算法或架构；不将旧报告当真实来源认证。

## 实施前定位与边界

| 问题 | 证据 / 最小修复 |
|---|---|
| 路由不可达 | `market_analysis_page.py:122–135` 的 cffex 条件嵌在 fear_greed/price_proxy 分支；`_values` 的 blocked 提前返回也使原始表不可见。将原始持仓模块调用放到父 render 的 cffex 段，保留八个核心诊断及其阻断，不改变评分 |
| 仅测试库绑定 | cffex page 仅 `_open_test_db`，未消费父 render(db)。显式传工作台 db，重新构造 read_only/require_existing 连接，忽略测试库变量；证据根复用 demo_app 的 sqlite/evidence 约定 |
| 元数据不完整 | 页面需展示存储质量/证据种类，查询返回具体版本的原值；不把结构 accepted 解释为来源认证或研究许可 |

允许三页/查询文件、针对回归、任务和结果报告。禁止 Schema/checksum、H1/M1、collector/评分/策略、正式库数据、AWS、自动合并。collector 问题只诊断/报告，不继续依赖它做正式入库。

## 正式写入门禁

正式库 `F:\codex-agnes\AI-trade-data\sqlite\workbench.sqlite3`，已有只读证据：v5、31表、CFFEX0行、hash `2d38f34d3a6a26026d576e24896f117ef68e017deae286a6293b5faba4ac333f`。PR57 的独立 H/业务门禁仍 PENDING；本次精确 review TASK 的 GitHub issue 搜索为空，没有取得解除门禁证据。

以上为用户例外授权前的状态。授权后采用既有有界 CffexRankingsClient（每品种 HTTPS 一次、失败后 HTTP 一次，0 重试、5秒超时、每响应2MB）新取回四份响应，不从测试库复制。通过既有 Evidence/Catalog 接口在正式库保存原始证据/传输证据、BLOCKED 尝试与 UNKNOWN 质量决定；重复写入相同原始层记录不增加行。没有写入日历、cffex_report_versions/cffex_rank_rows、输入快照或分析结果。正式库数据文件改变仅限此已授权范围，Schema及旧七表内容不变。

collector 在 fetch/parse/build_record 的早期失败只返回 CollectResult，尚未形成持久 attempt/raw 关联，不能假定 PR57 的 save_cffex 异常审计覆盖它。合成日历与原始文件 mtime 的时间证据也不能作为正式认证。本任务后续只做隔离反例、正式库只读完整性/备份安全核验，不发真实请求、不采集、不将测试库840行复制到正式库。

进一步核实：`cffex_sessions.py` 把 2026-10-24/25 周末写为开市，不可用于正式版本的 available_at。故原始层可以按用户例外保存，结构化采集仍 BLOCKED；上述例外前“无真实请求”计划已被用户范围明确的授权覆盖。实际响应4份、可解析840行；不是840条正式持仓版本。详见最终报告。

## 验收与交付

先增加回归复现：父 M3 空库/三模式必须到达 CFFEX 原始表；原八模块诊断均保留；正式连接优先于测试变量、实际只读、空数据提示、质量/来源元数据。跑相关测试、完整离线套件、pip check、diff；全部禁网且使用隔离临时库。已有五项 v2 搬迁夹具失败不在本任务修复范围。

8524 浏览器用实际正式空库验证模块与提示，截图/执行日志在 Git 外 `F:\codex-agnes\AI-trade-local-state\m3-cffex-ui-fix-001`。正式业务 E2E 仅在采集/入库/读回/浏览器全部通过时 PASS；本次门禁未解除则保持 BLOCKED/PARTIAL，不能以空库 UI 通过代替真实 E2E。

交付 Draft PR；独立 H 计划 `TASK-M3-CFFEX-UI-FIX-001-REVIEW`（待用户指派独立执行配置），绑定最终 SHA，审路由、正式只读、原始事实/研究门禁分离及 collector 阻断。未经独立审查不合并、不解除 M3/M4 门禁。

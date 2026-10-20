# TASK-M4-UI-002：交易模式导向选股监控工作台

## 身份、基线与执行边界

- implementation / L 展示整合：仅组织既有输出，不设计状态机、市场评分、退出/仓位规则。唯一执行模型 OpenAI / Codex Desktop `gpt-6.1-sol`，固定 `high`；2026-10-20 当前会话 turn_context 实测。费用/额度未知，不调用其他模型/子代理；同项最多两次不同诊断修复，核心失败立即停止依赖开发。
- GitHub API核实main=`94cdd487bfd4633ecc2f002aad014f98dec961a5`，本地存在相同提交；原M4 PR28已合并，head=`765ec321d35f70d27b96958f360cc4e417bf6ee4`，merge=`f46347bb492fd8474e38f5fa786a8c81a47c8a6d`。初次git fetch因TLS连接中断失败，未降TLS，使用已认证GitHub API与实际Git对象确认基线。
- 复用干净既有 `.worktrees/local-demo-verify`，分支 `codex/m4-ui-002` 从上述main创建；主目录 `codex/m3-remodel-002` 的未提交M3改造与测试不动。不新建worktree，不碰AWS、Nginx、登录认证、数据库契约或M0/M2/M3/M5实现。
- 已读：AGENTS、MODEL_ROUTING_POLICY v1.0、OPEN_SOURCE_RESEARCH_POLICY v1.0、TASK_TEMPLATE、DATA_CONTRACT、INTERFACE_CONTRACT、PROJECT_STATUS、DECISIONS、M3_CORE_CONTRACT，以及M4/M2/SQLite/M3相关实际源码和测试（上述SHA）。无子目录规则。适用G01–G12；延续用户不额外创建审查TASK的要求，登记本次L展示变更供既有人工PR审查队列，不把自检称独立审查。提交PR，不部署。
- 调研不适用：仅稳定既有输出的展示和输入整合，不引入外部实现、依赖、供应商或核心算法；复用项目已存真实行情及M2指标。许可证/数据授权保持既有候选研究源限制。

## 编码前页面审计（实际代码）

现有M4在 `demo_app.py?view=candidates` 进入 `daily_candidates_page.render(db)`，Streamlit直接渲染，无独立前端框架/模板/CSS。当前是表单、宽表、图表及详情堆叠的单页；缺少总览导航、阶段视图、多股票输入、独立详情与集中风险面板。已有load_batch最多20股/420日、严格/趋势两模式、真实SQLite版本读取、M2技术评分、结构/ATR止损、1%资金风险预算、未知状态阻断及缓存。名称按历史可见主数据读取，缺失明确未知。现有验收数据是腾讯候选源600000.SH历史，非实时、非全A覆盖。

实际正式规则与目标差异：M2 `m2-research-v1`仅日线趋势40分、独立放量突破25分（≥1.5倍前5条均量）、缩量回调20分（≤0.7倍）、一阳穿前一日三线15分；严格模式=日线趋势且任一形态，**不是**严格穿三线专用模式。周样本MA5/MA20尚非认证周线低位多头。没有首次/二次顺序、天量换手、持续横盘/回撤、B点、次日跳空阈值、持仓MA5两交易日退出状态机。不得把独立形态映射为S0–S6或把连续行情条数称交易日数。M2股数未按交易单位验证，M4继续置空。

M3新core诊断有市场/宽度/恐贪和strategy_admission，但契约明确仍有独立审查/来源时点准入限制，现有M4 loader仅返回未验证MarketState，没有获准正式市场结果的运行入口；本轮不复制M3计算、不读另一任务未提交页面、不自行生成全A等权/市场分数。M5/真实持仓/模拟成交服务在src实际未实现，不伪造记录。

## 数据接口映射与本轮实现范围

| 模块/页面字段 | 实际接口 | 展示边界 |
| --- | --- | --- |
| M0 行情/时间/来源 | demo_data.read_bars → SQLiteMarketDataRepository.get_bar | 严格版本可见性；真实OHLCV，不补价格 |
| M1 行情入口 | demo_app 工作区 | 原路径与认证/反代参数保持不变 |
| M2 MA/ATR/量比/独立条件/分数 | trading_analysis.Analysis.frame / summary | 显示公式输出及事件日期，不能标记首次/二次或B点 |
| M2 止损/1%预算 | Analysis.risk → Evaluation.risk | 两类止损分别展示；无交易单位/状态则不输出仓位 |
| M3 市场闸门 | CandidateBatch.market / MarketState.allows | 仅如实显示现有许可；未完成计算不开放新多头，无固定评分 |
| M4 候选/排除/多代码 | load_batch / CandidateBatch.evaluations / candidates | 复用单股已有读取；失败代码保留，不因分数隐藏指定股票 |
| 阶段/行业/基本面 | 当前无正式输出 | S0–S6能力表与“阶段待识别”；行业/基本面分数未知，不做前端状态机 |
| M5/真实持仓/交易退出记录 | 当前无实现 | 显示未接入及依赖；MA5相对位置仅观察，不宣称持仓或退出 |

本轮交付六视图：每日交易总览（默认）、六阶段监控、每日精选、股票详情、指定股票、风险与持仓。K线使用实际OHLC，红涨绿跌并辅以文字/图例；独立形态事件明确非顺序状态。新鲜度按观察日期如实显示，缺认证日历不推断休市/遗漏交易日。监控为信号研究，不是真实账户。后续依赖：M2审定状态机与执行/退出记录、M3正式准入输出、历史股票池/行业/基本面、M5回测/持仓服务；本任务不实现这些后端能力。

## 验收计划与交付

运行新增展示映射及多代码测试、现有离线完整套件、pip check、diff check；报告命令/数量/退出码/跳过原因。默认阻断网络、使用隔离临时库。实际本地浏览器对真实已有行情操作，桌面和390像素宽度检查，保存截图与预览；不新增行情网络请求、不做样本外回测或生产验证。报告、接口映射、功能说明、限制与结果集中在本记录，代码差异随PR提供。实际命令、日志、截图、提交及PR待验收后补齐。


## 2026-10-21 恢复与实际交付证据

恢复时仍为codex/m4-ui-002、HEAD 94cdd487bfd4633ecc2f002aad014f98dec961a5；GitHub API确认main相同。本任务尚无远端分支/PR，6个文件是未提交成果；两条既有stash、全部worktree和主目录M3任务保留。原git fetch失败不被当作成功；远端事实来自成功的认证API。模型仍为gpt-6.1-sol/high，未改变执行配置。

### 实际验证（不互相替代）

| 类型 | 实际结果、命令与退出码 | 证据 |
| --- | --- | --- |
| 定向离线 | `python -m pytest -q tests/unit/test_daily_candidates_view.py tests/manual/test_daily_candidates_offline.py`，5 passed / 0 failed / 0 skipped，exit0（7.50s） | 系统Temp/m4-ui-002-targeted.log |
| 完整离线 | `python -m pytest -q`，2838 passed / 0 failed / 1 skipped，exit0；跳过唯一真实AKShare用例，需显式网络开关。中断后从原exec会话86980读到完成与退出码0，未重复全量运行。记录耗时24456.71s，测量跨夜且会话经历中断，未分离等待/休眠与CPU时间，不作为计算性能指标。 | 系统Temp/m4-ui-002-full-offline.log |
| 最终布局回归 | 手机截图检查后仅将既有三张状态卡前移，原计算与映射未变；再次运行上述定向命令，5 passed / 0 failed / 0 skipped，exit0（7.04s）。完整套件对应此前功能树；最终提交完整回归交现有CI。 | 系统Temp/m4-ui-002-final-targeted.log |
| 空数据视图 | 隔离空SQLite、阻断外部Requests/socket，AppTest逐一打开6个视图：0异常、0候选、0网络请求，脚本exit0 | 系统Temp/m4-ui-002-empty-views.log |
| 环境/依赖 | Python F:/codex-agnes/AI-trade-main-demo/.venv/Scripts/python.exe；显式PYTHONPATH指本工作区src。Streamlit1.66.0、Pandas3.0.6、Altair6.3.0、pytest8.4.2；`python -m pip check` exit0 / No broken requirements found；`git diff --check` exit0 | 实际命令输出；未新增依赖 |
| 本地真实UI | 8524端口只读启动，实际多代码600000/600378查询：前者保留未达门槛分析，后者保留无行情原因；打开独立详情并核对真实K线/MA/量/独立形态。默认总览显示市场未完成计算、新增多头未获准、0候选和行情过期；390像素与1200像素真实iframe分别检查布局。 | 系统Temp/m4-ui-002/ 截图与本地预览 |
| 真实行情网络 | 未执行；复用已有腾讯候选源SQLite，不采集新行情。网络仅GitHub及本地预览。 | 已有批次demo-fab1a9b6062641248b5d97ce97a9723f |
| 样本外/生产 | 未执行，非本轮范围；未连接AWS、真实账户、生产数据库、线上Nginx/认证。 | 相关代码与配置未改，不能称线上端到端已验收 |

真实行情范围：600000.SH本地1217条（2021-10-08～2026-10-15），本次分析276条（2025-08-21～2026-10-15）。收盘9.64、M2评分40、结构止损8.95、ATR止损9.287120960685128。二者分开展示。未知名称/行业/阶段/交易单位不补造。600378.SH在本演示数据库无行情，指定输入仍显示其缺失结果。本地页面所用数据过期，未冒充当日实时行情。

### 文件清单、差异和预览

- daily_candidates_page.py：单页报表改为6个业务视图，默认交易总览、紧凑状态卡和可折叠设置；保留同一快照、两模式及空列表。
- daily_candidates_details.py：共享独立详情、真实OHLC K线/MA/成交量、M2独立条件事件、分开的止损与预算组件。
- daily_candidates_view.py：只读展示映射、多代码现有接口组合、数据状态、阶段能力表和风险距离；无状态机/交易信号计算。
- tests/manual/test_daily_candidates_offline.py：适配真实导航结构，保留评分/止损/预算/零网络断言，覆盖多代码与6视图。
- tests/unit/test_daily_candidates_view.py：阶段不推断、未知不填分、真实时间保留、独立事件不冒充首次/二次、输入批次上限。
- 本记录：编码前审计、实际接口映射、边界、恢复、验证及下一步依赖。

`demo_app.py?view=candidates`及Nginx/登录相关文件未改；M0/M2/M3/M5、交易定义、数据库契约未改。具体diff以本PR为准。预览：http://127.0.0.1:8524/?view=candidates；390/1200宽度检查为实际页面iframe，不是示例图。截图不含密钥，不提交SQLite/原始行情或截图到Git。

### 未实现能力与下一步建议

S0–S6的正式状态、B点、阶段日期/持续交易日、首次→缩量整理→二次放量、横盘区间、次日跳空阈值、MA5连续两日退出均依赖M2正式状态机；当前一律不推断。M3正式闸门、全A等权/广度/市场额需要已认证来源及准入输出；M4只展示当前未获准状态。基本面/行业分数、真实/模拟持仓与交易记录、M5回测尚未接入。真实手机触控与远程访问未测；线上认证/反代不在本地验证结论内。Streamlit仍提示既有use_container_width弃用，保持项目最低版本兼容，未扩大迁移。

建议下一阶段先审定M2状态机与退出记录契约，再接入获准M3结果及历史股票池，最后对接M5/持仓记录；仅建议，未另建任务或后台服务。UI完成不代表六阶段策略、来源准入、收益能力或实盘验收通过。最终提交、PR与CI以交付链接及GitHub记录绑定；不自动合并。

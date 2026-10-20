# TASK-M3-REMODEL-002：M3 数据质量诊断与准入页面

## 1. 身份、基线及执行配置

- 类型 implementation（包含UI验收）；H。只把现有正式诊断接入M3页面，不重新实现指标/准入、不认证真实来源、不修改核心契约或生产库。
- 唯一执行模型：OpenAI / Codex Desktop **gpt-6.1-sol / high**；当前 turn_context `2026-10-20T15:19:28.738Z` 实际核验。全局配置xhigh不是当前运行证据；此前已完成CORE-003-FIX的xhigh属于另一TASK，不混记。费用/额度未知，工具兼容已由实际文件/Git/API调用核验。
- 预算120分钟；同一验收项最多两次不同诊断性修复，非预期核心回归立即停止扩大修改。一个TASK固定本模型/档位，不委派、fallback或自称独立审查。
- 最新main/起点：`94cdd487bfd4633ecc2f002aad014f98dec961a5`，tree `2cbca81231bc2c1896f8a43b193a7a021030aa59`。API确认PR27/28/32/34/36均merged；Issue30/31/35/37均open。详细base/head/merge SHA保存在忽略目录 `artifacts/m3-remodel-002/baseline.json`。
- PR36 head `d60fa8809a248cb4b4a63ed4ee514296645bed2b`；已按用户决定合并为上述main。Issue37独立H复核PENDING_ASSIGNMENT，未执行，不能用合并/CI/UI代替。
- 起始分支codex/m3-core-003-fix，tracked干净，仅原有未跟踪.worktrees/。stash、其他15个worktree、历史报告/数据保留。API签名载荷重现精确main对象并核对SHA后建立 `codex/m3-remodel-002`；main与原HEAD文件树相同，不reset/clean/覆盖；不改变main ref。

## 2. 已读、规则与冲突

- 实际读取：AGENTS.md；MODEL_ROUTING_POLICY v1.0；TASK_TEMPLATE；OPEN_SOURCE_RESEARCH_POLICY v1.0；PROJECT_STATUS、DECISIONS、DATA_CONTRACT、INTERFACE_CONTRACT、M3_CORE_CONTRACT、M3_CORE_SOURCE_ACCEPTANCE及M3核心/修复任务记录；market_analysis_page/data/core/contract、旧计算器、demo_app/data和相关单元/UI测试。
- 版本基线为上述main（与当前树一致）；逐项核对正式Request/SourceEvidence/Diagnostic、Status/Admission/ReasonCode及to_dict，核心五个入口的真实签名；不按旧Issue中的枚举别名实现。
- 适用G01—G12：现场保护/路由核验、真实契约、UNKNOWN与时间不变量、默认禁网和临时数据库、测试与独立H分列、安全/PR人工处理及失败升级。全局AGENTS为空，无适用下级/override；不改治理文件或模型配置。
- 明确冲突及优先级：旧Issue31、M3/INTERFACE/PROJECT_STATUS文档在核心H复核前阻断页面改造；本轮用户明确授权继续TASK-M3-REMODEL-002，按当前用户指令执行**仅页面集成**例外。核心H未执行、真实来源/策略/生产门禁继续保留，不伪称所有旧门禁均满足，不在本任务关闭Issue37。
- 开源调研：不适用全面外部调研；复用现有诊断、Streamlit、SQLite只读端口和M3存档，不引入数据源/依赖/算法或改变时间契约。本次是既有契约的展示适配；已检查旧M3与Qlib/Pandera研究入口，仅保留现有设计，不新增外部采用。
- Computer Use技能/浏览器工具用于真实本地界面验证；离线AppTest、真实浏览器与真实数据来源认证分列。

## 3. 边界与接口映射计划

- 允许：market_analysis_page.py；M3局部的只读输入/展示适配模块；必要的M3 UI/适配器测试；任务/项目状态/页面说明与脱敏验收证据。不变更market_analysis_core/contract、共享validator、存储迁移、M4、指标/准入算法、依赖或治理规则。
- price_diagnostics→daily_trend/weekly_structure/wave/price_proxy；breadth_diagnostic→market_breadth；fear_greed_diagnostic→fear_greed；cffex_diagnostic→cffex_position；environment_diagnostic只组合上述正式结果。所有等级/数值/状态来自核心，不在UI用阈值重算方向或L1/L2/L3。
- 适配器只做本地读取、显式版本选择、元数据映射及读取/解析失败到正式INVALID_DATA/SOURCE_UNAVAILABLE/BLOCKED的结构化映射；永不升级许可。缺observed/event/available/quality/calendar等证据保持缺失，不用ingested时间冒充observed，不生成日历、完整股票池或CFFEX正式版本。
- 多版本必须显式选择，不默认取最新未知版本；宽度不按日期覆盖重观察记录，不回填历史。现有原始CFFEX CSV不等于CffexRankingsRecord；可以展示有依据的合约/会员/口径等元数据，正式版本不具备时由核心阻断数值/综合方向。
- 默认只读本地已保存数据；刷新/进入页面不采集。原主动采集按钮仅用户点击触发，read-only时禁用。本任务不点击真实采集、不发真实行情请求。接口失败明确保留，已有快照不能冒充失败请求结果。
- INVALID_DATA/BLOCKED隐藏数值/图表，UNKNOWN不显示0或猜测覆盖率。完整六因子与价格代理独立；live_trading始终false。输出仅白名单元数据/派生值，不展示密钥、原始CSV/响应或大段原始行情。

## 4. 验收计划

| AC | 验收 | 实际结果 |
| --- | --- | --- |
| 01—02 | 正式核心调用/八项独立总览/无UI准入算法 | PASS：核心调用映射及总览回归；核心文件无变更 |
| 03—04 | 真实日期/原因码/最小动作/缺失项；未知分母UNKNOWN、分子分母可溯源 | PASS：脱敏详情/下载与真实保存550行读回；分母未知不造百分比 |
| 05—07 | 六因子与代理、CFFEX口径/时点、INVALID/BLOCKED/UNKNOWN不升级 | PASS：原始CSV无正式记录时无净仓；严格模式八项BLOCKED、零图表 |
| 08 | 来源失败/空/部分因子/过期/日期错配/非法数值/冲突离线适配器与UI矩阵 | PASS：16项针对性测试（含8场景UI矩阵）；无真实来源认证含义 |
| 09 | 真实启动本地服务，桌面及窄屏、展开详情/刷新；本地保存数据读回/来源类型明确 | PASS：内置浏览器1280×720/390×844；观察仍1个、摘要未变、零非回环尝试 |
| 10 | 完整离线pytest、pip check、diff check | PASS：2848 passed/1 skipped，exit0；依赖和diff检查exit0 |
| 11 | 新PR/最终SHA交付及H未执行边界 | 报告完成；最终SHA/PR及独立H登记见交付PR与delivery-final.json；核心Issue37不关闭 |

解释器复用 `F:/codex-agnes/AI-trade-main-demo/.venv/Scripts/python.exe`；显式当前src的PYTHONPATH、PYTHONUTF8=1、PYTHONIOENCODING=utf-8、PYTHONDONTWRITEBYTECODE=1。pytest默认socket阻网，独立新basetemp及临时数据库，不开启实网选项。

| 证据类型 | 状态 |
| --- | --- |
| 离线单元/UI/完整套件 | PASS；本轮实际2848 passed/1 skipped，非继承旧结果 |
| 真实本地浏览器E2E/窄屏 | PASS；专用临时根与8769端口，只读真实保存观察；合成反例仅为离线回归；验收后关闭本任务服务/标签页 |
| 真实行情网络/来源认证 | 未执行；本任务不需要 |
| 样本外回测 | 未执行；不在范围 |
| 独立核心H/页面H复核 | 未执行；核心Issue37保持open；页面新SHA安排独立H计划 |

## 5. 交付与审查

- 日志/JUnit/截图/脱敏基线/本地临时数据放 `artifacts/m3-remodel-002/` 并检查Git忽略；不提交SQLite、原始行情或未经审查响应。页面截图须检查无敏感内容再决定是否提交，默认本机证据。
- 目标PR base=main，独立分支codex/m3-remodel-002，不直接提交main、不自动合并/部署。最终SHA/PR在交付及独立review Issue绑定，避免在提交内递归记录自身SHA。
- H实现不等待L批次；计划独立 `TASK-M3-REMODEL-003-REVIEW` 绑定最终SHA，只审查不改实现，自己的模型/档位实际确认前不执行。与核心Issue37分别保持，当前会话不自审、不宣布核心/来源/生产准入通过。
- 核心测试失败、契约或范围冲突立即保存现场及最小复现；同一验收问题两次不同诊断修复失败则升级，不以换编号/改弱断言清零。阻断/恢复记录保存在本任务及忽略证据目录。

## 6. 实际变更与验证输出

- `market_analysis_page.py`：去除旧页面直接调用指标/准入组合、推造股票observed_at和原始CSV净仓；独立总览、显式本地版本、核心派生值、脱敏详情与错误反馈。
- `market_analysis_view.py`：纯本地字段/证据映射与正式核心入口；不创建认证收据、不按日期覆盖快照、不写库、不联网。读取错误只能阻断。
- `tests/unit/test_market_analysis_view.py`：13项，覆盖接口映射、UNKNOWN/零、空/部分/过期/错配/非法/时间缺失/解析错误/冲突、旧数据保护及脱敏。
- `tests/manual/test_m3_page_offline.py`：保留2项导航、只读、显式失败/重试约束；将旧“原始CSV直接净仓”断言改为正式核心阻断，合成价格与真实来源验收分开。
- `tests/manual/test_m3_diagnostic_states.py`：1项子进程测试实际Streamlit渲染的8场景；夹具收据仅测试声明。无错误图表或999999阻断载荷泄漏。
- 页面说明/场景矩阵/复现：[M3_PAGE_DIAGNOSTICS](../M3_PAGE_DIAGNOSTICS.md)；项目状态只更新事实和本次用户授权的页面例外，不改治理、核心/数据契约、正式进度或依赖。
- 绑定基线、接口文件摘要、实际测试数量和本机截图摘要的脱敏机器记录：[M3_REMODEL_002_20261020.json](../evidence/M3_REMODEL_002_20261020.json)。截图/原始数据/数据库留本机，不上传原始响应。

| 实际命令（现有Python环境） | 退出码 / 实际输出 | 日志 |
| --- | --- | --- |
| `python -m pytest tests/unit/test_market_analysis_view.py tests/manual/test_m3_page_offline.py tests/manual/test_m3_diagnostic_states.py -q --junitxml=artifacts/m3-remodel-002/targeted-3.xml` | 0；16 passed in 20.04s | targeted-3.log/xml |
| `python -m pytest -q --basetemp=artifacts/m3-remodel-002/pytest-temp-final --junitxml=artifacts/m3-remodel-002/offline-full.xml` | 0；2848 passed, 1 skipped in 447.12s；真实AKShare测试未授权跳过 | offline-full.log/xml/exit |
| `python -m pip check` | 0；No broken requirements found. | pip-check.log/exit |
| `git diff --check` / staged diff检查 | 0；无差异格式错误；本机LF/CRLF提示非失败 | diff-check.log |
| 真实本地浏览器 | PASS；research保存数据、strict全部阻断、无数据标的、详情、刷新及窄屏无溢出 | browser-evidence.json、e2e-readback.json、PNG及server日志 |

早期针对性运行：targeted-1为14 passed/1 failed，旧UI测试在多版本不再自动选最新后找不到合约控件；按新行为显式选择版本后通过。targeted-2为15 passed/1 failed，新UI矩阵的禁网夹具阻断Windows asyncio自管道；允许127.0.0.1/::1内部管道并继续拒绝外部TCP后通过。每个问题一次诊断性修复；无核心回归失败、未降低核心校验或修改期望以接受错误数值。保留全部早期输出。

浏览器使用的原始保存观察摘要与时间详见页面说明；非回环拦截日志0条、刷新后仍1个观察且SHA256未变。清理时曾因服务的conhost子进程不匹配Python身份保护而停止清理；随后仅核对并停止本任务Python父子进程，不停止其他服务、不删除临时证据。

剩余风险：核心独立H未执行；真实源授权/时间/日历/全A分母未认证，现有数据只能L1或BLOCKED；CFFEX无正式本地版本接线所以不显示净仓；旧股票端口缺observed_at时被核心阻断。手机HTTPS/物理机、实网采集、样本外、生产与页面独立H未执行。页面H必须绑定交付SHA另行指派，不用本轮自检冒充独立审查。

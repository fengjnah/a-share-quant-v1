# TASK-M4 每日候选股票与交易计划

- 类型：implementation；目标：真实本地行情选股、同一结果详情、0–5候选和风险参考；不做交易、迁移或大规模回补。
- 基线：fengjnah/a-share-quant-v1 main `ba8588a87a9d55c95f20fbac46dca4ea0e74f57e`（Git fetch 与 GitHub PR26 合并 SHA 一致）。M2 PR25：base `fa2ac20152170719d35bb42b5dc694398a59ce15`、head `c76c09ee1fbef2f170456f13e7d6af767fe5c8c2`、合并 `5adfacdace69396d88b57b9a7a88b36aa7175c4a`。M3 尚未合并，不作为依赖。
- 工作区：复用已有干净 `.worktrees/local-demo-verify`，分支 `codex/m4-daily-candidates`；主目录 M3 的未提交文件不动。不新建 worktree。
- 唯一执行：OpenAI / Codex Desktop，`gpt-6.1-sol`，固定 `xhigh`；2026-10-19 当前 session rollout 的 turn_context 实测。H：候选门禁涉及历史可见性、未知状态与仓位安全。实际费用/额度未知；不调用其他模型或子代理；同项最多两次不同诊断修复。
- 已读：AGENTS、MODEL_ROUTING_POLICY v1.0、OPEN_SOURCE_RESEARCH_POLICY v1.0、TASK_TEMPLATE、DATA_CONTRACT、INTERFACE_CONTRACT、M2 trading_analysis / analysis_page / demo_data / SQLite 及相关测试（上述基线）。无下级规则。适用 G01–G12，保留时间、未知和数据真实性约束。
- 明确冲突：本次用户要求覆盖 G09 自动合并禁令、G11 全量本地离线回归、G05/G12 独立审查任务要求；仅做针对性/必要回归，完整套件由已有 CI 执行，门禁通过后正常合并，不增加审查 TASK，不绕过保护。
- 调研：复用基线 M2 已有指标、评分、risk_reference、严格 SQLite 可见版本读取及测试；用户限定只读现有相关模块，不引入外部源码/依赖/数据源，不开展外部调研。沿用腾讯候选源的已有许可/真实性限制，不宣称生产准入。
- 修改范围：新增 daily_candidates*、market_state 研究接口和必要测试；demo_app 仅增加入口。不得修改 trading_analysis、M3、数据库契约或其他任务成果。
- 不变量：分析日仅取本地可见行情日期；as_of 为当前读取时点，历史结果是现在回看；computed_at 不回填。缺失 ST/交易状态/周线认证/市场验证阻断准入和仓位。市值、行业、成长性未接入明确展示未执行。
- 市场约定：偏强/震荡/偏弱/证据冲突/数据不足，附 analysis_date、available_at、validated、source、reasons。未验证 M3 的 CFFEX/波浪/恐贪只作为辅助，M4 默认复用 M2 数据不足结果。
- 验收：排序/模式/空列表/市场过滤/止损1%预算/缺失状态/未来数据/同一表格详情结果；pytest unit + Streamlit 离线回归、pip check、diff check、真实本地浏览器与移动布局。离线网络阻断，临时数据库；本轮优先复用已存真实行情，不主动下载。
- 交付：本地页面、PR及正常合并 SHA。样本外回测不在本任务，未执行。实际结果补在同一记录和 PR，不创建重复报告。

集成更新：M3 PR27 已合并至 `59ce53999477ad898a2428679f19694b48f03005`，本分支已 fast-forward 对齐该最新 main 后才修改公共入口。M4 通过 `?view=candidates` 及工作区 radio 进入，复用同一数据库根目录。M3 未提供已验证正式市场过滤结果，依据其页面“指数/宽度无正式 available_at，不进入策略或回测”的限制，继续使用 M2 的数据不足门禁；共同状态枚举与带日期/可用时间/认证标志的包络定义于 market_state.py，不依赖 M3 运行成功。


验收记录（2026-10-19）：

- 离线：`python -m pytest -q tests/unit/test_daily_candidates.py tests/unit/test_trading_analysis.py tests/unit/test_demo_data.py tests/unit/test_market_analysis.py tests/manual/test_daily_candidates_offline.py tests/manual/test_trading_analysis_offline.py tests/manual/test_streamlit_demo_offline.py tests/manual/test_m3_page_offline.py`，退出0，97 passed / 37.23s。合成夹具只用于离线边界测试，不作为真实来源验收。
- 最后展示文字与上海日界调整后，`python -m pytest -q tests/manual/test_daily_candidates_offline.py`，退出0，1 passed / 4.21s。`python -m pip check`：退出0，No broken requirements found。`git diff --check`：退出0。
- 实际 Python：`F:/codex-agnes/AI-trade-main-demo/.venv/Scripts/python.exe`，通过显式 PYTHONPATH 指向本工作区 src，防止 editable 包串库。测试日志：系统 Temp/m4-targeted-tests.log、m4-final-page-test.log。
- 真实已有数据：腾讯候选源 600000.SH，本地2021-10-08～2026-10-15，1217条；既有真实采集批次 demo-fab1a9b6062641248b5d97ce97a9723f。本次分析420个日历日内276条（2025-08-21～2026-10-15）。未下载新行情。来源保持候选研究准入等级，未宣称生产认证。真实读回日志：系统 Temp/m4-real-data-check.log。
- 2026-10-15：收盘9.64，MA趋势满足，研究评分40；结构止损8.95，ATR14=0.1764395196574366，ATR/最终研究止损9.287120960685128。严格组合不满足，趋势确认条件满足，但两者均因市场、历史状态与周线/公司行为门禁输出0只。测试配置权益100000时风险金额1000，不输出交易股数；空权益仍为空。
- 本地浏览器：8524端口实际选择模式、生成结果、查看真实股票详情、核对公式/评分/止损和风险金额；统一入口保留M1/M2/M3。另用390×844真实页面iframe检查控件、纵向排版和表格水平滚动区域；移动设备触摸/远程手机访问未测试。截图保留在系统 Temp/m4-mobile-check/，不提交行情截图或SQLite。
- 真实网络行情测试：未执行，使用已存真实数据，本次无行情HTTP请求。GitHub网络仅用于fetch、PR、CI与合并。样本外回测：未执行，不在本任务范围。完整离线套件：本地不重复运行，按用户要求交给现有GitHub CI。
- 限制：真实历史证券名称/ST/市值/行业/成长性/停牌涨跌停/交易单位尚未接入或未认证；二次突破与突破后回调关联未实现；M3研究指标无正式过滤准入。缺口明确显示，不放宽条件。每日在页面加载时自动分析最新本地日期，或按用户日期生成；不包含后台定时下载/回补/无人值守报告调度。

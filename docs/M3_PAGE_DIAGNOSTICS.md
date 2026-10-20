# M3 页面诊断与验收

TASK-M3-REMODEL-002，基线 main `94cdd487bfd4633ecc2f002aad014f98dec961a5`。页面改造的最终提交在交付 PR、独立审查任务和本地 `artifacts/m3-remodel-002/delivery-final.json` 中绑定；不在提交内容中递归填写自身 SHA。核心独立 H [Issue #37](https://github.com/fengjnah/a-share-quant-v1/issues/37) 尚未执行。本页面不能认证真实来源、预测能力或生产策略准入。

## 使用与接口

本地入口 `/?view=market`，选择分析日期、可见性模式和本地版本。一个已保存版本可直接读取；多个指数/CFFEX版本不自动取最新，宽度由用户逐日选择，重复日期由核心拒绝。刷新只读，采集按钮仅显式点击触发；`AI_TRADE_READ_ONLY=1` 禁用采集。不会因失败生成模拟数据或自动换源。

| 页面模块 | 正式入口 / 输出键 | 数值与展示边界 |
| --- | --- | --- |
| 日线趋势 | price_diagnostics / daily_trend | 直接呈现核心 close/MA20/MA60/direction |
| 周线结构 | price_diagnostics / weekly_structure | 仅核心已结束周结构，不在页面重新聚合 |
| 波浪/确认转折 | price_diagnostics / wave | 核心多情景/确认日期；最近30个转折不等于唯一浪型 |
| 市场宽度 | breadth_diagnostic / market_breadth | 来源家数与全A分母分开；不以报价家数猜全A覆盖 |
| 完整六因子恐贪 | fear_greed_diagnostic / fear_greed | 任一缺失则完整分数 UNKNOWN；不补零/重分权重 |
| 独立价格代理 | price_diagnostics / price_proxy | 独立分数及此前历史分位，不代替全市场恐贪 |
| CFFEX会员持仓 | cffex_diagnostic / cffex_position | 原始CSV只读元数据，不构造缺日历/版本的正式记录或净仓方向 |
| 综合市场环境 | environment_diagnostic / environment | 仅组合核心 wave/fear_greed/cffex_position，不在UI投票 |

适配模块 `market_analysis_view.py` 不计算指标或准入等级。它只映射既有观察字段、保留行身份/时点、接入核心并格式化诊断；读取/解析失败只会追加正式 INVALID_DATA 并阻断，不能升级许可。股票旧端口缺 observed_at 时保留 UNKNOWN，不能用 ingested_at/available_at 推造。来源/授权/时间收据不会从本地文件标签升级为 VERIFIED。

状态枚举使用正式 `m3-core-diagnostic-v1`；UNKNOWN 是字段缺失的展示，并非新增准入状态。每个模块保留当前状态、Admission、分析日期和核心可见数据截止日期。INVALID_DATA/BLOCKED 或 calculated=false 时不展示分析数值/图表。研究观察的L1派生值始终伴随诊断，L2/L3仍不代表实盘许可，`live_trading=false`。

详情区给出来源及选定源版本、输入日期范围、真实观察/采集/可用时点与认证状态、样本覆盖分子/分母/定义/引用、缺失字段/日期/因子、原因码和核心最小补救动作。未知分母及其百分比显示 UNKNOWN；确知的0保留0。大量逐行原因按码分组展示首末示例，脱敏诊断下载保留全部原因。下载只含白名单元数据，不含原始CSV/响应、密钥或大段行情。

## 离线场景矩阵

| 场景 | 核心事实及UI断言 | 回归位置 |
| --- | --- | --- |
| 空数据/没有来源 | SOURCE_UNAVAILABLE/BLOCKED，截止及分母UNKNOWN，零图表 | view单测 / 页面AppTest / 真实浏览器无保存标的 |
| 部分因子 | 完整分数为空；代理独立，可观察但不升级综合方向 | view单测 / AppTest / 真实保存指数 |
| 过期 | STALE及真实截止日保留，L1不冒充研究通过 | view单测 / AppTest |
| 日期/标的错配 | INVALID_DATA/BLOCKED；不覆盖矛盾身份/日期 | view单测 / AppTest |
| 非法数值 | 核心INVALID_DATA；无数值、无图表 | view单测 / AppTest |
| 摘要/解析失败 | 明确读取失败、正式阻断；不显示旧值作为本次响应 | view单测 / AppTest |
| 时间未认证 | UNKNOWN收据不升级；strict_backtest阻断且零图表 | view单测 / 真实浏览器 |
| 合格证据冲突 | EVIDENCE_CONFLICT保留，无确定预测或实盘许可 | view单测 / AppTest（合成测试声明） |
| 多版本/重复日期 | 必须选择；保留重复交核心拒绝，不按日期覆盖 | view单测 / AppTest |
| 原始CFFEX榜单 | 合约/会员/scope/统计日可追溯，正式记录缺失时无净仓/方向 | AppTest（明确合成CSV） |
| 主动采集失败 | 一次点击一次调用，重绘不重试，显示错误；只读按钮禁用 | AppTest（模拟失败，无实网请求） |

合成收据仅用于门禁/UI回归，不是实际来源验收。旧UI的“原始CSV净仓1000”断言改为不得绕过核心；未降低核心测试或契约。

## 本地浏览器复现与证据

本轮使用Codex内置浏览器真实访问 `http://127.0.0.1:8769/?view=market`，不是静态HTML或AppTest截图；服务只绑定127.0.0.1，临时验收包装器阻断非回环TCP，采集按钮禁用。独立系统临时根 `a-share-quant-demo-m3-remodel-002-*` 中初始化空test数据库，复制先前已保存的指数观察，不触及生产库、旧服务或原始存档。

选用内容摘要 `c7b5534441830c8d8a6e7e0b8ef0e1722b93e2b38a51f20ee0bf7c072170a849` 的本地历史观察：550行，来源声明AKShare1.19.1/新浪财经，数据截止2026-10-16，保存观察时间2026-10-19T15:54:06.478989+00:00。该记录仅支持L1观察，源授权/时间/日历认证未知；本轮不重新请求来源，不能把旧文档的其他观察时间替换本文件时间。

1. 在新的系统临时 `a-share-quant-demo-*` 目录初始化 `Database(DatabaseConfig(root/'demo.sqlite3', environment='test', journal_mode='DELETE'))`；只把上述已保存观察复制到该根的 `m3-observations/` 并校验文件SHA256。无历史文件时可复现空态或用明确标注的合成夹具，不能声称真实来源复现。
2. 设置当前仓库src为PYTHONPATH、AI_TRADE_DEMO_ROOT为该已有临时根、AI_TRADE_READ_ONLY=1；清除该进程的AI_TRADE_WORKBENCH_ROOT。使用现有Python环境运行 `python -m streamlit run src/ai_trade/demo_app.py --server.address 127.0.0.1 --server.port 8769 --browser.gatherUsageStats false`。本轮实际使用额外socket阻网包装器 `artifacts/m3-remodel-002/serve_local.py`。
3. 打开market入口，research/沪深300/2026-10-16，检查八卡片、实际截止550条、UNKNOWN分母、完整分数UNKNOWN与代理分开；展开日线证据核对时点/源版本/最小动作。
4. 以1280×720桌面、390×844窄屏检查总览、详情、图表与状态。窄屏每卡宽348px，左16/右364，document宽390，main滚动宽与可见宽均380，无横向溢出。
5. 窄屏切换strict_backtest：八模块BLOCKED且零图表。选择没有保存版本的上证指数：来源不可用、数值UNKNOWN且零图表；返回research沪深300，刷新确认保存观察不增加、无自动采集。

本机证据目录 `artifacts/m3-remodel-002/`：e2e-setup.json、browser-evidence.json、desktop-overview.png、desktop-cards.png、desktop-evidence.png、mobile-top.png、mobile-strict-evidence.png、mobile-empty.png及server日志。原始行情、SQLite和截图默认留本机，不提交未经审查的原始响应；审查以任务测试及脱敏记录复现。

真实行情网络、真实来源认证、手机HTTPS/物理设备、样本外回测、生产准入、核心H与页面独立H均未执行。窄屏浏览器验收不等于手机部署成功。不自动合并或部署。

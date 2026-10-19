# TASK-M3-CORE-001：M3 核心诊断与准入契约

## 身份、基线与执行配置

- 类型：implementation + data acceptance；Issue [#30](https://github.com/fengjnah/a-share-quant-v1/issues/30)。只建立核心数据、计算、诊断和准入接口，不改造页面、不部署、不接交易账户、不操作生产数据库。
- 2026-10-19 实际核验 main：`f46347bb492fd8474e38f5fa786a8c81a47c8a6d`。PR #27 已合并为 `59ce53999477ad898a2428679f19694b48f03005`；PR #28 已合并为该最新 main。Issue #30 开放。AWS PR #29 不作为依赖，不混入本任务。
- Git HTTPS 传输失败后，由 GitHub API 重新解析 main；API 签名验证有效。本地已有完全相同的 tree `cb55ec7b5c2b45a088af27ad914980afcf1121ac`，按 API 原始签名载荷重建提交对象，Git SHA 逐字节核验一致后才建立 `codex/m3-core-001`。不是复制旧分支冒充最新 main。
- 开始时位于 `codex/aws-001-deploy-safety`，tracked 干净；已有未跟踪 `.worktrees/` 与 TASK-004 stash 保持原样。不 reset/clean，不创建 worktree。
- 唯一执行模型：OpenAI `gpt-6.1-sol`，固定推理 `high`。依据：用户在本任务明确回复“gtp-6.1 sol high 额度70%”，按明显拼写规范化记录；无独立服务端型号证明，不把全局配置或旧任务记录当本轮证据。不切换模型/档位，不调用子代理或外部模型。
- H：涉及可得时点、历史覆盖、来源认证和策略准入。用户额度预算上限 70%；账户初始共享 5 小时窗口已用 28%、周窗口已用 60%，较小剩余额度同样约束执行，不能折算确定 token/美元或归因本任务。实际费用未知，不自动购买/重置额度。按阶段核验，预算不足保留现场，不降低门槛。
- 同一验收项最多两次不同诊断修复；契约冲突、未来函数风险或核心测试失败先停止扩大修改、记录证据及影响，不悄悄迁就测试或改变基线。

## 已读、复用与范围

- 本基线实际读取：根 AGENTS.md、MODEL_ROUTING_POLICY v1.0、TASK_TEMPLATE、DECISIONS、DATA_CONTRACT、INTERFACE_CONTRACT、OPEN_SOURCE_RESEARCH_POLICY v1.0、PROJECT_STATUS。
- 实际读取 M3 三个模块与 test_market_analysis；补读 CFFEX 模型、日历/可见版本端口及 high_assurance 测试、TASK_022A_REPORT、reviews/TASK_022A_CFFEX_CONTRACT；M2 可见性验证、ReferenceResult、M4 market_state 仅核验消费边界。
- 适用 G01–G12：保护基线、固定执行配置、保持 UNKNOWN/时间语义、默认离线、生产边界、有限修复、真实证据分列、独立 H 审查后才可解除合并/阶段门禁。无本任务规则 override；旧任务例外不继承。
- 调研适用：统一接口和时点门禁属于 R01。优先复用仓库的 ReferenceResult/可得时间校验、CFFEX 已审纯端口及 M3 百分位/均线/转折规则；不重建适配器、日历、SQLite 或大型仓储，不引入第三方算法依赖。既有 CFFEX 审查仅覆盖其冻结范围，不扩大为本任务审查。
- 在数据验收前只读固定 AKShare 1.19.1 的相关指数/宽度函数与许可证，记录文件摘要；软件许可与数据授权分开，未知授权不得写成获准。未发现 docs/research 下已审研究产物，不读取全部历史报告或改动其他工作树。
- 允许：新增 market_analysis_contract.py / market_analysis_core.py 及必要测试；market_analysis_data.py 仅在已核实来源边界补采集证据；docs/M3_CORE_CONTRACT.md、同一任务记录及一份脱敏来源证据。必要时最小修复现有纯计算边界，不改变旧字段含义或策略行为。
- 禁止：数据库 Schema/迁移、available_at/ingested_at/as_of 语义重写、M1/M2/M4 策略、生产数据/部署/凭据、页面布局重做、自动合并。旧观察缺字段保持 UNKNOWN，不倒填采集/发布时刻。

## 验收与网络预算

- 基线相关离线测试：M3、CFFEX 两组与 M4 单测；实现后新增定向测试、必要回归、一次完整离线套件、pip check、git diff --check。结果在本记录补充，不用旧 CI 代替本轮执行。
- 新诊断必须公开计算版本、真实日期、时点认证、样本及覆盖分母、原因码、血缘和 L1/L2/L3；未认证或缺失不补零，不把调用方声明自动升级为来源认证。
- 真实网络只在显式验收开关下使用已存在的端点：Sina 沪深300（单标的，最多保存最近550条）、乐咕当前市场宽度（1快照）、CFFEX IF 指定日（1 CSV）。先读固定 SDK 源码列明精确端点；每类最多一次数据请求，无自动重试/换源；单 HTTP 连接/读取不超过5/8秒，worker总计不超过30秒，响应上限沿用指数8MB/CFFEX2MB。保持正常代理解析和 TLS 验证，不写系统代理。
- 所有原始响应与行情只在本机忽略目录，Git 只保留日期、行数、字段、状态、摘要和限制。任何未执行/受限/无日历或授权项单列 NOT RUN / ENV BLOCKED / UNKNOWN，不用 synthetic 验收源。
- 本地 UI 仅接口最小集成，不宣称页面改造完成；样本外回测不在本任务，NOT RUN。L3 不等于实盘许可。

## 审查与下游

- 独立 H 审查计划编号：`TASK-M3-CORE-001-REVIEW`，当前为计划、未创建/未指派；最终实现冻结后绑定精确 SHA，独立上下文只读审查，不由本实现会话换角色自审。
- AC-10 通过前，PR 保持待审、不合并、不宣布核心阶段验收通过。TASK-M3-REMODEL-001 在共享契约冻结和独立审查完成前保持阻断；交付时提供候选契约版本与确切 SHA，不能冒充稳定准入。
- 本记录尚为实施前登记，后文只补实际结果。

## 实施中的定向失败与有限修复

- 基线相关离线套件：163 passed，退出0，14.50s。新增核心初测36 passed，退出0，5.35s。
- 加入JSON Schema/采集边界测试后，定向回归 `pytest -q tests/unit/test_market_analysis_core.py tests/unit/test_market_analysis.py tests/unit/test_cffex_rankings.py tests/unit/test_cffex_high_assurance.py tests/unit/test_daily_candidates.py --junitxml=artifacts/m3-core-001/targeted.xml`：**1 failed, 204 passed，退出1，10.64s**。
- 失败为 `test_contract_unknown_zero_json_and_snapshot_identity`：顶层 time_verification 使用未经 clean 的 asdict，refs 仍为 tuple，JSON Schema 要求 array。不是调低Schema或修改期望。证据：上述JUnit和本地执行输出。影响是诊断直接交给Schema校验失败；尚未提交/供下游使用。
- 按G10暂停扩大范围，第一次定向修复仅统一序列化的Receipt/Enum清洗，然后先重跑该断言；失败次数不重置。其他行为不依赖失败结果继续推进。

## 实际交付与验证

- 新增 `market_analysis_contract.py`、`market_analysis_core.py`：统一诊断/JSON序列化、日线/完整周OHLC/因果转折/价格代理、六因子完整分数、全A分区分母、CFFEX已审端口封装、综合冲突与L1/L2/L3门禁。`market_analysis_data.py`仅增加一次allowlist请求/限流式大小检查、脱敏HTTP证据、实际新观察入库时间；旧快照不补时点。没有部署、交易、DB或旧策略变更。
- 契约 `m3-core-diagnostic-v1` / `m3-core-rules-v1`，文档 [M3_CORE_CONTRACT](../M3_CORE_CONTRACT.md)、JSON Schema；DATA_CONTRACT/INTERFACE_CONTRACT只增加候选扩展入口。新脚本 `scripts/verify_m3_sources.py`必须显式启用、只向忽略artifacts目录写私有观察。来源验收见 [M3_CORE_SOURCE_ACCEPTANCE](../M3_CORE_SOURCE_ACCEPTANCE.md) 和脱敏JSON。
- GitHub研究只读2个项目，固定SHA/源码/测试/许可及采用/拒绝理由在来源验收；不添加依赖、不复制代码。不把开源许可当数据授权。原有M3计算/CFFEX版本链/日历端口继续复用。
- 序列化第一次修复后的单项重验：`python -m pytest -q tests/unit/test_market_analysis_core.py::test_contract_unknown_zero_json_and_snapshot_identity --junitxml=artifacts/m3-core-001/serialization-recheck.xml`，**1 passed，退出0，1.04s**，恢复限定范围。随后又明确排除“日历范围完整但价格首周不完整”的首周，增加同一边界断言，未降低周线20完整周要求。
- 最终完整离线：`python -m pytest -q --junitxml=artifacts/m3-core-001/full-offline.xml`，**707 passed, 1 skipped，退出0，87.19s**。包含42项新增核心/采集边界测试，M1/M2/M3/M4既有离线回归。默认socket阻断、隔离临时文件/数据库；跳过 `tests/manual/test_akshare_daily_live.py:81`（未传 `--run-akshare-integration`）。旧Streamlit AppTest只是离线测试，不替代真实浏览器UI验收。
- 依赖：`python -m pip check` → `No broken requirements found.`，退出0。Python3.12.14，现有demo venv，AKShare1.19.1；未安装/升级依赖。CI使用已有Python3.11工作流，结果另以PR检查为准。
- 工作区 `git diff --check`退出0；暂存全部本任务文件后再检查新增文件。artifacts路径已用 `git check-ignore`确认忽略；没有原始行情/响应、SQLite、凭据进入差异。
- 真实源执行脚本退出0只代表生成报告：新浪HTTP200保留550行（2024-07-09～2026-10-16），趋势/周线/波浪/价格代理可计算但仅L1；乐咕ReadTimeout；CFFEX IF/10-16 SSLError，均一次无重试。完整恐贪为空，无真实L2/L3。未绕过TLS/授权/日历门槛。真实源失败独立保留，不用离线PASS覆盖。
- 本地浏览器UI端到端 NOT_RUN（本任务不改页面）；样本外回测 NOT_RUN；生产数据库/EC2/真实账户 NOT_RUN。旧AWS手机验收不继承到本任务。
- 收尾main再次经API核验仍为 `f46347bb492fd8474e38f5fa786a8c81a47c8a6d`。本任务唯一模型/档位不变；收尾共享5小时已用51%、周已用63%（均非本任务独占用量），未购买或重置额度。最终实现SHA和PR在交付及PRhead记录，避免文档内自指提交哈希。

| AC | 实际状态 | 证据/限制 |
| --- | --- | --- |
| 01/02/03/04 | 离线PASS | 稳定枚举/Schema、60日/20完整周边界、六因子缺失null、股票池日期/快照引用/分区分母 |
| 05/06/07 | 离线PASS | CFFEX未认证方向null、as_of/右3条/错误日期回放、分级/升级凭据一致性；不等于真实认证 |
| 08 | 本地PASS | 完整707/1skip、依赖检查、diff；CI另核验 |
| 09 | PARTIAL/ENV_BLOCKED | 新浪真实有限范围可算L1；宽度/CFFEX失败，所有源授权/权威日历/历史首次可得未认证 |
| 10 | PENDING | TASK-M3-CORE-001-REVIEW计划待独立指派，绑定最终PRhead；不能用本会话自检代替 |

## 结构化待审反馈与剩余门禁

```json
{"task":"TASK-M3-CORE-001","state":"PARTIAL","contract":"m3-core-diagnostic-v1","offline":"PASS","live":"PARTIAL_ENV_BLOCKED","ui":"NOT_RUN","out_of_sample":"NOT_RUN","independent_h_review":"PENDING","review_task":"TASK-M3-CORE-001-REVIEW","merge_allowed":false,"downstream":"TASK-M3-REMODEL-001","downstream_admission":"BLOCKED"}
```

R07要求反馈到看板，但本任务不在原TASK_METRICS计划定义内；TASK_BOARD是生成文件，其规则禁止手写/以普通反馈新增任务或权重。为避免越权计划修订，本轮只在本任务单保留上述结构化反馈，不改正式JSON/生成看板和完成率；正式纳入需独立计划审查，非本任务已完成项。

独立H计划：冻结最终PRhead，只读核验本任务新增契约、全A池认证/分母、6因子/as_of、周线/右侧确认、CFFEX发布/口径/版本链、L3审批边界和真实来源声明；不暗中改实现。未指定独立审查者及其实际模型/档位前不启动审查。不自动合并，不宣布阶段通过，不解除REMODEL阻断。下一步还需源授权、历史实体股票池/日历、真实可得时点和全A成交额证据；不能用调小阈值解决。

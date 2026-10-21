# TASK-M0-M3-DATA-001：Windows 本地 M3 数据库存盘点

## 任务与执行配置

- 类型：acceptance；H（真实来源、数据库归属、历史时间及研究准入边界）。先只读盘点，再按已确认前置条件推进；不以缺库为由另建平行数据库。
- 提供方/宿主：OpenAI / Codex Desktop；唯一执行模型 `gpt-6.1-sol`，固定 `high`。2026-10-21 实际 rollout `turn_context` `01a15ba8-8d07-7282-bc61-2e8c21132747` 核验，非全局配置推断。费用及剩余额度未知；不调用子代理或其他模型。
- 预算：120 分钟；阶段一行情请求 0、数据库写入 0、重试 0。后续实网仅在正式本地库、来源许可和明确范围/预算全部确认后开启；未知不视为授权。两次不同诊断性修复仍失败或核心失败依 G10 停止。
- GitHub main/任务基线 `c4b682d12c7c8dc42f75e717b855238f635ce05b`；独立分支 `codex/m0-m3-data-001`，工作区 `F:/codex-agnes/AI-trade-m0-m3-data-001`。原工作区 `codex/m3-remodel-002@964a24007ab208d7b10e254a4e86548007c69c4f`、未跟踪 `.worktrees/`、两条 stash 和其他 worktree 全部保留。fetch 更新 tracking ref，不切换原分支、不 reset/clean。
- PR #39 已合并，head `964a24007ab208d7b10e254a4e86548007c69c4f`、merge `90dfec6442c188d9e6263be12d90aea58a6dff91`；PR #40 已合并，head `88088b0ccda6a5752f7e14c383307d1041006c62`、merge `26554612e03900749e637e8696e59c56bf7baaa6`，二者 base 均 `94cdd487bfd4633ecc2f002aad014f98dec961a5`。Issue #37 仍 open/PENDING，既成合并不是独立 H 通过。

## 实际阅读、规则与边界

已读根 AGENTS、MODEL_ROUTING_POLICY v1.0、TASK_TEMPLATE、OPEN_SOURCE_RESEARCH_POLICY v1.0、PROJECT_STATUS、DECISIONS、DATA_CONTRACT、INTERFACE_CONTRACT、M3_CORE_CONTRACT、M3_CORE_SOURCE_ACCEPTANCE、M3_DATA_CERTIFICATION_MATRIX、LOCAL_MARKET_DEMO、AWS_RESOURCE_INVENTORY，以及本轮相关存储/页面/采集源码。最新 main 无下级 AGENTS/override。适用 G01–G12：保护现场、唯一模型、H 待审、未知/历史时间不变量、只读数据盘点、证据分列、PR 人工决定。

调研：阶段一只读现场和既有契约，无新模块/来源/依赖/迁移，不启动新的外部框架调研。后续来源计划复用 #40 已有固定 SDK/接口研究，实际检查当前代码差异；供应商授权未知保持 BLOCKED，SDK MIT 不替代数据授权。若要新增持久化数据集或历史语义，按 R01/G05 独立 H 设计和审查。

允许新增本任务报告、脱敏库存证据和本地忽略目录中的只读盘点工具/日志。禁止修改业务代码、测试期望、Schema、既有数据库/原始数据、系统代理/TLS、生产/EC2、交易账户；不自动合并、部署、同步或给未知项计验收通过。数据库只用原生 SQLite URI `mode=ro`、`query_only`、只读事务；不调用可能初始化/设置 journal 的应用连接入口。原始行情不进入报告或 Git。

## 验收与交付

1. 阶段一：明确搜索范围，核实全部候选库的表/行数/日期/来源/批次/版本和实际读写边界；复核 187 行与指数观察，区分临时夹具、真实验收样本、正式持久库与 EC2 文档记录。
2. 输出库存表、来源清单、真实接口证据边界、SQLite 质量报告和 M3 接入差距。数据库路径或库存无法确认时，不创建替代库，不继续依赖它的采集。
3. 阶段二仅按实际盘点给有界计划，未知来源/许可/历史时间明确阻断；增量和重复行为复用既有不可变版本仓储。
4. 阶段三/四前置不满足则标记 BLOCKED/NOT RUN，不宣称完成采集/接线；保留核心 UNKNOWN、缺因子、日历/历史身份及 L2/L3 门禁。
5. 必要检查：盘点只读/前后文件 hash、脱敏 JSON/报告链接、`git diff --check`；按 G11 在隔离测试目录运行既有完整离线套件、`python -m pip check`，不修改断言。网络、UI、样本外分列。

独立 H 计划：`TASK-M0-M3-DATA-001-REVIEW`（待指派，未自动创建/执行），绑定最终 SHA 核对库存范围/归属、只读证明、真实与夹具隔离、来源许可、历史时间、版本与阻断条件。普通自检和 CI 不替代该审查；本任务不解除核心 #37、页面、M4、策略或生产门禁。

## 实际结果、阻断与交付

状态：**PHASE_1_COMPLETE / PHASE_3_4_BLOCKED**，任务整体尚未完成。用户补充确认7张表的定义，未给出Windows正式库的完整路径；没有将表定义当作物理文件确认，没有初始化、复制、迁移或写入任何既有库。阶段二仅提交待前置的有界草案，行情请求始终0。

交付5个新增文件：本任务单、`docs/M0_M3_LOCAL_INVENTORY.md`、`docs/M0_M3_COLLECTION_PLAN.md`、`docs/M0_M3_DATA_ACCEPTANCE.md`及`docs/evidence/TASK_M0_M3_DATA_001_INVENTORY.json`。不修改业务、测试、依赖、共享看板/权重或Schema；结构化反馈随脱敏证据记录，不给未知项加分。

| 本轮检查 | 实际命令/结果及证据 |
| --- | --- |
| 库存扫描 | `python artifacts/m0-m3-data-001/inventory.py`；修正对畸形测试观察JSON顶层类型的假设后exit0；613库逐表检查、1361个项目测试库路径单列，库及侧车前后hash相同；`inventory.json`保存完整清单 |
| 既有真实样本读回 | `python artifacts/m0-m3-data-001/readback.py`；修正工具对Diagnostic序列化字段的误用后exit0；187/1217/2291逐字段全部相同，历史as_of拒绝，三个response hash和迁移checksum一致；`readback.json`及create-only版本manifest，无价格写入公开摘要 |
| 完整离线 | `python -m pytest -q -p no:cacheprovider --basetemp=artifacts/m0-m3-data-001/full-tmp --junitxml=artifacts/m0-m3-data-001/full.xml`；**exit0，2871 passed / 1 skipped，337.54秒**，`full.log/full.xml`；skip为原手动AKShare实网，未开启网络；隔离临时测试库，不触碰盘点原库 |
| 依赖 | `python -m pip check`；exit0，No broken requirements found.，`pip-check.log`，无依赖安装/升级 |
| 最新main CI | [Offline pytest run 39515585717](https://github.com/fengjnah/a-share-quant-v1/actions/runs/39515585717) 元数据completed/success，run head_sha绑定本任务main基线；仅记录远端状态，不冒称读取了该run完整job日志或独立H通过 |
| 发布前检查 | 5文件范围、JSON缺失/null/无原始OHLC及现有文件hash、文档链接和`git diff --check`；实际输出归档忽略目录，最终提交/PR由发布记录绑定 |

Python固定为既有 `F:/codex-agnes/AI-trade-main-demo/.venv/Scripts/python.exe`（3.12.14），所有应用/测试调用显式PYTHONPATH指当前任务src，设置PYTHONUTF8/PYTHONIOENCODING及PYTHONDONTWRITEBYTECODE，防止editable包串库。实际导入路径和依赖/关键源码hash在机器证据中。库检查仅用原生只读SQLite，后续读回通过不改变连接配置的本机只读包装复用既有仓储SELECT，不建立另一套业务写入端口。

只读库存/读回与完整离线通过；新实网采集、测试库新批次→正式库写入、浏览器/手机UI、样本外回测均未执行/前置阻断。生产、EC2、云同步、账户未连接/未操作。两次报告工具失败是独立诊断点，未改业务/测试，也未以换编号重置来源失败预算；详见质量报告。

最小继续条件：确认Windows正式研究SQLite文件路径与归属/绑定（或明确尚无），再取得选定来源的研究/存储/自动采集许可；对指数/全A/状态/CFFEX现有7表外契约缺口先独立H设计。不会为解决路径未知擅自创建另一库，既有数据不重下，不解除核心#37/策略/生产门禁。

独立H与任务后续保持待指派，不在本会话自行形成独立结论；Draft PR只提交本轮证据/计划，用户决定下一步，不合并、部署或关闭原Issue。

# TASK-M3-CFFEX-RAW-PREVIEW-005 第一阶段报告

日期：2026-10-24，Asia/Shanghai。结论：**权限检查完成；隔离合成证据预览代码已准备；正式原始持仓预览 BLOCKED。** 未把未获授权的原始响应接入 M3，840 行及中信期货 IF2611 的真实数值展示尚未验收。

## 基线与执行

远端 main `20112111dbe287a770e5b845b3e036ba33d068ef`，GitHub API、本次 fetch、交付前 ls-remote 一致。PR60 已合并；PR61 是未合并报告，仅作旁证。完整依赖 SHA、已读规则和边界见 [任务单](tasks/TASK-M3-CFFEX-RAW-PREVIEW-005.md)。唯一执行模型 `gpt-6.1-sol / medium`：本会话运行日志核实模型，用户确认档位“中”；费用未知，不调用其他模型/子代理。风险 H，实施自检不能代替独立 H 审查。

开发分支 `codex/m3-cffex-raw-preview-005` 从最新 main 创建，原 dev/main 和运行服务保持原状。正式 8524 正在运行 dev/main `3975e2e6c35fe7c1f1bc01a0276ef65b55fbc028`，未更新、重启或切换到本分支。没有向 main 提交或自动合并。

## 权限判断及证据

| 检查对象 | 最新 main 上的实际内容 | 对本任务的含义 |
| --- | --- | --- |
| H1，`m3_store_snapshots.py:13,44`、`m3_store_results.py:109` | 非 REVIEW 分析收据要求 research+storage；仅 display 不能升为研究输入 | 保护分析用途；没有授权任意原始响应展示，也不能据此声称预览必须先有 research |
| M1，`m3_store_market.py:147` 及 Catalog 失败审计 | 失败尝试保留确切原始 evidence_id | 可追溯失败证据，不是展示许可 |
| 数据字典 B07，`:44–48`；`m3_store_catalog.py:156–198` | storage/display 等用途逐项列明；VERIFIED 和撤销按可信签发者、作用域、时点及独立信任根检查 | 没有“维护人员/loopback 自动获准”的现成例外；实现模型没有签发权 |
| `M3_CORE_CONTRACT.md:93` | L1 可展示受限有效观察，但不能升级研究/策略 | 不是对所有 Catalog 私有原始文件的独立 display 授权，不能跳过现有用途边界 |
| 数据字典 R03，`:101` | 缺日历允许原始观察，不得构造正式可消费 record | 不应为预览补造日历或 available_at，也不应先写正式持仓表 |
| 原 UI 任务单，`:13` | 2026-10-23 IF/IH/IC/IM 一次原始观察正式保存例外 | 未包含本次原始内容展示例外，不能从 storage 推导 display |
| 正式库只读库存 | verification_receipts=0、4 份 source_payload、4 份 observation | 本轮没有可审核的独立 display 授权记录 |

准确结论是“**没有找到覆盖本地维护预览的既有授权**”，不是供应商法律许可判断，也不是声称 H1/M1 明文禁止所有预览。按用户“若契约不允许则禁止绕过”的分支处理：不自行扩大 L1/一次保存例外，不使用环境开关代替授权，不更改现有契约、allowed_uses、质量或信任根。

## 隔离代码准备

新增 `src/ai_trade/market_analysis_cffex_raw_preview.py`，**没有正式页面路由或正式数据适配器**。组件只接受显式 test 句柄和 Catalog 标记为 synthetic 的证据，local/production 在任何数据库连接前拒绝；测试库中的 source_payload 也在读取正文之前拒绝。environment=test 是调用约束，不是可信身份认证，不能靠给正式库换标签取得权限；即使换标签，真实 evidence_kind 仍被拒绝。

复用既有 Database 和 Catalog evidence_bytes：重新打开 mode=ro / query_only、require_existing，不初始化或迁移；按原始大小/hash/路径验证后调用现有 CFFEX parse。没有调用 save_cffex、build_record、quality/receipt 写入或新的日历规则，不创造历史可得时间。

默认 `enabled=False` 不查库；测试调用者显式打开后，用户仍需勾选“启用合成证据预览”。展示 IF/IH/IC/IM、日期、采集尝试、合约、会员及 volume/long/short 筛选；从已存合成响应解析排名/成交量/持仓/变化，空值保留 UNKNOWN，不补零、不算交易方向。来源 ID/provider/endpoint/adapter、evidence/attempt ID、SHA256/MATCH、captured_at、尝试结束时间均有展示；captured_at 缺失保留 null，不从结束时间倒填。

固定标识 `UNVERIFIED`、`NOT ADMITTED`、`NOT FOR RESEARCH OR TRADING`，另显著标记 `SYNTHETIC TEST FIXTURE`，避免被误认成正式 840 行。该组件是离线准备，不是已经批准的维护预览；没有新增正式开关或正式数据导出功能。

新增 `tests/unit/test_cffex_raw_preview.py`：四品种原值/过滤、真实零与缺失、正式句柄连接前拒绝、test 库真实证据正文读取前拒绝、缺文件/大小/hash 不一致、采集时间未知、每次连接只读、默认关闭/显式启用/取消、元数据/警示和 UI 损坏失败。借用现有 AppTest 的本地 IPC 夹具，外部网络保持禁止。合成数据不作为真实来源验收。

## 验证记录

环境：现有 `F:\codex-agnes\AI-trade-dev\.venv\Scripts\python.exe`（实际运行 Python 3.12），本分支工作目录，`PYTHONUTF8=1`、`PYTHONDONTWRITEBYTECODE=1`。无新依赖、真实行情请求、TLS 降级或代理修改。

| 类型 / 命令 | 实际结果 | 限制 |
| --- | --- | --- |
| `python -B -m pytest tests/unit/test_cffex_raw_preview.py tests/unit/test_cffex_workbench_route.py -q -p no:cacheprovider --junitxml=../targeted.xml` | **23 passed，7.67 秒，exit 0** | 临时 SQLite、合成证据、本地 AppTest；不是 8524 真实预览验收 |
| 完整离线 `python -B -m pytest -q -p no:cacheprovider --junitxml=../final.xml` | **3196 passed / 5 failed / 8 skipped，361.20 秒，exit 1** | 冻结代码后运行；五项既有搬迁夹具失败，全套不通过 |
| `python -B -m pip check` | **exit 0，No broken requirements found** | 现有环境，没有安装包 |
| `git diff --check` | **exit 0** | 最终提交前再核对 |
| 8524 HTTP `/_stcore/health` | **HTTP 200，ok** | 现存旧 main 服务健康 |
| 8524 实际浏览器 `/?view=market` | **现状核验 PASS**：M3/CFFEX 模块、正式库路径和 `No stored CFFEX report for IF on 2026-10-23`，无新增预览入口 | 原始真实数据 UI 验收 **BLOCKED**，未部署本分支；浏览器只放行 loopback 请求 |
| 真实行情网络 / 样本外回测 | **未执行** | 本阶段不需要；无来源认证或策略验收声明 |

首次全量运行在代码准备期间启动，结果 **3180 passed / 6 failed / 8 skipped，367.23 秒，exit 1**。五项是已知 `test_data_directory_relocation.py` 搬迁夹具失败；另有 `test_replay_parameter_changes_are_rejected` 在源文件变化期间触发 `build changed during computation`，属于本次测试调度污染，不能归咎于既有基线。已冻结 src/tests，重跑完整套件；不修改失败期望或业务代码消除此保护。

最终重跑中 replay 参数测试通过，仅余五项同样的失败：`test_nonempty_v2_backup_restore_relocate_and_explicit_rollback`、`test_failed_api_step_keeps_evidence_without_switching_or_cleaning[1/2/3]`、`test_detects_concurrent_source_change_without_creating_target`。复现根因是搬迁工具只接受精确 v2/七表，而共享初始化夹具已有后续迁移；见 `storage/relocation.py:29` 的 `relocation accepts only exact released v2 / seven tables; no upgrade`。未扩大修改搬迁工具、迁移或测试期望；该既有阻断仍需独立处理。8 项跳过分别为真实 AKShare 1、缺本机真实 CFFEX 样本 1、Windows symlink 权限 3、Linux systemd 专属测试 3。没有新增失败，不声称全套/整体阶段验收通过。

浏览器工具准备先遇系统 Node 18 与 Playwright 不兼容，改用既有 bundled Node；首次 UI 导航的 radio 查找在控件加载前为空，改用应用现有 `view=market` 路由后成功。没有修改应用、浏览器安全设置或安装依赖。这些是验证工具故障，不计作已通过 UI 验收。

日志在当前聊天 `work/`：targeted.log/xml、baseline.log/xml、final.log/xml、formal-before.json、formal-after.json、8524-initial.json、8524-m3.txt。该目录不在仓库提交范围。截图在当前聊天 `outputs/8524-m3-current.png`；仅展示既有服务的阻断现状，无原始持仓正文。

## 正式库保护

只读 metadata 库存于本轮 22:44:43 和 22:47:27（Asia/Shanghai）执行，未读取原始响应正文：`F:\codex-agnes\AI-trade-data\sqlite\workbench.sqlite3`。

前后 SHA256 均为 `696d18b1e49bcdb962ae5b3df819839bd6472addcff9d57d1946a1e563e5d67c`；31 表逐表计数相同、5 个迁移、integrity=ok、foreign_key_check=[]。4 尝试、8 证据、4 质量记录、0 收据、0 正式 CFFEX 报告/排名、0 分析结果保持不变。未连接可写正式句柄，未改 Schema/allowed_uses/quality/AWS。

## 最小后续授权路径

1. 由治理认可的授权方提供明确批准及依据：2026-10-23 IF/IH/IC/IM 四份已存 evidence/hash、本地维护人员、loopback、有效期、用途、未经来源认证状态、不得用于研究/策略/再分发。当前实现模型不自签，普通“开关打开”不算批准。
2. 如现有契约无法承载维护例外，单独 H 契约/权限任务定义并独立审查该边界；或由获授权流程走既有 B07 display 收据及独立信任根校验。**本任务不修改任何 allowed_uses、收据或信任根**，也没有创建/执行这个后续治理任务。
3. 批准明确后，再将本隔离准备适配为正式只读 Evidence/Catalog 读取，复核撤销/期限/来源作用域及错误路径，独立 H 审查绑定最终 SHA，然后在 8524 验证真实四品种及 IF2611/中信期货的原始值。不能把合成夹具或本次空报告截图当作该验收。

原始内容维护展示不必通过补造日历或先写结构化表实现；正式研究和结构化入库的日历、来源、用途门禁继续独立。本轮没有取回或重新认证 840 行，也未硬编码参考成交量/多空/净仓。

## 交付与看板反馈

- 变更仅新增隔离组件、针对测试、任务单与本报告，未改变现有生产调用路径。
- 交付 Draft PR，状态待独立 `TASK-M3-CFFEX-RAW-PREVIEW-005-REVIEW`；审查任务/执行配置待指派，本会话不冒充独立审查，不自动合并、不通过业务阶段验收。
- 看板消费反馈：权限检查完成；隔离准备及相关回归通过；正式原始数据预览 BLOCKED（缺明确 display/维护例外）；真实 8524 预览验收未完成。未改自动生成 TASK_BOARD 或进度权重，不把本次工作登记成业务可用。
- 代码/测试/任务单提交：`f2702ecd8599c21828926ed606140bfa50ef30d1`；独立审查须覆盖该代码树及最终 PR head。随后仅补本报告，src/tests 与完整重跑时完全相同，不重复无变化的测试。预览源文件 SHA256 `8ba324a1efa92abd9352aa4542982d9a4f45cd274c60a529f2e98299ca3c1fed`；测试文件 SHA256 `b5d1dd0f7103dff46e99c028d7e25deb25feebefd47fa8a65c73ba75d0d9406f`。完整离线失败如实保留，不自动合并。Draft PR URL 和最终报告提交 SHA 随最终交付附上。

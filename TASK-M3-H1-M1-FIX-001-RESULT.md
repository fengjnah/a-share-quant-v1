# TASK-M3-H1-M1-FIX-001-RESULT

日期：2026-10-24。实施者自检报告，**不是独立 H 关闭结论**。

```ini
H1_STATUS = FIXED
M1_STATUS = FIXED
TARGETED_TESTS = PASS
FULL_OFFLINE_TESTS = FAIL
FORMAL_DB_MODIFIED = NO
AWS_MODIFIED = NO
M3_BUSINESS_GATE = PENDING_INDEPENDENT_REVIEW
```

H1/M1 修复实施与离线回归已交付，**整体验收未通过**。完整套件仍有五项原有搬迁夹具失败；远端 CI 另有一项工作台验收失败待独立定位。M3 业务继续 BLOCKED，不因本修复自动启用。

## 1. 基线、模型与工作区

- GitHub 最新 main / 实际修复基线：`b1252e03584887c84186a0700aa90de4e749b8eb`，本次 `git ls-remote` 核实。
- PR [#51](https://github.com/fengjnah/a-share-quant-v1/pull/51) 已合并；base `04e530871e2c8b4889c60027ac8d1ec4275009a2`、head `1e2b2c3e8cbab09c226ff0edc739ff08511eb67e`、merge `b1252e03584887c84186a0700aa90de4e749b8eb`，本次 GitHub API 核实。
- 修复代码及最终 67 项回归提交：`46be463c198cc3065a6271bb464b85dab2f43c4b`。完整套件在该提交的干净代码上执行；后续报告提交不改变 src/tests。
- 工作区：`C:\Users\iyoyi\.codex\worktrees\m3-h1-m1-fix-001\AI-trade`；分支 `codex/m3-h1-m1-fix-001`；[Draft PR #57](https://github.com/fengjnah/a-share-quant-v1/pull/57)，base main。
- OpenAI `gpt-6.1-sol / high`，核验依据为本会话用户明确确认；风险 H。未换模型、调用模型 API 或子代理，费用未知。规则、调研不适用理由、预算及独立 H 计划见[任务单](docs/tasks/TASK-M3-H1-M1-FIX-001.md)。
- 未改主工作区、main、stash、其他 worktree。Agnes 的 `F:\codex-agnes\AI-trade-m3-collector-001` 开始时 clean、HEAD 同基线；15:48 只读复查时已出现其未跟踪的采集/页面文件，没有本 PR 四个存储文件的修改，本任务未写入该目录。CFFEX 集成可能与本 PR 的 `save_cffex` 入口重叠，须按提交集成，禁止覆盖 Agnes 代码。

## 2. 实际缺陷与修复

实际依据是本地独立报告 `C:\Users\iyoyi\.codex\worktrees\m3-db-schema-v5-h-001-review\AI-trade\TASK-M3-DB-SCHEMA-V5-H-001-REVIEW.md` 第 4 节，以及本次源码和隔离反例。没有把泛化风险描述当成已存在缺陷。

| 编号 / 严重度 | 实际缺陷、触发和影响 | 生产代码位置 | 修复及验证 |
|---|---|---|---|
| H1 / High | 信任根签发 VERIFIED 但仅 display 的来源/研究/时间收据，在三种模式下仍可封存 COMPLETE；结果消费者只核对引用、claim 和 VERIFIED，未消费用途 | `m3_store_snapshots.py:44`（`_check_record`）；`m3_store_results.py:109`（`_diagnostics`） | 所有非 REVIEW 输入认证收据必须显式包含 research+storage。缺项保留 `RECEIPT_USE_NOT_AUTHORIZED:<role>`；research 为 PARTIAL 观察，strict_backtest/paper_trade 为 BLOCKED。结果消费者再次检查实际冻结收据的用途，不能依靠旧 COMPLETE 标志绕过 |
| M1 / Medium | CFFEX 保存 raw 后解析失败，通用审计写入 FAILED 却没有 raw 的 evidence_id；事务回滚后的审计也有同样丢关联路径 | `m3_store_market.py:147`（`save_cffex`）、`:169`（`_save_cffex`）；`m3_store_catalog.py:260`（`_write`） | 公共入口取得真实存档 ID，绑定解析/校验失败；私有事务入口新增兼容的可选 failure_evidence_id，把事务失败绑定同一 raw。保留原始异常，审计失败另行明确报错，不制造成功 run |

H1 所需 research+storage 沿用已有聚合输入 `_market_gate` 的用途规则；三种分析模式均不把展示许可当研究许可。没有增加自动认证、自动化/实盘许可或新准入算法。REVIEW 的独立策略审查规则保持原样，本任务不认证 L3 审批或真实来源。

输入四个时间、业务日期、质量决定、来源绑定、最新版本/撤销与过期选择保持原规则。收据来自配置的信任根；有声明或能够计算均不证明供应商真实性或授权。封存检查仍记录具体收据/质量 ID 与哈希。旧快照和历史结果可读，不修改旧 COMPLETE、历史决定或 manifest；新结果消费必须重新满足用途检查。

M1 的失败记录通过 attempt_id 关联原 source_id、request_key、request_json、开始/结束时间及确切 raw。交易日/品种/合约沿用已有 m3-request-v1 参数（合约使用 symbol），不改表或字段。已 FAILED/BLOCKED 的尝试不可复用；即使换成有效响应也要求新 attempt ID，旧记录不会被覆盖。成功写入和已有成功数据的重复调用保持原有去重行为。网络未取得载荷或输入不可存档时 evidence_id 仍可为 NULL，禁止伪造证据。

空响应是 FAILED；缺会员且有数值仍由原解析器拒绝；无法表示的排名是 BLOCKED、仅保留 raw；缺排名不填零；明确会员的合法零持仓仍保存。CFFEX 写入后的质量仍为 UNKNOWN，未因此获得方向或研究认证。

## 3. 差异与兼容性

仅四个生产文件、两个新增测试文件及本任务文档。`save_cffex` 公共签名、Schema v5、已发布 v1–v5 checksum、31 张用户表、JSON 结构、核心评分、解析器和页面均未改动。私有 `_write` 新增可选失败证据参数，其他调用方默认行为不变。

调用链：`seal_snapshot → _check_record → 冻结决定/原因`；`execute → get_snapshot → adapter → _diagnostics → 原子结果写入/FAILED 运行`；`save_cffex → raw 存档 → _save_cffex → parse/重建校验 → _write`，前置和事务异常均关联实际 raw。

兼容性变化有意收紧：缺用途的新快照降级/阻断；声称 VERIFIED 的结果如收据用途不足则拒绝写入，保留 FAILED 运行，无诊断/因子子行。历史失败尝试不补写，旧 NULL 证据关联仍保持历史事实；新采集须使用新 ID。调用方不能以捕获异常后返回空成功或复用旧失败 ID 实现重试。

## 4. 离线复现与测试

环境：Windows、Python 3.12.14、SQLite 3.53.1、pytest 8.4.2、pandas 3.0.6、jsonschema 4.26.0、requests 2.34.2、streamlit 1.66.0。解释器为 `F:\codex-agnes\AI-trade-main-demo\.venv\Scripts\python.exe`；每次显式设置本 worktree 的 `PYTHONPATH=src`、禁写字节码。完整套件首轮遗漏 UTF-8 子进程设置，后续只在测试进程设置 `PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8` 重跑，未改系统环境。默认 conftest 阻断 socket；数据库均为 pytest 临时目录。为测试非合成门槛，个别夹具使用 source_observation 形状，但 provider、authority、bytes 全为显式离线夹具，绝不作为真实认证。

命令前缀：`python -B -m pytest -q -p no:cacheprovider`，各次均额外指定 Git 外 `--junitxml=...`。

| 阶段 | 实际结果 / exit | 证据 |
|---|---|---|
| 修复前新增两个回归文件，首批 64 项 | 47 failed / 17 passed，exit 1，40.38s | `before.log/xml`。36 项快照用途反例及 8 项 CFFEX 反例有效失败；另 3 项消费者测试先被新夹具重复引用 environment 的错误干扰 |
| 生产修改前修正新夹具，只跑消费者/旧快照反例 | 2 failed / 1 passed / 51 deselected，exit 1，4.53s | `before-consumer.log/xml`；两个负例均为未拒绝用途，正例通过。未修改任何既有测试断言 |
| 首次相关组命令 | exit 4，无测试执行 | `targeted.log/xml`；文件名误写 test_m3_schema.py，纠正为既有 test_m3_storage_schema.py |
| 两个新增文件 + 5 个既有 M3 存储/trace 文件 | 207 passed，exit 0，85.83s | `targeted-corrected.log/xml`，冻结提交前工作树；其后只补 3 个反例并增强旧快照为端到端，不再改生产实现 |
| 最终新增两个文件 | 67 passed，exit 0，40.24s | `regression-final.log/xml`，与修复提交 src/tests 内容一致 |
| 完整离线套件首轮，提交 46be463 | 3134 passed / 7 failed / 4 skipped，3 warnings，exit 1，455.81s | `full-offline.log/xml`；五项搬迁失败，另两项 progress 子进程编码失败 |
| 同两项 progress 在原 b1252e0、同缺省编码环境复现 | 2 failed / 3 warnings，exit 1，2.62s | `baseline-encoding.log/xml`；证明不是本修复引入 |
| 同两项在修复提交、显式 UTF-8 | 2 passed，exit 0，4.35s | `utf8-encoding.log/xml`；不改代码或断言 |
| 完整离线套件重跑，提交 46be463，显式 UTF-8 | **3136 passed / 5 failed / 4 skipped，exit 1，404.69s** | `full-offline-utf8.log/xml`；失败集合与原 H 基线 XML 完全一致，相关 M3 210 项全部通过 |
| `python -B -m pip check` | PASS / exit 0，No broken requirements found | `pip-check.log` |
| `git diff --check` 及受保护路径 diff | PASS / exit 0 | Schema/迁移、核心算法、数据解析器及数据字典与 b1252e0 相同 |

新回归覆盖：三种模式×三个认证角色×五组用途；合法授权、时点/业务日/过期/撤销/信任根、质量 FAIL/UNKNOWN、冻结与重复封存；公共 execute 消费及真正封存的旧 COMPLETE manifest；失败结果无可用子项。CFFEX 覆盖成功与读回、空响应、非法会员、日历失败、事务失败、部分品种成功/失败、不同批次、同 ID 拒绝、新 ID 重试、不可表示/缺排名、合法零、审计失败。

最终完整套件共 3145 项；67 个新增回归及原 143 个 M3 存储/Schema/trace 测试均通过。四个跳过为 1 项未授权真实 AKShare、3 项 Windows 缺 symlink 权限（1314），不视为通过。`final-evidence.json` 对比原 H 的 `offline.xml` 和本次 XML，确认失败集合相等、src/tests Python 文件与冻结提交测试开始时哈希全部一致。新测试不削弱现有断言；本地没有新增测试失败。

### GitHub CI（独立证据，未通过）

代码提交 46be463 对应 [Offline pytest #79 / run 40075848848](https://github.com/fengjnah/a-share-quant-v1/actions/runs/40075848848)，实际 completed / failure；job 120818892557。已读取真实 job 日志：**3135 passed / 6 failed / 4 skipped，12 warnings，226.77s**。五项为相同搬迁测试；另一项为 `tests/manual/test_workbench_offline.py::test_strict_workbench_all_pages_and_missing_store`，嵌入脚本 line 53 的 `assert any('不回退临时库' in e.value for e in fresh.error)` 失败，外层测试位置 `:66`。这是清除正式路径配置后的错误提示断言，不是 H1/M1 回归失败。

该工作台测试、页面及入口文件与基线没有 diff，本地完整套件同项通过。CI 使用 Linux / Python 3.11.17 / streamlit 1.66.1 / pandas 3.1.0，与本地不同；这些差异仅为已观察事实，**尚未证明是根因，也未取得同 CI 环境下的基线对照**。不能宣称它已修复或必然与本 PR 无关。按 G10 不扩大修改，保持为独立 CI 阻断：后续在相同 Linux/依赖环境复现缺绑定时的错误提示，并对照 b1252e0，记录实际 UI 错误；禁止仅改期待、放宽路径保护或降依赖掩盖失败。最终报告文档提交的 CI 如尚在运行，同样不报通过。

### 已知五项独立阻断

原 H 报告在相同 b1252e0 上完整套件为 3069 passed / 5 failed / 4 skipped。本任务须对照新运行核实以下五项是否仍存在，不修改它们：

- `test_nonempty_v2_backup_restore_relocate_and_explicit_rollback`
- `test_failed_api_step_keeps_evidence_without_switching_or_cleaning[1]`
- `test_failed_api_step_keeps_evidence_without_switching_or_cleaning[2]`
- `test_failed_api_step_keeps_evidence_without_switching_or_cleaning[3]`
- `test_detects_concurrent_source_change_without_creating_target`

位置：`tests/unit/test_data_directory_relocation.py:14–18` 的 setup 默认 initialize 为 v5；`storage/relocation.py:29` 按已发布契约只接受精确 v2 七表，在实际搬迁断言前拒绝。最小后续修复是让该测试夹具显式构造已发布 v2，而不是扩大生产搬迁能力或弱化断言；需独立任务/审查。本任务不消除这个基线失败数量。

## 5. 正式数据库与证据保护

正式库 `F:\codex-agnes\AI-trade-data\sqlite\workbench.sqlite3` 仅读取文件元数据/字节哈希，没有打开 SQLite 连接。修复前、测试期间及测试完成后 SHA256 均为 `2d38f34d3a6a26026d576e24896f117ef68e017deae286a6293b5faba4ac333f`，737280 字节；WAL/SHM/journal 均未出现。

全部运行日志/隔离证据在 Git 外：`F:\codex-agnes\AI-trade-local-state\m3-h1-m1-fix-001\`。`environment-and-tree.json` 记录解释器/依赖、正式库保护哈希与所有 src/tests Python 文件 SHA256。未提交 SQLite、原始真实行情、凭据或运行载荷。

| 验证类别 | 状态 | 边界 |
|---|---|---|
| H1/M1 离线回归 | PASS | 自检通过，等待独立 H |
| 完整离线套件 | FAIL | 3136/5/4；失败集合等于原 H 基线 |
| GitHub CI #79 | FAIL | 3135/6/4；另有工作台断言未定位 |
| 真实行情/来源认证 | NOT RUN | 未发真实行情请求，不能认证数据许可或覆盖 |
| 本地浏览器 UI | NOT RUN | 未启动/修改页面 |
| 样本外回测/策略有效性 | NOT RUN | 未执行 |
| 正式数据库 / AWS | 未修改 | 正式库只读文件哈希，未连接 AWS |

## 6. 剩余门禁与交付

1. 独立 `TASK-M3-H1-M1-FIX-001-REVIEW` 必须绑定最终 Draft PR SHA，重审用途、旧快照消费者、失败/事务/重试证据及与 collector 的实际调用链；本实施会话不自称独立审查。
2. 五项搬迁夹具失败、CI 工作台断言失败仍是独立验收阻断；不把本 PR 的局部通过写成完整套件/CI 通过。CI 额外失败的因果尚未闭环，不能将本任务标为全部验收完成。
3. Agnes collector 需集成该提交并单独验收网络/解析发生在 repository 外部时的失败记录、真实 Batch 参数、来源许可、日历、发布时间和会员 scope。此修复不替代真实最小闭环验收。
4. 真实数据认证、M3 业务启用、M4 发布、样本外、实盘和 AWS 门禁保持原状态。新表或修复提交均不自动解除。

交付为 [Draft PR #57](https://github.com/fengjnah/a-share-quant-v1/pull/57)。代码测试绑定 46be463；报告提交仅增加本文件，不冒称在新的文档 SHA 上重新执行全套。最终 PR head 以交付回复及 GitHub 实际 head 为准；CI 状态单独记录，不自动合并。

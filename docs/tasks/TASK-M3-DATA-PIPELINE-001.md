# TASK-M3-DATA-PIPELINE-001：接口证据与数据认证

## 身份与基线

- 类型：implementation / bounded source acceptance；等级 H（真实来源、时间和准入证据边界）。
- 唯一模型：OpenAI / Codex Desktop `gpt-6.1-sol`，固定 `high`。本轮运行元数据 turn_context `01a159ea-3895-7450-a28d-b4f7eece18c1` 实际核验，非全局配置推断；旧 REVIEW 已结束，配置不混记。费用/额度未知，不调用子代理或其他模型。
- 预算：90分钟；每个选定 HTTP 端点最多一次发送、零重试；股票腾讯包含起始日探测与行情页共至多2次，其他来源各1次，总计至多6次。每次I/O上限5秒，响应8MB（CFFEX沿用2MB），独立worker总限45秒；失败不重试/换源/修改代理或TLS。相同验收问题最多两次不同诊断性修复，核心回归失败立即停止扩大修改。
- GitHub main / 本地基线：`94cdd487bfd4633ecc2f002aad014f98dec961a5`。PR #36 merged（head `d60fa8809a248cb4b4a63ed4ee514296645bed2b`，base `79e715e54c29b274f57914313abcb3b992d43894`）；#32/#34亦merged。Issue #33/#35/#37/#38仍open；#37独立H尚未执行，不以CI/合并替代。
- 原目录 `F:/codex-agnes/AI-trade` 分支 `codex/m3-remodel-002`，tracked干净，保留原有`.worktrees/`及其他会话现场。托管worktree操作返回pending后长时间无最终路径，未使用其目录；从本地已核验提交建立独立Git工作区 `F:/codex-agnes/AI-trade-m3-data-pipeline-001` / `codex/m3-data-pipeline-001-work`，不切换原目录分支。
- 目标：取得有限真实接口证据、列明未接通项，建立消费现有核心诊断的认证矩阵及页面兼容提案。非目标：修改核心公式/准入/共享Schema/数据库结构/页面/策略/生产/AWS/账户，不执行#37独立审查。

## 开始前实际阅读与适用规则

已读同一基线：AGENTS.md、MODEL_ROUTING_POLICY v1.0、TASK_TEMPLATE、OPEN_SOURCE_RESEARCH_POLICY v1.0、PROJECT_STATUS、DECISIONS、DATA_CONTRACT、INTERFACE_CONTRACT、M3_CORE_CONTRACT、M3_CORE_SOURCE_ACCEPTANCE、TASK-M3-CORE-003-FIX、SOURCE_HEALTH_CHECKS、TASK-008A，以及实际public/CFFEX/stock adapters、HealthTransport/HealthService、Ingestor/EvidenceStore、SQLite仓储、核心Request/SourceEvidence/Diagnostic及测试。无适用子目录AGENTS/override。

适用G01–G12：隔离现场、实际规则/固定模型、H独立审查、时间/UNKNOWN不变量、受限实网与离线分列、生产/Git边界、失败升级及精确SHA交付。核心独立H未通过，因此稳定页面依赖和真实研究认证保留BLOCKED；本轮只做候选兼容和来源证据，不解除门禁。来源缺失时不制造Receipt、日历或历史证券状态。

调研：复用现有实现/既有研究，补查本次触达的固定AKShare1.19.1源码和MIT软件许可证（本地文件哈希写入报告），不复制外部代码、不新增依赖/数据源。已读Tencent/index/Legu实际调用、单位、失败与SDK清洗边界；SDK许可与数据供应商授权分开，后者未证实保持UNKNOWN。官方站点资料仅有界查阅，不推断全部数据权利；若需要新来源/历史契约/迁移则另立H任务。

## A/B/C 负责人、边界和交接

| 工作流 | 负责人 | 输入 | 输出 | 文件范围 |
| --- | --- | --- | --- | --- |
| A 接口 | 本会话，同一模型 | 既有适配器；固定沪深300、600000.SH/2026-10-14～15、IF/2026-10-16；显式实网开关 | 一次性来源状态/HTTP/解析/行数/日期/批次/本地快照证据；无来源项BLOCKED | scripts/verify_m3_pipeline.py；仅忽略artifacts内原始证据/隔离临时SQLite |
| B 认证 | 本会话，同一模型 | A的真实证据、既有M3核心Diagnostic | 来源/单位/覆盖/时间/质量/版本/准入矩阵，未知及升级条件 | src/ai_trade/m3_data_pipeline.py、对应新测试、认证矩阵/脱敏摘要 |
| C 页面兼容 | 本会话，同一模型；页面实现由TASK-M3-REMODEL-002负责 | 核心Diagnostic.to_dict原样及A的传输证据 | 兼容字段映射、候选接口、稳定门禁/后续清单 | docs/M3_DATA_PIPELINE_HANDOFF.md；不修改页面/核心/共享契约 |

## 验收、计划和证据

- AC-01：完整来源/字段/单位/历史/授权清单，逐项PASS/FAIL/BLOCKED/NOT RUN；网络成功不等于来源认证。
- AC-02：真实请求显式开启，预算/TLS/零重试/响应限额/worker期限可核验；默认离线不得发请求。原始载荷仅本机忽略目录，提交前审查脱敏摘要。
- AC-03：实际诊断只调用现有核心，原样序列化；没有行情、UNKNOWN质量/时间、缺全A分母等不能升级。六因子与价格代理分开。
- AC-04：离线测试覆盖网络默认关闭、请求预算及失败、旧快照不补造时间、禁止混源/重复日期、诊断与历史as_of一致、来源成功不签发VERIFIED。
- AC-05：相关及完整离线 `python -m pytest -q -p no:cacheprovider`（独立basetemp）；`python -m pip check`；`git diff --check`。父子进程显式当前工作区PYTHONPATH、PYTHONUTF8=1、PYTHONIOENCODING=utf-8。
- 交付：接口报告、认证矩阵、页面兼容/后续清单、任务记录、独立分支PR。H任务不等L批次；建议独立 TASK-M3-DATA-PIPELINE-001-REVIEW 对最终SHA复核，在完成前不合并/发布/声明稳定准入。独立审查须另行指派，不由本实施会话换角色执行。
- 真实来源、离线测试、浏览器UI和样本外分别记录；浏览器/样本外本任务未授权为通过，生产不操作。

## 实际交付与验证

独立工作区仅新增8个任务文件：m3_data_pipeline.py（纯证据组合，调用核心）、verify_m3_pipeline.py（受限显式验收编排）、对应19项离线测试、本任务单、接口报告、认证矩阵、页面交接和脱敏机器证据。原market_analysis_core/contract/data、共享Schema、旧页面、数据库Schema及依赖均未修改。

| 检查 | 实际命令/退出码/结果 |
| --- | --- |
| 初版相关离线 | `python -m pytest -q -x -p no:cacheprovider tests/unit/test_m3_data_pipeline.py --basetemp=artifacts/m3-data-pipeline-001/targeted-tmp --junitxml=artifacts/m3-data-pipeline-001/targeted.xml`；exit0，19 passed，2.04秒 |
| 适配边界自检后复跑 | 同命令，独立targeted-2-tmp / targeted-2.xml；exit0，19 passed，4.21秒。自检发现既有price_frame会覆盖显式行身份，新桥只补缺列并保留object原值交核心；同步使反例直接使用混标，不改弱断言/共享实现 |
| 完整离线 | `python -m pytest -q -p no:cacheprovider --basetemp=artifacts/m3-data-pipeline-001/full-tmp --junitxml=artifacts/m3-data-pipeline-001/full.xml`；**exit0，2853 passed / 1 skipped，446.01秒**。默认socket禁网，隔离测试库；唯一skip是未显式开启的live AKShare测试 |
| 真实受限接口 | `python scripts/verify_m3_pipeline.py --enable-live --analysis-date 2026-10-19 --output-dir artifacts/m3-data-pipeline-001/live`；exit0仅代表报告生成。批次pipeline-20261020T153923Z-c55591fd，实际6次发送/零重试；2个来源PASS、3个FAIL、8项BLOCKED。HTTP成功与源认证分列，见接口报告 |
| 依赖 | `python -m pip check`；exit0，No broken requirements found.，pip-check.log |
| 差异/文档/脱敏 | 对明确8文件清单检查暂存diff、内部文档链接及JSON/代码hash/请求预算/字段隔离；最终实际输出保留artifacts/m3-data-pipeline-001/delivery-checks.json；不提交原始价格/CSV/SDK帧/SQLite或凭据 |

命令中的python均为既有 `F:/codex-agnes/AI-trade-main-demo/.venv/Scripts/python.exe`；父子进程PYTHONPATH显式指本任务工作区src，UTF-8进程环境及PYTHONDONTWRITEBYTECODE=1。实际导入和版本见environment.json，不新增或升级依赖。未发生非预期核心测试失败，未进行诊断性业务修复；不因换编号重置失败记录。

| 验证类别 | 实际状态 |
| --- | --- |
| 现有完整离线/新增边界 | **通过**，上述2853/1skip |
| 真实网络接通 | **部分通过**，新浪/腾讯成功；东方财富/乐咕/CFFEX传输SSLError，HTTP未知；不推断根因、空行情或休市 |
| 数据质量/研究认证 | **BLOCKED**：两个成功源也仅L1；无真实L2/L3、无供应商授权/历史日历/全A池认证 |
| 浏览器/真实手机UI | **未执行**；页面只交兼容提案 |
| 样本外回测/生产/账户/AWS | **未执行/未操作** |

机器证据包含逐维要求、actual_fields、时间、批次、hash、源状态和structured_feedback；没有修改共享TASK_METRICS权重或给未知项加分。托管工作区迟到后核验其干净且同SHA，已通过宿主archive_worktree安全归档；实际实现始终留在上述F盘独立工作区。

状态：**READY_FOR_INDEPENDENT_REVIEW（候选证据桥）**。核心#37及本任务最终SHA的独立H尚未通过，稳定页面依赖/真实研究/策略/生产门禁不解除。提交SHA和草稿PR由实际发布后交付记录绑定，避免在提交内循环引用自身SHA；用户人工处理，不自动合并、部署或关闭旧Issue。

发布校验记录：首次API上传证据JSON读取了Windows工作副本CRLF字节，blob SHA与Git索引的LF版本不符；校验立即停止，未创建tree/commit/ref。改为从Git索引读取原始blob并逐一比对，只有8个blob及完整tree全部匹配才发布，不跳过SHA检查。此为传输字节规范诊断，没有改变代码或验收断言。

# TASK-M3-CFFEX-COLLECTOR-FIX-002

## 开始记录（实施前）

- 类型 implementation；H：时间可见性、来源边界及失败事务审计。唯一执行配置 gpt-6.1-sol / high，用户本任务明确确认；不调用子代理或外部模型。费用及剩余额度未知；预算120分钟，同一验收问题最多两次不同诊断修复，G10核心失败立即停止扩大范围。
- 基线 main `3975e2e6c35fe7c1f1bc01a0276ef65b55fbc028`；PR59 GitHub API确认 merged，head `c6db39dd69805c7a11463f2b2be183a3130f3a4b`，base `d10b281b84dd6950188aa010f3b9e6977f25d1bd`。复用干净工作区 `C:\Users\iyoyi\.codex\worktrees\m3-cffex-ui-fix-001\AI-trade`，新分支 `codex/m3-cffex-collector-fix-002`，原分支保留。
- 实际阅读上述基线的 AGENTS.md、docs/MODEL_ROUTING_POLICY.md、docs/tasks/TASK_TEMPLATE.md、docs/PROJECT_STATUS.md、docs/DECISIONS.md、docs/OPEN_SOURCE_RESEARCH_POLICY.md、docs/M3_CORE_CONTRACT.md，以及 cffex_collector、cffex_sessions、cffex_rankings/time/models、m3_store_catalog/market、相关单元测试及M3存储数据字典的B03审计约束。无下级AGENTS覆盖。适用G01–G12；本任务不自动合并，独立H须另会话绑定交付SHA。
- 调研：适用但有界复用既有内部实现，不引入外部软件/依赖，不复制外部代码。现有客户端有2MB响应上限和零自动重试；现有time_fence已实现逐日可见、下一开盘且不早于实际采集的保守规则；现有Catalog支持不可变结束态attempt，不支持IN_PROGRESS。采用这些接口；拒绝凭文件mtime生成日历知识。数据许可仍未知，公开访问不代表研究/再分发授权。
- 允许文件：collector、sessions及其针对性测试、本报告；不修改Schema、M3页面、评分、正式数据库、AWS或dev/main。此前原始观察写入例外不适用于本任务。
- 网络：仅官方日历证据调研，最多两次检索及两份官方文档，单请求20秒、无自动重试、TLS保持验证；不请求新行情。默认测试网络阻断，临时SQLite。正式库仅SQLite mode=ro检查。
- 验收：定向pytest、完整离线pytest、pip check、git diff --check、正式库前后哈希/行数/账本/证据校验。真实网络、离线重放、UI、样本外结果分开报告。
- 独立审查计划：TASK-M3-CFFEX-COLLECTOR-FIX-002-H（待指派，非本会话执行）；审核前保持Draft和M3业务门禁。正式结构化写入另行授权，不在本任务执行。

## 已确认根因与保护现场

1. 日历14条硬编码声明无独立日历证据，含10/24、10/25、10/31开市及10/29、10/30错误闭市声明；自动注册为accepted/synthetic并凭CSV文件mtime回填知识时间。
2. fetch、parse、calendar/build_record和证据前置失败直接return，save_cffex的M1事务审计无法覆盖；内存去重也跳过新attempt；响应体无大小上限，HTTP错误状态未拒绝。
3. 正式库只读基线：Schema5、31张用户表，4条BLOCKED、8份证据、4条UNKNOWN质量决定；结构化报告及持仓均0。SHA256 `696d18b1e49bcdb962ae5b3df819839bd6472addcff9d57d1946a1e563e5d67c`，integrity_check=ok，foreign_key_check=[]。完整快照保存于 `F:\codex-agnes\AI-trade-local-state\m3-cffex-collector-fix-002\formal-before.json`。

## 实际修改及兼容性

| 文件 | 修改及保持的不变量 |
| --- | --- |
| src/ai_trade/market_data/cffex_sessions.py | 原14条全部撤销为UNKNOWN，开收市时间和证据为None；返回防御性副本，不凭星期或缺文件推断开闭市 |
| src/ai_trade/market_data/cffex_collector.py | 删除自动生成日历、mtime回填及内存提前返回；显式冻结calendar_version_ids；增加请求/失败/重试证据；响应上限复用2MB；状态/类型检查、无自动重试；成功与重复均由原save_cffex完成 |
| tests/unit/test_cffex_collector_audit.py | 23项可移植回归，不依赖私有CSV，不修改原测试期望；覆盖未知日历、时间边界、失败审计、部分响应、幂等及读回 |
| 本报告 | 起始规则、证据、验收和剩余门禁；不修改自动生成的TASK_BOARD或未审计进度权重，反馈在本报告登记，待后续看板维护消费 |

原构造/collect/get_report仍可调用，新增calendar_version_ids默认为空；未提供有证据的冻结日历时有意BLOCKED，不再自动造日历。已知污染源`cffex-sessions`的存量版本也拒绝；合成日历只允许显式离线重放。显式ID只是调用方选定的版本，不构成独立认证，仍需来源、许可、时间、质量的独立核实及H审查，不能凭ID升级L2/L3。没有新增Receipt或质量通过状态；save_cffex的lineage质量仍UNKNOWN。原Schema v1–v5、H1/M1、快照权限、页面、评分及time_fence均未修改。

## 日历证据与认证范围

来源调研为CFFEX官方域名的两组有界检索（2026国庆安排、交易日规则），没有取得足以独立认证本次10月逐日日历及发布时间的材料。候选 [CFFEX交易规则PDF](https://www.cffex.com.cn/u/cms/www/202003/27155731wtng.pdf) 的搜索摘要只提供一般规则线索，不足以确认指定日期、完整假期/临时停市、实际开收市时段或会员排名发布时间；另一版本候选为 [官方交易规则PDF](https://www.cffex.com.cn/u/cms/www/202003/27155833v091.pdf)，未下载，不当作本轮已核实材料。

第一份PDF：web打开超时；本地单次HTTPS、verify=True、connect/read=6/12秒、禁止重定向、2MB上限，于`2026-10-24T13:46:34.884478+00:00`请求失败SSLError，无取得的官方响应正文，HTTP状态/文件SHA256均不可得，不制造哈希或改用HTTP冒充验证。证据元数据：`F:\codex-agnes\AI-trade-local-state\m3-cffex-collector-fix-002\official-calendar-evidence.json`。

机构=CFFEX；证据类型=一般规则候选（未成功取回原文）；可认证日期范围=无；具体10/23、10/24、10/25及其余受影响日期均保留UNKNOWN；排名原始响应只证明已观察的字节，不独立证明完整交易安排。实际发布时间仍UNKNOWN。来源自动采集、存储、研究、展示及再分发授权均未由本次规则检索证明。

## available_at及失败状态流转

复用既有time_fence：验证交易日及逐日可见的CFFEX日历；缺任一所需日期阻断；事件为已证实session close；实际观察不得早于收市；ingested不得早于observed。无发布时间证据时published_at保持NULL并附UNKNOWN告警，available_at采用不早于实际采集、晚于交易日的下一已知开盘，不倒填交易日零点或历史首发。日历未配置/未知时不生成结构化报告。默认观察时间在收到响应后取实际UTC，默认入库时间在解析后取实际UTC；离线显式历史时间仍经原门禁校验。再次获取相同字节可复用原已保存观察的时间，当前尝试的获取时间另在manifest保存，不覆盖历史版本。

状态顺序：生成UUID attempt/run → 来源登记 → 请求证据STARTED（不是ledger完成态）→ 有界单次fetch → 实际响应先存证 → HTTP/解析校验 → 显式日历/time_fence → 原save_cffex原子写入 → 完成manifest。

- 无响应的网络/超时失败：ledger FAILED、returned_rows=NULL，请求manifest关联，无伪造raw。
- 收到空/错误/部分响应：保存真实字节（含空字节），标明HTTP状态、传输和response_complete；失败阶段与异常类进入ledger及manifest，不把部分字节当完整成功响应。解析失败不补零或写业务表。
- 日历不足：BLOCKED，保留实际raw和阶段。save_cffex既有FAILED/BLOCKED不可变账本不覆盖。
- 审计/证据保存失败：调用返回AUDIT_FAILED（API状态，未扩展SQL枚举），不声称已完整留痕。若业务已SUCCESS而完成证据失败，明确AUDIT_FAILED且保留version_id，不谎称事务已回滚。源库失效导致连来源都无法登记时同样显式AUDIT_FAILED。
- 每次实际调用均新UUID。retry_of关联同source、variety、trade_date最近已完成尝试；不跨品种或批次篡改旧行。调用方重复run标签时生成新retry run，并在manifest保留requested_run_id；成功重复仍登记DUPLICATE，业务版本不重复。并发调用只关联各自开始时已完成前序，不声称单链串行化；无自动重试。
- 请求前只有STARTED证据，没有伪造finished_at；进程硬退出的未完成请求需按原B03恢复规则另行核实，不自动补SUCCESS。

## 验证记录

日志根：`F:\codex-agnes\AI-trade-local-state\m3-cffex-collector-fix-002`，SQLite/CSV/原始响应/私有日志不提交Git。

所有pytest使用`F:\codex-agnes\AI-trade-dev\.venv\Scripts\python.exe -B -m pytest`，工作区src加入PYTHONPATH，PYTHONDONTWRITEBYTECODE=1、PYTHONUTF8=1、PYTHONIOENCODING=utf-8，`-q -p no:cacheprovider --junitxml=<日志根相应.xml>`；默认conftest禁止联网。Python3.12.14/SQLite3.53.1，与既有环境一致。

| 检查 | 命令/范围 | 实际结果 |
| --- | --- | --- |
| 基线复用 | git diff --quiet a57e6f3a9eb6a77b98d49382ace89a1c19a3d472 3975e2e6c35fe7c1f1bc01a0276ef65b55fbc028 -- src tests | exit0，src/tests相同；既有完整日志full-integrated-main.xml实际3158通过/5失败/8跳过，非猜测基线 |
| 旧版反例 | git archive上述main的src到隔离目录；本轮测试选择`-k 'all_unsupported or transport_failure or parse_failures'`并显式`-o pythonpath=<baseline/src>` | exit1，8失败/15未选；另用旧版实际执行fetch超时及非法CSV，两次FAILED后直接查询账本实际仍0行；baseline-defect-reproduction.json。首次未覆盖pytest的pythonpath配置误测新版8通过，不作反例证据；纠正配置后的baseline-red.log/xml为有效记录 |
| 新回归 | tests/unit/test_cffex_collector_audit.py | exit0，23 passed，8.72秒；regressions.log/xml |
| 定向 | 新回归 + test_cffex_collector.py + test_cffex_rankings.py + test_m3_storage_market.py + test_m3_snapshot_permissions.py | exit0，136 passed，59.82秒；targeted.log/xml |
| 完整离线 | 无路径筛选pytest | exit1，3181 passed / 5 failed / 8 skipped，350.21秒；full-offline.log/xml/exit.txt。与main相比仅新增23通过，失败集合精确一致，full-baseline-comparison.json |
| 依赖/diff | python -m pip check；git diff --check | exit0，No broken requirements found；diff无空白错误 |
| 正式库保护 | sqlite3 URI mode=ro、integrity/FK、原31表行数/5迁移checksum/4attempt/8证据逐项比较，实际证据文件SHA复核 | unchanged=True，8文件哈希匹配；formal-before.json/formal-after.json，主库SHA不变，integrity=ok、FK=[] |

隔离真实字节重放：从已有live-raw四个文件读入临时`verified-replay-gutmzviy`库，网络请求0；默认未配置日历先验证BLOCKED，再注入明确SYNTHETIC的10/23开市、24/25闭市、26开市场景。IF240/IH180/IC180/IM240，共840行；四品种均写入/读回成功，每种再次采集均DUPLICATE且版本相同，quality仍UNKNOWN、evidence_kind=synthetic、publication_time=NULL、available_at=`2026-10-26T01:30:00.000000+00:00`。中信期货(代客)IF2611读回多头8556/空头8738/成交16838；仅为隔离重放读回，不是正式库或UI验收。integrity=ok/FK=[]。详细attempt/retry/version/raw引用在offline-real-byte-replay.json。

首次重放未设工作区PYTHONPATH而误载dev旧模块，结果保留为replay-wrong-import-not-acceptance.json并作废。有效重放显式断言inspect.getfile(CffexCollector)为本任务工作区，源码SHA256=`89d776e9b5d765e23b8f9c28c4dee1bf3dabf33864749edf2b01910fee920591`；没有使用作废结果作为修复证据。

## 剩余门禁与后续

1. 独立H绑定本PR最终SHA审查日历输入责任、失败证据与事务、重复/重试及时间边界；自检不替代独立H。
2. 真实逐日CFFEX日历/开收市/假日与临时变更、来源授权及发布时间证据仍不足。提供证据并完成既有准入认证后才能另行推进正式结构化写入。本任务没有解除M3来源、研究/策略、正式业务或M4门禁。
3. 完整套件五项已知v2搬迁夹具错误须另任务修复，不改本任务无关夹具或降低断言。
4. 本轮真实行情请求、真实结构化来源验收、8524浏览器及样本外回测均未执行；离线真实字节+合成日历重放不能替代这些验证。8524服务、dev/main和正式库保持原样。

五项失败均为tests/unit/test_data_directory_relocation.py：非空v2搬迁/回滚、失败步骤[1/2/3]及并发源变更。夹具db.initialize已初始化v5，搬迁要求exact v2，失败并非本轮Collector新增。按用户明确要求不修改这些夹具，完整离线状态仍FAIL，不声称全绿。8项跳过为未启用真实AKShare1、私有CFFEX样本缺少1、Windows符号链接权限3、Linux部署检查3；没有新增跳过。G10下停止扩大修改，保留这些独立阻断。

```ini
CFFEX_CALENDAR_EVIDENCE = BLOCKED
CFFEX_AVAILABLE_AT_SAFETY = PASS
CFFEX_FAILURE_AUDIT = PASS
CFFEX_RETRY_TRACEABILITY = PASS
CFFEX_ISOLATED_STRUCTURED_WRITE = PASS
PROD_DB_MODIFIED = NO
SCHEMA_CHANGED = NO
M3_PAGE_MODIFIED = NO
AWS_MODIFIED = NO
TASK_M3_CFFEX_COLLECTOR_FIX_002 = PARTIAL
FULL_OFFLINE_TESTS = FAIL
M3_BUSINESS_GATE = BLOCKED
INDEPENDENT_H_REVIEW = PENDING
```

PASS仅限明确列出的离线安全断言及隔离合成日历写入，不表示真实日历/真实结构化采集/研究授权通过。日历材料不足和既有完整测试失败均保留。本任务不合并、不重启工作台、不向正式库写入。

## 交付登记

- 代码与测试验证提交：`532ff5e3d47b85696e0739416e77332fec501887`。本节为后续纯文档登记，src/tests未改变，无理由重跑相同完整套件。
- Draft PR：[#60](https://github.com/fengjnah/a-share-quant-v1/pull/60)，base为上述main，4个任务文件；保持Draft、未合并，等待独立H审查及用户决定。
- 有效测试绑定的文件SHA256另存tested-source-hashes.json，与提交工作区逐项一致；正式保护和离线证据均在上述本地日志根。Git不包含SQLite、行情或原始响应。
- 独立H审查应冻结PR最终head（含本节文档提交），重点检查显式日历输入责任与认证边界、失败证据/ledger引用、部分响应、AUDIT_FAILED和重试/去重行为。正式日历认证与原五项完整测试失败未解决前不得宣称整体PASS或正式业务启用。

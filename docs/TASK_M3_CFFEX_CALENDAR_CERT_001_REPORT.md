# TASK-M3-CFFEX-CALENDAR-CERT-001

## 实施前记录

- 唯一执行模型gpt-6.1-sol / high，用户本TASK明确授权替代Agnes指定；H（来源/认证/时间语义）。本会话不切模型，不调用子代理或外部模型。预算60分钟，同一问题最多两次不同诊断尝试；费用/额度未知。
- 实际main `20112111dbe287a770e5b845b3e036ba33d068ef`；GitHub API确认PR60已merged（head `d4b27f538ed5db12008abdf306918ca3f61f7865`、base `3975e2e6c35fe7c1f1bc01a0276ef65b55fbc028`），ls-remote一致。干净工作区复用，新分支codex/m3-cffex-calendar-cert-001基于该main。原TASK003报告保留于其分支提交`ebbbe37d3a7e1df9aed4d1d0d55d42d0a96901cb`，不重写或删除。
- 实际阅读：AGENTS.md、MODEL_ROUTING_POLICY.md、tasks/TASK_TEMPLATE.md、OPEN_SOURCE_RESEARCH_POLICY.md、PROJECT_STATUS.md、DECISIONS.md、reviews/TASK_022A_CFFEX_CONTRACT.md、architecture/M3_CORE_DATA_MODEL_DICTIONARY.md的B10、cffex_sessions.py、cffex_rankings_time.py和MarketInputRepository.save_session。适用G01–G12，无下级AGENTS。治理要求独立H审查，不能由本实现会话自称独立认证。
- 调研适用：只补官方规则、年度公告及指定日期临时调整证据，复用已有Calendar/Evidence/Catalog/冻结接口，不引入新依赖/数据源，不恢复14条声明。限定最多6组聚焦查询、8个资料候选（含转载线索）、4次本地元数据抓取；每次6/12秒连接/读取、2MB上限、无自动重试/TLS验证关闭/代理改动。不请求新行情。
- 范围仅2026-10-23/24/25；不认证26日或全年，不修改正式库/Schema/评分/页面/AWS。只有真实证据足够才考虑隔离认证及冻结；证据不足时不写SYNTHETIC冒充认证、不制造PASS。新增认证字段如已有API不能承载，只报告缺口。
- 验收：原始官方文件hash、日期证据链、临时调整核验覆盖、隔离冻结/读回、可用时间及未来信息边界。只运行相关测试，按用户本轮限定不重复完整M3架构/全套；未验证项分别标注，不将旧离线结果当本轮真实认证。
- 证据日志根：`F:\codex-agnes\AI-trade-local-state\m3-cffex-calendar-cert-001`。来源文档/响应/SQLite留在私有证据目录，不提交原始响应。报告、必要最小变更走人工审查，不自动合并或启动TASK003写入。

## 官方证据检索与实际响应

### 交易规则

指定URL：[中国金融期货交易所交易规则](https://www.cffex.com.cn/u/cms/www/202003/27155731wtng.pdf)。web打开超时；浏览器正常HTTPS导航报net::ERR_CONNECTION_CLOSED；本地verify=True有界请求于2026-10-24 22:22:22.832677（Asia/Shanghai）报SSLError，没有官方PDF响应正文、有效版本或SHA256。没有绕过浏览器警告、关闭TLS或改代理。

因此第十条原文及其适用版本未通过本轮原件核验，不能仅凭历史摘要/规则名称登记PASS，也没有把搜索摘要的哈希充当PDF哈希。

### 2026年度公告

准确文号与标题的有界检索得到以下**转载线索**：

- [Publicnow](https://ebs.publicnow.com/view/ADDFFE5578158AB71CC79990697606A0CA2A0458) 搜索文本标明CFFEX、中金所发〔2025〕55号及2025-12-17日期，但打开403。
- [Worldnews转载](https://article.wn.com/view/WNAT2c66b2ab7e3c91fd3a2f96558acd8190/) web超时，本地HTTPS200取得39065字节；其外链只指向`www.publicnow.com/view/ADDFFE5578158AB71CC79990697606A0CA2A0458?1765961267`，没有找到CFFEX官方原文链接。该实际外链另一次有界HTTPS取得403。
- [财联社线索](https://www.cls.cn/detail/2232197) 没有取得可核验的官方原件链接。

转载文本有助于定位公告，**不是官方原件**，不能认证其真实性、有效版本或临时调整覆盖范围。精确官方公告URL本轮尚未定位；不猜公告ID或把转载域名改写成官方URL。

| 本地取得的字节 | HTTP/大小 | SHA256 | 证据身份 |
| --- | --- | --- | --- |
| reprint-lead.html | Publicnow 403 / 5489 | 79faef8b4cff07c9fc9194aac76bccd14a9da441ffc07da32a61ca3d6c90eda8 | 访问失败页，不是公告 |
| worldnews-lead.bin | 200 / 39065 | 57e7922f91d5e91225427edf867ffc47b76b962cf22bf2cd2c95fb3f99cff562 | 转载线索，不是官方证据 |
| linked-publicnow-lead.bin | 403 / 5559 | 6d1ed296996765b275b8495e26af2fa1db240669d5af603e6d564fa9282d7bd8 | 访问失败页，不是公告 |

本地请求时间分别为2026-10-24 22:20:18、22:22:20、22:22:56（Asia/Shanghai）。以上哈希只证明本轮保存的实际字节，不提升其证据等级。实际原件规则hash=NULL、年度公告hash=NULL。

### 临时休市/调整

在官方域名检索20261023/2026年10月23日的临时/休市信息没有结果；官方[交易所通知入口](https://www.cffex.com.cn/jystz/)亦打开超时，无法核验截至本轮时点的完整公告列表、临时停市或会话调整。**未检索到公告不等于不存在公告**。临时调整核验为NOT_PROVEN_COMPLETE，不能依据普通星期五和转载假期表作已认证开市判断。

原始请求/错误/时间元数据：source-requests.json、reprint-lead-request.json、linked-publicnow-request.json；实际响应字节保存在上述本地日志根。没有新行情请求或未经审查原文提交到Git。

## 三日认证矩阵

| 交易所/日期 | 认证交易状态 | 官方规则 | 年度公告 | 临时调整核验 | 官方文件SHA256 | 证据版本/认证 |
| --- | --- | --- | --- | --- | --- | --- |
| CFFEX / 2026-10-23 | UNKNOWN | 指定规则原件未取回 | 55号仅转载线索 | NOT_PROVEN_COMPLETE | NULL | calendar-cert-001-unverified-v1 / BLOCKED |
| CFFEX / 2026-10-24 | UNKNOWN | 指定规则原件未取回 | 55号仅转载线索 | NOT_PROVEN_COMPLETE | NULL | calendar-cert-001-unverified-v1 / BLOCKED |
| CFFEX / 2026-10-25 | UNKNOWN | 指定规则原件未取回 | 55号仅转载线索 | NOT_PROVEN_COMPLETE | NULL | calendar-cert-001-unverified-v1 / BLOCKED |

规则/公告的实际获取尝试时间如上；不存在“成功取得官方原件”的时间。本轮版本是本地未认证审计版本，不是CFFEX发布版本或证书。未把周末闭市或星期五开市从公历计算升级为认证结论，不扩展全年或10/26认证。

## 现有API可表达性与隔离验证

已有B10仅保存市场/日期/开闭状态/时段/error_reason；B04保存来源、版本、实际四时点及证据引用；官方文号、原文件哈希、获取过程、临时公告范围、认证依据等可存B02不可变证据manifest，通过B04.evidence_id引用；B06保存独立质量决定，B07保存有权限签发者及受限用途/时间认证收据。**没有发现必须新增Schema字段的阻断**，不扩DDL、不新增冲突认证算法。

但这些API不能自动证明官网原件、公告检索完整性或签发者真实权限；B06的结构PASS不能替代B07授权，未配置可信issuer不能登记VERIFIED。本轮不创造trusted root、真实issuer、官方签名或PASS。当前具体缺口仍是材料和认证依据，而非表字段数量。

隔离SQLite：日志根下`unknown-calendar-<随机后缀>/isolated.sqlite3`（完整实际路径见isolated-unknown-roundtrip.json）；显式test环境/DELETE模式，网络禁止。来源provider=LOCAL_AUDIT、endpoint=audit:missing-official-certification，全部is_trading_day=NULL、opens/closes=NULL、quality=unknown。证据种类为本地observation，不是synthetic冒充官方，也不把403响应当source_payload。

| 日期 | 冻结data_version_id（仅隔离UNKNOWN审计） |
| --- | --- |
| 2026-10-23 | 8bd32bbcfb35d14431b259797a1ee3d506d212aacb19ddbff45a22bdf1c571e8 |
| 2026-10-24 | 5a8f123fc358d6c7bbeb582b27ad55aaa2e4bdbc2cafe19b79d2af02134870b4 |
| 2026-10-25 | 3f0fdbf593e0a2743c32464b07cd6888c98d6fef44ed33827d47cede77e3b5fd |

实际断言：三份非官方材料字节经Evidence API读回与SHA一致；三日UNKNOWN版本经save_session/get_version及manifest读回一致；冻结这些ID后，Calendar API对三日均抛RankingCalendarError；额外未认证日期10/26也拒绝（仅负面测试，不认证该日期）；隔离库无VERIFIED收据和CFFEX排名，integrity=ok、FK=[]。这些断言通过**不等于三日官方认证通过**。

## 测试与时间边界

命令：设置PYTHONPATH为工作区src、PYTHONDONTWRITEBYTECODE=1、PYTHONUTF8=1、PYTHONIOENCODING=utf-8；使用`F:\codex-agnes\AI-trade-dev\.venv\Scripts\python.exe -B -m pytest tests/unit/test_cffex_collector_audit.py tests/unit/test_cffex_rankings.py tests/unit/test_m3_storage_market.py tests/unit/test_cffex_high_assurance.py -q -p no:cacheprovider --junitxml=<日志根>/targeted.xml`。

实际**169 passed，29.43秒，exit0**；targeted.log/xml/exit.txt。默认离线网络阻断，临时库。覆盖现有可得时间/晚到/未知日历/未来可见性/合成场景隔离的相关回归；既有合成夹具仅作离线边界测试，未用来认证真实日期。pip check=exit0，No broken requirements found；git diff --check通过。按用户本轮只运行相关测试的要求，不重复完整M3审查或全量离线套件（不声称本轮完整全绿）。

| 用户验收项 | 本轮真实状态 |
| --- | --- |
| 官方证据hash验证 | BLOCKED，无官方原件；仅非官方/失败响应的hash读回通过 |
| 10/23开市认证 | BLOCKED |
| 10/24闭市认证 | BLOCKED |
| 10/25闭市认证 | BLOCKED |
| 未认证日期UNKNOWN | PASS，三日及未覆盖日期无自动推断 |
| 冻结/读回 | PASS，仅隔离UNKNOWN审计版本，不是认证PASS |
| available_at回归 | PASS，相关既有测试和未知日历拒绝通过；没有真实可用时间新产物 |
| 不使用未来信息 | PASS（离线断言）；本轮获取的知识不回填至获取前as_of，真实历史可用性未认证 |

未来session可以依据已提前发布且当时可见的官方安排建立版本，并不因日期未来而一概非法；但本轮无此原件。若之后收到修订/临时公告，必须追加证据与版本，不能改写旧as_of。准确排名首发时间仍UNKNOWN，publication_time可按现有契约为NULL；event_time/保守available_at仍需真实收盘及下一合格开盘证据。

## 范围限制与TASK003继续检查

即使未来三日认证完成，也不足以单独得到本次晚采集的available_at：time_fence会继续查至首个已知合格开盘，10/26仍不在本任务认证范围。不得悄悄补硬编码26日或返回10/25错误开盘；需单独补充实际所需后续会话的有证据授权范围。

本轮已继续只读检查TASK003的来源和用途：正式库source time_policy_version仍unknown、verification_receipts=0、四条raw质量UNKNOWN、market_session_versions=0、结构化报告/持仓均0。8份已保存证据的实际文件hash全部匹配。storage/display/research均BLOCKED，原始观察例外不自动扩展；官方交易规则/假期公告本身也不能证明排名数据自动采集、存储、展示或研究许可。

正式库前后SHA256均`696d18b1e49bcdb962ae5b3df819839bd6472addcff9d57d1946a1e563e5d67c`，31表行数、5迁移、integrity=ok、FK=[]完全一致，原4个BLOCKED/8证据/4UNKNOWN未改变。formal-before.json、formal-after.json及task003-source-use-followup.json为本轮证据。没有向正式库登记本轮三日UNKNOWN、写结构化持仓、创建收据、改页面或重启8524。

## 最短补证路径

1. 在能正常校验证书的环境中取得指定规则的官方原件和适用版本；取得**55号官方原件/正式发布链接**。转载只作为定位文号线索，需保留实际文件字节、原URL、获取时间和SHA；不能提交搜索文本或403页面冒充原件。本轮已记录正常HTTPS在浏览器和Requests均失败，不以关闭TLS解决。
2. 从官方通知列表或可认证官方公告档案，核对截至认证时点对10/23—25的临时调整；记录实际覆盖范围/截止时间/相关公告或无相关项的完整检索依据。搜索引擎无结果不足以填写“无调整”。
3. 在既有证据manifest+冻结版本+独立授权/签发流程中复核这三日，再按真实知识时间登记，才能把本报告BLOCKED改为PASS；不重开发Collector、不需要新增Schema。若需要本次晚到排名的实际available_at，另补本任务范围外首个后续开盘证据。
4. 继续TASK003时另核实HTTP原始载荷的来源真实性及storage/display权限材料，research保持独立；未经这些门禁不正式写入。不把本任务完成、代码合并或普通本地测试通过等同于业务准入。

## 最终状态

```ini
CFFEX_OFFICIAL_RULE_EVIDENCE = BLOCKED
CFFEX_2026_HOLIDAY_NOTICE = BLOCKED
CFFEX_20261023_TRADING_DAY = BLOCKED
CFFEX_20261024_NONTRADING_DAY = BLOCKED
CFFEX_20261025_NONTRADING_DAY = BLOCKED
CFFEX_CALENDAR_EVIDENCE = BLOCKED
CFFEX_AVAILABLE_AT_SAFETY = PASS
PROD_DB_MODIFIED = NO
SCHEMA_CHANGED = NO
AWS_MODIFIED = NO
```

完成标准尚未达到：没有真实官方材料形成三日认证PASS。本轮交付为具体阻断和可复核证据，不宣称已解除日历或TASK003门禁。仅报告改动，生产代码与测试期望不变；提交报告供人工处理，不自动合并。

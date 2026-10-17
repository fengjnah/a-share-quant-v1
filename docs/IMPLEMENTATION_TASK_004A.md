# TASK-004A 第一轮：来源研究、可用性探测与验收计划

检查日期：2026-10-17，Asia/Shanghai。**本报告不是 TASK-004A 完整验收通过报告。** 本轮按要求先研究来源并验证有限可用性，不开发采集适配器、不修改数据库设计，不进行真实数据入库。证券主数据请求被 TLS 阻断；新浪日历仅通过一次 SDK 响应检查。后续采集和 SQLite 集成测试尚未执行。

## 1. Git、工作区与前置契约

GitHub 实查：main=`d09a259ec34fec8e587baa54b63706ba96c3b9af`；[PR #10](https://github.com/fengjnah/a-share-quant-v1/pull/10) 为 open、未合并，base=main，head=`codex/task-004-master-calendar-resumed@bb596a9bcf9d34c2ae29b43334873cc8e08c3313`，17 个文件。main 不能被当作已有 Schema v2。

复用已附加且干净的独立工作树，从 #10 的实际 head 创建 **codex/task-004a-source-review**。本轮 PR 应以 #10 的 head 分支为 base，明确堆叠依赖；#10 合并后先核对文件树/提交关系，再决定是否调整 base。本任务不合并 #10 或修改 main。

原 `F:\codex-agnes\AI-trade` 保留在 `codex/task-004-master-calendar@cd1b2b1`，16 个已有暂存/未暂存修改、检查点和文件均不清理；以状态及文件 SHA-256 核对。研究输出放在独立工作树忽略目录 `artifacts/task-004a/`。

已逐项读取 PROJECT_STATUS、IMPLEMENTATION_TASK_004、DATA_CONTRACT、INTERFACE_CONTRACT、ACCEPTANCE_TESTS，并复核实际实现：

| 检查对象 | 已有契约及本轮约束 |
| --- | --- |
| `reference_data/models.py`、`validation.py` | 稳定实体 ID 不等于证券代码；仅 A_SHARE，SH/SZ/BJ 后缀一致；名称/上市有效期左闭右开；ST 未知不能推断正常 |
| `security_master/repository.py` | `write_many/get/resolve`；先选可见版本再按业务日期查名称；不自动倒填当前名称 |
| `trading_calendar/repository.py` | `get_day/trading_days/previous_known_trading_day`；休市、缺失、源错误分开；最近已知日必须有搜索下界 |
| `storage/reference_schema.py`、`schema.py` | v2 追加；证券版本 `(instrument_id, record_version)`、日历版本 `(exchange, session_date, record_version)`；单根单后继、外键、不可覆盖 |
| `storage/db.py`、`reference_data/repository_support.py` | 复用既有连接/事务/迁移；坏行、重复及生成器失败须整批回滚 |
| 时间语义 | event/available/observed/ingested 必填；所有模式同时过滤 available/ingested；无法确认的事件/发布时间不伪造 |
| P0 验收边界 | AT-007、011、012 与本任务相关；已有离线验证不等于完整 ST/股票池、真实来源或历史质量验收 |

## 2. 运行环境及访问边界

| 项目 | 实查结果 |
| --- | --- |
| Python | `F:\codex-agnes\AI-trade\.venv\Scripts\python.exe`，3.12.14，Windows |
| OpenSSL | 3.5.8 |
| AKShare / pandas | **1.19.1** / 3.0.6；没有重复安装 |
| requests / urllib3 / certifi | 2.34.2 / 2.8.0 / 2026.7.22 |
| 日历 JS 运行库 / pytest | mini-racer 0.14.1（模块名 py_mini_racer）/ 8.4.2 |
| 请求路由 | requests 实际选择 HTTP 代理 127.0.0.1:7890；仅记录主机/端口及凭证存在与否，不保存凭证 |
| 安全边界 | 不改系统代理/NO_PROXY，不设置 verify=False，不重试，不切换直连，不连接交易账户 |
| 数据库 | 探测不实例化或打开 SQLite；原默认 local.sqlite3 仍不存在，不初始化生产库 |

本轮 Windows 只发起两个来源探测 GET，各一次；连接/读取超时 5/15 秒，单响应最多 8 MiB，禁止重定向和额外目标。使用独立 Python 进程调用 SDK，临时包装 Session.send 以记录请求/限制范围，进程结束恢复；不改变 SDK 的字段解析或业务规则。另通过文档浏览服务读取官方网页，其成功不等于 Windows SDK 请求成功。

## 3. 候选证券主数据来源

以下字段与能力来自官方文档和已安装 1.19.1 源码，除特别标明外**未实测**。样例记录不能当成实际返回。

| 候选与参数 | 数据/日期字段 | 覆盖、更新与历史限制 | 本轮结论 |
| --- | --- | --- | --- |
| `stock_info_sh_name_code(symbol="主板A股")` | 六列：证券代码、证券简称、证券全称、公司简称、公司全称、上市日期；最后一列转为 Python date，解析失败可能为 NaT | 当前指定板块列表；非完整沪市/全 A；无历史 as_of、名称生效区间、ST 区间、发布时点；lru_cache 无 TTL，无已验证更新 SLA | 优先候选；实际调用遭 TLS EOF，无 HTTP 响应，字段映射未完成真实验证 |
| `stock_info_sz_name_code(symbol="A股列表")` | A股代码/简称/上市日期、板块、股本、行业；Excel 日期需明确解析为 YYYY-MM-DD | 当前深市列表，非历史快照；返回少于等于 10 行时 SDK 不走同一规范列分支，需检测字段变化；缓存无 TTL | 备用；未发 Windows 数据请求，不能声称可用 |
| `stock_info_bj_name_code()` | 证券代码/简称、上市日期、报告日期、股本等；日期转 date | 分页、多次 POST，按列位置重命名；报告日期不等于发布/观察时间；没有可靠历史身份链 | 本轮不调用，避免扩大请求；BJ 覆盖未验收 |
| `stock_info_a_code_name()` | 只输出 code/name | 聚合多个板块/交易所，丢失上市日期，隐含多请求；无法提供稳定实体 ID 或历史证据 | 不选作最小验收入口 |
| `stock_info_sz_delist(symbol="终止上市公司")` | 证券代码、证券简称、上市日期、终止上市日期；日期转 date | 可提供退市事实候选，但没有历史版本首次发布时间/完整性保证；不能从名单缺失反推仍上市 | 文档/源码已审查，未联网验收 |
| `stock_info_sh_delist(symbol="全部")` | 公司代码、公司简称、上市日期、暂停上市日期 | 源码把 **DELIST_DATE** 映射为“暂停上市日期”，文档/名称存在歧义；固定 pageSize=500，完整分页未验证 | 在确认含义及截断风险前，不直接映射 delisting_date |
| `stock_info_sz_change_name(symbol="简称变更")` | 变更日期、代码及变更前后名称（实际列仍需验收） | 源码有历史变更日期，但不证明首次发布时点、所有实体或所有历史记录齐全；不能据此重建 ST 历史 | 仅后续研究候选 |

所有候选的真实历史首次可得时间均**尚无可靠记录级证据**。当前列表的上市日期是业务事实，不是该响应的历史可得时间；当前名称不得回填到上市日。公开接口不等于有永久实体标识，代码变更/复用仍需人工核对实体登记证据。

拟议映射（未实施）：

| 来源字段 | 领域字段/处理 |
| --- | --- |
| SSE 证券代码 / SZ A股代码 | 校验六位 ASCII 数字，保留前导零，再加显式 `.SH` / `.SZ`；不凭代码前缀认定类型 |
| 请求的交易所与板块类别 | exchange 与 A_SHARE 的依据；若源集合混有 B/CDR 等，停止，不自动归类 |
| 当前证券简称 | 只作为观察到的当前名称；真实 effective_from 未知时，不直接生成历史 SecurityPeriod |
| 上市日期 | 校验日期后映射 listing_date；NaT/缺失拒绝，不能以今天补齐 |
| 无退市/风险字段 | delisting_date 未记录不等于永不退市；risk_status 继续 None，不从 ST 字样推导区间 |
| 无稳定 ID 字段 | 使用独立登记并核对的上市实体 ID；禁止直接以 symbol 作为永久 ID |

## 4. 候选日历来源与独立核对

| 来源 | 接口/字段与日期格式 | 覆盖、更新时间、时间证据 | 采用建议 |
| --- | --- | --- | --- |
| 新浪，经 `tool_trade_date_hist_sina()` | 无参数；trade_date，Python date；源为 `klc_td_sh.txt`，SDK JS 解码并手工补 1992-05-04 | 本次 SDK 返回范围见第 5 节；只有开市日期，没有 exchange、明确休市行、来源错误行、逐版本发布证据或更新 SLA；文档文字截至 2024，示例截至 2025，与本次 2026 终点不同 | 仅作为待核实的开市日期候选；不能把缺项补 false，也不直接复制为 SZ/BJ |
| 上交所年度/专项休市公告 | 网页发布日期、交易所、明确休市区间、恢复开市日、特别周末休市；中文年月日需严格解析 | [2026 专项公告](https://www.sse.com.cn/disclosure/announcement/general/c/c_20260915_10832273.shtml)标示发布日期 2026-09-17；只有日精度，不能虚构精确发布时刻；[年度通知](https://www.sse.com.cn/disclosure/announcement/general/c/c_20251222_10802507.shtml)可作计划对照，仍需查后续修订 | 用显式事实核对有限日期，不生成未明确覆盖的日期；网页可读不等于自动解析/入库已验收 |
| 深交所专项公告 | [官方投资者站通知](https://investor.szse.cn/disclosure/notice/general/t20260917_622911.html)，日期、休市区间与恢复日 | 搜索索引可见 2026-09-17 摘要，正文浏览抓取失败；不将摘要当成本机抓取或完整正文证据 | 独立来源待验证；不能直接借用 SH 日历 |

有限对照：上交所专项公告明确 2026-10-01 休市、10-08 恢复开市、10-10 为周末休市。新浪结果包含 10-08，不包含 10-01 和 10-10，**只能说与该公告的三个检查点没有发现矛盾**；其中两个“不包含”本身不是 closed 证据。10-14/15 在新浪集合中，尚无本轮独立逐日实际交易证明。返回未来日期是日历计划，不证明未来实际成交或没有临时休市。

## 5. 本轮真实请求记录

| 项目 | 主数据探测 | 日历探测 |
| --- | --- | --- |
| UTC 时间 | 14:38:08.705598–14:38:09.313880 | 14:38:17.660411–14:38:20.113436 |
| SDK 调用 | stock_info_sh_name_code，主板A股 | tool_trade_date_hist_sina，无参数 |
| GET | query.sse.com.cn/sseQuery/commonQuery.do | finance.sina.com.cn/realstock/company/klc_td_sh.txt |
| 请求参数 | STOCK_TYPE=1；sqlId=COMMON_SSE_CP_GPJCTPZ_GPLB_GP_L；COMPANY_STATUS=2,4,5,7,8；STOCK_CODE 空；isPagination=true；pageHelp.cacheSize/beginPage/pageNo/endPage=1；pageSize=10000；REG_PROVINCE/CSRC_CODE 空；type=inParams | 无查询参数 |
| 实际 HTTP 尝试数 | 1 | 1 |
| HTTP 结果 | 无 HTTP 响应；状态未知 | 200；解压后字节数 508 |
| SDK 返回行数 | **未知（null），不是 0** | **8,797**；一列 trade_date；重复日期 0 |
| 日期范围 | 未获取 | **1990-12-19 至 2026-12-31**，包含 SDK 手工补日；不能宣称期间无缺漏 |
| 错误/状态 | tls_error；SSLError → MaxRetryError → SSLError；UNEXPECTED_EOF_WHILE_READING | sdk_response_success_only；不是完整数据验收通过 |
| SQLite | 未打开；插入 0；读回/版本查询未执行 | 未打开；插入 0；读回/版本查询未执行 |

日历响应 SHA-256：`d5112e08726ecc435092fb63547a34fc514b071b1a4a84f9e2c29fb9023726a9`。这是本次解压 HTTP 字节摘要；SDK 手工修补发生在摘要之后，应单独披露，不能称为未经变换的原始日期表。未落盘完整原始响应。

TLS 失败发生在现有代理路由上，但根因尚未定位；不能仅据此断言是代理、证书或上游单方故障。没有观察到 HTTP 429、403、空表或字段漂移，不能替代真实错误分类。也没有通过额外直连/重复请求来推断结论。

## 6. 时间契约与进入下一阶段的门槛

1. **主数据可访问性阻断**：须在保留 TLS 验证和授权网络路径下，获得一次成功且字段合格的主数据响应。最小下一步是对 query.sse.com.cn 做独立有界 TLS/代理诊断；不重新下载行情、不修改永久代理、不自动切换源掩盖故障。备用 SZ 也必须实际验收后才能替代。
2. **记录级时间/名称有效期不足**：当前列表没有名称 effective_from 或整条版本的发布时间。不能把上市日期当成当前名称生效日，也不能把下载时刻冒充历史发布事件。最小方案优先补充相应公告；若只验收“当前观察快照”，需先单独记录并评审 observation-event 的含义、日期粒度及使用限制，再映射现有 Provenance。本轮不修改强制字段或偷偷采用该假设。
3. **日历发布时刻不足**：新浪无版本发布证据；不能把各 session_date 收盘当 event_time，因为本次含未来日期。官方公告有日精度发布时间，也不能伪装成精确时刻。优先获取明确时区/精度的版本证据；如采用保守日期上界，须先记录规则、误差与证据，不能直接当真实首发时刻。
4. **保守系统可见性**：后续即使拿到历史公告，available_at 至少取本次实际获取并校验的时刻（如许可限制更晚，取更晚值），observed_at 记录响应完成，ingested_at 记录实际校验入库，三者必须可追踪；as_of 同时限制 available_at/ingested_at，不让今天下载的数据在过去可见。
5. **来源范围**：先只验 SH 主板限定实体及显式公告检查日；SZ/BJ、全部历史日历、退市/改名/ST 分别列为未覆盖。软件可用不等于来源商业许可或历史质量通过。

这些是进入真实 SQLite 验收前的条件，不是修改 Schema v2 的理由。缺少证据时保留研究摘要，暂不构造强制元数据齐全但事实错误的领域对象。

## 7. 后续验收计划（尚未执行）

| 步骤 | 范围与断言 | 成功门槛 |
| --- | --- | --- |
| 显式开启与错误分类 | 新手工测试使用既有 manual_integration 标记及 --run-akshare-integration，并要求专用来源参数；默认套件仍阻断 socket；每源最多一次 HTTP 请求、固定超时 | 未开启时不联网；empty / TLS / connection / HTTP限流 / schema / validation / source_error / success 分开；空表不自动视为成功 |
| 主数据字段验收 | 来源可访问后选择 600000.SH，一条经登记的内部 ID；对照证券代码、交易所、类型、名称、上市日和证据；不使用文档样例冒充返回 | 原始到领域映射逐字段一致，日期/缺失检查通过，事件和有效期依据齐全 |
| 日历验收 | SH：2026-10-01=false（专项公告）、10-08=true（公告及新浪）、10-10=false（公告）；10-14/15 只作新浪候选；另选一个故意不导入的日期验证 missing | 不用 weekday 或补集生成休市；不将新浪的缺项、网络错误或 SZ/BJ 空覆盖记为 closed |
| 临时 SQLite | TemporaryDirectory / pytest tmp_path；显式 DatabaseConfig(path, "test")，复用 initialize 和仓储，不读取 QUANT_DB_PATH | 初始化/重复初始化 v2，实际 SELECT/get/resolve/get_day 与域对象一致；PRAGMA foreign_key_check/integrity_check 通过 |
| 重复与版本 | 相同版本再次写入须明确 DuplicateRecordError，不改变旧行；新的真实观察仅在有新证据时追加，supersedes/reason 明确；同一 payload 另一个采集批次只能记重复观察/去重说明 | 旧时点返回旧版本，新时点返回新版本；真实源未发生修订就标记“真实修订未验证”，不人为改名伪造 |
| 原子回滚 | 将实际样本与明确标记的无效测试对象放同一测试批次，或注入生成器错误 | 版本、实体锚点及 ingestion_runs 均不残留；这是故障注入验证，不能计为真实坏数据发现 |
| as_of | 对 observed/available/ingested 前后及上海时区边界读回；旧历史 as_of 必须不可见 | source/event/available/observed/ingested、版本/血缘与证据摘要一致；不回填首发或历史名称 |
| 证据与失败收尾 | 只保存允许的请求参数、摘要、状态码、行数、覆盖/缺口、质量统计及错误码；HTTP 时间与 DB 事务分开记状态 | DB 已提交而摘要写失败必须明确标记 committed/evidence_failed，不报告成全失败或全成功；不提交数据、代理凭据或原始响应 |

网络故障与字段变化的回归用离线夹具/注入覆盖，不能为了“真实故障样本”发送恶意或大量额外请求。正式集成测试数量、文件和结果待上述门槛满足后再提交；本轮不增加虚假的 passed/skipped 用例来代表真实验收。

## 8. 实际测试、产物与未执行项

本轮重新实际执行，非沿用上轮结果：

```text
python -m pytest -q
327 passed, 1 skipped in 11.00s
SKIPPED tests/manual/test_akshare_daily_live.py:81
  live AKShare test requires --run-akshare-integration

python -m pip check
No broken requirements found.
```

| 验收层次 | 本轮结果 |
| --- | --- |
| 原有模型/存储离线回归 | 通过；默认网络阻断未改；无新增测试代码 |
| 真实来源可访问性 | 主数据：失败，TLS；新浪日历：一次成功响应 |
| 真实字段/覆盖质量 | 日历仅列、范围、唯一性及有限公告对照；主数据未知；均不作完整历史质量保证 |
| 真实 SQLite 写入/读回/版本/回滚 | **未执行**；两源插入行数均为 0 |
| 完整 TASK-004A 验收 | **未通过/未完成**；不能把接口成功或离线通过替代 |

本机忽略目录保存 environment.json、master-probe.json、calendar-probe.json、探测脚本、offline-tests.log、dependency-check.log 和工作区保护快照。日志只保留允许的诊断统计，不包含未经审查的完整响应或任何凭证。当前提交仅新增本报告；无业务/Schema/依赖/网络阻断配置变更，无生产库操作。

## 9. 复现有限可用性检查

在本分支的独立工作树运行离线回归：

```powershell
$py = "F:\codex-agnes\AI-trade\.venv\Scripts\python.exe"
& $py -m pytest -q
& $py -m pip check
git diff --check
```

本机完整有界探测脚本位于忽略产物中（不在干净克隆里）：

```powershell
& $py artifacts/task-004a/probe_reference_sources.py --enable-reference-source-probe --source master
& $py artifacts/task-004a/probe_reference_sources.py --enable-reference-source-probe --source calendar
```

以下独立片段供干净克隆复现同一 SDK 的有限连通性检查；需已安装声明的 `.[akshare]`（本机已安装，无需重装），最后一个参数选择 master 或 calendar，每次只执行一种。不写 SQLite、不输出完整表或原始异常文本；真实失败退出码 1。它不是完整验收测试，不应放入默认离线 CI：

```powershell
@'
import hashlib, json, sys
from datetime import datetime, timezone
from urllib.parse import urlsplit
import requests

if len(sys.argv) != 3 or sys.argv[1] != "--enable-reference-source-probe" or sys.argv[2] not in ("master", "calendar"):
    raise SystemExit("explicit source probe flag and source required")
import importlib.metadata as m
if m.version("akshare") != "1.19.1":
    raise SystemExit("requires akshare==1.19.1")
import akshare as ak
kind = sys.argv[2]
host, path = (("query.sse.com.cn", "/sseQuery/commonQuery.do") if kind == "master" else
              ("finance.sina.com.cn", "/realstock/company/klc_td_sh.txt"))
audit = {"source": kind, "started_at": datetime.now(timezone.utc).isoformat(), "attempts": 0}
original = requests.Session.send
def bounded(session, request, **kwargs):
    url = urlsplit(request.url)
    if (url.scheme, url.hostname, url.path, request.method) != ("https", host, path, "GET") or audit["attempts"]:
        raise RuntimeError("outside one-request scope")
    if kwargs.get("verify", True) is False:
        raise RuntimeError("TLS verification required")
    audit["attempts"] += 1
    kwargs.update(timeout=(5, 15), allow_redirects=False, stream=True)
    response = original(session, request, **kwargs)
    try:
        audit["http_status"] = response.status_code
        if not 200 <= response.status_code < 300:
            raise requests.HTTPError("non-success HTTP status")
        parts, size = [], 0
        for part in response.iter_content(65536):
            size += len(part)
            if size > 8 * 1024 * 1024:
                raise RuntimeError("response limit")
            parts.append(part)
        response._content = b"".join(parts)
        response._content_consumed = True
        audit["sha256"] = hashlib.sha256(response._content).hexdigest()
        return response
    finally:
        response.close()
requests.Session.send = bounded
ok = False
try:
    frame = ak.stock_info_sh_name_code(symbol="主板A股") if kind == "master" else ak.tool_trade_date_hist_sina()
    audit.update(rows=len(frame), columns=list(frame.columns))
    if kind == "calendar" and "trade_date" in frame and not frame.empty:
        audit.update(date_min=str(frame.trade_date.min()), date_max=str(frame.trade_date.max()))
    ok = not frame.empty
    audit["status"] = "response_only" if ok else "empty_unverified"
except Exception as exc:
    audit.update(status="failure", error_type=type(exc).__name__)
finally:
    requests.Session.send = original
print(json.dumps(audit, ensure_ascii=True))
raise SystemExit(0 if ok else 1)
'@ | & $py - --enable-reference-source-probe calendar
```

该片段未在本轮重新联网执行，避免第三次来源请求；本轮实际记录来自先前两个受限进程。上面的摘要成功状态只代表非空 SDK 响应，不能据此宣布字段/入库或历史质量合格。

## 10. 证据与尚未确认事项

- [AKShare 官方股票文档](https://akshare.akfamily.xyz/data/stock/stock.html)：列表、退市及名称变更参数与字段；不是实际返回证据。
- [AKShare 官方日历文档](https://akshare.akfamily.xyz/data/tool/tool.html)：单列开市日，覆盖文字与示例终点有差异。
- [stock_info.py 固定参考源码](https://github.com/akfamily/akshare/blob/fe10d1decb705e5f43cc8ca3339ca39e580fb8f4/akshare/stock/stock_info.py)：已安装版本实际检查函数起始行 20/122/185/286/355/384/440，含缓存、字段重命名、退市歧义和聚合行为。安装文件 SHA-256=`d3288903d1e8ce7796e051bfbe651cb15aad0b29d4043277b04984f3cec72892`；固定源码链接用于对照，不将格式/行号视为安装包字节相同的证明。
- [trade_date_hist.py 固定参考源码](https://github.com/akfamily/akshare/blob/fe10d1decb705e5f43cc8ca3339ca39e580fb8f4/akshare/tool/trade_date_hist.py)：安装版本第 19 行函数及手工补日；安装文件 SHA-256=`a3dd36d501dd38456e723ca7165d232c48b53c4325371bc32a732c152c117ea8`。
- [AKShare MIT 许可证](https://github.com/akfamily/akshare/blob/main/LICENSE)针对软件；不授予上游数据使用权。[上交所法律声明](https://www.sse.com.cn/home/legal/)区分非商业浏览/下载及向他人出售牟利的书面许可要求，且不保证资料完整及时。本轮不对商业授权作已获批结论；SZ/BJ/新浪数据条款、再分发及长期批量访问权限仍待逐源确认。

后续优先级：先诊断主数据 TLS 并取得一次合格响应；补齐记录级事件/名称有效期证据与日历发布精度规则；在条件满足后单独实现显式手工测试及真实临时 SQLite 验收。历史 ST、全交易所完整日历、所有退市/改名、临时休市和完整历史首次可得性继续列为未验收，不通过填充合成数据消除缺口。

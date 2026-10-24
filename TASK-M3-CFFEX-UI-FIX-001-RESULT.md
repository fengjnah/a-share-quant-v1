# TASK-M3-CFFEX-UI-FIX-001-RESULT（正式数据库版）

日期：2026-10-24；执行：OpenAI `gpt-6.1-sol / high`，用户明确授权覆盖初稿“Agnes”。实施自检，不是独立 H 审查。

```ini
CFFEX_ROUTE = PASS
CFFEX_PROD_COLLECTOR = BLOCKED
CFFEX_PROD_DB_READBACK = BLOCKED
CFFEX_8524_UI = BLOCKED
SCHEMA_CHANGED = NO
AWS_MODIFIED = NO
M3_CFFEX_PROD_E2E = PARTIAL
```

**页面路由与正式空库 UI 已修复；真实原始观察已获例外保存，结构化持仓和真实数值页面 E2E 仍未完成。** 不能把原始证据的840行解析结果称为840条正式持仓版本。

## 1. 基线、授权与合并边界

- 起点 dev/main、远端 main、PR58 merge 均为 `8450531b9ccba497b0a5b7b4a4b15604c2c5cf79`；PR57 head `40ff4ffc1bb4f102b1bc0e3f399c2a11ae2ed034`、merge `0dc0b152fedd9d8ec9b15893dfd16468e25969e2`。本次实际核实。
- 修复提交：`35e0c5f55936c27b92a8201bf4473d400808ad29`；旧调用方兼容性修正：`031824f6204385a10cd86fc59452bed2de483677`。
- 执行中 main 又合并 PR29/52 为 `d10b281b84dd6950188aa010f3b9e6977f25d1bd`；安全快进失败时停止，随后在任务分支整合为 `a57e6f3a9eb6a77b98d49382ace89a1c19a3d472`。页面源码/回归文件与031824f相同；主线新增 workbench_store 与部署测试单独纳入最终完整套件。无 AWS 运行操作。
- 修复 worktree：`C:\Users\iyoyi\.codex\worktrees\m3-cffex-ui-fix-001\AI-trade`，分支 `codex/m3-cffex-ui-fix-001`；运行目录按用户要求是 `F:\codex-agnes\AI-trade-dev` / `main`，不运行测试库。
- [PR #59](https://github.com/fengjnah/a-share-quant-v1/pull/59) 最初为 Draft。用户后来明确要求页面修复合并应用 main；这覆盖本 TASK 原不自动合并指令。用户另明确授权仅保存本日四品种原始观察的正式入库例外，认证/研究/策略仍 BLOCKED。未把合并授权写成独立 H 通过；其他门禁不变。
- 已读规则、G01–G12适用性、预算、范围与独立复核计划见[任务单](docs/tasks/TASK-M3-CFFEX-UI-FIX-001.md)。未使用子代理或其他模型，费用未知。

## 2. 页面最小修复

| 实际问题 | 修改 |
|---|---|
| `market_analysis_page.py` 把 cffex 条件放在 fear_greed/price_proxy 分支，且 `_values` 对 BLOCKED 提前返回 | 将原始持仓模块放进父 render 的 CFFEX 段，保留八项核心诊断、其阻断状态和其他七模块；原始事实不升级研究用途 |
| CFFEX page 仅选择测试库变量 | 接收父工作台 db，构造 read_only=True、require_existing=True 的真实 SQLite mode=ro 连接；正式路径优先且不读取测试变量；证据根沿用工作台 sqlite/evidence，不创建/迁移库 |
| 空报告和异常没有清楚区分 | 无结构化报告用明确空提示，不等于休市/零；证据缺失/读取错误仍报错；旧路径型假连接对象拒绝并显示错误，不崩溃、不回退、不建空库 |
| 质量和证据种类未展示 | 只读返回原版本 quality_status/evidence_kind，显示来源、实际交易日、采集/可用时间、哈希；明确 storage accepted 不代表来源/发布时间/会员scope认证 |

只改三个页面/只读查询文件。Schema v5/checksum、H1/M1、collector、日历、核心评分/策略均未修改。原有测试未修改、跳过或弱化；新增 `test_cffex_workbench_route.py`。参数 db=None 的独立测试入口仍须明确配置，不是正式页面的默认回退。

## 3. 正式采集准备与阻断

1. **独立审查/业务门禁**：PR57 报告仍 PENDING_INDEPENDENT_REVIEW；精确 review TASK 的 GitHub issue 搜索没有取得解除证据。用户原始观察例外不等于研究、策略或真实来源认证。
2. **前置失败审计缺口**：隔离调用真实 collector 的 fetch/parse 错误分支，均返回 FAILED，但 ingestion_attempts/evidence_objects/report/run 均0；save_cffex 的 M1修复覆盖不到它们。探针只用离线无效夹具，无正式数据。没有为通过验收修改 collector。
3. **日历错误**：`src/ai_trade/market_data/cffex_sessions.py` 明确将2026-10-24/25周末列为开市，也有其他不可信声明。collector 会写这些合成声明并据此计算 available_at；不得执行这条正式结构化写入路径，也不能用工作日推算法或修改状态字段绕过。
4. 正式库当前 v5、31张用户表，旧七表保留。首次检查 CFFEX结构化记录0行；integrity_check=ok、foreign_key_check为空。已做 SQLite Backup API 一致性备份并验证。原始写入前另做备份，BEGIN IMMEDIATE 随即回滚确认当时没有其他活动写事务；这不是承诺未来永无其他写者。

因此真实原始观察可以按例外保存；**现有 collector 不具备本次正式结构化版本验收条件**。修复日历证据/时点及前置审计应另立有界任务、独立 H 复核，不能在本 UI 修复中隐改。

## 4. 新真实请求与正式原始观察

明确启用：只请求2026-10-23的IF/IH/IC/IM；每品种HTTPS一次、失败后HTTP一次；无自动重试、无重定向，连接/读取各5秒、每响应最多2MB。复用既有 CffexRankingsClient 的有界取回与 parse；不关闭 TLS 校验、不改代理。**HTTP 没有 HTTPS 的传输认证**；SHA256只验证保存/读回一致，不能证明传输未被中间人修改。

URL模板：`{https|http}://www.cffex.com.cn/sj/ccpm/202610/23/{IF|IH|IC|IM}_1.csv`。实际每源HTTPS失败、HTTP200；响应大小/原始哈希/开始结束时间/传输错误类别保存于 `live-capture.json`，原始载荷仅本机。

| 品种 | HTTP原始响应可解析行数 | 原始证据SHA256 |
|---|---:|---|
| IF | 240 | `1b8fcd4cdd27e958fe26f0eb0b1b2d207d141e6bccbefc11a367911f281d4511` |
| IH | 180 | `18a4d2df79cbe19ae3ed3acf6f589e7eb65ac3d3389d334c7a3d761303eb60a9` |
| IC | 180 | `fd8dff7f7469311e7c4433c7076aafb515dc024abaeefe188c41f9eb494f1a92` |
| IM | 240 | `2186ddbd3731485849a4aa9026224ff09dd36074f6a485948523e4c606fba04f` |

使用 dev/main 的既有来源登记及 Evidence/Catalog API（非直接 SQL 插入），仅存储：1条来源、4份原始响应+4份传输证据、4条BLOCKED尝试、4条UNKNOWN质量决定。原始证据直接关联该日期/品种尝试；实际请求与响应时间、来源/协议/哈希保留。所有认证保持未知；没有写日历、typed版本、快照或评分。一次性受控执行器仅本地留存，不成为新生产管线。

**实际正式表数：** evidence_objects=8，ingestion_attempts=4，quality_assessments=4；market_session_versions=0，cffex_report_versions=0，cffex_rank_rows=0，analysis_runs=0。原始层重复写入同一证据/同一尝试ID不增加行，已验证；不能由此宣称完整 collector 跨批次幂等已通过。

正式库证据读回后重新用既有 parser 解析，IF2611 的中信期货(代客)：成交量16838、变化+4752、排名1；多头8556、变化-428、排名2；空头8738、变化+212、排名1；多空差-182。数值不是硬编码或测试库复制，**但仅来自正式库索引的原始响应，不是结构化持仓表读回**。

## 5. 数据安全和备份

- 正式库：`F:\codex-agnes\AI-trade-data\sqlite\workbench.sqlite3`。
- 写前SHA256：`2d38f34d3a6a26026d576e24896f117ef68e017deae286a6293b5faba4ac333f`；已授权原始观察写后：`696d18b1e49bcdb962ae5b3df819839bd6472addcff9d57d1946a1e563e5d67c`。
- 备份：Git外任务证据目录的 `formal-before-v5.sqlite3` 和 `formal-before-raw-add.sqlite3`；后者SHA256 `1dc19c8e362816dcdd7b2f6ea24ba7b5bb5b441fd4e74d0df3244e5a8492a26a`；Backup API、完整性/FK验证通过，不覆盖正式库，无恢复执行。
- 写后再次比较 sqlite_master，Schema完全相同；原七表全行内容与备份相同；五条迁移记录/checksum不变；integrity/FK通过。仅原始层获授权新增，未删除或覆盖旧数据。
- 正式库和原始证据文件在Git外。没有提交SQLite、CSV、凭据或原始响应。

## 6. 测试与实际页面

运行环境 Python3.12.14 / Streamlit1.66.0 / pandas3.0.6 / pytest8.4.2 / jsonschema4.26.0；每次显式绑定工作树 PYTHONPATH、PYTHONDONTWRITEBYTECODE=1、PYTHONUTF8=1、PYTHONIOENCODING=utf-8。

| 执行 | 实际结果 |
|---|---|
| 原代码首轮新增回归 | 6失败；5项先被Windows asyncio本地自管道禁网干扰，质量字段缺失反例有效；日志before保存 |
| 只允许测试loopback，外网仍禁，生产代码未改 | 6失败，5.24秒；真实复现路由/正式参数/质量字段缺口，before-local-ipc |
| 首轮相关测试 | 21通过/1跳过，7.14秒 |
| 相关页面+H1/M1回归 | 89通过/1跳过，40.97秒 |
| 首轮完整套件35e0c5f | 3151通过/6失败/5跳过，356.03秒；新增旧调用方TypeError已定位修复 |
| 新兼容用例+原8种页面状态 | 9通过，10.90秒，既有测试断言未改 |
| 完整套件031824f | 3153通过/5失败/5跳过，376.31秒；仅原有五项精确v2搬迁夹具失败 |
| 整合新main a57e6f3 完整套件 | **3158通过/5失败/8跳过，exit1，381.29秒**；失败集合与031824f一致，仅原有五项v2搬迁夹具 |
| pip check / diff /受保护路径 | PASS；Schema/H1/M1/collector/calendar/评分无本任务改动 |

源码修改与测试提交可从 PR59 追溯；最终文档/截图提交不更改 src/tests，未冒称在新文档 SHA 重跑全部。跳过分别记录真实AKShare未启用、未提交真实CFFEX样本不在新工作树、Windows symlink权限；新主线Linux部署测试在Windows按既有标记跳过。

8524仅保留一个服务，运行 `F:\codex-agnes\AI-trade-dev\src\ai_trade\demo_app.py` / main。按用户授权快进已测代码、仅重启本项目进程；`AI_TRADE_DATA_ROOT=F:\codex-agnes\AI-trade-data`、strict/read_only=1，未设置测试库变量。实际浏览器已显示 CFFEX 模块、正式库路径、IF、交易日2026-10-23和“No stored CFFEX report”提示；空正式版本 UI=PASS，真实数值展示=BLOCKED。未创建第二页面服务。

页面截图：[main正式库CFFEX模块](docs/evidence/TASK-M3-CFFEX-UI-FIX-001/main-cffex-empty.png)。截图记录的是结构化报告缺失，不是840行真实数值验收。

## 7. 证据、剩余工作与结论

本地完整证据：`F:\codex-agnes\AI-trade-local-state\m3-cffex-ui-fix-001\`，包括所有 pytest log/XML、formal-and-collector-preflight.json、live-capture.json、raw-store-result.json、formal-raw-readback.json、formal-after-raw-and-runtime.json、8524前后PID/代码SHA/日志、浏览器AX日志和截图。最终GitHub merge/main SHA、进程与最终测试计数保存在运行交付快照，不冒称main源码包含后来的运行事实。

下一步必须修正并认证CFFEX逐日日历/可用时间证据、补齐collector前置失败持久审计；再在独立H确认及新的有界入库任务中生成正式持仓版本。之后才能在8524核对IF2611的正式持仓表读回和会员数值。不得把本原始观察例外、页面合并或HTTP200当作研究/策略/实盘授权。AWS未操作，M3/M4其他门禁保留。

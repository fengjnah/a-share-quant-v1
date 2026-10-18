# TASK-022A：CFFEX 适配器交付与验收

更新：2026-10-18。本文是 TASK-022A / TASK-022A-H 的权威交付入口。PR #23 收敛原 #22；代码合并不代表生产准入。保留既有独立审查，不重新开展整轮审查。

## 基线与交付

- main：`2a5332448b32083ddbedc6b16ea0cf49057e3cb8`；原 #22：`33e33c8e0583b70e1864ca7fb40e94152a338b6c`。
- 独立复核冻结代码：`72b176aac256f1f6dd2eb6ce9f2a864919c21711`；后续整理仅改文档，源码/测试未变。
- 执行记录沿用本会话用户确认的 GPT-6.1 Sol / High；工具未独立暴露根会话型号和费用。独立验证为同型号/High/单独只读上下文，不是异模型交叉验证。
- 四个 `src/ai_trade/market_data/cffex_rankings*.py` 模块实现请求/解析、模型、日历端口和版本纯函数；两个 `tests/unit/test_cffex*.py` 文件提供离线回归。未改正式 SQLite Schema、策略、Demo 或其他行情适配器。
- 请求仅限 IF/IH/IC/IM 的 CFFEX HTTPS CSV；证书验证开启，无重试/重定向，超时和响应大小有界。支持严格 GBK / UTF-8 BOM 的 named、legacy、mixed 格式。

## 问题、修复与限制

| 原问题 | 修复及验证 | 仍未实现/验收 |
| --- | --- | --- |
| 下一自然日被当作交易会话；事件时间使用采集时刻 | 显式 CFFEX 会话端口；event_time 为收盘，未知发布时间为 null；available_at 为采集之后首个已知后续会话开盘；缺日历阻断 | 无可靠真实 CFFEX 日历和历史首发时间，不用工作日或 SH 日历替代 |
| 404 被判作非交易日 | 默认 unavailable、原因未知；仅独立可见日历明确 closed 才 no_session；首页/HTML/空响应/格式错误不算零行成功 | 不能自动确认未发布 |
| 跨到期月汇总、缺失补零或范围混合 | 强制合约及 as_of/mode；只配对同会员/范围/合约/日期；缺侧 null，已知零保留；UNKNOWN/代客/自营分离 | expiry_month 仅 YYMM；真实到期日、换月与跨合约净额未实现 |
| 重复排名、乱码、宽松混合解析及残缺文件 | 统一校验表头/列宽/日期/合约/整数/重复项/完整榜单，拒绝显式声明但为空的段；成交量与持仓分离 | 不证明来源真实、历史覆盖完整或最终客户身份 |
| 元数据被当作持久幂等和完整版本链 | 显式前驱/原因；重复载荷不覆盖；拒绝缺父/分叉/重复版本；读取实际过滤 available_at、ingested_at | 仅纯函数与调用方链；无持久仓储/全局去重/事务登记/重启恢复；不支持 A→B→A 复用 digest 版本键 |
| 私人夹具目录缺失时跳过关键测试 | 默认使用标注 synthetic 的可移植夹具；旧真实样本只读重放 | 合成测试不是真实来源验收 |

原始复现包括：重复排名被接受为 243 个领域行、周五可见时间落到周六、未指定合约产生 39 个混合净额。独立复核首版另发现 HIGH：mixed 的某段只有表头时静默降级，分别返回 legacy/6 行、named/60 行且 ingestion=success。增加空声明段拒绝和两个精确回归后，独立复核新 SHA，限定离线范围无剩余 BLOCKER/HIGH。

历史勘误：2010/2019 保存件实际含类别和具名两段；裸会员名仍 UNKNOWN。公开会员持仓不等于最终机构/客户持仓。`futures_rankings` 只是领域契约，Schema v2 没有该物理表。

## 实际验证

| 验证 | 结果 |
| --- | --- |
| 原 #22 未改基线完整回归 | 472 passed, 1 skipped，43.43s |
| 最终相关测试 | 主会话 122 passed / 0.78s；独立上下文 122 passed / 0.82s |
| 最终完整离线回归 | 主会话 568 passed, 1 skipped / 43.35s；独立上下文同数量 / 42.99s |
| 本次收尾精简后的唯一一次本地完整回归 | 568 passed, 1 skipped / 44.66s；pip check、保留 JSON/报告链接及 diff 检查通过，源码和测试无变化 |
| 原交付 c038bee 的 PR #23 CI | [39134358504](https://github.com/fengjnah/a-share-quant-v1/actions/runs/39134358504)：568 passed, 1 skipped / 21.18s；整理提交必须重新确认 CI |
| 依赖及差异 | pip check 无破损依赖；git diff --check 通过 |
| 历史 CSV 离线重放 | 13 份全部 parse 成功：2010 三份各 66、2019 一份 198、其余九份各 240 个展开领域行，不是新 HTTP 返回行数 |

独立首版完整运行曾有 **2 failed, 564 passed, 1 skipped**：既有 project_progress 的 Windows 子进程编码解码失败。仅对测试进程设置 UTF-8 后完整重跑通过，无排除文件、无降低断言。唯一跳过项为未启用的真实 AKShare 集成。首次失败、日志哈希及源码 blob 保留在[测试证据](reviews/TASK_022A_TEST_EVIDENCE.json)；原始日志保存在本机外部目录 `task-022a-h-20261018`，不作为可移植依赖。

Python 3.12.14、pytest 8.4.2、Requests 2.34.2、AKShare 1.19.1，未安装新依赖。可复现离线命令：

```powershell
$env:PYTHONPATH = (Resolve-Path src).Path
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
python -m pytest -q tests/unit/test_cffex_rankings.py tests/unit/test_cffex_high_assurance.py
python -m pytest -q
python -m pip check
git diff --check
```

CFFEX 验收未执行真实请求、生产数据库、UI、样本外回测、部署或全历史回补；未执行专门类型/漏洞/依赖许可审计。[样本证据](reviews/TASK_022A_SAMPLE_REPLAY.json)保留来源、字节哈希、日期/合约和数量；原始 CSV/ZIP 未提交、未删除。

## 文件精简与追溯

按用户明确授权，将重复结论合入本文；保留本文、[局部契约](reviews/TASK_022A_CFFEX_CONTRACT.md)及上述两个长期证据 JSON。删除 **4 个中间文件**（均位于 docs/reviews）：`TASK_022A_HIGH_ASSURANCE_REVIEW.md`、`TASK_022A_INDEPENDENT_VERIFICATION.md`、`TASK_022A_REDUNDANCY_AUDIT.md`、`TASK_022A_FILE_INVENTORY.json`。已核查引用并迁移有效结论，不删代码、测试、fixture、正式契约、原始证据或其他任务文件。

旧报告及 106 个跟踪文件、107 个相关证据的盘点可从提交 `c038bee49f82cb69bffd350d27b3f30e421a345f` 恢复，例如 `git show c038bee:docs/reviews/TASK_022A_HIGH_ASSURANCE_REVIEW.md`。无字节完全重复组不代表无语义重复。原 17 个工作树、1581 个清单文件在高强度验收前后保持 HEAD/分支/索引/差异哈希/字节不变；本次不清理它们或缓存。旧原始 CSV/ZIP 和审计 fixture 仍受保护。

## 准入边界

| 领域 | 状态 |
| --- | --- |
| 代码质量、缺失/会员范围 | VERIFIED，仅冻结代码的离线解析/派生范围 |
| 未来函数与时间 | PARTIAL；注入日历和读时门禁已验，真实日历/发布时间/权威历史读路径待验 |
| 版本链与幂等 | PARTIAL；缺持久化仓储、约束和账本 |
| 数据授权 R04 | UNKNOWN；商业/生产/再分发准入未确认 |
| HTTPS 生产可达性 | UNKNOWN；本轮未探测，历史失败不代替当前结果 |

整体仍为 PARTIAL。收敛离线适配器代码不批准正式策略、自动采集或生产运行。M0 A 股日线 Demo 复用既有腾讯/东方财富→临时 SQLite 路径，与 CFFEX 门禁分离；启动说明见[本地 Demo](LOCAL_MARKET_DEMO.md)。

# 项目状态与验收边界（2026-10-17）

本文件是当前状态索引；TASK 实施记录保留历史环境、旧 PR 和当时结果，不追溯改写。

## GitHub 集成状态

- 已合并：PR #1（TASK-002 SQLite）、#5（TASK-003 AKShare）、#6（TASK-003C TLS）、#7（Streamlit 演示）、#8（工程基线）、#9（讨论归档）。
- 已关闭且未合并：#2（由 #5 替代）、#3（由 #6 替代）、#4（由 #7 替代）。
- 默认分支：`main`；TASK-004 续执行基线为 `d09a259ec34fec8e587baa54b63706ba96c3b9af`。本分支 `codex/task-004-master-calendar-resumed` 保留并续接已有实现，交由独立 PR 审查，不代表 main 已合并 TASK-004。
- 代码库在本次核查时仍为 public；不要提交密钥、SQLite、原始数据或网络响应。

## 代码与文档映射

| 功能 | 主要代码 | 相关文档 | 验收 |
| --- | --- | --- | --- |
| SQLite 初始化、事务、迁移 | `src/ai_trade/storage/db.py`, `schema.py` | `IMPLEMENTATION_TASK_002.md` | 离线单元测试覆盖 |
| 日线验证、追加版本、时点读取 | `src/ai_trade/data_access/` | `DATA_CONTRACT.md`, `IMPLEMENTATION_TASK_002.md` | 最小数据契约测试；不是完整多数据集服务 |
| 证券主数据、日期级日历 | `src/ai_trade/reference_data/`, `security_master/`, `trading_calendar/`, `storage/reference_schema.py` | `IMPLEMENTATION_TASK_004.md` | 本分支模型/存储及离线测试通过；真实来源、历史覆盖未验收 |
| AKShare 历史日线、证据、采集 | `src/ai_trade/market_data/` | `IMPLEMENTATION_TASK_003.md`, `IMPLEMENTATION_TASK_003B.md` | 离线测试；指定真实批次见 TASK-003C |
| TLS 诊断 | `tools/diagnose_akshare_tls.py` | `IMPLEMENTATION_TASK_003C.md` | 诊断单元测试及指定环境的历史验收 |
| 本地 Streamlit 演示 | `src/ai_trade/demo_app.py` | `LOCAL_MARKET_DEMO.md` | 已集成，真实 UI→网络→SQLite 端到端未验收 |
| CI | `.github/workflows/offline-pytest.yml` | 本文件 | Python 3.11 pytest；不等于线上集成验收 |

## 已知缺口

- TASK-004：本分支实现稳定实体身份、已知名称时间线、上市/退市边界、日期级日历、不可变版本与双时间可见性查询；真实历史来源/覆盖未验收，历史 ST/停牌、代码变更别名、完整交易会话与可重开快照仍未实现。
- 未实现：全市场增量采集、复权及公司行为、市场宽度、期货持仓/恐贪、选股、择时、风控、回测、日报、AWS 发布。
- 离线测试通过不能证明 Streamlit 页面在用户 Windows PC 的代理/TLS 环境可正常采集；该验收必须使用实际 Windows 会话。
- Streamlit 临时 SQLite 是会话隔离的演示库，不能用来声称生产持久化已验收。
- 当前 CI 使用 `pip install -e '.[test]'`，不会安装 Streamlit 或 AKShare 可选依赖；因此它不执行演示页启动或真实请求测试。

## 本地 Streamlit 端到端验收步骤

先从最新 `main` 拉取代码，按 `LOCAL_MARKET_DEMO.md` 安装 `.[akshare,demo]` 并启动。应在浏览器中人工完成：

1. 页面可启动、输入默认代码 `600000` 和指定日期；点击前不发送真实行情请求。
2. 点击“采集真实行情”后，核对真实请求结果、返回/入库行数、来源、观察时间和响应摘要；不以空表冒充成功。
3. 核对页面显示的会话临时 `demo.sqlite3` 路径，以及页面从同一 SQLite 数据库读回的行情。
4. 失败场景展示网络/TLS 错误，不关闭证书验证；不自动绕过组织代理政策。
5. 确认不会读取或写入 `QUANT_DB_PATH` 指向的业务数据库，不泄露证据文件或密钥。
6. 保存脱敏的执行时间、环境、请求参数、结果、行数、数据库读回证据和问题记录。未完成前保持“待验收”。

可在 Windows PowerShell 中执行：

```powershell
git switch main
git pull --ff-only
.\.venv\Scripts\python.exe -m pip install -e ".[akshare,demo]"
$env:NO_PROXY = "push2his.eastmoney.com"  # 仅在组织网络策略允许直连时使用
.\.venv\Scripts\python.exe -m streamlit run src/ai_trade/demo_app.py
```

**验收状态：待用户 Windows 本地真实操作与证据。** GitHub 云端测试不等同于本机 GUI、代理与真实源端到端测试。

## 后续优先级

1. 审查 TASK-004 PR，验证最新基线回归和 CI。
2. 在 Windows 本地完成 Streamlit 真实端到端验收，记录缺陷。
3. 为主数据/日历选择有许可及发布时间证据的可靠来源，独立验收覆盖和缺口；不从当前列表倒推历史。
4. 在数据可得性与历史身份可靠后，推进市场状态、选股、回测。

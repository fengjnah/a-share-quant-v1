"""Small local Streamlit UI for the existing AKShare -> SQLite ingestion path.

Supports two data sources: Eastmoney (primary, existing) and Tencent (backup
candidate, TASK-008A). The app always uses an isolated temporary SQLite database.
It never resolves or initializes the configured production/local database.
Real network access occurs only after the user explicitly presses the
collection button.
"""
from __future__ import annotations

import tempfile
import uuid
from datetime import date
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="A股量化系统 V1.3 · 行情与项目进度", page_icon="📈", layout="wide")
workspace = st.sidebar.radio("工作区", ["行情工作台", "项目进度"],
                             index=1 if st.query_params.get("view") == "progress" else 0)
if workspace == "项目进度":
    from ai_trade.project_progress.page import render
    render()
    st.stop()

# The offline management page exits before loading any market or database modules.
import pandas as pd
import requests

from ai_trade.data_access.repository import SQLiteMarketDataRepository
from ai_trade.market_data.akshare_adapter import AkshareDailyClient
from ai_trade.market_data.evidence import EvidenceStore
from ai_trade.market_data.ingestor import DailyHistoryIngestor
from ai_trade.market_data.models import DailyHistoryRequest, EvidenceWriteError
from ai_trade.storage.db import Database, DatabaseConfig
from ai_trade.market_data.tx_adapter import TxDailyClient

PROVIDER_HOST = "push2his.eastmoney.com"


def normalize_symbol(raw: str) -> str:
    """Accept six-digit A-share codes or explicit .SH/.SZ suffixes."""
    value = raw.strip().upper()
    if len(value) == 6 and value.isdigit():
        if value.startswith(("600", "601", "603", "605", "688", "689")):
            return value + ".SH"
        if value.startswith(("000", "001", "002", "003", "300", "301")):
            return value + ".SZ"
        raise ValueError("该代码不在当前适配器支持的沪深 A 股代码范围内。")
    if len(value) == 9 and value[:6].isdigit() and value[6:] in (".SH", ".SZ"):
        return value
    raise ValueError("请输入 6 位沪深 A 股代码，例如 600000，或明确后缀 600000.SH。")


def get_demo_root() -> Path:
    """Create a per-Streamlit-session scratch area, never the production DB."""
    if "demo_root" not in st.session_state:
        st.session_state.demo_root = tempfile.mkdtemp(prefix="a-share-quant-demo-")
    return Path(st.session_state.demo_root)


def get_components():
    root = get_demo_root()
    db_path = root / "demo.sqlite3"
    db = Database(DatabaseConfig(db_path, environment="test", journal_mode="DELETE"))
    db.initialize()
    repository = SQLiteMarketDataRepository(db)
    evidence = EvidenceStore(root / "evidence")
    return db, repository, evidence


def saved_rows(db: Database) -> pd.DataFrame:
    with db.connection() as conn:
        rows = conn.execute(
            """SELECT i.symbol AS symbol, b.trade_date AS trade_date,
                      v.open AS open, v.high AS high, v.low AS low, v.close AS close,
                      v.volume AS volume_shares, v.amount AS amount_cny,
                      v.source AS source, v.available_at AS available_at,
                      v.ingested_at AS ingested_at, v.quality_status AS quality_status
               FROM daily_bars b
               JOIN instruments i ON i.instrument_id=b.instrument_id
               JOIN daily_bar_versions v ON v.bar_id=b.bar_id
               ORDER BY b.trade_date DESC, i.symbol"""
        ).fetchall()
    return pd.DataFrame([dict(row) for row in rows])


def proxy_configuration_label(url: str) -> str:
    """Resolve Requests configuration, without claiming the actual socket route."""
    try:
        selected = requests.utils.select_proxy(url, requests.utils.get_environ_proxies(url))
        return "选择代理" if selected else "未选择代理"
    except Exception:
        return "未知"


def record_collect_click() -> None:
    """Distinguish a new click from a Streamlit rerun of a submitted form."""
    st.session_state.collect_click_id = st.session_state.get("collect_click_id", 0) + 1


st.title("A股量化系统 V1.3")
st.caption("本地行情采集工作台 · AKShare 1.19.1 → 现有采集适配器 → 隔离 SQLite")

st.warning(
    "演示环境：数据库位于操作系统临时目录，与项目 local.sqlite3 / 生产数据库完全隔离。"
    "只有点击“采集真实行情”才会发出网络请求；不会使用合成行情填充结果。"
)

try:
    db, repository, evidence = get_components()
except Exception as exc:
    st.error(f"演示数据库初始化失败：{type(exc).__name__}: {exc}")
    st.stop()

with st.sidebar:
    st.subheader("运行环境")
    st.write("AKShare：固定版本 1.19.1（运行时核验）")
    st.write("东方财富代理配置（推断）：" + proxy_configuration_label(f"https://{PROVIDER_HOST}/"))
    st.write("腾讯行情代理配置（推断）：" + proxy_configuration_label("https://proxy.finance.qq.com/"))
    st.write("腾讯起始日探测代理配置（推断）：" + proxy_configuration_label("https://web.ifzq.gtimg.cn/"))
    st.caption("以上是 Requests 配置解析结果，实际连接路由未在页面观测。")
    st.write("TLS 证书验证：保持 requests 默认验证")
    st.code(str(db.config.path), language="text")
    st.caption("该临时数据库路径只属于当前演示会话。")
    if st.button("清空本演示数据", type="secondary"):
        st.session_state.pop("demo_root", None)
        st.rerun()

col1, col2, col3 = st.columns(3)
col1.metric("演示数据库", "已初始化")
col2.metric("已保存日线", str(len(saved_rows(db))))
col3.metric("数据源", "AKShare / 东方财富（默认）· 腾讯（备用）")

st.subheader("历史日线采集")
with st.form("collect_form"):
    source_choice = st.selectbox(
        "行情数据源",
        options=["东方财富（主源）", "腾讯（备用候选）"],
        index=0,
        help="腾讯为 TASK-008A 备用候选，尚未通过生产适用性验收。",
    )
    raw_symbol = st.text_input("股票代码", value="600000", help="支持 600000 或 600000.SH")
    date_cols = st.columns(2)
    start_date = date_cols[0].date_input("开始日期", value=date(2026, 10, 14))
    end_date = date_cols[1].date_input("结束日期", value=date(2026, 10, 15))
    adjustment = st.selectbox("复权口径", options=["none"], format_func=lambda _: "不复权")
    submitted = st.form_submit_button(
        "采集真实行情", type="primary", use_container_width=True,
        on_click=record_collect_click,
    )

click_id = st.session_state.get("collect_click_id", 0)
if submitted and click_id > st.session_state.get("processed_collect_click_id", 0):
    st.session_state.processed_collect_click_id = click_id
    try:
        symbol = normalize_symbol(raw_symbol)
        if start_date > end_date:
            raise ValueError("开始日期不能晚于结束日期。")
        request = DailyHistoryRequest(
            instrument_id=f"cn-equity:{symbol.replace('.', ':')}",
            symbol=symbol,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            adjustment_method=adjustment,
        )
        use_tx = source_choice.startswith("腾讯")
        if use_tx:
            sdk = TxDailyClient()
        else:
            sdk = AkshareDailyClient()
        with st.spinner("正在请求真实行情并写入隔离 SQLite……"):
            result = DailyHistoryIngestor(
                sdk, repository, evidence, timeout=10.0
            ).collect(request, run_id=f"demo-{uuid.uuid4().hex}")
        st.session_state.last_result = {
            "status": result.status.value,
            "source": result.source,
            "run_id": result.run_id,
            "returned_rows": result.returned_rows,
            "inserted_rows": result.inserted_rows,
            "http_status": result.http_status,
            "issues": list(result.issues),
            "warnings": list(result.warnings),
            "evidence_directory": result.evidence_directory,
            "response_sha256": result.response_sha256,
            "observed_at": result.observed_at,
            "use_tx": use_tx,
        }
        if result.status.value == "success":
            # Verify the saved record through the repository's point-in-time read API.
            for bar in result.records:
                repository.get_bar(
                    instrument_id=bar.instrument_id,
                    trade_date=bar.trade_date,
                    source=bar.source,
                    adjustment_method=bar.adjustment_method,
                    as_of=bar.ingested_at,
                    mode="strict_backtest",
                )
            st.success(
                f"真实采集成功：返回 {result.returned_rows} 行，"
                f"插入 {result.inserted_rows} 行；SQLite 时点读回检查通过。"
            )
        else:
            st.error(f"采集未通过：{result.status.value}。没有把失败解释为空行情。")
    except EvidenceWriteError as exc:
        st.error(
            f"采集证据写入失败：{exc}。database_committed={exc.database_committed}；"
            "请先检查临时数据库与证据目录，再决定是否重试。"
        )
    except Exception as exc:
        st.error(f"操作失败：{type(exc).__name__}: {exc}")
        st.caption("页面未生成虚构行情。若为网络/TLS 问题，请检查已审查的代理与 NO_PROXY 配置。")

if "last_result" in st.session_state:
    result = st.session_state.last_result
    st.subheader("最近一次采集结果")
    m1, m2, m3 = st.columns(3)
    m1.metric("状态", result["status"])
    m2.metric("返回行数", str(result["returned_rows"]) if result["observed_at"] is not None else "未知")
    m3.metric("入库行数", str(result["inserted_rows"]))
    st.write("来源：", result["source"])
    st.write("运行批次：", result["run_id"])
    st.write("HTTP 状态：", result["http_status"] if result["http_status"] is not None else "无 HTTP 响应 / SDK 未暴露")
    st.write("实际观察时间：", result["observed_at"] or "未取得")
    st.write("证据目录：", result["evidence_directory"])
    st.write("SDK 响应摘要：", result["response_sha256"] or "无")
    if result.get("use_tx"):
        st.warning("本批次使用腾讯备用候选接口，尚未通过生产适用性验收。")
    if result["issues"]:
        st.error("；".join(result["issues"]))
    if result["warnings"]:
        st.caption("边界说明：" + "；".join(result["warnings"]))

st.subheader("SQLite 实际读回的行情")
bars = saved_rows(db)
if bars.empty:
    st.info("当前演示数据库没有已保存的行情。请点击“采集真实行情”；网络失败时此表保持为空。")
else:
    st.dataframe(bars, use_container_width=True, hide_index=True)
    st.caption("以上数据直接从本次演示会话的 SQLite 读回，不是静态示例数据。")

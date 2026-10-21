"""Local M1 market workbench over the existing vendor/SQLite infrastructure."""
from __future__ import annotations

import os
import tempfile
import uuid
from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path

import streamlit as st

st.set_page_config(page_title="A股量化系统 V1.3 · 行情与项目进度", page_icon="📈", layout="wide")
workspace = st.sidebar.radio("工作区", ["行情工作台", "交易分析", "M3 市场分析", "M4 每日选股", "项目进度"],
                             index={"progress": 4, "analysis": 1, "market": 2, "candidates": 3}.get(st.query_params.get("view"), 0))
if workspace == "项目进度":
    from ai_trade.project_progress.page import render
    render()
    st.stop()

# Keep progress independent of all market/storage imports and failures.
import requests
from ai_trade.data_access.repository import SQLiteMarketDataRepository
from ai_trade.demo_data import SOURCES, chart_data, existing_demo_root, persistent_workbench_root, make_request, read_bars, verify_written
from ai_trade.market_data.akshare_adapter import AkshareDailyClient
from ai_trade.market_data.tx_adapter import TxDailyClient
from ai_trade.market_data.evidence import EvidenceStore
from ai_trade.market_data.ingestor import DailyHistoryIngestor
from ai_trade.market_data.models import DailyHistoryRequest, EvidenceWriteError
from ai_trade.storage.db import Database, DatabaseConfig


def get_demo_root() -> Path:
    if os.environ.get("AI_TRADE_STRICT_WORKBENCH") == "1" and not os.environ.get("AI_TRADE_WORKBENCH_ROOT"):
        raise ValueError("正式工作台未配置 AI_TRADE_WORKBENCH_ROOT；停止，不回退临时库")
    if os.environ.get("AI_TRADE_WORKBENCH_ROOT"):
        return persistent_workbench_root(os.environ["AI_TRADE_WORKBENCH_ROOT"])
    if "demo_root" not in st.session_state:
        configured = os.environ.get("AI_TRADE_DEMO_ROOT")
        st.session_state.demo_root = str(existing_demo_root(configured)) if configured else tempfile.mkdtemp(prefix="a-share-quant-demo-")
    return Path(st.session_state.demo_root)


def get_components():
    root = get_demo_root()
    persistent = bool(os.environ.get("AI_TRADE_WORKBENCH_ROOT"))
    if persistent:
        from ai_trade.storage.workbench import workbench_config, inspect_database
        db = Database(workbench_config())
        inspect_database(db)
    else:
        db = Database(DatabaseConfig(root / "demo.sqlite3", environment="test", journal_mode="DELETE"))
        db.initialize()
    return db, SQLiteMarketDataRepository(db), EvidenceStore(root / "evidence")


def proxy_configuration_label(url: str) -> str:
    try:
        selected = requests.utils.select_proxy(url, requests.utils.get_environ_proxies(url))
        return "选择代理" if selected else "未选择代理"
    except Exception:
        return "未知"


def record_collect_click() -> None:
    st.session_state.collect_click_id = st.session_state.get("collect_click_id", 0) + 1


if workspace == "行情工作台":
    st.title("M1 行情工作台")
    st.caption("查询本地数据不联网 · 重新采集需主动点击 · 图表与表格共用 SQLite 验证数据")
read_only = os.environ.get("AI_TRADE_READ_ONLY", "1" if os.environ.get("AI_TRADE_WORKBENCH_ROOT") else "0") == "1"
st.warning("使用独立持久研究工作台，与交易生产库隔离。" if os.environ.get("AI_TRADE_WORKBENCH_ROOT") else
           "仅使用系统临时演示数据库，与生产库隔离；不自动采集、不自动切换数据源。")
if read_only:
    st.info("当前禁止在线采集；正式工作台同时使用 SQLite mode=ro。Demo 的按钮禁用不等于数据库只读。")
try:
    db, repository, evidence = get_components()
except Exception as exc:
    operation = "正式数据库打开/校验失败" if os.environ.get("AI_TRADE_WORKBENCH_ROOT") or os.environ.get("AI_TRADE_STRICT_WORKBENCH") == "1" else "演示数据库初始化失败"
    st.error(f"{operation}，已停止：{type(exc).__name__}: {exc}")
    st.stop()

with st.sidebar:
    st.subheader("运行环境")
    st.write("AKShare：采集时核验固定版本 1.19.1")
    for name, host in [("东方财富", "push2his.eastmoney.com"), ("腾讯行情", "proxy.finance.qq.com"), ("腾讯起始日探测", "web.ifzq.gtimg.cn")]:
        st.write(f"{name}代理配置（推断）：" + proxy_configuration_label(f"https://{host}/"))
    st.caption("仅为 Requests 配置解析；实际路由未观测。TLS 证书验证保持开启。")
    st.code(str(db.config.path), language="text")
    if os.environ.get("AI_TRADE_WORKBENCH_ROOT"):
        from ai_trade.storage.workbench import inspect_database
        with st.expander("正式研究库连接诊断"):
            diagnosis = inspect_database(db)
            st.json({k: diagnosis[k] for k in ("path", "connected_path", "schema_version", "read_only",
                    "query_only", "counts", "latest_trade_date", "quick_check", "foreign_key_check")})
    release_file = Path.cwd() / "DEPLOYED_SHA"
    if release_file.is_file():
        st.caption("部署提交：" + release_file.read_text(encoding="utf-8").strip())
    st.caption("AI_TRADE_WORKBENCH_ROOT 绑定专用持久研究目录；普通刷新不初始化、不迁移。" if os.environ.get("AI_TRADE_WORKBENCH_ROOT") else
               "指定 AI_TRADE_DEMO_ROOT 可在浏览器刷新后继续打开同一个已有临时演示库。未指定时按会话隔离。")
    with st.expander("打开已有临时演示区"):
        saved_root = st.text_input("已有演示目录", value="")
        if st.button("打开已有演示数据", disabled=bool(os.environ.get("AI_TRADE_WORKBENCH_ROOT"))):
            try:
                st.session_state.demo_root = str(existing_demo_root(saved_root))
                for key in ("last_result", "display_request", "display_source", "operation_error", "m2spec"):
                    st.session_state.pop(key, None)
                st.rerun()
            except Exception as exc:
                st.error(f"演示目录未打开：{type(exc).__name__}: {exc}")
    if st.button("新建隔离演示区", type="secondary", disabled=bool(os.environ.get("AI_TRADE_WORKBENCH_ROOT"))):
        st.session_state.demo_root = tempfile.mkdtemp(prefix="a-share-quant-demo-")
        for key in ("last_result", "display_request", "display_source", "operation_error", "m2spec"):
            st.session_state.pop(key, None)
        st.rerun()

if workspace == "M4 每日选股":
    from ai_trade.daily_candidates_page import render
    render(db)
    st.stop()

if workspace == "M3 市场分析":
    from ai_trade.market_analysis_page import render
    render(db)
    st.stop()

if workspace == "交易分析":
    from ai_trade.analysis_page import render
    render(db)
    st.stop()

with st.form("collect_form"):
    source_choice = st.selectbox("行情数据源", options=list(SOURCES), index=0)
    st.caption("仅列出已接入来源；当前网络可用性以采集结果为准。腾讯仍为候选源，未获生产准入。")
    raw_symbol = st.text_input("股票代码", value="600000", help="沪深 A 股六位代码或明确 .SH/.SZ 后缀")
    left, right = st.columns(2)
    start_date = left.date_input("开始日期", value=date(2026, 10, 14))
    end_date = right.date_input("结束日期", value=date(2026, 10, 15))
    st.selectbox("复权口径", options=["none"], format_func=lambda _: "不复权")
    query_clicked = st.form_submit_button("查询本地已有数据", type="primary")
    submitted = st.form_submit_button("采集真实行情", on_click=record_collect_click, disabled=read_only)
    st.caption("采集真实行情会重新请求供应商；重复行情由既有唯一约束明确拒绝，不会静默覆盖。")

click_id = st.session_state.get("collect_click_id", 0)
collect_clicked = submitted and click_id > st.session_state.get("processed_collect_click_id", 0)
if query_clicked or collect_clicked:
    if collect_clicked:
        st.session_state.processed_collect_click_id = click_id
        st.session_state.pop("last_result", None)
    st.session_state.pop("operation_error", None)
    try:
        request = make_request(raw_symbol, start_date, end_date)
        st.session_state.display_request = asdict(request)
        st.session_state.display_source = SOURCES[source_choice]
        if collect_clicked:
            use_tx = source_choice.startswith("腾讯")
            sdk = TxDailyClient() if use_tx else AkshareDailyClient()
            with st.spinner("正在采集真实行情并写入临时 SQLite……"):
                result = DailyHistoryIngestor(sdk, repository, evidence, timeout=10.0).collect(
                    request, run_id=f"demo-{uuid.uuid4().hex}")
            st.session_state.last_result = {
                "status": result.status.value, "source": result.source, "run_id": result.run_id,
                "request": asdict(request), "returned_rows": result.returned_rows,
                "inserted_rows": result.inserted_rows, "http_status": result.http_status,
                "issues": list(result.issues), "warnings": list(result.warnings),
                "evidence_directory": result.evidence_directory, "response_sha256": result.response_sha256,
                "observed_at": result.observed_at, "use_tx": use_tx, "readback_rows": None,
            }
            if result.status.value == "success":
                count = verify_written(repository, result.records)
                st.session_state.last_result["readback_rows"] = count
                st.success(f"真实采集成功：返回 {result.returned_rows} 行，插入 {result.inserted_rows} 行；SQLite 逐字段读回 {count} 行一致。")
            else:
                st.error(f"采集未通过：{result.status.value}。下方仅展示本地既有数据，不是本次失败请求的响应。")
        else:
            st.info("本地查询完成：未请求行情接口、未创建采集批次。")
    except EvidenceWriteError as exc:
        st.session_state.operation_error = f"采集证据写入失败：database_committed={exc.database_committed}。检查临时数据库及证据目录后再决定是否重试。"
    except Exception as exc:
        if "last_result" in st.session_state and st.session_state.last_result["status"] == "success":
            st.session_state.last_result["status"] = "readback_error"
        st.session_state.operation_error = f"操作失败：{type(exc).__name__}: {exc}"
        st.session_state.pop("display_request", None)

if "operation_error" in st.session_state:
    st.error(st.session_state.operation_error)
    st.caption("检查股票代码、交易所后缀、日期顺序和日期范围；仅支持已结束的历史日期。不会生成示例行情。")

if "last_result" in st.session_state:
    result = st.session_state.last_result
    st.subheader("最近一次采集结果")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("状态", result["status"])
    m2.metric("返回行数", str(result["returned_rows"]) if result["observed_at"] is not None else "未知")
    m3.metric("入库行数", str(result["inserted_rows"]))
    m4.metric("本批次核对行数", str(result["readback_rows"]) if result["readback_rows"] is not None else "未验证")
    st.write("采集请求：", result["request"])
    st.write("来源：", result["source"])
    st.write("运行批次：", result["run_id"])
    st.write("HTTP 状态：", result["http_status"] if result["http_status"] is not None else "未知 / SDK 未暴露")
    st.write("实际观察时间：", result["observed_at"] or "未取得")
    if result["status"] == "success" and result["readback_rows"] is None:
        st.error("数据库已提交，但读回核对未通过；禁止将本批次判为完整成功，请检查后再重试。")
    if result["issues"]:
        st.error("；".join(result["issues"]))
        st.caption("网络失败：检查代理/网络后手动重试；空响应：核对请求范围及源覆盖；重复：改用本地查询。不会自动重试或切换源。")
    with st.expander("采集证据与限制"):
        st.write("证据目录：", result["evidence_directory"])
        st.write("SDK 响应摘要：", result["response_sha256"] or "无")
        st.write("边界说明：", "；".join(result["warnings"]))

if "display_request" not in st.session_state:
    st.info("尚未查询。请选择股票与日期，点击本地查询或主动采集。")
else:
    request = DailyHistoryRequest(**st.session_state.display_request)
    source = st.session_state.display_source
    st.subheader("SQLite 查询结果")
    st.write(f"{request.symbol} · {request.start_date} 至 {request.end_date} · 不复权")
    st.caption("实际来源：" + source)
    try:
        with st.spinner("正在从 SQLite 读取并校验……"):
            bars = read_bars(db, request, source=source, as_of=datetime.now(timezone.utc).isoformat())
        st.metric("数据库读回行数", str(len(bars)))
        if bars.empty:
            st.info("当前股票、来源和日期范围没有本地数据；这不代表休市或供应商返回零行。可调整查询，或主动采集。")
        else:
            st.success("完整性：现有领域校验及可见版本读取通过；交易日覆盖完整性尚未认证。")
            st.caption(f"数据日期：{bars.trade_date.min()} ～ {bars.trade_date.max()}；入库时间：{bars.ingested_at.max()}；批次：{'、'.join(bars.run_id.unique())}")
            prices, volumes = chart_data(bars)
            price_col, volume_col = st.columns(2)
            with price_col:
                st.subheader("收盘价走势（元）")
                if len(bars) >= 2:
                    st.line_chart(prices)
                else:
                    st.info("仅有 1 条记录，不足以显示价格走势；请扩大已有数据查询范围或主动采集。")
            with volume_col:
                st.subheader("成交量（股）")
                st.bar_chart(volumes)
            st.subheader("SQLite 实际读回的行情")
            st.dataframe(bars, use_container_width=True, hide_index=True)
            st.caption("图表和明细来自同一份 SQLite 验证数据；成交量单位为股，成交额为元，不再做单位转换。")
    except Exception as exc:
        st.error(f"SQLite 读取或数据校验失败：{type(exc).__name__}: {exc}")
        st.caption("本次未展示未经验证的图表或行情。检查演示库路径、锁定状态和数据版本；不要删除库后盲目重试。")

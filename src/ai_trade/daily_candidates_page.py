"""Mobile-first trading workflow over existing M4/M2 results; no new signals."""
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from ai_trade.daily_candidates import CandidateBatch, LIMITATIONS, STRATEGIES, table_row
from ai_trade.daily_candidates_data import load_batch, local_coverage
from ai_trade.daily_candidates_details import render_detail, risk_card
from ai_trade.daily_candidates_view import VIEWS, STAGES, data_status, load_watch_batch, monitor_row, risk_row, symbols_input
from ai_trade.demo_data import SOURCES
from ai_trade.market_state import MARKET_MODES, MarketState
from ai_trade.storage.db import Database, DatabaseConfig
from ai_trade.trading_analysis import risk_reference


@st.cache_data(ttl=300, max_entries=16, show_spinner=False)
def _cached_batch(path, journal_mode, fingerprint, source, analysis_date, as_of, strategy, market_mode, symbol, equity, watch=False):
    db = Database(DatabaseConfig(Path(path), environment="test", journal_mode=journal_mode))
    spec = dict(source=source, analysis_date=analysis_date, as_of=as_of, strategy=strategy, market_mode=market_mode, equity=equity)
    return load_watch_batch(db, symbols=symbols_input(symbol), **spec) if watch else load_batch(db, **spec)


def _fingerprint(path):
    return tuple((p.stat().st_mtime_ns, p.stat().st_size) if p.exists() else None
                 for p in (path, Path(str(path)+"-wal")))


def _open_detail(code):
    st.session_state.m4_view = "股票详情"
    st.session_state.m4_focus = code


def _open_watch():
    st.session_state.m4_view = "指定股票分析"


def _details_picker(rows, key):
    if not rows:
        st.info("当前没有股票结果；仍可在指定股票分析中输入代码查看缺失原因。")
        return
    selected = st.selectbox("选择股票", [r.symbol for r in rows], key=key)
    st.button("打开股票详情", on_click=_open_detail, args=(selected,), key=key+"-open")


def _zero(batch):
    st.warning("今日无合格候选（0只）。")
    st.write("市场闸门：", "；".join(batch.market.reasons))
    st.write("形态筛选：", f"{sum(r.research_match for r in batch.evaluations)}只满足当前模式研究条件；不代表完成六阶段或允许入场。")
    st.write("数据限制：历史ST/可交易状态、周线完整性、行业/基本面未认证；评分未知不按0补齐。")


def _overview(batch, status):
    if not batch.market.validated:
        st.warning("市场状态未完成计算；正式开仓许可未提供，不允许新增多头。")
    else:
        st.info("显示后端研究市场状态；研究过滤结果不等于真实账户开仓许可。")
    st.caption("市场来源："+batch.market.source)
    st.write("判断理由：", "；".join(batch.market.reasons))
    st.dataframe(pd.DataFrame([{"市场字段": name, "实际结果": "尚未提供正式结果"} for name in
                  ("市场评分", "全A等权趋势", "上涨/下跌家数", "市场广度", "全市场成交额变化")]),
                 hide_index=True, use_container_width=True)
    st.caption("本地最多20只的样本不能代表全A；不把M3未获准的研究分数升级为市场闸门。")
    st.subheader("交易阶段与重点观察")
    st.write("低位启动 → 天量换手 → 缩量横盘 → 二次放量 → 突破确认 → MA5持仓")
    st.info(f"阶段待识别 {len(batch.evaluations)} 只。M2尚未输出S0–S6顺序状态与B点，独立形态仅供观察。")
    if not batch.candidates:
        _zero(batch)
    else:
        _picks(batch)
    st.subheader("风险提醒")
    st.write("1%为单笔账户风险上限；无权益不填金额，无执行条件不填股数。市场闸门关闭仍保留全部观察与止损参考。")
    _details_picker(batch.evaluations, "m4-home-stock")


def _monitor(batch):
    st.subheader("六阶段选股监控")
    stage = st.selectbox("交易阶段", ("全部", "阶段待识别")+tuple(x[0]+" "+x[1] for x in STAGES))
    st.selectbox("行业筛选", ("全部", "未知（历史行业未接入）"))
    search = st.text_input("搜索股票代码", "").strip().upper()
    sort = st.selectbox("排序依据", ("技术研究评分降序（综合评分未提供）", "股票代码"))
    with st.expander("S0–S6能力与下一阶段条件"):
        st.dataframe(pd.DataFrame([{"阶段": code+" "+name, "计算状态": "后端尚未提供正式阶段", "待满足接口": need}
                                  for code, name, need in STAGES]), hide_index=True, use_container_width=True)
    rows = [r for r in batch.evaluations if search in r.symbol]
    if stage not in ("全部", "阶段待识别"):
        rows = []
        st.info("该阶段暂无正式后端输出；不将独立突破、缩量回调或日线趋势推断成阶段。")
    if sort == "股票代码":
        rows = sorted(rows, key=lambda r:r.symbol)
    if rows:
        st.dataframe(pd.DataFrame([monitor_row(r) for r in rows]), hide_index=True, use_container_width=True)
    else:
        st.info("该筛选范围没有已确认阶段股票。")
    st.caption("量比相对前5条均量，价格单位元；整理区间/进入日期/持续交易日数保持未知，不以20条高低点或行情条数替代。")
    _details_picker(rows, "m4-monitor-stock")


def _picks(batch):
    st.subheader("每日精选 · 最多5只")
    if not batch.candidates:
        _zero(batch)
        return
    for i, row in enumerate(batch.candidates, 1):
        with st.container(border=True):
            st.write(f"{i}. {row.symbol} · {row.name}")
            st.write("行业：未知；基本面/板块评分：尚未计算；技术研究评分：", row.score)
            st.write("交易阶段/B点：尚未提供；入场评估：正式执行约束未提供。")
            st.write("入选研究条件：", "、".join(k for k,v in row.analysis.summary["conditions"].items() if v is True))
            st.caption("行情日期："+row.analysis.summary["latest_trade_date"])
            risk_card(row)
            st.warning("次日跳空、可交易性、涨跌停、停牌及T+1必须重验；研究名单不保证成交。")
            st.button("查看 "+row.symbol, on_click=_open_detail, args=(row.symbol,), key="pick-"+row.symbol)


def _watch(db, batch, source, equity):
    st.subheader("指定股票分析")
    raw = st.text_area("自选股票（支持多个）", placeholder="600000, 600378\n000001", key="m4_watch_input")
    st.caption("临时会话输入，不创建自选服务；最多20个，仅分析已有本地行情，失败代码和未达门槛股票均保留。")
    if st.button("分析指定股票", type="primary"):
        st.session_state.pop("m4_watch_batch", None)
        try:
            symbols_input(raw)
            st.session_state.m4_watch_batch = _cached_batch(str(db.config.path), db.config.journal_mode,
                _fingerprint(db.config.path), source, batch.analysis_date, datetime.now(timezone.utc).isoformat(),
                batch.strategy, batch.market_mode, raw, equity, True)
        except Exception as exc:
            st.error(f"指定股票未完成：{type(exc).__name__}: {exc}")
    watch = st.session_state.get("m4_watch_batch")
    if watch is None:
        st.info("输入代码后查看每只股票的研究条件与排除原因。")
        return
    st.caption(f"指定分析快照 {watch.analysis_date} · {watch.strategy} · {watch.as_of}；不并入自动精选。")
    for row in watch.evaluations:
        with st.container(border=True):
            st.write(row.symbol+" · "+row.name)
            st.write("市值 / ST / 行业 / 成长性：数据不足，相关筛选未执行；不视为正常或通过。")
            st.write("技术形态：", "满足当前模式研究条件" if row.research_match else "未满足或数据不足")
            st.write("未通过原因：", "；".join(row.exclusions))
    _details_picker(watch.evaluations, "m4-watch-stock")


def _risk(batch):
    st.subheader("风险与持仓监控")
    st.warning("数据类型：行情派生研究，非真实持仓；当前没有真实账户或模拟成交接口。")
    st.write("新增多头：未获正式许可；市场状态缺失不解除止损观察，也不把观察股票当作持仓。")
    if batch.evaluations:
        st.dataframe(pd.DataFrame([risk_row(r) for r in batch.evaluations]), hide_index=True, use_container_width=True)
    st.info("MA5位置仅是收盘与均线的比较。连续两个交易日跌破MA5、初始持仓止损及退出/失效事件未由后端提供，不自行计数或制造退出信号。")
    st.caption("止损距离是当前收盘与当前研究止损之差，不是持仓损益、目标收益或真实账户风险。")
    _details_picker(batch.evaluations, "m4-risk-stock")


def render(db):
    st.title("M4 交易监控工作台")
    st.caption("先看市场许可，再看形态进程与风险 · 本地行情研究，不自动下单")
    view = st.selectbox("M4 页面", VIEWS, key="m4_view")
    now = datetime.now(timezone.utc).isoformat()
    today = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    coverage, dates, error = [], [], None
    with st.expander("筛选与账户设置", expanded=False):
        source_label = st.selectbox("选股行情来源", list(SOURCES), index=1, key="m4_source")
        source = SOURCES[source_label]
        try:
            coverage, dates = local_coverage(db, source=source, as_of=now)
        except Exception as exc:
            error = f"本地股票池读取失败：{type(exc).__name__}: {exc}"
        with st.form("m4-controls"):
            analysis_date = st.selectbox("选股分析日期", dates, disabled=not dates,
                                        help="只列出当前可见的本地行情日期")
            strategy = st.selectbox("策略模式", STRATEGIES)
            market_mode = st.selectbox("市场状态过滤模式", MARKET_MODES)
            pool = st.selectbox("股票池范围", ("本地同源A股（最多20只）", "指定股票"))
            symbol = st.text_input("指定股票代码", "", placeholder="支持多个代码，以逗号或空格分隔")
            equity_text = st.text_input("账户权益（元，可留空）", "")
            st.caption("严格模式=日线趋势且任一M2独立形态，并非穿三线专用模式；趋势确认模式只要求日线趋势。共同门禁不放宽。")
            submitted = st.form_submit_button("生成每日候选", type="primary")
        with st.expander("实际执行的筛选与本地覆盖"):
            st.dataframe(pd.DataFrame(LIMITATIONS, columns=["筛选条件", "执行状态", "依据/限制"]), hide_index=True, use_container_width=True)
            st.dataframe(pd.DataFrame(coverage), hide_index=True, use_container_width=True)
    identity = (str(db.config.path), source, today)
    equity = None
    try:
        equity = float(equity_text) if equity_text.strip() else None
        risk_reference(1.0, None, None, equity)
    except ValueError as exc:
        if submitted:
            st.error(str(exc))
            return
    if submitted or st.session_state.get("m4_identity") != identity:
        st.session_state.pop("m4_batch", None)
        st.session_state.pop("m4_watch_batch", None)
        try:
            if pool == "指定股票":
                symbols_input(symbol)
            batch = (_cached_batch(str(db.config.path), db.config.journal_mode, _fingerprint(db.config.path), source,
                        analysis_date, now, strategy, market_mode, symbol, equity, pool == "指定股票") if dates else
                     CandidateBatch(today, now, strategy, market_mode, MarketState(today), [], ["没有可见本地行情"]))
            st.session_state.m4_batch = batch
            st.session_state.m4_identity = identity
        except Exception as exc:
            st.error(f"未生成结果：{type(exc).__name__}: {exc}")
            return
    batch = st.session_state.get("m4_batch")
    if batch is None:
        st.info("请重新生成每日候选。")
        return
    if error:
        st.error(error)
    status = data_status(batch, today=today)
    if view == "每日交易总览":
        a, b, c = st.columns(3)
        a.metric("市场环境", batch.market.state)
        b.metric("新增多头仓位", "未获准")
        c.metric("合格候选", len(batch.candidates))
    st.caption(f"分析日期 {batch.analysis_date} · 最新行情 {status['latest'] or '未知'} · 数据更新时间 {status['updated'] or '未知'}")
    st.caption(f"{batch.strategy} · {batch.market_mode} · 来源 {source_label} · 数据状态：{status['state']}")
    if status["latest"] and status["oldest"] < today:
        st.warning("数据过期 / 历史回看：行情早于当前上海日期。日历未认证，不据此断言缺失交易日或休市；不会把旧信号当今日入场许可。")
    if status["synthetic"]:
        st.warning("离线演示：合成测试数据，不能作为真实行情或真实来源验收。")
    st.caption(f"读取快照 {batch.as_of}；历史价格截止后在当前时点计算，不回填为当日盘中已知。")
    if view == "每日交易总览":
        _overview(batch, status)
    elif view == "六阶段选股监控":
        _monitor(batch)
    elif view == "每日精选":
        _picks(batch)
    elif view == "指定股票分析":
        _watch(db, batch, source, equity)
    elif view == "风险与持仓监控":
        _risk(batch)
    else:
        rows = {r.symbol:r for r in batch.evaluations}
        watch = st.session_state.get("m4_watch_batch")
        if watch:
            rows.update({r.symbol:r for r in watch.evaluations})
        if not rows:
            st.info("尚无股票详情。可先进行指定股票分析，缺失代码仍显示失败原因。")
            st.button("前往指定股票分析", on_click=_open_watch)
            return
        options = list(rows)
        focus = st.session_state.get("m4_focus")
        selected = st.selectbox("查看股票详情（含被排除股票）", options,
                                index=options.index(focus) if focus in options else 0, key="m4_detail")
        render_detail(rows[selected])

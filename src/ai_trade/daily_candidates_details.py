"""M4 detail and risk components over one existing M2 analysis object."""
import altair as alt
import pandas as pd
import streamlit as st

from ai_trade.daily_candidates import score_rows
from ai_trade.daily_candidates_view import events, risk_row
from ai_trade.trading_analysis import FORMULAS


def value(number):
    return "数据不足 / 尚未提供" if number is None or pd.isna(number) else f"{number:,.4f}"


def risk_card(row):
    if row.analysis is None:
        st.error("；".join(row.exclusions))
        return
    r = row.risk
    a, b = st.columns(2)
    a.metric("结构止损（元）", value(r.get("structure_stop")))
    b.metric("ATR止损（元）", value(r.get("atr_stop")))
    st.write("最终研究止损（元）：", value(r.get("final_stop")))
    st.caption(r.get("stop_reason", ""))
    st.write("参考测算价（所属日收盘，非计划成交价）：", value(r.get("reference_entry")))
    st.write("账户权益（元）：", value(r.get("equity")), "；1%风险预算（元）：", value(r.get("risk_budget")))
    st.info(r.get("sizing_reason", "交易单位和执行状态未知，不计算仓位"))
    st.caption("初始持仓止损、计划入场价、实际持仓、风险收益目标均未提供；当前结构值是前10条最低价，不是某笔交易的初始止损。")


def price_charts(row):
    f = row.analysis.frame.copy()
    if len(f) < 2:
        st.info("真实行情不足2条，不能绘制日K趋势。")
        return
    f["date"] = pd.to_datetime(f.trade_date)
    base = alt.Chart(f).encode(x=alt.X("date:T", title="行情日期"))
    colors = alt.condition("datum.close >= datum.open", alt.value("#d94343"), alt.value("#19855b"))
    tip = [alt.Tooltip("trade_date:N", title="行情日"), alt.Tooltip("open:Q", title="开盘", format=".4f"),
           alt.Tooltip("high:Q", title="最高", format=".4f"), alt.Tooltip("low:Q", title="最低", format=".4f"),
           alt.Tooltip("close:Q", title="收盘", format=".4f")]
    wick = base.mark_rule().encode(y=alt.Y("low:Q", title="价格（元）", scale=alt.Scale(zero=False)), y2="high:Q", color=colors, tooltip=tip)
    body = base.mark_bar(size=4).encode(y="open:Q", y2="close:Q", color=colors, tooltip=tip)
    ma = base.transform_fold(["MA5", "MA10", "MA20"], as_=["均线", "值"]).mark_line(strokeWidth=1.4).encode(
        y="值:Q", color=alt.Color("均线:N", scale=alt.Scale(range=["#d7971e", "#3c70b4", "#7652a3"])))
    chart = (wick+body+ma).resolve_scale(color="independent").properties(height=280)
    marks = events(row)
    if not marks.empty:
        marks = marks.assign(date=pd.to_datetime(marks["行情日期"]))
        points = alt.Chart(marks).mark_point(shape="triangle-up", filled=True, color="#6d48ad", size=45).encode(
            x="date:T", y="收盘价:Q", tooltip=["行情日期:N", "独立M2条件:N", "指标可用时间:N"])
        chart += points
    st.altair_chart(chart, use_container_width=True)
    st.caption("红色：收盘≥开盘；绿色：收盘<开盘；紫色三角：独立M2条件。标记是行情所属日，不是当时已生成信号；未区分首次/二次放量。")
    volume = base.mark_bar().encode(y=alt.Y("volume_shares:Q", title="成交量（股）"), color=colors,
                                    tooltip=["trade_date:N", alt.Tooltip("volume_shares:Q", title="股数", format=",")]).properties(height=140)
    st.altair_chart(volume, use_container_width=True)
    if f.ATR14.notna().any():
        st.line_chart(f.set_index("trade_date")[["ATR14"]], height=140)


def render_detail(row):
    st.subheader(f"{row.symbol} · {row.name}")
    if row.analysis is None:
        st.error("；".join(row.exclusions))
        return
    s = row.analysis.summary
    st.caption(f"行情日期 {s['latest_trade_date']} · 不复权 · 元 / 股 · 数据来源 {s['source']}")
    st.caption(f"分析日 {s['analysis_date']} · 更新时间 {s['latest_ingested_at']} · 指标最早可用 {s['signal_available_at']}")
    st.warning("当前阶段：待识别；B点：尚未计算。首次→整理→二次突破、整理区间及阶段交易日数尚无M2正式输出。")
    st.write("下一阶段条件：等待M2正式顺序状态机；现有独立形态不等同于阶段确认。")
    price_charts(row)
    st.subheader("后端条件与评分依据")
    a, b = st.columns(2)
    a.metric("技术研究评分", "未知" if row.score is None else row.score)
    b.metric("基本面 / 板块评分", "尚未计算")
    st.write("当前模式条件：", "满足（仅研究）" if row.research_match else "未满足或未知")
    st.write("日线趋势：", s["trend"], "；周样本：", s["weekly_sample_trend"], "（周线完整性未认证）")
    st.dataframe(pd.DataFrame(score_rows(row)), hide_index=True, use_container_width=True)
    st.write("指标：", s["metrics"])
    st.write("未通过条件：", "；".join(row.exclusions) or "无")
    st.subheader("入场与风险参考")
    risk_card(row)
    st.warning("次日执行：下一可交易会话、涨跌停/停牌、跳空阈值、T+1与交易单位尚未验证；不能按所属日收盘回填成交。")
    st.subheader("历史条件与交易记录")
    marks = events(row)
    if marks.empty:
        st.info("当前真实区间没有满足的独立M2量价形态。")
    else:
        st.dataframe(marks, hide_index=True, use_container_width=True)
    st.info("模拟成交、真实持仓、止损触发和MA5退出记录尚未接入；不以行情图伪装交易记录。")
    st.write("MA5位置观察：", risk_row(row)["MA5位置观察"], "；连续两个交易日跌破计数：后端尚未提供。")
    with st.expander("计算公式、数据血缘与同一快照明细"):
        st.text(FORMULAS)
        st.caption(f"{s['rule_version']} · {s['snapshot_sha256']}")
        st.write("血缘：", s["lineage_refs"])
        st.dataframe(row.analysis.frame, hide_index=True, use_container_width=True)

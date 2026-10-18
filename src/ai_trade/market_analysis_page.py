"""Mobile-friendly M3 view over real observations and reproducible research rules."""
from datetime import date, timedelta
import os
from zoneinfo import ZoneInfo
from datetime import datetime

import pandas as pd
import streamlit as st

from ai_trade.demo_data import SOURCES, make_request, read_bars
from ai_trade.market_analysis import (
    RULES, WEIGHTS, contract_label, emotion, environment, extreme_outcomes,
    fear_greed, member_position, wave_scenarios,
)
from ai_trade.market_analysis_data import (
    INDEX_SYMBOLS, breadth_frame, collect_cffex, collect_public, now, price_frame,
    ranking_rows, snapshots,
)
from ai_trade.market_data.cffex_rankings_models import MemberScope
from ai_trade.trading_analysis import _visible


def _value(value):
    return "UNKNOWN（榜外/未知）" if value is None or pd.isna(value) else f"{value:,.0f}"


def _collect(key, operation):
    try:
        with st.spinner("正在进行一次有时限的真实查询……"):
            item = operation()
        st.session_state[key] = f"采集成功：数据日 {item['trade_date']}；观察时间 {item['observed_at']}"
    except Exception as exc:
        st.session_state[key] = f"数据不可用：{type(exc).__name__}；接口失败/超时/格式校验未通过，未生成替代数据。"
    message = st.session_state[key]
    st.success(message) if message.startswith("采集成功") else st.error(message)


def render(db):
    root = db.config.path.parent
    read_only = os.environ.get("AI_TRADE_READ_ONLY") == "1"
    as_of = now()
    st.title("M3 市场分析")
    st.caption("真实数据 · 派生指标 · 实验性情景｜本地查询不联网，采集需主动点击")
    st.warning("仅作研究辅助，不是预测或下单指令。公开会员席位不代表国家队或最终客户。数据对外展示/再分发授权待确认。")
    analysis_date = st.date_input("M3 分析日期", date(2026, 10, 16),
                                 max_value=datetime.fromisoformat(as_of).astimezone(ZoneInfo("Asia/Shanghai")).date()-timedelta(days=1))
    day = analysis_date.isoformat()
    st.caption(f"历史重建截止日 {day}｜本次系统读取时点 {as_of}；今天采集的历史数据不能视为当年已可见的信号。")
    summary = st.container()
    # Keep at most two columns; charts and detailed tables use the full narrow-screen width.
    target_kind = st.radio("趋势标的类型", ["指数", "股票"], horizontal=True)
    if target_kind == "指数":
        name = st.selectbox("指数", list(INDEX_SYMBOLS))
        symbol = INDEX_SYMBOLS[name]
        if st.button("查询真实指数历史", key="m3-index", disabled=read_only):
            _collect("m3-price-status", lambda: collect_public(root, "index", symbol))
        st.caption("新浪财经 / AKShare 1.19.1；单标的至多保存最近550条，不开展全历史回补。")
    else:
        symbol = st.text_input("M3 股票代码", "600000")
        source_label = st.selectbox("M3 股票行情源", list(SOURCES), index=1)
        st.caption("复用M1/M2已入库真实行情；新增股票历史可在M1/M2主动采集后返回。")
    if st.button("查询真实市场宽度快照", key="m3-breadth", disabled=read_only):
        _collect("m3-breadth-status", lambda: collect_public(root, "breadth", "market"))
    st.caption("宽度来源为乐咕乐股当前快照，只用于其实际统计日期，不回填到其他日期。")
    if "m3-price-status" in st.session_state:
        st.caption(st.session_state["m3-price-status"])
    if "m3-breadth-status" in st.session_state:
        st.caption(st.session_state["m3-breadth-status"])

    wave, sentiment, frame, breadth = None, None, None, pd.DataFrame()
    price_error = None
    try:
        if target_kind == "指数":
            items = snapshots(root, kind="index", symbol=symbol, analysis_date=day)
            if items:
                frame = price_frame(max(items, key=lambda x: x["observed_at"]))
        else:
            request = make_request(symbol, analysis_date-timedelta(days=800), analysis_date)
            frame = read_bars(db, request, source=SOURCES[source_label], as_of=as_of)
            if not frame.empty:
                frame = _visible(frame, day, as_of)
                frame["observed_at"] = frame.apply(lambda r: max(r.ingested_at, r.available_at, key=pd.Timestamp), axis=1)
        breadth = breadth_frame(snapshots(root, kind="breadth", symbol="market", analysis_date=day))
        if frame is not None and not frame.empty:
            wave = wave_scenarios(frame, analysis_date=day, as_of=as_of)
            sentiment = fear_greed(frame, analysis_date=day, as_of=as_of, breadth=breadth)
    except Exception as exc:
        price_error = f"数据不足或校验失败：{type(exc).__name__}: {exc}"

    st.subheader("A · CFFEX会员持仓")
    variety = st.selectbox("股指期货品种", ["IF", "IH", "IC", "IM"])
    cffex_status = f"m3-cffex-status:{variety}:{day}"
    if st.button("查询该日真实CFFEX榜单", key="m3-cffex", disabled=read_only):
        _collect(cffex_status, lambda: collect_cffex(root, variety, day))
    if cffex_status in st.session_state:
        st.caption(st.session_state[cffex_status])
    futures_direction = "数据不足"
    futures_reason = "没有该日期的HTTPS真实观察；权威日历及available_at未认证。"
    try:
        history = snapshots(root, kind="cffex", symbol=variety, analysis_date=day)
        exact = [x for x in history if x["trade_date"] == day]
        if not exact:
            st.info("数据不可用：当前品种与指定日期没有已保存榜单；可主动查询。缺文件不代表休市或零持仓。")
        else:
            item = exact[-1]
            rows = ranking_rows(item)
            contract = st.selectbox("合约范围（单合约，禁止默认跨月相加）", item["contracts"], format_func=contract_label)
            scope_name = st.selectbox("会员口径", ["代客", "自营", "代客+自营", "unknown"])
            scope = MemberScope(scope_name)
            names = sorted({r.member for r in rows if r.contract == contract and r.member and r.member_scope == scope})
            if not names:
                names = ["中信期货(代客)" if scope == MemberScope.AGENT else "中信期货(自营)"]
            selected = next((i for i, v in enumerate(names) if v.startswith("中信期货")), 0)
            member = st.selectbox("会员（默认中信期货）", names, index=selected)
            p = member_position(rows, contract=contract, member=member, scope=scope)
            a, b = st.columns(2)
            a.metric("多头持仓（供应商计数）", _value(p["long"]))
            b.metric("空头持仓（供应商计数）", _value(p["short"]))
            a, b = st.columns(2)
            a.metric("净持仓", _value(p["net"]))
            b.metric("净变化（榜单公布变化之差）", _value(p["net_change"]))
            raw_direction = "数据不足" if p["net"] is None else "偏多" if p["net"] > 0 else "偏空" if p["net"] < 0 else "中性"
            st.write("原始席位净额方向：", raw_direction)
            st.warning("换月提示：当前只展示选定合约；到期月份来自合约代码，准确到期日与换月日未认证。到期合约真实0持仓不自动判为换月；不拼接跨月趋势。")
            st.caption(f"交易日 {item['trade_date']}｜采集/保存观察 {item['observed_at']}｜状态 {item['status']}｜可用时间 UNKNOWN")
            st.info("权威CFFEX日历尚未接入，原始榜单与派生净额仅供本地观察；不冒充正式可见持仓记录，不纳入综合方向。合并口径不支持则UNKNOWN。")
            futures_reason = f"{contract} {member} {scope_name} {day}：原始净额{_value(p['net'])}，方向{raw_direction}；available_at未知，综合证据不足。"
            values = {}
            for previous in history:
                if contract in previous["contracts"]:
                    position = member_position(ranking_rows(previous), contract=contract, member=member, scope=scope)
                    values[previous["trade_date"]] = dict(交易日=previous["trade_date"], 多头=position["long"], 空头=position["short"],
                        净额=position["net"], 多头排名=position["long_rank"], 空头排名=position["short_rank"], 成交排名=position["volume_rank"])
            trend = pd.DataFrame(values.values())
            if len(trend) >= 2:
                st.line_chart(trend.set_index("交易日")[["多头", "空头", "净额"]])
                st.line_chart(trend.set_index("交易日")[["多头排名", "空头排名", "成交排名"]])
            else:
                st.info(f"历史覆盖不足：同合约/会员/口径仅{len(trend)}个真实日期，至少2个才画变化曲线。")
            ranking = pd.DataFrame([dict(排名=r.rank, 侧别=r.side.value, 会员=r.member, 口径=r.member_scope.value,
                       数量=r.volume if r.side.value == "volume" else r.open_interest,
                       变化=r.volume_change if r.side.value == "volume" else r.open_interest_change)
                       for r in rows if r.contract == contract])
            st.dataframe(ranking.loc[ranking["会员"] == member], hide_index=True, use_container_width=True)
            with st.expander("完整成交/多头/空头排名与原始证据"):
                st.dataframe(ranking, hide_index=True, use_container_width=True)
                st.dataframe(trend, hide_index=True, use_container_width=True)
                st.json({k: v for k, v in item.items() if k != "raw_csv_hex"})
    except Exception as exc:
        st.error(f"持仓数据不可用/校验失败：{type(exc).__name__}；未显示未经校验的数据。")

    st.subheader("B · 波浪趋势情景")
    if price_error:
        st.error(price_error)
    if wave is None:
        st.info("数据不足：请查询真实指数，或选择M1/M2已有行情的股票。日线方向需60条，转折确认至少7条，周趋势需20个已结束周。")
    else:
        f = wave["frame"]
        st.caption(f"{f.symbol.iloc[-1]}｜{f.source.iloc[-1]}｜{f.trade_date.min()}～{f.trade_date.max()}，{len(f)}条｜观察时间{f.observed_at.max()}")
        if f.trade_date.iloc[-1] != day:
            st.warning(f"所选日期无该日行情；实际截止 {f.trade_date.iloc[-1]}，不能当作{day}市场证据。")
        st.write(f"日线：{wave['direction']}；已结束周样本：{wave['weekly_direction']}。交易日完整性未认证。")
        st.line_chart(f.set_index("trade_date")[["close", "MA20", "MA60"]])
        pivots = wave["pivots"]
        if not pivots.empty:
            st.scatter_chart(pivots, x="trade_date", y="price", color="kind")
        else:
            st.info("尚无已确认关键转折。")
        if len(wave["weekly"]) >= 2:
            weeks = wave["weekly"].copy()
            weeks.index = weeks.index.astype(str)
            st.line_chart(weeks[["close"]])
        if not wave["scenarios"].empty:
            st.dataframe(wave["scenarios"], hide_index=True, use_container_width=True)
        else:
            st.info(f"情景历史不足：当前{len(f)}条，日线情景需60条。")
        with st.expander("关键转折、斐波那契回撤与数据明细"):
            st.dataframe(pivots, hide_index=True, use_container_width=True)
            st.dataframe(wave["fibonacci"], hide_index=True, use_container_width=True)
            st.dataframe(f, hide_index=True, use_container_width=True)

    st.subheader("C · 市场恐贪（实验性研究指标）")
    sentiment_direction = "数据不足"
    sentiment_reason = "没有足够真实行情与市场因子。"
    wave_direction = "数据不足"
    if sentiment is None:
        st.info("数据不足：至少41条真实价格才能计算前三个因子；完整分数另需同日市场家数与成交额历史。")
    else:
        latest = sentiment.iloc[-1]
        a, b = st.columns(2)
        a.metric("全市场完整分数", "数据不足" if pd.isna(latest.score) else f"{latest.score:.1f} · {emotion(latest.score)}")
        b.metric("因子权重覆盖率", f"{latest.coverage:.0%}")
        a, b = st.columns(2)
        a.metric("指数/个股价格代理（独立口径）", "数据不足" if pd.isna(latest.index_proxy) else f"{latest.index_proxy:.1f} · {emotion(latest.index_proxy)}")
        b.metric("代理历史分位（此前252条）", "数据不足" if pd.isna(latest.proxy_percentile) else f"{latest.proxy_percentile:.1f}%")
        missing = [k for k in WEIGHTS if pd.isna(latest[k])]
        if missing:
            st.warning("完整恐贪数据不足；缺失因子："+"、".join(missing)+"。价格代理不能代表全市场恐贪，不进入综合情绪方向。")
        st.dataframe(pd.DataFrame([dict(因子=k, 固定权重=w, 数值=None if pd.isna(latest[k]) else latest[k],
                    完整分贡献=None if pd.isna(latest[k]) else latest[k]*w) for k, w in WEIGHTS.items()]), hide_index=True, use_container_width=True)
        if sentiment.index_proxy.notna().sum() >= 2:
            st.line_chart(sentiment.set_index("trade_date")[["index_proxy"]])
            st.caption("价格代理历史曲线，仅为固定65%因子的单独归一化结果，未补齐全市场分数。")
        if sentiment.score.notna().sum() >= 2:
            st.line_chart(sentiment.set_index("trade_date")[["score"]])
        else:
            st.info("完整情绪历史不足2个真实日期，不绘制完整分数曲线。")
        if sentiment.percentile.notna().any():
            st.write("完整分数历史分位：", float(latest.percentile))
        if len(sentiment) >= 6 and sentiment.index_proxy.iloc[-6:].notna().all():
            price_change = latest.close/sentiment.close.iloc[-6]-1
            score_change = latest.index_proxy-sentiment.index_proxy.iloc[-6]
            st.write(f"5条价格变化 {price_change:.2%}；同口径代理变化 {score_change:+.2f}；"+
                     ("价格与代理背离（描述性）" if price_change*score_change < 0 else "未见该窗口背离"))
        outcomes = extreme_outcomes(sentiment)
        if outcomes.empty:
            st.info("极端情绪后表现：历史样本不足；每个窗口至少20个互相隔离的已完成事件才展示，不用代理样本冒充。")
        else:
            st.dataframe(outcomes, hide_index=True, use_container_width=True)
        if not breadth.empty:
            with st.expander("真实市场家数与统计日期"):
                st.dataframe(breadth, hide_index=True, use_container_width=True)
        is_current = latest.trade_date == day
        if not pd.isna(latest.score) and is_current and target_kind == "指数":
            sentiment_direction = "偏多" if latest.score > 60 else "偏空" if latest.score < 40 else "中性"
        if is_current and wave:
            wave_direction = wave["direction"]
        sentiment_reason = f"行情截止{latest.trade_date}；完整分数{emotion(latest.score)}，覆盖率{latest.coverage:.0%}；来源与因子明细见上。"
    with summary:
        st.subheader("综合市场环境")
        st.metric("综合结论", environment(futures_direction, wave_direction, sentiment_direction))
        st.write(f"期货席位：{futures_direction}｜波浪趋势：{wave_direction}｜市场恐贪：{sentiment_direction}")
        if sentiment is not None and pd.notna(sentiment.index_proxy.iloc[-1]):
            st.write(f"价格代理情绪：{sentiment.index_proxy.iloc[-1]:.1f} / 100（实验性，覆盖{sentiment.coverage.iloc[-1]:.0%}）")
        with st.expander("综合结论的逐项日期、原始数据与依据"):
            st.dataframe(pd.DataFrame([
                dict(证据="期货席位", 方向=futures_direction, 依据=futures_reason),
                dict(证据="波浪趋势", 方向=wave_direction, 依据="多情景并存；MA与确认转折见B；"+f"分析日{day}"),
                dict(证据="市场恐贪", 方向=sentiment_direction, 依据=sentiment_reason),
            ]), hide_index=True, use_container_width=True)
        st.caption("不同证据可冲突；任一未认证或缺失则不形成完整方向。净空席位也可能用于套保。")
    with st.expander("数据来源、时间边界与完整计算依据"):
        st.code(RULES, language="text")
        st.write("原始榜单：https://www.cffex.com.cn/ccpm/；指数：https://finance.sina.com.cn/；市场家数：https://legulegu.com/stockdata/market-activity")
        st.write("行情SQLite、M3原始观察文件与图表可读回；观察时间不是历史首次可用时间。指数/宽度无正式available_at，不进入策略或回测。")
        st.write("授权：本地个人研究展示；商业使用、对外展示与再分发授权未确认。远程服务默认关闭M3在线查询；启用前需真实授权及HTTPS访问控制。")

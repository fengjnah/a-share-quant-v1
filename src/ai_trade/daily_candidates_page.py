"""M4 daily workbench. Tables and details share one bounded analysis snapshot."""
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from ai_trade.daily_candidates import LIMITATIONS, STRATEGIES, score_rows, table_row
from ai_trade.daily_candidates_data import load_batch, local_coverage
from ai_trade.demo_data import SOURCES
from ai_trade.market_state import MARKET_MODES
from ai_trade.storage.db import Database, DatabaseConfig
from ai_trade.trading_analysis import FORMULAS, risk_reference


@st.cache_data(ttl=300, max_entries=16, show_spinner=False)
def _cached_batch(path, journal_mode, fingerprint, source, analysis_date, as_of, strategy, market_mode, symbol, equity):
    db = Database(DatabaseConfig(Path(path), environment="test", journal_mode=journal_mode))
    return load_batch(db, source=source, analysis_date=analysis_date, as_of=as_of,
                      strategy=strategy, market_mode=market_mode, symbol=symbol, equity=equity)


def _fingerprint(path):
    return tuple((p.stat().st_mtime_ns, p.stat().st_size) if p.exists() else None
                 for p in (path, Path(str(path)+"-wal")))


def render(db):
    st.title("M4 每日选股")
    st.caption("本地真实行情 · 每日最新可用日期 · 最多5只候选 · 研究参考，不自动下单")
    source_label = st.selectbox("选股行情来源", list(SOURCES), index=1, key="m4_source")
    source = SOURCES[source_label]
    now = datetime.now(timezone.utc).isoformat()
    try:
        coverage, dates = local_coverage(db, source=source, as_of=now)
    except Exception as exc:
        st.error(f"本地股票池读取失败：{type(exc).__name__}: {exc}")
        return
    if not dates:
        st.info("数据不足：当前来源没有可见的本地行情，今日无合格候选。请在 M1/M2 主动采集真实行情。")
        return
    with st.form("m4-controls"):
        analysis_date = st.selectbox("选股分析日期", dates, help="仅列出本地真实可见行情日期，不把缺失日当休市")
        left, right = st.columns(2)
        strategy = left.selectbox("策略模式", STRATEGIES)
        market_mode = right.selectbox("市场状态过滤模式", MARKET_MODES)
        pool = st.selectbox("股票池范围", ("本地同源A股（最多20只）", "指定股票"))
        symbol = st.text_input("指定股票代码", "", placeholder="例如 600000；仅分析已有本地行情")
        equity_text = st.text_input("账户权益（元，可留空）", "")
        st.caption("单笔最大风险1%。严格：日线多头＋至少一种M2量价形态；趋势确认：日线多头。所有正式准入门禁保持一致。")
        submitted = st.form_submit_button("生成每日候选", type="primary")
    identity = (str(db.config.path), source, datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat())
    if submitted or st.session_state.get("m4_identity") != identity:
        st.session_state.pop("m4_batch", None)
        try:
            equity = float(equity_text) if equity_text.strip() else None
            risk_reference(1.0, None, None, equity)
            if pool == "指定股票" and not symbol.strip():
                raise ValueError("指定股票模式必须填写代码")
            with st.spinner("正在读取本地可见行情并复用 M2 计算……"):
                batch = _cached_batch(str(db.config.path), db.config.journal_mode, _fingerprint(db.config.path), source,
                                      analysis_date, now, strategy, market_mode,
                                      symbol if pool == "指定股票" else "", equity)
            st.session_state.m4_batch = batch
            st.session_state.m4_identity = identity
        except Exception as exc:
            st.error(f"未生成结果：{type(exc).__name__}: {exc}")
            return
    batch = st.session_state.get("m4_batch")
    if batch is None:
        st.info("请重新生成每日候选。")
        return
    st.caption(f"结果快照：{batch.analysis_date} · {batch.strategy} · {batch.market_mode}；系统读取 {batch.as_of}")
    st.caption("历史日期是按当时价格截止、在当前时点回看；不代表当时已取得行情或已生成信号。修改控制项后点击生成更新快照。")
    a, b, c = st.columns(3)
    a.metric("合格候选", len(batch.candidates))
    b.metric("本次分析股票", len(batch.evaluations))
    c.metric("市场环境", batch.market.state)
    st.info(f"市场来源：{batch.market.source}；"+"；".join(batch.market.reasons))
    if batch.candidates:
        st.dataframe(pd.DataFrame([table_row(r, i+1) for i, r in enumerate(batch.candidates)]),
                     hide_index=True, use_container_width=True)
    else:
        st.warning("今日无合格候选（0只）。市场或证券状态未知时不放宽条件、不补足数量。")
    st.subheader("股票池研究评分与排除原因")
    st.dataframe(pd.DataFrame([table_row(r, i+1) for i, r in enumerate(batch.evaluations)]),
                 hide_index=True, use_container_width=True)
    st.caption("研究排名包括未准入股票，不是买入名单。分数相同按代码排序；未知总分排在最后。表格可横向滚动，手机可直接看下方股票详情。")
    for warning in batch.warnings:
        st.caption(warning)
    with st.expander("实际执行的筛选与本地覆盖", expanded=False):
        st.dataframe(pd.DataFrame(LIMITATIONS, columns=["筛选条件", "执行状态", "依据/限制"]),
                     hide_index=True, use_container_width=True)
        st.dataframe(pd.DataFrame(coverage), hide_index=True, use_container_width=True)
        st.caption("覆盖为当前来源本地观察范围，未认证逐个交易日完整性。代码范围由已有A股适配器验证。")
    if not batch.evaluations:
        return
    selected = st.selectbox("查看股票详情（含被排除股票）", [r.symbol for r in batch.evaluations], key="m4_detail")
    row = next(r for r in batch.evaluations if r.symbol == selected)
    st.subheader(f"{row.symbol} · {row.name}")
    if row.analysis is None:
        st.error("；".join(row.exclusions))
        return
    s, frame = row.analysis.summary, row.analysis.frame
    st.write(f"分析日期 {s['analysis_date']}；最新行情 {s['latest_trade_date']}；历史 {s['first_trade_date']} 起，共 {s['count']} 条。")
    st.caption(f"信号生成/最早可用 {s['signal_available_at']}；不得回填至所属日盘中或按当日收盘成交。下一可执行会话未知。")
    st.write("入选条件：", "、".join(k for k, v in s["conditions"].items() if v is True) or "无")
    st.write("未满足/未知：", "、".join(k for k, v in s["conditions"].items() if v is not True) or "无")
    st.write("排除/风险：", "；".join(row.exclusions) or "无")
    st.write("日线：", s["trend"], "；周样本：", s["weekly_sample_trend"], "（仅研究，正式周线门禁未知）")
    st.write("研究评分：", "未知" if row.score is None else row.score)
    st.dataframe(pd.DataFrame(score_rows(row)), hide_index=True, use_container_width=True)
    last = frame.iloc[-1]
    previous = frame.iloc[-2] if len(frame) > 1 else None
    def display(value):
        return "未知" if value is None or pd.isna(value) else f"{float(value):.4f}"
    st.write(f"日线依据：收盘 {display(last.close)}；MA5/10/20/60 = "+
             " / ".join(display(last[f"MA{n}"]) for n in (5, 10, 20, 60))+"；要求依次严格大于。")
    st.write(f"突破依据：收盘>{display(last['前20条最高价'])}（前20条最高价），量比 {display(last['量比5'])}≥1.5。")
    st.write(f"回调依据：收盘<{display(previous.close if previous is not None else None)}（前收），最低 {display(last.low)}≤MA20 {display(last.MA20)}≤收盘，量比≤0.7。")
    st.write(f"穿三线依据：开盘 {display(last.open)} 低于前一日MA5/10/20的全部值，收盘高于其全部值，且收盘>开盘。前一日均线："+
             " / ".join(display(previous[f"MA{n}"] if previous is not None else None) for n in (5, 10, 20)))
    st.caption("上述为独立M2形态；二次突破、突破后再回调的先后关联未实现，不作为已满足条件。")
    st.subheader("历史价格、均线与成交量")
    chart = frame.set_index("trade_date")
    if len(frame) >= 2:
        st.line_chart(chart[["close", "MA5", "MA10", "MA20", "MA60"]])
        st.bar_chart(chart[["volume_shares"]])
    else:
        st.info("真实行情不足2条，不能绘制价格趋势。")
    if frame.ATR14.notna().any():
        st.line_chart(chart[["ATR14"]])
    else:
        st.info("ATR14数据不足，至少需要15条真实行情。")
    st.write("最新指标：", s["metrics"])
    st.subheader("交易计划与1%风险预算")
    risk = row.risk
    for label, value in [("参考测算价（所属日收盘）", risk["reference_entry"]),
                         ("结构止损（前10条最低价）", risk["structure_stop"]),
                         ("ATR止损（收盘−2×ATR14）", risk["atr_stop"]),
                         ("最终研究止损", risk["final_stop"]), ("账户权益", risk["equity"]),
                         ("1%参考风险金额", risk["risk_budget"])]:
        st.write(label+"：", "未知/未配置" if value is None else round(value, 4))
    st.caption(risk["stop_reason"])
    st.info(risk["sizing_reason"])
    st.write("理论股数 / 仓位：不输出；风险收益比：未知（未定义已验证目标价，不编造收益）。")
    st.write("参考入场条件：指标可用后，下一已验证可交易会话重新确认趋势、形态、状态与价格；收盘价仅为风险测算基准，不保证成交。")
    st.write("失效条件：入场时趋势/形态失效、跌破研究止损、市场转弱/证据冲突/数据缺失时，不继续使用该计划。T+1、交易单位、涨跌停、停牌、费用和滑点须先验证。")
    with st.expander("计算依据与同一快照明细"):
        st.text(FORMULAS)
        st.write("实际来源：", s["source"], "；规则：", s["rule_version"])
        st.write("行情快照摘要：", s["snapshot_sha256"], "；血缘：", s["lineage_refs"])
        st.dataframe(frame, hide_index=True, use_container_width=True)

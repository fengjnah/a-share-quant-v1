"""M2 view: explicit collection, local-only analysis, no order or prediction API."""
from dataclasses import asdict
from datetime import date, datetime, timezone
import uuid

import pandas as pd
import streamlit as st

from ai_trade.demo_data import SOURCES, make_request, read_bars, verify_written
from ai_trade.market_data.akshare_adapter import AkshareDailyClient
from ai_trade.market_data.tx_adapter import TxDailyClient
from ai_trade.market_data.ingestor import DailyHistoryIngestor
from ai_trade.market_data.evidence import EvidenceStore
from ai_trade.market_data.models import DailyHistoryRequest
from ai_trade.data_access.repository import SQLiteMarketDataRepository
from ai_trade.storage.db import Database
from ai_trade.trading_analysis import FORMULAS, analyze, candidate_row


def _clicked():
    st.session_state.m2click = st.session_state.get("m2click", 0) + 1


def render(db: Database) -> None:
    st.title("M2 交易分析")
    st.caption("仅研究展示 · 不自动下单 · 所有指标按同一行情截止日及系统可见时点计算")
    st.warning("评分未做历史预测能力验证。腾讯为候选源；不复权数据可能受公司行为影响。数据未知不能当作股票池或交易条件通过。")
    with st.form("m2-analysis"):
        source_choice = st.selectbox("分析数据源", list(SOURCES), index=1)
        symbol = st.text_input("分析股票代码", "600000")
        left,right = st.columns(2)
        start = left.date_input("历史起始日", date(2026,1,1))
        end = right.date_input("分析日期", date(2026,10,15))
        equity_text = st.text_input("账户权益（元，可留空）", "")
        pool = st.checkbox("同时评分当前本地同源股票池（最多20只）")
        local = st.form_submit_button("分析本地真实行情", type="primary")
        live = st.form_submit_button("采集该股历史行情并分析", on_click=_clicked)
        st.caption("本地分析不联网。采集按钮只请求指定股票及历史区间，不自动重试/换源；重复记录由已有约束拒绝。")
    click = st.session_state.get("m2click", 0)
    collect = live and click > st.session_state.get("m2processed", 0)
    if local or collect:
        if collect:
            st.session_state.m2processed = click
        st.session_state.pop("m2spec", None)
        try:
            request = make_request(symbol,start,end)
            equity = float(equity_text) if equity_text.strip() else None
            # Validate money even when a symbol has no stored records.
            from ai_trade.trading_analysis import risk_reference
            risk_reference(1.0,None,None,equity)
            if collect:
                client = TxDailyClient() if source_choice.startswith("腾讯") else AkshareDailyClient()
                with st.spinner("正在通过现有适配器采集并校验历史行情……"):
                    result = DailyHistoryIngestor(client,SQLiteMarketDataRepository(db),
                        EvidenceStore(db.config.path.parent/"evidence"),timeout=10).collect(request,run_id=f"m2-{uuid.uuid4().hex}")
                st.write("采集状态：",result.status.value)
                st.write("返回 / 插入：", str(result.returned_rows) if result.observed_at else "未知", "/",result.inserted_rows)
                st.write("HTTP 状态：",result.http_status if result.http_status is not None else "未知 / SDK 未暴露")
                if result.status.value != "success":
                    st.error("；".join(result.issues)+"；未自动切换源，请优先分析已保存的真实行情。")
                    return
                count=verify_written(SQLiteMarketDataRepository(db),result.records)
                st.success(f"逐字段读回一致：{count}行；批次 {result.run_id}")
            st.session_state.m2spec = dict(request=asdict(request),source=SOURCES[source_choice],
                equity=equity,pool=pool,as_of=datetime.now(timezone.utc).isoformat())
        except Exception as exc:
            st.error(f"分析/采集失败：{type(exc).__name__}: {exc}")
            st.caption("核对股票代码、日期顺序、已结束的日期范围与账户权益。没有生成替代行情。")
            return
    # Expose actual local coverage, not assumptions about vendor coverage.
    try:
        with db.connection() as conn:
            coverage = conn.execute("""SELECT i.symbol, min(b.trade_date) AS first_date,
                max(b.trade_date) AS last_date,count(DISTINCT b.trade_date) AS observations
                FROM daily_bars b JOIN instruments i ON i.instrument_id=b.instrument_id
                JOIN daily_bar_versions v ON v.bar_id=b.bar_id WHERE v.source=?
                GROUP BY i.symbol ORDER BY i.symbol""",(SOURCES[source_choice],)).fetchall()
        st.caption("本地同源覆盖（不是完整交易日认证）："+"；".join(
            f"{r['symbol']} {r['first_date']}～{r['last_date']} / {r['observations']}条" for r in coverage))
    except Exception as exc:
        st.error(f"SQLite 覆盖查询失败：{type(exc).__name__}")
        return
    if "m2spec" not in st.session_state:
        st.info("选择日期并点击本地分析；MA60/完整技术评分需60条，ATR14需15条。历史不足时可主动采集。")
        return
    spec=st.session_state.m2spec
    request=DailyHistoryRequest(**spec["request"])
    try:
        frame=read_bars(db,request,source=spec["source"],as_of=spec["as_of"])
        with st.spinner("正在按同一截止日计算指标与研究条件……"):
            result=analyze(frame,analysis_date=request.end_date,as_of=spec["as_of"],equity=spec["equity"])
    except Exception as exc:
        st.error(f"数据不足或校验未通过：{type(exc).__name__}: {exc}")
        return
    s=result.summary
    st.subheader(f"{s['symbol']} · 截至 {s['latest_trade_date']}")
    st.write("实际来源：",s["source"])
    st.write(f"历史：{s['first_trade_date']}～{s['latest_trade_date']}，{s['count']}条；最新入库：{s['latest_ingested_at']}")
    st.caption(f"规则 {s['rule_version']}；系统读取/计算时点 {s['calculated_at']}；本次指标最早可用 {s['signal_available_at']}。不回填为历史当日盘中信号。")
    st.info("基础OHLCV与时间字段校验通过；交易日覆盖/公司行为未认证。当前周不进入周样本趋势，缺失交易日不补值。")
    cols=st.columns(6)
    for col,key in zip(cols,["MA5","MA10","MA20","MA60","ATR14","量比5"]):
        value=s["metrics"][key]
        col.metric(key,"数据不足" if value is None else f"{value:.4f}")
    f=result.frame
    st.subheader("价格与均线（元）")
    if len(f)>=2:
        present=[k for k in ["MA5","MA10","MA20","MA60"] if f[k].notna().any()]
        st.line_chart(f.set_index("trade_date")[["close"]+present])
    else:
        st.info("不足2条，不绘制价格走势。")
    left,right=st.columns(2)
    with left:
        st.subheader("成交量（股）与量比5")
        st.bar_chart(f.set_index("trade_date")[["volume_shares"]])
        st.write("最新成交量状态：",s["volume_state"])
    with right:
        st.subheader("ATR14（元）")
        if f.ATR14.notna().any(): st.line_chart(f.set_index("trade_date")[["ATR14"]])
        else: st.info(f"ATR14需15条，目前{s['count']}条。")
    st.subheader("形态、周样本与市场环境")
    for name,value in s["conditions"].items():
        st.write(name+"：", "数据不足" if value is None else "满足" if value else "未满足")
    st.write("最近满足形态的行情日：",s["last_occurrences"])
    st.write("周样本趋势：",s["weekly_sample_trend"],f"（{s['weekly_count']}个过往周样本；正式周线过滤未知）")
    st.info("市场环境：数据不足。当前没有已验证主要指数/全市场覆盖及该日涨跌家数、涨跌停数据，不能用本股推断偏强、震荡或偏弱。")
    st.subheader("股票池评分与排除原因")
    rows=[candidate_row(result)]
    if spec["pool"]:
        with db.connection() as conn:
            symbols=[r[0] for r in conn.execute("""SELECT DISTINCT i.symbol FROM instruments i
                JOIN daily_bars b ON b.instrument_id=i.instrument_id JOIN daily_bar_versions v ON v.bar_id=b.bar_id
                WHERE v.source=? ORDER BY i.symbol LIMIT 21""",(spec["source"],))]
        if len(symbols)>20: st.warning("本次仅分析本地股票池前20只，不进行全市场扫描。")
        for code in symbols[:20]:
            if code==request.symbol: continue
            try:
                req=make_request(code,date.fromisoformat(request.start_date),date.fromisoformat(request.end_date))
                other=analyze(read_bars(db,req,source=spec["source"],as_of=spec["as_of"]),
                    analysis_date=request.end_date,as_of=spec["as_of"],equity=spec["equity"])
                rows.append(candidate_row(other))
            except Exception as exc:
                rows.append({"股票代码":code,"信号状态":"数据不足","候选准入":"未通过","排除原因":str(exc)})
    st.dataframe(pd.DataFrame(rows),hide_index=True,use_container_width=True)
    st.warning("正式候选 0 只：市场、历史ST/市值、交易状态、日历与公司行为门禁未验收。研究评分不是预测胜率，不为凑数补股票。")
    st.subheader("入场与止损研究参考")
    st.write("研究信号：",s["signal_state"],"；正式入场条件未通过。")
    st.write("参考价格所属日：",s["latest_trade_date"])
    st.json(result.risk)
    st.caption("未配置权益时仅给1%公式，不填资金或数量。止损条件不适用时为null，不擅自替换。理论股数未按交易单位取整，不是下单数量。")
    st.error("执行限制：不得早于指标可用时点，也不得按所属日收盘回填成交；下一可交易会话未确认。T+1、停牌、涨跌停、交易单位、费用滑点须另验。")
    with st.expander("公式、参数及实际计算明细"):
        st.text(FORMULAS)
        st.dataframe(f,hide_index=True,use_container_width=True)

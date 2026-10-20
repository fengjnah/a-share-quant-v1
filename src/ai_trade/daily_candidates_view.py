"""Read-only M4 presentation projections. No strategy or stage inference."""
from datetime import date
import re

import pandas as pd

from ai_trade.daily_candidates import CandidateBatch, Evaluation, sort_evaluations
from ai_trade.daily_candidates_data import MAX_SYMBOLS, load_batch
from ai_trade.market_state import MarketState

VIEWS = ("每日交易总览", "六阶段选股监控", "每日精选", "股票详情", "指定股票分析", "风险与持仓监控")
STAGES = (
    ("S0", "低位启动候选", "已认证周K低位多头与低位定义"),
    ("S1", "首次放量启动", "首次/天量换手的阈值和前序状态"),
    ("S2", "缩量横盘整理", "整理持续交易日、区间与回撤限制"),
    ("S3", "二次放量突破", "首次→整理→二次放量的顺序状态与B点"),
    ("S4", "次日入场评估", "次日会话、跳空限制与可交易状态"),
    ("S5", "5日线趋势持仓", "持仓来源、入场记录与MA5持仓状态"),
    ("S6", "退出或失效", "止损/整理失败/连续两个交易日跌破MA5的退出记录"),
)


def number(value):
    return None if value is None or pd.isna(value) else float(value)


def symbols_input(raw: str) -> tuple[str, ...]:
    codes = tuple(dict.fromkeys(x.upper() for x in re.split(r"[\s,，;；]+", raw.strip()) if x))
    if not codes or len(codes) > MAX_SYMBOLS:
        raise ValueError(f"请输入1–{MAX_SYMBOLS}个代码，以空格、逗号或换行分隔")
    return codes


def load_watch_batch(db, *, symbols: tuple[str, ...], **spec) -> CandidateBatch:
    """Compose existing single-symbol requests; retain each failure and rejected stock."""
    rows, market = [], MarketState(spec["analysis_date"])
    for symbol in symbols:
        try:
            batch = load_batch(db, symbol=symbol, **spec)
            rows.extend(batch.evaluations)
            market = batch.market
        except Exception as exc:
            rows.append(Evaluation(symbol, exclusions=[f"指定股票分析失败：{type(exc).__name__}: {exc}"]))
    unique = {row.symbol: row for row in rows}
    return CandidateBatch(spec["analysis_date"], spec["as_of"], spec["strategy"], spec["market_mode"],
                          market, sort_evaluations(list(unique.values())), ["指定股票结果不受自动精选分数门槛隐藏"])


def data_status(batch: CandidateBatch, *, today: str) -> dict:
    date.fromisoformat(today)
    analyses = [r.analysis for r in batch.evaluations if r.analysis is not None]
    if not analyses:
        return dict(state="数据不足", latest=None, oldest=None, updated=None, sources=[], synthetic=False)
    dates = [r.summary["latest_trade_date"] for r in analyses]
    synthetic = any(any("synthetic" in str(v).lower() for v in r.frame[column])
                    for r in analyses for column in ("source", "source_version", "run_id"))
    state = "离线演示（合成测试数据）" if synthetic else "数据过期 / 历史快照" if min(dates) < today else "真实行情 / 筛选字段部分缺失"
    return dict(state=state, latest=max(dates), oldest=min(dates),
                updated=max(r.summary["latest_ingested_at"] for r in analyses),
                sources=sorted({r.summary["source"] for r in analyses}), synthetic=synthetic)


def monitor_row(row: Evaluation) -> dict:
    s = row.analysis.summary if row.analysis else {}
    close, metrics = s.get("close"), s.get("metrics", {})
    def relation(n):
        ma = metrics.get(f"MA{n}")
        return "未知" if close is None or ma is None else f"{close:.4f} {'>' if close > ma else '<' if close < ma else '='} {ma:.4f}"
    return {"股票代码": row.symbol, "名称": row.name, "行业": "未知（历史行业未接入）",
            "当前阶段": "阶段待识别", "阶段进入日期": None, "持续交易日数": None,
            "量比5（倍）": metrics.get("量比5"), "收盘/MA5": relation(5),
            "收盘/MA10": relation(10), "收盘/MA20": relation(20),
            "整理区间上沿": None, "整理区间下沿": None, "B点": "尚未计算",
            "下一阶段条件": "依赖M2正式顺序状态机；独立形态不能替代阶段确认",
            "技术研究评分": row.score, "综合评分": None,
            "未通过原因": "；".join(row.exclusions), "行情日期": s.get("latest_trade_date"),
            "数据更新时间": s.get("latest_ingested_at")}


def risk_row(row: Evaluation) -> dict:
    risk, s = row.risk, row.analysis.summary if row.analysis else {}
    close, stop = s.get("close"), risk.get("final_stop")
    distance = close-stop if close is not None and stop is not None else None
    ma = s.get("metrics", {}).get("MA5")
    state = "数据不足" if close is None or ma is None else "收盘高于MA5" if close > ma else "收盘低于MA5" if close < ma else "收盘等于MA5"
    return {"股票代码": row.symbol, "数据类型": "行情派生研究，非真实持仓", "行情日期": s.get("latest_trade_date"),
            "初始结构止损": None, "当前结构止损": risk.get("structure_stop"),
            "ATR止损": risk.get("atr_stop"), "研究止损参考": stop,
            "收盘至研究止损（元/股）": distance,
            "收盘至研究止损（%）": 100*distance/close if distance is not None else None,
            "MA5位置观察": state, "连续收盘跌破MA5交易日数": None,
            "账户风险上限": "1%", "参考风险金额（元）": risk.get("risk_budget"),
            "理论股数": risk.get("theoretical_shares"), "真实持仓风险": None}


def events(row: Evaluation) -> pd.DataFrame:
    columns = ["行情日期", "独立M2条件", "收盘价", "指标可用时间"]
    if row.analysis is None:
        return pd.DataFrame(columns=columns)
    f = row.analysis.frame
    records = []
    for kind in ("放量突破", "缩量回调", "一阳穿三线"):
        for _, bar in f.loc[f[kind].fillna(False)].iterrows():
            records.append({"行情日期": bar.trade_date, "独立M2条件": kind,
                            "收盘价": float(bar.close), "指标可用时间": bar["指标可用时间"]})
    return pd.DataFrame(records, columns=columns).sort_values("行情日期")

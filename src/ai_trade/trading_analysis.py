"""Versioned research-demo calculations; no execution, prediction or DB writes."""
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import math
from numbers import Real
from zoneinfo import ZoneInfo

import pandas as pd

from ai_trade.data_access.validation import iso_date, timestamp, text_field

RULE_VERSION = "m2-research-v1"
WEIGHTS = {"日线趋势": 40, "放量突破": 25, "缩量回调": 20, "一阳穿三线": 15}
FORMULAS = """研究规则 m2-research-v1（未做历史预测能力验证）：
MA(n)=最近 n 条收盘价均值，n=5/10/20/60，不补缺失；ATR14 需要 15 条行情。
TR=max(H-L,abs(H-前收),abs(L-前收))；前14个有效TR均值为种子，随后 ATR=(前ATR×13+TR)/14。
均量基准=前5条成交量均值（排除当日）；放量≥1.5倍，缩量≤0.7倍；量比≥10暂列异常，不生成信号。
日线趋势：C>MA5>MA10>MA20>MA60；放量突破：C>前20条最高价且放量。
缩量回调：C<前收、L≤当日MA20≤C且缩量；一阳穿三线：O<前一日MA5/10/20最小值、C>其最大值且C>O。
研究评分：日线趋势40、突破25、回调20、穿三线15；任一条件未知则总分未知，不按0填补。
周样本：仅用分析日所在周之前的日历周，比较周末观察值的MA5/MA20；未认证交易日完整性，不通过正式周线门禁。
结构止损=前10条最低价；ATR止损=所属日收盘-2×ATR14；两者均在(0,收盘)才取较高者。
参考入场仅以所属日收盘测算，不是成交价；风险预算=权益×1%，理论股数=floor(min(预算/(参考价-止损),权益/参考价))。
理论股数未按证券交易单位取整、未计滑点费用，不是订单。停牌、涨跌停、T+1与实际成交条件须另验。
"""


@dataclass
class Analysis:
    frame: pd.DataFrame
    summary: dict
    risk: dict


def _visible(frame: pd.DataFrame, analysis_date: str, as_of: str) -> pd.DataFrame:
    iso_date(analysis_date)
    cutoff = timestamp(as_of, "as_of")
    required = {"symbol", "source", "trade_date", "open", "high", "low", "close", "volume_shares",
                "amount_cny", "event_time", "available_at", "ingested_at", "quality_status", "adjustment_method", "run_id", "source_version"}
    if frame.columns.has_duplicates or not required.issubset(frame.columns):
        raise ValueError("行情列缺失或重复，不能计算。")
    for value in frame.trade_date:
        iso_date(value)
    data = frame.loc[frame.trade_date <= analysis_date].copy().sort_values("trade_date").reset_index(drop=True)
    if data.empty:
        raise ValueError("分析日期之前没有行情。")
    if data.trade_date.duplicated().any() or data.symbol.nunique() != 1 or data.source.nunique() != 1:
        raise ValueError("重复交易日期、混合股票或混合来源不能计算。")
    if not data.quality_status.eq("accepted").all() or not data.adjustment_method.eq("none").all():
        raise ValueError("只接受已校验的不复权行情。")
    for field in ["open", "high", "low", "close", "volume_shares", "amount_cny"]:
        for value in data[field]:
            if isinstance(value, bool) or not isinstance(value, Real) or not math.isfinite(value):
                raise ValueError(f"{field} 缺失或不是有限数值。")
            if value < 0 or (field in {"open", "high", "low", "close"} and value == 0):
                raise ValueError(f"{field} 范围不合法。")
            if field == "volume_shares" and (value != int(value) or value > 2**63 - 1):
                raise ValueError("成交量必须为非负 int64 股数。")
    if not ((data.low <= data.open) & (data.open <= data.high) &
            (data.low <= data.close) & (data.close <= data.high)).all():
        raise ValueError("OHLC 关系不合法。")
    for row in data.to_dict("records"):
        for name in ("symbol", "source", "run_id", "source_version"):
            text_field(row[name], name)
        times = {k: timestamp(row[k], k) for k in ["event_time", "available_at", "ingested_at"]}
        if any(v > cutoff for v in times.values()):
            raise ValueError("包含 as_of 时点尚不可见的行情，拒绝提前使用。")
        if times["event_time"] > min(times["available_at"], times["ingested_at"]):
            raise ValueError("可用时间/入库时间早于行情事件。")
        if datetime.fromisoformat(times["event_time"]).astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat() != row["trade_date"]:
            raise ValueError("事件时间与行情交易日不一致。")
        for k, v in times.items():
            data.loc[data.trade_date == row["trade_date"], k] = v
    return data


def indicators(data: pd.DataFrame) -> pd.DataFrame:
    """Causal rolling features; first ATR requires a previous close plus 14 TRs."""
    f = data.copy()
    for n in (5, 10, 20, 60):
        f[f"MA{n}"] = f.close.rolling(n, min_periods=n).mean()
    previous = f.close.shift(1)
    tr = pd.concat([f.high-f.low, (f.high-previous).abs(), (f.low-previous).abs()], axis=1).max(axis=1)
    tr.iloc[0] = float("nan")
    atr = [float("nan")] * len(f)
    if len(f) >= 15:
        atr[14] = float(tr.iloc[1:15].mean())
        for i in range(15, len(f)):
            atr[i] = (atr[i-1] * 13 + tr.iloc[i]) / 14
    f["ATR14"] = atr
    f["前5条均量"] = f.volume_shares.shift(1).rolling(5, min_periods=5).mean()
    f["量比5"] = f.volume_shares / f["前5条均量"].where(f["前5条均量"] > 0)
    f["前20条最高价"] = f.high.shift(1).rolling(20, min_periods=20).max()
    f["结构止损10"] = f.low.shift(1).rolling(10, min_periods=10).min()
    known_volume = (f.volume_shares > 0) & (f.amount_cny > 0) & (f["前5条均量"] > 0) & (f["量比5"] < 10)
    trend = (f.close > f.MA5) & (f.MA5 > f.MA10) & (f.MA10 > f.MA20) & (f.MA20 > f.MA60)
    breakout = (f.close > f["前20条最高价"]) & (f["量比5"] >= 1.5)
    pullback = (f.close < previous) & (f.low <= f.MA20) & (f.MA20 <= f.close) & (f["量比5"] <= .7)
    prior_ma = f[["MA5", "MA10", "MA20"]].shift(1)
    crossing = (f.open < prior_ma.min(axis=1)) & (f.close > prior_ma.max(axis=1)) & (f.close > f.open)
    for name, values, ready in [
        ("日线趋势", trend, f.MA60.notna() & known_volume),
        ("放量突破", breakout, f["前20条最高价"].notna() & known_volume),
        ("缩量回调", pullback, f.MA20.notna() & known_volume),
        ("一阳穿三线", crossing, prior_ma.notna().all(axis=1) & known_volume),
    ]:
        f[name] = values.astype("boolean").where(ready & (f.volume_shares > 0) & (f.amount_cny > 0))
    return f


def risk_reference(close: float, atr: float | None, structure: float | None, equity: float | None) -> dict:
    if not math.isfinite(close) or close <= 0:
        raise ValueError("参考价格必须为正有限数。")
    if equity is not None and (isinstance(equity, bool) or not math.isfinite(equity) or equity <= 0):
        raise ValueError("账户权益必须为正有限数；未配置应留空。")
    atr_stop = close - 2 * atr if atr is not None and atr > 0 else None
    final = max(structure, atr_stop) if (structure is not None and atr_stop is not None
                and 0 < structure < close and 0 < atr_stop < close) else None
    budget = equity * .01 if equity is not None else None
    shares = math.floor(min(budget/(close-final), equity/close)) if budget is not None and final is not None else None
    return dict(reference_entry=close, structure_stop=structure, atr_stop=atr_stop,
                final_stop=final, risk_fraction=.01, equity=equity, risk_budget=budget, theoretical_shares=shares)


def analyze(frame: pd.DataFrame, *, analysis_date: str, as_of: str, equity: float | None = None,
            computed_at: str | None = None) -> Analysis:
    computed = timestamp(computed_at or datetime.now(timezone.utc).isoformat(), "computed_at")
    if computed < timestamp(as_of, "as_of"):
        raise ValueError("计算时点不能早于系统读取时点。")
    data = _visible(frame, analysis_date, as_of)
    f = indicators(data)
    last = f.iloc[-1]
    conditions = {name: None if pd.isna(last[name]) else bool(last[name]) for name in WEIGHTS}
    score = None if any(v is None for v in conditions.values()) else sum(WEIGHTS[k] for k,v in conditions.items() if v)
    technical = None if any(v is None for v in conditions.values()) else conditions["日线趋势"] and any(conditions[k] for k in list(WEIGHTS)[1:])
    dates = pd.to_datetime(data.trade_date)
    week_start = pd.Timestamp(analysis_date).to_period("W-SUN").start_time
    weeks = data.assign(week=dates.dt.to_period("W-SUN").dt.start_time)
    weekly = weeks.loc[weeks.week < week_start].groupby("week").close.last()
    weekly_state = "数据不足（需20个过往周样本）" if len(weekly) < 20 else ("偏强" if weekly.tail(5).mean() > weekly.tail(20).mean() else "偏弱/震荡")
    latest = last.trade_date
    if latest != analysis_date:
        technical = None
    reasons = ["主要指数与全市场覆盖缺失，市场过滤未通过", "历史ST/市值/停牌/涨跌停状态未知，股票池约束未通过",
               "交易日历与周线完整性未认证", "不复权序列缺公司行为/因子核验，评分仅供研究"]
    if len(data) < 60:
        reasons.insert(0, f"历史不足：当前{len(data)}条，完整技术评分需60条；ATR14需15条")
    if latest != analysis_date:
        reasons.insert(0, f"最新交易日{latest}早于分析日期，非交易日与缺失/过期尚无法区分")
    if last.volume_shares == 0 or last.amount_cny == 0:
        reasons.insert(0, "零成交量/金额：可能停牌或源异常，不推断正常交易，不生成信号")
    if pd.notna(last["量比5"]) and last["量比5"] >= 10:
        reasons.insert(0, "量比≥10，列为异常待核验，不生成信号")
    if technical is False:
        reasons.insert(0, "日线趋势与形态组合未满足")
    def number(name):
        return None if pd.isna(last[name]) else float(last[name])
    risk = risk_reference(float(last.close), number("ATR14"), number("结构止损10"), equity)
    if last.volume_shares == 0 or last.amount_cny == 0 or (number("量比5") is not None and last["量比5"] >= 10):
        risk.update(final_stop=None, theoretical_shares=None)
    f["指标可用时间"] = computed
    summary = dict(symbol=last.symbol, source=last.source, analysis_date=analysis_date, latest_trade_date=latest,
                   count=len(data), first_trade_date=data.trade_date.iloc[0], close=float(last.close),
                   trend="数据不足" if conditions["日线趋势"] is None else ("偏强" if conditions["日线趋势"] else "未形成多头排列"),
                   volume_state="零成交/状态未知" if last.volume_shares == 0 or last.amount_cny == 0 else "异常待核验" if number("量比5") is not None and last["量比5"] >= 10 else "数据不足" if number("量比5") is None else ("放量" if last["量比5"] >= 1.5 else "缩量" if last["量比5"] <= .7 else "常量"),
                   conditions=conditions, score=score, technical_signal=technical,
                   signal_state="数据不足" if technical is None else "满足（研究条件）" if technical else "未满足",
                   weekly_sample_trend=weekly_state, weekly_count=len(weekly), weekly_filter=None,
                   market_state="数据不足", eligible=False, exclusions=reasons, rule_version=RULE_VERSION,
                   as_of=timestamp(as_of,"as_of"), calculated_at=computed, signal_available_at=computed,
                   evidence_grade="B：行情派生研究，源口径未获生产准入", definition=RULE_VERSION,
                   snapshot_sha256=hashlib.sha256(data.to_json(orient="split",double_precision=15).encode()).hexdigest(),
                   lineage_refs=sorted(set(data.run_id.tolist()+data.source_version.tolist())),
                   latest_ingested_at=data.ingested_at.max(), data_available_at=max(data.available_at.max(),data.ingested_at.max()),
                   last_occurrences={k: f.loc[f[k].fillna(False), "trade_date"].iloc[-1] if f[k].fillna(False).any() else None for k in list(WEIGHTS)[1:]},
                   metrics={k:number(k) for k in ["MA5","MA10","MA20","MA60","ATR14","量比5"]})
    return Analysis(f, summary, risk)


def candidate_row(result: Analysis) -> dict:
    s = result.summary
    return {"股票代码":s["symbol"],"最新可用交易日":s["latest_trade_date"],"收盘价":s["close"],
            "趋势状态":s["trend"],"成交量状态":s["volume_state"],"信号状态":s["signal_state"],
            "研究评分":s["score"],"止损参考":result.risk["final_stop"],"候选准入":"未通过",
            "排除原因":"；".join(s["exclusions"])}

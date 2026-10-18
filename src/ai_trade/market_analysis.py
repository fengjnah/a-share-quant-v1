"""Small, causal research projections for M3; never produces orders or odds."""
from __future__ import annotations

from datetime import date
import math

import pandas as pd

from ai_trade.market_data.cffex_rankings_models import MemberScope, RankingSide

RULES = """m3-research-v1：仅研究辅助，未验证预测能力。
转折点：左右各3条，严格局部高/低点；右侧3条收盘后确认，标记确认日期与观察时间。
日线趋势=C相对MA20/MA60；周样本排除分析日所在整周，至少20个已结束周。
候选推动结构只检查最近6个交替转折：高低点抬升、2不破起点、3非最短、4不重叠1；不是唯一波浪计数。
斐波那契参考=最近一对已确认异向转折之间38.2%/50%/61.8%回撤，不是目标价。
恐贪固定权重：趋势25%、5条动量20%、20条波动20%、上涨占比20%、涨停占比10%、成交额5%。
趋势=clip(50+500*(C/MA20-1),0,100)。动量=C/C[-5]-1；波动=20条收益总体标准差。
动量、波动和成交额比值，以此前60条有效值的中位秩百分位标准化，至少20条；排除当前值。
波动因子=100-波动百分位；成交额比值=当日额/此前20条均额，来源未给出则缺失。
上涨占比=100*上涨/(上涨+下跌+平盘)；涨停占比=100*涨停/(涨停+跌停)，分母0则未知。
完整分数须6因子全部已知，不补值。指数代理仅用前三项，权重除以65%，与完整分数分开展示。
分位数只使用此前最多252个同口径分数（至少20条）；当日不进入自身比较基准。
极端后表现仅描述已实现收益：<=20或>=80，按最大窗口20条隔离事件，每窗至少20个样本才展示。
综合：先检查有效证据是否冲突，再要求三类证据齐备；不相加、不产生胜率。
"""
WEIGHTS = {"趋势": .25, "动量": .20, "低波动": .20, "上涨占比": .20, "涨停占比": .10, "成交额": .05}


def visible_prices(frame: pd.DataFrame, *, analysis_date: str, as_of: str) -> pd.DataFrame:
    date.fromisoformat(analysis_date)
    cutoff = pd.Timestamp(as_of)
    if cutoff.tzinfo is None:
        raise ValueError("as_of必须有时区")
    required = {"trade_date", "open", "high", "low", "close", "source", "symbol", "observed_at"}
    if frame.columns.has_duplicates or not required.issubset(frame):
        raise ValueError("行情字段不足")
    f = frame.loc[frame.trade_date <= analysis_date].copy().sort_values("trade_date").reset_index(drop=True)
    if f.empty:
        raise ValueError("数据不足：分析日期之前无真实行情")
    if f.trade_date.duplicated().any() or f.source.nunique() != 1 or f.symbol.nunique() != 1:
        raise ValueError("日期重复或混合证券/来源")
    for row in f.to_dict("records"):
        date.fromisoformat(row["trade_date"])
        ts = pd.Timestamp(row["observed_at"])
        if ts.tzinfo is None or ts > cutoff or ts.date() < date.fromisoformat(row["trade_date"]):
            raise ValueError("包含截止时点尚不可见的行情")
        for col in ("open", "high", "low", "close"):
            if isinstance(row[col], bool) or not math.isfinite(float(row[col])) or float(row[col]) <= 0:
                raise ValueError("价格必须是正有限数")
        if not row["low"] <= min(row["open"], row["close"]) <= max(row["open"], row["close"]) <= row["high"]:
            raise ValueError("OHLC关系错误")
    return f


def member_position(rows, *, contract: str, member: str, scope: MemberScope) -> dict:
    """Raw publication arithmetic only; no invented calendar or available_at."""
    if contract not in {r.contract for r in rows}:
        raise ValueError("必须指定榜单内合约")
    result = dict(contract=contract, member=member, scope=scope.value, long=None, short=None,
                  net=None, net_change=None, long_rank=None, short_rank=None, volume_rank=None)
    if scope not in (MemberScope.AGENT, MemberScope.PROPRIO):
        return result
    sides = {}
    for row in rows:
        if row.contract == contract and row.member == member and row.member_scope == scope and row.rank_format == "named":
            if row.side in sides:
                raise ValueError("重复会员排名")
            sides[row.side] = row
    for side, key in [(RankingSide.LONG, "long"), (RankingSide.SHORT, "short")]:
        row = sides.get(side)
        if row:
            result[key] = row.open_interest if row.open_interest_known else None
            result[key + "_rank"] = row.rank
    volume = sides.get(RankingSide.VOLUME)
    result["volume_rank"] = volume.rank if volume else None
    if result["long"] is not None and result["short"] is not None:
        result["net"] = result["long"] - result["short"]
        a, b = sides[RankingSide.LONG].open_interest_change, sides[RankingSide.SHORT].open_interest_change
        if a is not None and b is not None:
            result["net_change"] = a - b
    return result


def contract_label(contract: str) -> str:
    return f"{contract} · 到期月份20{contract[2:4]}-{contract[4:6]}（准确到期日未认证）"


def wave_scenarios(frame: pd.DataFrame, *, analysis_date: str, as_of: str) -> dict:
    f = visible_prices(frame, analysis_date=analysis_date, as_of=as_of)
    f["MA20"] = f.close.rolling(20, min_periods=20).mean()
    f["MA60"] = f.close.rolling(60, min_periods=60).mean()
    pivots = []
    for i in range(3, len(f)-3):
        window = f.iloc[i-3:i+4]
        for kind, col, op in [("高", "high", max), ("低", "low", min)]:
            value = f.iloc[i][col]
            if value == op(window[col]) and (window[col] == value).sum() == 1:
                pivots.append(dict(trade_date=f.iloc[i].trade_date, kind=kind, price=float(value),
                                   confirmed_date=f.iloc[i+3].trade_date,
                                   confirmed_observed_at=max(f.iloc[:i+4].observed_at, key=pd.Timestamp)))
    # Keep all confirmed pivots in the table; compress same-kind pivots only for the current scenario.
    alternating = []
    for p in pivots:
        if alternating and p["trade_date"] == alternating[-1]["trade_date"]:
            continue  # outside bar order is unknown
        if alternating and p["kind"] == alternating[-1]["kind"]:
            if (p["price"] > alternating[-1]["price"]) == (p["kind"] == "高"):
                alternating[-1] = p
        else:
            alternating.append(p)
    week = pd.to_datetime(f.trade_date).dt.to_period("W-SUN")
    weeks = f.loc[week < pd.Period(analysis_date, freq="W-SUN")].groupby(week).last()
    weekly = "数据不足：需20个已结束周"
    if len(weeks) >= 20:
        weekly = "偏多" if weeks.close.iloc[-1] > weeks.close.iloc[-20:].mean() else "偏空"
    scenarios, fib = [], []
    direction = "数据不足"
    if len(f) >= 60:
        up = f.close.iloc[-1] > f.MA20.iloc[-1] > f.MA60.iloc[-1]
        down = f.close.iloc[-1] < f.MA20.iloc[-1] < f.MA60.iloc[-1]
        direction = "偏多" if up else "偏空" if down else "中性"
        lo, hi = float(f.low.iloc[-20:].min()), float(f.high.iloc[-20:].max())
        scenarios.append(dict(情景="反转候选" if up else "下跌中继" if down else "调整延续",
                              支持=f"收盘{f.close.iloc[-1]:.2f} / MA20 {f.MA20.iloc[-1]:.2f} / MA60 {f.MA60.iloc[-1]:.2f}",
                              失效与反证=f"跌破近20条低点{lo:.2f}" if up else f"突破近20条高点{hi:.2f}", 置信="低（规则候选）"))
        scenarios.append(dict(情景="调整延续" if up else "反转候选", 支持="备选：局部反弹或回撤可能改变均线排列",
                              失效与反证=f"观察区间{lo:.2f}～{hi:.2f}与日周方向是否一致", 置信="低（待确认）"))
    if len(alternating) >= 6:
        ps = alternating[-6:]
        v = [p["price"] for p in ps]
        if [p["kind"] for p in ps] == ["低", "高", "低", "高", "低", "高"]:
            impulse = v[2] > v[0] and v[3] > v[1] and v[4] > v[1] and v[5] > v[3] and v[3]-v[2] >= min(v[1]-v[0], v[5]-v[4])
            if impulse:
                scenarios.append(dict(情景="候选向上推动浪", 支持="最近6个确认转折满足简化推动结构规则", 失效与反证=f"跌破第4浪低点{v[4]:.2f}；可能存在其他计数", 置信="低"))
    if len(alternating) >= 2:
        a, b = alternating[-2:]
        for ratio in (.382, .5, .618):
            fib.append(dict(回撤比例=ratio, 参考价=b["price"]+(a["price"]-b["price"])*ratio,
                            起点=a["trade_date"], 终点=b["trade_date"]))
    if len(alternating) >= 4:
        ps = alternating[-4:]
        v = [p["price"] for p in ps]
        if [p["kind"] for p in ps] == ["高", "低", "高", "低"] and v[2] < v[0] and v[3] < v[1]:
            scenarios.append(dict(情景="候选A-B-C调整", 支持="B未越初高，C低于A末；也可能是下跌推动的一部分",
                                  失效与反证=f"突破初始高点{v[0]:.2f}", 置信="低"))
    return dict(frame=f, pivots=pd.DataFrame(pivots), weekly=weeks, weekly_direction=weekly,
                direction=direction, scenarios=pd.DataFrame(scenarios), fibonacci=pd.DataFrame(fib))


def past_percentile(values: pd.Series, window=60, minimum=20) -> pd.Series:
    def rank(window_values):
        previous, current = window_values[:-1], window_values[-1]
        previous = previous[~pd.isna(previous)]
        if len(previous) < minimum or pd.isna(current):
            return float("nan")
        return 100*((previous < current).sum()+.5*(previous == current).sum())/len(previous)
    return values.rolling(window+1, min_periods=minimum+1).apply(rank, raw=True)


def fear_greed(frame: pd.DataFrame, *, analysis_date: str, as_of: str, breadth: pd.DataFrame | None = None) -> pd.DataFrame:
    f = visible_prices(frame, analysis_date=analysis_date, as_of=as_of)
    close = f.close
    factors = pd.DataFrame(index=f.index)
    factors["趋势"] = (50+500*(close/close.rolling(20, min_periods=20).mean()-1)).clip(0, 100)
    factors["动量"] = past_percentile(close/close.shift(5)-1)
    factors["低波动"] = 100-past_percentile(close.pct_change(fill_method=None).rolling(20, min_periods=20).std(ddof=0))
    factors["上涨占比"], factors["涨停占比"], factors["成交额"] = float("nan"), float("nan"), float("nan")
    if "amount_cny" in f:
        amount = pd.to_numeric(f.amount_cny, errors="raise")
        if ((amount.dropna() < 0) | ~amount.dropna().map(math.isfinite)).any():
            raise ValueError("成交额无效")
        factors["成交额"] = past_percentile(amount/amount.shift(1).rolling(20, min_periods=20).mean().replace(0, float("nan")))
    if breadth is not None and not breadth.empty:
        b = breadth.copy()
        if b.trade_date.duplicated().any():
            raise ValueError("市场宽度日期重复")
        b = b.loc[b.trade_date <= analysis_date]
        for row in b.to_dict("records"):
            if pd.Timestamp(row["observed_at"]).tzinfo is None or pd.Timestamp(row["observed_at"]) > pd.Timestamp(as_of):
                raise ValueError("宽度数据尚不可见")
            numbers = [row[k] for k in ("advances", "declines", "flat", "limit_up", "limit_down")]
            if any(isinstance(v, bool) or not math.isfinite(float(v)) or v < 0 or v != int(v) for v in numbers):
                raise ValueError("市场家数必须为已知非负整数")
            total, limits = sum(numbers[:3]), sum(numbers[3:])
            mask = f.trade_date == row["trade_date"]
            factors.loc[mask, "上涨占比"] = 100*numbers[0]/total if total else float("nan")
            factors.loc[mask, "涨停占比"] = 100*numbers[3]/limits if limits else float("nan")
    f = pd.concat([f, factors], axis=1)
    f["coverage"] = sum(f[k].notna()*w for k, w in WEIGHTS.items())
    f["score"] = sum(f[k]*w for k, w in WEIGHTS.items())  # NaN propagation is intentional
    f["index_proxy"] = sum(f[k]*WEIGHTS[k] for k in list(WEIGHTS)[:3])/.65
    f["percentile"] = past_percentile(f.score, 252)
    f["proxy_percentile"] = past_percentile(f.index_proxy, 252)
    return f


def emotion(score) -> str:
    if pd.isna(score):
        return "数据不足"
    return "极度恐惧" if score <= 20 else "恐惧" if score < 40 else "中性" if score <= 60 else "贪婪" if score < 80 else "极度贪婪"


def extreme_outcomes(f: pd.DataFrame) -> pd.DataFrame:
    results = []
    for label, condition in [("恐惧", f.score <= 20), ("贪婪", f.score >= 80)]:
        indices, last = [], -20
        for i in f.index[condition]:
            if i-last >= 20:
                indices.append(i)
                last = i
        for window in (5, 10, 20):
            returns = [f.close.iloc[i+window]/f.close.iloc[i]-1 for i in indices if i+window < len(f)]
            if len(returns) >= 20:
                results.append(dict(情绪=label, 窗口=window, 样本数=len(returns), 平均后续收益=sum(returns)/len(returns)))
    return pd.DataFrame(results)


def environment(futures: str, wave: str, sentiment: str) -> str:
    values = [futures, wave, sentiment]
    if "偏多" in values and "偏空" in values:
        return "证据冲突"
    if "数据不足" in values:
        return "数据不足"
    return "偏强" if values.count("偏多") >= 2 else "偏弱" if values.count("偏空") >= 2 else "震荡"

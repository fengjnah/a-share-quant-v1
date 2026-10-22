"""Frozen pre-trace reference, main 04e5308. Test-only behavior preservation.
Original function SHA256: c9716ede37b36c5a5c74faae33e906ee03808948a3eb07862271f4e87ad38c9f
"""
import math
import pandas as pd
from ai_trade.market_analysis import WEIGHTS, visible_prices, past_percentile


def baseline_fear_greed(frame: pd.DataFrame, *, analysis_date: str, as_of: str, breadth: pd.DataFrame | None = None) -> pd.DataFrame:
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

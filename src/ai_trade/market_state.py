"""Shared, conservative market envelope for research consumers (M3/M4).

Only validated evidence for the exact analysis date may open a filter.
M3 research indicators have not received formal filter admission.
"""
from dataclasses import dataclass

from ai_trade.data_access.validation import iso_date, timestamp

STATES = ("偏强", "震荡", "偏弱", "证据冲突", "数据不足")
MARKET_MODES = ("遵循市场过滤", "仅偏强")


@dataclass(frozen=True)
class MarketState:
    analysis_date: str
    state: str = "数据不足"
    available_at: str | None = None
    validated: bool = False
    source: str = "M2 市场过滤（M3 研究因素未获正式准入）"
    reasons: tuple[str, ...] = ("主要指数与全市场覆盖缺失；市场门禁未通过",)

    def allows(self, *, analysis_date: str, as_of: str, mode: str) -> bool:
        iso_date(analysis_date)
        if mode not in MARKET_MODES:
            raise ValueError("未知市场过滤模式")
        if self.state not in STATES:
            raise ValueError("未知市场状态")
        if not self.validated or self.analysis_date != analysis_date or self.available_at is None:
            return False
        if timestamp(self.available_at, "available_at") > timestamp(as_of, "as_of"):
            return False
        return self.state == "偏强" or (mode == MARKET_MODES[0] and self.state == "震荡")

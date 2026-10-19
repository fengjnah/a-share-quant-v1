"""M4 projections over M2 calculations; no indicator, price or order synthesis."""
from dataclasses import dataclass, field

from ai_trade.market_state import MarketState, MARKET_MODES
from ai_trade.trading_analysis import Analysis, WEIGHTS

STRATEGIES = ("严格模式", "趋势确认模式")
RULE_VERSION = "m4-selection-v1+m2-research-v1"
LIMITATIONS = (
    ("OHLCV / 时间可见性", "执行", "复用 M2 校验与 SQLite 严格可见版本；完整评分需60条"),
    ("市场环境", "阻断", "复用 M2；M3 CFFEX/波浪/恐贪未获正式过滤准入"),
    ("历史 ST / 退市整理", "未执行，阻断准入", "现有证券主数据的 risk_status 始终未知，不按名称推断"),
    ("停牌 / 涨跌停 / 交易单位", "未执行，阻断仓位", "不存在已验证的逐日可执行状态与交易单位输入"),
    ("总市值≥100亿元", "未执行", "未接入对应历史日期的真实总市值"),
    ("热门行业 / 龙头 / 成长性", "未执行", "历史行业与基本面数据未接入，不使用当前分类倒填"),
    ("周线 / 交易日覆盖", "研究展示，正式门禁阻断", "M2 排除当前周；历史日历完整性尚未认证"),
    ("二次放量 / 突破后回调", "未执行关联判断", "M2 只有独立突破/缩量回调，不冒充已确认的先后组合"),
    ("公司行为 / 复权", "未认证", "沿用不复权行情，不能排除除权等结构性影响"),
)


@dataclass
class Evaluation:
    symbol: str
    name: str = "未知（缺少历史名称）"
    analysis: Analysis | None = None
    research_match: bool = False
    exclusions: list[str] = field(default_factory=list)
    risk: dict = field(default_factory=dict)

    @property
    def eligible(self) -> bool:
        return self.analysis is not None and self.research_match and not self.exclusions

    @property
    def score(self):
        return self.analysis.summary["score"] if self.analysis else None


@dataclass
class CandidateBatch:
    analysis_date: str
    as_of: str
    strategy: str
    market_mode: str
    market: MarketState
    evaluations: list[Evaluation]
    warnings: list[str] = field(default_factory=list)

    @property
    def candidates(self) -> list[Evaluation]:
        return [row for row in self.evaluations if row.eligible][:5]


def evaluate(result: Analysis, *, strategy: str, market: MarketState,
             market_mode: str = MARKET_MODES[0], name: str = "未知（缺少历史名称）",
             metadata_reasons: tuple[str, ...] = ()) -> Evaluation:
    if strategy not in STRATEGIES:
        raise ValueError("未知策略模式")
    s = result.summary
    matched = (s["technical_signal"] is True if strategy == STRATEGIES[0]
               else s["conditions"]["日线趋势"] is True)
    # M2's failed pattern combination is mode-specific; all data/risk gates remain.
    exclusions = [r for r in s["exclusions"] if r != "日线趋势与形态组合未满足"]
    exclusions.extend(metadata_reasons)
    if not matched:
        exclusions.append("严格组合未满足或未知" if strategy == STRATEGIES[0] else "日线趋势未确认或未知")
    if not market.allows(analysis_date=s["analysis_date"], as_of=s["as_of"], mode=market_mode):
        exclusions.append(f"市场过滤未通过：{market.state}（{market_mode}）")
    risk = dict(result.risk)
    # M2's unrounded theoretical shares must never become a proposed A-share order.
    risk.update(theoretical_shares=None, position_cny=None, lot_size=None,
                sizing_reason="交易单位、下一可交易会话、停牌/涨跌停和T+1执行约束未验证，不输出股数或仓位",
                stop_reason="仅当结构与ATR止损均位于(0,参考价)时取较高者；复用M2",
                reward_risk=None)
    return Evaluation(s["symbol"], name, result, matched, list(dict.fromkeys(exclusions)), risk)


def sort_evaluations(rows: list[Evaluation]) -> list[Evaluation]:
    return sorted(rows, key=lambda r: (r.score is None, -(r.score or 0), r.symbol))


def score_rows(row: Evaluation) -> list[dict]:
    if row.analysis is None:
        return []
    return [{"条件": k, "权重": weight,
             "状态": "未知" if row.analysis.summary["conditions"][k] is None else
             "满足" if row.analysis.summary["conditions"][k] else "未满足",
             "得分": None if row.analysis.summary["conditions"][k] is None else
             weight if row.analysis.summary["conditions"][k] else 0}
            for k, weight in WEIGHTS.items()]


def table_row(row: Evaluation, rank: int) -> dict:
    s = row.analysis.summary if row.analysis else {}
    satisfied = [k for k, v in s.get("conditions", {}).items() if v is True]
    missing = [k for k, v in s.get("conditions", {}).items() if v is not True]
    return {"排名": rank, "股票代码": row.symbol, "股票名称": row.name,
            "行情日期": s.get("latest_trade_date"), "收盘价": s.get("close"),
            "趋势状态": s.get("trend", "数据不足"), "量价信号": "、".join(satisfied[1:] if satisfied and satisfied[0] == "日线趋势" else satisfied) or "无",
            "研究评分": row.score, "模式条件": "满足" if row.research_match else "未满足/未知",
            "候选准入": "通过" if row.eligible else "未通过",
            "参考入场条件": "指标可用后，下一已验证交易会话重验趋势/形态及可交易性；收盘价仅测算基准",
            "结构止损": row.risk.get("structure_stop"), "ATR止损": row.risk.get("atr_stop"),
            "研究止损参考": row.risk.get("final_stop"), "未满足条件": "、".join(missing),
            "数据完整性": f"{s.get('count', 0)}条；基础校验通过，交易日完整性未认证" if row.analysis else "校验失败/数据不足",
            "排除/风险提示": "；".join(row.exclusions)}

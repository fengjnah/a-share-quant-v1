"""Bounded local discovery; all price reads reuse the M2/SQLite strict port."""
from datetime import date, timedelta

from ai_trade.data_access.validation import iso_date, timestamp
from ai_trade.daily_candidates import CandidateBatch, Evaluation, evaluate, sort_evaluations
from ai_trade.demo_data import make_request, read_bars
from ai_trade.market_state import MarketState
from ai_trade.security_master.repository import SQLiteSecurityMaster
from ai_trade.trading_analysis import analyze

MAX_SYMBOLS = 20
HISTORY_DAYS = 420


def local_coverage(db, *, source: str, as_of: str) -> tuple[list[dict], list[str]]:
    cutoff = timestamp(as_of, "as_of")
    with db.connection() as conn:
        # Discovery does not certify accepted quality; read_bars checks the selected version.
        rows = conn.execute("""SELECT i.symbol,min(b.trade_date) first_date,
            max(b.trade_date) last_date,count(DISTINCT b.trade_date) observations
            FROM daily_bars b JOIN daily_bar_versions v ON b.bar_id=v.bar_id
            JOIN instruments i ON i.instrument_id=b.instrument_id
            WHERE v.source=? AND b.adjustment_method='none'
              AND v.available_at<=? AND v.ingested_at<=? AND v.event_time<=?
            GROUP BY i.symbol ORDER BY i.symbol LIMIT ?""", (source, cutoff, cutoff, cutoff, MAX_SYMBOLS+1)).fetchall()
        dates = conn.execute("""SELECT DISTINCT b.trade_date FROM daily_bars b
            JOIN daily_bar_versions v ON b.bar_id=v.bar_id WHERE v.source=?
            AND b.adjustment_method='none' AND v.available_at<=? AND v.ingested_at<=? AND v.event_time<=?
            ORDER BY b.trade_date DESC""", (source, cutoff, cutoff, cutoff)).fetchall()
    return [dict(r) for r in rows], [r[0] for r in dates]


def load_batch(db, *, source: str, analysis_date: str, as_of: str, strategy: str,
               market_mode: str, symbol: str = "", equity: float | None = None) -> CandidateBatch:
    iso_date(analysis_date)
    coverage, dates = local_coverage(db, source=source, as_of=as_of)
    if analysis_date not in dates:
        raise ValueError("分析日期没有当前时点可见的本地行情；不能推断休市或回填")
    start = date.fromisoformat(analysis_date)-timedelta(days=HISTORY_DAYS)
    codes = [make_request(symbol, start, date.fromisoformat(analysis_date)).symbol] if symbol.strip() else [r["symbol"] for r in coverage[:MAX_SYMBOLS]]
    market = MarketState(analysis_date=analysis_date)
    rows = []
    for code in codes:
        try:
            request = make_request(code, start, date.fromisoformat(analysis_date))
            frame = read_bars(db, request, source=source, as_of=as_of)
            result = analyze(frame, analysis_date=analysis_date, as_of=as_of, equity=equity)
            name = "未知（缺少历史名称）"
            metadata_reasons = []
            try:
                security = SQLiteSecurityMaster(db).resolve(symbol=code, valid_on=analysis_date,
                                                            as_of=as_of, mode="strict_backtest")
                # Synthetic reference records must never supply a real display name.
                if security.value.snapshot.provenance.evidence_kind == "synthetic":
                    metadata_reasons.append("证券名称/身份为合成测试证据，不能用于真实候选")
                else:
                    name = security.value.period.name
            except Exception as exc:
                metadata_reasons.append(f"历史证券名称/身份不可确认：{type(exc).__name__}: {exc}")
            rows.append(evaluate(result, strategy=strategy, market=market, market_mode=market_mode,
                                 name=name, metadata_reasons=tuple(metadata_reasons)))
        except Exception as exc:
            rows.append(Evaluation(code, exclusions=[f"数据不足或校验失败：{type(exc).__name__}: {exc}"]))
    warnings = [f"最多扫描{MAX_SYMBOLS}只、每只最近{HISTORY_DAYS}个日历日；不进行历史回补"]
    if len(coverage) > MAX_SYMBOLS and not symbol:
        warnings.append("本地股票池超过批次上限，本次仅取代码排序前20只；不是全市场排名")
    return CandidateBatch(analysis_date, timestamp(as_of, "as_of"), strategy, market_mode,
                          market, sort_evaluations(rows), warnings)

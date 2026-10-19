"""Versioned M3 diagnostics over existing calculators, with no I/O or orders."""
from __future__ import annotations

from dataclasses import dataclass, field
import math
from numbers import Real

import pandas as pd

from ai_trade.data_access.validation import iso_date, text_field, timestamp
from ai_trade.market_analysis import WEIGHTS, emotion, fear_greed, member_position, wave_scenarios
from ai_trade.market_analysis_contract import (
    Admission, CalendarEvidence, Coverage, Diagnostic, Reason, ReasonCode as Code,
    Request, SourceEvidence, Status, clean,
)

# These are arithmetic/engineering requirements, NOT fitted prediction thresholds.
MINIMUMS = {"daily_trend": 60, "weekly_structure": 20, "wave": 60,
            "price_proxy": 41, "fear_greed": 41, "market_breadth": 1, "cffex_position": 1}
TIME_FIELDS = ("event_time", "observed_at", "ingested_at", "available_at")


@dataclass
class _Context:
    request: Request
    source: SourceEvidence
    frame: pd.DataFrame
    coverage: Coverage
    times: dict = field(default_factory=lambda: {k: None for k in TIME_FIELDS})
    reasons: list[Reason] = field(default_factory=list)
    missing: set[str] = field(default_factory=set)

    def add(self, code, detail, action, blocks=("L2", "L3")):
        self.reasons.append(Reason(code, detail, action, blocks))


def _coverage(f, request, calendar, reasons):
    if calendar is None or not calendar.receipt.verified:
        reasons.append(Reason(Code.CALENDAR_UNKNOWN, "No certified session denominator", "Supply a sourced dated calendar query"))
        return Coverage(len(f), None, "UNKNOWN")
    if (calendar.market != ("CFFEX" if request.instrument_type == "CFFEX" else "CN_A")
            or calendar.available_at is None or calendar.ingested_at is None
            or max(timestamp(calendar.available_at, "calendar.available_at"),
                   timestamp(calendar.ingested_at, "calendar.ingested_at")) > request.as_of):
        raise ValueError("Calendar scope/time is not visible for this request")
    start = f.trade_date.min() if len(f) else request.analysis_date
    if calendar.start > start or calendar.end < request.analysis_date:
        raise ValueError("Calendar does not cover the complete input/request range")
    expected = {d for d in calendar.sessions if start <= d <= request.analysis_date}
    actual = set(f.trade_date)
    if actual - expected:
        raise ValueError("Prices/counts include dates outside certified sessions")
    missing = tuple(sorted(expected - actual))
    if missing:
        reasons.append(Reason(Code.COVERAGE_INCOMPLETE, f"Missing {len(missing)} certified sessions", "Acquire those sessions without filling zeros"))
    return Coverage(len(actual), len(expected), "certified_trading_sessions", calendar.receipt.refs, missing)


def _prepare(frame, request, source, calendar=None, *, prices=True):
    ctx = _Context(request, source, pd.DataFrame(), Coverage(0, None, "UNKNOWN"))
    try:
        if frame is None or frame.empty:
            ctx.add(Code.SOURCE_UNAVAILABLE, "No observations supplied", "Acquire one explicit source/date with bounded requests")
            return ctx
        if prices and request.instrument_type not in {"INDEX", "STOCK"}:
            raise ValueError("Price definitions require explicit INDEX or STOCK scope")
        required = {"trade_date", "observed_at", "source"} | ({"symbol", "open", "high", "low", "close"} if prices else set())
        if frame.columns.has_duplicates or not required.issubset(frame):
            ctx.missing.update(required - set(frame))
            raise ValueError("Required columns missing or duplicated")
        for day in frame.trade_date:
            iso_date(day)
        f = frame.loc[frame.trade_date <= request.analysis_date].copy()
        visible = []
        for row in f.to_dict("records"):
            known = {}
            for key in TIME_FIELDS:
                value = row.get(key)
                if value is None or pd.isna(value):
                    pass  # UNKNOWN stays absent; record missing fields after visibility selection.
                else:
                    known[key] = timestamp(value, key)
            if "observed_at" not in known:
                raise ValueError("Observation time cannot be fabricated")
            if "event_time" in known:
                if pd.Timestamp(known["event_time"]).tz_convert("Asia/Shanghai").date().isoformat() != row["trade_date"]:
                    raise ValueError("Event date contradicts trade_date")
                if any(known["event_time"] > v for k, v in known.items() if k != "event_time"):
                    raise ValueError("Acquisition/availability precedes event")
            if "ingested_at" in known and known["observed_at"] > known["ingested_at"]:
                raise ValueError("Ingestion precedes actual observation")
            # Filtering, not relabeling, keeps late acquisitions out of historical replay.
            if all(t <= request.as_of for t in known.values()):
                visible.append(row)
        if not visible:
            ctx.add(Code.NOT_VISIBLE, "No input version visible at as_of", "Use an actually visible snapshot or later as_of")
            return ctx
        f = pd.DataFrame(visible).sort_values("trade_date").reset_index(drop=True)
        if f.trade_date.duplicated().any():
            raise ValueError("Duplicate date; select one visible version first")
        if "quality_status" not in f:
            ctx.missing.add("quality_status")
            ctx.add(Code.EVIDENCE_MISSING, "quality_status absent for the visible input series",
                    "Supply the actual per-record quality decision; a receipt cannot imply accepted")
        for row in f.to_dict("records"):
            location = f"trade_date={row['trade_date']} symbol={request.symbol}"
            identities = {"source": source.source}
            if prices or "symbol" in row:
                identities["symbol"] = request.symbol
            for key, expected in identities.items():
                value = text_field(row[key], f"{key} at {location}")
                if value != expected:
                    raise ValueError(f"{key} at {location}: does not match the declared identity")
            if "quality_status" in row:
                quality = row["quality_status"]
                if quality is None or quality is pd.NA or isinstance(quality, float) and math.isnan(quality):
                    ctx.missing.add("quality_status")
                    ctx.add(Code.EVIDENCE_MISSING, f"quality_status UNKNOWN at {location}",
                            "Supply the actual accepted quality decision; never fill it from a receipt")
                elif not isinstance(quality, str) or quality != "accepted":
                    raise ValueError(f"quality_status at {location}: explicit accepted required; rejected/isolated/invalid state")
        if prices:
            for row in f.to_dict("records"):
                for k in ("open", "high", "low", "close"):
                    v = row[k]
                    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0:
                        raise ValueError("Price must be a positive finite number")
                if not row["low"] <= min(row["open"], row["close"]) <= max(row["open"], row["close"]) <= row["high"]:
                    raise ValueError("OHLC relationship invalid")
            if "adjustment_method" in f and (f.adjustment_method.nunique() != 1 or not f.adjustment_method.eq("none").all()):
                raise ValueError("This definition accepts only explicit unadjusted prices")
            if "adjustment_method" not in f:
                ctx.missing.add("adjustment_method")
                ctx.add(Code.SCOPE_UNSUPPORTED, "Price adjustment definition is UNKNOWN", "Certify a fixed unadjusted price definition")
        # Only visible rows contribute to aggregated times and missing-field semantics.
        ctx.missing.update(k for k in TIME_FIELDS if k not in f or f[k].isna().any())
        for key in TIME_FIELDS:
            if key not in ctx.missing:
                ctx.times[key] = max(timestamp(v, key) for v in f[key])
        ctx.frame = f
        ctx.coverage = _coverage(f, request, calendar, ctx.reasons)
        if f.trade_date.iloc[-1] != request.analysis_date:
            ctx.add(Code.STALE, f"Requested {request.analysis_date}; actual visible cutoff {f.trade_date.iloc[-1]}", "Acquire the exact requested date; do not relabel an older date")
    except (ValueError, TypeError, KeyError) as exc:
        ctx.add(Code.INVALID_DATA, str(exc), "Correct the input or version selection; do not fill or silently drop bad observations")
    return ctx


def _finish(indicator, ctx, values, calculated, *, minimum=None, coverage=None):
    reasons = list(ctx.reasons)
    source, request = ctx.source, ctx.request
    if source.evidence_kind == "synthetic":
        reasons.append(Reason(Code.SYNTHETIC, "Synthetic evidence is only an offline fixture", "Acquire and independently verify real source evidence"))
    if not source.verification.verified:
        reasons.append(Reason(Code.SOURCE_UNVERIFIED, "Source verification UNKNOWN/unverified", "Supply a reviewed source receipt"))
    if not source.research_authorization.verified:
        reasons.append(Reason(Code.AUTHORIZATION_UNKNOWN, "Personal research permission is not certified", "Verify data terms separately from SDK license"))
    if not source.time_verification.verified or any(ctx.times.get(k) is None for k in TIME_FIELDS):
        reasons.append(Reason(Code.TIME_UNCERTIFIED, "Actual event/observation/ingestion/availability not fully certified", "Supply real timestamps and time-rule evidence; never backdate them"))
    cov = coverage or ctx.coverage
    if minimum is not None and cov.valid_samples < minimum:
        reasons.append(Reason(Code.HISTORY_INSUFFICIENT, f"Requires {minimum}; actual {cov.valid_samples}", "Acquire sufficient real history and certify the denominator"))
    invalid = any(r.code is Code.INVALID_DATA for r in reasons)
    if invalid:
        values, calculated = {}, False
    has_observation = not ctx.frame.empty and not invalid
    research = calculated and has_observation and not any("L2" in r.blocks for r in reasons)
    admission = Admission.L2 if research else Admission.L1 if has_observation else Admission.BLOCKED
    if request.mode != "research" and not research:
        values, calculated, admission = {}, False, Admission.BLOCKED
    reasons.append(Reason(Code.STRATEGY_GATE, "No independent strategy/execution/out-of-sample approval", "Supply matching strategy_admission receipt", ("L3",)))
    priority = ((Code.INVALID_DATA, Status.INVALID_DATA), (Code.SOURCE_UNAVAILABLE, Status.SOURCE_UNAVAILABLE),
                (Code.NOT_VISIBLE, Status.BLOCKED), (Code.STALE, Status.STALE),
                (Code.HISTORY_INSUFFICIENT, Status.HISTORY_INSUFFICIENT), (Code.FACTOR_MISSING, Status.FACTOR_MISSING),
                (Code.EVIDENCE_CONFLICT, Status.EVIDENCE_CONFLICT), (Code.TIME_UNCERTIFIED, Status.TIME_UNCERTIFIED))
    status = next((s for c, s in priority if any(r.code is c for r in reasons)),
                  Status.RESEARCH_ALLOWED if research else Status.BLOCKED if admission is Admission.BLOCKED
                  else Status.OBSERVATION_ONLY if has_observation else Status.BLOCKED)
    return Diagnostic(indicator, request, source, ctx.frame.trade_date.max() if has_observation else None,
                      dict(ctx.times), cov, clean(values), bool(calculated), admission, status,
                      tuple(reasons), tuple(sorted(ctx.missing)))


def price_diagnostics(frame, *, request: Request, source: SourceEvidence, calendar: CalendarEvidence | None = None):
    """Daily trend, closed-week OHLC, causal pivots and a separate price proxy."""
    ctx = _prepare(frame, request, source, calendar)
    f = ctx.frame
    empty = f.empty or any(r.code is Code.INVALID_DATA for r in ctx.reasons)
    results = {}
    if empty:
        return {name: _finish(name, ctx, {}, False, minimum=MINIMUMS[name])
                for name in ("daily_trend", "weekly_structure", "wave", "price_proxy")}
    old = wave_scenarios(f, analysis_date=request.analysis_date, as_of=request.as_of)
    daily = {"close": float(f.close.iloc[-1]), "MA20": old["frame"].MA20.iloc[-1],
             "MA60": old["frame"].MA60.iloc[-1], "direction": old["direction"]}
    results["daily_trend"] = _finish("daily_trend", ctx, daily, len(f) >= 60, minimum=60)
    week = pd.to_datetime(f.trade_date).dt.to_period("W-SUN")
    closed = f.loc[week < pd.Period(request.analysis_date, freq="W-SUN")].copy()
    closed["week"] = pd.to_datetime(closed.trade_date).dt.to_period("W-SUN").astype(str)
    # A query starting mid-week does not establish a complete first week.
    first_week = pd.Period(f.trade_date.min(), freq="W-SUN")
    first_complete = (calendar is not None and calendar.start <= first_week.start_time.date().isoformat()
                      and {d for d in calendar.sessions if pd.Period(d, freq="W-SUN") == first_week}.issubset(set(f.trade_date)))
    if not first_complete:
        closed = closed.loc[closed.week != str(first_week)]
    weeks = closed.groupby("week", sort=True).agg(open=("open", "first"), high=("high", "max"),
        low=("low", "min"), close=("close", "last"), first_date=("trade_date", "first"), last_date=("trade_date", "last"))
    expected_weeks = None
    refs = ()
    if ctx.coverage.expected_samples is not None:
        expected_weeks = len({str(pd.Period(d, freq="W-SUN")) for d in calendar.sessions
            if f.trade_date.min() <= d <= request.analysis_date
            and pd.Period(d, freq="W-SUN") < pd.Period(request.analysis_date, freq="W-SUN")
            and (pd.Period(d, freq="W-SUN") != first_week or first_complete)})
        refs = calendar.receipt.refs
    week_cov = Coverage(len(weeks), expected_weeks, "certified_closed_calendar_weeks" if refs else "UNKNOWN", refs, ctx.coverage.missing_dates)
    values = {"weeks": weeks.reset_index().to_dict("records"), "partial_current_week_used": False,
              "direction": ("偏多" if weeks.close.iloc[-1] > weeks.close.iloc[-20:].mean() else "偏空") if len(weeks) >= 20 else None}
    results["weekly_structure"] = _finish("weekly_structure", ctx, values, len(weeks) >= 20, minimum=20, coverage=week_cov)
    pivots = old["pivots"].to_dict("records")
    for pivot in pivots:
        i = f.index[f.trade_date == pivot["trade_date"]][0]
        inputs = f.iloc[i-3:i+4]
        pivot["confirmation_input_dates"] = inputs.trade_date.tolist()
        pivot["first_usable_at"] = (max(timestamp(v, k) for k in ("observed_at", "ingested_at", "available_at")
                                       for v in inputs[k]) if all(k in inputs and inputs[k].notna().all()
                                                                 for k in ("observed_at", "ingested_at", "available_at")) else None)
    values = {"direction": old["direction"], "pivots": pivots, "scenarios": old["scenarios"].to_dict("records"),
              "fibonacci": old["fibonacci"].to_dict("records"), "unique_wave_count": False}
    results["wave"] = _finish("wave", ctx, values, len(f) >= 60, minimum=60)
    proxy = fear_greed(f.drop(columns=["amount_cny"], errors="ignore"), analysis_date=request.analysis_date, as_of=request.as_of)
    latest = proxy.iloc[-1]
    values = {"score": latest.index_proxy, "percentile": latest.proxy_percentile,
              "factors": {k: latest[k] for k in list(WEIGHTS)[:3]}, "weight_denominator": .65,
              "historical_scores": proxy[["trade_date", "index_proxy"]].to_dict("records"),
              "percentile_reference": "previous at most 252 same-source/symbol/version values; excludes current; minimum 20"}
    results["price_proxy"] = _finish("price_proxy", ctx, values, pd.notna(latest.index_proxy), minimum=41)
    return results


def breadth_diagnostic(frame, *, request: Request, source: SourceEvidence, calendar=None,
                       universe_receipt=None):
    """Validate full-A membership accounting; quoted subset is not its denominator."""
    ctx = _prepare(frame, request, source, calendar, prices=False)
    f = ctx.frame
    values = {"reported_counts": [], "universe_coverage": [], "all_a_scope_verified": False}
    counts = ("advances", "declines", "flat", "limit_up", "limit_down")
    membership = ("eligible_count", "suspended", "unavailable", "missing")
    universe_fields = ("universe_snapshot_ref", "universe_date", "universe_available_at", "universe_ingested_at")
    try:
        for row in f.to_dict("records"):
            if any(k not in row or pd.isna(row[k]) for k in counts):
                ctx.missing.update(k for k in counts if k not in row or pd.isna(row[k]))
                ctx.add(Code.FACTOR_MISSING, "Reported breadth counts missing", "Acquire real counts for the same date")
                continue
            numbers = [row[k] for k in counts]
            if any(isinstance(v, bool) or not math.isfinite(v) or v < 0 or v != int(v) for v in numbers):
                raise ValueError("Breadth counts must be known nonnegative integers")
            if row["limit_up"] > row["advances"] or row["limit_down"] > row["declines"]:
                raise ValueError("Limit counts exceed advancing/declining members")
            values["reported_counts"].append({"trade_date": row["trade_date"], **{k: int(row[k]) for k in counts}})
            known = all(k in row and not pd.isna(row[k]) for k in (*membership, *universe_fields))
            if not known:
                ctx.missing.update(k for k in (*membership, *universe_fields) if k not in row or pd.isna(row[k]))
                values["universe_coverage"].append({"trade_date": row["trade_date"], "numerator": None, "denominator": None, "ratio": None})
                continue
            if (row["universe_date"] != row["trade_date"] or not isinstance(row["universe_snapshot_ref"], str)
                    or not row["universe_snapshot_ref"].strip()
                    or max(timestamp(row[k], k) for k in ("universe_available_at", "universe_ingested_at")) > request.as_of):
                raise ValueError("Universe date/reference/time not valid at as_of")
            nums = [row[k] for k in membership]
            if any(isinstance(v, bool) or not math.isfinite(v) or v < 0 or v != int(v) for v in nums):
                raise ValueError("Universe partition counts invalid")
            quoted = sum(row[k] for k in counts[:3])
            if row["eligible_count"] <= 0 or quoted + sum(row[k] for k in membership[1:]) != row["eligible_count"]:
                raise ValueError("Advances/declines/flat/suspended/unavailable/missing must partition eligible universe")
            numerator = quoted + row["suspended"]
            values["universe_coverage"].append({"trade_date": row["trade_date"], "numerator": int(numerator),
                "denominator": int(row["eligible_count"]), "ratio": numerator/row["eligible_count"],
                "denominator_ref": row["universe_snapshot_ref"], "quoted_denominator": int(quoted)})
        scope_ok = (request.instrument_type == "ALL_A" and universe_receipt is not None and universe_receipt.verified
                    and len(values["universe_coverage"]) == len(f) and len(f) > 0
                    and all(r["ratio"] == 1 and r["denominator_ref"] in universe_receipt.refs
                            for r in values["universe_coverage"]))
        values["all_a_scope_verified"] = scope_ok
        if not scope_ok:
            ctx.add(Code.UNIVERSE_UNKNOWN, "Full-A historical membership/complete partition not certified", "Supply dated point-in-time universe snapshots, identities and partition evidence")
    except (ValueError, TypeError) as exc:
        ctx.add(Code.INVALID_DATA, str(exc), "Correct source accounting; do not infer missing stocks as flat or suspended")
    return _finish("market_breadth", ctx, values, bool(values["reported_counts"]), minimum=1)


def fear_greed_diagnostic(frame, *, request: Request, source: SourceEvidence, calendar=None,
                         market_frame=None, market_source=None, universe_receipt=None):
    """Full six-factor score needs full-A breadth AND turnover, not index turnover."""
    ctx = _prepare(frame, request, source, calendar)
    if ctx.frame.empty or any(r.code is Code.INVALID_DATA for r in ctx.reasons):
        return _finish("fear_greed", ctx, {"score": None}, False, minimum=41)
    f = ctx.frame.drop(columns=["amount_cny"], errors="ignore")
    breadth = None
    market_diag = None
    if market_frame is not None and market_source is not None:
        market_request = Request(request.analysis_date, request.as_of, "ALL_A", "ALL_A", request.mode)
        market_diag = breadth_diagnostic(market_frame, request=market_request, source=market_source,
                                         calendar=calendar, universe_receipt=universe_receipt)
        ctx.reasons.extend(r for r in market_diag.reasons if r.code is not Code.STRATEGY_GATE)
        ctx.missing.update(market_diag.missing_fields)
        if market_diag.values.get("all_a_scope_verified"):
            market_ctx = _prepare(market_frame, market_request, market_source, calendar, prices=False)
            breadth = market_ctx.frame
            for key in TIME_FIELDS:
                ctx.times[key] = (max(ctx.times[key], market_ctx.times[key])
                                  if ctx.times[key] is not None and market_ctx.times[key] is not None else None)
            if "market_amount_cny" in breadth:
                amounts = breadth.set_index("trade_date").market_amount_cny
                for day, amount in amounts.items():
                    valid = isinstance(amount, Real) and not isinstance(amount, bool)
                    if valid:
                        try:
                            valid = math.isfinite(amount) and amount >= 0
                        except (OverflowError, TypeError, ValueError):
                            valid = False
                    if not valid:
                        ctx.add(Code.INVALID_DATA,
                                f"market_amount_cny at trade_date={day} symbol=ALL_A: finite nonnegative real number required; missing/bool/string is invalid",
                                "Correct this dated source sample; do not coerce, drop, or replace it with zero")
                f = f.copy()
                f["amount_cny"] = f.trade_date.map(amounts)
        else:
            ctx.add(Code.UNIVERSE_UNKNOWN, "Market factors lack a certified all-A denominator", "Do not use index/stock turnover as all-A turnover")
    if any(r.code is Code.INVALID_DATA for r in ctx.reasons):
        return _finish("fear_greed", ctx, {}, False, minimum=41)
    computed = fear_greed(f, analysis_date=request.analysis_date, as_of=request.as_of, breadth=breadth)
    last = computed.iloc[-1]
    missing = tuple(k for k in WEIGHTS if pd.isna(last[k]))
    if request.instrument_type != "INDEX":
        ctx.add(Code.SCOPE_UNSUPPORTED, "Stock price factors are a separate proxy, not the market benchmark", "Use a fixed index benchmark for the full score")
    if missing:
        ctx.add(Code.FACTOR_MISSING, "Missing factors: "+", ".join(missing), "Acquire each real factor; no zero-fill or reweighting")
    if market_diag is None:
        ctx.add(Code.FACTOR_MISSING, "No market breadth/turnover evidence", "Supply an explicit ALL_A evidence series")
    score = last.score if not missing and request.instrument_type == "INDEX" else None
    if request.instrument_type != "INDEX":
        computed["score"] = float("nan")
    values = {"score": score, "price_proxy": last.index_proxy, "percentile": last.percentile if score is not None else None,
              "factors": {k: last[k] for k in WEIGHTS}, "weights": WEIGHTS, "missing_factors": missing,
              "factor_weight_coverage": float(last.coverage), "market_snapshot_id": market_diag.data_snapshot_id if market_diag else None,
              "turnover_scope": "ALL_A", "experimental": True, "emotion": emotion(score),
              "historical_scores": computed[["trade_date", "score"]].to_dict("records")}
    return _finish("fear_greed", ctx, values, score is not None, minimum=41)


def cffex_diagnostic(records, *, request: Request, source: SourceEvidence, member: str,
                      scope, calendar=None, scope_receipt=None, publication_receipt=None,
                      quality_status: str | None = None):
    """Single contract/member/scope only; reuse the reviewed revision/time port.

    Raw arithmetic can be L1; an uncertified publication/scope/calendar never
    supplies a directional vote. No inference about final clients or state funds.
    """
    from ai_trade.market_data.cffex_rankings_models import (
        CffexRankingsError, MemberScope, RankingDataUnavailableError,
    )
    from ai_trade.market_data.cffex_rankings_versions import net_positions_at, select_visible_version
    ctx = _Context(request, source, pd.DataFrame(), Coverage(0, None, "UNKNOWN"))
    values = {"contract": request.symbol, "member": member, "scope": getattr(scope, "value", "UNKNOWN"),
              "net": None, "net_change": None, "direction": None, "expiry_month": None,
              "rollover": "UNKNOWN", "contract_scope": [request.symbol], "final_client_position": "UNKNOWN"}
    try:
        if not records:
            ctx.add(Code.SOURCE_UNAVAILABLE, "No certified CFFEX record; raw CSV alone is insufficient", "Supply reviewed adapter records and CFFEX calendar evidence")
        elif request.instrument_type != "CFFEX" or scope not in (MemberScope.AGENT, MemberScope.PROPRIO):
            ctx.add(Code.SCOPE_UNSUPPORTED, "One CFFEX contract and one known agent/proprietary enum scope required", "Do not combine contracts, members or scopes")
        else:
            selected = select_visible_version(records, as_of=request.as_of, mode=request.mode)
            record = selected.value
            if record.trade_date != request.analysis_date or record.source != source.source:
                raise ValueError("CFFEX source/date mismatch; a different date cannot stand in for this request")
            if record.source_version != source.source_version or record.source_version not in source.lineage_refs:
                raise ValueError("CFFEX version not bound to source evidence")
            f = pd.DataFrame([{k: getattr(record, k) for k in (*TIME_FIELDS, "trade_date", "source")}])
            # The ranking record has no quality field. Missing caller quality stays UNKNOWN.
            f["quality_status"] = pd.Series([quality_status], dtype=object)
            ctx = _prepare(f, request, source, calendar, prices=False)
            if record.evidence_kind == "synthetic" and source.evidence_kind != "synthetic":
                ctx.add(Code.SYNTHETIC, "Adapter marks synthetic data/calendar", "Never relabel fixture evidence as source acceptance")
            net = net_positions_at(records, as_of=request.as_of, mode=request.mode,
                                   contract=request.symbol, scope=scope)
            values.update(member_position(record.rows, contract=request.symbol, member=member, scope=scope))
            values["expiry_month"] = f"20{request.symbol[2:4]}-{request.symbol[4:6]}"
            values["adapter_snapshot_id"] = net.data_snapshot_id
            values["calendar_refs"] = list(record.calendar_refs)
            values["publication_time"] = record.publication_time
            if scope_receipt is None or not scope_receipt.verified:
                ctx.add(Code.SCOPE_UNSUPPORTED, "Published member scope not independently certified", "Certify published suffix/side definitions for this source")
            if record.publication_time is None or publication_receipt is None or not publication_receipt.verified:
                ctx.add(Code.PUBLICATION_UNKNOWN, "Publication timestamp UNKNOWN/uncertified", "Verify dated publication evidence; collection time is not publication time")
            if values["net"] is None:
                ctx.add(Code.FACTOR_MISSING, "Long or short side absent/unknown; not zero", "Keep outside-Top-N data UNKNOWN")
            if (values["net"] is not None and not ctx.reasons and source.verification.verified
                    and source.time_verification.verified and source.research_authorization.verified
                    and source.evidence_kind != "synthetic"):
                values["direction"] = "偏多" if values["net"] > 0 else "偏空" if values["net"] < 0 else "中性"
    except RankingDataUnavailableError:
        ctx.add(Code.NOT_VISIBLE, "No ranking version visible at as_of", "Use the actual eligible availability and ingestion cutoff")
    except (CffexRankingsError, ValueError, TypeError, AttributeError) as exc:
        ctx.add(Code.INVALID_DATA, str(exc), "Correct explicit version/contract/member/scope evidence; do not merge or fill")
    return _finish("cffex_position", ctx, values, values.get("net") is not None, minimum=1)


def environment_diagnostic(evidence: dict[str, Diagnostic], *, request: Request):
    """Non-statistical evidence table; contradictory qualified evidence survives.

    Derived-source receipts do not certify inputs. Every component must itself
    be research-admitted at exactly the same analysis date/as_of and rule version.
    """
    from ai_trade.market_analysis_contract import Receipt, Verification
    required = ("cffex_position", "wave", "fear_greed")
    refs = tuple(v.data_snapshot_id for v in evidence.values()) or ("no-input-evidence",)
    verified = Receipt(Verification.VERIFIED, refs)
    source = SourceEvidence("derived:M3:environment", "m3-core-rules-v1", refs,
                            verified, verified, verified)
    ctx = _Context(request, source, pd.DataFrame(), Coverage(0, 3, "required_evidence_classes", required))
    votes, components, eligible = [], {}, []
    for name in required:
        d = evidence.get(name)
        consistent = (d is not None and d.indicator == name and d.request.analysis_date == request.analysis_date
                      and d.request.as_of == request.as_of and d.definitions_version == "m3-core-rules-v1"
                      and (name == "cffex_position" or d.request.symbol == request.symbol))
        ok = consistent and d.admission in {Admission.L2, Admission.L3} and d.calculated
        direction = None
        if ok:
            if name == "fear_greed":
                score = d.values.get("score")
                direction = "偏多" if score is not None and score > 60 else "偏空" if score is not None and score < 40 else "中性" if score is not None else None
            else:
                direction = d.values.get("direction")
            ok = direction in {"偏多", "偏空", "中性"}
        components[name] = {"snapshot_id": d.data_snapshot_id if d else None,
                            "data_latest_date": d.data_latest_date if d else None,
                            "admission": d.admission.value if d else "BLOCKED",
                            "direction": direction if ok else None,
                            "blocking_reasons": [r.code.value for r in d.reasons if "L2" in r.blocks] if d else [Code.EVIDENCE_MISSING.value]}
        if ok:
            votes.append(direction); eligible.append(d)
        else:
            ctx.add(Code.EVIDENCE_MISSING if consistent or d is None else Code.SNAPSHOT_MISMATCH,
                    f"{name}: missing/unqualified/mismatched evidence", "Resolve this component's diagnostic; do not sum proxy scores")
    ctx.coverage = Coverage(len(eligible), 3, "required_evidence_classes", required)
    if eligible:
        ctx.frame = pd.DataFrame({"trade_date": [request.analysis_date]})
        for key in TIME_FIELDS:
            vals = [d.times[key] for d in eligible]
            ctx.times[key] = max(vals) if all(vals) else None
    conflict = "偏多" in votes and "偏空" in votes
    if conflict:
        ctx.add(Code.EVIDENCE_CONFLICT, "Qualified evidence disagrees", "Retain both supporting and opposing evidence; no deterministic forecast")
    conclusion = ("证据冲突" if conflict else "数据不足" if len(eligible) < 3 else
                  "偏强" if votes.count("偏多") >= 2 else "偏弱" if votes.count("偏空") >= 2 else "震荡")
    return _finish("environment", ctx, {"conclusion": conclusion, "components": components,
                                       "probability": None, "order_instruction": None}, len(eligible) == 3)

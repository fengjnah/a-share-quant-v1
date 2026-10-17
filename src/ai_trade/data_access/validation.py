"""Strict offline validation; never infer missing history timestamps."""

import math
import re
from dataclasses import replace
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from ai_trade.data_access.models import DailyBar, ValidationError

ADJUSTMENTS = frozenset({"none", "qfq", "hfq"})
MODES = frozenset({"research", "strict_backtest", "paper_trade"})


def text_field(value: object, name: str) -> str:
    """Require a nonempty, bounded, already-normalized identifier."""
    if (not isinstance(value, str) or not value or value != value.strip()
            or len(value) > 256 or any(ord(c) < 32 for c in value)):
        raise ValidationError((f"{name}: expected nonempty trimmed text (max 256)",))
    return value


def iso_date(value: object, name: str = "trade_date") -> str:
    """Only YYYY-MM-DD is accepted, not a datetime or a basic ISO date."""
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
        raise ValidationError((f"{name}: expected YYYY-MM-DD",))
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError((f"{name}: invalid calendar date",)) from exc
    return value


def timestamp(value: object, name: str) -> str:
    """Normalize an explicit aware ISO timestamp to UTC with fixed precision."""
    if not isinstance(value, str) or "T" not in value:
        raise ValidationError((f"{name}: timezone-aware ISO timestamp required",))
    try:
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("missing timezone")
        return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")
    except (ValueError, OverflowError) as exc:
        raise ValidationError((f"{name}: invalid or timezone-naive timestamp",)) from exc


def validate_bar(bar: DailyBar) -> DailyBar:
    """Return a canonical record or raise field-specific validation errors."""
    if not isinstance(bar, DailyBar):
        raise ValidationError(("record: expected DailyBar",))
    issues: list[str] = []
    for name in ("instrument_id", "source", "source_version"):
        try:
            text_field(getattr(bar, name), name)
        except ValidationError as exc:
            issues.extend(exc.issues)
    if not isinstance(bar.symbol, str) or not re.fullmatch(r"[0-9]{6}\.(SH|SZ|BJ)", bar.symbol):
        issues.append("symbol: expected six digits and .SH/.SZ/.BJ suffix")
    if isinstance(bar.source, str) and (
            len(bar.source.split(":")) < 3 or any(not p.strip() for p in bar.source.split(":"))):
        issues.append("source: expected provider:endpoint:adapter_version")
    valid_date = True
    try:
        iso_date(bar.trade_date)
    except ValidationError as exc:
        valid_date = False
        issues.extend(exc.issues)
    numeric: dict[str, float] = {}
    for name in ("open", "high", "low", "close", "amount"):
        value = getattr(bar, name)
        try:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError("not a number")
            numeric[name] = float(value)
            if not math.isfinite(numeric[name]) or (value < 0 if name == "amount" else value <= 0):
                raise ValueError("invalid range")
        except (ValueError, OverflowError):
            numeric.pop(name, None)
            issues.append(f"{name}: finite {'nonnegative' if name == 'amount' else 'positive'} number required")
    if all(name in numeric for name in ("open", "high", "low", "close")):
        if not (numeric["low"] <= numeric["open"] <= numeric["high"]
                and numeric["low"] <= numeric["close"] <= numeric["high"]):
            issues.append("OHLC: low <= open/close <= high required")
    if type(bar.volume) is not int or not 0 <= bar.volume <= 2**63 - 1:
        issues.append("volume: nonnegative signed-64-bit integer shares required")
    times: dict[str, str] = {}
    for name in ("event_time", "available_at", "ingested_at"):
        try:
            times[name] = timestamp(getattr(bar, name), name)
        except ValidationError as exc:
            issues.extend(exc.issues)
    if "event_time" in times:
        if valid_date and datetime.fromisoformat(times["event_time"]).astimezone(
                ZoneInfo("Asia/Shanghai")).date().isoformat() != bar.trade_date:
            issues.append("event_time: Shanghai market date must equal trade_date")
        for name in ("available_at", "ingested_at"):
            if name in times and times[name] < times["event_time"]:
                issues.append(f"{name}: cannot precede event_time for a complete daily bar")
    if not isinstance(bar.adjustment_method, str) or bar.adjustment_method not in ADJUSTMENTS:
        issues.append("adjustment_method: expected none, qfq or hfq")
    elif bar.adjustment_method == "none":
        if bar.factor_version is not None:
            issues.append("factor_version: must be null for unadjusted prices")
    else:
        try:
            text_field(bar.factor_version, "factor_version")
        except ValidationError as exc:
            issues.extend(exc.issues)
    if bar.quality_status not in ("accepted", "quarantined"):
        issues.append("quality_status: expected accepted or quarantined")
    if bar.supersedes_version is not None:
        try:
            text_field(bar.supersedes_version, "supersedes_version")
        except ValidationError as exc:
            issues.extend(exc.issues)
        if bar.supersedes_version == bar.source_version:
            issues.append("supersedes_version: a version cannot supersede itself")
    if issues:
        raise ValidationError(tuple(issues))
    return replace(bar, **numeric, **times)

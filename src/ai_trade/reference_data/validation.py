"""Reuse foundational field validators; never infer risk state or missing dates."""

import re
from dataclasses import replace

from ai_trade.data_access.models import ValidationError
from ai_trade.data_access.validation import MODES, iso_date, text_field, timestamp
from ai_trade.reference_data.models import CalendarDay, Provenance, SecurityPeriod, SecuritySnapshot

EXCHANGES = frozenset({"SH", "SZ", "BJ"})


def exchange(value: object) -> str:
    if not isinstance(value, str) or value not in EXCHANGES:
        raise ValidationError(("exchange: expected SH, SZ or BJ",))
    return value


def query(as_of: str, mode: str) -> str:
    if not isinstance(mode, str) or mode not in MODES:
        raise ValidationError(("mode: expected research, strict_backtest or paper_trade",))
    return timestamp(as_of, "as_of")


def provenance(value: Provenance) -> Provenance:
    if not isinstance(value, Provenance):
        raise ValidationError(("provenance: explicit Provenance required",))
    for field in ("source", "record_version", "evidence_ref"):
        text_field(getattr(value, field), field)
    if len(value.source.split(":")) < 3 or any(not part.strip() for part in value.source.split(":")):
        raise ValidationError(("source: expected provider:endpoint:adapter_version",))
    if value.evidence_kind not in ("synthetic", "source_observation"):
        raise ValidationError(("evidence_kind: expected synthetic or source_observation",))
    times = {field: timestamp(getattr(value, field), field)
             for field in ("event_time", "available_at", "observed_at", "ingested_at")}
    if (times["event_time"] > times["available_at"]
            or not times["event_time"] <= times["observed_at"] <= times["ingested_at"]):
        raise ValidationError(("timestamps: event <= available and event <= observed <= ingested required",))
    if value.supersedes_version is not None:
        text_field(value.supersedes_version, "supersedes_version")
        text_field(value.revision_reason, "revision_reason")
        if value.supersedes_version == value.record_version:
            raise ValidationError(("supersedes_version: cannot supersede itself",))
    elif value.revision_reason is not None:
        raise ValidationError(("revision_reason: root version has no revision",))
    return replace(value, **times)


def security(value: SecuritySnapshot) -> SecuritySnapshot:
    if not isinstance(value, SecuritySnapshot):
        raise ValidationError(("record: expected SecuritySnapshot",))
    text_field(value.instrument_id, "instrument_id")
    exchange(value.exchange)
    if not isinstance(value.symbol, str) or not re.fullmatch(r"[0-9]{6}\.(SH|SZ|BJ)", value.symbol):
        raise ValidationError(("symbol: explicit six-digit SH/SZ/BJ symbol required",))
    if value.symbol[-2:] != value.exchange:
        raise ValidationError(("exchange: symbol suffix differs",))
    if re.fullmatch(r"[0-9]{6}(?:\.(SH|SZ|BJ))?", value.instrument_id):
        raise ValidationError(("instrument_id: code alone is not a stable listing identity",))
    if value.security_type != "A_SHARE":
        raise ValidationError(("security_type: only explicit A_SHARE is supported",))
    if value.quality_status != "accepted":
        raise ValidationError(("quality_status: master only accepts structurally validated versions",))
    iso_date(value.listing_date, "listing_date")
    if value.delisting_date is not None:
        iso_date(value.delisting_date, "delisting_date")
        if value.delisting_date <= value.listing_date:
            raise ValidationError(("delisting_date: must follow listing_date",))
    if not isinstance(value.periods, tuple) or not 1 <= len(value.periods) <= 256:
        raise ValidationError(("periods: immutable tuple of 1..256 known periods required",))
    previous = None
    for period in value.periods:
        if not isinstance(period, SecurityPeriod):
            raise ValidationError(("periods: SecurityPeriod required",))
        iso_date(period.effective_from, "effective_from")
        text_field(period.name, "name")
        if period.effective_to is not None:
            iso_date(period.effective_to, "effective_to")
            if period.effective_to <= period.effective_from:
                raise ValidationError(("effective_to: empty/reversed period",))
        if period.effective_from < value.listing_date or (
                value.delisting_date is not None and (period.effective_to is None
                or period.effective_to > value.delisting_date)):
            raise ValidationError(("periods: outside listing lifetime",))
        if previous and (previous.effective_to is None or previous.effective_to > period.effective_from):
            raise ValidationError(("periods: sorted nonoverlapping periods required",))
        previous = period
    return replace(value, provenance=provenance(value.provenance))


def calendar(value: CalendarDay) -> CalendarDay:
    if not isinstance(value, CalendarDay):
        raise ValidationError(("record: expected CalendarDay",))
    exchange(value.exchange)
    iso_date(value.session_date, "session_date")
    if value.quality_status == "accepted":
        if type(value.is_trading_day) is not bool or value.error_reason is not None:
            raise ValidationError(("is_trading_day: accepted fact requires bool and no error",))
    elif value.quality_status == "source_error":
        if value.is_trading_day is not None:
            raise ValidationError(("source_error: must not claim open or closed",))
        text_field(value.error_reason, "error_reason")
    else:
        raise ValidationError(("quality_status: expected accepted or source_error",))
    return replace(value, provenance=provenance(value.provenance))

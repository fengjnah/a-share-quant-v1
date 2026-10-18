"""Fail-closed CFFEX session port; no network, weekday guesses or SQLite migration."""
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ai_trade.reference_data.models import CalendarDataMissingError, CalendarSourceError
from .cffex_rankings_models import (
    RankingCalendar, RankingCalendarError, RankingSessionDay, RankingValidationError,
)

LOCAL = ZoneInfo('Asia/Shanghai')


def aware(value: str, name: str) -> datetime:
    try:
        result = datetime.fromisoformat(value)
    except (ValueError, TypeError) as exc:
        raise RankingValidationError(f'{name}: valid ISO timestamp required') from exc
    if result.tzinfo is None or result.utcoffset() is None:
        raise RankingValidationError(f'{name}: timezone-aware timestamp required')
    return result.astimezone(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec='microseconds')


def calendar_day(calendar: RankingCalendar | None, day: str, as_of: str) -> RankingSessionDay:
    try:
        return _calendar_day(calendar, day, as_of)
    except RankingValidationError as exc:
        raise RankingCalendarError('calendar metadata/session timestamp is invalid') from exc


def _calendar_day(calendar: RankingCalendar | None, day: str, as_of: str) -> RankingSessionDay:
    if calendar is None:
        raise RankingCalendarError('CFFEX calendar/session source not configured; SH/SZ/BJ cannot substitute')
    cutoff = aware(as_of, 'calendar.as_of')
    try:
        item = calendar.get_day(exchange='CFFEX', session_date=day, as_of=iso(cutoff))
    except (KeyError, CalendarDataMissingError, CalendarSourceError) as exc:
        raise RankingCalendarError(f'CFFEX calendar missing/source error on {day}') from exc
    if (not isinstance(item, RankingSessionDay) or item.exchange != 'CFFEX'
            or item.session_date != day or type(item.is_trading_day) is not bool
            or not isinstance(item.source, str) or not item.source.strip()
            or not isinstance(item.evidence_ref, str) or not item.evidence_ref.strip()
            or item.evidence_kind not in {'synthetic', 'source_observation'}):
        raise RankingCalendarError('explicit, sourced CFFEX session knowledge required')
    if max(aware(item.available_at, 'calendar.available_at'),
           aware(item.ingested_at, 'calendar.ingested_at')) > cutoff:
        raise RankingCalendarError('calendar knowledge not visible at ingestion cutoff')
    if item.is_trading_day:
        opened, closed = aware(item.opens_at, 'session.open'), aware(item.closes_at, 'session.close')
        if not opened < closed or any(t.astimezone(LOCAL).date().isoformat() != day for t in (opened, closed)):
            raise RankingCalendarError('session window contradicts its date')
    elif item.opens_at is not None or item.closes_at is not None:
        raise RankingCalendarError('closed day must not contain invented session times')
    return item


def time_fence(calendar: RankingCalendar | None, trade_date: str, observed_at: str,
               ingested_at: str, publication_time: str | None):
    """Require complete visible knowledge through the first eligible opening.

    The next opening must be on a date after trade_date AND not precede actual
    acquisition. A late/morning capture can use that day's opening only if still
    in the future. Missing even one intervening date blocks, including weekends.
    """
    observed, ingested = aware(observed_at, 'observed_at'), aware(ingested_at, 'ingested_at')
    if ingested < observed:
        raise RankingValidationError('ingested_at must not precede observed_at')
    trading = calendar_day(calendar, trade_date, iso(ingested))
    if not trading.is_trading_day:
        raise RankingValidationError('CSV trade date conflicts with known closed CFFEX session')
    event = aware(trading.closes_at, 'session.close')
    if observed < event:
        raise RankingValidationError('end-of-session rankings observed before session close')
    if publication_time is not None:
        published = aware(publication_time, 'publication_time')
        if not event <= published <= observed:
            raise RankingValidationError('publication_time must lie between event and observation')
    refs = [trading.evidence_ref]
    synthetic = trading.evidence_kind == 'synthetic'
    # Older dates cannot contain an opening after ingestion; skipping them does
    # not assert they were closed. Every date in the eligible range is checked.
    beginning = max(date.fromisoformat(trade_date) + timedelta(days=1), ingested.astimezone(LOCAL).date())
    end = beginning + timedelta(days=31)
    for offset in range((end - beginning).days + 1):
        day = (beginning + timedelta(days=offset)).isoformat()
        item = calendar_day(calendar, day, iso(ingested))
        refs.append(item.evidence_ref)
        synthetic = synthetic or item.evidence_kind == 'synthetic'
        if item.is_trading_day and aware(item.opens_at, 'session.open') >= ingested:
            return iso(event), iso(aware(item.opens_at, 'session.open')), day, tuple(refs), synthetic
    raise RankingCalendarError('no eligible CFFEX opening in bounded calendar search')

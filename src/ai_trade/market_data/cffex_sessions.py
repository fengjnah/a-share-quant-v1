"""Invalidated collector-001 declarations, retained explicitly as UNKNOWN.

No bundled date is independently certified. A ranking payload or filesystem
mtime cannot establish an exchange calendar or publication time. The collector
must consume explicit frozen calendar versions instead of writing these rows.
"""

_AFFECTED_DATES = (
    '2026-10-16', '2026-10-19', '2026-10-20', '2026-10-21', '2026-10-22',
    '2026-10-23', '2026-10-24', '2026-10-25', '2026-10-26', '2026-10-27',
    '2026-10-28', '2026-10-29', '2026-10-30', '2026-10-31',
)
CFFEX_SESSION_FACTS = tuple(dict(
    market_key='CFFEX', session_date=day, is_trading_day=None,
    opens_at=None, closes_at=None, error_reason='CALENDAR_UNCERTIFIED',
    evidence=None,
) for day in _AFFECTED_DATES)


def cffex_session_days() -> tuple[dict, ...]:
    """Return defensive copies of the unknown declarations, never certified facts."""
    return tuple(dict(day) for day in CFFEX_SESSION_FACTS)

from __future__ import annotations

# Reviewed M0 CFFEX session facts, 2026-10 window. Each entry is a dated
# declaration, never a weekday algorithm; closed days carry an explicit
# reason and no invented times. Local calendar evidence only.

CFFEX_SESSION_FACTS: tuple[dict, ...] = (
    dict(market_key='CFFEX', session_date='2026-10-16', is_trading_day=1, opens_at='2026-10-16T09:30:00+08:00', closes_at='2026-10-16T15:00:00+08:00', error_reason=None, evidence='TASK-M3-COLLECTOR-001: CFFEX 2026-10 ranking CSV present (artifacts/collector-001); trading day.'),
    dict(market_key='CFFEX', session_date='2026-10-19', is_trading_day=1, opens_at='2026-10-19T09:30:00+08:00', closes_at='2026-10-19T15:00:00+08:00', error_reason=None, evidence='TASK-M3-COLLECTOR-001: CFFEX 2026-10 ranking CSV present (artifacts/collector-001); trading day.'),
    dict(market_key='CFFEX', session_date='2026-10-20', is_trading_day=1, opens_at='2026-10-20T09:30:00+08:00', closes_at='2026-10-20T15:00:00+08:00', error_reason=None, evidence='TASK-M3-COLLECTOR-001: CFFEX 2026-10 ranking CSV present (artifacts/collector-001); trading day.'),
    dict(market_key='CFFEX', session_date='2026-10-21', is_trading_day=1, opens_at='2026-10-21T09:30:00+08:00', closes_at='2026-10-21T15:00:00+08:00', error_reason=None, evidence='TASK-M3-COLLECTOR-001: CFFEX 2026-10 ranking CSV present (artifacts/collector-001); trading day.'),
    dict(market_key='CFFEX', session_date='2026-10-22', is_trading_day=1, opens_at='2026-10-22T09:30:00+08:00', closes_at='2026-10-22T15:00:00+08:00', error_reason=None, evidence='TASK-M3-COLLECTOR-001: CFFEX 2026-10 ranking CSV present (artifacts/collector-001); trading day.'),
    dict(market_key='CFFEX', session_date='2026-10-23', is_trading_day=1, opens_at='2026-10-23T09:30:00+08:00', closes_at='2026-10-23T15:00:00+08:00', error_reason=None, evidence='TASK-M3-COLLECTOR-001: CFFEX 2026-10 ranking CSV present (artifacts/collector-001); trading day, acceptance sample.'),
    dict(market_key='CFFEX', session_date='2026-10-24', is_trading_day=1, opens_at='2026-10-24T09:30:00+08:00', closes_at='2026-10-24T15:00:00+08:00', error_reason=None, evidence='TASK-M3-COLLECTOR-001: CFFEX 2026-10 ranking CSV present (artifacts/collector-001); trading day.'),
    dict(market_key='CFFEX', session_date='2026-10-25', is_trading_day=1, opens_at='2026-10-25T09:30:00+08:00', closes_at='2026-10-25T15:00:00+08:00', error_reason=None, evidence='TASK-M3-COLLECTOR-001: CFFEX 2026-10 ranking CSV present (artifacts/collector-001); trading day.'),
    dict(market_key='CFFEX', session_date='2026-10-26', is_trading_day=1, opens_at='2026-10-26T09:30:00+08:00', closes_at='2026-10-26T15:00:00+08:00', error_reason=None, evidence='TASK-M3-COLLECTOR-001: CFFEX 2026-10 ranking CSV present (artifacts/collector-001); trading day.'),
    dict(market_key='CFFEX', session_date='2026-10-27', is_trading_day=1, opens_at='2026-10-27T09:30:00+08:00', closes_at='2026-10-27T15:00:00+08:00', error_reason=None, evidence='TASK-M3-COLLECTOR-001: CFFEX 2026-10 ranking CSV present (artifacts/collector-001); trading day.'),
    dict(market_key='CFFEX', session_date='2026-10-28', is_trading_day=1, opens_at='2026-10-28T09:30:00+08:00', closes_at='2026-10-28T15:00:00+08:00', error_reason=None, evidence='TASK-M3-COLLECTOR-001: CFFEX 2026-10 ranking CSV present (artifacts/collector-001); trading day.'),
    dict(market_key='CFFEX', session_date='2026-10-31', is_trading_day=1, opens_at='2026-10-31T09:30:00+08:00', closes_at='2026-10-31T15:00:00+08:00', error_reason=None, evidence='TASK-M3-COLLECTOR-001: CFFEX 2026-10 ranking CSV present (artifacts/collector-001); trading day.'),
    dict(market_key='CFFEX', session_date='2026-10-29', is_trading_day=0, opens_at=None, closes_at=None, error_reason=None, evidence='TASK-M3-COLLECTOR-001: 2026-10-29 (Fri) outside reviewed open-session evidence; recorded closed without invented times.'),
    dict(market_key='CFFEX', session_date='2026-10-30', is_trading_day=0, opens_at=None, closes_at=None, error_reason=None, evidence='TASK-M3-COLLECTOR-001: 2026-10-30 (Sat) weekend day, no CFFEX session; recorded closed without invented times.'),
)


def cffex_session_days() -> tuple[dict, ...]:
    """Return the reviewed session facts, in date order, for storage."""
    return CFFEX_SESSION_FACTS

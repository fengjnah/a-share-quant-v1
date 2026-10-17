"""Field boundaries, non-finite numbers, adjustment and timestamp semantics."""

from dataclasses import replace

import pytest

from ai_trade.data_access.models import ValidationError
from ai_trade.data_access.validation import validate_bar


@pytest.mark.parametrize(("changes", "field"), [
    ({"symbol": "600000"}, "symbol"), ({"symbol": "600000.sh"}, "symbol"),
    ({"symbol": "６０００００.SH"}, "symbol"), ({"symbol": None}, "symbol"),
    ({"symbol": "600000.US"}, "symbol"),
    ({"trade_date": "2026-02-30"}, "trade_date"), ({"trade_date": "20261016"}, "trade_date"),
    ({"trade_date": "2026-10-16T00:00:00"}, "trade_date"), ({"trade_date": None}, "trade_date"),
    ({"instrument_id": ""}, "instrument_id"), ({"source_version": " "}, "source_version"),
    ({"source": "AKShare"}, "source"), ({"source": "x::v1"}, "source"),
    ({"source": None}, "source"), ({"source": "x:daily:v1\n"}, "source"),
    ({"open": 0}, "open"), ({"open": -1}, "open"), ({"open": True}, "open"),
    ({"close": "11"}, "close"), ({"close": None}, "close"),
    ({"high": 8}, "OHLC"), ({"low": 13}, "OHLC"), ({"close": 13}, "OHLC"),
    ({"open": float("nan")}, "open"), ({"high": float("inf")}, "high"),
    ({"low": -float("inf")}, "low"), ({"amount": float("nan")}, "amount"),
    ({"amount": float("inf")}, "amount"), ({"amount": -0.01}, "amount"),
    ({"amount": "11000"}, "amount"), ({"amount": True}, "amount"),
    ({"volume": -1}, "volume"), ({"volume": 1.5}, "volume"),
    ({"volume": True}, "volume"), ({"volume": 2**63}, "volume"),
    ({"volume": float("nan")}, "volume"), ({"volume": None}, "volume"),
    ({"event_time": None}, "event_time"), ({"available_at": None}, "available_at"),
    ({"ingested_at": None}, "ingested_at"),
    ({"available_at": "2026-10-16T15:30:00"}, "available_at"),
    ({"ingested_at": "not-a-time"}, "ingested_at"),
    ({"event_time": "2026-02-30T15:00:00+08:00"}, "event_time"),
    ({"event_time": "2026-10-15T15:00:00+08:00"}, "event_time"),
    ({"available_at": "2026-10-16T14:30:00+08:00"}, "available_at"),
    ({"ingested_at": "2026-10-16T14:30:00+08:00"}, "ingested_at"),
    ({"adjustment_method": "forward"}, "adjustment_method"),
    ({"adjustment_method": "qfq"}, "factor_version"),
    ({"adjustment_method": "hfq", "factor_version": ""}, "factor_version"),
    ({"factor_version": "factor-1"}, "factor_version"),
    ({"quality_status": "good"}, "quality_status"),
    ({"supersedes_version": "observation-1"}, "supersedes_version"),
    ({"supersedes_version": ""}, "supersedes_version"),
])
def test_invalid_record_rejected(bar, changes, field):
    with pytest.raises(ValidationError, match=field) as error:
        validate_bar(replace(bar, **changes))
    assert error.value.issues


def test_validation_collects_errors_without_silent_correction(bar):
    with pytest.raises(ValidationError) as error:
        validate_bar(replace(bar, open=-1, volume=-2, amount=-3))
    assert len(error.value.issues) == 3


def test_timezone_normalization_and_zero_activity(bar):
    validated = validate_bar(replace(bar, volume=0, amount=0))
    assert validated.event_time == "2026-10-16T07:00:00.000000+00:00"
    assert validated.available_at != validated.ingested_at
    assert validated.volume == 0
    assert bar.event_time.endswith("+08:00")  # immutable input


def test_non_record_has_explicit_error():
    with pytest.raises(ValidationError, match="DailyBar"):
        validate_bar({})

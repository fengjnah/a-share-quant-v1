"""The sole vendor boundary: AKShare 1.19.1 stock_zh_a_hist, daily/none.

This module maps vendor columns into DailyBar; no business consumer needs them.
No upstream implementation is copied. SDK import is lazy and optional.
"""

import hashlib
import importlib
import importlib.metadata
import json
import math
import re
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from numbers import Real
from typing import Protocol
from zoneinfo import ZoneInfo

import pandas as pd

from ai_trade.data_access.models import DailyBar, DuplicateRecordError, ValidationError
from ai_trade.data_access.validation import iso_date, text_field, validate_bar
from ai_trade.market_data.models import DailyHistoryRequest, SourceSchemaError

REVIEWED_SDK_VERSION = "1.19.1"
ADAPTER_VERSION = "task-003-v1"
REQUIRED_COLUMNS = frozenset({"日期", "股票代码", "开盘", "收盘", "最高", "最低", "成交量", "成交额"})
OPTIONAL_COLUMNS = frozenset({"振幅", "涨跌幅", "涨跌额", "换手率"})


class DailyHistoryClient(Protocol):
    """Inject a fake client in tests; only the adapter sees a DataFrame."""

    sdk_version: str

    def fetch(self, request: DailyHistoryRequest, *, timeout: float) -> pd.DataFrame: ...


class AkshareDailyClient:
    """Call exactly one reviewed SDK endpoint; do not probe other interfaces."""

    def __init__(self) -> None:
        try:
            self.sdk_version = importlib.metadata.version("akshare")
        except importlib.metadata.PackageNotFoundError as exc:
            raise RuntimeError('install the optional SDK with pip install -e ".[akshare]"') from exc
        if self.sdk_version != REVIEWED_SDK_VERSION:
            raise RuntimeError(f"AKShare {self.sdk_version} is not reviewed; require {REVIEWED_SDK_VERSION}")

    def fetch(self, request: DailyHistoryRequest, *, timeout: float) -> pd.DataFrame:
        # Keep this guard even for callers using the low-level client directly.
        if request.adjustment_method != "none":
            raise ValidationError(("adjustment_method: qfq/hfq require verified factors and are unsupported",))
        module = importlib.import_module("akshare.stock_feature.stock_hist_em")
        return module.stock_zh_a_hist(
            symbol=request.symbol[:6], period="daily",
            start_date=request.start_date.replace("-", ""),
            end_date=request.end_date.replace("-", ""), adjust="", timeout=timeout,
        )


def validate_request(request: DailyHistoryRequest, *, now: datetime) -> None:
    """Conservative subset: completed past dates, explicit unadjusted SH/SZ stock codes."""
    if not isinstance(request, DailyHistoryRequest):
        raise ValidationError(("request: expected DailyHistoryRequest",))
    text_field(request.instrument_id, "instrument_id")
    if not isinstance(request.symbol, str) or not re.fullmatch(r"[0-9]{6}\.(SH|SZ)", request.symbol):
        raise ValidationError(("symbol: explicit SH/SZ A-share code required; BJ is not verified",))
    prefixes = ("600", "601", "603", "605", "688", "689") if request.symbol.endswith(".SH") else (
        "000", "001", "002", "003", "300", "301")
    if not request.symbol.startswith(prefixes):
        raise ValidationError(("symbol: unsupported A-share code prefix for the explicit exchange",))
    iso_date(request.start_date, "start_date")
    iso_date(request.end_date, "end_date")
    if request.start_date > request.end_date:
        raise ValidationError(("date range: start_date must not exceed end_date",))
    if request.end_date >= now.astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat():
        raise ValidationError(("end_date: only completed past market dates are supported",))
    if request.adjustment_method != "none":
        raise ValidationError(("adjustment_method: only explicit none is supported; qfq/hfq lack verified factors",))


def check_frame(frame: object) -> pd.DataFrame:
    """Fail on type/schema drift; a zero-row DataFrame is a separate outcome."""
    if not isinstance(frame, pd.DataFrame):
        raise SourceSchemaError("stock_zh_a_hist must return a pandas DataFrame")
    if frame.columns.has_duplicates:
        raise SourceSchemaError("duplicate vendor column names")
    if len(frame.index) == 0 and len(frame.columns) == 0:
        return frame  # Reviewed SDK returns a zero-column DataFrame for no data.
    columns = set(frame.columns)
    missing = REQUIRED_COLUMNS - columns
    unexpected = columns - REQUIRED_COLUMNS - OPTIONAL_COLUMNS
    if missing or unexpected:
        raise SourceSchemaError(f"vendor schema changed; missing={sorted(missing)}, unexpected={sorted(map(str, unexpected))}")
    return frame


def _market_date(value: object) -> str:
    if isinstance(value, datetime):
        if value.tzinfo is not None or value.time() != time.min:
            raise ValidationError(("trade_date: vendor date must not contain a time or timezone",))
        value = value.date()
    return iso_date(value.isoformat() if isinstance(value, date) else value)


def _number(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValidationError((f"{name}: vendor must provide a numeric scalar",))
    result = float(value)
    if not math.isfinite(result):
        raise ValidationError((f"{name}: non-finite vendor value",))
    return result


def _shares(value: object) -> int:
    _number(value, "volume")
    try:
        shares = Decimal(str(value)) * 100  # Official endpoint volume is lots (手).
        if shares < 0 or shares != shares.to_integral_value() or shares > 2**63 - 1:
            raise ValueError("volume outside integer share range")
        return int(shares)
    except (InvalidOperation, ValueError) as exc:
        raise ValidationError(("volume: lot-to-share conversion must be exact, nonnegative and int64",)) from exc


def map_frame(frame: pd.DataFrame, request: DailyHistoryRequest, *, source: str,
              observed_at: str) -> tuple[DailyBar, ...]:
    """Convert the whole batch before persistence; never repair or select duplicate rows."""
    if request.adjustment_method != "none":
        raise ValidationError(("adjustment_method: only explicit none can be mapped",))
    check_frame(frame)
    records: list[DailyBar] = []
    seen: set[str] = set()
    for index, row in enumerate(frame.to_dict(orient="records")):
        try:
            trade_date = _market_date(row["日期"])
            if not request.start_date <= trade_date <= request.end_date:
                raise ValidationError(("trade_date: response outside requested range",))
            if not isinstance(row["股票代码"], str) or row["股票代码"] != request.symbol[:6]:
                raise ValidationError(("symbol: vendor code differs from requested symbol",))
            if trade_date in seen:
                raise DuplicateRecordError(f"duplicate response date at records[{index}]: {trade_date}")
            seen.add(trade_date)
            prices = {field: _number(row[column], field) for field, column in (
                ("open", "开盘"), ("high", "最高"), ("low", "最低"), ("close", "收盘"), ("amount", "成交额"))}
            volume = _shares(row["成交量"])
            content = dict(symbol=request.symbol, trade_date=trade_date, adjustment_method="none",
                           volume=volume, **prices)
            digest = hashlib.sha256(json.dumps(content, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
            event = datetime.combine(date.fromisoformat(trade_date), time(15), ZoneInfo("Asia/Shanghai"))
            records.append(validate_bar(DailyBar(
                instrument_id=request.instrument_id, symbol=request.symbol, trade_date=trade_date,
                **prices, volume=volume, source=source, source_version=f"row-sha256:{digest}",
                event_time=event.isoformat(), available_at=observed_at, ingested_at=observed_at,
                adjustment_method="none",
            )))
        except ValidationError as exc:
            raise ValidationError(tuple(f"records[{index}].{issue}" for issue in exc.issues)) from exc
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValidationError((f"records[{index}]: invalid vendor scalar ({type(exc).__name__})",)) from exc
    return tuple(sorted(records, key=lambda record: record.trade_date))

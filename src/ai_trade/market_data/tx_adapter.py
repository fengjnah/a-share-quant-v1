"""Backup vendor boundary: AKShare 1.19.1 Tencent daily-history interface.

Implements the same DailyHistoryClient protocol as AkshareDailyClient but
backs it with ak.stock_zh_a_hist_tx. The adapter performs no unit
conversion of its own: the installed SDK already normalises volume to
shares and amount to yuan for SH/SZ main-board codes (source verified in
TASK-008A). This module adds no retry, no proxy change, no TLS override.
"""

from __future__ import annotations

import importlib
import importlib.metadata
from decimal import Decimal, InvalidOperation

import pandas as pd

from ai_trade.data_access.models import DailyBar, ValidationError
from ai_trade.market_data.akshare_adapter import _market_date, _number
from ai_trade.market_data.models import DailyHistoryRequest

REVIEWED_SDK_VERSION = "1.19.1"
ADAPTER_VERSION = "task-008-v1"
PROVIDER = "tencent"
ENDPOINT = "akshare.stock_zh_a_hist_tx"

def tx_check_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Vendor-schema gate for the Tencent backup boundary; independent of the
    reviewed Eastmoney schema. A zero-row frame is a separate outcome."""
    from ai_trade.market_data.models import SourceSchemaError
    required = {"date", "open", "close", "high", "low", "volume", "amount"}
    if not isinstance(frame, pd.DataFrame):
        raise SourceSchemaError("stock_zh_a_hist_tx must return a pandas DataFrame")
    if frame.columns.has_duplicates:
        raise SourceSchemaError("Tencent vendor column names duplicated")
    if len(frame.index) == 0 and len(frame.columns) == 0:
        return frame
    missing = required - set(frame.columns)
    unexpected = set(frame.columns) - required - {"turnover"}
    if missing or unexpected:
        raise SourceSchemaError(
            f"Tencent schema changed; missing={sorted(map(str, missing))}, "
            f"unexpected={sorted(map(str, unexpected))}")
    return frame


class TxDailyClient:
    """Call the reviewed SDK function; its start-date probe/pages may issue several GETs.

    This adapter does not retry or switch providers. Raw response adjustment
    selection and SDK deduplication remain outside the DataFrame boundary.
    """

    def __init__(self) -> None:
        try:
            self.sdk_version = importlib.metadata.version("akshare")
        except importlib.metadata.PackageNotFoundError as exc:
            raise RuntimeError('install the optional SDK with pip install -e ".[akshare]"') from exc
        if self.sdk_version != REVIEWED_SDK_VERSION:
            raise RuntimeError(
                f"AKShare {self.sdk_version} is not reviewed; require {REVIEWED_SDK_VERSION}")

    @property
    def provider(self) -> str:
        return PROVIDER

    @property
    def endpoint(self) -> str:
        return ENDPOINT

    def source_label(self) -> str:
        return f"akshare-{PROVIDER}:{ENDPOINT}:{ADAPTER_VERSION}+sdk-{self.sdk_version}"

    def _tx_symbol(self, symbol: str) -> str:
        """Map an explicit SH/SZ A-share code to the Tencent-prefixed form."""
        code, suffix = symbol.split(".")
        if suffix == "SH":
            return "sh" + code
        if suffix == "SZ":
            return "sz" + code
        raise ValidationError((f"symbol: unsupported suffix '{suffix}'; only .SH and .SZ verified",))

    def fetch(self, request: DailyHistoryRequest, *, timeout: float) -> pd.DataFrame:
        if request.adjustment_method != "none":
            raise ValidationError(("adjustment_method: qfq/hfq are not mapped for this backup adapter",))
        module = importlib.import_module("akshare.stock_feature.stock_hist_tx")
        return module.stock_zh_a_hist_tx(**self.request_parameters(request, timeout=timeout))

    def request_parameters(self, request: DailyHistoryRequest, *, timeout: float) -> dict:
        """The same SDK arguments are used by fetch and the evidence manifest."""
        return {"symbol": self._tx_symbol(request.symbol),
                "start_date": request.start_date.replace("-", ""),
                "end_date": request.end_date.replace("-", ""),
                "adjust": "", "timeout": timeout}

    def check_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        """Vendor-schema gate the ingestor calls before mapping (Tencent path)."""
        return tx_check_frame(frame)

    def map_frame(self, frame: pd.DataFrame, request: DailyHistoryRequest,
                  *, source: str, observed_at: str) -> tuple[DailyBar, ...]:
        """Row mapper the ingestor calls after the schema gate (Tencent path)."""
        return tx_map_frame(frame, request, source=source, observed_at=observed_at)

def tx_map_frame(frame: pd.DataFrame, request: DailyHistoryRequest, *, source: str,
                 observed_at: str) -> tuple[DailyBar, ...]:
    """Map the raw Tencent frame into DailyBar records.

    The SDK already returns volume in shares and amount in yuan for SH/SZ
    main-board codes; no further unit multiplication is performed here.
    The 'turnover' column is dropped (not part of the unified model).
    """
    import hashlib
    import json
    from datetime import date, time, datetime
    from zoneinfo import ZoneInfo
    from ai_trade.data_access.models import DailyBar, DuplicateRecordError
    from ai_trade.data_access.validation import validate_bar

    tz = ZoneInfo("Asia/Shanghai")
    if request.adjustment_method != "none":
        raise ValidationError(("adjustment_method: only explicit none can be mapped",))
    tx_check_frame(frame)

    records: list[DailyBar] = []
    seen: set[str] = set()
    for index, row in enumerate(frame.to_dict(orient="records")):
        try:
            trade_date = _market_date(row["date"])
        except (TypeError, ValueError) as exc:
            raise ValidationError((f"records[{index}].trade_date: invalid vendor date",)) from exc
        if not request.start_date <= trade_date <= request.end_date:
            raise ValidationError((f"records[{index}].trade_date: {trade_date} outside requested range",))
        if trade_date in seen:
            raise DuplicateRecordError(f"duplicate Tencent date at records[{index}]: {trade_date}")
        seen.add(trade_date)
        prices = {f: _number(row[c], f) for f, c in (
            ("open", "open"), ("high", "high"), ("low", "low"),
            ("close", "close"), ("amount", "amount"))}
        _number(row["volume"], "volume")
        try:
            shares = Decimal(str(row["volume"]))
            if shares < 0 or shares != shares.to_integral_value() or shares > 2**63 - 1:
                raise ValueError("volume outside integer share range")
            volume = int(shares)
        except (InvalidOperation, ValueError) as exc:
            raise ValidationError((f"records[{index}].volume: nonnegative int64 shares required",)) from exc
        content = dict(symbol=request.symbol, trade_date=trade_date, adjustment_method="none",
                      volume=volume, **{k: v for k, v in prices.items()})
        digest = hashlib.sha256(
            json.dumps(content, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        event = datetime.combine(date.fromisoformat(trade_date), time(15), tz)
        records.append(validate_bar(DailyBar(
            instrument_id=request.instrument_id,
            symbol=request.symbol,
            trade_date=trade_date,
            open=prices["open"], high=prices["high"], low=prices["low"],
            close=prices["close"], volume=volume, amount=prices["amount"],
            source=source, source_version=f"row-sha256:{digest}",
            event_time=event.isoformat(),
            available_at=observed_at, ingested_at=observed_at,
            adjustment_method="none",
        )))
    return tuple(sorted(records, key=lambda r: r.trade_date))

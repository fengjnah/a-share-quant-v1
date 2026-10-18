"""Read-only workbench projections over the existing SQLite daily-bar port."""

from dataclasses import asdict
from datetime import date, datetime, timezone
from pathlib import Path
import tempfile

import pandas as pd

from ai_trade.data_access.models import DailyBar, IntegrityError
from ai_trade.data_access.repository import SQLiteMarketDataRepository
from ai_trade.data_access.validation import timestamp, validate_bar
from ai_trade.market_data.akshare_adapter import (
    ADAPTER_VERSION, REVIEWED_SDK_VERSION, validate_request,
)
from ai_trade.market_data.models import DailyHistoryRequest
from ai_trade.market_data.tx_adapter import ADAPTER_VERSION as TX_VERSION
from ai_trade.storage.db import Database


SOURCES = {
    "东方财富（主源）": f"akshare-eastmoney:stock_zh_a_hist:{ADAPTER_VERSION}+sdk-{REVIEWED_SDK_VERSION}",
    "腾讯（备用候选）": f"akshare-tencent:akshare.stock_zh_a_hist_tx:{TX_VERSION}+sdk-{REVIEWED_SDK_VERSION}",
}
COLUMNS = [
    "symbol", "trade_date", "open", "high", "low", "close", "volume_shares",
    "amount_cny", "source", "event_time", "available_at", "ingested_at",
    "quality_status", "source_version", "run_id", "adjustment_method",
]


def make_request(raw: str, start: date, end: date, *, now: datetime | None = None) -> DailyHistoryRequest:
    """Use the adapter's existing code/date/adjustment validation before any action."""
    symbol = raw.strip().upper()
    if len(symbol) == 6 and symbol.isascii() and symbol.isdigit():
        if symbol.startswith(("600", "601", "603", "605", "688", "689")):
            symbol += ".SH"
        elif symbol.startswith(("000", "001", "002", "003", "300", "301")):
            symbol += ".SZ"
    request = DailyHistoryRequest(
        instrument_id=f"cn-equity:{symbol.replace('.', ':')}", symbol=symbol,
        start_date=start.isoformat(), end_date=end.isoformat(), adjustment_method="none",
    )
    validate_request(request, now=now or datetime.now(timezone.utc))
    return request


def existing_demo_root(value: str) -> Path:
    """Accept only an existing demo.sqlite3 in a resolved OS-temp demo directory.

    This optional process setting reopens saved demo data across browser refreshes.
    It never resolves QUANT_DB_PATH or creates a database at a supplied path.
    """
    root = Path(value).expanduser().resolve(strict=True)
    temp = Path(tempfile.gettempdir()).resolve()
    if (not root.is_relative_to(temp) or not root.name.startswith("a-share-quant-demo-")
            or not root.is_dir()):
        raise ValueError("只能打开系统临时目录下已有的 a-share-quant-demo-* 演示区。")
    db = root / "demo.sqlite3"
    if not db.is_file() or db.resolve().parent != root:
        raise ValueError("指定演示区缺少普通 demo.sqlite3 文件，或数据库链接越出目录。")
    return root


def read_bars(db: Database, request: DailyHistoryRequest, *, source: str, as_of: str) -> pd.DataFrame:
    """Discover exact keys in SQLite, then select/validate through the existing port.

    No source, adjustment, instrument identity or revision is silently combined.
    Quarantine/unavailable versions fail the view instead of appearing as valid bars.
    """
    cutoff = timestamp(as_of, "as_of")
    with db.connection() as conn:
        keys = conn.execute(
            """SELECT DISTINCT b.instrument_id, b.trade_date
               FROM daily_bars b JOIN instruments i ON i.instrument_id=b.instrument_id
               JOIN daily_bar_versions v ON v.bar_id=b.bar_id
               WHERE i.symbol=? AND b.trade_date BETWEEN ? AND ?
                 AND b.adjustment_method=? AND v.source=?
               ORDER BY b.trade_date""",
            (request.symbol, request.start_date, request.end_date, request.adjustment_method, source),
        ).fetchall()
    if len({row["instrument_id"] for row in keys}) > 1:
        raise IntegrityError("该代码对应多个内部证券身份，不能在展示层自动合并。")
    repository = SQLiteMarketDataRepository(db)
    rows = []
    for key in keys:
        result = repository.get_bar(
            instrument_id=key["instrument_id"], trade_date=key["trade_date"], source=source,
            adjustment_method=request.adjustment_method, as_of=cutoff, mode="strict_backtest",
        )
        bar = validate_bar(result.bar)
        row = asdict(bar)
        row["volume_shares"] = row.pop("volume")
        row["amount_cny"] = row.pop("amount")
        row["run_id"] = next(ref.removeprefix("run:") for ref in result.lineage_refs if ref.startswith("run:"))
        rows.append(row)
    return pd.DataFrame(rows, columns=COLUMNS)


def verify_written(repository: SQLiteMarketDataRepository, records: tuple[DailyBar, ...]) -> int:
    """Compare all domain fields; a successful SELECT alone is insufficient."""
    for raw in records:
        bar = validate_bar(raw)
        saved = repository.get_bar(
            instrument_id=bar.instrument_id, trade_date=bar.trade_date, source=bar.source,
            adjustment_method=bar.adjustment_method, as_of=bar.ingested_at, mode="strict_backtest",
        ).bar
        if saved != bar:
            raise IntegrityError("SQLite 读回字段与本次写入记录不一致。")
    return len(records)


def chart_data(bars: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Both chart projections come only from the same validated table dataset."""
    ordered = bars.sort_values("trade_date").set_index("trade_date")
    return ordered[["close"]].copy(), ordered[["volume_shares"]].copy()

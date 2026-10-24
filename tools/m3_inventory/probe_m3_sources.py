"""Bounded read-only probes for TASK-M3-DATA-SOURCE-INVENTORY-001.

No production DB writes, no retries, no proxy/TLS changes, no credentials.
Each probe runs at most one SDK call; failures are recorded and the run
continues. JSON record goes to artifacts/m3-inventory-001/probes.json.
"""
from __future__ import annotations

import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts" / "m3-inventory-001"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jsonable(obj):
    import pandas as pd
    if isinstance(obj, (pd.Timestamp,)):
        return obj.isoformat()
    if isinstance(obj, (datetime,)):
        return obj.isoformat()
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    if isinstance(obj, (list, tuple)):
        return [_jsonable(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return str(obj)


def run_probe(name: str, fn) -> dict:
    started = now_iso()
    record = dict(probe=name, started_at=started, status=None, detail=None,
                   error=None, traceback=None, rows=None, columns=None,
                   sample=None, duration_sec=None, finished_at=None)
    try:
        result = fn()
        if isinstance(result, tuple):
            data, meta = result
        else:
            data, meta = result, {}
        record["status"] = "OK"
        record["detail"] = meta
        if hasattr(data, "to_dict"):
            rows = data.to_dict(orient="records")
            record["columns"] = [str(c) for c in getattr(data, "columns", [])]
            record["rows"] = len(rows)
            record["sample"] = rows[:3]
        else:
            record["detail"] = {"meta": meta, "value": str(data)[:2000]}
        record["finished_at"] = now_iso()
        record["duration_sec"] = round((datetime.fromisoformat(record["finished_at"]) -
                                        datetime.fromisoformat(started)).total_seconds(), 2)
        return record
    except Exception as exc:  # noqa: BLE001 - record and continue
        record["error"] = f"{type(exc).__name__}: {str(exc)[:500]}"
        record["traceback"] = traceback.format_exc(limit=6)
        record["finished_at"] = now_iso()
        record["duration_sec"] = round((datetime.fromisoformat(record["finished_at"]) -
                                        datetime.fromisoformat(started)).total_seconds(), 2)
        return record


def main() -> int:
    import importlib.metadata

    import akshare as ak
    import pandas as pd

    OUT.mkdir(parents=True, exist_ok=True)
    report = dict(task="TASK-M3-DATA-SOURCE-INVENTORY-001",
                  akshare_version=importlib.metadata.version("akshare"),
                  probes=[])

    probes = {}

    def index_zh_a_hist(symbol: str):
        df = ak.index_zh_a_hist(symbol=symbol, period="daily",
                                start_date="20260101", end_date="20261020")
        meta = dict(api="index_zh_a_hist", symbol=symbol,
                    first=str(df.iloc[0]["日期"]) if len(df) else None,
                    last=str(df.iloc[-1]["日期"]) if len(df) else None)
        return df, meta

    def index_zh_index_daily(symbol: str):
        df = ak.stock_zh_index_daily(symbol=symbol)
        meta = dict(api="stock_zh_index_daily", symbol=symbol,
                    first=str(df.iloc[0]["date"]) if len(df) else None,
                    last=str(df.iloc[-1]["date"]) if len(df) else None)
        return df, meta

    def stock_market_activity_legu():
        df = ak.stock_market_activity_legu()
        meta = dict(api="stock_market_activity_legu")
        return df, meta

    def stock_zh_a_spot_em_all():
        df = ak.stock_zh_a_spot_em()
        amt = pd.to_numeric(df.get("成交额"), errors="coerce")
        limit_up = int((pd.to_numeric(df.get("涨跌幅"), errors="coerce") >= 9.8).sum())
        limit_down = int((pd.to_numeric(df.get("涨跌幅"), errors="coerce") <= -9.8).sum())
        meta = dict(api="stock_zh_a_spot_em", total_rows=len(df),
                    total_amount_yuan=float(amt.sum()) if amt.notna().any() else None,
                    estimated_limit_up_by_pct=limit_up,
                    estimated_limit_down_by_pct=limit_down)
        return df, meta

    def cffex_hist_daily():
        df = ak.futures_hist_daily_cffex(date="20261023")
        meta = dict(api="futures_hist_daily_cffex", date="20261023",
                    rows_if_ok=len(df) if hasattr(df, "__len__") else None,
                    columns_if_ok=[str(c) for c in getattr(df, "columns", [])])
        return df, meta

    probes["index_zh_a_hist_sh000300"] = lambda: index_zh_a_hist("000300")
    probes["index_zh_a_hist_sh000001"] = lambda: index_zh_a_hist("000001")
    probes["index_zh_index_daily_sh000300"] = lambda: index_zh_index_daily("sh000300")
    probes["index_zh_index_daily_sz399001"] = lambda: index_zh_index_daily("sz399001")
    probes["market_activity_legu"] = stock_market_activity_legu
    probes["spot_em_market_totals"] = stock_zh_a_spot_em_all
    probes["cffex_futures_hist_daily"] = cffex_hist_daily

    only = sys.argv[1:] if len(sys.argv) > 1 else list(probes)
    for name in only:
        print(f"== {name} ==", flush=True)
        record = run_probe(name, probes[name])
        report["probes"].append(record)
        print(json.dumps({k: _jsonable(v) for k, v in record.items() if k != "traceback"},
                         ensure_ascii=False, default=str)[:800], flush=True)
        if name == "spot_em_market_totals" and record.get("status") == "OK":
            (OUT / "spot_em_sample.json").write_text(
                json.dumps(_jsonable(record.get("sample")), ensure_ascii=False, indent=2, default=str),
                encoding="utf-8")

    report["finished_at"] = now_iso()
    out_path = OUT / "probes.json"
    out_path.write_text(json.dumps(_jsonable(report), ensure_ascii=False, indent=2, default=str),
                        encoding="utf-8")
    print(f"recorded -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

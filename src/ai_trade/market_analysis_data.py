"""Bounded, explicit M3 observations; private demo files, no production ledger."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

import pandas as pd

from ai_trade.market_data.cffex_rankings import CffexRankingsClient, parse
from ai_trade.market_data.cffex_rankings_models import CffexRankingsRequest

INDEX_SYMBOLS = {"沪深300": "sh000300", "上证指数": "sh000001"}
INDEX_SOURCE = "AKShare 1.19.1 / 新浪财经 stock_zh_index_daily"
BREADTH_SOURCE = "AKShare 1.19.1 / 乐咕乐股 stock_market_activity_legu"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_snapshot(root: Path, data: dict) -> Path:
    """Content-addressed observations preserve prior files across app reruns/restarts."""
    directory = root / "m3-observations"
    directory.mkdir(exist_ok=True)
    payload = json.dumps(data, ensure_ascii=False, sort_keys=True, allow_nan=False).encode("utf-8")
    target = directory / (hashlib.sha256(payload).hexdigest()+".json")
    if not target.exists():
        temporary = target.with_suffix(".tmp")
        temporary.write_bytes(payload)
        temporary.replace(target)
    return target


def snapshots(root: Path, *, kind: str, symbol: str, analysis_date: str) -> list[dict]:
    result = []
    # This is a small local demo archive, not a full history repository.
    paths = sorted((root / "m3-observations").glob("*.json"))
    if len(paths) > 1000:
        raise ValueError("本地观察文件超过1000个，请缩小独立演示目录")
    for path in paths:
        payload = path.read_bytes()
        if len(payload) > 2_000_000 or hashlib.sha256(payload).hexdigest() != path.stem:
            raise ValueError("本地观察文件摘要不匹配或超出大小上限")
        item = json.loads(payload)
        if item["kind"] == kind and item["symbol"] == symbol and (kind == "index" or item["trade_date"] <= analysis_date):
            item["observation_file"] = str(path)
            result.append(item)
    return sorted(result, key=lambda x: (x["trade_date"], x["observed_at"]))


def collect_cffex(root: Path, variety: str, trade_date: str) -> dict:
    request = CffexRankingsRequest("CFFEX", variety, trade_date)
    client = CffexRankingsClient(timeout=8)
    payload = client.fetch(request)
    format_name, rows = parse(payload, request)
    data = dict(kind="cffex", symbol=variety, trade_date=trade_date, observed_at=now(),
                source=request.url(), transport="HTTPS", payload_sha256=hashlib.sha256(payload).hexdigest(),
                raw_csv_hex=payload.hex(), format=format_name,
                contracts=sorted({r.contract for r in rows}), rows=len(rows),
                available_at=None, status="原始榜单观察；权威CFFEX日历未接入", authorization="对外展示/再分发授权待确认")
    save_snapshot(root, data)
    return data


def ranking_rows(item: dict):
    payload = bytes.fromhex(item["raw_csv_hex"])
    if hashlib.sha256(payload).hexdigest() != item["payload_sha256"]:
        raise ValueError("CFFEX原始载荷摘要不一致")
    return parse(payload, CffexRankingsRequest("CFFEX", item["symbol"], item["trade_date"]))[1]


def collect_public(root: Path, kind: str, symbol: str) -> dict:
    if kind not in ("index", "breadth") or (kind == "index" and symbol not in INDEX_SYMBOLS.values()):
        raise ValueError("仅允许已列出的指数/市场宽度请求")
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    # SDK methods have no timeout parameter. Bound the entire private worker as well as HTTP calls.
    proc = subprocess.run([sys.executable, "-m", "ai_trade.market_analysis_data", kind, symbol],
                          capture_output=True, text=True, encoding="utf-8", timeout=30, env=env, check=False)
    if proc.returncode:
        raise RuntimeError("公共数据采集失败："+proc.stdout.strip()[-250:])
    item = json.loads(proc.stdout)
    save_snapshot(root, item)
    return item


def price_frame(item: dict) -> pd.DataFrame:
    frame = pd.DataFrame(item["prices"])
    for name in ("symbol", "source", "observed_at"):
        frame[name] = item[name]
    return frame


def breadth_frame(items: list[dict]) -> pd.DataFrame:
    # Re-observations do not create extra days; never backfill dates from a latest snapshot.
    by_date = {}
    for item in items:
        by_date[item["trade_date"]] = dict(item["breadth"], trade_date=item["trade_date"],
                                         observed_at=item["observed_at"], source=item["source"])
    return pd.DataFrame(by_date.values())


def _worker(kind: str, symbol: str) -> dict:
    import importlib.metadata
    from unittest.mock import patch
    import requests

    if importlib.metadata.version("akshare") != "1.19.1":
        raise ValueError("需要项目固定AKShare 1.19.1")
    import akshare as ak
    original = requests.get

    def bounded_get(url, **kwargs):
        if not url.startswith("https://"):
            raise ValueError("仅允许HTTPS")
        kwargs.update(timeout=(5, 8), allow_redirects=False, verify=True)
        response = original(url, **kwargs)
        response.raise_for_status()
        if response.is_redirect or len(response.content) > 8_000_000:
            raise ValueError("重定向或响应过大")
        response.encoding = response.apparent_encoding
        return response

    with patch.object(requests, "get", bounded_get):
        if kind == "index" and symbol in INDEX_SYMBOLS.values():
            frame = ak.stock_zh_index_daily(symbol=symbol)
            frame = frame.rename(columns={"date": "trade_date"})
            frame["trade_date"] = frame.trade_date.astype(str)
            today = datetime.now().astimezone(__import__('zoneinfo').ZoneInfo("Asia/Shanghai")).date().isoformat()
            frame = frame.loc[frame.trade_date < today].sort_values("trade_date").tail(550)
            if frame.empty:
                raise ValueError("没有已结束日期的指数行情")
            prices = frame[["trade_date", "open", "high", "low", "close"]].to_dict("records")
            return dict(kind="index", symbol=symbol, source=INDEX_SOURCE, observed_at=now(),
                        trade_date=frame.trade_date.iloc[-1], prices=prices, status="真实观察",
                        available_at=None, authorization="对外展示/再分发授权待确认")
        if kind == "breadth":
            frame = ak.stock_market_activity_legu()
            if frame.item.duplicated().any():
                raise ValueError("宽度来源标签重复")
            mapping = dict(zip(frame.item.str.strip(), frame.value))
            fields = {"advances": "上涨", "declines": "下跌", "flat": "平盘", "limit_up": "涨停", "limit_down": "跌停"}
            values = {k: float(mapping[v]) for k, v in fields.items()}
            if any(v < 0 or not v.is_integer() for v in values.values()):
                raise ValueError("家数无效")
            day = str(mapping["统计日期"])[:10]
            from datetime import date
            date.fromisoformat(day)
            return dict(kind="breadth", symbol="market", source=BREADTH_SOURCE, observed_at=now(),
                        trade_date=day, breadth=values, status="真实观察", available_at=None,
                        authorization="对外展示/再分发授权待确认")
    raise ValueError("不支持的采集")


if __name__ == "__main__":
    try:
        print(json.dumps(_worker(sys.argv[1], sys.argv[2]), ensure_ascii=False, allow_nan=False))
    except Exception as exc:
        # Do not expose response bodies, proxies, credentials or exception URLs.
        print(json.dumps({"error": type(exc).__name__}, ensure_ascii=False))
        sys.exit(1)

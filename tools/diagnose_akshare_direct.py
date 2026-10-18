"""One bounded, instrumented call through the project's AKShare ingestion entry.

Run as a separate process. Never log raw URLs, request/response buffers or secrets.
"""

from __future__ import annotations

import argparse
import hashlib
import http.client
import importlib.metadata
import json
import os
import socket
import ssl
import tempfile
import time
import uuid
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import requests
from urllib3.util.retry import Retry

from ai_trade.data_access.models import DataUnavailableError
from ai_trade.data_access.repository import SQLiteMarketDataRepository
from ai_trade.market_data.akshare_adapter import AkshareDailyClient, REQUIRED_COLUMNS
from ai_trade.market_data.evidence import EvidenceStore
from ai_trade.market_data.ingestor import DailyHistoryIngestor
from ai_trade.market_data.models import DailyHistoryRequest
from ai_trade.storage.db import Database, DatabaseConfig

HOST = "push2his.eastmoney.com"
PATH = "/api/qt/stock/kline/get"
URL = f"https://{HOST}{PATH}"
ZERO_RETRY = Retry(total=0, connect=0, read=0, redirect=0, status=0)


def error_types(exc: BaseException) -> list[str]:
    """Bounded type-only chain: exception messages can contain proxy credentials."""
    names: list[str] = []
    seen: set[int] = set()
    while exc is not None and id(exc) not in seen and len(names) < 8:
        seen.add(id(exc))
        names.append(type(exc).__name__)
        exc = exc.__cause__ or exc.__context__
    return names


def proxy_shape(value: str | None) -> dict | None:
    if not value:
        return None
    parsed = urlsplit(value)
    # A proxy hostname or URL might be sensitive. Keep only type, never authority.
    return {"scheme": parsed.scheme, "configured": True}


class RequestBudgetExceeded(RuntimeError):
    """The next send would exceed the single market GET budget."""


class TransportTrace:
    """Observe the real Requests call without altering the prepared request."""

    def __init__(self, audit: dict):
        self.audit = audit
        self.adapter_attempts = 0
        self.session_attempts = 0
        self.originals: dict[str, object] = {}

    def check_send(self, method: str, url: str) -> None:
        parsed = urlsplit(url)
        params = parse_qs(parsed.query)
        if (method, parsed.scheme, parsed.hostname, parsed.path) != (
            "GET", "https", HOST, PATH
        ) or any(params.get(key) != [value] for key, value in {
            "secid": "1.600000", "beg": "20261014", "end": "20261015",
            "klt": "101", "fqt": "0",
        }.items()):
            self.audit["blocked_requests"].append("unexpected_method_or_target")
            raise RequestBudgetExceeded("unexpected request blocked before network send")
        if self.adapter_attempts >= 1:
            self.audit["blocked_requests"].append("second_adapter_send")
            raise RequestBudgetExceeded("second market GET blocked before network send")
        self.adapter_attempts += 1

    @contextmanager
    def installed(self):
        """Install process-local hooks and restore every one on all exits."""
        self.originals = {
            "getaddrinfo": socket.getaddrinfo,
            "connect": socket.socket.connect,
            "wrap_socket": ssl.SSLContext.wrap_socket,
            "session_send": requests.Session.send,
            "adapter_send": requests.adapters.HTTPAdapter.send,
            "http_send": http.client.HTTPConnection.send,
            "read_status": http.client.HTTPResponse._read_status,
        }
        original = self.originals
        audit = self.audit

        def getaddrinfo(host, port, *args, **kwargs):
            event = {"host": str(host), "port": port, "status": "started"}
            audit["dns"].append(event)
            try:
                result = original["getaddrinfo"](host, port, *args, **kwargs)
                event.update(status="resolved", addresses=sorted({item[4][0] for item in result}))
                return result
            except Exception as exc:
                event.update(status="failed", error_types=error_types(exc))
                raise

        def connect(sock, address):
            event = {"peer_ip": str(address[0]), "peer_port": address[1], "status": "started"}
            audit["tcp"].append(event)
            try:
                result = original["connect"](sock, address)
                event["status"] = "connected"
                return result
            except Exception as exc:
                event.update(status="failed", error_types=error_types(exc))
                raise

        def wrap_socket(context, sock, *args, **kwargs):
            event = {
                "server_hostname": kwargs.get("server_hostname"),
                "verify_mode": context.verify_mode.name,
                "check_hostname": context.check_hostname,
                "status": "started",
            }
            audit["tls"].append(event)
            try:
                wrapped = original["wrap_socket"](context, sock, *args, **kwargs)
                event.update(status="handshake_complete", protocol=wrapped.version())
                return wrapped
            except Exception as exc:
                event.update(status="failed", error_types=error_types(exc))
                raise

        def session_send(session, prepared, **kwargs):
            self.session_attempts += 1
            if self.session_attempts > 1:
                audit["blocked_requests"].append("redirect_or_second_session_send")
                raise RequestBudgetExceeded("redirect/second Session.send blocked")
            parsed = urlsplit(prepared.url)
            selected = requests.utils.select_proxy(prepared.url, kwargs.get("proxies") or {})
            audit["requests"] = {
                "method": prepared.method, "host": parsed.hostname, "path": parsed.path,
                "selected_proxy": proxy_shape(selected),
                "verify_enabled": kwargs.get("verify", True) is not False,
                "redirects_disabled": True,
                "timeout_seconds": kwargs.get("timeout"),
            }
            if selected or kwargs.get("verify", True) is False:
                audit["blocked_requests"].append("proxy_or_disabled_tls_verification")
                raise RequestBudgetExceeded("direct verified TLS precondition failed")
            # Requests' public get() does not expose redirect control in the SDK.
            # This diagnostic-only change prevents resolve_redirects from sending a second GET.
            kwargs["allow_redirects"] = False
            return original["session_send"](session, prepared, **kwargs)

        def adapter_send(adapter, request, *args, **kwargs):
            self.check_send(request.method, request.url)
            previous_retry = adapter.max_retries
            adapter.max_retries = ZERO_RETRY
            audit["requests"]["urllib3_retries_disabled"] = True
            try:
                response = original["adapter_send"](adapter, request, *args, **kwargs)
                audit["http"].update(status="response_received", status_code=response.status_code,
                                     content_type=response.headers.get("Content-Type"))
                return response
            finally:
                adapter.max_retries = previous_retry

        def http_send(conn, data):
            event = {"status": "started"}
            audit["http_send_calls"].append(event)
            try:
                result = original["http_send"](conn, data)
                event["status"] = "local_send_completed"
                return result
            except Exception as exc:
                event.update(status="failed", error_types=error_types(exc))
                raise

        def read_status(response):
            event = {"status": "started"}
            audit["http_status_lines"].append(event)
            try:
                result = original["read_status"](response)
                event.update(status="received", status_code=result[1])
                return result
            except Exception as exc:
                event.update(status="failed", error_types=error_types(exc))
                raise

        socket.getaddrinfo = getaddrinfo
        socket.socket.connect = connect
        ssl.SSLContext.wrap_socket = wrap_socket
        requests.Session.send = session_send
        requests.adapters.HTTPAdapter.send = adapter_send
        http.client.HTTPConnection.send = http_send
        http.client.HTTPResponse._read_status = read_status
        try:
            yield self
        finally:
            socket.getaddrinfo = original["getaddrinfo"]
            socket.socket.connect = original["connect"]
            ssl.SSLContext.wrap_socket = original["wrap_socket"]
            requests.Session.send = original["session_send"]
            requests.adapters.HTTPAdapter.send = original["adapter_send"]
            http.client.HTTPConnection.send = original["http_send"]
            http.client.HTTPResponse._read_status = original["read_status"]


def audit_template() -> dict:
    return {
        "started_at": datetime.now(timezone.utc).isoformat(),
        "target": {"host": HOST, "path": PATH, "symbol": "600000.SH",
                   "start_date": "2026-10-14", "end_date": "2026-10-15",
                   "period": "daily", "adjustment_method": "none"},
        "request_budget": {"max_target_get": 1},
        "dns": [], "tcp": [], "tls": [], "http_send_calls": [],
        "http_status_lines": [], "http": {"status": "not_observed"},
        "requests": {"status": "not_executed"}, "blocked_requests": [],
        "akshare": {"status": "not_executed", "returned_rows": None},
        "sqlite_write": {"status": "not_executed"},
        "sqlite_readback": {"status": "not_executed"},
    }


def run(audit: dict) -> int:
    if importlib.metadata.version("akshare") != "1.19.1":
        audit["stop_reason"] = "unreviewed_akshare_version"
        return 2
    old_no_proxy = os.environ.get("NO_PROXY")
    os.environ["NO_PROXY"] = HOST
    try:
        audit["configuration"] = {
            "no_proxy": HOST,
            "no_proxy_match": requests.utils.should_bypass_proxies(URL, HOST),
            "selected_environment_proxy": proxy_shape(
                requests.utils.select_proxy(URL, requests.utils.get_environ_proxies(URL))
            ),
            "tls_verification": "enabled",
            "retry_policy": "urllib3 total/connect/read/redirect/status=0 for this call",
            "redirect_policy": "allow_redirects=False for this call",
        }
        if audit["configuration"]["selected_environment_proxy"]:
            audit["stop_reason"] = "proxy_still_selected"
            return 2

        temp_root = Path(tempfile.mkdtemp(prefix="a-share-quant-demo-004-"))
        audit["temporary_root"] = str(temp_root)
        db = Database(DatabaseConfig(temp_root / "acceptance.sqlite3", environment="test", journal_mode="DELETE"))
        db.initialize()
        repository = SQLiteMarketDataRepository(db)
        evidence = EvidenceStore(temp_root / "evidence")
        request = DailyHistoryRequest("cn-equity:600000:SH", "600000.SH",
                                      "2026-10-14", "2026-10-15", "none")

        class RecordingClient:
            def __init__(self):
                self.client = AkshareDailyClient()
                self.sdk_version = self.client.sdk_version
                self.frame = None

            def fetch(self, request, *, timeout):
                self.frame = self.client.fetch(request, timeout=timeout)
                return self.frame

        client = RecordingClient()
        trace = TransportTrace(audit)
        started = time.monotonic()
        try:
            with trace.installed():
                result = DailyHistoryIngestor(client, repository, evidence, timeout=10.0).collect(
                    request, run_id="demo-004-" + uuid.uuid4().hex
                )
        except Exception as exc:
            audit["akshare"].update(status="exception", error_types=error_types(exc))
            audit["stop_reason"] = "formal_ingestion_exception"
            return 2
        finally:
            audit["elapsed_seconds"] = round(time.monotonic() - started, 3)
            audit["request_budget"]["adapter_get_count"] = trace.adapter_attempts
            audit["request_budget"]["session_send_count"] = trace.session_attempts

        audit["akshare"].update(
            status=result.status.value, source=result.source, run_id=result.run_id,
            returned_rows=result.returned_rows if result.observed_at else None,
            inserted_rows=result.inserted_rows, observed_at=result.observed_at,
            issues=list(result.issues), response_sha256=result.response_sha256,
            fields=list(client.frame.columns) if client.frame is not None else None,
        )
        if result.status.value != "success":
            audit["stop_reason"] = "ingestion_not_success"
            return 2

        frame = client.frame
        assert frame is not None and REQUIRED_COLUMNS <= set(frame.columns)
        audit["sqlite_write"] = {"status": "committed", "inserted_rows": result.inserted_rows}
        with db.connection() as conn:
            rows = conn.execute("""SELECT b.trade_date, v.source, v.run_id, v.open, v.high,
                v.low, v.close, v.volume, v.amount FROM daily_bars b
                JOIN daily_bar_versions v ON v.bar_id=b.bar_id ORDER BY b.trade_date""").fetchall()
            integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_keys = len(conn.execute("PRAGMA foreign_key_check").fetchall())
        vendor = {str(row["日期"]): row for row in frame.to_dict(orient="records")}
        checks = []
        for bar, row in zip(result.records, rows, strict=True):
            raw = vendor[bar.trade_date]
            values_match = all(getattr(bar, field) == float(raw[column]) for field, column in (
                ("open", "开盘"), ("high", "最高"), ("low", "最低"),
                ("close", "收盘"), ("amount", "成交额")))
            volume_match = Decimal(bar.volume) == Decimal(str(raw["成交量"])) * 100
            storage_match = all(row[field] == getattr(bar, field) for field in (
                "trade_date", "source", "open", "high", "low", "close", "volume", "amount"))
            quality = 0 < bar.low <= min(bar.open, bar.close) <= max(bar.open, bar.close) <= bar.high
            query = dict(instrument_id=bar.instrument_id, trade_date=bar.trade_date,
                         source=bar.source, adjustment_method="none", mode="strict_backtest")
            hidden_before = False
            try:
                repository.get_bar(**query, as_of=(datetime.fromisoformat(bar.available_at)
                                                  - timedelta(microseconds=1)).isoformat())
            except DataUnavailableError:
                hidden_before = True
            visible = repository.get_bar(**query, as_of=bar.ingested_at).bar == bar
            checks.append({"trade_date": bar.trade_date, "vendor_values_match": values_match,
                           "lots_to_shares_match": volume_match, "sqlite_values_match": storage_match,
                           "run_id_match": row["run_id"] == result.run_id,
                           "ohlc_valid": quality, "hidden_before_available_at": hidden_before,
                           "visible_at_ingested_at": visible})
        response_file = Path(result.evidence_directory) / "response.json"
        digest_matches = hashlib.sha256(response_file.read_bytes()).hexdigest() == result.response_sha256
        audit["sqlite_readback"] = {
            "status": "checked", "readback_rows": len(rows),
            "trade_dates": [row["trade_date"] for row in rows],
            "integrity_check": integrity, "foreign_key_violations": foreign_keys,
            "row_checks": checks, "evidence_sha256_matches": digest_matches,
        }
        assert len(rows) == result.returned_rows == result.inserted_rows == len(frame)
        assert integrity == "ok" and foreign_keys == 0 and digest_matches
        assert all(all(value for key, value in row.items() if key != "trade_date") for row in checks)
        audit["acceptance"] = "passed_for_this_request_only"
        return 0
    finally:
        if old_no_proxy is None:
            os.environ.pop("NO_PROXY", None)
        else:
            os.environ["NO_PROXY"] = old_no_proxy


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    audit = audit_template()
    try:
        code = run(audit)
    except Exception as exc:
        audit["stop_reason"] = "unexpected_local_exception"
        audit["local_error_types"] = error_types(exc)
        code = 2
    audit["completed_at"] = datetime.now(timezone.utc).isoformat()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"audit_path": str(args.output), "request_budget": audit["request_budget"],
                      "stop_reason": audit.get("stop_reason"), "acceptance": audit.get("acceptance")},
                     ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())

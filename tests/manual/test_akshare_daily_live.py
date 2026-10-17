"""Manual integration only; configure all inputs and pass the explicit pytest flag."""

import hashlib
import json
import math
import os
import re
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

from ai_trade.data_access.models import DataUnavailableError
from ai_trade.data_access.repository import SQLiteMarketDataRepository
from ai_trade.market_data.akshare_adapter import AkshareDailyClient
from ai_trade.market_data.evidence import EvidenceStore
from ai_trade.market_data.ingestor import DailyHistoryIngestor
from ai_trade.market_data.models import DailyHistoryRequest, EvidenceWriteError, IngestionStatus
from ai_trade.storage.db import Database, DatabaseConfig


def _error_chain(error):
    """Keep bounded diagnostic causes without URL credentials or query strings."""
    result, seen = [], set()
    while error is not None and id(error) not in seen and len(result) < 8:
        seen.add(id(error))
        message = re.sub(r"https?://[^\s'\"\)]+", "[URL redacted]", str(error))
        message = re.sub(r"(/[^\s?'\"\)]*)\?[^\s'\"\)]+", r"\1?[query redacted]", message)
        message = re.sub(r"(?i)\b(ut|token|access_token|password|authorization|api[_-]?key)\s*[:=]\s*[^&\s,'\"\)]+",
                         r"\1=[redacted]", message)
        result.append({"type": type(error).__name__, "message": message[:1000]})
        error = error.__cause__ or error.__context__
    return result


def _verify_saved_batch(db, repository, result, frame):
    """Verify actual SQLite reads, conservative visibility and saved SDK evidence."""
    with db.connection() as conn:
        assert conn.execute("SELECT count(*) FROM daily_bar_versions").fetchone()[0] == result.inserted_rows
        dates = [row[0] for row in conn.execute("SELECT trade_date FROM daily_bars ORDER BY trade_date")]
    assert dates == [bar.trade_date for bar in result.records]
    assert len(dates) == len(set(dates)) == len(frame.index) == result.returned_rows == result.inserted_rows
    vendor = {str(row["日期"]): row for row in frame.to_dict(orient="records")}
    for bar in result.records:
        row = vendor[bar.trade_date]
        for field, column in (("open", "开盘"), ("high", "最高"), ("low", "最低"),
                              ("close", "收盘"), ("amount", "成交额")):
            assert math.isfinite(getattr(bar, field))
            assert getattr(bar, field) == float(row[column])
        assert 0 < bar.low <= min(bar.open, bar.close) <= max(bar.open, bar.close) <= bar.high
        assert type(bar.volume) is int and bar.volume >= 0 and bar.amount >= 0
        assert Decimal(bar.volume) == Decimal(str(row["成交量"])) * 100
        assert bar.adjustment_method == "none" and bar.factor_version is None
        assert bar.available_at == result.observed_at and bar.ingested_at == result.validated_at
        query = dict(instrument_id=bar.instrument_id, trade_date=bar.trade_date,
                     source=bar.source, adjustment_method="none", mode="strict_backtest")
        for cutoff in (bar.event_time, *(
                (datetime.fromisoformat(t) - timedelta(microseconds=1)).isoformat()
                for t in (bar.available_at, bar.ingested_at))):
            with pytest.raises(DataUnavailableError):
                repository.get_bar(**query, as_of=cutoff)
        assert repository.get_bar(**query, as_of=bar.ingested_at).bar == bar
    folder = Path(result.evidence_directory)
    request = json.loads((folder / "request.json").read_text(encoding="utf-8"))
    assert request["run_id"] == result.run_id and request["source"] == result.source
    assert request["parameters"]["adjust"] == "" and request["request"]["adjustment_method"] == "none"
    payload = (folder / "response.json").read_bytes()
    assert hashlib.sha256(payload).hexdigest() == result.response_sha256
    saved = json.loads(payload)
    assert saved["not_raw_http"] is True
    assert saved["frame"] == json.loads(frame.to_json(orient="split", date_format="iso", double_precision=15))
    assert json.loads((folder / "result.json").read_text(encoding="utf-8")) == json.loads(json.dumps(asdict(result)))
    return dates


@pytest.mark.manual_integration
def test_akshare_daily_live(tmp_path, monkeypatch):
    names = ("AKSHARE_TEST_INSTRUMENT_ID", "AKSHARE_TEST_SYMBOL", "AKSHARE_TEST_START", "AKSHARE_TEST_END")
    missing = [name for name in names if not os.environ.get(name)]
    if missing:
        pytest.fail("explicit manual configuration required: " + ", ".join(missing))
    request = DailyHistoryRequest(*(os.environ[name] for name in names), adjustment_method="none")
    db = Database(DatabaseConfig(tmp_path / "manual.sqlite3", "test"))
    db.initialize()
    repository = SQLiteMarketDataRepository(db)
    audit = {"request": asdict(request), "http": [], "acceptance": "not_completed",
             "returned_rows": None, "inserted_rows": 0, "fault_injection": "not_executed"}
    original_send = requests.Session.send

    def traced_send(session, prepared, **kwargs):
        url = urlsplit(prepared.url)
        assert url.hostname == "push2his.eastmoney.com" and url.path == "/api/qt/stock/kline/get", "unexpected SDK HTTP target"
        assert not audit["http"], "manual acceptance permits one HTTP attempt; no retries or redirects"
        params = parse_qs(url.query)
        event = {"host": url.hostname, "path": url.path, "method": prepared.method,
                 "parameters": {key: params.get(key) for key in ("secid", "beg", "end", "klt", "fqt")},
                 "proxy_configured": bool(kwargs.get("proxies")),
                 "certificate_verification": kwargs.get("verify", True) is True
                     or isinstance(kwargs.get("verify"), str) and bool(kwargs["verify"])}
        assert event["certificate_verification"], "manual acceptance must retain TLS verification"
        audit["http"].append(event)
        try:
            response = original_send(session, prepared, **kwargs)
            event.update(status=response.status_code, content_type=response.headers.get("Content-Type"))
            event["classification"] = ("rate_limited" if response.status_code == 429
                                       else "http_error" if response.status_code >= 400 else "response_received")
            return response
        except Exception as exc:
            event["classification"] = (
                "proxy_connection_failure" if isinstance(exc, requests.exceptions.ProxyError)
                else "tls_failure" if isinstance(exc, requests.exceptions.SSLError)
                else "network_timeout" if isinstance(exc, requests.exceptions.Timeout)
                else "network_connection_failure" if isinstance(exc, requests.exceptions.ConnectionError)
                else "unexpected_transport_error")
            event["error_chain"] = _error_chain(exc)
            raise

    class RecordingClient:
        def __init__(self):
            self.client = AkshareDailyClient()
            self.sdk_version = self.client.sdk_version
            self.frame = None

        def fetch(self, request, *, timeout):
            try:
                self.frame = self.client.fetch(request, timeout=timeout)
                return self.frame
            except Exception as exc:
                audit["sdk_error_chain"] = _error_chain(exc)
                raise

    monkeypatch.setattr(requests.Session, "send", traced_send)
    try:
        client = RecordingClient()
        service = DailyHistoryIngestor(client, repository, EvidenceStore(tmp_path / "evidence"))
        result = service.collect(request, run_id="manual-" + uuid.uuid4().hex)
        audit.update(status=result.status.value,
                     returned_rows=result.returned_rows if result.observed_at is not None else None,
                     sdk_row_counter=result.returned_rows,
                     inserted_rows=result.inserted_rows, issues=result.issues,
                     evidence_directory=result.evidence_directory, response_sha256=result.response_sha256,
                     source=result.source, observed_at=result.observed_at, validated_at=result.validated_at)
        if result.status == IngestionStatus.EMPTY_RESPONSE:
            audit["empty_cause"] = "undetermined; no evidence distinguishes no sessions, source limits or source failure"
        assert len(audit["http"]) == 1 and audit["http"][0].get("status") == 200, audit
        assert audit["http"][0]["parameters"] == {
            "secid": ["1." + request.symbol[:6]] if request.symbol.endswith(".SH") else ["0." + request.symbol[:6]],
            "beg": [request.start_date.replace("-", "")], "end": [request.end_date.replace("-", "")],
            "klt": ["101"], "fqt": ["0"],
        }
        # Empty SDK data is inconclusive: no calendar or source diagnostic proves why.
        assert result.status == IngestionStatus.SUCCESS and result.inserted_rows > 0, audit
        assert all(request.start_date <= bar.trade_date <= request.end_date
                   and bar.symbol == request.symbol for bar in result.records)
        audit["trade_dates"] = _verify_saved_batch(db, repository, result, client.frame)
        audit["live_checks"] = "passed: mapping, SQLite readback, visibility and evidence"

        # Replay the captured live SDK frame in another temporary DB; no second HTTP call.
        fault_db = Database(DatabaseConfig(tmp_path / "fault.sqlite3", "test"))
        fault_db.initialize()
        fault_repository = SQLiteMarketDataRepository(fault_db)
        evidence = EvidenceStore(tmp_path / "fault-evidence")
        write = evidence._write

        def fail_result(path, payload):
            if path.name == "result.json":
                raise OSError("controlled post-commit evidence failure")
            write(path, payload)

        monkeypatch.setattr(evidence, "_write", fail_result)

        class ReplayClient:
            sdk_version = client.sdk_version

            def fetch(self, request, *, timeout):
                return client.frame.copy(deep=True)

        replay = DailyHistoryIngestor(ReplayClient(), fault_repository, evidence)
        with pytest.raises(EvidenceWriteError) as error:
            replay.collect(request, run_id="fault-" + uuid.uuid4().hex)
        assert error.value.database_committed is True
        with fault_db.connection() as conn:
            assert conn.execute("SELECT count(*) FROM daily_bar_versions").fetchone()[0] == result.inserted_rows
        assert len(audit["http"]) == 1
        audit.update(fault_injection="passed: replay only; database_committed=True; SQLite rows retained",
                     acceptance="passed")
    except Exception as exc:
        audit["acceptance"] = "failed"
        audit["error_chain"] = _error_chain(exc)
        raise
    finally:
        with db.connection() as conn:
            audit["sqlite_rows_after_test"] = conn.execute("SELECT count(*) FROM daily_bar_versions").fetchone()[0]
        path = tmp_path / "integration-audit.json"
        path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print("INTEGRATION_AUDIT=" + str(path))

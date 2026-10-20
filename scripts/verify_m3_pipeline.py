"""Explicit bounded M3 source acceptance; default is offline, no production DB.

Reuse adapters, ingestion batches, evidence store and scratch SQLite. Raw payloads
and bundles remain under ignored artifacts; only a reviewed summary is publishable.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from urllib.parse import urlsplit
import uuid

import requests
from urllib3.util.retry import Retry

from ai_trade.m3_data_pipeline import build_bundle, inventory, public_summary
from ai_trade.market_analysis_data import _worker as public_worker, collect_cffex, save_snapshot
from ai_trade.market_data.evidence import EvidenceStore
from ai_trade.market_data.health_service import SOURCES, _ObservedClient, _ScratchWriter
from ai_trade.market_data.health_transport import BudgetBlocked, HealthTransport
from ai_trade.market_data.ingestor import DailyHistoryIngestor, _transport_type_chain
from ai_trade.market_data.models import DailyHistoryRequest, IngestionStatus

REPO = Path(__file__).resolve().parents[1]
LIVE = ("sina_index", "eastmoney_stock", "tencent_stock", "legu_breadth", "cffex_rankings")
REQUESTS = {
    "sina_index": {"symbol": "sh000300", "d": "2020_2_4", "retained_rows_max": 550},
    "eastmoney_stock": {"symbol": "600000.SH", "start_date": "2026-10-14", "end_date": "2026-10-15", "adjust": "none"},
    "tencent_stock": {"symbol": "600000.SH", "start_date": "2026-10-14", "end_date": "2026-10-15", "adjust": "none"},
    "legu_breadth": {"scope": "current published snapshot"},
    "cffex_rankings": {"exchange": "CFFEX", "variety": "IF", "trade_date": "2026-10-16"},
}


def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    # Each run has an exclusive directory; never overwrite a prior observation.
    with Path(path).open("x", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, allow_nan=False, indent=2)
        stream.write("\n")


def checked_root(path):
    resolved = Path(path).resolve()
    if not resolved.is_relative_to((REPO / "artifacts").resolve()):
        raise ValueError("Evidence and scratch DB must stay inside this checkout's ignored artifacts")
    return resolved


def targets(source_id):
    if source_id in ("eastmoney_stock", "tencent_stock"):
        return SOURCES[source_id.split("_")[0]].targets
    parsed = urlsplit(inventory()[source_id]["endpoint"])
    return frozenset({(parsed.hostname, parsed.path)})


@contextmanager
def capture_http(source_id, root):
    """Add bounded body/hash evidence to existing transport, in one private worker.

    The existing HealthTransport remains the source/HTTPS/retry policy. This
    layer additionally limits EACH target to one send and records observed HTTP
    status even when the SDK/CSV parser subsequently fails. No URLs with queries,
    headers, credentials, or response bodies enter the public trace.
    """
    approved = targets(source_id)
    rows, seen = [], set()
    original = requests.adapters.HTTPAdapter.send

    def save_event(row):
        with (root / "http-events.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, sort_keys=True) + "\n")

    def send(adapter, request, **kwargs):
        parsed = urlsplit(request.url)
        key = (parsed.hostname, parsed.path)
        verify = kwargs.get("verify", True)
        if (request.method != "GET" or parsed.scheme != "https" or parsed.port not in (None, 443)
                or parsed.username or parsed.password or key not in approved or key in seen
                or not (verify is True or isinstance(verify, str) and bool(verify.strip()))):
            raise BudgetBlocked("unapproved/repeated endpoint or TLS policy")
        seen.add(key)
        row = dict(endpoint=parsed.scheme + "://" + parsed.netloc + parsed.path, started_at=now(),
                   http_status=None, response_bytes=None, payload_sha256=None, error_type=None)
        rows.append(row)
        save_event(row)
        prior = adapter.max_retries
        adapter.max_retries = Retry(total=0, connect=0, read=0, redirect=0, status=0)
        kwargs.update(timeout=(5, 5), stream=True)
        try:
            response = original(adapter, request, **kwargs)
            row["http_status"] = response.status_code
            save_event(row)
            try:
                body = bytearray()
                limit = 2_000_000 if source_id == "cffex_rankings" else 8_000_000
                for chunk in response.iter_content(65536):
                    body.extend(chunk)
                    if len(body) > limit:
                        raise BudgetBlocked("bounded response size exceeded")
                response._content = bytes(body)
                response._content_consumed = True
                row.update(response_bytes=len(body), payload_sha256=hashlib.sha256(body).hexdigest())
            finally:
                response.close()
            return response
        except Exception as exc:
            row["error_type"] = type(exc).__name__
            raise
        finally:
            row["finished_at"] = now()
            save_event(row)
            adapter.max_retries = prior

    requests.adapters.HTTPAdapter.send = send
    try:
        yield rows
    finally:
        requests.adapters.HTTPAdapter.send = original


def stock_observation(source_id, root, run_id):
    provider = source_id.split("_")[0]
    observed = _ObservedClient(SOURCES[provider].client_factory())
    writer = _ScratchWriter(root)
    request = DailyHistoryRequest("observation-sample:600000:SH", "600000.SH", "2026-10-14", "2026-10-15", "none")
    budget = 2 if provider == "tencent" else 1
    with HealthTransport(SOURCES[provider].targets, budget, 5).installed():
        result = DailyHistoryIngestor(observed, writer, EvidenceStore(root / "ingestion-evidence"), timeout=5).collect(request, run_id=run_id)
    read_back = 0
    for record in result.records:
        selected = writer.repository.get_bar(instrument_id=record.instrument_id, trade_date=record.trade_date,
            source=record.source, adjustment_method=record.adjustment_method, as_of=record.ingested_at, mode="strict_backtest")
        if selected.bar != record:
            raise ValueError("Scratch SQLite readback mismatch")
        read_back += 1
    summary = dict(ingestion_status=result.status.value, batch_id=result.run_id,
        parse_status="PASS" if observed.frame is not None else "NOT RUN",
        validation_status="PASS" if result.status is IngestionStatus.SUCCESS else "NOT RUN" if observed.frame is None else "FAIL",
        actual_fields=list(map(str, observed.frame.columns)) if observed.frame is not None else None,
        returned_rows=result.returned_rows if observed.frame is not None else None,
        inserted_rows=result.inserted_rows, read_back_rows=read_back,
        sdk_frame_sha256=result.response_sha256, observed_at=result.observed_at, ingested_at=result.validated_at,
        error_type_chain=_transport_type_chain(observed.error) if observed.error is not None else None)
    if result.status is not IngestionStatus.SUCCESS:
        return None, summary
    records = [asdict(record) for record in result.records]
    return dict(source=result.source, trade_date=max(r["trade_date"] for r in records), records=records,
                observed_at=result.observed_at, ingested_at=result.validated_at, batch_id=result.run_id), summary


def worker(source_id, root, run_id, *, enable_live=False):
    if enable_live is not True:
        raise ValueError("Explicit --enable-live required before any client construction/request")
    root = checked_root(root)
    root.mkdir(parents=True, exist_ok=False)
    result = dict(source_id=source_id, started_at=now(), request=REQUESTS[source_id],
                  status="FAIL", parse_status="NOT RUN", returned_rows=None, data_date_min=None,
                  data_date_max=None, missing_dates=None, expected_samples=None, authorization="UNKNOWN")
    trace, observation = [], None
    try:
        with capture_http(source_id, root) as trace:
            if source_id in ("eastmoney_stock", "tencent_stock"):
                observation, details = stock_observation(source_id, root, run_id)
                result.update(details)
            else:
                # CFFEX client already enforces HTTPS, no redirects/retries and 2MB.
                if source_id == "cffex_rankings":
                    observation = collect_cffex(root, "IF", "2026-10-16")
                else:
                    kind, symbol = ("index", "sh000300") if source_id == "sina_index" else ("breadth", "market")
                    with HealthTransport(targets(source_id), 1, 5).installed():
                        observation = public_worker(kind, symbol)
                    observation["ingested_at"] = now()  # Actual local evidence ingestion, not historical availability.
                    save_snapshot(root, observation)
                count = len(observation["prices"]) if source_id == "sina_index" else observation["rows"] if source_id == "cffex_rankings" else 1
                result.update(returned_rows=count, parse_status="PASS", observed_at=observation["observed_at"],
                              ingested_at=observation["ingested_at"])
            if observation is not None:
                if "prices" in observation or "records" in observation:
                    records = observation.get("prices", observation.get("records"))
                    result.update(data_date_min=min(r["trade_date"] for r in records), data_date_max=max(r["trade_date"] for r in records))
                    result.setdefault("actual_fields", sorted(records[0]))
                else:
                    result.update(data_date_min=observation["trade_date"], data_date_max=observation["trade_date"])
                    result["actual_fields"] = sorted(observation["breadth"]) if "breadth" in observation else ["contract", "member", "member_scope", "rank", "side", "open_interest", "volume"]
                if result["returned_rows"]:
                    result["status"] = "PASS"  # Transport/parse only, never source authorization/research certification.
                write_json(root / "observation.json", observation)
    except Exception as exc:
        result.update(error_type=type(exc).__name__, error_type_chain=_transport_type_chain(exc))
        if hasattr(exc, "http_status"):
            result["http_status"] = exc.http_status
    result.update(finished_at=now(), request_count=len(trace), http_trace=trace, tls_verification=True,
                  retries=0, certification_status="BLOCKED", observed_at=result.get("observed_at"),
                  historical_available_at="UNKNOWN", expected_latest_session="UNKNOWN")
    write_json(root / "result.json", result)
    return result


def run(output, *, enable_live=False, analysis_date="2026-10-19"):
    parent = checked_root(output)
    run_id = "pipeline-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ-") + uuid.uuid4().hex[:8]
    root = parent / run_id
    root.mkdir(parents=True, exist_ok=False)
    observations, results = {}, {}
    for source_id, spec in inventory().items():
        result = dict(source_id=source_id, status="NOT RUN" if source_id in LIVE else "BLOCKED",
            certification_status="BLOCKED", authorization="UNKNOWN", returned_rows=None, request_count=0,
            data_date_min=None, data_date_max=None, expected_samples=None, missing_dates=None,
            reason="real_network_not_enabled" if source_id in LIVE else "no_accepted_source_or_required_evidence")
        if source_id in LIVE and enable_live is True:
            command = [sys.executable, str(Path(__file__).resolve()), "--worker", source_id,
                       "--output-dir", str(root / source_id), "--run-id", run_id + ":" + source_id, "--enable-live"]
            env = dict(os.environ, PYTHONPATH=str(REPO / "src"), PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
            try:
                process = subprocess.run(command, cwd=REPO, env=env, capture_output=True, timeout=45)
                path = root / source_id / "result.json"
                if path.exists():
                    result = json.loads(path.read_text(encoding="utf-8"))
                else:
                    result.update(status="FAIL", request_count=None, reason="worker_failed_without_final_evidence", worker_exit=process.returncode)
            except subprocess.TimeoutExpired:
                result.update(status="BLOCKED", request_count=None, reason="worker_45_second_deadline", error_type="TimeoutExpired")
            saved = root / source_id / "observation.json"
            if result["status"] == "PASS" and saved.exists():
                observations[source_id] = json.loads(saved.read_text(encoding="utf-8"))
        results[source_id] = result
    as_of = now()
    bundle = build_bundle(observations, analysis_date=analysis_date, as_of=as_of, run_id=run_id)
    write_json(root / "pipeline-bundle.json", bundle)
    summary = public_summary(bundle, results)
    summary["execution"] = dict(enable_live=enable_live, endpoint_send_limit=1, retries=0,
                                live_http_send_budget=6, worker_deadline_seconds=45, observation_keys=sorted(observations))
    write_json(root / "summary.json", summary)
    print(json.dumps(dict(run_id=run_id, evidence_directory=str(root),
        source_status={key: value["status"] for key, value in results.items()}), ensure_ascii=False))
    return root


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=REPO / "artifacts/m3-data-pipeline-001")
    parser.add_argument("--enable-live", action="store_true")
    parser.add_argument("--analysis-date", default="2026-10-19")
    parser.add_argument("--worker", choices=LIVE, help=argparse.SUPPRESS)
    parser.add_argument("--run-id", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.worker:
        worker(args.worker, args.output_dir, args.run_id, enable_live=args.enable_live)
    else:
        run(args.output_dir, enable_live=args.enable_live, analysis_date=args.analysis_date)
    return 0  # Evidence generation success; each source keeps its own status.


if __name__ == "__main__":
    raise SystemExit(main())

"""Explicit three-request source acceptance, no DB, retries or source switching.

Raw local observations go only to ignored artifacts/. Commit only a reviewed
summary. A successful request does not certify authorization/calendar/timestamps.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

from ai_trade.market_analysis_data import collect_cffex, collect_public, price_frame
from ai_trade.market_analysis_contract import Request, SourceEvidence
from ai_trade.market_analysis_core import fear_greed_diagnostic, price_diagnostics


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enable-live", action="store_true", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/m3-core-001"))
    parser.add_argument("--cffex-date", default="2026-10-16")
    args = parser.parse_args()
    artifacts = (Path(__file__).resolve().parents[1] / "artifacts").resolve()
    if not args.output_dir.resolve().is_relative_to(artifacts):
        parser.error("Raw observations must stay inside this repository's ignored artifacts directory")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    report = dict(started_at=datetime.now(timezone.utc).isoformat(), akshare=importlib.metadata.version("akshare"),
                  requests_per_source_max=1, retries=0, tls_verification=True, results=[])
    for kind, symbol in (("index", "sh000300"), ("breadth", "market"), ("cffex", "IF")):
        row = dict(kind=kind, symbol=symbol, requested_date=args.cffex_date if kind == "cffex" else None)
        try:
            item = (collect_cffex(args.output_dir, symbol, args.cffex_date) if kind == "cffex"
                    else collect_public(args.output_dir, kind, symbol))
            row.update(status="OBSERVED", source=item["source"], data_date=item["trade_date"],
                       observed_at=item["observed_at"], ingested_at=item.get("ingested_at"),
                       available_at=item.get("available_at"), authorization="UNKNOWN",
                       fields=sorted(item.get("prices", [item.get("breadth", {})])[0]) if kind != "cffex" else
                       ["contract", "rank", "side", "member", "member_scope", "open_interest", "open_interest_change", "volume"],
                       rows=len(item["prices"]) if kind == "index" else item["rows"] if kind == "cffex" else 1,
                       trace=item.get("http_trace"), payload_sha256=item.get("payload_sha256"),
                       calendar="UNKNOWN", time_certification="UNKNOWN")
            if kind == "index":
                row["first_date"] = item["prices"][0]["trade_date"]
                frame = price_frame(item)
                src = SourceEvidence(item["source"], "akshare-1.19.1-observation", ("sha256:"+hashlib.sha256(json.dumps(item, sort_keys=True).encode()).hexdigest(),))
                req = Request(item["trade_date"], datetime.now(timezone.utc).isoformat(), symbol)
                diagnostics = price_diagnostics(frame, request=req, source=src)
                diagnostics["fear_greed"] = fear_greed_diagnostic(frame, request=req, source=src)
                row["diagnostics"] = {k: dict(status=d.status.value, admission=d.admission.value, calculated=d.calculated,
                    reasons=[r.code.value for r in d.reasons], valid=d.coverage.valid_samples,
                    expected=d.coverage.expected_samples) for k, d in diagnostics.items()}
            if kind == "cffex":
                row["contracts"] = item["contracts"]
        except Exception as exc:
            # Do not persist exception URLs, response bodies, proxy or credentials.
            row.update(status="ENV_BLOCKED", error_type=type(exc).__name__)
            if isinstance(exc, RuntimeError):
                # collect_public exposes only a bounded error type/allowlisted HTTP trace.
                row["worker_result"] = str(exc)
            if isinstance(exc, subprocess.TimeoutExpired):
                row["worker_timeout_seconds"] = 30
            if hasattr(exc, "http_status"):
                row["http_status"] = exc.http_status
        report["results"].append(row)
    output = args.output_dir / "source-summary.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False)+"\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

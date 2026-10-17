"""Offline checks of diagnostic boundaries, without opening TLS connections."""

import json
from pathlib import Path
import runpy
import sys
import time

import pytest


@pytest.fixture(scope="module")
def diagnostics():
    return runpy.run_path(str(Path(__file__).parents[2] / "tools" / "diagnose_akshare_tls.py"))


def test_default_diagnostics_open_no_network_or_database(diagnostics, tmp_path, monkeypatch):
    output = tmp_path / "readonly.json"
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("QUANT_DB_ENV", raising=False)
    monkeypatch.delenv("QUANT_DB_PATH", raising=False)
    monkeypatch.setattr(sys, "argv", ["diagnose_akshare_tls.py", "--output", str(output)])
    diagnostics["main"]()
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["network_opt_in"] is False and report["probes"] == []
    assert report["database"]["connection_opened"] is False
    assert not (tmp_path / "data").exists()


def test_proxy_credentials_are_never_returned(diagnostics):
    result = diagnostics["proxy_info"]("http://fixture-user:fixture-secret@127.0.0.1:7890")
    assert result["credentials_present"] is True
    assert "fixture-user" not in json.dumps(result) and "fixture-secret" not in json.dumps(result)


def test_unknown_target_is_rejected_before_connecting(diagnostics):
    with pytest.raises(ValueError, match="fixed host/route"):
        diagnostics["tls_probe"]("example.invalid", "direct", None, [], time.monotonic() + 1)


@pytest.mark.parametrize("proxy", [
    {"scheme": "http", "host": "127.0.0.1", "port": 7890, "credentials_present": True},
    {"scheme": "http", "host": "example.invalid", "port": 7890, "credentials_present": False},
])
def test_unsupported_proxy_is_skipped_without_credentials_or_network(diagnostics, proxy):
    result = diagnostics["tls_probe"]("push2his.eastmoney.com", "proxy", proxy, [], time.monotonic() + 1)
    assert result["status"] == "skipped"
    assert result["market_http_get_sent"] is False

"""Exercise the optional Streamlit Demo without external network access."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(importlib.util.find_spec("streamlit") is None,
                    reason="install the optional demo extra")
def test_demo_only_collects_once_per_click():
    # Streamlit's in-process test loop needs a Windows loopback socketpair.
    # Keep the repository's pytest network guard intact in this parent process.
    script = r'''
import json
import socket
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from ai_trade.market_data import akshare_adapter

real_connect = socket.socket.connect
def loopback_only(sock, address):
    if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
        return real_connect(sock, address)
    raise AssertionError("offline Demo test forbids external network")
socket.socket.connect = loopback_only

calls = []
class OfflineClient:
    sdk_version = "1.19.1"
    def fetch(self, request, *, timeout):
        calls.append((request.symbol, request.start_date, request.end_date,
                      request.adjustment_method))
        raise ConnectionError("offline transport failure")

with patch.object(akshare_adapter, "AkshareDailyClient", OfflineClient):
    app = AppTest.from_file("src/ai_trade/demo_app.py").run()
    initial_calls = len(calls)
    initial_errors = len(app.exception)
    def collect():
        return next(button for button in app.button if button.label == "采集真实行情")
    app = collect().click().run()
    first_calls = len(calls)
    first_errors = len(app.exception)
    first_count = next(metric.value for metric in app.metric if metric.label == "返回行数")
    first_inserted = next(metric.value for metric in app.metric if metric.label == "入库行数")
    app = app.run()
    rerun_calls = len(calls)
    rerun_errors = len(app.exception)
    app = collect().click().run()
    second_calls = len(calls)
    second_errors = len(app.exception)

print(json.dumps({"initial_calls": initial_calls, "first_calls": first_calls,
                  "rerun_calls": rerun_calls, "second_calls": second_calls,
                  "calls": calls, "first_count": first_count,
                  "first_inserted": first_inserted,
                  "errors": [initial_errors, first_errors, rerun_errors, second_errors]}))
'''
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, "-c", script], cwd=root,
                            capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["errors"] == [0, 0, 0, 0]
    assert evidence["initial_calls"] == 0
    assert evidence["first_calls"] == evidence["rerun_calls"] == 1
    assert evidence["second_calls"] == 2
    assert evidence["calls"] == [["600000.SH", "2026-10-14", "2026-10-15", "none"]] * 2
    assert evidence["first_count"] == "未知"
    assert evidence["first_inserted"] == "0"

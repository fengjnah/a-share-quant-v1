"""Offline checks for the one-request diagnostic boundary."""

import http.client
import importlib.util
import socket
import ssl
from pathlib import Path

import pytest
import requests


SCRIPT = Path(__file__).resolve().parents[2] / "tools" / "diagnose_akshare_direct.py"
spec = importlib.util.spec_from_file_location("diagnose_akshare_direct", SCRIPT)
diagnostic = importlib.util.module_from_spec(spec)
spec.loader.exec_module(diagnostic)
PARAMS = {"secid": "1.600000", "beg": "20261014", "end": "20261015",
          "klt": "101", "fqt": "0"}
TARGET = requests.Request("GET", diagnostic.URL, params=PARAMS).prepare().url


def fake_response(request, status=200):
    result = requests.Response()
    result.status_code = status
    result.url = request.url
    result.request = request
    if status == 302:
        result.headers["Location"] = "/another-path"
    return result


def test_one_adapter_send_and_no_redirect(monkeypatch):
    monkeypatch.setenv("NO_PROXY", diagnostic.HOST)
    calls = []

    def fake_send(adapter, request, *args, **kwargs):
        calls.append((request.method, request.url, adapter.max_retries.total))
        return fake_response(request, 302)

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", fake_send)
    audit = diagnostic.audit_template()
    trace = diagnostic.TransportTrace(audit)
    with trace.installed():
        response = requests.get(diagnostic.URL, params=PARAMS, timeout=3)
    assert response.status_code == 302
    assert len(calls) == trace.adapter_attempts == trace.session_attempts == 1
    assert calls[0][2] == 0
    assert audit["requests"]["redirects_disabled"] is True
    assert audit["blocked_requests"] == []


def test_budget_blocks_second_send_and_unexpected_target():
    audit = diagnostic.audit_template()
    trace = diagnostic.TransportTrace(audit)
    trace.check_send("GET", TARGET)
    with pytest.raises(diagnostic.RequestBudgetExceeded):
        trace.check_send("GET", TARGET)
    assert trace.adapter_attempts == 1
    assert audit["blocked_requests"] == ["second_adapter_send"]
    other = diagnostic.TransportTrace(diagnostic.audit_template())
    with pytest.raises(diagnostic.RequestBudgetExceeded):
        other.check_send("GET", "https://example.com/")
    assert other.adapter_attempts == 0


def test_hooks_restore_after_exception():
    names = (socket.getaddrinfo, socket.socket.connect, ssl.SSLContext.wrap_socket,
             requests.Session.send, requests.adapters.HTTPAdapter.send,
             http.client.HTTPConnection.send, http.client.HTTPResponse._read_status)
    trace = diagnostic.TransportTrace(diagnostic.audit_template())
    with pytest.raises(ValueError), trace.installed():
        raise ValueError("deliberate")
    assert names == (socket.getaddrinfo, socket.socket.connect, ssl.SSLContext.wrap_socket,
                     requests.Session.send, requests.adapters.HTTPAdapter.send,
                     http.client.HTTPConnection.send, http.client.HTTPResponse._read_status)


def test_exception_chain_excludes_messages():
    try:
        try:
            raise OSError("proxy-user:secret@host")
        except OSError as exc:
            raise requests.ConnectionError("token=secret") from exc
    except requests.ConnectionError as exc:
        assert diagnostic.error_types(exc) == ["ConnectionError", "OSError"]

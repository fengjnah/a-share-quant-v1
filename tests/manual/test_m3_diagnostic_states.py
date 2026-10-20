"""Actual Streamlit renderer over synthetic core results; no source acceptance."""
from pathlib import Path
import subprocess
import sys


def test_m3_core_state_matrix_keeps_unknowns_and_hides_blocked_values():
    script = r'''
import sys, socket, tempfile
from pathlib import Path
from dataclasses import replace
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
sys.path.insert(0, 'tests/unit')
from test_market_analysis_core import prices, source, request, compute
from ai_trade import market_analysis_page as page
from ai_trade.market_analysis_view import LocalInput, unavailable, diagnostic_bundle
from ai_trade.market_analysis_core import environment_diagnostic
from ai_trade.market_analysis_contract import Admission, Status

real_connect = socket.socket.connect
def loopback_only(sock, address):
    # Windows asyncio creates its self-pipe over loopback TCP.
    if isinstance(address, tuple) and address[0] in ('127.0.0.1', '::1'):
        return real_connect(sock, address)
    raise AssertionError('offline UI matrix forbids networking')
socket.socket.connect = loopback_only
f = prices()
req = request(f)
def bundle(frame=f, request=req, error=None):
    return diagnostic_bundle(LocalInput(frame, source(), error=error), unavailable('breadth'), request=request)
cases = {
    'empty': diagnostic_bundle(unavailable('price'), unavailable('breadth'), request=req),
    'partial': bundle(),
    'stale': bundle(request=replace(req, analysis_date='2026-10-16')),
    'date_mismatch': bundle(frame=f.assign(trade_date='2026-01-05')),
    'illegal': bundle(frame=f.assign(close=float('inf'))),
    'parse_failure': bundle(error='本地解析失败，未生成替代数据'),
}
wave = compute(f)['wave']
conflict = environment_diagnostic(dict(wave=wave,
    fear_greed=replace(wave, indicator='fear_greed', values={'score':80}),
    cffex_position=replace(wave, indicator='cffex_position', values={'direction':'偏空'})), request=req)
cases['conflict'] = {**bundle(), 'environment': conflict}
# Deliberately inconsistent payload from a future caller must still fail closed.
cases['blocked_payload'] = {k: replace(d, status=Status.BLOCKED, admission=Admission.BLOCKED,
    calculated=True, values={'score':999999, 'close':999999}) for k,d in bundle().items()}
with tempfile.TemporaryDirectory() as folder:
    script = "from types import SimpleNamespace\nfrom pathlib import Path\nfrom ai_trade.market_analysis_page import render\nrender(SimpleNamespace(config=SimpleNamespace(path=Path(" + repr(folder) + ")/'test.sqlite3')))"
    for name, result in cases.items():
        with patch.object(page, 'diagnostic_bundle', return_value=result):
            app = AppTest.from_string(script).run(timeout=20)
        assert not app.exception, (name, app.exception)
        overview = next(m.value for m in app.markdown if 'm3-overview' in m.value and '<article' in m.value)
        assert overview.count('<article') == 8
        assert 'UNKNOWN' in overview
        assert next(m.value for m in app.metric if m.label=='完整六因子分数') == 'UNKNOWN'
        assert all(m.value != '999999.0' for m in app.metric)
        assert len(app.expander) == 10
        if name in ('date_mismatch','illegal','parse_failure','blocked_payload','empty'):
            assert len(app.get('vega_lite_chart')) == 0, name
        if name == 'partial':
            assert next(m.value for m in app.metric if m.label=='独立价格代理分数') != 'UNKNOWN'
        if name == 'conflict':
            assert 'EVIDENCE_CONFLICT' in overview
            assert any('证据冲突' in m.value for m in app.markdown)
print('8 offline core/UI scenarios passed; live_trading=false')
'''
    result = subprocess.run([sys.executable, '-c', script], cwd=Path(__file__).resolve().parents[2],
                            capture_output=True, text=True, timeout=90)
    assert result.returncode == 0, result.stderr
    assert '8 offline core/UI scenarios passed' in result.stdout

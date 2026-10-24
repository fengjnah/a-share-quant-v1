"""Actual Streamlit entry with strict storage; subprocess only permits loopback."""
import subprocess
import sys
from pathlib import Path


def test_strict_workbench_all_pages_and_missing_store(tmp_path):
    script = r'''
import os, sys, socket, hashlib
from pathlib import Path
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from ai_trade.storage.db import Database
from ai_trade.storage.workbench_cli import initialize_new

base = Path(sys.argv[1])
data_root = base / 'data'
root = data_root / 'sqlite'
real = socket.socket.connect
def loopback(sock, address):
    if isinstance(address, tuple) and address[0] in ('127.0.0.1', '::1'):
        return real(sock, address)
    raise AssertionError('workbench UI test forbids external network')
socket.socket.connect = loopback
socket.create_connection = lambda *a, **k: (_ for _ in ()).throw(AssertionError('no network'))
# Explicit fixture directory; production Temp rejection tested separately.
with patch('ai_trade.storage.workbench.tempfile.gettempdir', return_value=str(base/'os-temp')):
    initialize_new(root, base/'backup.sqlite3', base/'restore.sqlite3')
    os.environ['AI_TRADE_WORKBENCH_ROOT'] = str(root)
    os.environ['AI_TRADE_DATA_ROOT'] = str(data_root)
    os.environ['AI_TRADE_STRICT_WORKBENCH'] = '1'
    for name in ('AI_TRADE_DEMO_ROOT', 'AI_TRADE_READ_ONLY', 'QUANT_DB_PATH', 'QUANT_DB_ENV', 'QUANT_DB_JOURNAL'):
        os.environ.pop(name, None)
    path = root/'workbench.sqlite3'
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    with patch.object(Database, 'initialize', side_effect=AssertionError('refresh must not initialize')):
        app = AppTest.from_file('src/ai_trade/demo_app.py', default_timeout=30).run()
        assert not app.exception and not app.error
        assert any(str(path) in c.value for c in app.code)
        assert next(b for b in app.button if b.label=='采集真实行情').disabled
        for label in ('交易分析', 'M3 市场分析', 'M4 每日选股', '行情工作台'):
            app.sidebar.radio[0].set_value(label).run()
            assert not app.exception
            assert any(str(path) in c.value for c in app.code)
            if label=='M3 市场分析':
                assert next(b for b in app.button if b.label=='查询真实指数历史').disabled
                assert any(m.value=='UNKNOWN' for m in app.metric)
        app.run()
        assert hashlib.sha256(path.read_bytes()).hexdigest()==before
        assert not list(root.glob('m3-observations/*'))
        os.environ['AI_TRADE_WORKBENCH_ROOT']=str(base/'missing')
        os.environ['AI_TRADE_DATA_ROOT']=str(base/'missing-data')
        fresh=AppTest.from_file('src/ai_trade/demo_app.py',default_timeout=30).run()
        assert not fresh.exception
        assert any('已停止' in e.value for e in fresh.error)
        assert not (base/'missing').exists()
        os.environ.pop('AI_TRADE_WORKBENCH_ROOT')
        os.environ.pop('AI_TRADE_DATA_ROOT')
        fresh=AppTest.from_file('src/ai_trade/demo_app.py',default_timeout=30).run()
        assert any('不回退临时库' in e.value for e in fresh.error)
print('strict M1-M4; no initialize; missing binding fails; no network: PASS')
'''
    result = subprocess.run([sys.executable, "-c", script, str(tmp_path)],
                            cwd=Path(__file__).resolve().parents[2], capture_output=True,
                            text=True, encoding="utf-8", timeout=150)
    assert result.returncode == 0, result.stdout + "\n" + result.stderr

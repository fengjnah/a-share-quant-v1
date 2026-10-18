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


@pytest.mark.skipif(importlib.util.find_spec("streamlit") is None,
                    reason="install the optional demo extra")
def test_demo_tencent_source_once_per_click_and_no_auto_request():
    """Tencent path: one real fetch per click, none on start, none on rerun."""
    script = r'''
import json
import socket
from unittest.mock import patch

from streamlit.testing.v1 import AppTest
from ai_trade.market_data import tx_adapter

real_connect = socket.socket.connect
def loopback_only(sock, address):
    if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
        return real_connect(sock, address)
    raise AssertionError("offline Demo test forbids external network")
socket.socket.connect = loopback_only

calls = []
class OfflineTxClient:
    sdk_version = "1.19.1"
    def __init__(self):
        # bypass version check side effect
        type(self).__init__ = lambda self: None
    @property
    def provider(self):
        return "tencent"
    def source_label(self):
        return "akshare-tencent:stock_zh_a_hist_tx:task-008-v1+sdk-1.19.1"
    def fetch(self, request, *, timeout):
        calls.append((request.symbol, request.start_date, request.end_date, request.adjustment_method))
        raise ConnectionError("offline transport failure")

with patch.object(tx_adapter, "TxDailyClient", OfflineTxClient):
    app = AppTest.from_file("src/ai_trade/demo_app.py").run()
    initial_calls = len(calls)
    initial_errors = len(app.exception)

    # Select the Tencent option and click collect exactly once.
    selectbox = next(s for s in app.selectbox if s.label == "行情数据源")
    selectbox.set_value("腾讯（备用候选）")
    def collect():
        return next(button for button in app.button if button.label == "采集真实行情")
    app = collect().click().run()
    first_calls = len(calls)
    first_errors = len(app.exception)
    first_count = next(metric.value for metric in app.metric if metric.label == "返回行数")

    # Plain rerun must not re-trigger the fetch.
    app = app.run()
    rerun_calls = len(calls)

    # Click again -> a second fetch, still one per click.
    app = collect().click().run()
    second_calls = len(calls)

    print(json.dumps({"initial_calls": initial_calls, "first_calls": first_calls,
                      "rerun_calls": rerun_calls, "second_calls": second_calls,
                      "calls": calls, "first_count": first_count,
                      "errors": [initial_errors, first_errors, len(app.exception)]}))
'''
    import subprocess, sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, "-c", script], cwd=root,
                            capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence["initial_calls"] == 0
    assert evidence["first_calls"] == evidence["rerun_calls"] == 1
    assert evidence["second_calls"] == 2
    assert evidence["first_count"] == "未知"
    assert evidence["calls"] == [["600000.SH", "2026-10-14", "2026-10-15", "none"]] * 2
    assert evidence["errors"] == [0, 0, 0]


@pytest.mark.skipif(importlib.util.find_spec("streamlit") is None,
                    reason="install the optional demo extra")
@pytest.mark.parametrize("provider", ["eastmoney", "tencent"])
def test_demo_success_reads_back_units_without_production_db(provider, tmp_path):
    script = r'''
import json, os, socket, sqlite3, sys
from datetime import date
from pathlib import Path
from unittest.mock import patch
import pandas as pd
from streamlit.testing.v1 import AppTest
from ai_trade.market_data import akshare_adapter, tx_adapter
provider = sys.argv[1]
production = Path(sys.argv[2])
os.environ['QUANT_DB_ENV'] = 'production'
os.environ['QUANT_DB_PATH'] = str(production)
real_connect = socket.socket.connect
def loopback_only(sock, address):
    if isinstance(address, tuple) and address[0] in ('127.0.0.1', '::1'):
        return real_connect(sock, address)
    raise AssertionError('offline Demo test forbids external network')
socket.socket.connect = loopback_only
calls = []
class Eastmoney:
    sdk_version = '1.19.1'
    def fetch(self, request, *, timeout):
        calls.append('eastmoney')
        return pd.DataFrame({'日期':['2026-10-14'], '股票代码':['600000'],
                             '开盘':[10.0], '收盘':[11.0], '最高':[12.0], '最低':[9.0],
                             '成交量':[123], '成交额':[135300.0]})
class Tencent(tx_adapter.TxDailyClient):
    sdk_version = '1.19.1'
    def __init__(self): pass
    def fetch(self, request, *, timeout):
        calls.append('tencent')
        return pd.DataFrame({'date':[date(2026,10,14)], 'open':[10.0], 'close':[11.0],
                             'high':[12.0], 'low':[9.0], 'volume':[12300], 'amount':[135300.0]})
with patch.object(akshare_adapter, 'AkshareDailyClient', Eastmoney), patch.object(tx_adapter, 'TxDailyClient', Tencent):
    app = AppTest.from_file('src/ai_trade/demo_app.py').run()
    source = next(s for s in app.selectbox if s.label == '行情数据源')
    assert source.value == '东方财富（主源）'
    assert calls == []
    if provider == 'tencent': source.set_value('腾讯（备用候选）')
    button = next(b for b in app.button if b.label == '采集真实行情')
    app = button.click().run()
    assert len(app.exception) == 0
    assert next(m.value for m in app.metric if m.label == '状态') == 'success'
    assert next(m.value for m in app.metric if m.label == '返回行数') == '1'
    db = Path(app.session_state['demo_root']) / 'demo.sqlite3'
    with sqlite3.connect(db.as_uri()+'?mode=ro', uri=True) as conn:
        volume, amount, source = conn.execute('select volume,amount,source from daily_bar_versions').fetchone()
        assert volume == 12300 and amount == 135300.0
        assert provider in source
    shown = app.dataframe[0].value
    assert shown.iloc[0]['volume_shares'] == volume
    assert shown.iloc[0]['amount_cny'] == amount
    app = app.run()
    assert calls == [provider] and len(app.exception) == 0
    assert not production.exists()
print(json.dumps({'calls':calls, 'production_created':production.exists(), 'readback':'matched'}))
'''
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run([sys.executable, "-c", script, provider, str(tmp_path / "production.sqlite3")],
                            cwd=root, capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 0, result.stderr
    evidence = json.loads(result.stdout)
    assert evidence == {"calls": [provider], "production_created": False, "readback": "matched"}


@pytest.mark.skipif(importlib.util.find_spec("streamlit") is None, reason="install demo extra")
def test_m1_local_query_charts_empty_invalid_and_database_error():
    """Synthetic data exercise UI behavior; never count this as real-source acceptance."""
    script = r'''
import os,socket,sqlite3,tempfile,json
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch
import requests
from streamlit.testing.v1 import AppTest
from ai_trade.data_access.models import DailyBar
from ai_trade.data_access.repository import SQLiteMarketDataRepository
from ai_trade.demo_data import SOURCES
from ai_trade.storage.db import Database,DatabaseConfig
real=socket.socket.connect
def loopback(sock,address):
    if isinstance(address,tuple) and address[0] in ('127.0.0.1','::1'): return real(sock,address)
    raise AssertionError('offline: no external network')
socket.socket.connect=loopback
with tempfile.TemporaryDirectory(prefix='a-share-quant-demo-') as folder:
    os.environ['AI_TRADE_DEMO_ROOT']=folder
    db=Database(DatabaseConfig(Path(folder)/'demo.sqlite3',environment='test',journal_mode='DELETE'));db.initialize()
    bar=DailyBar(instrument_id='synthetic:m1:600000',symbol='600000.SH',trade_date='2026-10-14',
        open=10.0,high=12.0,low=9.0,close=11.0,volume=12300,amount=135300.0,
        source=SOURCES['腾讯（备用候选）'],source_version='synthetic-1',
        event_time='2026-10-14T07:00:00+00:00',available_at='2026-10-16T09:00:00+00:00',
        ingested_at='2026-10-16T09:01:00+00:00',adjustment_method='none')
    SQLiteMarketDataRepository(db).write_many([bar,replace(bar,trade_date='2026-10-15',
        event_time='2026-10-15T07:00:00+00:00',source_version='synthetic-2',close=10.5,volume=23400)],run_id='synthetic-m1')
    with patch.object(requests.Session,'send',side_effect=AssertionError('local query cannot request')) as send:
        app=AppTest.from_file('src/ai_trade/demo_app.py').run()
        assert not app.exception
        next(s for s in app.selectbox if s.label=='行情数据源').set_value('腾讯（备用候选）')
        def query(app): return next(b for b in app.button if b.label=='查询本地已有数据').click().run()
        app=query(app)
        assert not app.exception
        assert next(m.value for m in app.metric if m.label=='数据库读回行数')=='2'
        assert app.dataframe[0].value.volume_shares.tolist()==[12300,23400]
        assert app.dataframe[0].value.close.tolist()==[11.0,10.5]
        assert len(app.get('vega_lite_chart'))==2
        app=app.run()
        assert len(app.dataframe[0].value)==2 and not app.exception
        # A new browser session reopens the same explicitly selected scratch DB.
        fresh=AppTest.from_file('src/ai_trade/demo_app.py').run()
        assert fresh.session_state['demo_root']==folder
        next(s for s in app.selectbox if s.label=='行情数据源').set_value('东方财富（主源）')
        app=query(app)
        assert next(m.value for m in app.metric if m.label=='数据库读回行数')=='0'
        assert any('没有本地数据' in i.value for i in app.info)
        next(t for t in app.text_input if t.label=='股票代码').set_value('600000.SZ')
        app=query(app)
        assert any('操作失败' in e.value for e in app.error) and not app.dataframe
        next(t for t in app.text_input if t.label=='股票代码').set_value('600000')
        next(s for s in app.selectbox if s.label=='行情数据源').set_value('腾讯（备用候选）')
        with patch.object(SQLiteMarketDataRepository,'get_bar',side_effect=RuntimeError('synthetic read failure')):
            app=query(app)
            assert any('SQLite 读取或数据校验失败' in e.value for e in app.error)
            assert not app.dataframe and not app.get('vega_lite_chart')
        assert send.call_count==0
    with db.connection() as c:
        assert c.execute('select count(*) from ingestion_runs').fetchone()[0]==1
        assert c.execute('select count(*) from daily_bar_versions').fetchone()[0]==2
print(json.dumps({'local_query':'2 rows, 2 charts','rerun_runs':1,'network_calls':0,'empty_invalid_db_error':'explicit'}))
'''
    result = subprocess.run([sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[2],
                            capture_output=True, text=True, encoding="utf-8", timeout=40)
    assert result.returncode == 0, result.stdout + result.stderr
    assert json.loads(result.stdout)["network_calls"] == 0

"""Offline Streamlit navigation and failure states, using the existing subprocess pattern."""
import json
from pathlib import Path
import subprocess
import sys


def test_m3_empty_failure_read_only_and_m1_m2_navigation():
    script = r'''
import json, socket, os
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from ai_trade import market_analysis_data
real_connect = socket.socket.connect
def loopback_only(sock, address):
    if isinstance(address, tuple) and address[0] in ('127.0.0.1', '::1'):
        return real_connect(sock, address)
    raise AssertionError('offline M3 test forbids external network')
socket.socket.connect = loopback_only
os.environ.pop('AI_TRADE_WORKBENCH_ROOT', None)
os.environ.pop('AI_TRADE_DEMO_ROOT', None)
os.environ.pop('AI_TRADE_READ_ONLY', None)
calls = []
def failed(*args):
    calls.append(args[1:])
    raise ConnectionError('synthetic offline failure')
with patch.object(market_analysis_data, 'collect_cffex', failed):
    app = AppTest.from_file('src/ai_trade/demo_app.py')
    app.query_params['view'] = 'market'
    app.run(timeout=15)
    assert not app.exception
    assert not calls
    assert any(m.value == 'UNKNOWN' for m in app.metric)
    assert any('SOURCE_UNAVAILABLE' in m.value for m in app.markdown)
    assert any('Issue #37' in w.value for w in app.warning)
    next(b for b in app.button if b.label == '查询该日真实CFFEX榜单').click().run()
    assert not app.exception and len(calls) == 1
    assert any('接口失败' in e.value for e in app.error)
    app.run()
    assert len(calls) == 1
    for name in ('行情工作台', '交易分析', 'M3 市场分析'):
        app.sidebar.radio[0].set_value(name).run(timeout=15)
        assert not app.exception
    os.environ['AI_TRADE_READ_ONLY'] = '1'
    app.run()
    assert all(b.disabled for b in app.button if b.label.startswith('查询真实') or b.label == '查询该日真实CFFEX榜单')
print(json.dumps({'calls': len(calls), 'navigation': 3, 'exceptions': len(app.exception)}))
'''
    result = subprocess.run([sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[2],
                            capture_output=True, text=True, timeout=70)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"calls": 1, "navigation": 3, "exceptions": 0}


def test_m3_raw_rankings_cannot_bypass_core_and_price_proxy_stays_separate():
    script = r'''
import os,sys,json,tempfile,hashlib,socket
from pathlib import Path
from streamlit.testing.v1 import AppTest
from ai_trade.storage.db import Database,DatabaseConfig
from ai_trade.market_analysis_data import save_snapshot
sys.path.insert(0,'tests/unit')
from test_cffex_rankings import named
from test_market_analysis import prices,ASOF
real_connect=socket.socket.connect
def loopback_only(sock,address):
    if isinstance(address,tuple) and address[0] in ('127.0.0.1','::1'):
        return real_connect(sock,address)
    raise AssertionError('offline test')
socket.socket.connect=loopback_only
with tempfile.TemporaryDirectory(prefix='a-share-quant-demo-') as folder:
    root=Path(folder)
    Database(DatabaseConfig(root/'demo.sqlite3',environment='test',journal_mode='DELETE')).initialize()
    os.environ['AI_TRADE_DEMO_ROOT']=folder
    os.environ.pop('AI_TRADE_WORKBENCH_ROOT',None)
    for day in ('2026-10-15','2026-10-16'):
        payload=named(day=day).decode('gbk').replace('甲会员','中信期货').encode('gbk')
        save_snapshot(root,dict(kind='cffex',symbol='IF',trade_date=day,observed_at=ASOF,
            source='synthetic:offline',format='named',status='synthetic offline fixture',
            contracts=['IF2610','IF2611','IF2612','IF2703'],raw_csv_hex=payload.hex(),
            payload_sha256=hashlib.sha256(payload).hexdigest(),available_at=None))
    f=prices(200)
    f['source']='synthetic:offline'
    f['symbol']='sh000300'
    save_snapshot(root,dict(kind='index',symbol='sh000300',trade_date=f.trade_date.max(),
        observed_at=ASOF,source='synthetic:offline',prices=f.to_dict('records')))
    app=AppTest.from_file('src/ai_trade/demo_app.py')
    app.query_params['view']='market'
    app.run(timeout=15)
    assert not app.exception
    cf = next(s for s in app.selectbox if s.label == 'CFFEX 本地版本')
    assert cf.value is None  # Multiple saved versions require a choice.
    cf.set_value(cf.options[-1]).run()
    next(s for s in app.selectbox if s.label.startswith('合约范围')).set_value('IF2611').run()
    assert not app.exception
    assert not any(m.label in ('净持仓','净变化（榜单公布变化之差）') for m in app.metric)
    assert next(m.value for m in app.metric if m.label=='完整六因子分数')=='UNKNOWN'
    assert next(m.value for m in app.metric if m.label=='独立价格代理分数')!='UNKNOWN'
    assert any('CffexRankingsRecord' in str(t.value) for t in app.dataframe)
    assert len(app.get('vega_lite_chart'))>=2
    app.run()
    assert not app.exception
    assert len(list((root/'m3-observations').glob('*.json')))==3
print(json.dumps({'charts':'rendered','net':'BLOCKED','observations':3}))
'''
    result = subprocess.run([sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[2],
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["net"] == 'BLOCKED'

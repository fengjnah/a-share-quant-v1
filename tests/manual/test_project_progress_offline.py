"""Real Streamlit widget lifecycle with forbidden network/DB; no browser claim."""
import importlib.util
import json
import subprocess
import sys

import pytest

from ai_trade.project_progress.core import ROOT


@pytest.mark.skipif(importlib.util.find_spec('streamlit') is None,reason='install demo extra')
def test_progress_survives_market_db_failure_and_never_fetches(tmp_path):
    script=r'''
import json,os,socket,sys
from pathlib import Path
from unittest.mock import patch
import requests
from streamlit.testing.v1 import AppTest
from ai_trade.storage.db import Database
production=Path(sys.argv[1]);os.environ['QUANT_DB_ENV']='production';os.environ['QUANT_DB_PATH']=str(production)
real=socket.socket.connect
def only_loopback(sock,address):
    if isinstance(address,tuple) and address[0] in ('127.0.0.1','::1'):return real(sock,address)
    raise AssertionError('no external networking')
socket.socket.connect=only_loopback
with patch.object(Database,'initialize',side_effect=RuntimeError('synthetic unavailable database')) as db, patch.object(requests.Session,'send',side_effect=AssertionError('market network forbidden')) as send:
    app=AppTest.from_file('src/ai_trade/demo_app.py')
    app.query_params['view']='progress';app.run()
    assert not app.exception
    assert any(m.label=='有证据的加权完成率' for m in app.metric)
    assert db.call_count==0 and send.call_count==0
    app=app.radio[0].set_value('行情工作台').run()
    assert db.call_count==1 and any('初始化失败' in e.value for e in app.error)
    app=app.radio[0].set_value('项目进度').run()
    assert not app.exception
    assert any(m.label=='有证据的加权完成率' for m in app.metric)
    app=app.selectbox[0].set_value('TASK-004A').run()
    assert any('BLOCKED' in m.value for m in app.markdown)
    assert any('FAIL' in str(d.value) for d in app.dataframe)
    assert send.call_count==0 and not production.exists()
print(json.dumps({'progress':'opened_before_and_after_market_failure','network_calls':0,'production_created':False}))
'''
    r=subprocess.run([sys.executable,'-c',script,str(tmp_path/'production.sqlite3')],cwd=ROOT,
                     capture_output=True,text=True,encoding='utf-8',timeout=40)
    assert r.returncode==0,r.stdout+'\n'+r.stderr
    assert json.loads(r.stdout)['network_calls']==0


@pytest.mark.skipif(importlib.util.find_spec('streamlit') is None,reason='install demo extra')
def test_market_transport_failure_does_not_prevent_progress_navigation():
    script=r'''
import socket
from unittest.mock import patch
from streamlit.testing.v1 import AppTest
from ai_trade.market_data import akshare_adapter
real=socket.socket.connect
def loopback(sock,address):
    if isinstance(address,tuple) and address[0] in ('127.0.0.1','::1'):return real(sock,address)
    raise AssertionError('external networking prohibited')
socket.socket.connect=loopback
class Offline:
    sdk_version='1.19.1'
    def fetch(self,*args,**kwargs):raise ConnectionError('synthetic offline transport failure')
with patch.object(akshare_adapter,'AkshareDailyClient',Offline):
    app=AppTest.from_file('src/ai_trade/demo_app.py').run()
    app=next(b for b in app.button if b.label=='采集真实行情').click().run()
    assert next(m.value for m in app.metric if m.label=='状态')=='network_error'
    assert next(m.value for m in app.metric if m.label=='返回行数')=='未知'
    app=app.radio[0].set_value('项目进度').run()
    assert not app.exception
    assert any(m.label=='有证据的加权完成率' for m in app.metric)
print('offline network_error -> progress: PASS')
'''
    r=subprocess.run([sys.executable,'-c',script],cwd=ROOT,capture_output=True,text=True,encoding='utf-8',timeout=40)
    assert r.returncode==0,r.stdout+'\n'+r.stderr

"""Synthetic UI lifecycle; no network, production DB or true-market claim."""
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.skipif(importlib.util.find_spec("streamlit") is None,reason="install demo extra")
def test_m2_page_matches_calculations_and_does_not_collect_on_rerun():
    script=r'''
import os,socket,tempfile,json
from pathlib import Path
from datetime import date,timedelta
from unittest.mock import patch
import requests
from streamlit.testing.v1 import AppTest
from ai_trade.data_access.models import DailyBar
from ai_trade.data_access.repository import SQLiteMarketDataRepository
from ai_trade.demo_data import SOURCES
from ai_trade.storage.db import Database,DatabaseConfig
real=socket.socket.connect
def loopback(sock,address):
    if isinstance(address,tuple) and address[0] in ('127.0.0.1','::1'):return real(sock,address)
    raise AssertionError('offline only')
socket.socket.connect=loopback
with tempfile.TemporaryDirectory(prefix='a-share-quant-demo-') as folder:
    os.environ['AI_TRADE_DEMO_ROOT']=folder
    db=Database(DatabaseConfig(Path(folder)/'demo.sqlite3',environment='test',journal_mode='DELETE'));db.initialize()
    records=[]
    for i in range(65):
        day=(date(2026,8,12)+timedelta(days=i)).isoformat();c=100.+i
        records.append(DailyBar(instrument_id='synthetic:m2:600000',symbol='600000.SH',trade_date=day,
            open=c,high=c+1,low=c-1,close=c,volume=1000,amount=100000.,
            source=SOURCES['腾讯（备用候选）'],source_version=f'synthetic-{i}',event_time=day+'T07:00:00+00:00',
            available_at='2026-10-16T09:00:00+00:00',ingested_at='2026-10-16T09:01:00+00:00',adjustment_method='none'))
    SQLiteMarketDataRepository(db).write_many(records,run_id='synthetic-m2-ui')
    with patch.object(requests.Session,'send',side_effect=AssertionError('local analysis must not fetch')) as send:
        app=AppTest.from_file('src/ai_trade/demo_app.py');app.query_params['view']='analysis';app.run()
        assert not app.exception
        app.checkbox[0].check()
        app=next(b for b in app.button if b.label=='分析本地真实行情').click().run(timeout=15)
        assert not app.exception
        assert next(m.value for m in app.metric if m.label=='MA60')=='134.5000'
        assert next(m.value for m in app.metric if m.label=='ATR14')=='2.0000'
        assert len(app.get('vega_lite_chart'))==3
        candidate=app.dataframe[0].value.iloc[0]
        assert candidate['研究评分']==40 and candidate['候选准入']=='未通过'
        assert any('正式候选 0' in w.value for w in app.warning)
        detail=app.dataframe[-1].value
        assert detail.close.iloc[-1]==164 and detail.MA60.iloc[-1]==134.5
        assert detail.ATR14.iloc[-1]==2
        assert any('市场环境：数据不足' in i.value for i in app.info)
        app=app.run(timeout=15)
        assert not app.exception and send.call_count==0
        app=app.radio[0].set_value('行情工作台').run()
        assert any(b.label=='查询本地已有数据' for b in app.button)
        assert send.call_count==0
    with db.connection() as c:
        assert c.execute('select count(*) from ingestion_runs').fetchone()[0]==1
print(json.dumps({'charts':3,'prediction_claim':False,'automatic_fetches':0}))
'''
    result=subprocess.run([sys.executable,"-c",script],cwd=Path(__file__).resolve().parents[2],
        capture_output=True,text=True,encoding="utf-8",timeout=45)
    assert result.returncode==0,result.stdout+result.stderr

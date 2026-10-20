"""Network-blocked M4 lifecycle against isolated synthetic observations."""
import importlib.util
from pathlib import Path
import subprocess
import sys

import pytest


@pytest.mark.skipif(importlib.util.find_spec("streamlit") is None, reason="install demo extra")
def test_m4_snapshot_budget_modes_and_missing_symbol_without_network():
    script = r'''
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
        records.append(DailyBar(instrument_id='synthetic:m4:600000',symbol='600000.SH',trade_date=day,
            open=c,high=c+1,low=c-1,close=c,volume=1000,amount=100000.,
            source=SOURCES['腾讯（备用候选）'],source_version=f'synthetic-{i}',event_time=day+'T07:00:00+00:00',
            available_at='2026-10-16T09:00:00+00:00',ingested_at='2026-10-16T09:01:00+00:00',adjustment_method='none'))
    SQLiteMarketDataRepository(db).write_many(records,run_id='synthetic-m4-ui')
    with patch.object(requests.Session,'send',side_effect=AssertionError('M4 must not fetch')) as send:
        app=AppTest.from_file('src/ai_trade/demo_app.py')
        app.query_params['view']='candidates'
        app.run(timeout=20)
        assert not app.exception
        assert next(m.value for m in app.metric if m.label=='合格候选')=='0'
        assert any('今日无合格候选' in w.value for w in app.warning)
        assert next(m.value for m in app.metric if m.label=='新增多头仓位')=='未获准'
        assert any('市场状态未完成计算' in w.value for w in app.warning)
        next(s for s in app.selectbox if s.label=='M4 页面').set_value('六阶段选股监控').run(timeout=20)
        table=next(d.value for d in app.dataframe if '技术研究评分' in d.value.columns)
        assert table.iloc[0]['技术研究评分']==40 and table.iloc[0]['当前阶段']=='阶段待识别'
        assert table.iloc[0]['阶段进入日期'] is None and table.iloc[0]['综合评分'] is None
        next(s for s in app.selectbox if s.label=='M4 页面').set_value('股票详情').run(timeout=20)
        assert not app.exception
        detail=app.dataframe[-1].value
        assert detail.close.iloc[-1]==164
        assert next(m.value for m in app.metric if m.label=='技术研究评分')=='40'
        assert len(app.get('vega_lite_chart'))==3
        first=app.session_state['m4_batch'].evaluations[0]
        assert not first.research_match
        next(s for s in app.selectbox if s.label=='策略模式').set_value('趋势确认模式')
        next(t for t in app.text_input if t.label=='账户权益（元，可留空）').set_value('100000')
        next(b for b in app.button if b.label=='生成每日候选').click().run(timeout=20)
        assert not app.exception
        second=app.session_state['m4_batch'].evaluations[0]
        assert second.research_match and not second.eligible
        assert second.risk['risk_budget']==1000 and second.risk['theoretical_shares'] is None
        timestamp=second.analysis.summary['signal_available_at']
        app.run(timeout=20)
        assert app.session_state['m4_batch'].evaluations[0].analysis.summary['signal_available_at']==timestamp
        next(s for s in app.selectbox if s.label=='股票池范围').set_value('指定股票')
        next(t for t in app.text_input if t.label=='指定股票代码').set_value('600001')
        next(b for b in app.button if b.label=='生成每日候选').click().run(timeout=20)
        assert not app.exception
        assert app.session_state['m4_batch'].evaluations[0].analysis is None
        assert any('数据不足或校验失败' in e.value for e in app.error)
        assert not app.get('vega_lite_chart') and send.call_count==0
        next(s for s in app.selectbox if s.label=='M4 页面').set_value('指定股票分析').run(timeout=20)
        next(t for t in app.text_area if t.label=='自选股票（支持多个）').set_value('600000,600001,invalid')
        next(b for b in app.button if b.label=='分析指定股票').click().run(timeout=20)
        assert not app.exception
        watch=app.session_state['m4_watch_batch']
        assert len(watch.evaluations)==3 and not watch.candidates
        assert next(r for r in watch.evaluations if r.symbol=='600000.SH').analysis is not None
        assert next(r for r in watch.evaluations if r.symbol=='600001.SH').analysis is None
        for name in ['每日精选','风险与持仓监控','每日交易总览']:
            next(s for s in app.selectbox if s.label=='M4 页面').set_value(name).run(timeout=20)
            assert not app.exception
        assert next(m.value for m in app.metric if m.label=='新增多头仓位')=='未获准'
        assert send.call_count==0
    with db.connection() as c:
        assert c.execute('select count(*) from ingestion_runs').fetchone()[0]==1
print(json.dumps({'automatic_fetches':0,'candidate_count':0,'mode_difference':True,'shared_snapshot':True}))
'''
    result = subprocess.run([sys.executable, "-c", script], cwd=Path(__file__).resolve().parents[2],
                            capture_output=True, text=True, encoding="utf-8", timeout=65)
    assert result.returncode == 0, result.stdout+result.stderr

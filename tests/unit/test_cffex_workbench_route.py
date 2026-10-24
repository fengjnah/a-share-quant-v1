"""Offline UI routing over temporary SQLite only; never a real-source proof."""
from dataclasses import replace
import socket
import sqlite3

import pytest
from streamlit.testing.v1 import AppTest

from ai_trade.storage.db import Database, DatabaseConfig
from ai_trade.market_analysis_view import MODULES

_CONNECT = socket.socket.connect
_CONNECT_EX = socket.socket.connect_ex


@pytest.fixture(autouse=True)
def app_test_local_ipc(monkeypatch, forbid_network):
    # Windows asyncio's self-pipe needs loopback. External sockets remain
    # forbidden; no manual-integration flag or real source is enabled here.
    def local_only(original):
        def connect(sock, address):
            if isinstance(address, tuple) and address[0] in ('127.0.0.1', '::1'):
                return original(sock, address)
            raise AssertionError('CFFEX page tests forbid external network')
        return connect
    monkeypatch.setattr(socket.socket, 'connect', local_only(_CONNECT))
    monkeypatch.setattr(socket.socket, 'connect_ex', local_only(_CONNECT_EX))

def app_script(path, *, full_page=True):
    target = 'ai_trade.market_analysis_page import render' if full_page else 'ai_trade.market_analysis_cffex_page import render_cffex_holdings as render'
    return f'''
from pathlib import Path
from ai_trade.storage.db import Database, DatabaseConfig
from {target}
db = Database(DatabaseConfig(Path({str(path)!r}), environment='local', read_only=True, require_existing=True))
render(db)
'''


@pytest.mark.parametrize('mode', ['research', 'strict_backtest', 'paper_trade'])
def test_parent_routes_cffex_when_core_is_blocked_and_keeps_all_modules(database, monkeypatch, mode):
    import ai_trade.market_analysis_page as page
    import ai_trade.market_analysis_cffex_page as cffex
    visited, delegated = [], []
    original = page._values
    def values(name, diagnostic):
        visited.append(name)
        return original(name, diagnostic)
    def holdings(db=None):
        delegated.append(db)
    monkeypatch.setattr(page, '_values', values)
    monkeypatch.setattr(cffex, 'render_cffex_holdings', holdings)
    app = AppTest.from_string(app_script(database.config.path), default_timeout=20).run()
    if mode != 'research':
        visited.clear(); delegated.clear()
        next(x for x in app.selectbox if x.label == '时间可见性模式').set_value(mode).run()
    assert not app.exception
    assert visited == list(MODULES)
    assert len(delegated) == 1
    assert delegated[0].config.path == database.config.path
    assert delegated[0].config.read_only
    assert all(name in [h.value for h in app.subheader] for name in MODULES.values())
    assert any('BLOCKED' in x.value for x in app.markdown)


def test_formal_empty_store_is_read_only_and_never_falls_back_to_test_env(database, tmp_path, monkeypatch):
    import ai_trade.market_analysis_cffex_page as page
    monkeypatch.setenv('AI_TRADE_M3_TEST_DB_PATH', str(tmp_path / 'must-not-open.sqlite3'))
    def forbidden():
        raise AssertionError('workbench must not open test environment')
    monkeypatch.setattr(page, '_open_test_db', forbidden)
    before = database.config.path.read_bytes()
    app = AppTest.from_string(app_script(database.config.path, full_page=False), default_timeout=20).run()
    assert not app.exception and not app.error
    assert any(str(database.config.path) in x.value for x in app.info)
    assert any('No stored CFFEX report for IF on 2026-10-23' in x.value for x in app.info)
    assert database.config.path.read_bytes() == before
    assert not (tmp_path / 'must-not-open.sqlite3').exists()
    assert not any('never read or written' in x.value for x in app.caption)


def test_workbench_readback_exposes_quality_and_original_values(database, tmp_path):
    from m3_storage_fixtures import repo, DAY
    from test_m3_storage_market import report
    from ai_trade.market_analysis_cffex_db import cffex_report
    r = repo(database, tmp_path)
    calendars, payload, record, p, batch = report(r)
    vid = r.save_cffex(payload, record, p, batch=batch, calendar_version_ids=calendars)
    reader = Database(replace(database.config, read_only=True, require_existing=True))
    actual = cffex_report(reader, 'IF', DAY, evidence_root=tmp_path / 'evidence')
    assert actual['version_id'] == vid
    assert actual['quality_status'] == r.get_version(vid)[0]['quality_status']
    assert actual['evidence_kind'] == 'synthetic'
    assert actual['source'] == record.source and actual['trade_date'] == record.trade_date
    assert actual['row_count'] == len(record.rows)
    app = AppTest.from_string(app_script(database.config.path, full_page=False), default_timeout=20).run()
    assert not app.exception
    next(x for x in app.text_input if x.label == 'Trade date (YYYY-MM-DD)').set_value(DAY).run()
    assert not app.exception and not app.error
    text = '\n'.join(x.value for x in app.caption)
    assert 'accepted' in text and 'synthetic' in text and record.source in text
    shown = app.dataframe[0].value
    expected_long = sorted((x for x in actual['rows'] if x['side'] == 'long'), key=lambda x: x['rank'])
    assert shown.loc[shown['side'] == 'long', 'open_interest'].tolist() == [x['open_interest'] for x in expected_long]
    member = next(x['member'] for x in expected_long
        if any(y['side'] == 'short' and y['member'] == x['member'] for y in actual['rows']))
    next(x for x in app.text_input if x.label == 'Member (exact name from the table above)').set_value(member)
    next(x for x in app.selectbox if x.label == 'Net position contract').set_value(record.contracts[0]).run()
    long_oi = next(x['open_interest'] for x in expected_long if x['member'] == member)
    short_oi = next(x['open_interest'] for x in actual['rows'] if x['side'] == 'short' and x['member'] == member)
    assert next(x for x in app.metric if x.label == 'Net OI (long - short)').value == str(long_oi - short_oi)
    assert any(f'Long OI: {long_oi}' in x.value and f'Short OI: {short_oi}' in x.value for x in app.caption)


def test_readback_error_is_not_disguised_as_empty_data(database, monkeypatch):
    import ai_trade.market_analysis_cffex_page as page
    def corrupted(*args, **kwargs):
        raise ValueError('isolated evidence missing')
    monkeypatch.setattr(page, 'cffex_report', corrupted)
    app = AppTest.from_string(app_script(database.config.path, full_page=False), default_timeout=20).run()
    assert not app.exception
    assert any('Report readback failed: ValueError' in x.value for x in app.error)
    assert not any('No stored CFFEX report' in x.value for x in app.info)


def test_legacy_path_only_caller_fails_closed_without_crashing_or_creating_db(tmp_path, monkeypatch):
    import ai_trade.market_analysis_cffex_page as page
    def forbidden():
        raise AssertionError('invalid workbench binding must not select test data')
    monkeypatch.setattr(page, '_open_test_db', forbidden)
    missing = tmp_path / 'must-not-create.sqlite3'
    script = f'''
from pathlib import Path
from types import SimpleNamespace
from ai_trade.market_analysis_cffex_page import render_cffex_holdings
render_cffex_holdings(SimpleNamespace(config=SimpleNamespace(path=Path({str(missing)!r}))))
'''
    app = AppTest.from_string(script, default_timeout=20).run()
    assert not app.exception
    assert any('Workbench database binding invalid: TypeError' in x.value for x in app.error)
    assert not missing.exists()


def test_workbench_module_reopens_writable_handle_read_only(database, monkeypatch):
    import ai_trade.market_analysis_cffex_page as page
    from ai_trade.market_analysis_cffex_db import cffex_report
    observed = []
    def checked(db, *args, **kwargs):
        with db.connection() as c:
            observed.append((db.config.read_only, c.execute('PRAGMA query_only').fetchone()[0]))
            with pytest.raises(sqlite3.OperationalError, match='readonly|read-only'):
                c.execute("INSERT INTO ingestion_runs VALUES ('must-not-write', '2026-10-24T00:00:00+00:00')")
        return cffex_report(db, *args, **kwargs)
    monkeypatch.setattr(page, 'cffex_report', checked)
    script = app_script(database.config.path, full_page=False).replace('read_only=True', 'read_only=False')
    app = AppTest.from_string(script, default_timeout=20).run()
    assert not app.exception
    assert observed == [(True, 1)]

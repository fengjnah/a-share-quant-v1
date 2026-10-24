"""Local formal root, aliases and read-only failure paths; isolated stores only."""
from dataclasses import replace
import hashlib
import os
from pathlib import Path
import sqlite3

import pytest

from ai_trade.storage.db import Database, DatabaseConfig
from ai_trade.storage.workbench import data_root, is_workbench, workbench_config, workbench_root, inspect_database
from ai_trade.data_access.models import IntegrityError


@pytest.fixture
def formal(tmp_path, monkeypatch):
    monkeypatch.setattr('ai_trade.storage.workbench.tempfile.gettempdir', lambda: str(tmp_path/'other-temp'))
    root = tmp_path/'independent'
    db = Database(DatabaseConfig(root/'sqlite/workbench.sqlite3','test','DELETE'))
    db.initialize()
    return root, db


def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()


def test_new_root_is_single_source_and_never_depends_on_cwd(formal,tmp_path,monkeypatch):
    root, db = formal
    env = {'AI_TRADE_DATA_ROOT':str(root),'AI_TRADE_STRICT_WORKBENCH':'1'}
    assert is_workbench(env)
    for cwd in (tmp_path,root/'sqlite'):
        monkeypatch.chdir(cwd)
        config = DatabaseConfig.from_env(env)
        assert config == workbench_config(env) and config.path == db.config.path
        assert config.read_only and config.require_existing and config.journal_mode == 'DELETE'
    assert workbench_root(env) == root/'sqlite'
    assert workbench_config(env | {'AI_TRADE_WORKBENCH_ROOT':str(root/'sqlite'), 'QUANT_DB_PATH':str(db.config.path)}) == config


@pytest.mark.parametrize('change',[
    {'AI_TRADE_WORKBENCH_ROOT':'relative'}, {'AI_TRADE_WORKBENCH_ROOT':''},
    {'QUANT_DB_PATH':'relative'}, {'QUANT_DB_PATH':''}, {'QUANT_DB_ENV':'production'},
    {'AI_TRADE_READ_ONLY':'yes'},
])
def test_alias_and_profile_conflicts_do_not_choose_another_database(formal,change):
    root,db=formal; before=sha(db.config.path)
    with pytest.raises(ValueError): workbench_config({'AI_TRADE_DATA_ROOT':str(root)}|change)
    assert sha(db.config.path)==before


@pytest.mark.parametrize('key',['AI_TRADE_WORKBENCH_ROOT','QUANT_DB_PATH'])
def test_old_absolute_alias_cannot_override_new_root(formal,tmp_path,key):
    root,db=formal
    other=tmp_path/'old'/('workbench.sqlite3' if key=='QUANT_DB_PATH' else 'sqlite')
    with pytest.raises(ValueError,match='conflict'): workbench_config({'AI_TRADE_DATA_ROOT':str(root),key:str(other)})
    assert not other.exists()


@pytest.mark.parametrize('kind',['blank','relative','missing_root','missing_sqlite','missing_db'])
def test_missing_primary_never_falls_back_to_valid_legacy_or_creates(formal,tmp_path,kind):
    root,db=formal; candidate=tmp_path/'not-created'
    value={'blank':'','relative':'relative','missing_root':str(candidate),'missing_sqlite':str(tmp_path),'missing_db':str(root/'sqlite')}[kind]
    env={'AI_TRADE_DATA_ROOT':value,'AI_TRADE_WORKBENCH_ROOT':str(root/'sqlite')}
    assert is_workbench(env)
    before=sha(db.config.path)
    with pytest.raises((ValueError,FileNotFoundError)): workbench_config(env)
    assert not candidate.exists() and sha(db.config.path)==before


def test_default_readonly_cannot_initialize_or_write(formal):
    root,db=formal; before=sha(db.config.path)
    reader=Database(workbench_config({'AI_TRADE_DATA_ROOT':str(root)}))
    for _ in range(2):
        assert inspect_database(reader)['query_only']==1
        with pytest.raises(IntegrityError): reader.initialize()
        with pytest.raises(IntegrityError):
            with reader.transaction(): pass
        with reader.connection() as c, pytest.raises(sqlite3.OperationalError,match='readonly'):
            c.execute("INSERT INTO instruments VALUES ('not-written','600000.SH')")
    assert sha(db.config.path)==before


def test_strict_windows_requires_new_root_but_linux_explicit_interface_remains(formal,monkeypatch):
    root,db=formal; env={'AI_TRADE_WORKBENCH_ROOT':str(root/'sqlite'),'AI_TRADE_STRICT_WORKBENCH':'1'}
    monkeypatch.setattr('ai_trade.storage.workbench.sys.platform','win32')
    with pytest.raises(ValueError,match='AI_TRADE_DATA_ROOT'): workbench_config(env)
    monkeypatch.setattr('ai_trade.storage.workbench.sys.platform','linux')
    assert workbench_config(env).path==db.config.path


def test_data_root_inside_git_or_temp_is_rejected(tmp_path,monkeypatch):
    monkeypatch.setattr('ai_trade.storage.workbench.tempfile.gettempdir',lambda:str(tmp_path/'temp'))
    git=tmp_path/'repo'; git.mkdir(); (git/'.git').write_text('gitdir: fixture')
    with pytest.raises(ValueError,match='Git'): data_root(str(git/'data'),must_exist=False)
    with pytest.raises(ValueError,match='Temp'): data_root(str(tmp_path/'temp/data'),must_exist=False)


@pytest.mark.parametrize('where',['root','sqlite','database'])
def test_links_cannot_redirect_formal_data(formal,tmp_path,where):
    root,db=formal; alias=tmp_path/'alias'
    try:
        if where=='root': alias.symlink_to(root,target_is_directory=True)
        else:
            alias.mkdir()
            if where=='sqlite': (alias/'sqlite').symlink_to(root/'sqlite',target_is_directory=True)
            else:
                (alias/'sqlite').mkdir(); (alias/'sqlite/workbench.sqlite3').symlink_to(db.config.path)
    except OSError as e: pytest.skip('symlink privilege unavailable: '+str(e.winerror))
    with pytest.raises(ValueError): workbench_config({'AI_TRADE_DATA_ROOT':str(alias)})


def test_launcher_has_new_default_and_preserves_main_guard():
    script=(Path(__file__).resolve().parents[2]/'scripts/start_workbench.ps1').read_text(encoding='utf-8-sig')
    assert "'F:\\codex-agnes\\AI-trade-data'" in script
    assert 'AI-trade\\data\\sqlite' not in script
    assert '$env:AI_TRADE_DATA_ROOT = $DataRoot' in script
    assert "$ExpectedBranch = 'main'" in script and "$env:AI_TRADE_READ_ONLY = '1'" in script


@pytest.mark.skipif(os.name != 'nt', reason='Windows junction-specific check')
@pytest.mark.parametrize('where',['root','sqlite'])
def test_windows_junction_cannot_redirect_data_without_symlink_privilege(formal,tmp_path,where):
    from _winapi import CreateJunction
    root,db=formal; alias=tmp_path/'junction-alias'
    if where=='root': CreateJunction(str(root),str(alias))
    else:
        alias.mkdir(); CreateJunction(str(root/'sqlite'),str(alias/'sqlite'))
    with pytest.raises(ValueError,match='links'):
        workbench_config({'AI_TRADE_DATA_ROOT':str(alias)})

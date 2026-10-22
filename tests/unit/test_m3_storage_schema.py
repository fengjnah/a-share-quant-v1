"""Additive migrations and strict old/new prefix compatibility in temp stores."""
from dataclasses import replace
import hashlib
import sqlite3

import pytest

from ai_trade.data_access.models import IntegrityError
from ai_trade.data_access.repository import SQLiteMarketDataRepository
from ai_trade.storage.db import Database, DatabaseConfig
from ai_trade.storage.schema import MIGRATIONS
from ai_trade.storage.m3_schema import TABLES, GROUPS, FKS
from ai_trade.storage.workbench import inspect_database
from ai_trade.storage.workbench_cli import backup_new
from m3_storage_fixtures import repo, source, index, evidence, batch


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def test_released_checksums_and_exact_24_fields(database):
    assert [x.checksum for x in MIGRATIONS[:2]]==[
        'c6d31829bdef4ad9c6f45279c7696cfe94ac6acb9ff016c59320298b8e8dc0bd',
        'a4a5c6b2bbf2008d1f452610ecc3213de3dc4fbfe62daa0f55c161e36ef88125']
    assert len(TABLES)==24 and list(map(len,GROUPS))==[8,9,7]
    with database.connection() as c:
        assert len(c.execute("SELECT * FROM sqlite_master WHERE type='table'").fetchall())==31
        for name,table in TABLES.items():
            assert tuple(x['name'] for x in c.execute(f'PRAGMA table_info({name})'))==table.fields
            fk=list(c.execute(f'PRAGMA foreign_key_list({name})'))
            assert all(x['on_delete']=='RESTRICT' for x in fk)
            assert len(fk)==sum(len(fields.split(',')) for fields,_,_ in FKS.get(name,()))
        assert list(c.execute('PRAGMA foreign_key_check'))==[]


@pytest.mark.parametrize('version',[2,3,4,5])
def test_exact_readonly_prefix_never_upgrades(tmp_path,version):
    path=tmp_path/f'v{version}.sqlite3'
    writer=Database(DatabaseConfig(path,'test','DELETE')); writer.initialize(MIGRATIONS[:version])
    before=sha(path)
    reader=Database(replace(writer.config,read_only=True,require_existing=True))
    assert inspect_database(reader)['schema_version']==version
    with pytest.raises(IntegrityError,match='maintenance'): reader.initialize()
    assert sha(path)==before
    if version<5:
        with pytest.raises(ValueError,match='SCHEMA_CAPABILITY'): repo(reader,tmp_path).require(5)
    assert sha(path)==before


@pytest.mark.parametrize('damage',['future','gap','checksum','extra_table','missing_trigger','alter_column'])
def test_prefix_drift_refused_without_repair(tmp_path,damage):
    db=Database(DatabaseConfig(tmp_path/'drift.sqlite3','test','DELETE')); db.initialize(MIGRATIONS[:2])
    with db.connection() as c:
        if damage=='future': c.execute("INSERT INTO schema_migrations VALUES (9,'future','bad','now')")
        elif damage=='gap': c.execute('DELETE FROM schema_migrations WHERE version=1')
        elif damage=='checksum': c.execute("UPDATE schema_migrations SET checksum='bad' WHERE version=2")
        elif damage=='extra_table': c.execute('CREATE TABLE surprise(x)')
        elif damage=='missing_trigger':
            name=c.execute("SELECT name FROM sqlite_master WHERE type='trigger' LIMIT 1").fetchone()[0]; c.execute(f'DROP TRIGGER {name}')
        else: c.execute('ALTER TABLE instruments ADD COLUMN surprise TEXT')
    before=sha(db.config.path)
    with pytest.raises(IntegrityError): inspect_database(Database(replace(db.config,read_only=True)))
    assert sha(db.config.path)==before


@pytest.mark.parametrize('failure_version',[3,4,5])
def test_failed_upgrade_is_atomic_and_old_data_survives(tmp_path,bar,failure_version):
    db=Database(DatabaseConfig(tmp_path/'rollback.sqlite3','test','DELETE')); db.initialize(MIGRATIONS[:2])
    SQLiteMarketDataRepository(db).write_many([bar],run_id='legacy')
    old=inspect_database(db)
    broken=list(MIGRATIONS[:failure_version]); m=broken[-1]
    broken[-1]=replace(m,statements=m.statements+('INVALID SQL FOR ROLLBACK',))
    with pytest.raises(sqlite3.OperationalError): db.initialize(tuple(broken))
    after=inspect_database(db)
    for key in ('counts','migrations','objects','structure'): assert after[key]==old[key]
    assert db.initialize()==5
    assert inspect_database(db)['counts']['daily_bar_versions']==1
    with db.connection() as c: assert c.execute('SELECT close FROM daily_bar_versions').fetchone()[0]==bar.close


def test_v2_backup_restores_old_store_after_successful_upgrade(tmp_path,bar):
    db=Database(DatabaseConfig(tmp_path/'upgrade.sqlite3','test','DELETE')); db.initialize(MIGRATIONS[:2])
    SQLiteMarketDataRepository(db).write_many([bar],run_id='old')
    before=inspect_database(db)
    backup=tmp_path/'backup.sqlite3'; backup_new(Database(replace(db.config,read_only=True)),backup)
    assert db.initialize()==5 and db.initialize()==5
    recovered=tmp_path/'recovered.sqlite3'
    backup_new(Database(DatabaseConfig(backup,'test','DELETE',read_only=True)),recovered)
    state=inspect_database(Database(DatabaseConfig(recovered,'test','DELETE',read_only=True)))
    for key in ('counts','migrations','objects','structure'): assert state[key]==before[key]


@pytest.mark.parametrize('table',list(TABLES))
@pytest.mark.parametrize('operation',['UPDATE','DELETE'])
def test_audit_rows_are_immutable_even_direct_sql(database,table,operation):
    # Trigger existence/body matters even for currently empty tables. Populated
    # graph operations are exercised separately, not inferred from this check.
    with database.connection() as c:
        trigger=c.execute("SELECT sql FROM sqlite_master WHERE type='trigger' AND name=?",(f'm3_immutable_{table}_{operation.lower()}',)).fetchone()
        assert trigger and 'RAISE(ABORT' in trigger[0]


def test_sealed_version_cannot_append_or_update_and_wrong_fk_rolls_back(database,tmp_path):
    r=repo(database,tmp_path); _,ids,_,_=index(r)
    with database.transaction() as c:
        with pytest.raises(sqlite3.IntegrityError,match='immutable'):
            c.execute("UPDATE index_bar_versions SET close=101 WHERE data_version_id=?",(ids[0],))
        with pytest.raises(sqlite3.IntegrityError,match='sealed'):
            c.execute('INSERT INTO index_bar_versions SELECT * FROM index_bar_versions WHERE data_version_id=?',(ids[0],))
        with pytest.raises(sqlite3.IntegrityError,match='immutable'):
            c.execute('DELETE FROM data_versions WHERE data_version_id=?',(ids[0],))
    sid=source(r,'calendar')
    with pytest.raises(sqlite3.IntegrityError):
        with database.transaction() as c:
            c.execute("INSERT INTO legacy_version_links(data_version_id,calendar_version_id) VALUES (?,999)",('a'*64,))
    with database.connection() as c: assert c.execute('SELECT count(*) FROM legacy_version_links').fetchone()[0]==0

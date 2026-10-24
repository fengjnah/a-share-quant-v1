"""Real Backup API on synthetic temporary v2 DBs, never a formal path."""
import hashlib
from pathlib import Path
import sqlite3

import pytest

from ai_trade.data_access.repository import SQLiteMarketDataRepository
from ai_trade.storage.db import Database,DatabaseConfig
from ai_trade.storage import relocation as r


@pytest.fixture
def setup(tmp_path,monkeypatch,bar):
    monkeypatch.setattr('ai_trade.storage.workbench.tempfile.gettempdir',lambda:str(tmp_path/'other-temp'))
    source=Database(DatabaseConfig(tmp_path/'old/workbench.sqlite3','test','DELETE')); source.initialize()
    SQLiteMarketDataRepository(source).write_many([bar],run_id='synthetic-before-relocation')
    args=dict(source=source.config.path,root=tmp_path/'new-data',batch_id='fixture-001',
        expected_sha256=hashlib.sha256(source.config.path.read_bytes()).hexdigest(),
        review_ref='SYNTHETIC-OPERATOR-ACK-NOT-REAL-H-REVIEW',stopped=r.STOP_CONFIRMATION)
    return args,source


def test_nonempty_v2_backup_restore_relocate_and_explicit_rollback(setup):
    args,source=setup; before=source.config.path.read_bytes(); baseline=r.inventory(r.reader(source.config.path))
    result=r.relocate(**args)
    assert result['status']=='COPIED_VERIFIED_NOT_SWITCHED'
    assert result['baseline']==result['backup_inventory']==result['restore_inventory']==result['target_inventory']==baseline
    assert result['target_inventory']['counts']['daily_bar_versions']==1
    assert source.config.path.read_bytes()==before and not result['schema_upgraded'] and not result['configuration_switched']
    for folder in ('raw/market','raw/cffex','raw/evidence','exports'):
        assert (args['root']/folder).is_dir() and not list((args['root']/folder).iterdir())
    # Rollback is an explicit old-configuration read; neither DB is replaced.
    assert r.inventory(r.reader(args['source']))==baseline
    assert r.inventory(r.reader(Path(result['target'])))==baseline
    with pytest.raises(FileExistsError): r.relocate(**args)
    assert source.config.path.read_bytes()==before


@pytest.mark.parametrize('kind',['target','backup','restore','target_wal','backup_shm','restore_journal'])
def test_unknown_destination_or_sidecar_is_never_overwritten(setup,kind):
    args,source=setup; root=args['root']
    targets={'target':root/'sqlite/workbench.sqlite3','backup':root/'backups/fixture-001.sqlite3',
        'restore':root/'backups/fixture-001-restore/workbench.sqlite3'}
    key,_,side=kind.partition('_'); occupied=Path(str(targets[key])+('-'+side if side else ''))
    occupied.parent.mkdir(parents=True,exist_ok=True); occupied.write_bytes(b'unknown user evidence')
    before=source.config.path.read_bytes()
    with pytest.raises(FileExistsError): r.relocate(**args)
    assert occupied.read_bytes()==b'unknown user evidence' and source.config.path.read_bytes()==before


@pytest.mark.parametrize('field,value',[('stopped','yes'),('review_ref',''),('expected_sha256','f'*64),('batch_id','../escape')])
def test_missing_ack_wrong_identity_and_traversal_stop_before_creation(setup,field,value):
    args,_=setup
    with pytest.raises(ValueError): r.relocate(**(args|{field:value}))
    assert not args['root'].exists()


@pytest.mark.parametrize('suffix',['-wal','-shm','-journal'])
def test_source_sidecars_are_preserved_and_block_maintenance(setup,suffix):
    args,_=setup; side=Path(str(args['source'])+suffix); side.write_bytes(b'preserve me')
    with pytest.raises(ValueError,match='sidecar'): r.relocate(**args)
    assert side.read_bytes()==b'preserve me' and not args['root'].exists()


@pytest.mark.parametrize('failure_step',[1,2,3])
def test_failed_api_step_keeps_evidence_without_switching_or_cleaning(setup,monkeypatch,failure_step):
    args,source=setup; before=source.config.path.read_bytes(); real=r.backup_new; calls=[]
    def copy(origin,destination):
        calls.append(destination)
        if len(calls)==failure_step:
            destination.parent.mkdir(parents=True,exist_ok=True); destination.write_bytes(b'partial diagnostic evidence')
            raise OSError('synthetic interrupted backup')
        return real(origin,destination)
    monkeypatch.setattr(r,'backup_new',copy)
    with pytest.raises(OSError,match='interrupted'): r.relocate(**args)
    assert source.config.path.read_bytes()==before and calls[-1].read_bytes()==b'partial diagnostic evidence'
    if failure_step<3: assert not (args['root']/'sqlite/workbench.sqlite3').exists()


def test_detects_concurrent_source_change_without_creating_target(setup,monkeypatch):
    args,source=setup; real=r.backup_new
    def changing(origin,destination):
        result=real(origin,destination)
        with source.transaction() as c: c.execute("INSERT INTO instruments VALUES ('synthetic:late','600001.SH')")
        return result
    monkeypatch.setattr(r,'backup_new',changing)
    with pytest.raises(ValueError,match='source changed'): r.relocate(**args)
    assert (args['root']/'backups/fixture-001.sqlite3').exists()
    assert not (args['root']/'sqlite/workbench.sqlite3').exists()


def test_unversioned_or_drifted_source_cannot_be_adopted(setup):
    args,source=setup
    with source.connection() as c: c.execute('CREATE TABLE unknown_v3_candidate(x)')
    args['expected_sha256']=hashlib.sha256(source.config.path.read_bytes()).hexdigest()
    with pytest.raises(Exception): r.relocate(**args)
    assert not args['root'].exists()

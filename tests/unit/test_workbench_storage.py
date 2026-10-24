"""Strict store lifecycle and protection of existing data, all isolated/offline."""
import hashlib
import sqlite3
from dataclasses import replace
from pathlib import Path

import pytest

from ai_trade.data_access.models import IntegrityError
from ai_trade.data_access.repository import SQLiteMarketDataRepository
from ai_trade.storage.db import Database, DatabaseConfig
from ai_trade.storage.schema import MIGRATIONS
from ai_trade.storage.m3_schema import TABLES
from ai_trade.storage.workbench import inspect_database, workbench_config
from ai_trade.storage.workbench_cli import backup_new, initialize_new


@pytest.fixture
def store(tmp_path, monkeypatch):
    # Explicit isolated test store; production resolver still rejects OS Temp.
    monkeypatch.setattr("ai_trade.storage.workbench.tempfile.gettempdir", lambda: str(tmp_path / "other-temp"))
    root = tmp_path / "formal"
    backup = tmp_path / "backups" / "initial.sqlite3"
    restore = tmp_path / "restore" / "check.sqlite3"
    return root, backup, restore


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_initialization_backup_restore_and_repeat_refusal(store):
    root, backup, restore = store
    result = initialize_new(root, backup, restore)
    assert result["idempotence"]
    assert result["database"]["counts"] == {
        "schema_migrations": len(MIGRATIONS), "instruments": 0, "ingestion_runs": 0, "daily_bars": 0,
        "daily_bar_versions": 0, "security_versions": 0, "calendar_versions": 0,
        **dict.fromkeys(TABLES,0)}
    before = {p: digest(p) for p in (root / "workbench.sqlite3", backup, restore)}
    with pytest.raises(FileExistsError):
        initialize_new(root, backup.with_name("unused.sqlite3"), restore.with_name("unused.sqlite3"))
    assert before == {p: digest(p) for p in before}


def test_ordinary_open_and_repository_cannot_write_or_initialize(store, bar):
    root, backup, restore = store
    initialize_new(root, backup, restore)
    env = {"AI_TRADE_WORKBENCH_ROOT": str(root)}
    db = Database(DatabaseConfig.from_env(env))
    before = digest(db.config.path)
    assert db.config == workbench_config(env)
    for _ in range(2):
        result = inspect_database(db)
        assert Path(result["connected_path"]).resolve() == db.config.path
        assert result["query_only"] == 1 and result["read_only"]
        with db.connection() as conn, pytest.raises(sqlite3.OperationalError, match="readonly"):
            conn.execute("INSERT INTO instruments VALUES ('no', '600000.SH')")
        with pytest.raises(IntegrityError, match="read-only"):
            SQLiteMarketDataRepository(db).write_many([bar], run_id="forbidden")
        with pytest.raises(IntegrityError, match="maintenance"):
            db.initialize()
    assert digest(db.config.path) == before
    assert not list(root.glob("*-*"))


@pytest.mark.parametrize("kind", ["missing", "directory", "sidecar"])
def test_init_refuses_protected_paths_before_any_creation(store, kind):
    root, backup, restore = store
    if kind == "missing":
        root.mkdir()
        with pytest.raises(ValueError, match="existing regular"):
            workbench_config({"AI_TRADE_WORKBENCH_ROOT": str(root)})
        assert not (root / "workbench.sqlite3").exists()
        return
    root.mkdir()
    target = root / "workbench.sqlite3"
    if kind == "directory":
        target.mkdir()
    else:
        Path(str(target) + "-wal").write_bytes(b"protected")
    with pytest.raises(FileExistsError):
        initialize_new(root, backup, restore)
    assert not backup.exists() and not restore.exists()


@pytest.mark.parametrize("env", [
    {}, {"AI_TRADE_WORKBENCH_ROOT": ""}, {"AI_TRADE_WORKBENCH_ROOT": "relative"},
])
def test_strict_configuration_never_chooses_demo(env):
    with pytest.raises(ValueError, match="absolute"):
        workbench_config(env)
    with pytest.raises(ValueError):
        DatabaseConfig.from_env(dict(env, AI_TRADE_STRICT_WORKBENCH="1"))


def test_configuration_conflicts_and_explicit_writer(store):
    root, backup, restore = store
    initialize_new(root, backup, restore)
    env = {"AI_TRADE_WORKBENCH_ROOT": str(root)}
    for change in ({"QUANT_DB_PATH": str(root / "other.sqlite3")}, {"QUANT_DB_PATH": ""},
                   {"QUANT_DB_ENV": "production"}, {"AI_TRADE_READ_ONLY": "yes"}):
        with pytest.raises(ValueError):
            workbench_config(env | change)
    config = workbench_config(env | {"AI_TRADE_READ_ONLY": "0"})
    assert not config.read_only and config.require_existing
    writer = Database(config)
    with writer.transaction() as conn:
        conn.execute("INSERT INTO instruments VALUES ('explicit', '600000.SH')")
    assert inspect_database(Database(replace(config, read_only=True)))["counts"]["instruments"] == 1


@pytest.mark.parametrize("damage", ["checksum", "trigger", "table", "corrupt", "v1"])
def test_schema_or_corruption_stops_without_repair(store, damage):
    root, backup, restore = store
    initialize_new(root, backup, restore)
    path = root / "workbench.sqlite3"
    if damage == "corrupt":
        path.write_bytes(b"explicit synthetic corruption")
    else:
        conn = sqlite3.connect(path)
        try:
            if damage == "checksum":
                conn.execute("UPDATE schema_migrations SET checksum='invalid' WHERE version=2")
            elif damage == "v1":
                conn.execute("DELETE FROM schema_migrations WHERE version=2")
            elif damage == "trigger":
                name = conn.execute("SELECT name FROM sqlite_master WHERE type='trigger' LIMIT 1").fetchone()[0]
                conn.execute(f'DROP TRIGGER "{name}"')
            else:
                conn.execute("ALTER TABLE instruments ADD COLUMN unintended TEXT")
            conn.commit()
        finally:
            conn.close()
    before = digest(path)
    db = Database(workbench_config({"AI_TRADE_WORKBENCH_ROOT": str(root)}))
    with pytest.raises((IntegrityError, sqlite3.DatabaseError)):
        inspect_database(db)
    assert digest(path) == before


def test_missing_file_after_config_does_not_recreate(store):
    root, backup, restore = store
    initialize_new(root, backup, restore)
    config = workbench_config({"AI_TRADE_WORKBENCH_ROOT": str(root)})
    config.path.rename(root / "preserved.sqlite3")
    for readonly in (True, False):
        with pytest.raises(sqlite3.OperationalError):
            with Database(replace(config, read_only=readonly)).connection():
                pass
    assert not config.path.exists()


def test_backup_refuses_existing_destination_and_preserves_source(store):
    root, backup, restore = store
    initialize_new(root, backup, restore)
    db = Database(workbench_config({"AI_TRADE_WORKBENCH_ROOT": str(root)}))
    before = digest(backup)
    with pytest.raises(FileExistsError):
        backup_new(db, backup)
    assert digest(backup) == before


def test_existing_wrong_journal_is_not_switched(store):
    root, backup, restore = store
    initialize_new(root, backup, restore)
    path = root / "workbench.sqlite3"
    with sqlite3.connect(path) as conn:
        assert conn.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
    config = workbench_config({"AI_TRADE_WORKBENCH_ROOT": str(root)})
    with pytest.raises(IntegrityError, match="journal"):
        inspect_database(Database(config))
    with sqlite3.connect(path) as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"


def test_backup_restore_preserves_nonempty_versions_and_times(store, bar):
    root, backup, restore = store
    initialize_new(root, backup, restore)
    config = workbench_config({"AI_TRADE_WORKBENCH_ROOT": str(root), "AI_TRADE_READ_ONLY": "0"})
    writer = Database(config)
    SQLiteMarketDataRepository(writer).write_many([bar], run_id="synthetic-backup-test")
    readonly = Database(replace(config, read_only=True))
    second = backup.with_name("nonempty.sqlite3")
    recovered = restore.with_name("nonempty.sqlite3")
    backup_new(readonly, second)
    backup_new(Database(DatabaseConfig(second, journal_mode="DELETE", read_only=True)), recovered)
    with readonly.connection() as source:
        for path in (second, recovered):
            with Database(DatabaseConfig(path, journal_mode="DELETE", read_only=True)).connection() as other:
                for table in inspect_database(readonly)["counts"]:
                    assert [tuple(r) for r in source.execute(f'SELECT * FROM "{table}"')] == [
                        tuple(r) for r in other.execute(f'SELECT * FROM "{table}"')]

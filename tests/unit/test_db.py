"""Lifecycle, schema migration and SQL-level integrity behavior."""

import sqlite3
import subprocess
import sys
from dataclasses import replace

import pytest

from ai_trade.data_access.models import IntegrityError
from ai_trade.storage.db import Database, DatabaseConfig
from ai_trade.storage.schema import MIGRATIONS, Migration


def test_first_initialization_and_ledger(tmp_path):
    db = Database(DatabaseConfig(tmp_path / "nested" / "test.sqlite3", "test"))
    assert db.initialize() == len(MIGRATIONS)
    with db.connection() as conn:
        ledger = conn.execute("SELECT * FROM schema_migrations").fetchone()
        assert ledger["version"] == 1
        assert ledger["checksum"] == MIGRATIONS[0].checksum
        assert ledger["applied_at"].endswith("+00:00")
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA recursive_triggers").fetchone()[0] == 1
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
        assert conn.execute("PRAGMA synchronous").fetchone()[0] == 2
        assert conn.execute("PRAGMA busy_timeout").fetchone()[0] == 5000


def test_repeated_initialization_preserves_data(database, repository, bar, query):
    repository.write_many([bar], run_id="first")
    before = query()
    assert database.initialize() == database.initialize() == len(MIGRATIONS)
    assert query() == before
    with database.connection() as conn:
        assert conn.execute("SELECT count(*) FROM schema_migrations").fetchone()[0] == len(MIGRATIONS)


@pytest.mark.parametrize("raises", [False, True])
def test_connection_closed_on_both_paths(database, raises):
    conn = None
    try:
        with database.connection() as conn:
            if raises:
                raise RuntimeError("synthetic failure")
    except RuntimeError:
        assert raises
    with pytest.raises(sqlite3.ProgrammingError, match="closed"):
        conn.execute("SELECT 1")
    renamed = database.config.path.with_suffix(".closed.sqlite3")
    database.config.path.rename(renamed)
    assert renamed.is_file()


def test_transaction_commit_and_exception_rollback(database):
    with database.transaction() as conn:
        conn.execute("INSERT INTO instruments VALUES ('one', '600001.SH')")
    with pytest.raises(RuntimeError):
        with database.transaction() as conn:
            conn.execute("INSERT INTO instruments VALUES ('two', '600002.SH')")
            raise RuntimeError("rollback")
    with database.connection() as conn:
        assert [r[0] for r in conn.execute("SELECT instrument_id FROM instruments")] == ["one"]


def test_interrupt_rolls_back_and_closes(database):
    with pytest.raises(KeyboardInterrupt):
        with database.transaction() as conn:
            conn.execute("INSERT INTO instruments VALUES ('one', '600001.SH')")
            raise KeyboardInterrupt()
    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1")
    with database.connection() as other:
        assert other.execute("SELECT count(*) FROM instruments").fetchone()[0] == 0


def test_foreign_keys_enforced(database):
    with pytest.raises(sqlite3.IntegrityError, match="FOREIGN KEY"):
        with database.transaction() as conn:
            conn.execute("""INSERT INTO daily_bars (instrument_id, trade_date, adjustment_method)
                VALUES ('missing', '2026-10-16', 'none')""")


def test_second_migration_is_repeatable(database):
    registry = MIGRATIONS + (Migration(len(MIGRATIONS)+1, "test_extension", ("CREATE TABLE extension (id INTEGER)",)),)
    assert database.initialize(registry) == len(registry)
    with database.transaction() as conn:
        conn.execute("INSERT INTO extension VALUES (42)")
    assert database.initialize(registry) == len(registry)
    with database.connection() as conn:
        assert conn.execute("SELECT id FROM extension").fetchone()[0] == 42


def test_failed_migration_rolls_back_ddl_and_version(database):
    registry = MIGRATIONS + (Migration(len(MIGRATIONS)+1, "broken", (
        "CREATE TABLE half_created (id INTEGER)", "INSERT INTO nonexistent VALUES (1)")),)
    with pytest.raises(sqlite3.OperationalError):
        database.initialize(registry)
    with database.connection() as conn:
        assert conn.execute("SELECT max(version) FROM schema_migrations").fetchone()[0] == len(MIGRATIONS)
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE name='half_created'").fetchone() is None
    assert database.initialize() == len(MIGRATIONS)


def test_first_migration_failure_is_atomic(tmp_path):
    db = Database(DatabaseConfig(tmp_path / "broken.sqlite3", "test"))
    with pytest.raises(sqlite3.OperationalError):
        db.initialize((Migration(1, "broken", ("CREATE TABLE half_created (id INTEGER)", "INVALID SQL")),))
    with db.connection() as conn:
        assert conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall() == []
    assert db.initialize() == len(MIGRATIONS)


def test_checksum_drift_rejected(database):
    changed = (replace(MIGRATIONS[0], name="rewritten_history"),) + MIGRATIONS[1:]
    with pytest.raises(IntegrityError, match="checksum drift"):
        database.initialize(changed)


def test_future_schema_rejected(database):
    database.initialize(MIGRATIONS + (Migration(len(MIGRATIONS)+1, "extension", ("CREATE TABLE extra (id INTEGER)",)),))
    with pytest.raises(IntegrityError, match="newer"):
        database.initialize()


def test_history_gap_rejected(database):
    with database.transaction() as conn:
        conn.execute("UPDATE schema_migrations SET version=? WHERE version=?", (len(MIGRATIONS)+1, len(MIGRATIONS)))
    with pytest.raises(IntegrityError, match="gap"):
        database.initialize()


def test_registry_gap_rejected(database):
    with pytest.raises(IntegrityError, match="contiguous"):
        database.initialize((Migration(2, "gap", ()),))


def test_unversioned_database_not_adopted(tmp_path):
    db = Database(DatabaseConfig(tmp_path / "existing.sqlite3", "test"))
    with db.connection() as conn:
        conn.execute("CREATE TABLE existing (id INTEGER)")
    with pytest.raises(IntegrityError, match="unversioned"):
        db.initialize()
    with db.connection() as conn:
        assert [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")] == ["existing"]


def test_delete_journal_option(tmp_path):
    db = Database(DatabaseConfig(tmp_path / "delete.sqlite3", "test", journal_mode="DELETE"))
    db.initialize()
    with db.connection() as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"


def test_config_environments_are_explicit(tmp_path):
    local = DatabaseConfig.from_env({})
    assert local.environment == "local"
    with pytest.raises(ValueError, match="explicit"):
        DatabaseConfig.from_env({"QUANT_DB_ENV": "production"})
    with pytest.raises(ValueError, match="explicit"):
        DatabaseConfig.from_env({"QUANT_DB_ENV": "test"})
    production = DatabaseConfig.from_env({"QUANT_DB_ENV": "production", "QUANT_DB_PATH": str(tmp_path / "prod.sqlite3")})
    assert production.path != local.path
    assert not production.path.exists()


@pytest.mark.parametrize("overrides", [
    {"environment": "staging"}, {"journal_mode": "TRUNCATE"},
    {"busy_timeout_ms": -1}, {"busy_timeout_ms": True}, {"busy_timeout_ms": 2**31},
])
def test_invalid_configuration_rejected(tmp_path, overrides):
    with pytest.raises(ValueError):
        DatabaseConfig(tmp_path / "test.sqlite3", **overrides)


def test_blank_env_path_rejected():
    with pytest.raises(ValueError, match="blank"):
        DatabaseConfig.from_env({"QUANT_DB_PATH": " "})


def test_test_databases_are_isolated(tmp_path):
    first = Database(DatabaseConfig(tmp_path / "first.sqlite3", "test"))
    second = Database(DatabaseConfig(tmp_path / "second.sqlite3", "test"))
    first.initialize()
    second.initialize()
    with first.transaction() as conn:
        conn.execute("INSERT INTO instruments VALUES ('one', '600001.SH')")
    with second.connection() as conn:
        assert conn.execute("SELECT count(*) FROM instruments").fetchone()[0] == 0


def test_initialization_cli_from_another_directory(tmp_path, monkeypatch):
    path = tmp_path / "cli" / "test.sqlite3"
    monkeypatch.setenv("QUANT_DB_ENV", "test")
    monkeypatch.setenv("QUANT_DB_PATH", str(path))
    monkeypatch.setenv("QUANT_DB_JOURNAL", "WAL")
    for _ in range(2):
        result = subprocess.run([sys.executable, "-m", "ai_trade.storage"],
                                cwd=tmp_path, capture_output=True, text=True, check=True)
        assert f"schema version {len(MIGRATIONS)}" in result.stdout
    assert path.is_file()


@pytest.mark.parametrize("table", ["instruments", "ingestion_runs", "daily_bars", "daily_bar_versions"])
@pytest.mark.parametrize("operation", ["UPDATE", "DELETE"])
def test_audit_data_is_append_only(database, repository, bar, table, operation):
    repository.write_many([bar], run_id="initial")
    statement = f"DELETE FROM {table}" if operation == "DELETE" else f"UPDATE {table} SET rowid=rowid"
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        with database.transaction() as conn:
            conn.execute(statement)


def test_replace_cannot_bypass_immutable_history(database, repository, bar):
    repository.write_many([bar], run_id="first")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        with database.transaction() as conn:
            conn.execute("INSERT OR REPLACE INTO instruments VALUES (?, ?)", (bar.instrument_id, "600001.SH"))
    with database.connection() as conn:
        assert conn.execute("SELECT symbol FROM instruments").fetchone()[0] == bar.symbol

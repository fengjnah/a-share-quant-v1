"""Deployment backups must preserve WAL data and detect same-count mutations."""
import sqlite3
import pytest

from ai_trade.workbench_store import backup, check_schema, database_inventory, initialize_empty, inventory


def test_online_backup_includes_wal_and_does_not_overwrite_source(tmp_path):
    source = tmp_path / "workbench.sqlite3"
    with sqlite3.connect(source) as connection:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("CREATE TABLE facts(id INTEGER PRIMARY KEY, value TEXT)")
        connection.execute("INSERT INTO facts VALUES (1, 'before')")
        connection.commit()
        saved = backup(tmp_path)
        assert saved is not None and saved != source
        assert database_inventory(saved) == database_inventory(source)
        connection.execute("UPDATE facts SET value='after' WHERE id=1")
        connection.commit()
        assert database_inventory(saved) != database_inventory(source)
        second = backup(tmp_path)
        assert second != saved and saved.is_file()
        assert database_inventory(second) == database_inventory(source)


def test_inventory_detects_changed_values_without_row_count_change(tmp_path):
    source = tmp_path / "workbench.sqlite3"
    with sqlite3.connect(source) as c:
        c.execute("CREATE TABLE facts(value TEXT)")
        c.execute("INSERT INTO facts VALUES ('old')")
    first = inventory(tmp_path)
    with sqlite3.connect(source) as c:
        c.execute("UPDATE facts SET value='new'")
    second = inventory(tmp_path)
    assert first["database"]["facts"]["rows"] == second["database"]["facts"]["rows"] == 1
    assert first != second


def test_empty_bootstrap_refuses_to_adopt_or_rebuild_existing_data(tmp_path):
    initialize_empty(tmp_path)
    check_schema(tmp_path)
    before = inventory(tmp_path)
    with pytest.raises(ValueError, match="empty"):
        initialize_empty(tmp_path)
    assert inventory(tmp_path) == before
    with sqlite3.connect(tmp_path / "workbench.sqlite3") as c:
        c.execute("CREATE TABLE unrelated(value INTEGER)")
    with sqlite3.connect(tmp_path / "workbench.sqlite3") as c:
        c.execute("UPDATE schema_migrations SET checksum='different' WHERE version=1")
    with pytest.raises(ValueError, match="schema"):
        check_schema(tmp_path)


def test_missing_database_is_not_fabricated_by_backup(tmp_path):
    assert backup(tmp_path) is None
    assert inventory(tmp_path) == {"database": None, "observations": {}}


def test_observation_mutation_is_visible_and_backups_are_outside_inventory(tmp_path):
    observations = tmp_path / "m3-observations"
    observations.mkdir()
    sample = observations / "sample.json"
    sample.write_text('{"source":"synthetic"}', encoding="utf-8")
    first = inventory(tmp_path)
    sample.write_text('{"source":"changed"}', encoding="utf-8")
    assert inventory(tmp_path) != first

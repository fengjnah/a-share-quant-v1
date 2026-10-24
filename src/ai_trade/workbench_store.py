"""Deployment-only SQLite snapshots and content checks; never migrates an existing store."""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import uuid


def _connect(path: Path):
    return sqlite3.connect(path.resolve().as_uri()+"?mode=ro", uri=True, timeout=10)


def _quote(name: str) -> str:
    return '"'+name.replace('"', '""')+'"'


def _json(value):
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"),
                      default=lambda v: {"bytes": v.hex()} if isinstance(v, bytes) else str(v)).encode()


def database_inventory(path: Path) -> dict:
    with closing(_connect(path)) as connection:
        connection.execute("BEGIN")
        if connection.execute("PRAGMA quick_check").fetchall() != [("ok",)]:
            raise ValueError("SQLite quick_check failed")
        tables = connection.execute("SELECT name,sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
        result = {}
        for name, schema in tables:
            cols = [r[1] for r in connection.execute(f"PRAGMA table_info({_quote(name)})")]
            digest = hashlib.sha256(_json([schema, cols]))
            count = 0
            for row in connection.execute(f"SELECT * FROM {_quote(name)} ORDER BY "+",".join(_quote(c) for c in cols)):
                digest.update(_json(row)+b"\n")
                count += 1
            result[name] = {"rows": count, "sha256": digest.hexdigest()}
        return result


def inventory(root: Path) -> dict:
    root = root.resolve(strict=True)
    database = root / "workbench.sqlite3"
    if database.is_symlink():
        raise ValueError("database must not be a symlink")
    observations = {}
    for path in sorted((root / "m3-observations").glob("*.json")):
        if path.is_symlink() or path.resolve().parent != root / "m3-observations":
            raise ValueError("observation link outside store")
        observations[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"database": database_inventory(database) if database.exists() else None, "observations": observations}


def backup(root: Path) -> Path | None:
    root = root.resolve(strict=True)
    original = root / "workbench.sqlite3"
    if not original.exists():
        return None
    if original.is_symlink():
        raise ValueError("database must not be a symlink")
    directory = root / "backups"
    directory.mkdir(mode=0o700, exist_ok=True)
    if directory.is_symlink() or directory.resolve().parent != root:
        raise ValueError("backup directory must stay inside dedicated store")
    name = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")+"-"+uuid.uuid4().hex[:12]+".sqlite3"
    target = directory / name
    descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.close(descriptor)
    # Online backup includes committed WAL content; a filesystem copy of only the main file does not.
    with closing(_connect(original)) as source, closing(sqlite3.connect(target)) as destination:
        source.backup(destination, pages=256, sleep=.05)
    database_inventory(target)  # refuse a corrupt backup before switching any release
    return target


def check_schema(root: Path) -> None:
    from ai_trade.storage.schema import MIGRATIONS
    with closing(_connect(root / "workbench.sqlite3")) as connection:
        actual = connection.execute("SELECT version,name,checksum FROM schema_migrations ORDER BY version").fetchall()
    expected = [(m.version, m.name, m.checksum) for m in MIGRATIONS]
    if actual != expected:
        raise ValueError("deployment would migrate or adopt a different schema; explicit database approval required")


def initialize_empty(root: Path) -> None:
    from ai_trade.storage.db import Database, DatabaseConfig
    root = root.resolve(strict=True)
    if any(root.iterdir()):
        raise ValueError("bootstrap accepts only a new empty dedicated store")
    Database(DatabaseConfig(root / "workbench.sqlite3", environment="local", journal_mode="DELETE")).initialize()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("inventory", "backup", "check-schema", "initialize-empty"))
    parser.add_argument("root", type=Path)
    args = parser.parse_args()
    if args.action == "inventory":
        print(json.dumps(inventory(args.root), sort_keys=True))
    elif args.action == "backup":
        result = backup(args.root)
        print(str(result) if result else "NO_EXISTING_DATABASE")
    elif args.action == "check-schema":
        check_schema(args.root)
    else:
        initialize_empty(args.root)

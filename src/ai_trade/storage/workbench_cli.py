"""Explicit create-only initialization and SQLite API backup/isolated restore."""

import argparse
import hashlib
import json
import sqlite3
import subprocess
import time
from dataclasses import replace
from pathlib import Path

from ai_trade.storage.db import Database, DatabaseConfig
from ai_trade.storage.workbench import inspect_database, persistent_root, workbench_config


def file_state(path: Path) -> list[dict]:
    result = []
    for candidate in (path, *(Path(str(path) + suffix) for suffix in ("-wal", "-shm", "-journal"))):
        entry = {"path": str(candidate), "exists": candidate.exists() or candidate.is_symlink()}
        if candidate.is_file():
            with candidate.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            entry.update(bytes=candidate.stat().st_size, sha256=digest)
        result.append(entry)
    return result


def ensure_absent(path: Path) -> None:
    if any(item["exists"] for item in file_state(path)):
        raise FileExistsError(f"refusing existing database/directory/sidecar: {path}")


def reserve(path: Path) -> None:
    ensure_absent(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb"):
        pass


def backup_new(source: Database, destination: Path) -> dict:
    """Creates only a new destination; never overwrites an existing backup."""
    reserve(destination)
    started = time.monotonic()

    def progress(status, remaining, total):
        if status not in (sqlite3.SQLITE_OK, sqlite3.SQLITE_DONE) or time.monotonic() - started > 30:
            raise TimeoutError("bounded backup failed; partial destination retained for diagnosis")

    with source.connection() as src:
        dest = sqlite3.connect(destination)
        try:
            src.backup(dest, pages=64, progress=progress, sleep=0.1)
        finally:
            dest.close()
    return inspect_database(Database(DatabaseConfig(destination, journal_mode="DELETE", read_only=True)))


def initialize_new(root: Path, backup: Path, restored: Path) -> dict:
    root = persistent_root(str(root), must_exist=False)
    path = root / "workbench.sqlite3"
    targets = (path, backup, restored)
    if len({p.resolve() for p in targets}) != 3 or any(not p.is_absolute() for p in targets):
        raise ValueError("database, backup and isolated restore require distinct absolute paths")
    if backup.resolve().is_relative_to(root) or restored.resolve().is_relative_to(root):
        raise ValueError("backup and restore must be outside the formal store")
    for target in targets:
        ensure_absent(target)
    before = {str(p): file_state(p) for p in targets}
    reserve(path)
    db = Database(DatabaseConfig(path, journal_mode="DELETE"))
    db.initialize()
    first = inspect_database(db)
    db.initialize()  # Explicit init operation only: verify idempotence, not page refresh.
    if inspect_database(db) != first:
        raise RuntimeError("initialization was not idempotent")
    readonly = Database(replace(db.config, read_only=True, require_existing=True))
    copied = backup_new(readonly, backup)
    recovered = backup_new(Database(DatabaseConfig(backup, journal_mode="DELETE", read_only=True)), restored)
    for candidate in (copied, recovered):
        for key in ("counts", "migrations", "objects", "structure", "quick_check", "foreign_key_check"):
            if candidate[key] != first[key]:
                raise RuntimeError(f"backup/restore verification differs: {key}")
    return {"before": before, "database": inspect_database(readonly), "backup": copied,
            "isolated_restore": recovered, "idempotence": True,
            "after": {str(p): file_state(p) for p in targets}}


def code_identity() -> dict:
    root = Path(__file__).resolve().parents[3]
    def git(*args):
        return subprocess.check_output(["git", "-C", str(root), *args], text=True).strip()
    return {"code_root": str(root), "code_sha": git("rev-parse", "HEAD"),
            "code_dirty": bool(git("status", "--porcelain"))}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("initialize-new", "diagnose"))
    parser.add_argument("--root", required=True)
    parser.add_argument("--backup")
    parser.add_argument("--restore")
    parser.add_argument("--report")
    args = parser.parse_args()
    if args.report and Path(args.report).exists():
        parser.error("report already exists; use a new evidence filename")
    if args.action == "initialize-new":
        if not args.backup or not args.restore:
            parser.error("initialize-new requires --backup and --restore")
        result = initialize_new(Path(args.root), Path(args.backup), Path(args.restore))
    else:
        import os
        env = dict(os.environ, AI_TRADE_WORKBENCH_ROOT=args.root)
        result = inspect_database(Database(workbench_config(env)))
    result.update(code_identity())
    output = json.dumps(result, ensure_ascii=False, indent=2)
    if args.report:
        report = Path(args.report)
        report.parent.mkdir(parents=True, exist_ok=True)
        with report.open("x", encoding="utf-8") as stream:
            stream.write(output + "\n")
    print(output)


if __name__ == "__main__":
    main()

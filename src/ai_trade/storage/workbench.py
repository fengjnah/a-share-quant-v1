"""Strict existing-store binding and read-only schema diagnostics; no migrations."""

import os
import sqlite3
import sys
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Mapping

from ai_trade.data_access.models import IntegrityError
from ai_trade.storage.db import Database, DatabaseConfig
from ai_trade.storage.schema import LEDGER_SQL, MIGRATIONS


def persistent_root(value: str, *, must_exist: bool = True) -> Path:
    configured = Path(value).expanduser()
    if not configured.is_absolute():
        raise ValueError("工作台持久目录必须使用绝对路径")
    root = configured.resolve(strict=must_exist)
    repository = Path(__file__).resolve().parents[3]
    temp = Path(tempfile.gettempdir()).resolve()
    if ((must_exist and not root.is_dir()) or root.is_relative_to(temp)
            or (root.is_relative_to(repository) and root != repository / "data" / "sqlite")):
        raise ValueError("持久目录须在临时目录之外；仓库内仅允许专用 data/sqlite")
    if (root / "demo.sqlite3").exists():
        raise ValueError("不能将开发临时演示数据库作为正式存储")
    if (root / "workbench.sqlite3").resolve().parent != root:
        raise ValueError("工作台数据库链接不能越出持久目录")
    return root


def is_workbench(environ: Mapping[str, str] | None = None) -> bool:
    env = os.environ if environ is None else environ
    return ("AI_TRADE_DATA_ROOT" in env or "AI_TRADE_WORKBENCH_ROOT" in env
            or env.get("AI_TRADE_STRICT_WORKBENCH") == "1")


def data_root(value: str, *, must_exist: bool = True) -> Path:
    """Formal local data lives outside every Git checkout and OS Temp.

    This function validates only. Even a missing root is never created here.
    """
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError("AI_TRADE_DATA_ROOT requires an absolute data directory")
    configured = Path(value).expanduser()
    if not configured.is_absolute():
        raise ValueError("AI_TRADE_DATA_ROOT requires an absolute data directory")
    absolute = configured.absolute()
    resolved = configured.resolve(strict=must_exist)
    if absolute != resolved or configured.is_symlink():
        raise ValueError("data directory links/ambiguous paths are forbidden")
    if (((must_exist or resolved.exists()) and not resolved.is_dir()) or resolved.is_relative_to(Path(tempfile.gettempdir()).resolve())
            or any((p / ".git").exists() for p in (resolved, *resolved.parents))):
        raise ValueError("data directory must be outside Git and Temp")
    return resolved


def workbench_root(environ: Mapping[str, str] | None = None) -> Path:
    env = os.environ if environ is None else environ
    if "AI_TRADE_DATA_ROOT" in env:
        sqlite_root = data_root(env["AI_TRADE_DATA_ROOT"]) / "sqlite"
        if sqlite_root.is_symlink() or sqlite_root.resolve() != sqlite_root:
            raise ValueError("sqlite directory links outside data root are forbidden")
        root = persistent_root(str(sqlite_root))
        if "AI_TRADE_WORKBENCH_ROOT" in env:
            alias = env["AI_TRADE_WORKBENCH_ROOT"]
            if not alias.strip() or not Path(alias).is_absolute() or Path(alias).resolve() != root:
                raise ValueError("AI_TRADE_WORKBENCH_ROOT conflicts with AI_TRADE_DATA_ROOT/sqlite")
        return root
    # Preserve the explicit Linux deployment interface. The local strict
    # Windows entry point must opt in to the independent data root, never fall
    # back to a previously inherited checkout-owned database.
    if sys.platform == "win32" and env.get("AI_TRADE_STRICT_WORKBENCH") == "1":
        raise ValueError("正式工作台未配置 AI_TRADE_DATA_ROOT；停止，不回退临时库或旧库")
    raw = env.get("AI_TRADE_WORKBENCH_ROOT", "")
    if not raw.strip() or not Path(raw).is_absolute():
        raise ValueError("formal workbench requires absolute AI_TRADE_WORKBENCH_ROOT")
    return persistent_root(raw)


def workbench_config(environ: Mapping[str, str] | None = None) -> DatabaseConfig:
    env = os.environ if environ is None else environ
    root = workbench_root(env)
    path = root / "workbench.sqlite3"
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"existing regular workbench database required: {path}")
    if env.get("QUANT_DB_ENV", "local") != "local":
        raise ValueError("workbench is local research, not test or trading production")
    if "QUANT_DB_PATH" in env:
        other = env["QUANT_DB_PATH"]
        if not other.strip() or not Path(other).is_absolute() or Path(other).resolve() != path:
            raise ValueError("QUANT_DB_PATH conflicts with AI_TRADE_WORKBENCH_ROOT")
    readonly = env.get("AI_TRADE_READ_ONLY", "1")
    if readonly not in ("0", "1"):
        raise ValueError("AI_TRADE_READ_ONLY must be 0 or 1")
    return DatabaseConfig(path, "local", env.get("QUANT_DB_JOURNAL", "DELETE"),
                          read_only=readonly == "1", require_existing=True)


def _objects(conn):
    return [tuple(row) for row in conn.execute(
        "SELECT type,name,tbl_name,sql FROM sqlite_master "
        "WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name")]


@lru_cache(maxsize=None)
def expected_objects(version=None):
    # Deterministic reference derived solely from immutable released migrations.
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute(LEDGER_SQL)
        if version is None:
            version = len(MIGRATIONS)
        if type(version) is not int or not 2 <= version <= len(MIGRATIONS):
            raise IntegrityError("unsupported workbench schema prefix")
        for migration in MIGRATIONS[:version]:
            for statement in migration.statements:
                conn.execute(statement)
        return _objects(conn)
    finally:
        conn.close()


def inspect_database(db: Database) -> dict:
    """Validate ledger AND physical DDL in one snapshot. Never initializes/repairs."""
    with db.connection() as conn:
        conn.execute("BEGIN")
        quick = [row[0] for row in conn.execute("PRAGMA quick_check")]
        if quick != ["ok"]:
            raise IntegrityError(f"SQLite quick_check failed: {quick}")
        migrations = [dict(row) for row in conn.execute("SELECT * FROM schema_migrations ORDER BY version")]
        version = len(migrations)
        if not 2 <= version <= len(MIGRATIONS):
            raise IntegrityError("unsupported workbench schema version; explicit maintenance required")
        expected = [(m.version, m.name, m.checksum) for m in MIGRATIONS[:version]]
        if [(r["version"], r["name"], r["checksum"]) for r in migrations] != expected:
            raise IntegrityError("workbench schema version/checksum mismatch; explicit maintenance required")
        objects = _objects(conn)
        if objects != expected_objects(version):
            raise IntegrityError("workbench physical schema drift (tables/indexes/triggers)")
        foreign_errors = [tuple(row) for row in conn.execute("PRAGMA foreign_key_check")]
        if foreign_errors:
            raise IntegrityError("workbench foreign_key_check failed")
        tables = [r[1] for r in objects if r[0] == "table"]
        counts = {name: conn.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0] for name in tables}
        structure = {name: {
            "columns": [dict(r) for r in conn.execute(f'PRAGMA table_info("{name}")')],
            "foreign_keys": [dict(r) for r in conn.execute(f'PRAGMA foreign_key_list("{name}")')],
            "indexes": [dict(r) for r in conn.execute(f'PRAGMA index_list("{name}")')],
        } for name in tables}
        bound = conn.execute("PRAGMA database_list").fetchone()[2]
        return {"path": str(db.config.path), "connected_path": bound,
                "schema_version": len(migrations), "migrations": migrations,
                "quick_check": quick, "foreign_key_check": foreign_errors,
                "read_only": db.config.read_only, "require_existing": db.config.require_existing,
                "journal_mode": conn.execute("PRAGMA journal_mode").fetchone()[0],
                "query_only": conn.execute("PRAGMA query_only").fetchone()[0],
                "foreign_keys_enabled": conn.execute("PRAGMA foreign_keys").fetchone()[0],
                "recursive_triggers": conn.execute("PRAGMA recursive_triggers").fetchone()[0],
                "counts": counts, "structure": structure, "objects": objects,
                "latest_trade_date": conn.execute("SELECT max(trade_date) FROM daily_bars").fetchone()[0]}

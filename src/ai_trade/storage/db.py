"""Short-lived SQLite connections, explicit transactions and atomic migrations."""

import os
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Mapping

from ai_trade.data_access.models import IntegrityError
from ai_trade.storage.schema import LEDGER_SQL, MIGRATIONS, Migration


@dataclass(frozen=True)
class DatabaseConfig:
    """Explicit file configuration; tests must supply their own temporary path."""

    path: Path
    environment: str = "local"
    journal_mode: str = "WAL"
    busy_timeout_ms: int = 5000

    def __post_init__(self) -> None:
        if not str(self.path).strip() or str(self.path) == ":memory:":
            raise ValueError("a file path is required; tests should use tmp_path")
        object.__setattr__(self, "path", Path(self.path).expanduser().resolve())
        if self.environment not in ("local", "test", "production"):
            raise ValueError("environment must be local, test or production")
        if self.journal_mode not in ("WAL", "DELETE"):
            raise ValueError("journal_mode must be WAL or DELETE")
        if type(self.busy_timeout_ms) is not int or not 0 <= self.busy_timeout_ms <= 2**31 - 1:
            raise ValueError("busy_timeout_ms must be a nonnegative 32-bit integer")

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> "DatabaseConfig":
        """Read shell variables; never implicitly load a .env file."""
        env = os.environ if environ is None else environ
        environment = env.get("QUANT_DB_ENV", "local")
        path = env.get("QUANT_DB_PATH")
        if environment in ("production", "test") and not path:
            raise ValueError(f"{environment} requires explicit QUANT_DB_PATH")
        if path is not None and not path.strip():
            raise ValueError("QUANT_DB_PATH cannot be blank")
        return cls(Path(path or "data/sqlite/local.sqlite3"), environment,
                   env.get("QUANT_DB_JOURNAL", "WAL"))


class Database:
    """Owns configuration only; connections are never global or shared."""

    def __init__(self, config: DatabaseConfig):
        self.config = config

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        """Close on success or error. Use transaction() for atomic writes.

        WAL is supported for local disks. Network shares are not certified;
        configure DELETE explicitly if WAL is unavailable and test the filesystem.
        """
        conn = sqlite3.connect(self.config.path, isolation_level=None,
                               timeout=self.config.busy_timeout_ms / 1000)
        try:
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA recursive_triggers = ON")
            conn.execute(f"PRAGMA busy_timeout = {self.config.busy_timeout_ms}")
            mode = conn.execute(f"PRAGMA journal_mode = {self.config.journal_mode}").fetchone()[0]
            if mode.upper() != self.config.journal_mode:
                raise IntegrityError("SQLite refused configured journal mode")
            conn.execute("PRAGMA synchronous = FULL")
            yield conn
        finally:
            conn.close()

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Commit a successful batch and roll back even on interruption."""
        with self.connection() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    def initialize(self, migrations: tuple[Migration, ...] = MIGRATIONS) -> int:
        """Apply an ordered migration registry atomically and reject drift.

        Each SQL statement is executed separately: executescript() would commit
        implicitly and could leave a half-applied migration after failure.
        """
        if [m.version for m in migrations] != list(range(1, len(migrations) + 1)):
            raise IntegrityError("migration registry must be contiguous from version 1")
        self.config.path.parent.mkdir(parents=True, exist_ok=True)
        with self.transaction() as conn:
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            )}
            if "schema_migrations" not in tables:
                if tables:
                    raise IntegrityError("refusing to adopt an unversioned nonempty database")
                conn.execute(LEDGER_SQL)
            applied = list(conn.execute("SELECT * FROM schema_migrations ORDER BY version"))
            if len(applied) > len(migrations):
                raise IntegrityError("database schema is newer than this application")
            for expected, actual in zip(migrations, applied):
                if (actual["version"], actual["name"], actual["checksum"]) != (
                        expected.version, expected.name, expected.checksum):
                    raise IntegrityError("migration history gap or checksum drift")
            for migration in migrations[len(applied):]:
                for statement in migration.statements:
                    conn.execute(statement)
                conn.execute("INSERT INTO schema_migrations VALUES (?, ?, ?, ?)", (
                    migration.version, migration.name, migration.checksum,
                    datetime.now(timezone.utc).isoformat(timespec="microseconds"),
                ))
        return len(migrations)

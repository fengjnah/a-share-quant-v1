"""Small repository helpers over the existing Database transaction lifecycle."""

import hashlib
import json
import sqlite3
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from typing import Callable, Iterable, TypeVar

from ai_trade.data_access.models import DuplicateRecordError, IntegrityError, ValidationError, WriteResult
from ai_trade.data_access.validation import text_field
from ai_trade.reference_data.models import Provenance, ReferenceResult
from ai_trade.storage.db import Database

T = TypeVar("T")


def write_batch(database: Database, records: Iterable[T], run_id: str,
                validator: Callable[[T], T], insert: Callable[[sqlite3.Connection, T, str], None]) -> WriteResult:
    text_field(run_id, "run_id")
    try:
        with database.transaction() as conn:
            if conn.execute("SELECT 1 FROM ingestion_runs WHERE run_id=?", (run_id,)).fetchone():
                raise DuplicateRecordError(f"run_id already exists: {run_id}")
            conn.execute("INSERT INTO ingestion_runs VALUES (?,?)", (
                run_id, datetime.now(timezone.utc).isoformat(timespec="microseconds")))
            count = 0
            for index, raw in enumerate(records):
                try:
                    record = validator(raw)
                except ValidationError as exc:
                    raise ValidationError(tuple(f"records[{index}].{issue}" for issue in exc.issues)) from exc
                insert(conn, record, run_id)
                count += 1
            if not count:
                raise ValidationError(("records: batch cannot be empty",))
    except sqlite3.IntegrityError as exc:
        raise IntegrityError(f"reference batch rejected; nothing committed: {exc}") from exc
    return WriteResult(run_id, count)


def insert_row(conn: sqlite3.Connection, table: str, keys: dict, values: dict) -> None:
    """Only internal constant table/column names are used; all values are bound."""
    where = " AND ".join(f"{key}=?" for key in keys)
    if conn.execute(f"SELECT 1 FROM {table} WHERE {where}", tuple(keys.values())).fetchone():
        raise DuplicateRecordError(f"duplicate reference version: {keys}")
    conn.execute(f"INSERT INTO {table} ({','.join(values)}) VALUES ({','.join('?' for _ in values)})",
                 tuple(values.values()))


def meta_from_row(row: sqlite3.Row) -> Provenance:
    return Provenance(**{key: row[key] for key in Provenance.__dataclass_fields__})


def envelope(value: T, rows: list[sqlite3.Row], cutoff: str, mode: str, kind: str,
             scope: dict, warnings: tuple[str, ...] = (), missing: tuple[str, ...] = (),
             errors: tuple[str, ...] = ()) -> ReferenceResult[T]:
    notices = list(warnings)
    if mode == "research":
        notices.append("research mode: not an audited backtest result")
    if any(row["evidence_kind"] == "synthetic" for row in rows):
        notices.append("synthetic evidence: not verified real-source data")
    if missing:
        notices.append("incomplete calendar: missing dates are not closed sessions")
    if errors:
        notices.append("calendar source errors: affected dates are not usable sessions")
    lineage = tuple(f"{kind}_version:{row['version_id']}:run:{row['run_id']}" for row in rows)
    payload = dict(value=value, as_of=cutoff, mode=mode, scope=scope,
                   lineage=lineage, missing=missing, source_errors=errors)
    def encode(obj):
        if is_dataclass(obj):
            return asdict(obj)
        raise TypeError(f"cannot serialize {type(obj).__name__}")
    digest = hashlib.sha256(json.dumps(payload, default=encode, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return ReferenceResult(value, cutoff, mode, f"reference-observation:sha256:{digest}",
                           "task-004-v1", tuple(notices), lineage, missing, errors)

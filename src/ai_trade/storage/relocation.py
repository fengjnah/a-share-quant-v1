"""Create-only v2 relocation using existing SQLite Backup API; no config switch.

Operators must independently verify review and quiescence before executing.
The acknowledgments record that decision; they do not certify it automatically.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re

from ai_trade.storage.db import Database, DatabaseConfig
from ai_trade.storage.workbench import data_root, inspect_database
from ai_trade.storage.workbench_cli import backup_new, ensure_absent, file_state

STOP_CONFIRMATION = "ALL_WRITERS_AND_READERS_STOPPED"


def reader(path):
    path = Path(path)
    if not path.is_absolute() or path.absolute() != path.resolve() or path.is_symlink() or not path.is_file():
        raise ValueError("existing absolute regular source database required")
    return Database(DatabaseConfig(path, journal_mode="DELETE", read_only=True, require_existing=True))


def inventory(db):
    state = inspect_database(db)
    if state['schema_version'] != 2 or len(state['counts']) != 7:
        raise ValueError("relocation accepts only exact released v2 / seven tables; no upgrade")
    # One read transaction for all content fingerprints and integrity checks.
    with db.connection() as conn:
        conn.execute('BEGIN')
        integrity = [r[0] for r in conn.execute('PRAGMA integrity_check')]
        foreign = [tuple(r) for r in conn.execute('PRAGMA foreign_key_check')]
        if integrity != ['ok'] or foreign:
            raise ValueError("integrity/foreign-key failure")
        hashes = {}
        for table in sorted(state['counts']):
            rows = [tuple(r) for r in conn.execute(f'SELECT * FROM "{table}" ORDER BY rowid')]
            hashes[table] = hashlib.sha256(json.dumps(rows, ensure_ascii=False, allow_nan=False,
                separators=(',', ':')).encode('utf-8')).hexdigest()
    return {k: state[k] for k in ('schema_version', 'migrations', 'counts', 'objects', 'structure')} | {
        'integrity_check': integrity, 'foreign_key_check': foreign, 'table_content_sha256': hashes}


def _new_path(path):
    path = Path(path)
    if not path.is_absolute() or path.absolute() != path.resolve():
        raise ValueError("absolute destination without links/traversal required")
    ensure_absent(path)
    return path


def relocate(*, source, root, batch_id, expected_sha256, review_ref, stopped):
    """Does not initialize/migrate, modify the source, stop apps, or select a DB.

    Failure artifacts remain for diagnosis. No overwrite, cleanup or retry.
    Call only inside an approved stopped-writer maintenance window.
    """
    if stopped != STOP_CONFIRMATION or not isinstance(review_ref, str) or not review_ref.strip():
        raise ValueError("independent review reference and explicit stopped-writer confirmation required")
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', batch_id):
        raise ValueError("safe unique batch ID required")
    if not re.fullmatch(r'[0-9a-f]{64}', expected_sha256):
        raise ValueError("exact audited source SHA256 required")
    src = reader(source)
    before = file_state(src.config.path)
    if before[0]['sha256'] != expected_sha256 or any(x['exists'] for x in before[1:]):
        raise ValueError("source identity changed or sidecar present; stop and audit")
    root = data_root(str(root), must_exist=False)
    target = _new_path(root / 'sqlite' / 'workbench.sqlite3')
    backup = _new_path(root / 'backups' / (batch_id + '.sqlite3'))
    restored = _new_path(root / 'backups' / (batch_id + '-restore') / 'workbench.sqlite3')
    if len({src.config.path, target, backup, restored}) != 4:
        raise ValueError("four distinct paths required")
    layout = [root / r for r in ('raw/market', 'raw/cffex', 'raw/evidence', 'exports')]
    for directory in layout:
        if directory.resolve() != directory or (directory.exists() and not directory.is_dir()):
            raise ValueError("unsafe layout path; no copy performed")
    baseline = inventory(src)

    def unchanged():
        if file_state(src.config.path) != before or inventory(src) != baseline:
            raise ValueError("source changed during maintenance; retain all files, do not switch")

    def copy_and_verify(origin, destination):
        unchanged()
        backup_new(origin, destination)  # existing create-only API; never initialize
        copied = inventory(reader(destination))
        if copied != baseline:
            raise ValueError("backup/restore content or schema mismatch; do not switch")
        unchanged()
        return copied

    copied = copy_and_verify(src, backup)
    recovered = copy_and_verify(reader(backup), restored)
    relocated = copy_and_verify(reader(restored), target)
    # Reserve only empty layout directories. No copied/guessed source data.
    for directory in layout:
        if directory.resolve() != directory or (directory.exists() and not directory.is_dir()):
            raise ValueError("unsafe layout path; preserve artifacts and do not switch")
        directory.mkdir(parents=True, exist_ok=True)
    unchanged()
    return {'status': 'COPIED_VERIFIED_NOT_SWITCHED', 'source': str(src.config.path),
            'target': str(target), 'backup': str(backup), 'restore': str(restored),
            'review_ref': review_ref, 'stop_confirmation': stopped,
            'source_before': before, 'source_after': file_state(src.config.path),
            'baseline': baseline, 'backup_inventory': copied, 'restore_inventory': recovered,
            'target_inventory': relocated, 'target_files': file_state(target),
            'schema_upgraded': False, 'configuration_switched': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--data-root', type=Path, required=True)
    parser.add_argument('--batch-id', required=True)
    parser.add_argument('--expected-sha256', required=True)
    parser.add_argument('--review-ref', required=True)
    parser.add_argument('--confirm-stopped', choices=[STOP_CONFIRMATION], required=True)
    args = parser.parse_args()
    report = relocate(source=args.source, root=args.data_root, batch_id=args.batch_id,
                      expected_sha256=args.expected_sha256, review_ref=args.review_ref, stopped=args.confirm_stopped)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()

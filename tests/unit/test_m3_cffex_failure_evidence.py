"""Bounded offline CFFEX failures retain exact raw evidence and attempt identity."""
from dataclasses import replace
import sqlite3

import pytest

from ai_trade.m3_store_values import decoded
from m3_storage_fixtures import repo, batch, DAY
from test_cffex_rankings import named, legacy
from test_m3_storage_market import report


def attempt(r, b):
    with r.database.connection() as c:
        row = c.execute('SELECT * FROM ingestion_attempts WHERE attempt_id=?', (b.attempt_id,)).fetchone()
    return decoded('ingestion_attempts', row)


def requested(b, label):
    b = batch(b.source_id, label)
    return replace(b, request_key='CFFEX:IF:' + DAY, request={
        'schema_version': 'm3-request-v1', 'parameters': {
            'symbol': 'IF2611', 'variety': 'IF', 'trade_date': DAY, 'operation': 'rankings'}})


@pytest.mark.parametrize('case', ['blank_member', 'empty', 'calendar', 'transaction'])
def test_failed_response_links_exact_bytes_without_typed_success(database, tmp_path, case):
    r = repo(database, tmp_path)
    ids, payload, record, p, b = report(r)
    b = requested(b, case)
    record = replace(record, run_id=b.run_id)
    if case == 'blank_member':
        payload = payload.decode('gbk').replace('甲会员(代客)', '').encode('gbk')
    elif case == 'empty':
        payload = b''
    elif case == 'calendar':
        ids = ids[:1]
    else:
        # Force a data transaction failure after raw and validation succeeded.
        with database.transaction() as c:
            c.execute('INSERT INTO ingestion_runs VALUES (?,?)', (b.run_id, b.finished_at))
    with pytest.raises(Exception):
        r.save_cffex(payload, record, p, batch=b, calendar_version_ids=ids)
    saved = attempt(r, b)
    assert saved['outcome'] == 'FAILED'
    assert saved['evidence_id'] is not None
    assert r.evidence_bytes(saved['evidence_id']) == payload
    assert saved['source_id'] == b.source_id and saved['request_json'] == b.request
    assert saved['request_key'] == b.request_key and saved['committed_run_id'] is None
    with database.connection() as c:
        assert c.execute('SELECT count(*) FROM cffex_report_versions').fetchone()[0] == 0
        assert c.execute('SELECT count(*) FROM data_versions WHERE attempt_id=?', (b.attempt_id,)).fetchone()[0] == 0
        if case != 'transaction':
            assert c.execute('SELECT 1 FROM ingestion_runs WHERE run_id=?', (b.run_id,)).fetchone() is None


def test_failed_attempt_cannot_be_reused_and_new_attempt_retry_preserves_old_evidence(database, tmp_path):
    r = repo(database, tmp_path)
    ids, payload, record, p, b = report(r)
    bad = payload.decode('gbk').replace('甲会员(代客)', '').encode('gbk')
    with pytest.raises(Exception):
        r.save_cffex(bad, record, p, batch=b, calendar_version_ids=ids)
    before = attempt(r, b)
    with pytest.raises(ValueError, match='attempt.*finalized|new attempt'):
        r.save_cffex(payload, record, p, batch=b, calendar_version_ids=ids)
    assert attempt(r, b) == before
    retry = requested(b, 'retry')
    vid = r.save_cffex(payload, replace(record, run_id=retry.run_id), p, batch=retry, calendar_version_ids=ids)
    assert r.get_cffex(vid).rows == record.rows
    assert attempt(r, retry)['outcome'] == 'SUCCESS'
    assert attempt(r, b) == before
    assert r.evidence_bytes(before['evidence_id']) == bad


def test_partial_collection_and_distinct_failed_batches_are_isolated(database, tmp_path):
    r = repo(database, tmp_path)
    ids, payload, record, p, good = report(r)
    vid = r.save_cffex(payload, record, p, batch=good, calendar_version_ids=ids)
    failures = []
    for variety, raw in [('IH', b''), ('IC', b'not a rankings response')]:
        b = requested(good, variety)
        b = replace(b, request_key='CFFEX:' + variety + ':' + DAY,
            request={'schema_version': 'm3-request-v1', 'parameters': {'variety': variety, 'trade_date': DAY}})
        with pytest.raises(Exception):
            r.save_cffex(raw, replace(record, variety=variety, run_id=b.run_id), p,
                         batch=b, calendar_version_ids=ids)
        saved = attempt(r, b)
        assert saved['outcome'] == 'FAILED' and saved['request_json'] == b.request
        assert r.evidence_bytes(saved['evidence_id']) == raw
        failures.append(saved)
    assert failures[0]['evidence_id'] != failures[1]['evidence_id']
    assert r.get_cffex(vid) == record
    assert attempt(r, good)['outcome'] == 'SUCCESS'


def test_unrepresentable_report_is_blocked_and_cannot_overwrite_its_attempt(database, tmp_path):
    r = repo(database, tmp_path)
    ids, raw, record, p, b = report(r, legacy(DAY, 'IF2611'))
    assert r.save_cffex(raw, record, p, batch=b, calendar_version_ids=ids) is None
    before = attempt(r, b)
    assert before['outcome'] == 'BLOCKED' and r.evidence_bytes(before['evidence_id']) == raw
    with pytest.raises(ValueError, match='attempt.*finalized|new attempt'):
        r.save_cffex(raw, record, p, batch=b, calendar_version_ids=ids)
    assert attempt(r, b) == before


def test_real_zero_is_retained_and_missing_member_is_rejected(database, tmp_path):
    r = repo(database, tmp_path)
    ids, raw, record, p, b = report(r, named(contracts=['IF2610']))
    vid = r.save_cffex(raw, record, p, batch=b, calendar_version_ids=ids)
    assert all(row.open_interest == 0 for row in r.get_cffex(vid).rows if row.open_interest is not None)
    bad = raw.decode('gbk').replace('甲会员(代客)', '').encode('gbk')
    failed = requested(b, 'missing-member-zero')
    with pytest.raises(Exception):
        r.save_cffex(bad, replace(record, run_id=failed.run_id), p,
                     batch=failed, calendar_version_ids=ids)
    assert attempt(r, failed)['outcome'] == 'FAILED'
    assert r.evidence_bytes(attempt(r, failed)['evidence_id']) == bad


def test_absent_ranking_is_blocked_rather_than_stored_as_zero(database, tmp_path):
    r = repo(database, tmp_path)
    ids, raw, record, p, b = report(r)
    lines = raw.decode('gbk').splitlines()
    fields = lines[2].split(',')
    fields[6:9] = ['', '', '']  # No long-side member, quantity or change.
    lines[2] = ','.join(fields)
    missing = ('\n'.join(lines) + '\n').encode('gbk')
    assert r.save_cffex(missing, record, p, batch=b, calendar_version_ids=ids) is None
    saved = attempt(r, b)
    assert saved['outcome'] == 'BLOCKED' and saved['committed_run_id'] is None
    assert r.evidence_bytes(saved['evidence_id']) == missing
    with database.connection() as c:
        assert c.execute('SELECT count(*) FROM cffex_report_versions').fetchone()[0] == 0


def test_unarchivable_input_has_no_invented_evidence(database, tmp_path):
    r = repo(database, tmp_path)
    ids, _, record, p, b = report(r)
    with pytest.raises(ValueError, match='bounded evidence bytes'):
        r.save_cffex(None, record, p, batch=b, calendar_version_ids=ids)
    assert attempt(r, b)['outcome'] == 'FAILED'
    assert attempt(r, b)['evidence_id'] is None


def test_failure_audit_error_is_explicit_and_preserves_parse_cause(database, tmp_path, monkeypatch):
    r = repo(database, tmp_path)
    ids, _, record, p, b = report(r)
    def unavailable(*args, **kwargs):
        raise sqlite3.OperationalError('offline audit failure fixture')
    monkeypatch.setattr(r, 'record_attempt', unavailable)
    with pytest.raises(ValueError, match='failure audit also failed') as exc:
        r.save_cffex(b'', record, p, batch=b, calendar_version_ids=ids)
    assert exc.value.__cause__ is not None
    with database.connection() as c:
        assert c.execute('SELECT count(*) FROM cffex_report_versions').fetchone()[0] == 0

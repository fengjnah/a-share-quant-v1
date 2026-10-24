"""Portable offline regressions; synthetic calendars never certify real dates."""
import json
from dataclasses import replace
from unittest.mock import Mock

import pytest
import requests

from ai_trade.market_data.cffex_collector import CffexCollector
from ai_trade.market_data.cffex_sessions import cffex_session_days
from m3_storage_fixtures import A, I, DAY
from test_cffex_rankings import named
from test_m3_storage_market import sessions


def collector(database, tmp_path, payload=None, *, calendar=False):
    c = CffexCollector(database, tmp_path / 'evidence',
                       collect_from_file=lambda *_: named(contracts=['IF2611']) if payload is None else payload)
    if calendar:
        c._session_ids = tuple(sessions(c._repo))
    return c


def attempt(c, result):
    with c._db.connection() as conn:
        return dict(conn.execute('SELECT * FROM ingestion_attempts WHERE attempt_id=?',
                                (result.attempt_id,)).fetchone())


def no_report(c):
    with c._db.connection() as conn:
        assert conn.execute('SELECT count(*) FROM cffex_report_versions').fetchone()[0] == 0
        assert conn.execute('SELECT count(*) FROM cffex_rank_rows').fetchone()[0] == 0


def test_all_unsupported_calendar_dates_unknown():
    days = cffex_session_days()
    assert len(days) == 14
    assert {'2026-10-23', '2026-10-24', '2026-10-25', '2026-10-29', '2026-10-30'} <= {d['session_date'] for d in days}
    assert all(d['is_trading_day'] is None and d['opens_at'] is None
               and d['closes_at'] is None and d['error_reason'] == 'CALENDAR_UNCERTIFIED' for d in days)
    days[0]['is_trading_day'] = True
    assert cffex_session_days()[0]['is_trading_day'] is None


def test_missing_calendar_blocks_and_audits_without_inventing_sessions(database, tmp_path):
    c = collector(database, tmp_path)
    r = c.collect('IF', DAY, observed_at=A, ingested_at=I)
    assert r.status == 'BLOCKED'
    row = attempt(c, r)
    assert row['outcome'] == 'BLOCKED' and row['returned_rows'] == 60
    manifest = json.loads(c._repo.evidence_bytes(row['evidence_id']))
    assert manifest['stage'] == 'calendar'
    assert c._repo.evidence_bytes(manifest['raw_evidence_id']) == named(contracts=['IF2611'])
    with database.connection() as conn:
        assert conn.execute('SELECT count(*) FROM market_session_versions').fetchone()[0] == 0
    no_report(c)


@pytest.mark.parametrize('error', [ConnectionError, requests.Timeout, FileNotFoundError])
def test_transport_failure_has_ended_attempt_not_fake_response(database, tmp_path, error):
    c = collector(database, tmp_path)
    def fail(*_):
        raise error('secret URL text must not be recorded')
    c._offline = fail
    r = c.collect('IF', DAY)
    assert r.status == 'FAILED'
    row = attempt(c, r)
    assert row['outcome'] == 'FAILED' and row['returned_rows'] is None
    manifest = json.loads(c._repo.evidence_bytes(row['evidence_id']))
    assert manifest['stage'] == 'fetch' and manifest['raw_evidence_id'] is None
    assert 'secret' not in json.dumps(manifest)
    assert manifest['request_evidence_id']
    no_report(c)


@pytest.mark.parametrize('payload', [b'', b'<html>error</html>', b'wrong,columns\n1,2',
    named(contracts=['IF2611']).decode('gbk').replace('甲会员(代客)', '').encode('gbk')])
def test_parse_failures_preserve_exact_received_bytes(database, tmp_path, payload):
    c = collector(database, tmp_path, payload)
    r = c.collect('IF', DAY)
    assert r.status == 'FAILED'
    row = attempt(c, r)
    assert row['outcome'] == 'FAILED' and row['returned_rows'] is None
    assert json.loads(c._repo.evidence_bytes(row['evidence_id']))['stage'] == 'parse'
    assert c._repo.evidence_bytes(r.raw_evidence_id) == payload
    no_report(c)


def test_http_error_cannot_be_success_even_for_valid_csv(database, tmp_path, monkeypatch):
    c = collector(database, tmp_path, calendar=True)
    raw = named(contracts=['IF2611'])
    monkeypatch.setattr(c, '_fetch', lambda *_: (raw, 'https://www.cffex.com.cn/test', 500, 'HTTPS'))
    r = c.collect('IF', DAY)
    assert r.status == 'FAILED' and attempt(c, r)['error_code'] == 'http:ValueError'
    assert c._repo.evidence_bytes(r.raw_evidence_id) == raw
    no_report(c)


def test_retry_chain_is_immutable_and_isolated_by_request(database, tmp_path):
    c = collector(database, tmp_path, b'bad')
    one = c.collect('IF', DAY, run_id='same-caller-batch')
    original = attempt(c, one)
    other = c.collect('IH', DAY)
    two = c.collect('IF', DAY, run_id='same-caller-batch')
    three = c.collect('IF', DAY)
    assert len({r.attempt_id for r in (one, two, three, other)}) == 4
    assert one.retry_of is None and other.retry_of is None
    assert two.retry_of == one.attempt_id and three.retry_of == two.attempt_id
    assert attempt(c, one) == original
    assert json.loads(c._repo.evidence_bytes(two.audit_evidence_id))['retry_of'] == one.attempt_id
    assert json.loads(c._repo.evidence_bytes(two.audit_evidence_id))['run_id'] != json.loads(c._repo.evidence_bytes(one.audit_evidence_id))['run_id']


@pytest.mark.parametrize('stage', ['request_evidence', 'raw_evidence', 'ledger', 'source_setup'])
def test_audit_persistence_failure_is_explicit(database, tmp_path, monkeypatch, stage):
    c = collector(database, tmp_path, b'bad')
    if stage == 'ledger':
        monkeypatch.setattr(c._repo, 'record_attempt', Mock(side_effect=OSError('disk full')))
    elif stage == 'source_setup':
        monkeypatch.setattr(c, '_ensure_source', Mock(side_effect=OSError('disk full')))
    else:
        original = c._repo.put_evidence
        def put(payload, **kw):
            if (stage == 'request_evidence' and kw['evidence_kind'] == 'observation'
                    or stage == 'raw_evidence' and kw['media_type'] == 'text/csv'):
                raise OSError('disk full')
            return original(payload, **kw)
        monkeypatch.setattr(c._repo, 'put_evidence', put)
    r = c.collect('IF', DAY)
    assert r.status == 'AUDIT_FAILED'
    assert stage in r.error or 'audit:' in r.error
    no_report(c)


def test_success_readback_and_duplicate_across_instances(database, tmp_path):
    c = collector(database, tmp_path, calendar=True)
    one = c.collect('IF', DAY, observed_at=A, ingested_at=I)
    assert one.status == 'SUCCESS', one.error
    record = c._repo.get_cffex(one.version_id)
    assert record.publication_time is None
    assert record.available_at == '2026-10-19T01:30:00.000000+00:00'
    assert record.evidence_kind == 'synthetic'
    new = CffexCollector(database, tmp_path / 'evidence', collect_from_file=c._offline,
                         calendar_version_ids=c._session_ids)
    two = new.collect('IF', DAY, observed_at=A, ingested_at=I)
    assert two.status == 'SUCCESS', two.error
    assert two.version_id == one.version_id and two.attempt_id != one.attempt_id
    assert attempt(c, two)['outcome'] == 'DUPLICATE'
    assert two.retry_of == one.attempt_id
    with database.connection() as conn:
        assert conn.execute('SELECT count(*) FROM cffex_rank_rows').fetchone()[0] == 60
        assert conn.execute("SELECT decision FROM quality_assessments WHERE data_version_id=?", (one.version_id,)).fetchone()[0] == 'UNKNOWN'


@pytest.mark.parametrize('mode', ['closed', 'missing', 'late', 'before_close'])
def test_time_boundaries_remain_fail_closed(database, tmp_path, mode, monkeypatch):
    c = collector(database, tmp_path, calendar=True)
    observed, ingested = A, I
    if mode in ('closed', 'missing'):
        original = c._repo.ranking_calendar
        def calendar(ids):
            obj = original(ids)
            get = obj.get_day
            def day(**kw):
                if mode == 'missing':
                    raise KeyError('missing calendar')
                return replace(get(**kw), is_trading_day=False, opens_at=None, closes_at=None)
            obj.get_day = day
            return obj
        monkeypatch.setattr(c._repo, 'ranking_calendar', calendar)
    elif mode == 'late':
        observed = ingested = '2026-10-20T08:00:00Z'
    else:
        observed = ingested = '2026-10-16T06:00:00Z'
    r = c.collect('IF', DAY, observed_at=observed, ingested_at=ingested)
    assert r.status in ('FAILED', 'BLOCKED')
    assert attempt(c, r)['outcome'] in ('FAILED', 'BLOCKED')
    no_report(c)


@pytest.mark.parametrize('failure', ['timeout', 'oversized', 'content_type'])
def test_bounded_transfer_partial_response_evidence(database, tmp_path, monkeypatch, failure):
    c = CffexCollector(database, tmp_path / 'evidence')
    response = Mock(status_code=200, headers={'Content-Type': 'text/csv'})
    raw = b'partial response'
    def chunks(_):
        yield raw
        raise requests.Timeout('private network text')
    if failure == 'timeout':
        response.iter_content.side_effect = chunks
    elif failure == 'oversized':
        raw = b'x' * 2_000_001
        response.iter_content.return_value = iter([raw])
    else:
        response.headers['Content-Type'] = 'text/html'
        response.iter_content.return_value = iter([raw])
    session = Mock()
    session.get.return_value = response
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(requests, 'Session', Mock(return_value=session))
    r = c.collect('IF', DAY)
    assert r.status == 'FAILED', r.error
    assert r.response_complete is False
    assert c._repo.evidence_bytes(r.raw_evidence_id) == raw
    assert attempt(c, r)['outcome'] == 'FAILED'
    assert session.get.call_args.kwargs['verify'] is True
    assert session.get.call_args.kwargs['allow_redirects'] is False
    response.close.assert_called_once()
    no_report(c)

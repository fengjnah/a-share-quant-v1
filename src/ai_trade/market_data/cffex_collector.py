from __future__ import annotations

"""Bounded CFFEX collection with fail-closed calendars and durable attempts.

No automatic database initialization, calendar fabrication or certification.
HTTP requires explicit opt-in; HTTPS always retains certificate verification.
"""
import hashlib
import json
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4
from typing import Optional

from ai_trade.market_data.cffex_rankings import CffexRankingsClient, MAX_PAYLOAD_BYTES, build_record, parse
from ai_trade.market_data.cffex_rankings_models import CffexRankingsRequest, RankingCalendarError
from ai_trade.m3_store_catalog import Batch, Provenance
from ai_trade.m3_store_market import MarketInputRepository

@dataclass
class CollectResult:
    """Outcome of one CFFEX variety collection attempt."""
    variety: str
    trade_date: str
    status: str
    version_id: Optional[str] = None
    row_count: int = 0
    payload_sha256: str = ''
    request_url: str = ''
    http_status: int = 0
    transport: str = ''
    error: str = ''
    observed_at: str = ''
    ingested_at: str = ''
    attempt_id: str = ''
    retry_of: Optional[str] = None
    audit_evidence_id: Optional[str] = None
    raw_evidence_id: Optional[str] = None
    response_complete: Optional[bool] = None

    def to_dict(self):
        return self.__dict__.copy()


class _FetchFailure(Exception):
    """A failed bounded transfer, retaining bytes actually received if any."""
    def __init__(self, cause, payload, url, status, transport):
        super().__init__(type(cause).__name__)
        self.payload, self.url, self.status, self.transport = payload, url, status, transport


class CffexCollector:
    """CFFEX holdings collector using an explicitly supplied database.

    Idempotent: re-collecting the same (variety, trade_date, payload_sha)
    returns the existing version_id without writing duplicates.
    """

    def __init__(self, database, evidence_root, *, http_transport=False, timeout=20.0,
                 collect_from_file=None, calendar_version_ids=()):
        """collect_from_file: offline source, callable(variety, trade_date) -> bytes.

        When provided, raw bytes come from this callable instead of the network;
        transport is recorded as 'offline-file'. No socket is opened.
        """
        self._db = database
        self._evidence_root = Path(evidence_root)
        self._http = http_transport
        self._offline = collect_from_file
        self._client = CffexRankingsClient(timeout=timeout)
        self._repo = MarketInputRepository(database, self._evidence_root)
        self._session_ids = tuple(calendar_version_ids)
        self._source_id: Optional[str] = None

    def _now(self):
        return datetime.now(timezone.utc).isoformat(timespec='microseconds')

    def _ensure_source(self):
        if self._source_id is not None:
            return self._source_id
        # The storage layer verifies record.source against the batch source_id
        # and recomputes provenance from the stored payload, so the registered
        # source identifier must equal the CffexRankingsClient source label.
        source_id = self._client.source_label()
        with self._db.connection() as c:
            existing = c.execute(
                "SELECT 1 FROM data_sources WHERE source_id=?",
                (source_id,)).fetchone()
        if existing is not None:
            # The source row is immutable audit data; do not re-register it.
            self._source_id = source_id
            return source_id
        self._repo.register_source(
            source_id=source_id,
            provider='CFFEX',
            endpoint_key='ccpm',
            adapter_version='task-m3-collector-001',
            dataset_key='cffex_report',
            units_json={},
            time_policy_version='unknown',
        )
        self._source_id = source_id
        return source_id

    def _ensure_sessions(self):
        """Consume explicit frozen calendar versions; never manufacture knowledge.

        The removed collector-001 declarations are known invalid, including
        persisted copies. Explicit inputs do not constitute source certification;
        the existing repository/core quality and receipt gates still apply.
        Synthetic calendars are restricted to explicit offline replay.
        """
        if not self._session_ids:
            raise RankingCalendarError('explicit independently evidenced CFFEX calendar required')
        with self._db.connection() as c:
            for vid in self._session_ids:
                row = c.execute('SELECT source_id,evidence_kind FROM data_versions '
                                'WHERE data_version_id=?', (vid,)).fetchone()
                if row is None or row['source_id'] == 'cffex-sessions':
                    raise RankingCalendarError('missing or invalidated collector-001 calendar version')
                if row['evidence_kind'] == 'synthetic' and self._offline is None:
                    raise RankingCalendarError('synthetic calendar requires offline replay')
        return self._session_ids

    def _fetch(self, variety, trade_date):
        """Fetch raw CSV. Returns (payload, url, http_status, transport)."""
        request = CffexRankingsRequest('CFFEX', variety, trade_date)
        request.validate()
        if self._offline is not None:
            payload = self._offline(variety, trade_date)
            return payload, request.url(), 200, 'offline-file'
        import requests
        url = request.url()
        transport = 'HTTP' if self._http else 'HTTPS'
        if self._http:
            url = url.replace('https://', 'http://', 1)
        body = bytearray()
        received = False
        status = 0
        try:
            with requests.Session() as session:
                session.mount('http://',  requests.adapters.HTTPAdapter(max_retries=0))
                session.mount('https://', requests.adapters.HTTPAdapter(max_retries=0))
                resp = session.get(
                    url,
                    headers={'User-Agent': 'a-share-quant-v1/0.1 (research; TASK-M3-COLLECTOR-001)'},
                    timeout=(self._client.timeout, self._client.timeout),
                    allow_redirects=False, verify=True, stream=True)
                received = True
                status = resp.status_code
                try:
                    for chunk in resp.iter_content(65536):
                        body.extend(chunk)
                        if len(body) > MAX_PAYLOAD_BYTES:
                            raise ValueError('response exceeds bounded payload limit')
                    content_type = resp.headers.get('Content-Type', '').split(';')[0].strip().lower()
                    if content_type not in {'text/csv', 'text/plain', 'application/octet-stream',
                                            'application/vnd.ms-excel'}:
                        raise ValueError('unexpected response media type')
                finally:
                    resp.close()
            return bytes(body), url, status, transport
        except (requests.exceptions.RequestException, ValueError) as exc:
            raise _FetchFailure(exc, bytes(body) if received else None, url, status, transport) from exc

    def collect(self, variety, trade_date, *, run_id=None, observed_at=None, ingested_at=None):
        """One bounded attempt, with immutable request/response/failure evidence.

        B03 only admits completed ledger rows. A request manifest is persisted
        before acquisition; retries link to the previous completed attempt for
        this exact source/variety/date. No automatic retries or calendar writes.
        """
        started = self._now()
        identity = uuid4().hex
        attempt_id = 'cffex:' + identity
        run_id = run_id or 'cffex-run:' + identity
        requested_run_id = run_id
        result = CollectResult(variety, trade_date, 'FAILED', attempt_id=attempt_id)
        source_id = None
        stage = 'source_setup'
        raw_id = None
        returned_rows = None
        request_evidence = None
        request = CffexRankingsRequest('CFFEX', variety, trade_date)

        def batch():
            return Batch(attempt_id, run_id, source_id, variety + ':' + trade_date,
                         {'schema_version': 'm3-request-v1', 'parameters': {
                             'variety': variety, 'trade_date': trade_date}},
                         started, self._now())

        def manifest(state, error=None):
            value = dict(schema_version='m3-cffex-attempt-v1', attempt_id=attempt_id, run_id=run_id,
                         requested_run_id=requested_run_id,
                         retry_of=result.retry_of, source_id=source_id,
                         variety=variety, trade_date=trade_date, state=state,
                         stage=stage, error=error, started_at=started,
                         recorded_at=self._now(), request_evidence_id=request_evidence,
                         raw_evidence_id=raw_id, request_url=result.request_url,
                         payload_sha256=result.payload_sha256 or None,
                         observed_at=result.observed_at or None, ingested_at=result.ingested_at or None,
                         transport=result.transport, http_status=result.http_status,
                         returned_rows=returned_rows, response_complete=result.response_complete)
            return self._repo.put_evidence(
                json.dumps(value, sort_keys=True).encode(),
                evidence_kind='observation', media_type='application/json',
                captured_at=self._now())

        try:
            source_id = self._ensure_source()
            stage = 'request'
            request.validate()
            result.request_url = request.url().replace('https://', 'http://', 1) if self._http else request.url()
            result.transport = 'offline-file' if self._offline else ('HTTP' if self._http else 'HTTPS')
            with self._db.connection() as c:
                previous = c.execute('SELECT attempt_id FROM ingestion_attempts '
                                     'WHERE source_id=? AND request_key=? '
                                     'ORDER BY finished_at DESC,attempt_id DESC LIMIT 1',
                                     (source_id, variety + ':' + trade_date)).fetchone()
            result.retry_of = previous[0] if previous else None
            # A caller may repeat its batch label. The actual retry run remains
            # unique, including when a failed attempt created no ingestion_run.
            with self._db.connection() as c:
                run_exists = c.execute('SELECT 1 FROM ingestion_runs WHERE run_id=?', (run_id,)).fetchone()
            if result.retry_of is not None or run_exists:
                run_id = 'cffex-retry:' + identity
            stage = 'request_evidence'
            request_evidence = manifest('STARTED')
            stage = 'fetch'
            payload, url, status, transport = self._fetch(variety, trade_date)
            result.request_url, result.http_status, result.transport = url, status, transport
            result.response_complete = True
            result.observed_at = observed_at or self._now()
            stage = 'raw_evidence'
            # Offline scenarios are explicitly synthetic, including real-byte
            # replay with synthetic calendars. They are never real certification.
            raw_kind = 'synthetic' if self._offline else 'source_payload'
            raw_id = self._repo.put_evidence(payload, evidence_kind=raw_kind,
                                            media_type='text/csv', captured_at=result.observed_at)
            result.raw_evidence_id = raw_id
            result.payload_sha256 = hashlib.sha256(payload).hexdigest()
            stage = 'http'
            if status != 200:
                raise ValueError('non-success HTTP status')
            if len(payload) > MAX_PAYLOAD_BYTES:
                raise ValueError('response exceeds bounded payload limit')
            stage = 'parse'
            _, rows = parse(payload, request)
            returned_rows = len(rows)
            result.row_count = returned_rows
            result.ingested_at = ingested_at or self._now()
            stage = 'calendar'
            session_ids = self._ensure_sessions()
            calendar = self._repo.ranking_calendar(session_ids)
            stage = 'build_record'
            record = build_record(request, payload, run_id=run_id,
                                  observed_at=result.observed_at, ingested_at=result.ingested_at,
                                  calendar=calendar,
                                  evidence_kind='synthetic' if self._offline else 'source_observation')
            # Reuse an identical prior observation, not a new version stamped
            # with a later fetch time. Its original knowledge times stay intact.
            stage = 'duplicate_lookup'
            with self._db.connection() as c:
                candidates = c.execute('SELECT data_version_id FROM data_versions '
                                       'WHERE dataset_key=? AND source_id=? AND record_version=?',
                                       ('cffex_report', source_id, record.source_version)).fetchall()
            for candidate in candidates:
                old = self._repo.get_cffex(candidate[0])
                if (old.calendar_refs == record.calendar_refs and old.evidence_kind == record.evidence_kind
                        and old.observed_at <= record.observed_at and old.ingested_at <= record.ingested_at):
                    record = replace(old, run_id=run_id)
                    break
            provenance = Provenance(record.source_version, record.event_time, record.available_at,
                                    record.observed_at, record.ingested_at, raw_id,
                                    'accepted', record.evidence_kind)
            stage = 'save_cffex'
            result.version_id = self._repo.save_cffex(
                payload, record, provenance, batch=batch(), calendar_version_ids=session_ids)
            result.status = 'SUCCESS' if result.version_id else 'BLOCKED'
            if not result.version_id:
                result.error = 'save_cffex:UNREPRESENTABLE_RANK_ROWS'
            stage = 'completion_evidence'
            result.audit_evidence_id = manifest(result.status, result.error or None)
            return result
        except Exception as exc:
            # Do not log arbitrary exception text (URLs may contain credentials).
            result.error = stage + ':' + (str(exc) if isinstance(exc, _FetchFailure) else type(exc).__name__)
            result.status = 'BLOCKED' if isinstance(exc, RankingCalendarError) else 'FAILED'
            if source_id is None:
                result.status = 'AUDIT_FAILED'
                return result
            audit_incomplete = stage in {'request_evidence', 'raw_evidence', 'completion_evidence'}
            try:
                if isinstance(exc, _FetchFailure):
                    result.request_url, result.http_status, result.transport = exc.url, exc.status, exc.transport
                    result.response_complete = False
                    if exc.payload is not None:
                        result.observed_at = self._now()
                        raw_id = self._repo.put_evidence(exc.payload, evidence_kind='source_payload',
                                                        media_type='text/csv', captured_at=result.observed_at)
                        result.raw_evidence_id = raw_id
                        result.payload_sha256 = hashlib.sha256(exc.payload).hexdigest()
                result.audit_evidence_id = manifest(result.status, result.error)
                with self._db.connection() as c:
                    existing = c.execute('SELECT outcome FROM ingestion_attempts WHERE attempt_id=?',
                                         (attempt_id,)).fetchone()
                if existing is None:
                    self._repo.record_attempt(batch(), outcome=result.status,
                                              error_code=result.error, returned_rows=returned_rows,
                                              evidence_id=result.audit_evidence_id)
                # Storage may already have finalized a FAILED/BLOCKED attempt.
                # A failure after SUCCESS/DUPLICATE is an audit failure, not a
                # rolled-back successful write; expose this distinction.
                elif existing[0] in ('SUCCESS', 'DUPLICATE'):
                    audit_incomplete = True
                if audit_incomplete:
                    result.status = 'AUDIT_FAILED'
            except Exception as audit_error:
                result.status = 'AUDIT_FAILED'
                result.error += ';audit:' + type(audit_error).__name__
            return result

    def get_report(self, variety, trade_date):
        """Read back the stored CFFEX report for the M3 page."""
        from ai_trade.m3_store_values import rows
        with self._db.connection() as conn:
            report_rows = rows(conn, 'cffex_report_versions',
                exchange='CFFEX', variety=variety, trade_date=trade_date)
        if not report_rows:
            return None
        latest = max(report_rows, key=lambda r: r.get('data_version_id', ''))
        vid = latest['data_version_id']
        record = self._repo.get_cffex(vid)
        return {
            'variety': variety,
            'trade_date': trade_date,
            'version_id': vid,
            'row_count': len(record.rows),
            'contracts': list(record.contracts),
            'format': record.rank_format,
            'payload_sha256': record.payload_sha256,
            'source': record.source,
            'ingested_at': record.ingested_at,
            'available_at': record.available_at,
            'event_time': record.event_time,
            'rows': [
                {
                    'contract': r.contract,
                    'rank': r.rank,
                    'side': r.side.value,
                    'member': r.member,
                    'member_scope': r.member_scope.value,
                    'open_interest': r.open_interest,
                    'open_interest_change': r.open_interest_change,
                    'open_interest_known': r.open_interest_known,
                    'volume': r.volume,
                    'volume_change': r.volume_change,
                } for r in record.rows
            ],
        }

    @staticmethod
    def init_db(db_path):
        """Create and initialise the isolated test SQLite database."""
        from ai_trade.storage.db import Database, DatabaseConfig
        db = Database(DatabaseConfig(Path(db_path), environment='test', journal_mode='DELETE'))
        db.initialize()
        return db

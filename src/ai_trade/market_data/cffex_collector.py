from __future__ import annotations

"""CFFEX member-holdings collector: real fetch -> PR #51 storage -> test SQLite.

P0 loop: CFFEX -> CffexRankingsClient (HTTPS/HTTP) -> parse/build_record
  -> MarketInputRepository.save_cffex -> test SQLite -> M3 page CFFEX module.

Network: production uses HTTPS; current env has CFFEX 443 TLS SSLEOF,
HTTP 80 works. http_transport=True falls back to HTTP. TLS verification
is never disabled. No CAPTCHA or auth bypass.

Semantics: out-of-Top-N members are UNKNOWN (never zero); unknown member
scope is never merged into known-scope aggregates; 16:35 data is available
from the next session at earliest; failed fetches are never recorded as
success; member seat holdings are B-grade proxies, not final-client facts.
"""
import hashlib
import logging
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ai_trade.market_data.cffex_rankings import CffexRankingsClient, build_record, parse
from ai_trade.market_data.cffex_rankings_models import CffexRankingsRequest, MemberScope
from ai_trade.market_data.cffex_sessions import cffex_session_days
from ai_trade.m3_store_catalog import Batch, Provenance
from ai_trade.m3_store_market import MarketInputRepository
from ai_trade.storage.db import Database

logger = logging.getLogger(__name__)


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

    def to_dict(self):
        return self.__dict__.copy()


class CffexCollector:
    """CFFEX holdings collector writing to an isolated test SQLite DB.

    Idempotent: re-collecting the same (variety, trade_date, payload_sha)
    returns the existing version_id without writing duplicates.
    """

    def __init__(self, database, evidence_root, *, http_transport=False, timeout=20.0,
                 collect_from_file=None):
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
        self._session_ids: Optional[list] = None
        self._source_id: Optional[str] = None
        self._session_source_id: Optional[str] = None
        self._collected: dict = {}
        # record_version must exactly mirror CffexRankingsClient.source_label():
        # the storage layer recomputes record.source from it and rejects mismatches.
        self._record_version = self._client.source_label()
        # CffexRankingsRecord has no public field mutators (slots not enforced,
        # plain dataclass) -- but source is set by build_record; the record
        # returned by build_record already carries source=client.source_label().

    def _now(self):
        return datetime.now(timezone.utc).isoformat(timespec='microseconds')

    def _archive_capture_time(self):
        """Capture time of the reviewed session-declaration archive.

        Session declarations in cffex_sessions.py were reviewed from the
        saved CFFEX CSV archive; treat their availability as that archive's
        capture time (the earliest named CSV modification time), which keeps
        calendar knowledge visible at any later report ingestion cutoff.
        """
        times = []
        for name in ('IF_20261023_http.csv',):
            path = self._evidence_root / name
            if path.is_file():
                times.append(path.stat().st_mtime)
        if times:
            return datetime.fromtimestamp(min(times), tz=timezone.utc).isoformat(timespec='microseconds')
        return self._now()

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

    def _ensure_session_source(self):
        """Sessions are a distinct dataset (market_session); the batch must
        carry a source registered with the matching dataset_key."""
        if self._session_source_id is not None:
            return self._session_source_id
        row = self._repo.register_source(
            source_id='cffex-sessions',
            provider='CFFEX',
            endpoint_key='ccpm',
            adapter_version='task-m3-collector-001',
            dataset_key='market_session',
            units_json={},
            time_policy_version='unknown',
        )
        self._session_source_id = row['source_id']
        return self._session_source_id

    def _ensure_sessions(self):
        """Save reviewed CFFEX session days; idempotent."""
        if self._session_ids is not None:
            return self._session_ids
        sid = self._ensure_session_source()
        ids = []
        # Session declarations are sourced from the reviewed CFFEX CSV evidence
        # archive: observed/ingested at their archive capture time, not now.
        # This keeps calendar knowledge visible at the report ingestion cutoff.
        declaration_time = self._archive_capture_time()
        for day in cffex_session_days():
            now = declaration_time
            session_row = {k: v for k, v in day.items() if k != 'evidence'}
            with self._db.connection() as c:
                existing = c.execute(
                    "SELECT dv.data_version_id FROM data_versions dv "
                    "JOIN market_session_versions msv ON msv.data_version_id=dv.data_version_id "
                    "WHERE dv.source_id=? AND msv.session_date=?",
                    (sid, day['session_date'])).fetchone()
            if existing is not None:
                ids.append(existing['data_version_id'])
                continue
            ids.append(self._save_session_day(day, sid, now))
        self._session_ids = ids
        return ids

    def _save_session_day(self, day, sid, now):
        """Write one session declaration; an immutable audit row may already
        exist for the original attempt identity from a prior failed run, in
        which case the day is retried under a derived, new identity."""
        attempt_id = 'attempt:sessions:' + day['session_date']
        run_id = 'run:sessions:' + day['session_date']
        with self._db.connection() as c:
            prior = c.execute(
                "SELECT outcome FROM ingestion_attempts WHERE attempt_id=? AND source_id=?",
                (attempt_id, sid)).fetchone()
        if prior is not None:
            attempt_id = attempt_id + ':retry'
            run_id = run_id + ':retry'
        batch = Batch(
            attempt_id,
            run_id,
            sid, day['session_date'],
            {'schema_version': 'm3-request-v1',
             'parameters': {'operation': 'cffex_session',
              'trade_date': day['session_date']}},
            now, now)
        ev = self._repo.put_evidence(
            json.dumps({
                'schema_version': 'm3-cffex-session-declaration-v1',
                'declaration': day.get('evidence'),
                'session_date': day['session_date'],
            }, ensure_ascii=False, sort_keys=True).encode('utf-8'),
            evidence_kind='synthetic',
            media_type='application/json',
            captured_at=now,
        )
        p = Provenance(
            'session-v1',
            event_time=now, available_at=now, observed_at=now, ingested_at=now,
            evidence_id=ev, quality_status='accepted',
            evidence_kind='synthetic')
        return self._repo.save_session(
            {k: v for k, v in day.items() if k != 'evidence'}, p, batch=batch)

    def _fetch(self, variety, trade_date):
        """Fetch raw CSV. Returns (payload, url, http_status, transport)."""
        request = CffexRankingsRequest('CFFEX', variety, trade_date)
        if self._offline is not None:
            payload = self._offline(variety, trade_date)
            return payload, request.url(), 200, 'offline-file'
        import requests
        url = request.url()
        transport = 'HTTP' if self._http else 'HTTPS'
        if self._http:
            url = url.replace('https://', 'http://', 1)
        try:
            with requests.Session() as session:
                session.mount('http://',  requests.adapters.HTTPAdapter(max_retries=0))
                session.mount('https://', requests.adapters.HTTPAdapter(max_retries=0))
                resp = session.get(
                    url,
                    headers={'User-Agent': 'a-share-quant-v1/0.1 (research; TASK-M3-COLLECTOR-001)'},
                    timeout=(self._client.timeout, self._client.timeout),
                    allow_redirects=False, verify=True, stream=True)
                body = bytearray()
                for chunk in resp.iter_content(65536):
                    body.extend(chunk)
                status = resp.status_code
                resp.close()
            return bytes(body), url, status, transport
        except requests.exceptions.RequestException as exc:
            raise RuntimeError('transport failure: ' + type(exc).__name__) from exc

    def collect(self, variety, trade_date, *, run_id=None, observed_at=None, ingested_at=None):
        """Collect one CFFEX variety for one trade date; persist to test SQLite.

        Idempotent: duplicate payload returns the existing version_id.
        """
        now = self._now()
        observed_at = observed_at or now
        ingested_at = ingested_at or now
        # The immutable audit ledger blocks reuse of attempt/run identities on
        # retry; derived identities keep the audit trail complete and honest.
        def _next_id(table, column, base):
            with self._db.connection() as c:
                n = c.execute(
                    f"SELECT count(*) FROM {table} WHERE {column} LIKE ?",
                    (base + '%',)).fetchone()[0]
            return base if n == 0 else base + ':retry' + str(n)
        attempt_id = _next_id('ingestion_attempts', 'attempt_id',
                             'attempt:' + variety + ':' + trade_date)
        run_id = (run_id or 'run:' + variety + ':' + trade_date
                  + ':' + hashlib.sha256(now.encode()).hexdigest()[:12])
        run_id = _next_id('ingestion_runs', 'run_id', run_id)
        result = CollectResult(variety=variety, trade_date=trade_date, status='FAILED',
                              observed_at=observed_at, ingested_at=ingested_at)

        try:
            payload, url, http_status, transport = self._fetch(variety, trade_date)
        except Exception as exc:
            result.status = 'FAILED'
            result.error = 'fetch: ' + type(exc).__name__ + ': ' + str(exc)
            logger.warning(result.error, exc_info=True)
            return result

        result.request_url = url
        result.http_status = http_status
        result.transport = transport
        result.payload_sha256 = hashlib.sha256(payload).hexdigest()

        cache_key = (variety, trade_date, result.payload_sha256)
        if cache_key in self._collected:
            result.status = 'SUCCESS'
            result.version_id = self._collected[cache_key]
            result.row_count = 0
            return result

        request = CffexRankingsRequest('CFFEX', variety, trade_date)
        try:
            fmt, rows = parse(payload, request)
        except Exception as exc:
            result.status = 'FAILED'
            result.error = 'parse: ' + type(exc).__name__ + ': ' + str(exc)
            logger.warning(result.error, exc_info=True)
            return result

        result.row_count = len(rows)

        try:
            session_ids = self._ensure_sessions()
            sid = self._ensure_source()
        except Exception as exc:
            result.status = 'BLOCKED'
            result.error = 'session/source setup: ' + type(exc).__name__ + ': ' + str(exc)
            logger.error(result.error, exc_info=True)
            return result

        try:
            calendar = self._repo.ranking_calendar(session_ids)
            record = build_record(
                request, payload, run_id=run_id,
                observed_at=observed_at, ingested_at=ingested_at,
                calendar=calendar,
                evidence_kind='source_observation',
            )
        except Exception as exc:
            result.status = 'BLOCKED'
            result.error = 'build_record: ' + type(exc).__name__ + ': ' + str(exc)
            logger.error(result.error, exc_info=True)
            return result

        try:
            evidence_id = self._repo.put_evidence(
                payload, evidence_kind='source_payload',
                media_type='text/csv', captured_at=observed_at)
            batch = Batch(
                attempt_id,
                run_id, sid, variety + ':' + trade_date,
                {'schema_version': 'm3-request-v1',
                 'parameters': {'variety': variety, 'trade_date': trade_date}},
                observed_at, ingested_at)
            provenance = Provenance(
                record_version=record.source_version,
                event_time=record.event_time,
                available_at=record.available_at,
                observed_at=record.observed_at,
                ingested_at=record.ingested_at,
                evidence_id=evidence_id,
                quality_status='accepted',
                evidence_kind='source_observation')
        except Exception as exc:
            result.status = 'FAILED'
            result.error = 'evidence/batch: ' + type(exc).__name__ + ': ' + str(exc)
            logger.error(result.error, exc_info=True)
            return result

        try:
            version_id = self._repo.save_cffex(
                payload, record, provenance,
                batch=batch, calendar_version_ids=session_ids)
            if version_id is None:
                result.status = 'BLOCKED'
                result.error = 'save_cffex BLOCKED: unrepresentable ranking rows'
            else:
                result.status = 'SUCCESS'
                result.version_id = version_id
                self._collected[cache_key] = version_id
        except Exception as exc:
            result.status = 'FAILED'
            result.error = 'save_cffex: ' + type(exc).__name__ + ': ' + str(exc)
            logger.error(result.error, exc_info=True)

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

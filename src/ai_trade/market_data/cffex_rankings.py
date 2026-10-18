"""Offline-testable CFFEX rankings boundary; no persistent repository or strategy.

Actual publication, calendar, permission and HTTPS availability are separate
acceptance gates. All requests use HTTPS, one GET, no redirects or retries.
"""
from __future__ import annotations

import csv
import hashlib
import io
import math
import re
from dataclasses import dataclass
from datetime import date

from .cffex_rankings_models import (
    CffexRankingsRecord, CffexRankingsRequest, IngestionOutcome, MemberScope,
    RankingCalendar, RankingCalendarError, RankingResponseError, RankingSide,
    RankingTransportError, RankingValidationError, RankFormatError, RankingRow,
    RankingVersionError,
)
from .cffex_rankings_time import aware, calendar_day, iso, time_fence

ADAPTER_VERSION = 'task-022a-h-v2'
PROVIDER = 'cffex'
ENDPOINT = 'cffex.com.cn/sj/ccpm/{YYYYMM}/{DD}/{VARIETY}_1.csv'
EXCHANGE = 'CFFEX'
VARIETIES = ('IF', 'IH', 'IC', 'IM')
RANK_TOP_N = 20
MAX_PAYLOAD_BYTES = 2_000_000

_SCOPE_SUFFIXES = {
    "(代客)": MemberScope.AGENT,
    "(自营)": MemberScope.PROPRIO,
}
_SCOPE_SUFFIX_RE = re.compile(r"^(?P<base>.+)(?P<suffix>\(代客\)|\(自营\))$")

# Column layout of the *named* format (2020-03-16 onward). Header occupies the
# first two rows of the CSV; data rows carry 12 fields.
_NAMED_HEADER_0 = (
    "交易日,合约,排名,成交量排名,,,持买单量排名,,,持卖单量排名,,")
_NAMED_HEADER_1 = (
    ",,,会员简称,成交量,比上一交易日增减,会员简称,持买单量,"
    "比上一交易日增减,会员简称,持卖单量,比上一交易日增减")

# Column layout of the *legacy* (2010-2019) aggregate format: two rows per
# contract (futures-company / non-futures-company) with 9 fields.
_LEGACY_HEADER_0 = (
    "交易日,合约,会员类别,总成交量,比上交易日增减,总持买单量,"
    "比上交易日增减,总持卖单量,比上一交易日增减")
_LEGACY_CATEGORY = {"期货公司", "非期货公司"}



@dataclass(frozen=True)
class CffexRankingsClient:
    """One explicit GET with Requests' normal proxy/certificate verification.

    No response headers/body or potentially credential-bearing exception text is
    copied into outcome issues; the original exception remains chained in memory.
    """
    timeout: float = 20.0

    def __post_init__(self):
        if (isinstance(self.timeout, bool) or not isinstance(self.timeout, (int, float))
                or not math.isfinite(self.timeout) or not 0 < self.timeout <= 120):
            raise RankingValidationError('timeout: finite value in (0, 120] required')

    def source_label(self) -> str:
        return f'{PROVIDER}:{ENDPOINT}:{ADAPTER_VERSION}'

    def fetch(self, request: CffexRankingsRequest) -> bytes:
        import requests
        url = request.url()
        try:
            with requests.Session() as session:
                session.mount('https://', requests.adapters.HTTPAdapter(max_retries=0))
                response = session.get(url, headers={'User-Agent': 'a-share-quant-v1/0.1 (research; TASK-022A)'},
                                       timeout=(self.timeout, self.timeout), allow_redirects=False, verify=True,
                                       stream=True)
                try:
                    if response.status_code != 200:
                        code = ('unavailable' if response.status_code == 404 else
                                'redirect' if 300 <= response.status_code < 400 else 'http_error')
                        raise RankingResponseError(f'HTTP {response.status_code}; reason not inferred',
                                                   code=code, http_status=response.status_code)
                    media = response.headers.get('Content-Type', '').split(';', 1)[0].strip().lower()
                    if media not in {'', 'text/csv', 'text/plain', 'application/csv', 'application/octet-stream',
                                     'application/vnd.ms-excel'}:
                        raise RankingResponseError('non-CSV response Content-Type', code='content_type', http_status=200)
                    body = bytearray()
                    for chunk in response.iter_content(chunk_size=65536):
                        body.extend(chunk)
                        if len(body) > MAX_PAYLOAD_BYTES:
                            raise RankingResponseError('response exceeds bounded CSV size', code='oversized', http_status=200)
                    return bytes(body)
                finally:
                    response.close()
        except requests.RequestException as exc:
            raise RankingTransportError(f'transport failure: {type(exc).__name__}') from exc


def _decode(payload: bytes) -> str:
    if not isinstance(payload, bytes) or len(payload) > MAX_PAYLOAD_BYTES:
        raise RankFormatError('bounded bytes payload required')
    try:
        return payload.decode('utf-8-sig' if payload.startswith(b'\xef\xbb\xbf') else 'gbk', errors='strict')
    except UnicodeError as exc:
        raise RankFormatError('invalid declared GBK / UTF-8-BOM encoding') from exc


def classify_payload(payload: bytes, request: CffexRankingsRequest) -> str:
    request.validate()
    if not payload or not payload.strip():
        return 'empty'
    # HTML is a response condition regardless of byte length or Content-Type.
    prefix = payload.lstrip()[:200].lower()
    if prefix.startswith((b'<!doctype', b'<html', b'<head', b'<body')):
        text = _decode(payload)
        return 'not_found' if '页面未找到' in text else 'home_fallback'
    text = _decode(payload).strip()
    if '页面未找到' in text:
        return 'not_found'
    first = text.splitlines()[0] if text else ''
    return 'csv' if first in {_NAMED_HEADER_0, _LEGACY_HEADER_0} else 'unknown'


def _scope_for(name: str) -> MemberScope:
    normalized = name.strip().replace('（', '(').replace('）', ')')
    match = _SCOPE_SUFFIX_RE.fullmatch(normalized)
    return _SCOPE_SUFFIXES[match.group('suffix')] if match else MemberScope.UNKNOWN


def _int_or_none(value: str, name: str, *, allow_negative_change: bool = False):
    value = value.strip()
    if not value:
        return None
    if not re.fullmatch(r'[+-]?[0-9]+', value):
        raise RankingValidationError(f'{name}: integer required')
    try:
        result = int(value)
    except ValueError as exc:
        raise RankingValidationError(f'{name}: integer out of parser bounds') from exc
    if result < 0 and not allow_negative_change:
        raise RankingValidationError(f'{name}: negative quantity')
    return result


def _check_trade_date_and_contract(day, contract, request):
    basic = day.replace('-', '')
    if not re.fullmatch(r'[0-9]{8}', basic):
        raise RankingValidationError('CSV trade date: YYYYMMDD or YYYY-MM-DD required')
    try:
        parsed = date.fromisoformat(f'{basic[:4]}-{basic[4:6]}-{basic[6:]}')
    except ValueError as exc:
        raise RankingValidationError('invalid CSV date') from exc
    if day not in {basic, parsed.isoformat()} or parsed.isoformat() != request.trade_date:
        raise RankingValidationError('file date differs from request')
    if not re.fullmatch(request.variety+r'[0-9]{2}(0[1-9]|1[0-2])', contract):
        raise RankingValidationError('invalid variety/contract YYMM token')


def _rows_for_side(contract, rank, member, quantity, change, side, format):
    member = member.strip()
    count = _int_or_none(quantity, 'quantity')
    delta = _int_or_none(change, 'change', allow_negative_change=True)
    if any(ord(c) < 32 for c in member) or (not member and (count is not None or delta is not None)):
        raise RankingValidationError('numeric facts require an explicit member')
    if count is None and delta is not None:
        raise RankingValidationError('change without known quantity')
    if side is RankingSide.VOLUME:
        return RankingRow(contract, rank, side, member, _scope_for(member), None, None, False,
                          format, volume=count, volume_change=delta)
    return RankingRow(contract, rank, side, member, _scope_for(member), count, delta,
                      count is not None, format)


def _parse_sections(payload, request, expected):
    request.validate()
    try:
        records = list(csv.reader(io.StringIO(_decode(payload)), strict=True))
    except csv.Error as exc:
        raise RankFormatError('malformed/truncated CSV quoting') from exc
    records = [r for r in records if any(v.strip() for v in r)]
    if not records or tuple(records[0]) != tuple(expected.split(',')):
        raise RankFormatError('CSV first header differs from reviewed layout')
    section = 'legacy' if expected == _LEGACY_HEADER_0 else 'named_header'
    rows, ranks, members, categories = [], set(), set(), set()
    named_contracts, legacy_contracts = set(), set()
    named_seen = section == 'named_header'
    for record in records[1:]:
        if tuple(record) == tuple(_NAMED_HEADER_0.split(',')):
            if named_seen:
                raise RankFormatError('duplicate named header')
            named_seen, section = True, 'named_header'
            continue
        if section == 'named_header':
            if tuple(record) != tuple(_NAMED_HEADER_1.split(',')):
                raise RankFormatError('complete named second header required')
            section = 'named'
            continue
        fields = 9 if section == 'legacy' else 12
        if len(record) != fields:
            raise RankFormatError(f'{section} row requires {fields} fields')
        day, contract, identity = (v.strip() for v in record[:3])
        _check_trade_date_and_contract(day, contract, request)
        if section == 'legacy':
            if identity not in _LEGACY_CATEGORY or (contract, identity) in categories:
                raise RankingValidationError('unknown/duplicate legacy category')
            categories.add((contract, identity));legacy_contracts.add(contract)
            for side, offset in [(RankingSide.VOLUME, 3), (RankingSide.LONG, 5), (RankingSide.SHORT, 7)]:
                rows.append(_rows_for_side(contract, 0, identity, record[offset], record[offset+1], side, 'legacy'))
        else:
            rank = _int_or_none(identity, 'rank')
            if rank is None or not 1 <= rank <= RANK_TOP_N or (contract, rank) in ranks:
                raise RankingValidationError('invalid or duplicate named rank')
            ranks.add((contract, rank));named_contracts.add(contract)
            for side, offset in [(RankingSide.VOLUME, 3), (RankingSide.LONG, 6), (RankingSide.SHORT, 9)]:
                row = _rows_for_side(contract, rank, record[offset], record[offset+1], record[offset+2], side, 'named')
                key = (contract, side, row.member)
                if row.member and (key in members or row.member in _LEGACY_CATEGORY):
                    raise RankingValidationError('duplicate member/side or category posing as named member')
                if row.member:members.add(key)
                rows.append(row)
    if not rows or section == 'named_header':
        raise RankFormatError('empty or truncated CSV section')
    if expected == _LEGACY_HEADER_0 and not legacy_contracts:
        raise RankFormatError('declared legacy section has no category data')
    if named_seen and not named_contracts:
        raise RankFormatError('declared named section has no ranking data')
    for contract in named_contracts:
        if {rank for c, rank in ranks if c == contract} != set(range(1, RANK_TOP_N+1)):
            raise RankingValidationError('incomplete named rank list')
    for contract in legacy_contracts:
        if {category for c, category in categories if c == contract} != _LEGACY_CATEGORY:
            raise RankingValidationError('incomplete legacy categories')
    if named_contracts and legacy_contracts and named_contracts != legacy_contracts:
        raise RankingValidationError('mixed-format contract scopes disagree')
    formats = {r.rank_format for r in rows}
    return next(iter(formats)) if len(formats) == 1 else 'mixed', rows


def parse_named(payload: bytes, request: CffexRankingsRequest) -> tuple[str, list[RankingRow]]:
    return _parse_sections(payload, request, _NAMED_HEADER_0)


def parse_legacy(payload: bytes, request: CffexRankingsRequest) -> tuple[str, list[RankingRow]]:
    return _parse_sections(payload, request, _LEGACY_HEADER_0)


def parse(payload: bytes, request: CffexRankingsRequest) -> tuple[str, list[RankingRow]]:
    kind = classify_payload(payload, request)
    if kind == 'unknown':
        raise RankFormatError('unrecognised CSV/header/encoding layout')
    if kind != 'csv':
        code = 'unavailable' if kind == 'not_found' else kind
        raise RankingResponseError(f'{kind} response; no calendar or publication conclusion inferred', code=code)
    first = _decode(payload).strip().splitlines()[0]
    return parse_named(payload, request) if first == _NAMED_HEADER_0 else parse_legacy(payload, request)


def build_record(request: CffexRankingsRequest, payload: bytes, *, run_id: str, observed_at: str, ingested_at: str,
                 publication_time=None, calendar: RankingCalendar | None = None,
                 evidence_kind: str='source_observation', supersedes_version: str | None=None,
                 revision_reason: str | None=None) -> CffexRankingsRecord:
    if not isinstance(run_id, str) or not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', run_id):
        raise RankingValidationError('run_id: explicit safe batch identifier required')
    if evidence_kind not in {'synthetic', 'source_observation'}:
        raise RankingValidationError('evidence_kind must be explicit')
    if (supersedes_version is None) != (revision_reason is None):
        raise RankingVersionError('revision requires both parent version and reason')
    if revision_reason is not None and (not isinstance(revision_reason, str) or not revision_reason.strip()):
        raise RankingVersionError('nonblank revision reason required')
    format, rows = parse(payload, request)
    event, available, session, refs, synthetic_calendar = time_fence(
        calendar, request.trade_date, observed_at, ingested_at, publication_time)
    digest = hashlib.sha256(payload).hexdigest()
    warnings = ['Published Top-N membership is not final-client holdings; contract-universe completeness unverified']
    if publication_time is None:
        warnings.append('publication_time unknown; no historical first-publication timestamp inferred')
    if synthetic_calendar or evidence_kind == 'synthetic':
        warnings.append('synthetic evidence/calendar: offline verification only, not real-source acceptance')
    if any(r.member_scope is MemberScope.UNKNOWN for r in rows):
        warnings.append('unknown member scopes excluded from known-scope nets')
    return CffexRankingsRecord(
        EXCHANGE, request.variety, request.trade_date, tuple(sorted({r.contract for r in rows})), tuple(rows),
        CffexRankingsClient().source_label(), f'payload-sha256:{digest}', digest, run_id,
        event, available, iso(aware(ingested_at, 'ingested_at')), format, tuple(warnings),
        observed_at=iso(aware(observed_at, 'observed_at')),
        publication_time=iso(aware(publication_time, 'publication_time')) if publication_time else None,
        earliest_session_date=session, calendar_refs=refs,
        evidence_kind='synthetic' if synthetic_calendar else evidence_kind,
        supersedes_version=supersedes_version, revision_reason=revision_reason)


def _response_outcome(exc, request, calendar, ingested_at):
    status = 'unavailable' if exc.code == 'unavailable' else 'response_error'
    if status == 'unavailable' and calendar is not None:
        try:
            day = calendar_day(calendar, request.trade_date, ingested_at)
            if not day.is_trading_day:status = 'no_session'
        except (RankingCalendarError, RankingValidationError):
            pass  # Remains ambiguous, never becomes closed/unpublished.
    return IngestionOutcome(status, None, (str(exc),), http_status=exc.http_status)


def ingest(client, request, *, run_id, observed_at, ingested_at, publication_time=None,
           calendar: RankingCalendar | None = None, evidence_kind='source_observation', previous=None,
           supersedes_version=None, revision_reason=None):
    try:
        request.validate()
        if not isinstance(run_id, str) or not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', run_id):
            raise RankingValidationError('run_id: explicit safe batch identifier required')
        if aware(ingested_at, 'ingested_at') < aware(observed_at, 'observed_at'):
            raise RankingValidationError('ingestion precedes observation')
        if publication_time is not None and aware(publication_time, 'publication_time') > aware(observed_at, 'observed_at'):
            raise RankingValidationError('publication cannot be in the future at observation')
        payload = client.fetch(request)
        record = build_record(request, payload, run_id=run_id, observed_at=observed_at,
                              ingested_at=ingested_at, publication_time=publication_time, calendar=calendar,
                              evidence_kind=evidence_kind, supersedes_version=supersedes_version,
                              revision_reason=revision_reason)
        if previous is not None:
            from .cffex_rankings_versions import compare_revision
            if compare_revision(previous, record) == 'duplicate_payload':
                return IngestionOutcome('duplicate_payload', None, ('original version retained; no durable registration performed',))
        elif record.supersedes_version is not None:
            raise RankingVersionError('revision requires explicit prior record')
    except RankingTransportError as exc:
        return IngestionOutcome('network_error', None, (str(exc),))
    except RankingResponseError as exc:
        return _response_outcome(exc, request, calendar, ingested_at)
    except RankingCalendarError as exc:
        return IngestionOutcome('calendar_error', None, (str(exc),))
    except RankFormatError as exc:
        return IngestionOutcome('schema_error', None, (str(exc),))
    except RankingValidationError as exc:
        return IngestionOutcome('validation_error', None, (str(exc),))
    except RankingVersionError as exc:
        return IngestionOutcome('version_error', None, (str(exc),))
    return IngestionOutcome('success', record, record.warnings)


@dataclass(frozen=True)
class MemberNetPosition:
    member: str
    member_scope: MemberScope
    long_oi: int | None
    short_oi: int | None
    net: int | None
    contract: str
    trade_date: str
    expiry_month: str  # Contract YYMM token only; exact expiry/rollover unverified.
    rollover_flag: None = None
    evidence_grade: str = 'B'
    definition: str = 'Same-member, same-scope, single-contract published Top-N long minus short; absent is unknown'


def net_positions(record: CffexRankingsRecord, *, scope: MemberScope=MemberScope.AGENT,
                  contract: str | None=None, as_of: str | None=None,
                  mode: str | None=None) -> tuple[MemberNetPosition, ...]:
    from .cffex_rankings_versions import assert_visible
    assert_visible(record, as_of=as_of, mode=mode)
    if not isinstance(scope, MemberScope) or scope not in (MemberScope.AGENT, MemberScope.PROPRIO):
        raise RankingValidationError('single known enum scope required')
    if contract is None or contract not in record.contracts:
        raise RankingValidationError('explicit contract in this record required; cross-contract aggregation not implemented')
    members = {}
    seen = set()
    for row in record.rows:
        if row.contract != contract or row.rank_format != 'named' or row.member_scope is not scope or row.side is RankingSide.VOLUME:
            continue
        key = (row.member, row.side)
        if key in seen:
            raise RankingValidationError('duplicate member/side in net input')
        seen.add(key)
        if row.member:
            members.setdefault(row.member, {})[row.side] = row.open_interest if row.open_interest_known else None
    result = []
    for member, sides in sorted(members.items()):
        long, short = sides.get(RankingSide.LONG), sides.get(RankingSide.SHORT)
        result.append(MemberNetPosition(member, scope, long, short,
                      long-short if long is not None and short is not None else None,
                      contract, record.trade_date, contract[2:]))
    return tuple(result)

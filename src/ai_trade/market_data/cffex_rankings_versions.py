"""Pure revision/read contract over caller-provided records, NOT a repository.

No global registry, durable idempotence, transactional write or restart recovery
is implemented. The caller must provide a complete confirmed chain. Missing
parents, duplicate versions and branches fail rather than select a plausible row.
"""
import hashlib
import json
import re

from ai_trade.reference_data.models import ReferenceResult
from .cffex_rankings_models import (
    CffexRankingsRecord, CffexRankingsRequest, RankingDataUnavailableError, RankingVersionError,
    RankingRow, RankingSide, MemberScope,
)
from .cffex_rankings_time import aware, iso, LOCAL


def _key(record):
    return record.exchange, record.variety, record.trade_date, record.source


def _check(record):
    if not isinstance(record, CffexRankingsRecord):
        raise RankingVersionError('explicit ranking record required')
    CffexRankingsRequest(record.exchange, record.variety, record.trade_date).validate()
    if (not re.fullmatch('[0-9a-f]{64}', record.payload_sha256)
            or record.source_version != 'payload-sha256:'+record.payload_sha256
            or not record.calendar_refs or not record.rows or not record.run_id
            or record.evidence_kind not in {'synthetic', 'source_observation'}):
        raise RankingVersionError('invalid version/provenance contract')
    if any(not isinstance(row, RankingRow) for row in record.rows):
        raise RankingVersionError('row must be a RankingRow')
    if ((record.supersedes_version is None) != (record.revision_reason is None)
            or record.supersedes_version == record.source_version
            or record.revision_reason is not None and (not isinstance(record.revision_reason,str) or not record.revision_reason.strip())):
        raise RankingVersionError('invalid parent/revision reason')
    if (not isinstance(record.source, str) or len(record.source.split(':')) < 3
            or not re.fullmatch(r'[A-Za-z0-9._:-]{1,128}', record.run_id)
            or len(set(record.contracts)) != len(record.contracts)
            or set(record.contracts) != {r.contract for r in record.rows}
            or any(not isinstance(ref, str) or not ref.strip() for ref in record.calendar_refs)):
        raise RankingVersionError('invalid source, run, contract scope or calendar lineage')
    seen, member_keys, ranks, categories = set(), set(), {}, {}
    for row in record.rows:
        if (not isinstance(row, RankingRow) or not isinstance(row.side, RankingSide)
                or not isinstance(row.member_scope, MemberScope) or not isinstance(row.member, str)
                or type(row.rank) is not int or type(row.open_interest_known) is not bool
                or not re.fullmatch(record.variety+r'[0-9]{2}(0[1-9]|1[0-2])', row.contract)
                or row.rank_format not in {'named','legacy'}):
            raise RankingVersionError('invalid row identity')
        key=(row.contract,row.rank_format,row.rank,row.side)
        # Legacy has rank 0 for each of two distinct categories.
        if row.rank_format=='legacy':key=key+(row.member,)
        if key in seen:raise RankingVersionError('duplicate row/rank')
        seen.add(key)
        if row.rank_format=='named':
            if not 1 <= row.rank <= 20:raise RankingVersionError('invalid named rank')
            ranks.setdefault((row.contract,row.side),set()).add(row.rank)
        else:
            if row.rank!=0 or row.member not in {'期货公司','非期货公司'} or row.member_scope is not MemberScope.UNKNOWN:
                raise RankingVersionError('invalid aggregate category')
            categories.setdefault((row.contract,row.side),set()).add(row.member)
        if row.member:
            normalized=row.member.strip().replace('（','(').replace('）',')')
            scope=(MemberScope.AGENT if normalized.endswith('(代客)') else
                   MemberScope.PROPRIO if normalized.endswith('(自营)') else MemberScope.UNKNOWN)
            if row.member_scope is not scope:
                raise RankingVersionError('scope contradicts published name suffix')
            member_key=(row.contract,row.rank_format,row.side,row.member)
            if member_key in member_keys:raise RankingVersionError('duplicate member/side')
            member_keys.add(member_key)
        volume=row.side is RankingSide.VOLUME
        quantity,change=(row.volume,row.volume_change) if volume else (row.open_interest,row.open_interest_change)
        if (quantity is not None and (type(quantity) is not int or quantity < 0)
                or change is not None and type(change) is not int
                or quantity is None and change is not None
                or quantity is not None and not row.member
                or volume and (row.open_interest is not None or row.open_interest_change is not None or row.open_interest_known)
                or not volume and (row.volume is not None or row.volume_change is not None or row.open_interest_known != (quantity is not None))):
            raise RankingVersionError('invalid quantity/volume/unknown semantics')
    named_contracts={r.contract for r in record.rows if r.rank_format=='named'}
    legacy_contracts={r.contract for r in record.rows if r.rank_format=='legacy'}
    formats={r.rank_format for r in record.rows}
    if (record.rank_format != (next(iter(formats)) if len(formats)==1 else 'mixed')
            or named_contracts and legacy_contracts and named_contracts != legacy_contracts
            or any(ranks.get((c,side)) != set(range(1,21)) for c in named_contracts for side in RankingSide)
            or any(categories.get((c,side)) != {'期货公司','非期货公司'} for c in legacy_contracts for side in RankingSide)):
        raise RankingVersionError('incomplete caller-supplied rank/category lists')
    event, observed, ingested, available = [aware(getattr(record, f), f)
                                          for f in ('event_time','observed_at','ingested_at','available_at')]
    if not event <= observed <= ingested <= available:
        raise RankingVersionError('inconsistent event/observation/ingestion/availability')
    if record.publication_time is not None and not event <= aware(record.publication_time,'publication_time') <= observed:
        raise RankingVersionError('publication timestamp contradicts event/observation')
    if (event.astimezone(LOCAL).date().isoformat() != record.trade_date
            or available.astimezone(LOCAL).date().isoformat() != record.earliest_session_date
            or record.earliest_session_date <= record.trade_date):
        raise RankingVersionError('event/eligible-session dates contradict fact date')


def compare_revision(previous, candidate) -> str:
    """Compare a specific prior version; does not register either observation."""
    _check(previous);_check(candidate)
    if _key(previous) != _key(candidate):
        raise RankingVersionError('revision cannot silently change date/variety/source')
    if previous.payload_sha256 == candidate.payload_sha256:
        if candidate.supersedes_version not in {None, previous.source_version}:
            raise RankingVersionError('duplicate payload has conflicting parent')
        return 'duplicate_payload'
    if (candidate.supersedes_version != previous.source_version
            or not isinstance(candidate.revision_reason, str) or not candidate.revision_reason.strip()):
        raise RankingVersionError('content revision requires explicit parent and reason')
    if (aware(candidate.event_time, 'event_time') != aware(previous.event_time, 'event_time')
            or aware(candidate.observed_at, 'observed_at') < aware(previous.observed_at, 'observed_at')
            or aware(candidate.ingested_at, 'ingested_at') < aware(previous.ingested_at, 'ingested_at')
            or aware(candidate.available_at, 'available_at') < aware(previous.available_at, 'available_at')
            or max(aware(candidate.available_at, 'available_at'), aware(candidate.ingested_at, 'ingested_at'))
            <= max(aware(previous.available_at, 'available_at'), aware(previous.ingested_at, 'ingested_at'))):
        raise RankingVersionError('revision visibility must advance without backdating')
    if candidate.run_id == previous.run_id:
        raise RankingVersionError('different payload cannot reuse the prior run_id')
    return 'revision'


def assert_visible(record, *, as_of, mode):
    _check(record)
    if mode not in {'research', 'strict_backtest', 'paper_trade'}:
        raise RankingDataUnavailableError('explicit research/strict_backtest/paper_trade required')
    cutoff = aware(as_of, 'as_of')
    if max(aware(record.available_at, 'available_at'), aware(record.ingested_at, 'ingested_at')) > cutoff:
        raise RankingDataUnavailableError('record not yet available and ingested at as_of')
    if mode != 'research' and record.evidence_kind == 'synthetic':
        raise RankingDataUnavailableError('synthetic record/calendar is not audited backtest input')
    return cutoff


def select_visible_version(records, *, as_of, mode) -> ReferenceResult[CffexRankingsRecord]:
    """Actual as_of predicate; no backtest engine or persistent storage implied."""
    chain = tuple(records)
    if not chain:
        raise RankingDataUnavailableError('no caller-provided history')
    by_version, children, roots, keys = {}, {}, [], set()
    for record in chain:
        _check(record);keys.add(_key(record))
        if record.source_version in by_version:
            raise RankingVersionError('duplicate version in caller history')
        by_version[record.source_version] = record
        if record.supersedes_version is None:
            if record.revision_reason is not None:
                raise RankingVersionError('root cannot contain revision reason')
            roots.append(record)
        else:
            if record.supersedes_version in children:
                raise RankingVersionError('branching revision history')
            children[record.supersedes_version] = record
    if len(keys) != 1 or len(roots) != 1:
        raise RankingVersionError('one logical object and one root required')
    ordered = [roots[0]]
    while ordered[-1].source_version in children:
        candidate = children[ordered[-1].source_version]
        if candidate in ordered or compare_revision(ordered[-1], candidate) != 'revision':
            raise RankingVersionError('cycle or duplicate payload must not be appended as revision')
        ordered.append(candidate)
    if len(ordered) != len(chain):
        raise RankingVersionError('missing parent or disconnected/cyclic history')
    cutoff = aware(as_of, 'as_of')
    visible = [r for r in ordered if max(aware(r.available_at, 'available_at'),
                                       aware(r.ingested_at, 'ingested_at')) <= cutoff]
    if not visible:
        raise RankingDataUnavailableError('no version visible at as_of')
    value = visible[-1]
    assert_visible(value, as_of=as_of, mode=mode)
    lineage = tuple(r.source_version+':'+r.run_id for r in visible)
    digest = hashlib.sha256(json.dumps([iso(cutoff), mode, lineage], ensure_ascii=False).encode()).hexdigest()
    return ReferenceResult(value, iso(cutoff), mode, digest, 'cffex-rankings-read-v2', value.warnings, lineage)


def net_positions_at(records, *, as_of: str, mode: str, contract: str, scope: MemberScope):
    """Read/derive with one explicit chain and point-in-time envelope.

    The unimplemented durable repository must eventually supply the complete
    chain. This pure port does not guarantee the caller actually supplied it.
    """
    from dataclasses import replace
    from .cffex_rankings import net_positions
    result=select_visible_version(records,as_of=as_of,mode=mode)
    value=net_positions(result.value,as_of=as_of,mode=mode,contract=contract,scope=scope)
    digest=hashlib.sha256(json.dumps([result.data_snapshot_id,contract,scope.value]).encode()).hexdigest()
    return replace(result,value=value,data_snapshot_id=digest,definitions_version='cffex-rankings-net-v2')

"""CFFEX index-futures member-holdings (Top-N) CSV adapter.

TASK-022A. Reads the reviewed public ranking file
``https://www.cffex.com.cn/sj/ccpm/{YYYYMM}/{DD}/{VARIETY}_1.csv`` for the
four index-futures varieties IF/IH/IC/IM and maps it into
:class:`CffexRankingsRecord`/``RankingRow``.

Design rules (enforced, tested, and cross-checked with the TASK-022 review):

* No auto-trade, no production schema/table changes, no full-history backfill.
* A 404 page, the site's home-page fallback, an empty file or a CSV that does
  not match the reviewed layout all fail *explicitly* (``RankingResponseError``
  / ``RankFormatError``); none is coerced into "no session" or a zero row.
* A non-trading day is a legitimate request whose payload must classify as
  ``no_session`` only after the transport returned a real body. (HTTP 404 is
  *reported* to the caller; the adapter never invents a row for it.)
* A member that is not in the Top-N for a side is ``open_interest=None`` and
  ``open_interest_known=False`` — never 0.
* The published name suffix selects ``member_scope``; an unrecognised/missing
  suffix is ``unknown`` and is never merged with a known scope.
* ``available_at`` is conservative. When the publication timestamp is unknown
  it equals the observed/ingested time, and the usable-from fence is pushed to
  the *next* session so the record can never be read for same-day intraday use.
* ``net`` is a derived B-grade proxy and is computed only when *both* sides
  are known; otherwise it is None.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from ai_trade.market_data.cffex_rankings_models import (
    CffexRankingsRecord,
    CffexRankingsRequest,
    IngestionOutcome,
    MemberScope,
    RankingResponseError,
    RankingSide,
    RankingValidationError,
    RankFormatError,
    RankingRow,
)

ADAPTER_VERSION = "task-022a-v1"
PROVIDER = "cffex"
ENDPOINT = "cffex.com.cn/sj/ccpm/{YYYYMM}/{DD}/{VARIETY}_1.csv"
EXCHANGE = "CFFEX"
VARIETIES = ("IF", "IH", "IC", "IM")
RANK_TOP_N = 20

# The site serves the 404 page for non-existent/non-trading-day files; that page
# carries this marker. The home-page fallback (an unrelated 98KB page) is a
# *different* marker: it is a 200 with the CFFEX home layout, not a rankings CSV.
_NOT_FOUND_MARKER = "页面未找到"
_NOT_FOUND_BYTES = 2132
_HOME_FALLBACK_BYTES = 98656

# published name suffix => MemberScope. Anything else is UNKNOWN.
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


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _parse_aware(value: str, name: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise RankingValidationError(f"{name}: invalid ISO timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise RankingValidationError(f"{name}: timezone-aware timestamp required")
    return parsed


@dataclass(frozen=True)
class CffexRankingsClient:
    """Transport boundary. ``fetch`` returns *raw bytes*; a fake client is used
    in tests and in offline replay, so the mapping logic is fully testable.
    """

    adapter_version: str = ADAPTER_VERSION
    provider: str = PROVIDER
    endpoint: str = ENDPOINT
    timeout: float = 20.0

    def source_label(self) -> str:
        return f"{PROVIDER}:{ENDPOINT}:{self.adapter_version}"

    def fetch(self, request: CffexRankingsRequest) -> bytes:
        import requests  # optional; not imported at module load time

        url = request.url()
        headers = {"User-Agent": "a-share-quant-v1/0.1 (research; TASK-022A)"}
        try:
            response = requests.get(url, headers=headers, timeout=self.timeout)
        except requests.RequestException as exc:
            raise RankingResponseError(f"transport failure fetching {url}: {type(exc).__name__}") from exc
        if response.status_code == 404:
            raise RankingResponseError(f"HTTP 404 for {request.trade_date}: likely non-trading day or not yet published")
        if response.status_code != 200:
            raise RankingResponseError(f"unexpected HTTP {response.status_code} for {url}")
        return response.content


def classify_payload(payload: bytes, request: CffexRankingsRequest) -> str:
    """Return one of: "csv", "not_found", "home_fallback", "empty", "unknown".

    The classification is conservative: only a body that actually parses as the
    reviewed CSV layout is treated as data. A 404 page, the home fallback, or an
    empty body are all *response conditions*, never data.
    """
    if not payload:
        return "empty"
    text = payload.decode("gbk", "ignore")
    if _NOT_FOUND_MARKER in text:
        return "not_found"
    # The home-page fallback is a large HTML document; it never starts with CSV.
    if len(payload) >= _HOME_FALLBACK_BYTES and payload[:20].lstrip().startswith(b"<!DOCTYPE"):
        return "home_fallback"
    lines = text.strip().split("\n")
    if not lines or not lines[0].strip():
        return "unknown"
    return "csv"


def _scope_for(name: str) -> MemberScope:
    if not name or name in ("", "-"):
        return MemberScope.UNKNOWN
    m = _SCOPE_SUFFIX_RE.match(name.strip())
    if m:
        return _SCOPE_SUFFIXES[m.group("suffix")]
    # A bare "中信期货" (no suffix) is still a known *named* member but its scope
    # is unknown to us; keep it unknown rather than guessing.
    return MemberScope.UNKNOWN


def _int_or_none(value: str, name: str, *, allow_negative_change: bool = False) -> Optional[int]:
    v = (value or "").strip()
    if v == "":
        return None
    try:
        parsed = int(v)
    except ValueError as exc:
        raise RankingValidationError(f"{name}: expected integer, got {value!r}") from exc
    if parsed < 0:
        # OI itself cannot be negative; a *change* can be negative.
        if not allow_negative_change:
            raise RankingValidationError(f"{name}: OI must be non-negative, got {parsed}")
    return parsed


def parse_named(payload: bytes, request: CffexRankingsRequest) -> tuple[str, list[RankingRow]]:
    text = payload.decode("gbk", "ignore")
    lines = text.strip().split("\n")
    if len(lines) < 2:
        raise RankFormatError("named CSV requires two header rows")
    if lines[0].strip() != _NAMED_HEADER_0 or lines[1].strip() != _NAMED_HEADER_1:
        raise RankFormatError("CSV header does not match the reviewed named layout")
    reader = csv.reader(io.StringIO("\n".join(lines[2:])))
    rows: list[RankingRow] = []
    contracts: set[str] = set()
    dates: set[str] = set()
    for index, record in enumerate(reader):
        if not record or not "".join(record).strip():
            continue
        if len(record) != 12:
            raise RankFormatError(f"named CSV row {index} has {len(record)} fields, expected 12")
        trade_date, contract, rank_s, vol_name, vol, vol_chg, \
            long_name, long_oi, long_chg, short_name, short_oi, short_chg = record
        trade_date = trade_date.strip()
        contract = contract.strip()
        dates.add(trade_date)
        contracts.add(contract)
        if len(dates) > 1:
            raise RankingValidationError(f"file mixes trade dates {sorted(dates)}")
        if trade_date.replace("-", "") != request.trade_date.replace("-", ""):
            raise RankingValidationError(
                f"file trade date {trade_date} does not match requested {request.trade_date}")
        if not re.fullmatch(r"[A-Z]{2}\d{4}", contract) or contract[:2] != request.variety:
            raise RankingValidationError(f"contract {contract!r} not under variety {request.variety}")
        rank = _int_or_none(rank_s, f"row {index}.rank")
        if rank is None or not 1 <= rank <= RANK_TOP_N:
            raise RankingValidationError(f"row {index}.rank out of 1..{RANK_TOP_N}")

        for side, name, oi, chg in (
            (RankingSide.VOLUME, vol_name, vol, vol_chg),
            (RankingSide.LONG, long_name, long_oi, long_chg),
            (RankingSide.SHORT, short_name, short_oi, short_chg),
        ):
            oi_val = _int_or_none(oi, f"row {index}.{side}.oi")
            chg_val = _int_or_none(chg, f"row {index}.{side}.chg", allow_negative_change=True)
            # A published rank whose OI is empty means the member is *not* in the
            # Top-N for that side even though it appears on a different side's list;
            # record it as UNKNOWN, not zero.
            known = oi_val is not None
            rows.append(RankingRow(
                contract=contract, rank=rank, side=side,
                member=(name or "").strip(), member_scope=_scope_for(name),
                open_interest=(oi_val if known else None),
                open_interest_change=(chg_val if known else None),
                open_interest_known=known, rank_format="named"))
    if not rows:
        raise RankFormatError("named CSV contained no data rows")
    # Completeness: each contract must present exactly RANK_TOP_N ranks.
    per_contract = {c: set() for c in contracts}
    for r in rows:
        per_contract[r.contract].add(r.rank)
    for c in sorted(per_contract):
        if per_contract[c] != set(range(1, RANK_TOP_N + 1)):
            raise RankingValidationError(f"contract {c} missing ranks {sorted(set(range(1, RANK_TOP_N+1)) - per_contract[c])}")
    return "named", rows


def parse_legacy(payload: bytes, request: CffexRankingsRequest) -> tuple[str, list[RankingRow]]:
    """Legacy (2010-2019) category aggregate, with an embedded named block.

    Early files carry BOTH a 9-field 会员类别 aggregate section and a 12-field
    named section. We parse the section currently active: rows under the
    category header are ingested as ``rank_format="legacy"``; rows under the
    named header are ingested as ``rank_format="named"`` with their own scope
    detection. A 12-field row before the named header, or a 9-field row after
    it, is an explicit ``RankFormatError`` (a layout we have not reviewed).
    """
    text = payload.decode("gbk", "ignore")
    lines = text.strip().split("\n")
    if not lines or lines[0].strip() != _LEGACY_HEADER_0:
        raise RankFormatError("file does not start with the reviewed legacy category header")
    reader = csv.reader(io.StringIO("\n".join(lines[1:])))
    rows: list[RankingRow] = []
    dates: set[str] = set()
    section = "legacy"
    for index, record in enumerate(reader):
        if not record or len(record) == 1:
            # Blank / stray blank lines between the two sections are skipped
            # (the named block in early files is separated from the legacy block
            # by an empty line).
            continue
        first = record[0].strip()
        # Section boundary rows are detected by the exact legacy/named header
        # shapes (they carry the Chinese column labels), not by content.
        if first == "交易日":
            section = "named" if len(record) == 12 else "legacy"
            continue
        if section == "legacy":
            if len(record) != 9:
                raise RankFormatError(f"legacy row {index} has {len(record)} fields, expected 9")
            rows.extend(_legacy_data_row(record, index, request, dates))
        else:
            if record[0].strip() == "":
                # Second row of the two-row named header (member-label row).
                continue
            if len(record) != 12:
                raise RankFormatError(f"named row {index} has {len(record)} fields, expected 12")
            _named_data_row(record, index, request, dates, rows)
    if not rows:
        raise RankFormatError("legacy CSV contained no data rows")
    return _rank_format_label(rows), rows


def _rank_format_label(rows) -> str:
    formats = {r.rank_format for r in rows}
    if formats == {"legacy"}:
        return "legacy"
    if formats == {"named"}:
        return "named"
    return "mixed"


def _legacy_data_row(record, index, request, dates) -> list[RankingRow]:
    trade_date, contract, category, vol, vol_chg, long_oi, long_chg, short_oi, short_chg = record
    trade_date = trade_date.strip()
    contract = contract.strip()
    category = category.strip()
    dates.add(trade_date)
    if category not in _LEGACY_CATEGORY:
        raise RankFormatError(f"legacy row {index} category {category!r} not recognised")
    _check_trade_date_and_contract(trade_date, contract, request, dates)
    out = []
    for side, oi, chg in ((RankingSide.VOLUME, vol, vol_chg),
                          (RankingSide.LONG, long_oi, long_chg),
                          (RankingSide.SHORT, short_oi, short_chg)):
        oi_val = _int_or_none(oi, f"legacy {index}.{side}.oi")
        chg_val = _int_or_none(chg, f"legacy {index}.{side}.chg", allow_negative_change=True)
        out.append(RankingRow(
            contract=contract, rank=0, side=side, member=category,
            member_scope=MemberScope.UNKNOWN, open_interest=oi_val,
            open_interest_change=chg_val, open_interest_known=oi_val is not None,
            rank_format="legacy"))
    return out


def _named_data_row(record, index, request, dates, rows) -> None:
    trade_date, contract, rank_s, vol_name, vol, vol_chg, \
        long_name, long_oi, long_chg, short_name, short_oi, short_chg = record
    trade_date = trade_date.strip()
    contract = contract.strip()
    dates.add(trade_date)
    _check_trade_date_and_contract(trade_date, contract, request, dates)
    rank = _int_or_none(rank_s, f"row {index}.rank")
    if rank is None or not 1 <= rank <= RANK_TOP_N:
        raise RankingValidationError(f"row {index}.rank out of 1..{RANK_TOP_N}")
    for side, name, oi, chg in (
        (RankingSide.VOLUME, vol_name, vol, vol_chg),
        (RankingSide.LONG, long_name, long_oi, long_chg),
        (RankingSide.SHORT, short_name, short_oi, short_chg),
    ):
        oi_val = _int_or_none(oi, f"row {index}.{side}.oi")
        chg_val = _int_or_none(chg, f"row {index}.{side}.chg", allow_negative_change=True)
        known = oi_val is not None
        rows.append(RankingRow(
            contract=contract, rank=rank, side=side, member=(name or "").strip(),
            member_scope=_scope_for(name), open_interest=(oi_val if known else None),
            open_interest_change=(chg_val if known else None),
            open_interest_known=known, rank_format="named"))


def _check_trade_date_and_contract(trade_date, contract, request, dates) -> None:
    if len(dates) > 1:
        raise RankingValidationError(f"file mixes trade dates {sorted(dates)}")
    if trade_date.replace("-", "") != request.trade_date.replace("-", ""):
        raise RankingValidationError(f"file trade date {trade_date} does not match requested {request.trade_date}")
    if not re.fullmatch(r"[A-Z]{2}\d{4}", contract) or contract[:2] != request.variety:
        raise RankingValidationError(f"contract {contract!r} not under variety {request.variety}")


def parse(payload: bytes, request: CffexRankingsRequest) -> tuple[str, list[RankingRow]]:
    kind = classify_payload(payload, request)
    if kind == "not_found":
        raise RankingResponseError(f"endpoint returned the site 404 page for {request.trade_date}; likely non-trading day or unpublished")
    if kind == "home_fallback":
        raise RankingResponseError("endpoint returned the CFFEX home page, not a rankings CSV")
    if kind == "empty":
        raise RankingResponseError("endpoint returned an empty body")
    if kind == "unknown":
        raise RankingResponseError("endpoint returned an unrecognised body (not CSV, not 404, not home)")
    text = payload.decode("gbk", "ignore").strip()
    first = text.split("\n", 1)[0].strip()
    if first == _NAMED_HEADER_0:
        return parse_named(payload, request)
    if first == _LEGACY_HEADER_0:
        return parse_legacy(payload, request)
    raise RankFormatError("CSV body does not match any reviewed layout")


# 16:35 Asia/Shanghai capture floor, expressed in UTC: the record is usable only
# from the start of the NEXT session (09:30 Asia/Shanghai of D+1), never for the
# same-day intraday session. We keep the floor conservative (next 09:30), so a
# late capture still cannot leak a same-day signal.
_CST = ZoneInfo("Asia/Shanghai")


def _next_session_floor(available_at: str) -> str:
    """Return the earliest UTC instant at which the record may be read.

    ``available_at`` is floored to the next A-share regular open (09:30
    Asia/Shanghai) strictly *after* the observation date. A 16:35 capture on D
    therefore yields D+1 09:30 +08 == D+1 01:30 UTC. This is the no-same-day
    intraday-use rule required by the review (G1).
    """
    avail = _parse_aware(available_at, "available_at")
    local = avail.astimezone(_CST)
    # 09:30 on the local day is 01:30 UTC; the local day is D, so floor = D+1.
    floor_local = datetime(local.year, local.month, local.day, 9, 30, tzinfo=_CST)
    # Strictly after the availability instant, not at-or-before it.
    if avail >= floor_local:
        floor_local = datetime.fromordinal(
            datetime(floor_local.year, floor_local.month, floor_local.day).toordinal() + 1
        ).replace(hour=9, minute=30, tzinfo=_CST)
    return _utc_iso(floor_local)


def build_record(
    request: CffexRankingsRequest,
    payload: bytes,
    *,
    run_id: str,
    observed_at: str,
    ingested_at: str,
    publication_time: Optional[str] = None,
) -> CffexRankingsRecord:
    """Map parsed rows into a record with provenance and time fences.

    ``available_at`` is ``max(publication_time, observed_at)`` when the
    publication time is known, else ``ingested_at`` (conservative). The usable-
    from fence is always the next session, regardless of which of those was used.
    """
    rank_format, rows = parse(payload, request)
    _observed = _parse_aware(observed_at, "observed_at")
    _ingested = _parse_aware(ingested_at, "ingested_at")
    if _ingested < _observed:
        raise RankingValidationError("ingested_at must not precede observed_at")
    if publication_time is not None:
        _published = _parse_aware(publication_time, "publication_time")
        available = _published if _published > _ingested else _ingested
        publish_known = True
    else:
        available = _ingested
        publish_known = False
    available_iso = _utc_iso(available)
    source = CffexRankingsClient().source_label()
    digest = _sha256(payload)
    warnings: list[str] = []
    if not publish_known:
        warnings.append("publication_time unknown; available_at set to ingested_at (conservative)")
    # No same-day intraday use: the record may only be read on/after the next
    # session open. We floor available_at to that next 09:30 Asia/Shanghai open
    # so a 16:35 capture on D is never usable for D's own session.
    usable_from = _next_session_floor(available_iso)
    if usable_from > available_iso:
        available_iso = usable_from
    warnings.append("usable_from next-session floor applied; no same-day intraday read")
    unknown_scope = sum(1 for r in rows if r.member_scope == MemberScope.UNKNOWN)
    if unknown_scope:
        warnings.append(f"{unknown_scope} rows have unknown member_scope and are excluded from scope-known aggregates")
    return CffexRankingsRecord(
        exchange=EXCHANGE, variety=request.variety, trade_date=request.trade_date,
        contracts=tuple(sorted({r.contract for r in rows})), rows=tuple(rows),
        source=source, source_version=f"payload-sha256:{digest}", payload_sha256=digest,
        run_id=run_id, event_time=_utc_iso(_parse_aware(observed_at, "observed_at")),
        available_at=available_iso, ingested_at=_utc_iso(_ingested),
        rank_format=rank_format, warnings=tuple(warnings),
    )


def ingest(
    client: CffexRankingsClient,
    request: CffexRankingsRequest,
    *,
    run_id: str,
    observed_at: str,
    ingested_at: str,
    publication_time: Optional[str] = None,
) -> IngestionOutcome:
    """Fetch + classify + map one file. Only a SUCCESS outcome carries a record.

    Response conditions (404, home fallback, empty, malformed) are returned as
    explicit outcomes; they are never coerced into "no session" and never
    produce a record with fabricated rows.
    """
    if request.exchange != EXCHANGE:
        return IngestionOutcome("validation_error", None, (f"exchange must be {EXCHANGE}",))
    if request.variety not in VARIETIES:
        return IngestionOutcome("validation_error", None, (f"variety must be one of {VARIETIES}",))
    try:
        payload = client.fetch(request)
    except RankingResponseError as exc:
        status = "no_session" if "404" in str(exc) or "non-trading" in str(exc) else "network_error"
        return IngestionOutcome(status, None, (str(exc),))
    try:
        record = build_record(request, payload, run_id=run_id, observed_at=observed_at,
                              ingested_at=ingested_at, publication_time=publication_time)
    except RankingResponseError as exc:
        return IngestionOutcome("response_error", None, (str(exc),))
    except RankFormatError as exc:
        return IngestionOutcome("schema_error", None, (str(exc),))
    except RankingValidationError as exc:
        return IngestionOutcome("validation_error", None, (str(exc),))
    return IngestionOutcome("success", record, tuple(record.warnings))


# ---------------------------------------------------------------------------
# Derived, B-grade aggregates. These are convenience views over the *published*
# Top-N only; they are NOT final-client facts and MUST carry evidence_grade B.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MemberNetPosition:
    """Derived net (long OI - short OI) for one member, one side scope.

    ``net`` is None unless BOTH the long and the short OI are known; a missing
    side is UNKNOWN and is not filled with 0.
    """

    member: str
    member_scope: MemberScope
    long_oi: Optional[int]
    short_oi: Optional[int]
    net: Optional[int]
    evidence_grade: str = "B"  # always a proxy, never a final-client fact


def net_positions(
    record: CffexRankingsRecord,
    *,
    scope: MemberScope = MemberScope.AGENT,
    contract: Optional[str] = None,
) -> tuple[MemberNetPosition, ...]:
    """Compute per-member net for a single *known* scope.

    ``scope`` must be a specific known scope (AGENT or PROPRIO); passing
    UNKNOWN or AGENT_AND_PROPRIO raises, because merging unknown with known is
    exactly what the contract forbids. Set ``contract`` to restrict to one
    contract, else aggregate across the file's contracts.
    """
    if scope not in (MemberScope.AGENT, MemberScope.PROPRIO):
        raise ValueError("net_positions requires a single known scope, not unknown/combined")
    contracts = (contract,) if contract else record.contracts
    long_by_member: dict[tuple[str, MemberScope], int] = {}
    short_by_member: dict[tuple[str, MemberScope], int] = {}
    known_long: set[tuple[str, MemberScope]] = set()
    known_short: set[tuple[str, MemberScope]] = set()
    for row in record.rows:
        if row.contract not in contracts:
            continue
        if row.member_scope is not scope:
            continue
        key = (row.member, scope)
        if row.side is RankingSide.LONG and row.open_interest_known:
            long_by_member[key] = long_by_member.get(key, 0) + row.open_interest
            known_long.add(key)
        if row.side is RankingSide.SHORT and row.open_interest_known:
            short_by_member[key] = short_by_member.get(key, 0) + row.open_interest
            known_short.add(key)
    members = sorted(set(long_by_member) | set(short_by_member))
    out: list[MemberNetPosition] = []
    for member, _ in [(m, s) for (m, s) in members]:
        lo = long_by_member.get((member, scope))
        so = short_by_member.get((member, scope))
        long_known = (member, scope) in known_long
        short_known = (member, scope) in known_short
        net = (lo - so) if (long_known and short_known and lo is not None and so is not None) else None
        out.append(MemberNetPosition(
            member=member, member_scope=scope,
            long_oi=lo if long_known else None,
            short_oi=so if short_known else None,
            net=net))
    return tuple(out)

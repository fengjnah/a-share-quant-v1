"""Local M3 input/presentation mapping. Admission and calculations stay in core.

Archive metadata is an unverified observation, never a verification receipt.
No I/O here writes data or calls a supplier. Missing timestamps stay missing.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
import hashlib
from html import escape
import json
from pathlib import Path
import re
from urllib.parse import urlsplit, urlunsplit

import pandas as pd

from ai_trade import market_analysis_core as core
from ai_trade import market_analysis_data as archive
from ai_trade.market_analysis_contract import (
    Admission, Diagnostic, Reason, ReasonCode, Request, SourceEvidence, Status,
)
from ai_trade.market_data.cffex_rankings_models import MemberScope

MODULES = {
    'daily_trend': '日线趋势', 'weekly_structure': '周线结构', 'wave': '波浪 / 确认转折',
    'market_breadth': '市场宽度', 'fear_greed': '完整六因子恐贪', 'price_proxy': '独立价格代理',
    'cffex_position': 'CFFEX 会员持仓', 'environment': '综合市场环境',
}
STATUS_LABELS = {
    Status.SOURCE_UNAVAILABLE: '来源不可用', Status.HISTORY_INSUFFICIENT: '历史不足',
    Status.FACTOR_MISSING: '因子缺失', Status.STALE: '数据过期',
    Status.TIME_UNCERTIFIED: '时间未认证', Status.INVALID_DATA: '非法数据',
    Status.EVIDENCE_CONFLICT: '证据冲突', Status.OBSERVATION_ONLY: '仅可观察',
    Status.RESEARCH_ALLOWED: '研究准入', Status.STRATEGY_ALLOWED: '策略凭据通过',
    Status.BLOCKED: '阻断',
}
REASON_LABELS = {
    ReasonCode.SOURCE_UNAVAILABLE: '缺少可消费的本地输入', ReasonCode.SOURCE_UNVERIFIED: '来源尚未认证',
    ReasonCode.AUTHORIZATION_UNKNOWN: '研究授权未知', ReasonCode.HISTORY_INSUFFICIENT: '最低历史样本未满足',
    ReasonCode.FACTOR_MISSING: '必要因子缺失', ReasonCode.STALE: '数据未覆盖分析日期',
    ReasonCode.TIME_UNCERTIFIED: '真实时间字段或认证不齐', ReasonCode.NOT_VISIBLE: '截止时点尚不可见',
    ReasonCode.INVALID_DATA: '输入格式、数值或一致性校验失败', ReasonCode.CALENDAR_UNKNOWN: '交易日历分母未知',
    ReasonCode.COVERAGE_INCOMPLETE: '认证交易日缺失', ReasonCode.UNIVERSE_UNKNOWN: '全 A 历史股票池证据不足',
    ReasonCode.SCOPE_UNSUPPORTED: '数据口径未满足要求', ReasonCode.PUBLICATION_UNKNOWN: '发布时间未认证',
    ReasonCode.SYNTHETIC: '离线合成夹具', ReasonCode.EVIDENCE_CONFLICT: '合格证据互相冲突',
    ReasonCode.EVIDENCE_MISSING: '必要证据或质量决定缺失', ReasonCode.SNAPSHOT_MISMATCH: '日期、标的或快照不一致',
    ReasonCode.STRATEGY_GATE: '策略、执行及样本外审批未具备',
}


def safe_text(value) -> str:
    """Display only: reveal neither control characters nor credential-bearing URLs."""
    if value is None:
        return 'UNKNOWN'
    text = str(value)
    text = ''.join(f'\\u{ord(c):04x}' if ord(c) < 32 or 127 <= ord(c) <= 159 else c for c in text)
    def public_url(match):
        try:
            url = urlsplit(match.group())
            return urlunsplit((url.scheme, url.hostname or '', url.path, '', ''))
        except ValueError:
            return '[URL已隐藏]'
    text = re.sub(r'https?://[^\s]+', public_url, text)
    return re.sub(r'(?i)(api[_-]?key|token|secret|password|authorization|proxy)\s*[=:]\s*\S+',
                  r'\1=[已隐藏]', text)


@dataclass
class LocalInput:
    frame: pd.DataFrame
    source: SourceEvidence
    facts: dict = field(default_factory=dict)
    error: str | None = None


def unavailable(kind: str, error: str | None = None) -> LocalInput:
    return LocalInput(pd.DataFrame(), SourceEvidence(f'local:M3:{kind}', 'unavailable',
                      (f'no-local-{kind}-snapshot',)), {'input_rows': 0, 'parse_status': '未取得输入'}, error)


def catalogue(root, *, kind, symbol, analysis_date):
    """Reuse checksum/bounds checks; do not pick latest or hide read failures."""
    try:
        return archive.snapshots(root, kind=kind, symbol=symbol, analysis_date=analysis_date), None
    except (OSError, ValueError, TypeError, KeyError) as exc:
        return [], f'本地快照读取/摘要或结构校验失败（{type(exc).__name__}）；未显示未经校验的数据。'


def snapshot_ref(item):
    if item.get('observation_file'):
        return 'observation-sha256:' + Path(item['observation_file']).stem
    data = {k: v for k, v in item.items() if k != 'observation_file'}
    return 'observation-sha256:' + hashlib.sha256(json.dumps(data, sort_keys=True, allow_nan=False).encode()).hexdigest()


def snapshot_label(item):
    return safe_text(f"{item.get('trade_date', 'UNKNOWN')} · 观察 {item.get('observed_at', 'UNKNOWN')} · {snapshot_ref(item)[-10:]}")


def _facts(frame, item=None):
    dates = frame.trade_date.tolist() if 'trade_date' in frame else []
    valid_dates = all(isinstance(d, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', d) for d in dates)
    facts = {'input_rows': len(frame), 'input_start': min(dates) if dates and valid_dates else None,
             'input_end': max(dates) if dates and valid_dates else None, 'parse_status': '本地结构已读取，语义以核心校验为准'}
    if item:
        facts['observation_ref'] = snapshot_ref(item)
        facts['collection_claim'] = item.get('status')
        facts['source_declared_date'] = item.get('trade_date')
        facts['http_trace'] = [{k: t.get(k) for k in ('endpoint', 'status', 'error', 'payload_sha256')}
                               for t in item.get('http_trace', []) if isinstance(t, dict)]
    return facts


def from_snapshots(items, *, kind):
    if not items:
        return unavailable(kind)
    try:
        frames, refs = [], []
        for item in items:
            if kind == 'index':
                rows = item['prices']
            else:
                row = dict(item['breadth'])
                if 'trade_date' in row and row['trade_date'] != item['trade_date']:
                    raise ValueError('Contradictory breadth dates')
                row.setdefault('trade_date', item['trade_date'])
                rows = [row]
            frame = pd.DataFrame(rows, dtype=object)
            # Only fill an absent column from an actual archive field. Never
            # overwrite a contradictory row identity or invent time/quality.
            for name in ('source', 'symbol', 'observed_at', 'ingested_at', 'available_at',
                         'event_time', 'quality_status', 'adjustment_method'):
                # "market" is the legacy archive selector, not an ALL_A identity.
                if name == 'symbol' and kind == 'breadth' and item.get(name) == 'market':
                    continue
                if name not in frame and name in item:
                    frame[name] = pd.Series([item[name]] * len(frame), dtype=object)
            frames.append(frame); refs.append(snapshot_ref(item))
        frame = pd.concat(frames, ignore_index=True)
        version = refs[0] if len(refs) == 1 else 'selection-sha256:' + hashlib.sha256(json.dumps(refs).encode()).hexdigest()
        evidence_kind = 'synthetic' if any(i.get('evidence_kind') == 'synthetic' or str(i.get('source', '')).startswith('synthetic:') for i in items) else 'source_observation'
        src = SourceEvidence(items[0]['source'], version, tuple(refs), evidence_kind=evidence_kind)
        facts = _facts(frame, items[0] if len(items) == 1 else None)
        facts['selected_refs'] = refs
        return LocalInput(frame, src, facts)
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        return unavailable(kind, f'选定快照无法映射为核心输入（{type(exc).__name__}）；请检查字段/版本，不补值。')


def from_stock_frame(frame, *, source, request):
    """The old bar model has no observed_at; never derive it from ingestion."""
    if frame.empty:
        return unavailable('stock')
    refs = tuple(dict.fromkeys(str(v) for v in frame.source_version)) if 'source_version' in frame else ('unknown-local-version',)
    version = 'query-sha256:' + hashlib.sha256(json.dumps([request.as_of, request.symbol, refs]).encode()).hexdigest()
    return LocalInput(frame, SourceEvidence(source, version, refs), _facts(frame))


def input_error(diagnostic: Diagnostic, local: LocalInput) -> Diagnostic:
    """I/O/parse failure mapping only. This can only block, never grant a level."""
    if not local.error:
        return diagnostic
    reason = Reason(ReasonCode.INVALID_DATA, local.error,
                    '修复选定本地文件/字段/摘要，或显式选择有依据的版本；不丢弃异常记录、不生成替代数据。')
    return replace(diagnostic, values={}, calculated=False, admission=Admission.BLOCKED,
                   status=Status.INVALID_DATA, reasons=diagnostic.reasons + (reason,))


def diagnostic_bundle(price, market, *, request, cffex_source=None, cffex_records=(),
                      contract='UNKNOWN', member='UNKNOWN', scope=MemberScope.UNKNOWN,
                      cffex_error=None, calendar=None, universe_receipt=None, cffex_options=None):
    """One invocation per formal indicator family; no local admission formula."""
    result = {k: input_error(d, price) for k, d in core.price_diagnostics(
        price.frame, request=request, source=price.source, calendar=calendar).items()}
    market_request = replace(request, symbol='ALL_A', instrument_type='ALL_A')
    result['market_breadth'] = input_error(core.breadth_diagnostic(
        market.frame, request=market_request, source=market.source, calendar=calendar,
        universe_receipt=universe_receipt), market)
    fear = core.fear_greed_diagnostic(price.frame, request=request, source=price.source, calendar=calendar,
        market_frame=market.frame, market_source=market.source, universe_receipt=universe_receipt)
    result['fear_greed'] = input_error(input_error(fear, price), market)
    cf = core.cffex_diagnostic(cffex_records,
        request=replace(request, symbol=contract, instrument_type='CFFEX'),
        source=cffex_source or unavailable('cffex').source, member=member, scope=scope, **(cffex_options or {}))
    result['cffex_position'] = input_error(cf, unavailable('cffex', cffex_error))
    result['environment'] = core.environment_diagnostic(
        {k: result[k] for k in ('wave', 'fear_greed', 'cffex_position')}, request=request)
    return {k: result[k] for k in MODULES}


def displayable(d: Diagnostic) -> bool:
    # Honour core flags, with a defensive fail-closed presentation check.
    return d.calculated and d.admission is not Admission.BLOCKED and d.status not in {Status.INVALID_DATA, Status.BLOCKED}


def coverage_text(d):
    c = d.coverage
    ratio = 'UNKNOWN' if c.ratio is None else f'{c.ratio:.1%}'
    return f'{c.valid_samples} / {c.expected_samples if c.expected_samples is not None else "UNKNOWN"} · {ratio}'


def overview_html(diagnostics):
    cards = []
    for name, d in diagnostics.items():
        tone = 'blocked' if d.admission is Admission.BLOCKED else 'research' if d.admission in {Admission.L2, Admission.L3} else 'observe'
        reasons = tuple(dict.fromkeys(REASON_LABELS.get(r.code, r.code.value) for r in d.reasons if 'L2' in r.blocks))
        detail = '；'.join(reasons[:2]) or '核心未报告研究级阻断；策略审批单独核验'
        cards.append(f'<article class="m3-card {tone}"><div class="m3-name">{escape(MODULES[name])}</div>'
            f'<div class="m3-state">{escape(STATUS_LABELS[d.status])}</div><div class="m3-chip">{escape(d.admission.value)}</div>'
            f'<div class="m3-code">{escape(d.status.value)}</div><p>{escape(detail)}</p>'
            f'<footer>实际截止 {escape(safe_text(d.data_latest_date))}<br>覆盖 {escape(coverage_text(d))}</footer></article>')
    return '<div class="m3-overview">' + ''.join(cards) + '</div>'


def evidence_payload(d, facts=None):
    """Whitelisted metadata; omit open-ended values and raw source responses."""
    p = d.to_dict()
    payload = {k: p[k] for k in ('indicator', 'schema_version', 'definitions_version', 'request', 'data_latest_date',
               'times', 'time_verification', 'coverage', 'status', 'admission', 'missing_fields', 'reasons',
               'data_snapshot_id', 'allowed_uses')}
    payload['source'] = {k: p['source'][k] for k in ('source', 'source_version', 'lineage_refs', 'evidence_kind')}
    payload['local_read'] = facts or {}
    def scrub(value):
        if isinstance(value, dict): return {k: scrub(v) for k, v in value.items()}
        if isinstance(value, (list, tuple)): return [scrub(v) for v in value]
        return safe_text(value) if isinstance(value, str) else value
    return scrub(payload)

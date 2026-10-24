"""Read-only M3 presentation of the official core diagnostics."""
from datetime import date, datetime, timedelta
import json
import os
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st

from ai_trade import market_analysis_data as archive
from ai_trade.demo_data import SOURCES, make_request, read_bars
from ai_trade.market_analysis_contract import Request, SourceEvidence
from ai_trade.market_analysis_view import (
    MODULES, REASON_LABELS, STATUS_LABELS, catalogue, coverage_text,
    diagnostic_bundle, displayable, evidence_payload, from_snapshots,
    from_stock_frame, overview_html, safe_text, snapshot_label, snapshot_ref, unavailable,
)
from ai_trade.market_data.cffex_rankings_models import MemberScope

CSS = """<style>
.m3-overview{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,220px),1fr));gap:12px}
.m3-card{min-width:0;overflow-wrap:anywhere;border:1px solid #7775;border-left:4px solid #bc8227;border-radius:10px;padding:14px}
.m3-card.blocked{border-left-color:#cc5353}.m3-card.research{border-left-color:#39856e}
.m3-name{font-weight:600}.m3-state{font-size:1.2rem;margin-top:8px}.m3-code,.m3-card footer{font-size:.8rem;opacity:.8}
.m3-chip{display:inline-block;border:1px solid #8886;border-radius:4px;padding:2px 6px;margin:6px 0}
.m3-card p{font-size:.85rem;min-height:2.6em}
@media(max-width:600px){.m3-overview{grid-template-columns:1fr}.m3-card p{min-height:0}}
</style>"""


def _collect(key, operation):
    try:
        with st.spinner('正在进行一次有时限的真实查询……'):
            item = operation()
        st.session_state[key] = (True, f"采集已保存：数据日 {safe_text(item.get('trade_date'))}；观察 {safe_text(item.get('observed_at'))}。保存不代表研究准入，请显式选择版本。")
    except Exception as exc:
        st.session_state[key] = (False, f'接口失败/超时/格式校验未通过（{type(exc).__name__}），未生成替代数据。下方仅为先前本地保存版本。')


def _feedback(key):
    if key in st.session_state:
        ok, message = st.session_state[key]
        (st.success if ok else st.error)(message)


def _choose(items, label):
    if not items:
        st.caption(label + '：没有已保存版本 / UNKNOWN')
        return None
    return st.selectbox(label, items, index=0 if len(items) == 1 else None,
                        format_func=snapshot_label, placeholder='多个版本，请明确选择；不默认取最新')


def _details(name, diagnostic, facts):
    d = diagnostic
    with st.expander('证据详情 · ' + MODULES[name]):
        rows = {
            '分析日期': d.request.analysis_date, '读取截止 as_of': d.request.as_of,
            '实际最新数据日期（核心可见）': d.data_latest_date,
            '来源': d.source.source, '源版本 / 选定观察版本': d.source.source_version,
            **d.times, '时间认证': d.source.time_verification.status.value,
            '有效样本数': d.coverage.valid_samples, '预期样本数': d.coverage.expected_samples,
            '覆盖率': coverage_text(d), '覆盖率分母定义': d.coverage.denominator,
            '覆盖分母引用': ', '.join(d.coverage.denominator_refs) or None,
            '输入日期起': facts.get('input_start'), '输入日期止': facts.get('input_end'),
            '原始输入行数': facts.get('input_rows'), '本地读取 / 解析状态': facts.get('parse_status'),
            '来源声明截止日期（未认证）': facts.get('source_declared_date'),
        }
        st.dataframe(pd.DataFrame([{'字段': k, '值': safe_text(v)} for k, v in rows.items()]),
                     hide_index=True, width='stretch')
        st.code('缺失字段：' + (', '.join(d.missing_fields) or '核心未列出；不代表证据完整') +
                '\n缺失日期：' + (', '.join(d.coverage.missing_dates) or ('UNKNOWN（分母未知）' if d.coverage.expected_samples is None else '核心未列出')) +
                '\n缺失因子：' + ', '.join(d.values.get('missing_factors', ())), language='text', wrap_lines=True)
        groups = {}
        for r in d.reasons:
            groups.setdefault(r.code, []).append(r)
        for code, reasons in groups.items():
            st.write(REASON_LABELS.get(code, code.value) + f' · {code.value} · {len(reasons)}项')
            for r in dict.fromkeys((reasons[0], reasons[-1])):
                st.code(safe_text(r.detail) + '\n最小补救 / 升级条件：' + safe_text(r.next_action),
                        language='text', wrap_lines=True)
        payload = evidence_payload(d, facts)
        st.json({k: v for k, v in payload.items() if k != 'reasons'}, expanded=False)
        st.download_button('下载脱敏诊断 · ' + MODULES[name],
                           json.dumps(payload, ensure_ascii=False, allow_nan=False, indent=2),
                           file_name=f'm3-{name}-diagnostic.json', mime='application/json', key='m3-diagnostic-' + name)


def _values(name, d):
    """Render values only under core's flags, without calculating a direction."""
    if not displayable(d):
        if name == 'fear_greed':
            st.metric('完整六因子分数', 'UNKNOWN')
        elif name == 'price_proxy':
            st.metric('独立价格代理分数', 'UNKNOWN')
        elif name == 'environment':
            st.metric('综合结论', 'UNKNOWN（研究级证据未齐或冲突）')
        st.info('数值不可用：' + STATUS_LABELS[d.status] + '；原因及最小补救动作见证据详情。')
        return
    # Core's serialised values normalise nonfinite missing values to null.
    v = d.to_dict()['values']
    if name == 'daily_trend':
        st.write('派生方向（研究解释）：' + safe_text(v.get('direction')))
        st.dataframe(pd.DataFrame([{'核心指标': k, '值': safe_text(v.get(k))} for k in ('close', 'MA20', 'MA60')]), hide_index=True, width='stretch')
    elif name == 'weekly_structure':
        st.write('已结束周结构：' + safe_text(v.get('direction')))
        weeks = pd.DataFrame(v.get('weeks', []))
        if not weeks.empty:
            st.line_chart(weeks.set_index('last_date')[['close']])
    elif name == 'wave':
        st.caption('研究解释：多情景并存，确认转折不等于唯一波浪计数或预测。')
        st.dataframe(pd.DataFrame(v.get('scenarios', [])), hide_index=True, width='stretch')
        pivots = pd.DataFrame(v.get('pivots', [])[-30:])
        if not pivots.empty:
            st.scatter_chart(pivots, x='trade_date', y='price', color='kind')
            st.caption('仅显示最近30个核心已确认转折；确认输入日期及首次可用时间保留。')
            st.dataframe(pivots, hide_index=True, width='stretch')
    elif name == 'market_breadth':
        st.caption('原始来源事实：供应商家数；样本日期覆盖不等于全 A 股票池覆盖。')
        st.dataframe(pd.DataFrame(v.get('reported_counts', [])[-10:]), hide_index=True, width='stretch')
        st.json({'全A口径认证': v.get('all_a_scope_verified'), '全A覆盖分子/分母': v.get('universe_coverage')}, expanded=False)
    elif name in ('fear_greed', 'price_proxy'):
        full = name == 'fear_greed'
        score = v.get('score')
        st.metric('完整六因子分数' if full else '独立价格代理分数', 'UNKNOWN' if score is None else f'{score:.1f}')
        st.caption('派生指标：完整六因子缺一不计分。' if full else '派生指标：独立价格口径，不能替代完整恐贪或进入综合情绪方向。')
        st.write('历史分位：' + safe_text(v.get('percentile')))
        st.dataframe(pd.DataFrame([{'因子': k, '核心值': safe_text(x)} for k, x in v.get('factors', {}).items()]), hide_index=True, width='stretch')
        series = pd.DataFrame(v.get('historical_scores', []))
        field = 'score' if full else 'index_proxy'
        if not series.empty and field in series and series[field].notna().sum() >= 2:
            st.line_chart(series.set_index('trade_date')[[field]])
    elif name == 'environment':
        st.metric('综合结论（研究解释）', safe_text(v.get('conclusion')))
        st.json(v.get('components', {}))


def render(db):
    root = db.config.path.parent
    read_only = getattr(db.config, 'read_only', False) or os.environ.get('AI_TRADE_READ_ONLY') == '1'
    as_of = archive.now()
    st.markdown(CSS, unsafe_allow_html=True)
    st.title('M3 市场分析')
    st.caption('本地已保存事实 → 核心派生指标 → 研究解释 → 准入证据；进入和刷新页面不采集。')
    st.warning('核心已合并，但独立 H 复核 Issue #37 尚未执行。页面、CI 或 L2/L3 不代表来源认证、预测能力或实盘许可。live_trading=false。')
    overview = st.container()
    with st.expander('本地数据与读取条件', expanded=True):
        day = st.date_input('M3 分析日期', date(2026, 10, 16),
            max_value=datetime.fromisoformat(as_of).astimezone(ZoneInfo('Asia/Shanghai')).date()-timedelta(days=1)).isoformat()
        st.caption(f'分析日 {day}｜本次读取时点 {as_of}；读取时钟不等于历史首次可得时间。')
        mode = st.selectbox('时间可见性模式', ['research', 'strict_backtest', 'paper_trade'])
        target = st.radio('趋势标的类型', ['指数', '股票'], horizontal=True)
        price = unavailable('price')
        if target == '指数':
            symbol = archive.INDEX_SYMBOLS[st.selectbox('指数', list(archive.INDEX_SYMBOLS))]
            if st.button('查询真实指数历史', key='m3-index', disabled=read_only):
                _collect('m3-price-status', lambda: archive.collect_public(root, 'index', symbol))
            items, error = catalogue(root, kind='index', symbol=symbol, analysis_date=day)
            selected = _choose(items, '指数本地版本')
            price = from_snapshots([selected] if selected else [], kind='index')
            price.error = error or price.error
            request = Request(day, as_of, symbol, 'INDEX', mode)
        else:
            symbol = st.text_input('M3 股票代码', '600000')
            source = SOURCES[st.selectbox('M3 股票行情源', list(SOURCES), index=1)]
            request = Request(day, as_of, symbol.strip() or 'UNKNOWN', 'STOCK', mode)
            try:
                query = make_request(symbol, date.fromisoformat(day)-timedelta(days=800), date.fromisoformat(day))
                price = from_stock_frame(read_bars(db, query, source=source, as_of=as_of), source=source, request=request)
            except Exception as exc:
                price = unavailable('stock', f'本地股票读取/请求校验失败（{type(exc).__name__}）；未生成替代数据。')
            st.caption('只读 M1/M2 已入库行情；observed_at 缺失保留 UNKNOWN。')
        _feedback('m3-price-status')
        if st.button('查询真实市场宽度快照', key='m3-breadth', disabled=read_only):
            _collect('m3-breadth-status', lambda: archive.collect_public(root, 'breadth', 'market'))
        _feedback('m3-breadth-status')
        items, error = catalogue(root, kind='breadth', symbol='market', analysis_date=day)
        selected = st.multiselect('宽度本地版本（逐日显式选择；重复日期交由核心拒绝）', items,
                                  default=items if len(items) == 1 else [], format_func=snapshot_label)
        market = from_snapshots(selected, kind='breadth')
        market.error = error or market.error
        variety = st.selectbox('股指期货品种', ['IF', 'IH', 'IC', 'IM'])
        key = f'm3-cffex-status:{variety}:{day}'
        if st.button('查询该日真实CFFEX榜单', key='m3-cffex', disabled=read_only):
            _collect(key, lambda: archive.collect_cffex(root, variety, day))
        _feedback(key)
        items, cf_error = catalogue(root, kind='cffex', symbol=variety, analysis_date=day)
        item = _choose(items, 'CFFEX 本地版本')
        scope = MemberScope(st.selectbox('会员口径', [s.value for s in MemberScope]))
        contract = member = 'UNKNOWN'
        cf_source = None
        cf_facts = {'input_rows': 0, 'parse_status': '没有已保存榜单；缺文件不代表休市或零持仓'}
        if item:
            try:
                rows = archive.ranking_rows(item)
                contracts = sorted({r.contract for r in rows})
                contract = st.selectbox('合约范围（单合约，禁止默认跨月相加）', contracts,
                                        index=0 if len(contracts) == 1 else None) or 'UNKNOWN'
                names = sorted({r.member for r in rows if r.contract == contract and r.member_scope == scope and r.member})
                member = st.selectbox('会员（不推定未知席位身份）', names, index=0 if len(names) == 1 else None) or 'UNKNOWN'
                cf_source = SourceEvidence(item['source'], snapshot_ref(item), (snapshot_ref(item),),
                    evidence_kind='synthetic' if item.get('evidence_kind') == 'synthetic' or item['source'].startswith('synthetic:') else 'source_observation')
                cf_facts = {k: item.get(k) for k in ('trade_date', 'observed_at', 'ingested_at', 'available_at', 'format', 'payload_sha256')}
                cf_facts.update(source_declared_date=item.get('trade_date'), input_rows=len(rows),
                    parse_status='原始 CSV 已解析；缺正式 CffexRankingsRecord 版本/日历/时点证据，未构造替代记录')
            except Exception as exc:
                cf_error = f'持仓本地文件读取/解析失败（{type(exc).__name__}）；未显示未经校验的数据。'
        st.caption('CFFEX 仅为会员席位，不能解释为国家队或最终客户真实仓位。原始文件不等于正式版本记录。')
        cf_facts.update(contract=contract, member=member, member_scope=scope.value, time_verification='UNKNOWN')
        st.dataframe(pd.DataFrame([{'持仓元数据': k, '值': safe_text(v)} for k, v in cf_facts.items()]), hide_index=True, width='stretch')
    diagnostics = diagnostic_bundle(price, market, request=request, cffex_source=cf_source,
        contract=contract, member=member, scope=scope, cffex_error=cf_error)
    with overview:
        st.subheader('数据质量与准入总览')
        st.markdown(overview_html(diagnostics), unsafe_allow_html=True)
    for name, d in diagnostics.items():
        st.subheader(MODULES[name])
        st.write(f'{STATUS_LABELS[d.status]} · {d.status.value} · {d.admission.value}')
        st.caption(f'分析 {d.request.analysis_date}｜实际截止 {safe_text(d.data_latest_date)}｜覆盖 {coverage_text(d)}')
        _values(name, d)
        if name == 'cffex_position':
            # Stored raw facts remain inspectable when research diagnostics
            # block. This does not upgrade the diagnostic or its allowed uses.
            from ai_trade.market_analysis_cffex_page import render_cffex_holdings
            render_cffex_holdings(db=db)
        facts = cf_facts if name == 'cffex_position' else market.facts if name == 'market_breadth' else price.facts
        if name == 'fear_greed':
            facts = {'price_input': price.facts, 'market_input': market.facts, **price.facts}
        elif name == 'environment':
            facts = {'inputs': 'wave / fear_greed / cffex_position；对应快照引用见核心组件'}
        _details(name, d, facts)
    with st.expander('准入说明与未完成边界'):
        st.write('L1：仅观察；L2：研究；L3：仍须独立策略、执行及样本外审批。级别和状态来自核心诊断。')
        st.code('live_trading=false', language='text')
        st.write('核心独立 H（Issue #37）、真实来源认证、生产准入与样本外验证尚未完成。刷新失败不生成模拟数据；完整恐贪不以价格代理补齐。')

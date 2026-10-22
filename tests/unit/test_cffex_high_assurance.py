"""Adversarial tests with explicit synthetic inputs; no vendor calls or raw data."""
from dataclasses import replace
from unittest.mock import Mock

import pytest

from test_cffex_rankings import (
    _build, _ingest, _net, _req, named, legacy, SyntheticCalendar, HEADER0, HEADER1,
)
from ai_trade.market_data import cffex_rankings as cr
from ai_trade.market_data.cffex_rankings_models import (
    CffexRankingsRequest, MemberScope, RankingResponseError, RankingSide,
    RankingValidationError, RankFormatError, RankingCalendarError,
    RankingVersionError, RankingDataUnavailableError, RankingTransportError,
)
from ai_trade.market_data.cffex_rankings_versions import compare_revision, select_visible_version

TIMES = dict(run_id='synthetic-run', observed_at='2026-10-16T08:35:00Z', ingested_at='2026-10-16T08:35:00Z')


@pytest.mark.parametrize('variety', ['IF', 'IH', 'IC', 'IM'])
def test_all_request_paths(variety):
    assert _req(variety).url() == f'https://www.cffex.com.cn/sj/ccpm/202610/16/{variety}_1.csv'


@pytest.mark.parametrize('day', ['20261016', '2026-1-16', '2026-02-30', '../2026-10-16', '', None])
def test_invalid_request_never_reaches_transport(day):
    client=Mock()
    result=cr.ingest(client,CffexRankingsRequest('CFFEX','IF',day),**TIMES)
    assert result.status=='validation_error'
    client.fetch.assert_not_called()


@pytest.mark.parametrize('mutation', ['duplicate_rank','duplicate_member','rank_zero','rank_21','month_00',
    'month_13','cross_date','cross_variety','negative_quantity','invalid_number','orphan_change','anonymous_quantity',
    'truncated','junk_line','header_drift','duplicate_header','invalid_encoding'])
def test_named_rejects_structural_corruption(mutation):
    lines=named(contracts=['IF2611']).decode('gbk').splitlines()
    if mutation=='duplicate_rank':lines.append(lines[2])
    if mutation=='duplicate_member':
        row=lines[3].split(',');row[6]='甲会员(代客)';lines[3]=','.join(row)
    if mutation in {'rank_zero','rank_21'}:lines[2]=lines[2].replace(',1,',',0,' if mutation=='rank_zero' else ',21,',1)
    if mutation in {'month_00','month_13'}:lines[2]=lines[2].replace('IF2611','IF2600' if mutation=='month_00' else 'IF2613')
    if mutation=='cross_date':lines[2]=lines[2].replace('20261016','20261015')
    if mutation=='cross_variety':lines[2]=lines[2].replace('IF2611','IH2611')
    if mutation in {'negative_quantity','invalid_number','orphan_change','anonymous_quantity'}:
        row=lines[2].split(',')
        if mutation=='anonymous_quantity':row[6]=''
        else:row[7]={'negative_quantity':'-1','invalid_number':'1_000','orphan_change':''}[mutation]
        lines[2]=','.join(row)
    if mutation=='truncated':lines.pop()
    if mutation=='junk_line':lines.append('unexpected trailer')
    if mutation=='header_drift':lines[1]=lines[1].replace('持买单量','持仓总额')
    if mutation=='duplicate_header':lines.append(HEADER0)
    payload=('\n'.join(lines)+'\n').encode('gbk')+(b'\x81' if mutation=='invalid_encoding' else b'')
    with pytest.raises((RankFormatError,RankingValidationError)):cr.parse(payload,_req('IF'))


@pytest.mark.parametrize('mutation',['wrong_header','missing_second_header','duplicate_rank','truncated_named',
                                      'duplicate_category','missing_category','junk','unknown_category'])
def test_mixed_rejects_same_corruption(mutation):
    lines=legacy('2026-10-16','IF2611').decode('gbk').splitlines()
    if mutation=='wrong_header':lines[3]=lines[3].replace('排名','错误',1)
    if mutation=='missing_second_header':lines.pop(4)
    if mutation=='duplicate_rank':lines.append(lines[5])
    if mutation=='truncated_named':lines.pop()
    if mutation=='duplicate_category':lines.insert(2,lines[1])
    if mutation=='missing_category':lines.pop(2)
    if mutation=='junk':lines.append('trailer')
    if mutation=='unknown_category':lines[1]=lines[1].replace('期货公司','不明类别')
    with pytest.raises((RankFormatError,RankingValidationError)):
        cr.parse(('\n'.join(lines)+'\n').encode('gbk'),_req('IF'))


def test_utf8_bom_quoted_member_and_separate_volume():
    text=named(contracts=['IF2611']).decode('gbk').replace('甲会员(代客)','"甲,会员(代客)"')
    format,rows=cr.parse(b'\xef\xbb\xbf'+text.encode('utf-8'),_req('IF'))
    assert format=='named' and sum(r.member=='甲,会员(代客)' for r in rows)==2
    vol=next(r for r in rows if r.rank==1 and r.side is RankingSide.VOLUME)
    assert (vol.volume,vol.volume_change)==(4999,1)
    assert (vol.open_interest,vol.open_interest_change,vol.open_interest_known)==(None,None,False)
    long=next(r for r in rows if r.rank==1 and r.side is RankingSide.LONG)
    assert (long.open_interest,long.open_interest_change,long.volume)==(2999,-4286,None)


def test_zero_missing_and_scope_nets_are_distinct():
    record=_build(_req('IF'),named(),**TIMES)
    assert next(n for n in _net(record,contract='IF2610') if n.member=='甲会员(代客)').net==0
    one=_net(record,contract='IF2611')
    assert next(n for n in one if n.member=='单侧多(代客)').net is None
    assert [n.member for n in _net(record,contract='IF2611',scope=MemberScope.PROPRIO)]==['乙会员(自营)']
    assert all(n.contract=='IF2611' and n.trade_date=='2026-10-16' and n.expiry_month=='2611'
               and n.rollover_flag is None and n.evidence_grade=='B' for n in one)
    for invalid in [None,'IF2612x','IH2611']:
        with pytest.raises(RankingValidationError):_net(record,contract=invalid)
    payload=named(contracts=['IF2611']).decode('gbk').replace('甲会员(代客)','甲会员').encode('gbk')
    unknown=_build(_req('IF'),payload,**TIMES)
    assert not any(n.member=='甲会员' for n in _net(unknown,contract='IF2611'))
    pure=legacy('2026-10-16','IF2611').split(HEADER0.encode('gbk'))[0]
    aggregate=_build(_req('IF'),pure,**TIMES)
    assert aggregate.rank_format=='legacy' and _net(aggregate,contract='IF2611')==()


@pytest.mark.parametrize('when,expected',[
    ('2026-10-16T08:35:00Z','2026-10-19'),('2026-10-18T08:35:00Z','2026-10-19'),
    ('2026-10-19T00:00:00Z','2026-10-19'),('2026-10-19T01:30:00Z','2026-10-19'),
    ('2026-10-19T01:31:00Z','2026-10-20')])
def test_weekend_and_late_acquisition(when,expected):
    record=_build(_req('IF'),named(),run_id='late',observed_at=when,ingested_at=when)
    assert record.earliest_session_date==expected and record.available_at.startswith(expected+'T01:30:00')
    assert record.event_time=='2026-10-16T07:00:00.000000+00:00'
    assert record.observed_at!=record.event_time and record.publication_time is None


def test_synthetic_holiday_range_and_first_session():
    record=_build(_req('IF','2026-09-30'),named(day='2026-09-30'),run_id='holiday',
                  observed_at='2026-09-30T08:35:00Z',ingested_at='2026-09-30T08:35:00Z')
    assert record.earliest_session_date=='2026-10-09' and len(record.calendar_refs)==10


@pytest.mark.parametrize('case',['none','missing','wrong_exchange','future_knowledge','source_error'])
def test_missing_calendar_fails_closed(case):
    from ai_trade.reference_data.models import CalendarSourceError
    base=SyntheticCalendar()
    if case=='missing':del base.days['2026-10-17']
    class Port:
        def get_day(self,**kwargs):
            if case=='source_error':raise CalendarSourceError('synthetic failure')
            item=base.get_day(**kwargs)
            if case=='wrong_exchange':return replace(item,exchange='SH')
            if case=='future_knowledge':return replace(item,available_at='2027-01-01T00:00:00Z')
            return item
    with pytest.raises(RankingCalendarError):
        cr.build_record(_req('IF'),named(),calendar=None if case=='none' else Port(),**TIMES)


@pytest.mark.parametrize('published',['2026-10-16T06:59:00Z','2026-10-16T08:36:00Z','2026-10-16T08:30:00'])
def test_no_invented_or_future_publication(published):
    with pytest.raises(RankingValidationError):_build(_req('IF'),named(),publication_time=published,**TIMES)


def test_actual_read_and_net_gate():
    record=_build(_req('IF'),named(),**TIMES)
    for mode in ['research','strict_backtest','paper_trade']:
        with pytest.raises(RankingDataUnavailableError):
            cr.net_positions(record,contract='IF2611',as_of='2026-10-19T01:29:59Z',mode=mode)
    assert _net(record,contract='IF2611',as_of='2026-10-19T09:30:00+08:00')
    with pytest.raises(RankingDataUnavailableError):
        cr.net_positions(record,contract='IF2611',as_of=record.available_at,mode='strict_backtest')
    with pytest.raises(RankingDataUnavailableError):cr.net_positions(record,contract='IF2611')


def pair():
    first=_build(_req('IF'),named(),**TIMES)
    second=_build(_req('IF'),named().replace(b',2999,',b',3999,',1),run_id='correction',
        observed_at='2026-10-19T08:35:00Z',ingested_at='2026-10-19T08:35:00Z',
        supersedes_version=first.source_version,revision_reason='synthetic correction')
    return first,second


def test_revision_read_preserves_old_cutoff_and_evidence():
    first,second=pair()
    assert compare_revision(first,second)=='revision'
    old=select_visible_version([second,first],as_of='2026-10-19T01:30:00Z',mode='research')
    new=select_visible_version([first,second],as_of='2026-10-20T01:30:00Z',mode='research')
    assert old.value==first and new.value==second and len(old.lineage_refs)==1 and len(new.lineage_refs)==2
    with pytest.raises(RankingDataUnavailableError):
        select_visible_version([first,second],as_of='2026-10-19T01:29:59Z',mode='research')


def test_duplicate_is_not_durable_registration():
    first,_=pair();client=Mock();client.fetch.return_value=named()
    result=_ingest(client,_req('IF'),previous=first,run_id='repeated',
                   observed_at='2026-10-19T08:35:00Z',ingested_at='2026-10-19T08:35:00Z')
    assert result.status=='duplicate_payload' and result.record is None
    assert first.run_id=='synthetic-run' and first.earliest_session_date=='2026-10-19'
    assert _ingest(client,_req('IF'),**TIMES).status=='success'  # No hidden global registry.


@pytest.mark.parametrize('case',['missing_parent','fork','duplicate','wrong_source','same_run','backdated','no_reason'])
def test_revision_conflicts_fail_closed(case):
    first,second=pair()
    if case=='missing_parent':chain=[second]
    elif case=='fork':chain=[first,second,replace(second,run_id='fork')]
    elif case=='duplicate':chain=[first,first]
    else:
        changes={'wrong_source':{'source':'another:provider:v1'},'same_run':{'run_id':first.run_id},
                 'backdated':{'available_at':first.available_at,'ingested_at':first.ingested_at,'observed_at':first.observed_at},
                 'no_reason':{'revision_reason':None}}[case]
        chain=[first,replace(second,**changes)]
    with pytest.raises(RankingVersionError):
        select_visible_version(chain,as_of='2026-10-21T01:30:00Z',mode='research')


def session_mock(monkeypatch, *, status=200, media='text/csv', chunks=(), error=None):
    import requests
    response=Mock(status_code=status,headers={'Content-Type':media});response.iter_content.return_value=iter(chunks)
    session=Mock();session.get.return_value=response
    if error is not None:session.get.side_effect=error
    manager=Mock();manager.__enter__=Mock(return_value=session);manager.__exit__=Mock(return_value=False)
    monkeypatch.setattr(requests,'Session',lambda:manager)
    return session,response


@pytest.mark.parametrize('status,code',[(404,'unavailable'),(302,'redirect'),(429,'http_error'),(503,'http_error')])
def test_http_single_get_no_redirect_no_retry(monkeypatch,status,code):
    session,response=session_mock(monkeypatch,status=status)
    with pytest.raises(RankingResponseError) as error:cr.CffexRankingsClient(timeout=1).fetch(_req('IF'))
    assert error.value.code==code and error.value.http_status==status and session.get.call_count==1
    args=session.get.call_args.kwargs
    assert args['verify'] is True and args['allow_redirects'] is False and args['timeout']==(1,1)
    assert session.mount.call_args.args[1].max_retries.total==0
    response.close.assert_called_once()


def test_transport_chain_retained_credentials_not_reported(monkeypatch):
    import requests
    secret=requests.exceptions.SSLError('https://user:secret@proxy.invalid/?token=hidden')
    session_mock(monkeypatch,error=secret)
    with pytest.raises(RankingTransportError) as e:cr.CffexRankingsClient().fetch(_req('IF'))
    assert e.value.__cause__ is secret and 'secret' not in str(e.value)
    result=_ingest(cr.CffexRankingsClient(),_req('IF'),**TIMES)
    assert result.status=='network_error' and result.record is None
    assert all('secret' not in i and 'token' not in i for i in result.issues)


@pytest.mark.parametrize('case',['content_type','oversized','truncated_stream','valid'])
def test_transport_body_bounds_and_resource_release(monkeypatch,case):
    import requests
    chunks=[named()] if case!='oversized' else [b'x'*(cr.MAX_PAYLOAD_BYTES+1)]
    session,response=session_mock(monkeypatch,media='text/html' if case=='content_type' else 'text/csv',chunks=chunks)
    if case=='truncated_stream':response.iter_content.side_effect=requests.exceptions.ChunkedEncodingError('synthetic truncation')
    if case=='valid':assert cr.CffexRankingsClient().fetch(_req('IF'))==named()
    else:
        with pytest.raises((RankingResponseError,RankingTransportError)):cr.CffexRankingsClient().fetch(_req('IF'))
    response.close.assert_called_once()


@pytest.mark.parametrize('timeout',[0,-1,True,float('nan'),float('inf'),121,'20'])
def test_timeout_bounded(timeout):
    with pytest.raises(RankingValidationError):cr.CffexRankingsClient(timeout=timeout)


@pytest.mark.parametrize('calendar,day,expected',[(None,'2026-10-16','unavailable'),
    (SyntheticCalendar(),'2026-10-16','unavailable'),(SyntheticCalendar(),'2026-10-17','no_session')])
def test_404_requires_independent_calendar(calendar,day,expected):
    client=Mock();client.fetch.side_effect=RankingResponseError('HTTP 404; unknown cause',code='unavailable',http_status=404)
    result=cr.ingest(client,_req('IF',day),calendar=calendar,**TIMES)
    assert result.status==expected and result.http_status==404 and result.record is None


@pytest.mark.parametrize('body,expected',[(b'','response_error'),(b'<html>404</html>','response_error'),
    ('页面未找到'.encode('gbk'),'unavailable'),(b'hello,changed,columns','schema_error')])
def test_200_body_failure_is_not_valid_empty_data(body,expected):
    client=Mock();client.fetch.return_value=body
    result=cr.ingest(client,_req('IF'),**TIMES)
    assert result.status==expected and result.record is None


def test_sqlite_contract_remains_existing_schema_only(database):
    from ai_trade.storage.schema import MIGRATIONS
    with database.connection() as conn:
        assert conn.execute('SELECT max(version) FROM schema_migrations').fetchone()[0]==len(MIGRATIONS)
        assert conn.execute('PRAGMA foreign_keys').fetchone()[0]==1
        assert conn.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
        assert conn.execute("SELECT count(*) FROM sqlite_master WHERE name='futures_rankings'").fetchone()[0]==0


@pytest.mark.parametrize('case',['duplicate_row','missing_side','wrong_format','negative_quantity','missing_volume','bad_publication'])
def test_read_gate_revalidates_caller_constructed_record(case):
    record=_build(_req('IF'),named(),**TIMES)
    if case=='duplicate_row':record=replace(record,rows=record.rows+(record.rows[0],))
    if case=='missing_side':record=replace(record,rows=tuple(r for r in record.rows if r.side is not RankingSide.SHORT))
    if case=='wrong_format':record=replace(record,rank_format='legacy')
    if case=='negative_quantity':
        rows=list(record.rows);i=next(i for i,r in enumerate(rows) if r.side is RankingSide.LONG)
        rows[i]=replace(rows[i],open_interest=-1);record=replace(record,rows=tuple(rows))
    if case=='missing_volume':
        rows=list(record.rows);rows[0]=replace(rows[0],volume=None);record=replace(record,rows=tuple(rows))
    if case=='bad_publication':record=replace(record,publication_time='2027-01-01T00:00:00Z')
    with pytest.raises(RankingVersionError):_net(record,contract='IF2611')


def test_unknown_calendar_times_are_calendar_errors_and_no_run_no_request():
    class Invalid(SyntheticCalendar):
        def get_day(self,**kwargs):return replace(super().get_day(**kwargs),closes_at=None)
    result=_ingest(Mock(fetch=Mock(return_value=named())),_req('IF'),calendar=Invalid(),**TIMES)
    assert result.status=='calendar_error'
    client=Mock()
    assert cr.ingest(client,_req('IF'),**{**TIMES,'run_id':''}).status=='validation_error'
    client.fetch.assert_not_called()


def test_derived_read_selects_the_visible_revision_not_the_latest_payload():
    from ai_trade.market_data.cffex_rankings_versions import net_positions_at
    first,second=pair()
    old=net_positions_at([first,second],as_of='2026-10-19T01:30:00Z',mode='research',contract='IF2611',scope=MemberScope.AGENT)
    new=net_positions_at([first,second],as_of='2026-10-20T01:30:00Z',mode='research',contract='IF2611',scope=MemberScope.AGENT)
    assert next(n.net for n in old.value if n.member=='甲会员(代客)')==1000
    assert next(n.net for n in new.value if n.member=='甲会员(代客)')==2000
    assert old.data_snapshot_id!=new.data_snapshot_id


def test_scope_tampering_and_self_revision_are_rejected_by_read():
    first,_=pair();rows=list(first.rows)
    i=next(i for i,r in enumerate(rows) if r.member=='乙会员(自营)' and r.side is RankingSide.LONG)
    rows[i]=replace(rows[i],member_scope=MemberScope.AGENT)
    for record in [replace(first,rows=tuple(rows)),replace(first,supersedes_version=first.source_version,revision_reason='bad')]:
        with pytest.raises(RankingVersionError):_net(record,contract='IF2611')


@pytest.mark.parametrize('missing',['named','legacy'])
def test_declared_mixed_section_cannot_silently_disappear(missing):
    lines=legacy('2026-10-16','IF2611').decode('gbk').splitlines()
    truncated=lines[:5] if missing=='named' else [lines[0],*lines[3:]]
    payload=('\n'.join(truncated)+'\n').encode('gbk')
    with pytest.raises(RankFormatError):cr.parse(payload,_req('IF'))
    client=Mock();client.fetch.return_value=payload
    outcome=_ingest(client,_req('IF'),**TIMES)
    assert outcome.status=='schema_error' and outcome.record is None

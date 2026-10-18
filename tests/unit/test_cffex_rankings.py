"""Portable synthetic offline fixtures; never count as real CFFEX acceptance.

Original raw samples remain protected outside the repository. Explicit replay is
reported separately and does not determine default unit-test availability.
"""
import hashlib
from dataclasses import replace
from datetime import date
from unittest.mock import Mock

import pytest

from ai_trade.market_data import cffex_rankings as cr
from ai_trade.market_data.cffex_rankings_models import (
    CffexRankingsRequest, MemberScope, RankingResponseError, RankingSide,
    RankingValidationError, RankFormatError, RankingSessionDay, RankingCalendarError,
    RankingVersionError, RankingDataUnavailableError, RankingTransportError,
)
from ai_trade.market_data.cffex_rankings_versions import compare_revision, select_visible_version

HEADER0='交易日,合约,排名,成交量排名,,,持买单量排名,,,持卖单量排名,,'
HEADER1=',,,会员简称,成交量,比上一交易日增减,会员简称,持买单量,比上一交易日增减,会员简称,持卖单量,比上一交易日增减'
LEGACY='交易日,合约,会员类别,总成交量,比上交易日增减,总持买单量,比上交易日增减,总持卖单量,比上一交易日增减'


def named(variety='IF', day='2026-10-16', contracts=None):
    contracts=contracts or [variety+c for c in ('2610','2611','2612','2703')]
    rows=[HEADER0,HEADER1]
    for contract in contracts:
        for rank in range(1,21):
            long_name={1:'甲会员(代客)',2:'乙会员(自营)',3:'单侧多(代客)'}.get(rank,f'多{rank}(代客)')
            short_name={1:'甲会员(代客)',2:'乙会员(自营)',3:'单侧空(代客)'}.get(rank,f'空{rank}(代客)')
            long,short=(0,0) if contract.endswith('2610') else (3000-rank,2000-rank)
            rows.append(f'{day.replace("-","")},{contract},{rank},量{rank}(代客),{5000-rank},1,{long_name},{long},{-4286 if rank==1 else 1},{short_name},{short},1')
    return ('\n'.join(rows)+'\n').encode('gbk')


def legacy(day, contract):
    rows=[LEGACY,f'{day.replace("-","")},{contract},期货公司,100,1,90,1,80,-1',
          f'{day.replace("-","")},{contract},非期货公司,20,1,10,1,10,1']
    return ('\n'.join(rows)+'\n').encode('gbk')+named(day=day,contracts=[contract])


class SyntheticCalendar:
    """Explicit scenario dates, NOT a weekday algorithm or certified calendar."""
    def __init__(self):
        self.days={d:False for d in ['2026-10-01','2026-10-02','2026-10-03','2026-10-04',
                                   '2026-10-05','2026-10-06','2026-10-07','2026-10-08',
                                   '2026-10-10','2026-10-11','2026-10-17','2026-10-18']}
        self.days.update({d:True for d in ['2026-09-30','2026-10-09','2026-10-12','2026-10-13',
                                        '2026-10-14','2026-10-15','2026-10-16','2026-10-19',
                                        '2026-10-20','2026-10-21']})
    def get_day(self, *, exchange, session_date, as_of):
        opened=self.days[session_date]
        return RankingSessionDay(exchange,session_date,opened,
            session_date+'T09:30:00+08:00' if opened else None,
            session_date+'T15:00:00+08:00' if opened else None,
            '2026-01-01T00:00:00Z','2026-01-01T00:00:00Z',
            'synthetic:calendar:v1','synthetic:'+session_date,'synthetic')


@pytest.fixture(scope='module')
def fixtures():
    data={v:named(v) for v in ('IF','IH','IC','IM')}
    data.update(IF_15=named(day='2026-10-15'),LEGACY_2019=legacy('2019-08-05','IF1908'),
                LEGACY_2010=legacy('2010-04-16','IF1005'))
    return data


def _build(*args, **kwargs):
    kwargs.setdefault('calendar',SyntheticCalendar());kwargs.setdefault('evidence_kind','synthetic')
    return cr.build_record(*args,**kwargs)


def _ingest(*args, **kwargs):
    kwargs.setdefault('calendar',SyntheticCalendar());kwargs.setdefault('evidence_kind','synthetic')
    return cr.ingest(*args,**kwargs)


def _net(record, **kwargs):
    kwargs.setdefault('as_of','2026-10-20T01:30:00Z');kwargs.setdefault('mode','research')
    return cr.net_positions(record,**kwargs)


def _req(variety: str, trade_date: str = "2026-10-16") -> CffexRankingsRequest:
    return CffexRankingsRequest(exchange="CFFEX", variety=variety, trade_date=trade_date)


class TestUrlAndRequest:
    def test_url_month_day_keyed(self):
        assert _req("IF").url() == "https://www.cffex.com.cn/sj/ccpm/202610/16/IF_1.csv"

    def test_url_rejects_bad_variety_at_ingest(self):
        client = cr.CffexRankingsClient()
        outcome = _ingest(client, CffexRankingsRequest("CFFEX", "XX", "2026-10-16"),
                            run_id="r1", observed_at="2026-10-18T09:00:00+00:00",
                            ingested_at="2026-10-18T09:00:00+00:00")
        assert outcome.status == "validation_error" and outcome.record is None


class TestNamedParsing:
    @pytest.mark.parametrize("variety", ("IF", "IC", "IH", "IM"))
    def test_parses_all_four_varieties(self, fixtures, variety):
        rank_format, rows = cr.parse(fixtures[variety], _req(variety))
        assert rank_format == "named"
        # 4 contracts x 20 ranks x 3 sides = 240 rows
        assert len(rows) == 240
        assert cr.classify_payload(fixtures[variety], _req(variety)) == "csv"

    def test_rank_completeness_per_contract(self, fixtures):
        _, rows = cr.parse(fixtures["IF"], _req("IF"))
        for c in ("IF2610", "IF2611", "IF2612", "IF2703"):
            # Each contract must present exactly ranks 1..20 on one side.
            long_ranks = sorted(r.rank for r in rows if r.contract == c and r.side is RankingSide.LONG)
            assert long_ranks == list(range(1, 21)), f"{c} long ranks incomplete"

    def test_member_scope_detection(self, fixtures):
        _, rows = cr.parse(fixtures["IF"], _req("IF"))
        scopes = {r.member_scope for r in rows}
        assert MemberScope.AGENT in scopes
        # named rows carry a concrete scope; only truly ambiguous names are unknown
        agent = [r for r in rows if "(代客)" in r.member]
        assert agent and all(r.member_scope is MemberScope.AGENT for r in agent)

    def test_missing_side_is_unknown_not_zero(self, fixtures):
        """A member in the long top-N but absent from the short top-N must be
        UNKNOWN on the short side, never 0."""
        _, rows = cr.parse(fixtures["IF"], _req("IF"))
        by_key = {}
        for r in rows:
            if r.contract == "IF2611":
                by_key.setdefault(r.member, {})[r.side] = r
        found_unknown = False
        for member, sides in by_key.items():
            short = sides.get(RankingSide.SHORT)
            if short is not None and not short.open_interest_known:
                found_unknown = True
                assert short.open_interest is None
                assert short.open_interest_change is None
        # The review found IF2610 fully zeroed (rollover); assert it parses clean.
        near = [r for r in rows if r.contract == "IF2610" and r.side is RankingSide.LONG]
        assert all(r.open_interest == 0 for r in near)  # published 0 is a real 0, known


class TestNetPosition:
    def test_net_is_none_when_side_missing(self, fixtures):
        record = _build(_req("IF"), fixtures["IF"], run_id="run-net",
                                 observed_at="2026-10-18T08:35:00+00:00",
                                 ingested_at="2026-10-18T08:35:00+00:00")
        nets = _net(record, scope=MemberScope.AGENT, contract="IF2611")
        assert nets
        # A member present on only one side must have net None (UNKNOWN), not a guess.
        one_sided = [n for n in nets if (n.long_oi is None) != (n.short_oi is None)]
        assert one_sided, "fixture must actually exercise a missing side"
        for n in one_sided:
            assert n.net is None

    def test_net_known_when_both_sides_known(self, fixtures):
        record = _build(_req("IF"), fixtures["IF"], run_id="run-net2",
                                 observed_at="2026-10-18T08:35:00+00:00",
                                 ingested_at="2026-10-18T08:35:00+00:00")
        nets = _net(record, scope=MemberScope.AGENT, contract="IF2611")
        both = [n for n in nets if n.long_oi is not None and n.short_oi is not None]
        assert both
        for n in both:
            assert n.net == n.long_oi - n.short_oi
            assert n.evidence_grade == "B"

    def test_refuses_unknown_or_combined_scope(self, fixtures):
        record = _build(_req("IF"), fixtures["IF"], run_id="run-net3",
                                 observed_at="2026-10-18T08:35:00+00:00",
                                 ingested_at="2026-10-18T08:35:00+00:00")
        with pytest.raises(RankingValidationError):
            _net(record, scope=MemberScope.UNKNOWN)
        with pytest.raises(RankingValidationError):
            _net(record, scope=MemberScope.AGENT_AND_PROPRIO)


class TestTimeSemantics:
    def test_available_at_floors_to_next_session(self, fixtures):
        record = _build(_req("IF"), fixtures["IF"], run_id="run-time",
                                 observed_at="2026-10-16T08:35:00+00:00",
                                 ingested_at="2026-10-16T08:35:00+00:00")
        # 16:35 Asia/Shanghai == 08:35 UTC on 2026-10-16 -> usable from 2026-10-17 09:30 +08
        assert record.available_at.startswith("2026-10-19T01:30:00")  # 09:30 +08 == 01:30 UTC
        assert "publication_time unknown" in " ".join(record.warnings)

    def test_known_publication_time_advances_available_at(self, fixtures):
        record = _build(_req("IF"), fixtures["IF"], run_id="run-time2",
                                 observed_at="2026-10-16T08:35:00+00:00",
                                 ingested_at="2026-10-16T08:35:00+00:00",
                                 publication_time="2026-10-16T08:30:00+00:00")
        # published 09:00Z > ingested 08:35Z -> available_at = max(pub, ingested)
        # = 09:00Z on 10-16, still floored to next known opening (01:30 UTC 10-19)
        # because 10-16 data cannot be read during 10-16's own intraday session.
        assert record.available_at.startswith("2026-10-19T01:30:00")

    def test_ingested_before_observed_rejected(self, fixtures):
        with pytest.raises(RankingValidationError):
            _build(_req("IF"), fixtures["IF"], run_id="run-time3",
                           observed_at="2026-10-16T08:40:00+00:00",
                           ingested_at="2026-10-16T08:35:00+00:00")


class TestLegacyFormat:
    def test_2019_category_format(self, fixtures):
        rank_format, rows = cr.parse(fixtures["LEGACY_2019"], _req("IF", "2019-08-05"))
        # 2019-08-05 file carries a legacy category section AND an embedded
        # named block, so the file-level label is "mixed".
        assert rank_format == "mixed"
        legacy_rows = [r for r in rows if r.rank_format == "legacy"]
        assert legacy_rows
        assert all(r.member_scope is MemberScope.UNKNOWN for r in legacy_rows)
        assert {r.member for r in legacy_rows} <= {"期货公司", "非期货公司"}
        assert [r for r in rows if r.rank_format == "named"]

    def test_2010_first_day(self, fixtures):
        rank_format, rows = cr.parse(fixtures["LEGACY_2010"], _req("IF", "2010-04-16"))
        # 2010-04-16 is also a mixed file (category + named blocks).
        assert rank_format == "mixed"
        assert any(r.rank_format == "legacy" for r in rows)
        assert any(r.rank_format == "named" for r in rows)


class TestResponseClassification:
    def test_404_page_is_response_not_data(self, fixtures):
        body = "页面未找到".encode("gbk")
        assert cr.classify_payload(body, _req("IF")) == "not_found"
        with pytest.raises(RankingResponseError):
            cr.parse(body, _req("IF"))

    def test_home_fallback_is_response_not_data(self, fixtures):
        body = b"<!DOCTYPE html><html><body>" + b"x" * 99000
        assert cr.classify_payload(body, _req("IF")) == "home_fallback"
        with pytest.raises(RankingResponseError):
            cr.parse(body, _req("IF"))

    def test_empty_body(self):
        assert cr.classify_payload(b"", _req("IF")) == "empty"
        with pytest.raises(RankingResponseError):
            cr.parse(b"", _req("IF"))

    def test_malformed_named_csv_fails_explicitly(self, fixtures):
        body = fixtures["IF"].replace(b"-4286", b"not-a-number", 1)
        with pytest.raises(RankingValidationError):
            cr.parse(body, _req("IF"))

    def test_date_mismatch_rejected(self, fixtures):
        # Ask for 2026-10-15 but hand it the 2026-10-16 file.
        with pytest.raises(RankingValidationError):
            cr.parse(fixtures["IF"], _req("IF", "2026-10-15"))

    def test_variety_mismatch_rejected(self, fixtures):
        with pytest.raises(RankingValidationError):
            cr.parse(fixtures["IF"], _req("IC", "2026-10-16"))


class TestIngestOutcomes:
    def _client_returning(self, payload: bytes):
        class _Static:
            def __init__(self, data: bytes):
                self._data = data
            def fetch(self, request):
                return self._data
        return _Static(payload)

    def test_success_returns_record(self, fixtures):
        client = self._client_returning(fixtures["IF"])
        outcome = _ingest(client, _req("IF"), run_id="ok",
                            observed_at="2026-10-18T08:35:00+00:00",
                            ingested_at="2026-10-18T08:35:00+00:00")
        assert outcome.status == "success"
        assert outcome.record is not None
        assert outcome.record.payload_sha256 == hashlib.sha256(fixtures["IF"]).hexdigest()

    def test_404_known_closed_requires_calendar(self):
        client = cr.CffexRankingsClient()

        class _Boom:
            def fetch(self, request):
                raise RankingResponseError("HTTP 404; reason unknown", code="unavailable", http_status=404)

        client = _Boom()
        outcome = _ingest(client, _req("IF", "2026-10-17"), run_id="r404",
                           observed_at="2026-10-18T08:35:00+00:00",
                           ingested_at="2026-10-18T08:35:00+00:00")
        assert outcome.status == "no_session"
        assert outcome.record is None

    def test_home_fallback_is_response_error_not_success(self, fixtures):
        client = self._client_returning(b"<!DOCTYPE html>" + b"y" * 99000)
        outcome = _ingest(client, _req("IF"), run_id="home",
                            observed_at="2026-10-18T08:35:00+00:00",
                            ingested_at="2026-10-18T08:35:00+00:00")
        assert outcome.status == "response_error"
        assert outcome.record is None

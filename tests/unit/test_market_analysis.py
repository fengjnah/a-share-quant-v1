"""Synthetic hand-checks, isolated files and causal-prefix counterexamples for M3."""
from datetime import date, timedelta
import math

import pandas as pd
import pytest

from ai_trade.market_analysis import (
    WEIGHTS, contract_label, environment, extreme_outcomes, fear_greed,
    member_position, past_percentile, wave_scenarios,
)
from ai_trade.market_analysis_data import save_snapshot, snapshots
from ai_trade.market_data.cffex_rankings_models import MemberScope as Scope, RankingRow, RankingSide as Side
from ai_trade.demo_data import persistent_workbench_root

ASOF = "2026-10-18T16:00:00+00:00"


def prices(n=100):
    return pd.DataFrame([dict(trade_date=(date(2026, 1, 1)+timedelta(days=i)).isoformat(),
        open=100+i/5+math.sin(i)*3, close=100+i/5+math.sin(i)*3,
        high=102+i/5+math.sin(i)*3, low=98+i/5+math.sin(i)*3,
        source="synthetic:unit:m3", symbol="synthetic-index", observed_at=ASOF,
        amount_cny=100000.+i*100) for i in range(n)])


def run(function, f, **kw):
    return function(f, analysis_date=kw.pop("analysis_date", f.trade_date.max()), as_of=kw.pop("as_of", ASOF), **kw)


def row(side, quantity, **kw):
    return RankingRow(kw.pop("contract", "IF2611"), 1, side, kw.pop("member", "中信期货(代客)"),
                      kw.pop("scope", Scope.AGENT), quantity, kw.pop("change", 2), quantity is not None, "named")


def position(rows, **kw):
    return member_position(rows, contract=kw.pop("contract", "IF2611"), member="中信期货(代客)", scope=kw.pop("scope", Scope.AGENT))


def test_net_and_published_change_are_same_member_contract_scope():
    rows = [row(Side.LONG, 100, change=8), row(Side.SHORT, 130, change=-5)]
    p = position(rows)
    assert p["net"] == -30 and p["net_change"] == 13


@pytest.mark.parametrize("short,expected", [(0, 0), (None, None)])
def test_true_zero_is_separate_from_unknown(short, expected):
    assert position([row(Side.LONG, 0), row(Side.SHORT, short, change=None)])["net"] == expected


def test_other_scope_contract_member_and_absent_side_are_never_combined():
    rows = [row(Side.LONG, 100), row(Side.SHORT, 40, contract="IF2612"),
            row(Side.SHORT, 50, scope=Scope.PROPRIO), row(Side.SHORT, 60, member="其他(代客)")]
    assert position(rows)["short"] is None
    assert position(rows)["net"] is None
    for scope in (Scope.AGENT_AND_PROPRIO, Scope.UNKNOWN):
        assert position(rows, scope=scope)["net"] is None
    with pytest.raises(ValueError):
        position(rows, contract="IC2611")
    assert "2026-11" in contract_label("IF2611") and "未认证" in contract_label("IF2611")


def test_duplicate_ranking_refused():
    with pytest.raises(ValueError):
        position([row(Side.LONG, 100), row(Side.LONG, 200)])


def test_wave_cutoff_and_confirmation_use_only_already_available_prices():
    f = prices()
    cutoff = f.trade_date.iloc[49]
    before = run(wave_scenarios, f.iloc[:50])
    after = run(wave_scenarios, f, analysis_date=cutoff)
    pd.testing.assert_frame_equal(before["pivots"], after["pivots"])
    assert (after["pivots"].confirmed_date <= cutoff).all()
    assert set(after["pivots"].confirmed_observed_at) == {ASOF}
    assert (pd.to_datetime(after["pivots"].confirmed_date)-pd.to_datetime(after["pivots"].trade_date)).dt.days.min() == 3
    assert before["direction"] == "数据不足" and before["scenarios"].empty
    with pytest.raises(ValueError, match="尚不可见"):
        run(wave_scenarios, f, as_of="2026-10-17T00:00:00Z")


def test_week_sample_excludes_current_week():
    f = prices(200)
    result = run(wave_scenarios, f)
    assert (result["weekly"].index < pd.Period(f.trade_date.iloc[-1], freq="W-SUN")).all()


@pytest.mark.parametrize("n", [1, 6, 20, 39])
def test_insufficient_history_never_fabricates_score(n):
    result = run(fear_greed, prices(n))
    assert result.score.isna().all() and result.index_proxy.isna().all()
    assert extreme_outcomes(result).empty


def test_past_percentile_excludes_current_and_future_samples():
    series = pd.Series([1.]*20+[2., 1000000.])
    result = past_percentile(series)
    assert result.iloc[:20].isna().all()
    assert result.iloc[20] == 100
    assert past_percentile(pd.Series([1.]*21)).iloc[-1] == 50


def test_factor_formula_complete_score_and_missing_breadth():
    f = prices()
    proxy = run(fear_greed, f)
    assert proxy.score.isna().all() and pd.notna(proxy.index_proxy.iloc[-1])
    assert proxy.coverage.iloc[-1] == pytest.approx(.70)
    breadth = pd.DataFrame([dict(trade_date=f.trade_date.iloc[-1], observed_at=ASOF,
        advances=60, declines=30, flat=10, limit_up=3, limit_down=1)])
    full = run(fear_greed, f, breadth=breadth)
    assert full["上涨占比"].iloc[-1] == 60 and full["涨停占比"].iloc[-1] == 75
    assert full.score.iloc[:-1].isna().all()
    assert full.score.iloc[-1] == pytest.approx(sum(full[k].iloc[-1]*w for k, w in WEIGHTS.items()))
    assert full.coverage.iloc[-1] == pytest.approx(1)
    f = f.drop(columns="amount_cny")
    missing_amount = run(fear_greed, f, breadth=breadth)
    assert pd.isna(missing_amount.score.iloc[-1])
    assert missing_amount.coverage.iloc[-1] == pytest.approx(.95)


def test_fear_greed_future_append_does_not_rewrite_history():
    f = prices()
    a = run(fear_greed, f.iloc[:70])
    b = run(fear_greed, f)
    pd.testing.assert_frame_equal(a, b.iloc[:70].reset_index(drop=True))


def test_breadth_wrong_date_or_invisible_is_not_backfilled():
    f = prices()
    b = pd.DataFrame([dict(trade_date="2026-01-02", observed_at=ASOF,
                          advances=1, declines=1, flat=0, limit_up=0, limit_down=0)])
    result = run(fear_greed, f, breadth=b)
    assert result["上涨占比"].notna().sum() == 1
    assert result["涨停占比"].isna().all()
    b.loc[0, "observed_at"] = "2027-01-01T00:00:00Z"
    with pytest.raises(ValueError, match="尚不可见"):
        run(fear_greed, f, breadth=b)


@pytest.mark.parametrize("values,expected", [
    (("偏多", "偏空", "数据不足"), "证据冲突"),
    (("偏多", "中性", "数据不足"), "数据不足"),
    (("偏多", "偏多", "中性"), "偏强"),
    (("偏空", "偏空", "中性"), "偏弱"),
    (("中性", "中性", "中性"), "震荡"),
])
def test_combined_evidence_can_conflict_or_be_insufficient(values, expected):
    assert environment(*values) == expected


def test_archive_preserves_observations_and_refuses_tampering(tmp_path):
    item = dict(kind="index", symbol="sh000300", trade_date="2026-10-16", observed_at=ASOF)
    path = save_snapshot(tmp_path, item)
    save_snapshot(tmp_path, dict(item, observed_at="2026-10-19T00:00:00Z"))
    assert len(snapshots(tmp_path, kind="index", symbol="sh000300", analysis_date="2026-10-15")) == 2
    path.write_bytes(b"{}")
    with pytest.raises(ValueError, match="摘要"):
        snapshots(tmp_path, kind="index", symbol="sh000300", analysis_date="2026-10-16")


def test_persistent_store_rejects_relative_and_temporary_demo_paths(tmp_path):
    with pytest.raises(ValueError, match="绝对路径"):
        persistent_workbench_root("relative-workbench")
    with pytest.raises(ValueError, match="临时目录"):
        persistent_workbench_root(str(tmp_path))

"""Synthetic SQLite fixtures only; these tests perform no network requests."""
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path
import tempfile
from unittest.mock import Mock

import pytest

from ai_trade.data_access.models import DataUnavailableError, IntegrityError, ValidationError
from ai_trade.demo_data import SOURCES, chart_data, existing_demo_root, make_request, read_bars, verify_written


NOW = datetime(2026, 10, 18, 12, tzinfo=timezone.utc)
SOURCE = SOURCES["腾讯（备用候选）"]


@pytest.mark.parametrize("symbol", ["600000", "600000.sh", "000001.SZ"])
def test_request_uses_existing_adapter_validation(symbol):
    request = make_request(symbol, date(2026, 10, 14), date(2026, 10, 16), now=NOW)
    assert request.adjustment_method == "none"


@pytest.mark.parametrize("symbol,start,end", [
    ("600000.SZ", date(2026, 10, 14), date(2026, 10, 16)),
    ("bad", date(2026, 10, 14), date(2026, 10, 16)),
    ("600000", date(2026, 10, 16), date(2026, 10, 14)),
    ("600000", date(2026, 10, 14), date(2026, 10, 18)),
])
def test_invalid_inputs_never_reach_storage_or_vendor(symbol, start, end):
    with pytest.raises(ValidationError):
        make_request(symbol, start, end, now=NOW)


def test_filtered_read_and_both_charts_use_same_validated_values(database, repository, bar):
    first = replace(bar, source=SOURCE)
    second = replace(bar, trade_date="2026-10-15", event_time="2026-10-15T15:00:00+08:00",
                     source=SOURCE, source_version="observation-2", volume=2000, close=10.5)
    other_source = replace(first, source=SOURCES["东方财富（主源）"])
    repository.write_many([first, second, other_source], run_id="synthetic-view")
    req = make_request("600000", date(2026, 10, 14), date(2026, 10, 16), now=NOW)
    bars = read_bars(database, req, source=SOURCE, as_of=NOW.isoformat())
    prices, volume = chart_data(bars)
    assert bars.trade_date.tolist() == ["2026-10-15", "2026-10-16"]
    assert prices.close.tolist() == bars.close.tolist() == [10.5, 11.0]
    assert volume.volume_shares.tolist() == bars.volume_shares.tolist() == [2000, 1000]
    assert bars.source.unique().tolist() == [SOURCE]
    assert bars.run_id.unique().tolist() == ["synthetic-view"]
    narrow = replace(req, end_date="2026-10-15")
    assert len(read_bars(database, narrow, source=SOURCE, as_of=NOW.isoformat())) == 1
    assert verify_written(repository, (first, second)) == 2
    with database.connection() as conn:
        assert conn.execute("select count(*) from ingestion_runs").fetchone()[0] == 1


def test_empty_read_does_not_create_a_run(database):
    req = make_request("600000", date(2026, 10, 14), date(2026, 10, 16), now=NOW)
    assert read_bars(database, req, source=SOURCE, as_of=NOW.isoformat()).empty
    with database.connection() as conn:
        assert conn.execute("select count(*) from ingestion_runs").fetchone()[0] == 0


def test_future_or_quarantined_values_are_not_displayed(database, repository, bar):
    original = replace(bar, source=SOURCE)
    repository.write_many([original], run_id="synthetic-original")
    req = make_request("600000", date(2026, 10, 14), date(2026, 10, 16), now=NOW)
    with pytest.raises(DataUnavailableError):
        read_bars(database, req, source=SOURCE, as_of="2026-10-16T07:00:00+00:00")
    changed = replace(original, source_version="correction", supersedes_version=original.source_version,
                      quality_status="quarantined", available_at="2026-10-17T09:00:00+08:00",
                      ingested_at="2026-10-17T09:01:00+08:00")
    repository.write_many([changed], run_id="synthetic-correction")
    with pytest.raises(DataUnavailableError):
        read_bars(database, req, source=SOURCE, as_of=NOW.isoformat())


def test_readback_must_match_all_fields(bar):
    repository = Mock()
    repository.get_bar.return_value.bar = replace(bar, volume=bar.volume + 1)
    with pytest.raises(IntegrityError, match="不一致"):
        verify_written(repository, (bar,))


def test_reopen_only_existing_temp_demo_database(tmp_path):
    with tempfile.TemporaryDirectory(prefix="a-share-quant-demo-") as folder:
        root = Path(folder)
        with pytest.raises(ValueError, match="缺少"):
            existing_demo_root(str(root))
        (root / "demo.sqlite3").touch()
        assert existing_demo_root(str(root)) == root.resolve()
    (tmp_path / "demo.sqlite3").touch()
    with pytest.raises(ValueError, match="只能"):
        existing_demo_root(str(tmp_path))

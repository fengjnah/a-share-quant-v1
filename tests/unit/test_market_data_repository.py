"""Atomic batches, explicit identities/sources and point-in-time revisions."""

import sqlite3
from dataclasses import replace

import pytest

from ai_trade.data_access.models import (
    DataUnavailableError, DuplicateRecordError, IntegrityError, ValidationError,
)
from ai_trade.data_access.validation import validate_bar


def counts(database):
    with database.connection() as conn:
        return tuple(conn.execute(f"SELECT count(*) FROM {name}").fetchone()[0]
                     for name in ("instruments", "daily_bars", "daily_bar_versions", "ingestion_runs"))


def revised(bar, **changes):
    return replace(bar, source_version="observation-2", supersedes_version=bar.source_version,
                   available_at="2026-10-17T10:00:00+08:00",
                   ingested_at="2026-10-17T10:01:00+08:00", **changes)


def test_normal_batch_and_portable_read(repository, database, bar, query):
    result = repository.write_many([bar], run_id="first")
    assert result.inserted == 1
    assert counts(database) == (1, 1, 1, 1)
    read = query()
    assert read.bar == validate_bar(bar)
    assert read.as_of == "2026-10-16T08:00:00.000000+00:00"
    assert read.data_snapshot_id.startswith("observation:sha256:")
    assert read.definitions_version == "task-002-v1"
    assert "run:first" in read.lineage_refs
    assert any("ingestion delay" in warning for warning in read.warnings)


@pytest.mark.parametrize("close", [11.0, 10.5])
def test_same_version_duplicate_never_overwrites(repository, database, bar, query, close):
    repository.write_many([bar], run_id="first")
    with pytest.raises(DuplicateRecordError, match="duplicate"):
        repository.write_many([replace(bar, close=close)], run_id="retry")
    assert query().bar.close == bar.close
    assert counts(database) == (1, 1, 1, 1)


def test_duplicate_run_rejected(repository, database, bar):
    repository.write_many([bar], run_id="first")
    with pytest.raises(DuplicateRecordError, match="run_id"):
        repository.write_many([bar], run_id="first")
    assert counts(database) == (1, 1, 1, 1)


def test_duplicate_within_same_batch_rolls_back(repository, database, bar):
    with pytest.raises(DuplicateRecordError):
        repository.write_many([bar, bar], run_id="batch")
    assert counts(database) == (0, 0, 0, 0)


def test_late_invalid_record_rolls_back_entire_batch(repository, database, bar):
    with pytest.raises(ValidationError, match=r"records\[1\].volume"):
        repository.write_many([bar, replace(bar, volume=-1)], run_id="batch")
    assert counts(database) == (0, 0, 0, 0)


def test_late_conflict_preserves_existing_rows_only(repository, database, bar):
    repository.write_many([bar], run_id="existing")
    new = replace(bar, instrument_id="listing:synthetic:2", symbol="600001.SH")
    with pytest.raises(DuplicateRecordError):
        repository.write_many([new, bar], run_id="batch")
    assert counts(database) == (1, 1, 1, 1)


def test_generator_failure_rolls_back(repository, database, bar):
    def records():
        yield bar
        raise RuntimeError("synthetic input stream failed")
    with pytest.raises(RuntimeError, match="input stream"):
        repository.write_many(records(), run_id="batch")
    assert counts(database) == (0, 0, 0, 0)


@pytest.mark.parametrize("run_id", ["", " ", None])
def test_missing_run_id_rejected(repository, database, bar, run_id):
    with pytest.raises(ValidationError, match="run_id"):
        repository.write_many([bar], run_id=run_id)
    assert counts(database) == (0, 0, 0, 0)


def test_empty_batch_rejected(repository, database):
    with pytest.raises(ValidationError, match="empty"):
        repository.write_many([], run_id="empty")
    assert counts(database) == (0, 0, 0, 0)


@pytest.mark.parametrize("as_of", [
    "2026-10-16T14:00:00+08:00", "2026-10-16T15:30:00+08:00",
    "2026-10-16T15:30:59.999999+08:00",
])
def test_strict_read_waits_for_both_timestamps(repository, bar, query, as_of):
    repository.write_many([bar], run_id="first")
    with pytest.raises(DataUnavailableError):
        query(as_of=as_of)
    assert query(as_of=bar.ingested_at).bar.source_version == bar.source_version


def test_available_after_ingestion_still_limits_read(repository, bar, query):
    delayed = replace(bar, available_at="2026-10-16T15:40:00+08:00")
    repository.write_many([delayed], run_id="first")
    with pytest.raises(DataUnavailableError):
        query(as_of=bar.ingested_at)
    assert query(as_of=delayed.available_at).bar.available_at.endswith("+00:00")


def test_revision_is_append_only_and_not_backfilled(repository, database, bar, query):
    repository.write_many([bar], run_id="first")
    original = query()
    repository.write_many([revised(bar, close=10.5)], run_id="revision")
    assert query() == original
    assert query(as_of="2026-10-17T10:00:30+08:00") == replace(
        original, as_of="2026-10-17T02:00:30.000000+00:00")
    latest = query(as_of="2026-10-17T02:01:00Z")
    assert latest.bar.close == 10.5
    assert latest.bar.supersedes_version == bar.source_version
    assert latest.data_snapshot_id != original.data_snapshot_id
    assert counts(database) == (1, 1, 2, 2)


def test_sources_are_separate_and_never_automatically_selected(repository, database, bar, query):
    other = replace(bar, source="other:daily:v1", close=10.5)
    repository.write_many([bar, other], run_id="two-sources")
    assert query().bar.close == 11
    assert query(source=other.source).bar.close == 10.5
    with pytest.raises(DataUnavailableError):
        query(source="missing:daily:v1")
    assert counts(database) == (1, 1, 2, 1)


def test_adjustment_methods_have_distinct_logical_objects(repository, database, bar, query):
    qfq = replace(bar, adjustment_method="qfq", factor_version="factor-1", close=10.5)
    hfq = replace(bar, adjustment_method="hfq", factor_version="factor-2", close=10.2)
    repository.write_many([bar, qfq, hfq], run_id="three-prices")
    assert query().bar.factor_version is None
    assert query(adjustment_method="qfq").bar.close == qfq.close
    assert query(adjustment_method="hfq").bar.factor_version == "factor-2"
    assert counts(database) == (1, 3, 3, 1)


def test_symbol_reuse_does_not_merge_listing_entities(repository, database, bar, query):
    reused = replace(bar, instrument_id="different-listing-same-code", close=10.5)
    repository.write_many([bar, reused], run_id="identities")
    assert query(instrument_id=reused.instrument_id).bar.close == 10.5
    assert query().bar.close == 11
    assert counts(database) == (2, 2, 2, 1)


def test_instrument_symbol_conflict_rejected(repository, database, bar):
    repository.write_many([bar], run_id="first")
    with pytest.raises(IntegrityError, match="different symbol"):
        repository.write_many([replace(bar, symbol="600001.SH")], run_id="conflict")
    assert counts(database) == (1, 1, 1, 1)


@pytest.mark.parametrize("changes", [
    {"supersedes_version": "missing-parent"},
    {"supersedes_version": None},
    {"available_at": "2026-10-16T15:00:00+08:00"},
    {"ingested_at": "2026-10-16T15:30:00+08:00"},
    {"available_at": "2026-10-16T15:30:00+08:00", "ingested_at": "2026-10-16T15:31:00+08:00"},
    {"source": "another:daily:v1"},
    {"adjustment_method": "qfq", "factor_version": "factor-1"},
])
def test_invalid_revision_chain_rejected(repository, database, bar, changes):
    repository.write_many([bar], run_id="first")
    candidate = replace(revised(bar), **changes)
    with pytest.raises(IntegrityError):
        repository.write_many([candidate], run_id="bad-revision")
    assert counts(database) == (1, 1, 1, 1)


def test_revision_cannot_fork(repository, database, bar):
    repository.write_many([bar], run_id="first")
    second = revised(bar)
    repository.write_many([second], run_id="second")
    fork = replace(second, source_version="observation-fork", ingested_at="2026-10-17T11:00:00+08:00")
    with pytest.raises(IntegrityError):
        repository.write_many([fork], run_id="fork")
    assert counts(database) == (1, 1, 2, 2)


@pytest.mark.parametrize("mode", ["strict_backtest", "paper_trade"])
def test_quarantined_revision_blocks_strict_instead_of_reviving_old(repository, bar, query, mode):
    repository.write_many([bar], run_id="first")
    repository.write_many([revised(bar, quality_status="quarantined")], run_id="quarantine")
    with pytest.raises(DataUnavailableError, match="quarantined"):
        query(as_of="2026-10-17T11:00:00+08:00", mode=mode)
    assert query(mode=mode).bar.quality_status == "accepted"
    research = query(as_of="2026-10-17T11:00:00+08:00", mode="research")
    assert research.bar.quality_status == "quarantined"
    assert any("quarantined" in warning for warning in research.warnings)


def test_research_still_refuses_future_records(repository, bar, query):
    repository.write_many([bar], run_id="first")
    with pytest.raises(DataUnavailableError):
        query(mode="research", as_of="2026-10-16T15:30:00+08:00")


@pytest.mark.parametrize("changes", [
    {"as_of": None}, {"as_of": "2026-10-16T16:00:00"}, {"mode": "live"},
    {"adjustment_method": "auto"}, {"trade_date": "2026-02-30"}, {"source": ""},
])
def test_read_requires_explicit_valid_query(repository, bar, query, changes):
    repository.write_many([bar], run_id="first")
    with pytest.raises(ValidationError):
        query(**changes)


@pytest.mark.parametrize("changes", [
    {"open": -1}, {"close": 15}, {"high": float("inf")}, {"amount": -1},
    {"volume": -1}, {"volume": "invalid"}, {"available_at": None},
    {"ingested_at": "invalid"}, {"factor_version": "not-raw"},
])
def test_sql_constraints_defend_against_repository_bypass(database, repository, bar, changes):
    repository.write_many([bar], run_id="first")
    with database.connection() as conn:
        row = dict(conn.execute("SELECT * FROM daily_bar_versions").fetchone())
    row.pop("version_id")
    row.update(source_version="bad-version", supersedes_version=bar.source_version,
               available_at="2026-10-17T02:00:00.000000+00:00",
               ingested_at="2026-10-17T02:01:00.000000+00:00")
    row.update(changes)
    with pytest.raises(sqlite3.IntegrityError):
        with database.transaction() as conn:
            conn.execute(f"INSERT INTO daily_bar_versions ({','.join(row)}) VALUES ({','.join('?' for _ in row)})",
                         tuple(row.values()))
    assert counts(database) == (1, 1, 1, 1)


def test_sql_logical_key_is_unique(database, repository, bar):
    repository.write_many([bar], run_id="first")
    with pytest.raises(sqlite3.IntegrityError, match="UNIQUE"):
        with database.transaction() as conn:
            conn.execute("INSERT INTO daily_bars (instrument_id, trade_date, adjustment_method) VALUES (?, ?, ?)",
                         (bar.instrument_id, bar.trade_date, bar.adjustment_method))

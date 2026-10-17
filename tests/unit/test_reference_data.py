"""Synthetic reference facts against real isolated SQLite; never vendor data."""

import json
import sqlite3
import socket
from dataclasses import asdict, replace

import pytest

from ai_trade.data_access.models import DuplicateRecordError, IntegrityError, ValidationError
from ai_trade.data_access.repository import SQLiteMarketDataRepository
from ai_trade.reference_data.models import (
    CalendarDataMissingError, CalendarDay, CalendarSourceError, NoKnownTradingDayError, Provenance,
    SecurityDataMissingError, SecurityNotActiveError, SecurityPeriod, SecuritySnapshot,
)
from ai_trade.security_master.repository import SQLiteSecurityMaster
from ai_trade.storage.db import Database, DatabaseConfig
from ai_trade.storage.schema import MIGRATIONS
from ai_trade.trading_calendar.repository import SQLiteTradingCalendar

EARLY = "2026-10-16T00:01:00Z"
LATE = "2026-10-17T00:01:00Z"


@pytest.fixture
def provenance():
    return Provenance("synthetic:reference:v1", "v1", "2026-10-10T00:00:00Z",
                      "2026-10-16T00:00:00Z", "2026-10-16T00:00:00Z", EARLY,
                      "synthetic", "fixture:reference-v1")


@pytest.fixture
def security(provenance):
    return SecuritySnapshot("fixture:listing:1", "600000.SH", "SH", "A_SHARE", "2026-01-01", None,
                            (SecurityPeriod("2026-01-01", None, "Synthetic Old Name"),), provenance)


@pytest.fixture
def day(provenance):
    return CalendarDay("SH", "2026-10-16", True, provenance)


@pytest.fixture
def master(database):
    return SQLiteSecurityMaster(database)


@pytest.fixture
def calendar(database):
    return SQLiteTradingCalendar(database)


def revision(meta, **changes):
    base = replace(meta, record_version="v2", supersedes_version=meta.record_version,
                   revision_reason="fixture correction evidence", available_at="2026-10-17T00:00:00Z",
                   observed_at="2026-10-17T00:00:00Z", ingested_at=LATE)
    return replace(base, **changes)


def get(master, security, **changes):
    args = dict(instrument_id=security.instrument_id, valid_on="2026-08-01", as_of=LATE, mode="strict_backtest")
    return master.get(**(args | changes))


def read(calendar, day, **changes):
    args = dict(exchange=day.exchange, session_date=day.session_date, as_of=LATE, mode="strict_backtest")
    return calendar.get_day(**(args | changes))


def table_count(database, table):
    with database.connection() as conn:
        return conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]


def test_v1_upgrade_preserves_daily_data_and_released_checksum(tmp_path, bar):
    db = Database(DatabaseConfig(tmp_path / "upgrade.sqlite3", "test"))
    assert MIGRATIONS[0].checksum == "c6d31829bdef4ad9c6f45279c7696cfe94ac6acb9ff016c59320298b8e8dc0bd"
    assert db.initialize(MIGRATIONS[:1]) == 1
    repository = SQLiteMarketDataRepository(db)
    repository.write_many([bar], run_id="v1-existing")
    assert db.initialize() == db.initialize() == 2
    assert table_count(db, "daily_bar_versions") == 1
    result = repository.get_bar(instrument_id=bar.instrument_id, trade_date=bar.trade_date,
                                source=bar.source, adjustment_method="none", as_of="2026-10-17T00:00:00Z",
                                mode="strict_backtest")
    assert result.bar.close == bar.close


@pytest.mark.parametrize("existing_v1", [False, True])
def test_v2_failure_rolls_back_tables_and_ledger(tmp_path, existing_v1):
    db = Database(DatabaseConfig(tmp_path / "failed.sqlite3", "test"))
    if existing_v1:
        db.initialize(MIGRATIONS[:1])
    broken = MIGRATIONS[:1] + (replace(MIGRATIONS[1], statements=MIGRATIONS[1].statements + ("INVALID SQL",)),)
    with pytest.raises(sqlite3.OperationalError):
        db.initialize(broken)
    with db.connection() as conn:
        names = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "security_versions" not in names and "calendar_versions" not in names
        if existing_v1:
            assert conn.execute("SELECT max(version) FROM schema_migrations").fetchone()[0] == 1
        else:
            assert names == set()
    assert db.initialize() == 2


def test_master_read_metadata_and_repeat_initialization(master, database, security):
    assert master.write_many([security], run_id="master").inserted == 1
    before = get(master, security)
    assert database.initialize() == database.initialize() == 2
    assert get(master, security) == before
    assert before.value.period.name == "Synthetic Old Name"
    assert before.value.risk_status is None
    assert any("ST/risk" in warning for warning in before.warnings)
    assert any("synthetic" in warning for warning in before.warnings)
    assert before.data_snapshot_id.startswith("reference-observation:sha256:")
    assert before.lineage_refs and before.definitions_version == "task-004-v1"


@pytest.mark.parametrize("symbol,exchange", [("600000.SH", "SH"), ("000001.SZ", "SZ"), ("920001.BJ", "BJ")])
def test_exchange_and_code_formats(master, security, symbol, exchange):
    record = replace(security, symbol=symbol, exchange=exchange)
    master.write_many([record], run_id="master")
    assert master.resolve(symbol=symbol, valid_on="2026-08-01", as_of=LATE, mode="research").value.snapshot.symbol == symbol


@pytest.mark.parametrize("changes", [
    {"instrument_id": "600000.SH"}, {"instrument_id": "000001"}, {"instrument_id": ""},
    {"symbol": "600000"}, {"symbol": "６０００００.SH"}, {"symbol": "600000.US"},
    {"exchange": "SZ"}, {"exchange": "HK"}, {"exchange": None},
    {"security_type": "ETF"}, {"security_type": "INDEX"}, {"security_type": "B_SHARE"},
    {"quality_status": "quarantined"},
    {"listing_date": "2026-02-30"}, {"delisting_date": "2026-01-01"},
    {"delisting_date": "2026-09-01"}, {"periods": ()},
    {"periods": (SecurityPeriod("2025-12-31", None, "before listing"),)},
    {"periods": (SecurityPeriod("2026-01-01", None, ""),)},
    {"periods": (SecurityPeriod("2026-01-01", "2026-06-01", "one"),
                 SecurityPeriod("2026-05-01", None, "overlap"))},
    {"periods": (SecurityPeriod("2026-01-01", "2026-01-01", "empty"),)},
])
def test_invalid_master_rejected_without_rows(master, database, security, changes):
    with pytest.raises(ValidationError):
        master.write_many([replace(security, **changes)], run_id="bad")
    assert table_count(database, "security_versions") == table_count(database, "instruments") == 0
    assert table_count(database, "ingestion_runs") == 0


@pytest.mark.parametrize("valid_on,active", [("2025-12-31", False), ("2026-01-01", True),
                                           ("2026-10-19", True), ("2026-10-20", False)])
def test_listing_and_delisting_half_open_boundaries(master, security, valid_on, active):
    record = replace(security, delisting_date="2026-10-20", periods=(SecurityPeriod("2026-01-01", "2026-10-20", "known"),))
    master.write_many([record], run_id="master")
    if active:
        assert get(master, record, valid_on=valid_on).value.period.name == "known"
    else:
        with pytest.raises(SecurityNotActiveError):
            get(master, record, valid_on=valid_on)


def test_name_change_and_historical_revision_do_not_backfill(master, security):
    master.write_many([security], run_id="root")
    original = get(master, security, as_of=EARLY)
    updated = replace(security, periods=(SecurityPeriod("2026-01-01", "2026-07-01", "Synthetic Old Name"),
                                        SecurityPeriod("2026-07-01", None, "Synthetic New Name")),
                      provenance=revision(security.provenance))
    master.write_many([updated], run_id="revision")
    assert get(master, security, as_of=EARLY) == original
    assert get(master, security, as_of="2026-10-17T00:00:59.999999Z").value.period.name == "Synthetic Old Name"
    assert get(master, security).value.period.name == "Synthetic New Name"
    assert get(master, security, valid_on="2026-06-30").value.period.name == "Synthetic Old Name"
    assert get(master, security, valid_on="2026-07-01").value.period.name == "Synthetic New Name"


def test_unknown_effective_period_and_risk_stay_unknown(master, security):
    record = replace(security, periods=(SecurityPeriod("2026-10-01", None, "ST is only a fixture name"),))
    master.write_many([record], run_id="root")
    with pytest.raises(SecurityDataMissingError):
        get(master, record)
    assert get(master, record, valid_on="2026-10-01").value.risk_status is None


@pytest.mark.parametrize("mode", ["research", "strict_backtest", "paper_trade"])
def test_both_cutoffs_and_timezone_required(master, security, mode):
    master.write_many([security], run_id="master")
    for cutoff in ("2026-10-15T23:59:59.999999Z", "2026-10-16T00:00:59.999999Z"):
        with pytest.raises(SecurityDataMissingError):
            get(master, security, as_of=cutoff, mode=mode)
    assert get(master, security, as_of="2026-10-16T08:01:00+08:00", mode=mode).value.snapshot.instrument_id == security.instrument_id
    with pytest.raises(ValidationError):
        get(master, security, as_of="2026-10-17T00:01:00", mode=mode)


@pytest.mark.parametrize("changed_payload", [False, True])
def test_master_duplicate_never_overwrites(master, database, security, changed_payload):
    master.write_many([security], run_id="root")
    candidate = replace(security, periods=(SecurityPeriod("2026-01-01", None, "different"),)) if changed_payload else security
    with pytest.raises(DuplicateRecordError):
        master.write_many([candidate], run_id="retry")
    assert get(master, security).value.period.name == "Synthetic Old Name"
    assert table_count(database, "ingestion_runs") == 1


@pytest.mark.parametrize("changes", [
    {"supersedes_version": None, "revision_reason": None}, {"supersedes_version": "missing"},
    {"available_at": "2026-10-15T00:00:00Z"}, {"observed_at": "2026-10-15T00:00:00Z"},
    {"ingested_at": "2026-10-15T00:01:00Z", "observed_at": "2026-10-15T00:00:00Z"},
    {"available_at": "2026-10-16T00:00:00Z", "observed_at": "2026-10-16T00:00:00Z", "ingested_at": EARLY},
])
def test_master_conflict_and_backdated_revision_rejected(master, database, security, changes):
    master.write_many([security], run_id="root")
    bad = replace(security, provenance=revision(security.provenance, **changes))
    with pytest.raises(IntegrityError):
        master.write_many([bad], run_id="bad-revision")
    assert table_count(database, "security_versions") == 1


def test_canonical_source_change_requires_explicit_revision_and_cannot_fork(master, security):
    master.write_many([security], run_id="root")
    updated = replace(security, provenance=revision(security.provenance, source="other:verified:v1"))
    master.write_many([updated], run_id="new-source")
    assert get(master, security).value.snapshot.provenance.source == "other:verified:v1"
    fork = replace(updated, provenance=replace(updated.provenance, record_version="fork", available_at="2026-10-18T00:00:00Z"))
    with pytest.raises(IntegrityError):
        master.write_many([fork], run_id="fork")


def test_existing_bar_anchor_reused_and_symbol_change_not_silent(master, repository, bar, security):
    repository.write_many([bar], run_id="bar")
    record = replace(security, instrument_id=bar.instrument_id)
    master.write_many([record], run_id="master")
    assert get(master, record).value.snapshot.instrument_id == bar.instrument_id
    with pytest.raises(IntegrityError, match="another symbol"):
        master.write_many([replace(record, symbol="600001.SH", provenance=revision(record.provenance))], run_id="code-change")


def test_code_reuse_requires_nonoverlapping_lifetimes(master, database, security):
    old = replace(security, listing_date="1990-01-01", delisting_date="2000-01-01",
                  periods=(SecurityPeriod("1990-01-01", "2000-01-01", "old listing"),))
    new = replace(security, instrument_id="fixture:listing:2", listing_date="2000-01-01",
                  periods=(SecurityPeriod("2000-01-01", None, "new listing"),))
    master.write_many([old, new], run_id="reuse")
    for date, expected in (("1999-12-31", old.instrument_id), ("2000-01-01", new.instrument_id)):
        assert master.resolve(symbol=security.symbol, valid_on=date, as_of=LATE, mode="research").value.snapshot.instrument_id == expected
    bad = replace(new, instrument_id="fixture:listing:3")
    with pytest.raises(IntegrityError, match="code reuse"):
        master.write_many([bad], run_id="overlap")
    assert table_count(database, "security_versions") == 2


def test_code_reuse_checks_historical_visibility_not_only_current_head(master, security):
    old = replace(security, listing_date="1990-01-01", periods=(SecurityPeriod("1990-01-01", None, "old"),),
                  provenance=replace(security.provenance, available_at="2026-10-15T00:00:00Z",
                                     observed_at="2026-10-15T00:00:00Z", ingested_at="2026-10-15T00:01:00Z"))
    master.write_many([old], run_id="old")
    closed = replace(old, delisting_date="2000-01-01", periods=(SecurityPeriod("1990-01-01", "2000-01-01", "old"),),
                     provenance=revision(old.provenance))
    master.write_many([closed], run_id="closed-later")
    new = replace(security, instrument_id="fixture:listing:2", listing_date="2000-01-01",
                  periods=(SecurityPeriod("2000-01-01", None, "new"),))
    with pytest.raises(IntegrityError, match="visibility time"):
        master.write_many([new], run_id="earlier-observation-conflict")
    master.write_many([replace(new, provenance=replace(new.provenance, available_at="2026-10-17T00:00:00Z",
                      observed_at="2026-10-17T00:00:00Z", ingested_at=LATE))], run_id="consistent-observation")


def test_open_closed_missing_source_error_are_distinct(calendar, day):
    closed = replace(day, session_date="2026-10-17", is_trading_day=False)
    error = replace(day, session_date="2026-10-18", is_trading_day=None,
                    quality_status="source_error", error_reason="fixture upstream schema failure")
    calendar.write_many([day, closed, error], run_id="calendar")
    assert read(calendar, day).value.is_trading_day is True
    assert read(calendar, closed).value.is_trading_day is False
    with pytest.raises(CalendarDataMissingError):
        read(calendar, replace(day, session_date="2026-10-19"))
    with pytest.raises(CalendarSourceError, match="upstream schema"):
        read(calendar, error)


def test_calendar_range_and_previous_known_are_bounded_and_explicit(calendar, day):
    records = [day, replace(day, session_date="2026-10-17", is_trading_day=False),
               replace(day, session_date="2026-10-18", is_trading_day=True)]  # Synthetic Sunday open, no weekday inference.
    calendar.write_many(records, run_id="calendar")
    result = calendar.trading_days(exchange="SH", start="2026-10-16", end="2026-10-18", as_of=LATE, mode="strict_backtest")
    assert [x.session_date for x in result.value] == ["2026-10-16", "2026-10-18"]
    assert result.complete
    latest = calendar.previous_known_trading_day(exchange="SH", before="2026-10-19", search_start="2026-10-16", as_of=LATE, mode="strict_backtest")
    assert latest.value.session_date == "2026-10-18"
    assert calendar.previous_known_trading_day(exchange="SH", before="2026-10-18", search_start="2026-10-16", as_of=LATE, mode="research").value.session_date == day.session_date


def test_partial_ranges_never_hide_missing_or_errors(calendar, day):
    calendar.write_many([day, replace(day, session_date="2026-10-18", is_trading_day=None,
                         quality_status="source_error", error_reason="fixture")], run_id="calendar")
    args = dict(exchange="SH", start="2026-10-16", end="2026-10-18", as_of=LATE)
    result = calendar.trading_days(**args, mode="research")
    assert result.missing_dates == ("2026-10-17",) and result.source_error_dates == ("2026-10-18",)
    assert not result.complete and len(result.value) == 1
    for mode in ("strict_backtest", "paper_trade"):
        with pytest.raises(CalendarSourceError):
            calendar.trading_days(**args, mode=mode)
    with pytest.raises(CalendarDataMissingError):
        calendar.trading_days(**(args | {"end": "2026-10-17"}), mode="strict_backtest")
    prior = calendar.previous_known_trading_day(exchange="SH", before="2026-10-19", search_start="2026-10-16", as_of=LATE, mode="research")
    assert prior.value.session_date == day.session_date and not prior.complete


def test_all_closed_is_not_same_as_missing(calendar, day):
    calendar.write_many([replace(day, is_trading_day=False)], run_id="closed")
    closed = calendar.trading_days(exchange="SH", start=day.session_date, end=day.session_date, as_of=LATE, mode="research")
    missing = calendar.trading_days(exchange="SH", start="2026-10-17", end="2026-10-17", as_of=LATE, mode="research")
    assert closed.value == missing.value == ()
    assert closed.complete and not missing.complete
    assert closed.data_snapshot_id != missing.data_snapshot_id
    with pytest.raises(NoKnownTradingDayError):
        calendar.previous_known_trading_day(exchange="SH", before="2026-10-17", search_start="2026-10-16", as_of=LATE, mode="research")


def test_calendar_revisions_future_announcements_and_error_do_not_revive_old(calendar, day):
    calendar.write_many([day], run_id="open")
    closed = replace(day, is_trading_day=False, provenance=revision(day.provenance, available_at="2026-10-18T00:00:00Z"))
    calendar.write_many([closed], run_id="correction")
    assert read(calendar, day).value.is_trading_day is True  # available cutoff, despite ingestion on 17th
    assert read(calendar, day, as_of="2026-10-18T00:00:00Z").value.is_trading_day is False
    broken_meta = replace(revision(closed.provenance), record_version="v3", available_at="2026-10-19T00:00:00Z",
                          observed_at="2026-10-19T00:00:00Z", ingested_at="2026-10-19T00:01:00Z")
    error = replace(day, is_trading_day=None, quality_status="source_error", error_reason="fixture source unavailable", provenance=broken_meta)
    calendar.write_many([error], run_id="error")
    for mode in ("research", "strict_backtest", "paper_trade"):
        with pytest.raises(CalendarSourceError):
            read(calendar, day, as_of="2026-10-19T01:00:00Z", mode=mode)
    # Future session dates may be announced before the session; event_time is source release, not session close.
    calendar.write_many([replace(day, session_date="2027-01-01", is_trading_day=False)], run_id="future-announced")
    assert read(calendar, replace(day, session_date="2027-01-01"), as_of=EARLY).value.is_trading_day is False


@pytest.mark.parametrize("exchange", ["SH", "SZ", "BJ"])
def test_calendar_exchange_isolation(calendar, day, exchange):
    calendar.write_many([replace(day, exchange=exchange)], run_id="exchange")
    assert read(calendar, day, exchange=exchange).value.is_trading_day
    other = "SZ" if exchange == "SH" else "SH"
    with pytest.raises(CalendarDataMissingError):
        read(calendar, day, exchange=other)


@pytest.mark.parametrize("changes", [
    {"is_trading_day": None}, {"is_trading_day": 1}, {"is_trading_day": "true"},
    {"quality_status": "source_error"}, {"error_reason": "not accepted"},
    {"is_trading_day": None, "quality_status": "source_error", "error_reason": ""},
    {"session_date": "2026-02-30"}, {"exchange": "US"},
])
def test_calendar_invalid_fact_rejected(calendar, database, day, changes):
    with pytest.raises(ValidationError):
        calendar.write_many([replace(day, **changes)], run_id="invalid")
    assert table_count(database, "calendar_versions") == table_count(database, "ingestion_runs") == 0


@pytest.mark.parametrize("changes", [
    {"event_time": None}, {"available_at": None}, {"observed_at": None}, {"ingested_at": None},
    {"observed_at": "2026-10-18T00:00:00Z"}, {"available_at": "2026-10-01T00:00:00Z"},
    {"source": "AKShare"}, {"record_version": ""}, {"evidence_kind": "real_verified"}, {"evidence_ref": ""},
    {"supersedes_version": "v0", "revision_reason": None},
])
def test_metadata_is_explicit_and_not_fabricated(calendar, database, day, changes):
    with pytest.raises(ValidationError):
        calendar.write_many([replace(day, provenance=replace(day.provenance, **changes))], run_id="bad")
    assert table_count(database, "ingestion_runs") == 0


@pytest.mark.parametrize("kind", ["security", "calendar"])
def test_batch_validation_duplicate_and_generator_failure_roll_back_all(
        master, calendar, security, day, database, kind):
    repository, record, table = (master, security, "security_versions") if kind == "security" else (calendar, day, "calendar_versions")
    invalid = replace(security, periods=()) if kind == "security" else replace(day, is_trading_day=-1)
    with pytest.raises(ValidationError):
        repository.write_many([record, invalid], run_id="late-invalid")
    with pytest.raises(DuplicateRecordError):
        repository.write_many([record, record], run_id="duplicate")
    def stream():
        yield record
        raise RuntimeError("fixture interrupted stream")
    with pytest.raises(RuntimeError):
        repository.write_many(stream(), run_id="generator")
    assert table_count(database, table) == table_count(database, "ingestion_runs") == table_count(database, "instruments") == 0
    with pytest.raises(ValidationError):
        repository.write_many([], run_id="empty")


@pytest.mark.parametrize("table", ["security_versions", "calendar_versions"])
@pytest.mark.parametrize("operation", ["UPDATE", "DELETE", "REPLACE"])
def test_new_tables_are_append_only(master, calendar, security, day, database, table, operation):
    master.write_many([security], run_id="master")
    calendar.write_many([day], run_id="calendar")
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        with database.transaction() as conn:
            if operation == "REPLACE":
                row = dict(conn.execute(f"SELECT * FROM {table}").fetchone())
                conn.execute(f"INSERT OR REPLACE INTO {table} ({','.join(row)}) VALUES ({','.join('?' for _ in row)})", tuple(row.values()))
            elif operation == "UPDATE":
                conn.execute(f"UPDATE {table} SET run_id=run_id")
            else:
                conn.execute(f"DELETE FROM {table}")


@pytest.mark.parametrize("mutation", ["date", "overlap", "extra_field", "missing_anchor", "missing_run", "missing_parent"])
def test_sql_master_integrity_without_repository_validation(master, security, database, mutation):
    master.write_many([security], run_id="master")
    with database.connection() as conn:
        row = dict(conn.execute("SELECT * FROM security_versions").fetchone())
    row.pop("version_id")
    row.update(record_version="v2", supersedes_version="v1", revision_reason="SQL fixture",
               available_at="2026-10-17T00:00:00.000000+00:00", observed_at="2026-10-17T00:00:00.000000+00:00",
               ingested_at="2026-10-17T00:01:00.000000+00:00")
    if mutation == "date":
        row["periods_json"] = json.dumps([dict(effective_from="2026-02-30", effective_to=None, name="bad")])
    elif mutation == "overlap":
        row["periods_json"] = json.dumps([asdict(security.periods[0]), asdict(security.periods[0])])
    elif mutation == "extra_field":
        row["periods_json"] = json.dumps([asdict(security.periods[0]) | {"risk_status": "normal"}])
    elif mutation == "missing_anchor":
        row.update(instrument_id="missing:anchor", symbol="600001.SH", supersedes_version=None, revision_reason=None)
    elif mutation == "missing_run":
        row["run_id"] = "missing-run"
    else:
        row["supersedes_version"] = "missing-parent"
    with pytest.raises(sqlite3.IntegrityError):
        with database.transaction() as conn:
            conn.execute(f"INSERT INTO security_versions ({','.join(row)}) VALUES ({','.join('?' for _ in row)})", tuple(row.values()))
    assert table_count(database, "security_versions") == 1


def test_database_integrity_and_run_id_shared_across_datasets(master, calendar, security, day, database):
    master.write_many([security], run_id="master")
    with pytest.raises(DuplicateRecordError):
        calendar.write_many([day], run_id="master")
    calendar.write_many([day], run_id="calendar")
    with database.connection() as conn:
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


@pytest.mark.parametrize("source_error", [False, True])
def test_previous_with_no_usable_day_preserves_failure_kind(calendar, day, source_error):
    if source_error:
        calendar.write_many([replace(day, is_trading_day=None, quality_status="source_error", error_reason="fixture")], run_id="error")
    error = CalendarSourceError if source_error else CalendarDataMissingError
    with pytest.raises(error):
        calendar.previous_known_trading_day(exchange="SH", before="2026-10-17", search_start="2026-10-16", as_of=LATE, mode="research")


@pytest.mark.parametrize("mutation", ["bad_date", "bad_flag", "missing_run", "missing_parent"])
def test_sql_calendar_constraints(calendar, day, database, mutation):
    calendar.write_many([day], run_id="root")
    with database.connection() as conn:
        row = dict(conn.execute("SELECT * FROM calendar_versions").fetchone())
    row.pop("version_id")
    row.update(session_date="2026-10-18")
    if mutation == "bad_date":
        row["session_date"] = "2026-02-30"
    elif mutation == "bad_flag":
        row["is_trading_day"] = -1
    elif mutation == "missing_run":
        row["run_id"] = "missing"
    else:
        row.update(supersedes_version="missing", revision_reason="fixture")
    with pytest.raises(sqlite3.IntegrityError):
        with database.transaction() as conn:
            conn.execute(f"INSERT INTO calendar_versions ({','.join(row)}) VALUES ({','.join('?' for _ in row)})", tuple(row.values()))
    assert table_count(database, "calendar_versions") == 1


def test_calendar_duplicate_conflicting_root_and_fork_are_not_overwritten(calendar, day, database):
    calendar.write_many([day], run_id="root")
    with pytest.raises(DuplicateRecordError):
        calendar.write_many([replace(day, is_trading_day=False)], run_id="same-version")
    with pytest.raises(IntegrityError):
        calendar.write_many([replace(day, is_trading_day=False, provenance=replace(day.provenance, record_version="other-root"))], run_id="conflict")
    correction = replace(day, is_trading_day=False, provenance=revision(day.provenance))
    calendar.write_many([correction], run_id="revision")
    with pytest.raises(IntegrityError):
        calendar.write_many([replace(correction, provenance=replace(correction.provenance, record_version="fork"))], run_id="fork")
    assert read(calendar, day, as_of=EARLY).value.is_trading_day is True
    assert read(calendar, day).value.is_trading_day is False
    assert table_count(database, "ingestion_runs") == 2


@pytest.mark.parametrize("changes", [
    {"start": "2026-10-18", "end": "2026-10-16"}, {"start": "2026-02-30"},
    {"mode": "latest"}, {"as_of": None}, {"exchange": "US"},
])
def test_invalid_range_query_is_explicit(calendar, changes):
    args = dict(exchange="SH", start="2026-10-16", end="2026-10-18", as_of=LATE, mode="research")
    with pytest.raises(ValidationError):
        calendar.trading_days(**(args | changes))


def test_calendar_first_observation_waits_for_ingestion(calendar, day):
    calendar.write_many([day], run_id="root")
    with pytest.raises(CalendarDataMissingError):
        read(calendar, day, as_of="2026-10-16T00:00:59.999999Z")
    assert read(calendar, day, as_of="2026-10-16T08:01:00+08:00").value.is_trading_day


def test_reference_suite_inherits_default_network_block():
    with pytest.raises(AssertionError, match="must not access"):
        socket.create_connection(("example.invalid", 443))

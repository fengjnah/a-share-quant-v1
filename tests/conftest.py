"""Independent temporary files and synthetic records; networking is forbidden."""

import socket

import pytest

from ai_trade.data_access.models import DailyBar
from ai_trade.data_access.repository import SQLiteMarketDataRepository
from ai_trade.storage.db import Database, DatabaseConfig


def pytest_addoption(parser):
    parser.addoption("--run-akshare-integration", action="store_true", default=False,
                     help="explicitly permit tests marked manual_integration to call AKShare")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-akshare-integration"):
        skip = pytest.mark.skip(reason="live AKShare test requires --run-akshare-integration")
        for item in items:
            if item.get_closest_marker("manual_integration"):
                item.add_marker(skip)


@pytest.fixture(autouse=True)
def forbid_network(monkeypatch, request):
    if (request.node.get_closest_marker("manual_integration")
            and request.config.getoption("--run-akshare-integration")):
        return
    def denied(*args, **kwargs):
        raise AssertionError("unit tests must not access the network")
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket.socket, "connect_ex", denied)
    monkeypatch.setattr(socket, "create_connection", denied)


@pytest.fixture
def database(tmp_path):
    db = Database(DatabaseConfig(tmp_path / "test.sqlite3", environment="test"))
    db.initialize()
    return db


@pytest.fixture
def repository(database):
    return SQLiteMarketDataRepository(database)


@pytest.fixture
def bar():
    return DailyBar(
        instrument_id="listing:synthetic:1", symbol="600000.SH", trade_date="2026-10-16",
        open=10.0, high=12.0, low=9.0, close=11.0, volume=1000, amount=11000.0,
        source="synthetic:daily:v1", source_version="observation-1",
        event_time="2026-10-16T15:00:00+08:00",
        available_at="2026-10-16T15:30:00+08:00",
        ingested_at="2026-10-16T15:31:00+08:00", adjustment_method="none",
    )


@pytest.fixture
def query(repository, bar):
    def read(**overrides):
        arguments = dict(instrument_id=bar.instrument_id, trade_date=bar.trade_date,
                         source=bar.source, adjustment_method=bar.adjustment_method,
                         as_of="2026-10-16T16:00:00+08:00", mode="strict_backtest")
        return repository.get_bar(**(arguments | overrides))
    return read

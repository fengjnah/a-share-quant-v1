"""Initialize a local database without downloading data or running a strategy."""

import argparse

from ai_trade.storage.db import Database, DatabaseConfig


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize/migrate the SQLite data foundation")
    parser.parse_args()
    config = DatabaseConfig.from_env()
    version = Database(config).initialize()
    print(f"Initialized {config.environment}: {config.path} (schema version {version})")


if __name__ == "__main__":
    main()

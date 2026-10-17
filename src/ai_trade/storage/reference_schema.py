"""Schema v2 only. The released v1 statements and checksum remain unchanged."""


def _date(field: str) -> str:
    return (f"({field} GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]' "
            f"AND date({field}, '+0 days') IS NOT NULL AND date({field}, '+0 days') = {field})")


def reference_statements(time_check: str) -> tuple[str, ...]:
    """Reuse v1's timestamp storage check; require built-in JSON and window support."""
    meta = ",\n".join(f"{field} TEXT NOT NULL {time_check.format(field=field)}"
                       for field in ("event_time", "available_at", "observed_at", "ingested_at"))
    meta += """,
        source TEXT NOT NULL CHECK (length(trim(source)) > 0 AND source GLOB '*:*:*'),
        record_version TEXT NOT NULL CHECK (length(trim(record_version)) > 0),
        evidence_kind TEXT NOT NULL CHECK (evidence_kind IN ('synthetic','source_observation')),
        evidence_ref TEXT NOT NULL CHECK (length(trim(evidence_ref)) > 0),
        supersedes_version TEXT,
        revision_reason TEXT,
        run_id TEXT NOT NULL REFERENCES ingestion_runs(run_id),
        CHECK (event_time <= available_at AND event_time <= observed_at AND observed_at <= ingested_at),
        CHECK ((supersedes_version IS NULL AND revision_reason IS NULL) OR
               (supersedes_version IS NOT NULL AND revision_reason IS NOT NULL
                AND length(trim(revision_reason)) > 0 AND supersedes_version <> record_version))
    """
    security = f"""CREATE TABLE security_versions (
        version_id INTEGER PRIMARY KEY,
        instrument_id TEXT NOT NULL,
        symbol TEXT NOT NULL,
        exchange TEXT NOT NULL CHECK (exchange IN ('SH','SZ','BJ') AND substr(symbol,8)=exchange),
        security_type TEXT NOT NULL CHECK (security_type='A_SHARE'),
        quality_status TEXT NOT NULL CHECK (quality_status='accepted'),
        listing_date TEXT NOT NULL CHECK {_date('listing_date')},
        delisting_date TEXT CHECK (delisting_date IS NULL OR {_date('delisting_date')}),
        periods_json TEXT NOT NULL CHECK (json_valid(periods_json)),
        {meta},
        CHECK (delisting_date IS NULL OR listing_date < delisting_date),
        CHECK (instrument_id <> symbol AND instrument_id <> substr(symbol,1,6)),
        CHECK (NOT (length(instrument_id)=6 AND instrument_id NOT GLOB '*[^0-9]*')),
        CHECK (NOT (length(instrument_id)=9 AND substr(instrument_id,1,6) NOT GLOB '*[^0-9]*'
                    AND substr(instrument_id,7) IN ('.SH','.SZ','.BJ'))),
        FOREIGN KEY (instrument_id,symbol) REFERENCES instruments(instrument_id,symbol),
        UNIQUE (instrument_id,record_version),
        UNIQUE (instrument_id,supersedes_version),
        FOREIGN KEY (instrument_id,supersedes_version) REFERENCES security_versions(instrument_id,record_version)
    )"""
    calendar = f"""CREATE TABLE calendar_versions (
        version_id INTEGER PRIMARY KEY,
        exchange TEXT NOT NULL CHECK (exchange IN ('SH','SZ','BJ')),
        session_date TEXT NOT NULL CHECK {_date('session_date')},
        is_trading_day INTEGER,
        quality_status TEXT NOT NULL CHECK (quality_status IN ('accepted','source_error')),
        error_reason TEXT,
        {meta},
        CHECK ((quality_status='accepted' AND is_trading_day IS NOT NULL AND is_trading_day IN (0,1)
                AND error_reason IS NULL) OR (quality_status='source_error' AND is_trading_day IS NULL
                AND error_reason IS NOT NULL AND length(trim(error_reason))>0)),
        UNIQUE (exchange,session_date,record_version),
        UNIQUE (exchange,session_date,supersedes_version),
        FOREIGN KEY (exchange,session_date,supersedes_version)
            REFERENCES calendar_versions(exchange,session_date,record_version)
    )"""
    statements = [
        "SELECT json_valid('[]'),(SELECT count(*) FROM json_each('[]')),row_number() OVER ()",
        security, calendar,
    ]
    for table, keys in (("security_versions", ("instrument_id",)),
                        ("calendar_versions", ("exchange", "session_date"))):
        columns = ",".join(keys)
        match = " AND ".join(f"p.{key}=NEW.{key}" for key in keys)
        statements.extend((
            f"CREATE UNIQUE INDEX {table}_root ON {table}({columns}) WHERE supersedes_version IS NULL",
            f"CREATE INDEX {table}_visibility ON {table}({columns},available_at,ingested_at)",
            f"CREATE INDEX {table}_run ON {table}(run_id)",
            f"""CREATE TRIGGER {table}_revision BEFORE INSERT ON {table} BEGIN
                SELECT CASE WHEN NEW.supersedes_version IS NOT NULL AND EXISTS (
                    SELECT 1 FROM {table} p WHERE {match} AND p.record_version=NEW.supersedes_version
                      AND (NEW.available_at<p.available_at OR NEW.observed_at<p.observed_at
                           OR NEW.ingested_at<p.ingested_at OR
                           max(NEW.available_at,NEW.ingested_at)<=max(p.available_at,p.ingested_at))
                ) THEN RAISE(ABORT,'revision visibility must advance without backdating') END;
            END""",
        ))
        for operation in ("UPDATE", "DELETE"):
            statements.append(f"""CREATE TRIGGER immutable_{table}_{operation.lower()}
                BEFORE {operation} ON {table}
                BEGIN SELECT RAISE(ABORT,'audit records are append-only'); END""")
    start = "json_extract(p.value,'$.effective_from')"
    end = "json_extract(p.value,'$.effective_to')"
    statements.extend((
        "CREATE INDEX security_symbol_lifetime ON security_versions(symbol,listing_date,delisting_date)",
        f"""CREATE TRIGGER security_periods BEFORE INSERT ON security_versions BEGIN
            SELECT CASE WHEN NOT json_valid(NEW.periods_json)
                THEN RAISE(ABORT,'invalid timeline JSON') END;
            SELECT CASE WHEN json_type(NEW.periods_json) IS NOT 'array'
                OR json_array_length(NEW.periods_json) NOT BETWEEN 1 AND 256
                THEN RAISE(ABORT,'timeline requires 1..256 periods') END;
            SELECT CASE WHEN EXISTS (
                SELECT 1 FROM json_each(NEW.periods_json) p WHERE p.type IS NOT 'object'
                OR (SELECT count(*) FROM json_each(p.value))<>3
                OR json_type(p.value,'$.effective_from') IS NOT 'text'
                OR NOT {_date(start)}
                OR json_type(p.value,'$.name') IS NOT 'text'
                OR length(trim(json_extract(p.value,'$.name'))) NOT BETWEEN 1 AND 256
                OR json_type(p.value,'$.effective_to') IS NULL
                OR json_type(p.value,'$.effective_to') NOT IN ('null','text')
                OR ({end} IS NOT NULL AND (NOT {_date(end)} OR {end}<={start}))
                OR {start}<NEW.listing_date
                OR (NEW.delisting_date IS NOT NULL AND ({end} IS NULL OR {end}>NEW.delisting_date))
            ) THEN RAISE(ABORT,'invalid period or lifetime boundary') END;
            SELECT CASE WHEN EXISTS (
                SELECT 1 FROM json_each(NEW.periods_json) p JOIN json_each(NEW.periods_json) q ON p.key<q.key
                WHERE json_extract(p.value,'$.effective_to') IS NULL OR
                      json_extract(p.value,'$.effective_to')>json_extract(q.value,'$.effective_from')
            ) THEN RAISE(ABORT,'timeline periods overlap or are unsorted') END;
        END""",
        """CREATE TRIGGER security_code_lifetime BEFORE INSERT ON security_versions BEGIN
            SELECT CASE WHEN EXISTS (
                SELECT 1 FROM security_versions p
                WHERE p.symbol=NEW.symbol AND p.instrument_id<>NEW.instrument_id
                  AND (p.delisting_date IS NULL OR NEW.listing_date<p.delisting_date)
                  AND (NEW.delisting_date IS NULL OR p.listing_date<NEW.delisting_date)
                  AND NOT EXISTS (
                    SELECT 1 FROM security_versions successor
                    WHERE successor.instrument_id=p.instrument_id AND successor.supersedes_version=p.record_version
                      AND max(successor.available_at,successor.ingested_at)<=max(NEW.available_at,NEW.ingested_at)
                  )
            ) THEN RAISE(ABORT,'code reuse conflicts in business and visibility time') END;
        END""",
    ))
    return tuple(statements)

"""Read-only metadata inventory and migration preview. Never imports market rows."""
import argparse
import hashlib
import json
import sqlite3
from pathlib import Path


def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read(path):
    wal = Path(str(path) + "-wal")
    if wal.exists() and wal.stat().st_size:
        raise ValueError("nonempty WAL requires a separate consistent-snapshot review")
    # Archived, inactive samples only; never creates/changes WAL/SHM sidecars.
    return sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous-inventory", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output exists; preserve prior evidence")
    previous = json.loads(args.previous_inventory.read_text(encoding="utf-8"))
    records = []
    for old in previous["databases"]:
        path = Path(old["path"])
        entry = {"path": str(path), "exists": path.is_file(), "ownership": "legacy sample / not formal"}
        if path.is_file():
            before = sha(path)
            conn = read(path)
            try:
                conn.execute("PRAGMA query_only=ON")
                entry["sha256"] = before
                entry["tables"] = {r[0]: conn.execute('SELECT count(*) FROM "'+r[0]+'"').fetchone()[0]
                    for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
                if "daily_bar_versions" in entry["tables"]:
                    entry["batches"] = [dict(zip(("symbol","source","run_id","source_version","quality_status",
                        "rows","first_date","last_date","first_available","last_available","first_ingested","last_ingested"), row))
                        for row in conn.execute("""SELECT i.symbol,v.source,v.run_id,v.source_version,v.quality_status,
                            count(*),min(b.trade_date),max(b.trade_date),min(v.available_at),max(v.available_at),
                            min(v.ingested_at),max(v.ingested_at)
                            FROM daily_bar_versions v JOIN daily_bars b USING(bar_id) JOIN instruments i USING(instrument_id)
                            GROUP BY i.symbol,v.source,v.run_id,v.source_version,v.quality_status""")]
                entry["migrations"] = [list(r) for r in conn.execute("SELECT * FROM schema_migrations ORDER BY version")]
                entry["quick_check"] = [r[0] for r in conn.execute("PRAGMA quick_check")]
            except sqlite3.DatabaseError as exc:
                entry["error_type"] = type(exc).__name__
            finally:
                conn.close()
            entry["unchanged_after_read"] = sha(path) == before
        records.append(entry)
    observations = []
    for old in previous["observations"]:
        path = Path(old["path"])
        item = {k: v for k,v in old.items() if k not in ("fields", "price_fields")}
        item["exists"] = path.is_file()
        item["unchanged_from_previous"] = (path.is_file() and sha(path) == old["sha256"]
                                            if old.get("sha256") else None)
        if path.is_file():
            item["current_sha256"] = sha(path)
        observations.append(item)
    # Compare actual logical keys and all source payload values; output counts only.
    chosen = next(r for r in records if r.get("tables",{}).get("daily_bars")==1217
                  and any(b["symbol"]=="600000.SH" for b in r.get("batches",[])))
    source = read(Path(chosen["path"]))
    sql = """SELECT b.instrument_id,i.symbol,b.trade_date,b.adjustment_method,v.source,v.source_version,
             v.open,v.high,v.low,v.close,v.volume,v.amount,v.factor_version,v.quality_status,
             v.event_time,v.available_at,v.ingested_at,v.run_id
             FROM daily_bars b JOIN instruments i USING(instrument_id) JOIN daily_bar_versions v USING(bar_id)"""
    try:
        rows = list(source.execute(sql))
    finally:
        source.close()
    overlap_source = next(r for r in records if r.get("tables",{}).get("daily_bars")==187
                          and any(b["symbol"]=="600000.SH" for b in r.get("batches",[])))
    conn = read(Path(overlap_source["path"]))
    try:
        small_rows = list(conn.execute(sql))
    finally:
        conn.close()
    # Different batch/recorded times are retained; equality of OHLCV is not merge authorization.
    by_date = {r[1:5]:r for r in rows}
    overlap = [(r, by_date[r[1:5]]) for r in small_rows if r[1:5] in by_date]
    cross_sample = {"smaller_source":overlap_source["path"],"larger_source":chosen["path"],
        "overlapping_logical_dates":len(overlap),
        "different_price_volume_amount_or_factor":sum(a[6:13]!=b[6:13] for a,b in overlap),
        "different_quality":sum(a[13]!=b[13] for a,b in overlap),
        "different_batch_or_system_times":sum(a[14:]!=b[14:] for a,b in overlap),
        "merge_authorized":False}
    targets = []
    if args.target.is_file():
        conn = read(args.target)
        try:
            targets = list(conn.execute(sql))
        finally:
            conn.close()
    target_map = {r[:6]:r[6:] for r in targets}
    preview = {"source": chosen["path"], "target":str(args.target), "target_exists":args.target.is_file(),
        "source_versions":len(rows), "target_versions":len(targets),
        "candidate_new_versions":sum(r[:6] not in target_map for r in rows),
        "identical_existing_versions":sum(r[:6] in target_map and target_map[r[:6]]==r[6:] for r in rows),
        "conflicting_existing_versions":sum(r[:6] in target_map and target_map[r[:6]]!=r[6:] for r in rows),
        "source_duplicate_version_keys":len(rows)-len({r[:6] for r in rows}),
        "migration_executed":False, "authorization":"UNKNOWN", "admission":"BLOCKED",
        "conditions":["source/storage/research license", "historical availability evidence", "identity/calendar",
                      "quality review", "approved auditable/deduplicated/recoverable migration task"]}
    result={"market_requests":0,"database_writes":0,"inventory_scope":"existing PR44 manifest, not a new global scan",
            "databases":records,"observations":observations,"cross_sample_187_1217":cross_sample,
            "preview_1217":preview,
            "old_files_unchanged":[{"path":name,"unchanged":Path(name).is_file() and sha(Path(name))==state["sha256"]}
                for old in previous["databases"] for name,state in old["before"].items()]}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("x",encoding="utf-8") as stream:
        json.dump(result,stream,ensure_ascii=False,indent=2)
    print(json.dumps({"databases":len(records),"observations":len(observations),"preview":preview},ensure_ascii=False))


if __name__=="__main__":
    main()

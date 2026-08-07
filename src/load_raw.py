"""
Load every raw CSV in data/raw/ into the raw_orders table, unchanged.

- Idempotent: a file already present in raw_orders (by source_file) is skipped,
  so re-running or backfilling never double-loads.
- Column-order agnostic: whichever product column a file uses
  (product_id / new_product_id / product_id_source), it maps to the right raw
  column; missing columns become NULL.
- Empty files (header only) add no rows but are reported.

Usage:
    uv run python -m src.load_raw
"""

import uuid

import pandas as pd
from sqlalchemy import text

from helpers import config, io, db, logs
from src.capture import classify_file
from src.init_db import init_db

# Fixed column set of the raw_orders table (order does not matter for to_sql).
RAW_ORDERS_COLUMNS = [
    "source_file", "ingested_at", "order_id", "order_date", "store_id",
    "product_id", "new_product_id", "product_id_source", "quantity",
    "unit_price", "discount_pct", "sales_channel", "loyalty_member",
]


def _loaded_dates(engine):
    """Dates already in raw_orders, derived from each stored source_file name.

    Keying on the DATE (not the raw filename) makes loading robust to mixed
    naming, e.g. 'orders_20260718.csv' and 'orders_2026-07-18.csv' are the same
    day and will not be double-loaded.
    """
    try:
        df = pd.read_sql("SELECT DISTINCT source_file FROM raw_orders", engine)
        return {io.expected_date_from_filename(f) for f in df["source_file"]}
    except Exception:
        return set()


def _sync_ingestion_log_table(engine):
    """Mirror the authoritative data/ingestion_log.csv into the SQLite
    `ingestion_log` table so the table is actually queryable instead of sitting
    empty (verify_tables.py otherwise reports 0 rows every run). The CSV stays
    the source of truth; the table is refreshed from it on each load. We DELETE
    then append rather than to_sql(replace=...) so the schema init_db created
    (run_id PRIMARY KEY, NOT NULL columns) is preserved."""
    if not config.INGESTION_LOG_CSV.exists():
        return 0
    df = pd.read_csv(config.INGESTION_LOG_CSV, dtype=str)
    if df.empty:
        return 0
    df["rows_loaded"] = pd.to_numeric(df["rows_loaded"], errors="coerce").astype("Int64")
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM ingestion_log"))   # full refresh
    df.to_sql("ingestion_log", engine, if_exists="append", index=False)
    return len(df)


def load_raw():
    init_db()                       # ensure the schema exists (idempotent)
    engine = db.get_sqlite_engine()
    done_dates = _loaded_dates(engine)          # already in raw_orders
    logged_dates = logs.already_logged_dates()  # already in ingestion_log.csv

    loaded, skipped, empty = 0, 0, 0
    for path in sorted(config.RAW_DIR.glob("orders_*.csv")):
        file_date = io.expected_date_from_filename(path.name)

        # --- ingestion log (one row per file, idempotent by date) ---
        if file_date not in logged_dates:
            status, rows, found_date = classify_file(path, file_date)
            logs.append_ingestion_log({
                "run_id": uuid.uuid4().hex,
                "run_timestamp": io.utc_now_iso(),
                "source_url": config.ORDERS_URL,
                "source_date_expected": file_date,
                "source_date_found": found_date,
                "status": status,
                "rows_loaded": rows,
                "file_hash": io.file_hash(path),
                "error_message": "",
            })
            logged_dates.add(file_date)

        # --- load into raw_orders (idempotent by date) ---
        if file_date in done_dates:
            skipped += 1
            continue
        df = io.read_orders_csv(path)
        if len(df) == 0:
            empty += 1
            print(f"[load_raw] {path.name}: empty, logged, no rows to load")
            continue
        # Ensure every raw column exists, then tag provenance.
        for col in RAW_ORDERS_COLUMNS:
            if col not in df.columns:
                df[col] = None
        df["source_file"] = path.name
        df["ingested_at"] = io.utc_now_iso()
        df[RAW_ORDERS_COLUMNS].to_sql(
            "raw_orders", engine, if_exists="append", index=False
        )
        done_dates.add(file_date)   # guard against a same-date dup within this run
        loaded += 1
        print(f"[load_raw] {path.name}: loaded {len(df)} rows")

    total = pd.read_sql("SELECT COUNT(*) AS n FROM raw_orders", engine)["n"][0]
    synced = _sync_ingestion_log_table(engine)
    print(f"[load_raw] done. files loaded={loaded}, skipped={skipped}, "
          f"empty={empty}; raw_orders now has {total} rows")
    print(f"[load_raw] ingestion_log table synced from CSV: {synced} rows")
    return total


if __name__ == "__main__":
    load_raw()

"""
Load reference CSVs (produced by src/extract_reference.py) into the local
SQLite database. Safe to run repeatedly (replaces the reference tables).

This is the network-free half: the daily pipeline / GitHub Actions uses the
committed data/reference/*.csv snapshots, never the UTK MySQL server.

If a CSV is not present yet (before the first VPN pull), it is skipped and the
pipeline continues without that reference table.

Usage:
    uv run python -m src.reference
"""

import pandas as pd

from helpers import config, db


def load_reference_into_sqlite():
    engine = db.get_sqlite_engine()
    loaded = []
    for table in config.REFERENCE_TABLES:
        csv_path = config.REFERENCE_DIR / f"{table}.csv"
        if not csv_path.exists():
            print(f"[reference] {table}.csv not found; skipping")
            continue
        df = pd.read_csv(csv_path, dtype=str, keep_default_na=False, na_values=[""])
        df.to_sql(table, engine, if_exists="replace", index=False)
        loaded.append(f"{table}({len(df)})")
        print(f"[reference] loaded {table}: {len(df)} rows into SQLite")
    if not loaded:
        print("[reference] no reference CSVs found in data/reference/")
    return loaded


if __name__ == "__main__":
    load_reference_into_sqlite()

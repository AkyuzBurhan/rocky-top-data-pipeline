"""
Reference extraction -- run MANUALLY while on the UTK network or VPN, because
the UTK MySQL server is not reachable from GitHub Actions.

Everything happens in code (no manual copy/paste):
    1. Connect to the reference SOURCE database (instructor's DB if
       'source_db' is set in credentials.json, otherwise our team DB).
    2. SELECT stores / products / new_products.
    3. Write each result to:
         - data/reference/<table>.csv  (committed; feeds the SQLite pipeline)
         - our TEAM database <netid>_bzan545  (the "real" SQL home)
         - the local SQLite database

new_products is released later in the project; if it does not exist yet in the
source, that one table is skipped with a message.

Usage:
    uv run python -m src.extract_reference                 # all reference tables
    uv run python -m src.extract_reference stores products # a subset
"""

import sys

import pandas as pd

from helpers import config, db


def extract(tables=None):
    tables = tables or config.REFERENCE_TABLES
    source = db.get_source_engine()   # instructor's DB, or team DB fallback
    team = db.get_team_engine()       # our DB (write target)
    sqlite_engine = db.get_sqlite_engine()
    config.REFERENCE_DIR.mkdir(parents=True, exist_ok=True)

    for table in tables:
        try:
            print(f"[extract_reference] SELECT * FROM {table} ...")
            df = pd.read_sql(f"SELECT * FROM {table}", source)
        except Exception as exc:  # noqa: BLE001
            print(f"[extract_reference] {table}: SKIPPED ({exc})")
            continue

        # 1) commit-friendly CSV snapshot (feeds SQLite / reproducible)
        df.to_csv(config.REFERENCE_DIR / f"{table}.csv", index=False)
        # 2) copy into our team database (code, not manual copy/paste)
        df.to_sql(table, team, if_exists="replace", index=False)
        # 3) load into the local SQLite pipeline DB
        df.to_sql(table, sqlite_engine, if_exists="replace", index=False)

        print(f"[extract_reference] {table}: {len(df)} rows "
              f"-> CSV + team DB + SQLite")


if __name__ == "__main__":
    args = sys.argv[1:] or None
    extract(args)

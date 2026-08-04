"""
Create the local SQLite database (rocky_top.db) by running sql/01_schema.sql.
Safe to run repeatedly: every statement uses CREATE TABLE IF NOT EXISTS.

Usage:
    uv run python -m src.init_db
"""

import sqlite3

import sqlalchemy

from helpers import config, db


def init_db():
    schema_sql = (config.ROOT_DIR / "sql" / "01_schema.sql").read_text()
    con = sqlite3.connect(config.SQLITE_PATH)
    con.executescript(schema_sql)
    con.close()

    # Report which tables now exist.
    engine = db.get_sqlite_engine()
    tables = sqlalchemy.inspect(engine).get_table_names()
    print(f"[init_db] {config.SQLITE_PATH.name} ready with {len(tables)} tables:")
    for t in sorted(tables):
        print(f"  - {t}")
    return tables


if __name__ == "__main__":
    init_db()

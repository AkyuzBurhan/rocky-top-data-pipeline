"""
Run row/cell-level data-quality checks over every file in data/raw/ and write
one row per file to data/data_quality_log.csv.

Idempotent: a file already in the log is skipped. Open the CSV in Excel and
compare a day to the previous one -- a sudden jump (e.g. yesterday 0 NA, today
30) is the signal to investigate.

Orphan checks (store_id / product not in reference) activate automatically once
the reference tables are loaded into SQLite (Step 6); until then they are blank
and each row is flagged 'ref_not_loaded'.

Usage:
    uv run python -m src.check_quality
"""

import pandas as pd

from helpers import config, io, dq, logs, db


def _reference_sets():
    """(store_ids, product_ids) from SQLite, or (None, None) if not loaded/empty."""
    try:
        engine = db.get_sqlite_engine()
        s = set(pd.read_sql("SELECT store_id FROM stores", engine)["store_id"].dropna())
        p = set(pd.read_sql("SELECT product_id FROM products", engine)["product_id"].dropna())
        try:
            np_ids = set(pd.read_sql(
                "SELECT new_product_id FROM new_products", engine
            )["new_product_id"].dropna())
        except Exception:
            np_ids = set()
        product_ids = p | np_ids
        if not s or not product_ids:
            return None, None
        return s, product_ids
    except Exception:
        return None, None


def check_quality():
    store_ids, product_ids = _reference_sets()
    done = logs.already_logged_files(config.DATA_QUALITY_LOG_CSV)

    checked = 0
    for path in sorted(config.RAW_DIR.glob("orders_*.csv")):
        if path.name in done:
            continue
        expected = io.expected_date_from_filename(path.name)
        row = dq.run_quality_checks(path, expected, store_ids, product_ids)
        logs.append_dq_log(row)
        checked += 1
        print(f"[check_quality] {path.name}: n_rows={row['n_rows']} "
              f"flags={row['flags'] or 'none'}")
    print(f"[check_quality] done. {checked} new file(s) checked "
          f"-> {config.DATA_QUALITY_LOG_CSV.name}")


if __name__ == "__main__":
    check_quality()

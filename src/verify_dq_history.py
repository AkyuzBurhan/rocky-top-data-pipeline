"""Re-run the CURRENT data-quality gate over every historical raw file.

Why this exists. `src/check_quality.py` is idempotent: a file already recorded
in `data/data_quality_log.csv` is skipped forever. That is the right behaviour
for a daily pipeline, but it means a check added AFTER a file was ingested has
never been applied to it. The non-numeric gate (`helpers/dq._nonnumeric`, added
in commit 3676313 in response to the 2026-08-05 currency-string incident) is
exactly that case: until this script, it had only ever fired on the synthetic
poison fixture, never on real data.

This closes that gap without touching anything. Every file in `data/raw/` is
re-checked in memory against the current gate and the result is compared to the
row already in the log.

This script WRITES NOTHING, and that is deliberate, not an oversight.
`data/data_quality_log.csv` is cited as evidence: the 2026-08-05 row showing
`na_unit_price=0` alongside no non-numeric flag is the proof that no check
fired at the time. Rewriting the log would destroy the record of the miss.

Usage:
    uv run python src/verify_dq_history.py
    uv run python -m src.verify_dq_history

Exit code 0 = every difference is a known, documented one.
Nonzero = a historical file flags something we have not accounted for.
"""
import sqlite3
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))          # so both invocation forms work

from helpers import config, dq, io     # noqa: E402

# Differences we expect and have already written up. 2026-08-05 is the
# currency-string day (DECISIONS.md Limitation 1): all 155 rows arrived with
# "$"-prefixed unit_price, the gate did not exist yet, so the logged row is
# clean. The current gate catches all 155. Anything NOT in this dict is a
# finding.
KNOWN_DIFFS = {
    "orders_2026-08-05.csv": "nonnumeric(unit_price=155)",
}


def _reference_sets():
    """(store_ids, product_ids) from SQLite, read-only, or (None, None).

    Mirrors `src/check_quality.py:_reference_sets` so the orphan checks behave
    identically here. Opened with mode=ro: verification must never be able to
    alter the database it is verifying.
    """
    db = REPO / "rocky_top.db"
    if not db.exists():
        return None, None
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        stores = {r[0] for r in con.execute("SELECT store_id FROM stores")}
        products = {r[0] for r in con.execute("SELECT product_id FROM products")}
        products |= {r[0] for r in con.execute(
            "SELECT new_product_id FROM new_products")}
        con.close()
        return (stores or None), (products or None)
    except sqlite3.Error:
        return None, None


def _logged_flags():
    """{file_name: set(flags)} from the committed quality log."""
    path = config.DATA_QUALITY_LOG_CSV
    if not path.exists():
        return {}
    df = pd.read_csv(path, dtype=str).fillna("")
    # An unflagged file stores an empty cell, which pandas reads back as NaN
    # before fillna. Comparing raw strings would report every clean file as a
    # difference, so compare sets of flags instead.
    return {r["file_name"]: set(filter(None, r["flags"].split(";")))
            for _, r in df.iterrows()}


def verify():
    store_ids, product_ids = _reference_sets()
    if store_ids is None or product_ids is None:
        print("WARN  reference tables unavailable; orphan checks will be blank")
    logged = _logged_flags()

    files = sorted(config.RAW_DIR.glob("orders_*.csv"))
    unexpected, known = [], []

    for path in files:
        expected_date = io.expected_date_from_filename(path.name)
        row = dq.run_quality_checks(path, expected_date, store_ids, product_ids)
        now = set(filter(None, row["flags"].split(";")))
        was = logged.get(path.name, set())
        if now == was:
            continue
        added, removed = sorted(now - was), sorted(was - now)
        entry = (path.name, added, removed)
        # A known diff must match exactly: the same single flag added, nothing
        # removed. A changed row count means the file itself changed.
        if not removed and added == [KNOWN_DIFFS.get(path.name)]:
            known.append(entry)
        else:
            unexpected.append(entry)

    print(f"re-checked {len(files)} file(s) in {config.RAW_DIR.name}/ "
          f"against the current gate")
    for name, added, removed in known:
        print(f"KNOWN      {name}")
        print(f"           gate now adds: {', '.join(added)}")
        print("           documented in DECISIONS.md Limitation 1")
    for name, added, removed in unexpected:
        print(f"UNEXPECTED {name}")
        if added:
            print(f"           gate now adds: {', '.join(added)}")
        if removed:
            print(f"           logged but no longer flagged: {', '.join(removed)}")

    if unexpected:
        sys.exit(f"FAIL: {len(unexpected)} file(s) flag something undocumented")
    print(f"PASS: {len(known)} known difference(s), no undocumented ones. "
          "The quality log was not modified.")


if __name__ == "__main__":
    verify()

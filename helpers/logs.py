"""
Append-only CSV logger for the file-level ingestion log.

ingestion_log.csv answers, per attempt: did the file arrive, how many rows,
its hash, whether it was fresh, and a status. Columns follow the assignment's
recommended schema. (The row/cell-level data-quality log is added in Step 5.)
"""

import csv

from helpers import config
from helpers.dq import DQ_COLUMNS

INGESTION_COLUMNS = [
    "run_id",
    "run_timestamp",
    "source_url",
    "source_date_expected",
    "source_date_found",
    "status",
    "rows_loaded",
    "file_hash",
    "error_message",
]


def _append_row(path, columns, row):
    """Append one dict as a CSV row, writing the header if the file is new."""
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists()
    with open(path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def append_ingestion_log(row):
    """Append a file-level ingestion record to ingestion_log.csv."""
    _append_row(config.INGESTION_LOG_CSV, INGESTION_COLUMNS, row)


def append_dq_log(row):
    """Append a row/cell-level data-quality record to data_quality_log.csv."""
    _append_row(config.DATA_QUALITY_LOG_CSV, DQ_COLUMNS, row)


def already_logged_files(path, key="file_name"):
    """Set of file names already present in a CSV log (for idempotency)."""
    if not path.exists():
        return set()
    with open(path, newline="") as f:
        return {r[key] for r in csv.DictReader(f) if r.get(key)}


def already_logged_dates():
    """Set of expected dates already present in ingestion_log.csv. Used to keep
    logging idempotent so backfill does not duplicate a day already logged
    (e.g. by the live capture step)."""
    if not config.INGESTION_LOG_CSV.exists():
        return set()
    with open(config.INGESTION_LOG_CSV, newline="") as f:
        return {r["source_date_expected"] for r in csv.DictReader(f)
                if r.get("source_date_expected")}

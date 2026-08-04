"""
Small input/output helpers shared across the pipeline.
"""

import hashlib
import re
from datetime import datetime, timezone

import pandas as pd

from helpers import config


def detect_product_column(df):
    """Decide which product-identifier column a file uses.

    The header alone is NOT trustworthy: from 2026-07-31 the column is named
    'product_id' but holds new-system IDs (e.g. 'NP5008'), flagged by
    'product_id_source' == 'new_system'. Returns a tuple:

        (physical_column_name, has_source_flag)
    """
    has_source_flag = config.PRODUCT_SOURCE_COL in df.columns
    if config.NEW_PRODUCT_COL in df.columns:
        return config.NEW_PRODUCT_COL, has_source_flag
    return config.LEGACY_PRODUCT_COL, has_source_flag


def file_hash(path):
    """Return a SHA-256 hash of a file's bytes. Used to detect duplicate or
    stale daily files (e.g. a file re-published unchanged)."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def expected_date_from_filename(filename):
    """Extract the date encoded in a raw file name, e.g.
    'orders_2026-08-03.csv' -> '2026-08-03'. Returns None if not found."""
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", str(filename))
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    m = re.search(r"(\d{4})(\d{2})(\d{2})", str(filename))  # compact YYYYMMDD
    if m:
        return f"{m.group(1)}-{m.group(2)}-{m.group(3)}"
    return None


def read_orders_csv(path):
    """Read a raw daily orders CSV as strings (we do not trust types yet).
    Returns an empty DataFrame (with headers) for a zero-row file."""
    return pd.read_csv(path, dtype=str, keep_default_na=False, na_values=[""])


def utc_now_iso():
    """Current UTC timestamp as an ISO-8601 string (SQLite-friendly TEXT)."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

"""
Row-/cell-level data quality checks for each daily orders file.

Each file produces one dict (one row) for data/data_quality_log.csv with a
FIXED set of columns, so the log opens cleanly in Excel and can be compared day
over day. We record raw COUNTS (not percentages), e.g. "5 NA in quantity",
"10 duplicate order_id".

Column names in the file shift with the product migration, so per-column NA
counts always map to the same fixed log columns (the product identifier is
always counted as 'na_product' regardless of its physical name).
"""

import pandas as pd

from helpers import config, io

# Fixed column order for data_quality_log.csv
DQ_COLUMNS = [
    "run_date",
    "file_name",
    "n_rows",
    "product_col",       # physical product column present in the file
    "has_source_flag",   # was product_id_source present?
    "na_order_id",
    "na_order_date",
    "na_store_id",
    "na_product",
    "na_quantity",
    "na_unit_price",
    "na_discount_pct",
    "na_sales_channel",
    "na_loyalty",
    "dup_rows",          # fully duplicated rows
    "dup_order_id",      # repeated order_id values
    "neg_quantity",
    "neg_unit_price",
    "bad_discount",      # discount_pct outside 0..100
    "orphan_store",      # store_id not in stores reference
    "orphan_product",    # product not in the relevant reference
    "flags",             # short human-readable notes, ';'-separated
]


def _na(df, col):
    return int(df[col].isna().sum()) if col in df.columns else ""


def _num(series):
    return pd.to_numeric(series, errors="coerce")


def _nonnumeric(df, col):
    """Count values that are present (not null) but do NOT parse as numbers --
    e.g. "$72.70", "1,024". This is the class of bug that silently zeroed
    2026-08-05: an isna() check misses them because the value is a valid
    non-null string, so the day looked clean while its revenue was lost."""
    if col not in df.columns:
        return 0
    raw = df[col]
    return int((raw.notna() & _num(raw).isna()).sum())


def run_quality_checks(path, expected_date, store_ids=None, product_ids=None):
    """Run all checks on one file; return a dict keyed by DQ_COLUMNS.

    store_ids / product_ids: optional sets from the reference tables. When not
    provided, orphan checks are blank and a 'ref_not_loaded' flag is added.
    """
    df = io.read_orders_csv(path)
    file_name = path.name if hasattr(path, "name") else str(path)
    product_col, has_source_flag = io.detect_product_column(df)
    flags = []
    n_rows = len(df)

    if n_rows == 0:
        flags.append("empty")
    if product_col == config.NEW_PRODUCT_COL:
        flags.append("schema_new_product_col")
    if has_source_flag:                       # header says product_id, values are new IDs
        flags.append("header_mislabeled_product")

    # Freshness / staleness
    found_date = ""
    if n_rows and "order_date" in df.columns:
        dates = df["order_date"].dropna().unique().tolist()
        found_date = dates[0] if len(dates) == 1 else ";".join(map(str, dates))
        if expected_date and found_date and found_date != expected_date:
            flags.append(f"stale(expected={expected_date},found={found_date})")

    # Duplicates
    dup_rows = int(df.duplicated().sum()) if n_rows else 0
    dup_order_id = int(df["order_id"].duplicated().sum()) if n_rows and "order_id" in df.columns else 0
    if dup_rows or dup_order_id:
        flags.append("duplicates")

    # Out-of-range numeric checks
    neg_quantity = neg_unit_price = bad_discount = 0
    if n_rows:
        q = _num(df.get("quantity", pd.Series(dtype=str)))
        p = _num(df.get("unit_price", pd.Series(dtype=str)))
        d = _num(df.get("discount_pct", pd.Series(dtype=str)))
        neg_quantity = int((q < 0).sum())
        neg_unit_price = int((p < 0).sum())
        bad_discount = int(((d < 0) | (d > 100)).sum())
    if neg_quantity or neg_unit_price or bad_discount:
        flags.append("out_of_range")

    # Non-numeric (but non-null) values in numeric columns -- the silent-failure
    # class from 2026-08-05 ("$72.70" strings). Surface it as a flag so a
    # malformed day reads RED instead of showing na_*=0 and looking healthy.
    if n_rows:
        nn = []
        for col in ("unit_price", "quantity", "discount_pct"):
            c = _nonnumeric(df, col)
            if c:
                nn.append(f"{col}={c}")
        if nn:
            flags.append("nonnumeric(" + ",".join(nn) + ")")

    # Orphan checks (need reference tables)
    orphan_store = orphan_product = ""
    if store_ids is not None and n_rows and "store_id" in df.columns:
        orphan_store = int((~df["store_id"].isin(store_ids)).sum())
    if product_ids is not None and n_rows:
        orphan_product = int((~df[product_col].isin(product_ids)).sum())
    if store_ids is None or product_ids is None:
        flags.append("ref_not_loaded")
    if (isinstance(orphan_store, int) and orphan_store) or \
       (isinstance(orphan_product, int) and orphan_product):
        flags.append("orphans")

    return {
        "run_date": io.utc_now_iso()[:10],
        "file_name": file_name,
        "n_rows": n_rows,
        "product_col": product_col if n_rows else "",
        "has_source_flag": int(has_source_flag),
        "na_order_id": _na(df, "order_id"),
        "na_order_date": _na(df, "order_date"),
        "na_store_id": _na(df, "store_id"),
        "na_product": _na(df, product_col),
        "na_quantity": _na(df, "quantity"),
        "na_unit_price": _na(df, "unit_price"),
        "na_discount_pct": _na(df, "discount_pct"),
        "na_sales_channel": _na(df, "sales_channel"),
        "na_loyalty": _na(df, "loyalty_member"),
        "dup_rows": dup_rows,
        "dup_order_id": dup_order_id,
        "neg_quantity": neg_quantity,
        "neg_unit_price": neg_unit_price,
        "bad_discount": bad_discount,
        "orphan_store": orphan_store,
        "orphan_product": orphan_product,
        "flags": ";".join(flags),
    }

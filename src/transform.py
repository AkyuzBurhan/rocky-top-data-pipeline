"""
Transformations: raw_orders -> clean_orders.

The heart of the migration handling: the product identifier is resolved by
VALUE and FLAG, never by the column header, because some source phases label
new-system IDs under the old 'product_id' name.

Resolution rule per row:
    raw value = new_product_id if present else product_id
    is_new    = product_id_source == 'new_system'
                OR the new_product_id column was used
                OR the value starts with 'NP'
    product_key       = the new_product_id when new; otherwise the crosswalk's
                        mapped new id if we have one, else the legacy id (kept
                        so the row is never lost)
    legacy_product_id = the legacy id when the row is legacy

Cleaning also: fixes types, derives line_revenue, maps loyalty Y/N -> 1/0,
drops rows with no usable date, and de-duplicates on the natural key
(this removes the 4 duplicate rows on 2026-07-16 and the 2026-07-24 stale copy
of 2026-07-23). Dropped rows are recorded in rejected_rows, never silently lost.

Usage:
    uv run python -m src.transform
"""

import pandas as pd

from helpers import db


def _to_int(series):
    return pd.to_numeric(series, errors="coerce").astype("Int64")


def _to_float(series):
    return pd.to_numeric(series, errors="coerce")


def _record_rejected(engine, rows, reason):
    """Append dropped rows to rejected_rows with a reason (honest, not silent)."""
    if rows.empty:
        return
    out = pd.DataFrame({
        "source_file": rows.get("source_file"),
        "reason": reason,
        "order_id": rows.get("order_id"),
        "raw_json": rows.astype(str).apply(lambda r: r.to_json(), axis=1),
    })
    out.to_sql("rejected_rows", engine, if_exists="append", index=False)


def build_clean_orders(engine=None):
    engine = engine or db.get_sqlite_engine()
    # Full rebuild: clear rejected_rows so repeated runs do not accumulate.
    pd.DataFrame(columns=["source_file", "reason", "order_id", "raw_json"]).to_sql(
        "rejected_rows", engine, if_exists="replace", index=False)
    raw = pd.read_sql("SELECT * FROM raw_orders", engine)
    if raw.empty:
        print("[transform] raw_orders is empty; nothing to clean")
        return 0

    # Optional legacy -> new crosswalk map (empty until Step 8 is run).
    try:
        cw = pd.read_sql(
            "SELECT product_id, new_product_id FROM product_crosswalk "
            "WHERE new_product_id IS NOT NULL", engine)
        cw_map = dict(zip(cw["product_id"], cw["new_product_id"]))
    except Exception:
        cw_map = {}

    # --- resolve product identity by value/flag, not header ---
    raw_val = raw["new_product_id"].where(raw["new_product_id"].notna(),
                                          raw["product_id"])
    is_new = (raw["product_id_source"].eq("new_system")
              | raw["new_product_id"].notna()
              | raw_val.astype(str).str.startswith("NP"))
    legacy_product_id = raw["product_id"].where(~is_new)
    product_key = raw_val.where(is_new, raw_val.map(lambda v: cw_map.get(v, v)))

    quantity = _to_int(raw["quantity"])
    unit_price = _to_float(raw["unit_price"])
    clean = pd.DataFrame({
        "order_id": raw["order_id"],
        "order_date": raw["order_date"],
        "store_id": raw["store_id"],
        "product_key": product_key,
        "legacy_product_id": legacy_product_id,
        "is_new_system": is_new.astype(int),
        "quantity": quantity,
        "unit_price": unit_price,
        "discount_pct": _to_float(raw["discount_pct"]),
        "line_revenue": quantity.astype("float") * unit_price,
        "sales_channel": raw["sales_channel"],
        "loyalty_member": raw["loyalty_member"].map({"Y": 1, "N": 0}),
        "source_file": raw["source_file"],
    })

    # --- drop rows with no usable date (quarantine, do not silently delete) ---
    bad_date = clean["order_date"].isna() | (clean["order_date"] == "")
    _record_rejected(engine, clean[bad_date], "missing_or_bad_order_date")
    clean = clean[~bad_date]

    # --- de-duplicate on the natural key ---
    dup = clean.duplicated(subset=["order_id", "order_date", "store_id", "product_key"])
    _record_rejected(engine, clean[dup], "duplicate_natural_key")
    clean = clean[~dup]

    clean.to_sql("clean_orders", engine, if_exists="replace", index=False)
    print(f"[transform] clean_orders rebuilt: {len(clean)} rows "
          f"(dropped {int(bad_date.sum())} bad-date, {int(dup.sum())} duplicate)")
    return len(clean)


if __name__ == "__main__":
    build_clean_orders()

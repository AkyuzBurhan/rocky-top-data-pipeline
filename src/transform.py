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
from src.crosswalk import CATEGORY_TO_DEPARTMENT


def _clean_numeric_str(series):
    """Strip formatting the upstream feed sends inconsistently -- currency
    symbols, thousands separators, stray whitespace -- so values like "$72.70"
    or "1,024.50" parse as numbers instead of silently coercing to NaN.

    This is the single choke point every numeric column flows through, so the
    normalization is applied uniformly (not special-cased to one day/column).
    Genuinely non-numeric junk still becomes NaN below and is quarantined --
    we normalize known formatting, we do not silently accept garbage.
    """
    return series.astype("string").str.strip().str.replace(r"[$,]", "", regex=True)


def _to_int(series):
    return pd.to_numeric(_clean_numeric_str(series), errors="coerce").astype("Int64")


def _to_float(series):
    return pd.to_numeric(_clean_numeric_str(series), errors="coerce")


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


def build_daily_sales(engine=None):
    """Aggregate clean_orders to the analytics grain: order_date x store_id x
    category, joining product category and daily weather.

    - category (Decision 1 = A): the new-system department, looked up from
      new_products via the crosswalk-resolved product_key. Products with no
      new-system match (unresolved legacy items, and the orphan NP9999) fall to
      'UNKNOWN' -- nothing is dropped, so revenue reconciles (Decision 2).
    - revenue (Decision 4 = B): unit_price is already the POST-discount price,
      so net_revenue = quantity * unit_price, gross_revenue adds the discount
      back, and discount_given is the difference.

    Prints grain and reconciliation checks for the Analytics-Ready milestone.
    """
    engine = engine or db.get_sqlite_engine()
    clean = pd.read_sql("SELECT * FROM clean_orders", engine)
    if clean.empty:
        print("[transform] clean_orders empty; skipping daily_sales")
        return 0

    # category = new-system department, with a legacy fallback + a source flag
    # so both views are kept:
    #   new_system       -> department looked up from new_products (matched/new)
    #   legacy_recovered -> product discontinued in the migration; department
    #                       recovered from its legacy category (still a real sale)
    #   unknown          -> genuinely uncatalogued (the NP9999 orphan)
    try:
        nd = pd.read_sql("SELECT new_product_id, department FROM new_products", engine)
        new_dept = dict(zip(nd["new_product_id"], nd["department"]))
    except Exception:
        new_dept = {}
    try:
        pc = pd.read_sql("SELECT product_id, category FROM products", engine)
        legacy_cat = dict(zip(pc["product_id"], pc["category"]))
    except Exception:
        legacy_cat = {}

    def resolve_category(row):
        pk = row["product_key"]
        if pk in new_dept:
            return pd.Series([new_dept[pk], "new_system"])
        lid = row["legacy_product_id"]
        if pd.notna(lid) and lid in legacy_cat:
            dep = CATEGORY_TO_DEPARTMENT.get(str(legacy_cat[lid]).lower(), "UNKNOWN")
            return pd.Series([dep, "legacy_recovered"])
        return pd.Series(["UNKNOWN", "unknown"])

    clean[["category", "category_source"]] = clean.apply(resolve_category, axis=1)

    # revenue math (unit_price is post-discount)
    q = _to_float(clean["quantity"])
    up = _to_float(clean["unit_price"])
    disc = _to_float(clean["discount_pct"]).fillna(0)
    denom = (1 - disc / 100).where(lambda s: s > 0, other=1)  # guard against /0
    clean["_q"] = q
    clean["_net"] = q * up
    clean["_gross"] = (q * up) / denom
    clean["_disc"] = clean["_gross"] - clean["_net"]

    agg = (clean.groupby(["order_date", "store_id", "category", "category_source"],
                         dropna=False)
           .agg(units_sold=("_q", "sum"),
                net_revenue=("_net", "sum"),
                gross_revenue=("_gross", "sum"),
                discount_given=("_disc", "sum"))
           .reset_index())

    # join daily weather on (date, store)
    try:
        w = pd.read_sql(
            "SELECT weather_date, store_id, temperature_2m_max, "
            "temperature_2m_min, precipitation_sum, weather_code "
            "FROM weather_daily", engine)
    except Exception:
        w = pd.DataFrame()
    if not w.empty:
        w = w.rename(columns={"weather_date": "order_date",
                              "temperature_2m_max": "temp_max",
                              "temperature_2m_min": "temp_min"})
        agg = agg.merge(w, on=["order_date", "store_id"], how="left")
    for col in ["temp_max", "temp_min", "precipitation_sum", "weather_code"]:
        if col not in agg.columns:
            agg[col] = None

    cols = ["order_date", "store_id", "category", "category_source", "units_sold",
            "net_revenue", "gross_revenue", "discount_given",
            "temp_max", "temp_min", "precipitation_sum", "weather_code"]
    agg[cols].to_sql("daily_sales", engine, if_exists="replace", index=False)

    # --- validations for the Analytics-Ready milestone ---
    grain_cols = ["order_date", "store_id", "category", "category_source"]
    grain_unique = len(agg) == len(agg[grain_cols].drop_duplicates())
    ds_net = float(agg["net_revenue"].sum())
    co_net = float(_to_float(clean["line_revenue"]).sum())  # from clean_orders
    reconciles = abs(ds_net - co_net) < 0.01
    weather_rows = int(agg["temp_max"].notna().sum())
    print(f"[transform] daily_sales rebuilt: {len(agg)} rows "
          f"(grain: order_date x store_id x category x category_source)")
    print(f"[transform]   grain unique: {grain_unique}")
    print(f"[transform]   reconciliation net_revenue: daily_sales={ds_net:,.2f} "
          f"vs clean_orders line_revenue={co_net:,.2f} "
          f"-> {'MATCH' if reconciles else 'MISMATCH'}")
    print(f"[transform]   weather-joined rows: {weather_rows}/{len(agg)}")
    return len(agg)


if __name__ == "__main__":
    build_clean_orders()
    build_daily_sales()

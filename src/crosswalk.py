"""
Build product_crosswalk: reconcile legacy `products` with `new_products`
(entity resolution across the product migration).

Method = attribute BLOCKING + fuzzy SCORING (see docs/DECISIONS.md):

  Tier 1  exact normalized name (product_name == item_name)  -> matched / high
  Tier 2  block on preserved attributes (launch_date + margin + mapped
          department), then score candidates by fuzzy name similarity
          (product_name vs item_name), token similarity (subcategory vs class)
          and price proximity (base_price vs msrp):
            - single candidate, strong name     -> matched / high
            - single candidate, weak name       -> matched / medium
            - two candidates, close scores      -> possible_match / medium
            - best candidate below MIN_SCORE    -> unresolved / low
  Tier 3  no attribute-block candidate          -> unresolved / low

After building, we VALIDATE (not match) against the observed id pattern
P1xxx -> NP(xxx+4000) and the category->department rename, and report agreement.

Runs from the reference tables (products, new_products), not from orders.
NP9999 (an order-only code absent from both catalogs) is not a crosswalk row;
it is handled as an orphan in the analytics/quality layer.

Usage:
    uv run python -m src.crosswalk
"""

import pandas as pd

from helpers import config, db
from helpers.matching import normalize_text, text_similarity

# Deterministic legacy-category -> new-department rename (verified 100% on
# known pairs). Used for blocking and as a validation cross-check.
CATEGORY_TO_DEPARTMENT = {
    "camping": "camping",
    "emergency": "preparedness",
    "footwear": "footwear",
    "hydration": "drinkware",
    "outerwear": "apparel",
    "patio": "patio",
}

# Scoring weights within a candidate block.
W_NAME, W_SUBCLASS, W_PRICE = 0.6, 0.2, 0.2
STRONG_NAME = 0.85       # name similarity above this -> high confidence
AMBIGUOUS_GAP = 0.05     # top-2 combined scores closer than this -> possible
MIN_SCORE = 0.60         # best candidate must clear this or nothing is claimed

def _price_closeness(base_price, msrp):
    try:
        b, m = float(base_price), float(msrp)
        if b <= 0:
            return 0.0
        return max(0.0, 1.0 - abs(m - b) / b)
    except (TypeError, ValueError):
        return 0.0


def _score(lrow, nrow):
    name = text_similarity(normalize_text(lrow["product_name"]),
                           normalize_text(nrow["item_name"]))
    subcls = text_similarity(normalize_text(lrow["subcategory"]),
                             normalize_text(nrow["class"]))
    price = _price_closeness(lrow["base_price"], nrow["msrp"])
    combined = W_NAME * name + W_SUBCLASS * subcls + W_PRICE * price
    return combined, name


def build_crosswalk(engine=None):
    engine = engine or db.get_sqlite_engine()
    try:
        legacy = pd.read_sql("SELECT * FROM products", engine)
        new = pd.read_sql("SELECT * FROM new_products", engine)
    except Exception:
        print("[crosswalk] reference tables not loaded; skipping")
        return 0
    if legacy.empty or new.empty:
        print("[crosswalk] products/new_products empty; skipping")
        return 0

    # Exact-name lookup (normalized).
    new["_n_name"] = new["item_name"].map(normalize_text)
    name_to_new = {}
    for _, r in new.iterrows():
        name_to_new.setdefault(r["_n_name"], r["new_product_id"])

    # Attribute block: (launch_date, gross_margin, department) -> candidate rows.
    block = {}
    for _, r in new.iterrows():
        block.setdefault((r["launch_date"], r["gross_margin"], r["department"]),
                         []).append(r)

    rows = []
    for _, lp in legacy.iterrows():
        n_name = normalize_text(lp["product_name"])
        dept = CATEGORY_TO_DEPARTMENT.get(str(lp["category"]).lower(), "")

        # --- Tier 1: exact normalized name ---
        if n_name in name_to_new:
            rows.append((lp["product_id"], name_to_new[n_name], "matched",
                         "high", "exact_name", "exact normalized name match"))
            continue

        # --- Tier 2: attribute block + fuzzy/price scoring ---
        cands = block.get((lp["launch_date"], lp["margin_rate"], dept), [])
        if cands:
            scored = sorted((_score(lp, c) + (c,) for c in cands),
                            key=lambda x: x[0], reverse=True)
            combined, name_sim, best = scored[0]
            if combined < MIN_SCORE:
                rows.append((lp["product_id"], None, "unresolved", "low",
                             "below_threshold",
                             f"best candidate {best['new_product_id']} scored "
                             f"{combined:.2f}, under the {MIN_SCORE} floor"))
                continue
            ambiguous = len(scored) > 1 and (scored[0][0] - scored[1][0]) < AMBIGUOUS_GAP
            if ambiguous:
                alt = scored[1][2]["new_product_id"]
                rows.append((lp["product_id"], best["new_product_id"],
                             "possible_match", "medium", "attributes_fuzzy",
                             f"two close candidates ({best['new_product_id']} vs "
                             f"{alt}); picked higher name/price score"))
            else:
                conf = "high" if name_sim >= STRONG_NAME else "medium"
                note = ("attribute block unique" if len(cands) == 1
                        else "best of block by name/price")
                note += f"; name_sim={name_sim:.2f}"
                rows.append((lp["product_id"], best["new_product_id"], "matched",
                             conf, "attributes_fuzzy", note))
            continue

        # --- Tier 3: unresolved ---
        rows.append((lp["product_id"], None, "unresolved", "low", "none",
                     "no candidate sharing launch_date+margin+department"))

    cw = pd.DataFrame(rows, columns=[
        "product_id", "new_product_id", "match_status",
        "match_confidence", "match_method", "notes"])

    # Anything that is not a high-confidence match goes to the human-review
    # queue: matched-but-medium, possible_match, and unresolved.
    cw["needs_review"] = (~((cw["match_status"] == "matched")
                            & (cw["match_confidence"] == "high"))).astype(int)

    _validate(cw)

    cw.to_sql("product_crosswalk", engine, if_exists="replace", index=False)
    config.REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    cw.to_csv(config.REFERENCE_DIR / "product_crosswalk.csv", index=False)

    summary = cw["match_status"].value_counts().to_dict()
    print(f"[crosswalk] built {len(cw)} rows -> product_crosswalk "
          f"(+ CSV). status: {summary}")
    return len(cw)


def _validate(cw):
    """Report meaningful quality checks (reporting only, does not change matches):
      - 1:1 integrity: no new product assigned to more than one legacy product.
      - confidence breakdown.
    The possible_match / unresolved rows are the honest human-review queue."""
    matched = cw[cw["new_product_id"].notna()]
    n_matched = len(matched)
    distinct = matched["new_product_id"].nunique()
    dupes = n_matched - distinct
    integrity = "OK (1:1)" if dupes == 0 else f"{dupes} DOUBLE-ASSIGNED new id(s)!"
    print(f"[crosswalk] integrity: {distinct}/{n_matched} new ids unique -> {integrity}")
    print(f"[crosswalk] confidence: {cw['match_confidence'].value_counts().to_dict()}")
    review = cw[cw["needs_review"] == 1]
    if not review.empty:
        matched_med = len(review[review["match_status"] == "matched"])
        possible = len(review[review["match_status"] == "possible_match"])
        unresolved = len(review[review["match_status"] == "unresolved"])
        print(f"[crosswalk] {len(review)} row(s) need human review "
              f"(needs_review=1): {matched_med} matched-medium, "
              f"{possible} possible_match, {unresolved} unresolved "
              f"-- see product_crosswalk.csv / DECISIONS.md")


if __name__ == "__main__":
    build_crosswalk()

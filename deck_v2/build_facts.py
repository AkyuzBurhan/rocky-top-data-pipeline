"""Generate deck_v2/facts.json: every number the v2 deck is allowed to say.

Two databases, on purpose:

  S = the LOCKED snapshot, `git show 82d221e:rocky_top.db`. Every deck figure
      comes from here, so the slides reproduce exactly what the team rehearsed
      and what analysis/rain_analysis_output.md documents.
  L = the LIVE database in this worktree (pinned at 1f7fc1a). Used for the
      "has it run since?" facts and for the DELTA LEDGER: the same statistics
      recomputed on today's data, so every presenter knows which numbers have
      moved and why before an instructor asks.

Conventions are the deck's, lifted from analysis/rain_analysis.py and NOT
re-derived (any deviation fails to reproduce the locked figures):
  - rain day = store-day grain, MAX(precipitation_sum) strictly > 1.0mm
  - revenue lifts are MEDIANS of store-day net revenue
  - agreement counts all 8 stores; a store with no rain days counts as no-lift
  - channel shift is share of order LINES, pooled two-proportion z test

The build ASSERTS that window-invariant facts (revenue, row counts, crosswalk)
agree between S and L. If the pipeline ever changed them, this fails loudly
rather than shipping a slide that disagrees with the repo.

Usage:
    uv run python deck_v2/build_facts.py
"""

import json
import math
import re
import sqlite3
import statistics
import subprocess
import sys
from pathlib import Path

import pandas as pd
from scipy import stats

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from helpers.matching import normalize_text, text_similarity  # noqa: E402

LOCK_COMMIT = "82d221e"
LIVE_DB = ROOT / "rocky_top.db"
SNAP_DB = HERE / "assets" / "locked_snapshot.db"
OUT_JSON = HERE / "facts.json"

RAIN_MM = 1.0
THRESHOLDS = [0.4, 1.0, 5.0, 10.0]
WINDOW_START, WINDOW_END = "2026-07-07", "2026-08-07"

# crosswalk scoring, mirroring src/crosswalk.py
W_NAME, W_SUBCLASS, W_PRICE = 0.6, 0.2, 0.2
MIN_SCORE, AMBIGUOUS_GAP, STRONG_NAME = 0.60, 0.05, 0.85
CATEGORY_TO_DEPARTMENT = {
    "camping": "camping", "emergency": "preparedness", "footwear": "footwear",
    "hydration": "drinkware", "outerwear": "apparel", "patio": "patio",
}

FACTS = {}


def fact(fid, value, display, source, derivation, anchor, unit=""):
    """Record one fact. `display` is what a slide may print, verbatim."""
    FACTS[fid] = {
        "value": value,
        "display": display,
        "unit": unit,
        "source": source,          # S = locked snapshot, L = live, const, file
        "derivation": derivation,
        "anchor": anchor,
    }
    return value


def ensure_snapshot():
    """Extract the locked DB from git. Binary-safe (no shell redirection)."""
    if SNAP_DB.exists() and SNAP_DB.stat().st_size > 0:
        return
    SNAP_DB.parent.mkdir(parents=True, exist_ok=True)
    with SNAP_DB.open("wb") as fh:
        proc = subprocess.run(["git", "show", f"{LOCK_COMMIT}:rocky_top.db"],
                              cwd=ROOT, stdout=fh, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        SNAP_DB.unlink(missing_ok=True)
        sys.exit(f"could not extract {LOCK_COMMIT}:rocky_top.db -> "
                 f"{proc.stderr.decode(errors='replace')}")
    print(f"[snapshot] extracted {LOCK_COMMIT}:rocky_top.db "
          f"({SNAP_DB.stat().st_size:,} bytes)")


def connect_ro(path):
    return sqlite3.connect(f"file:{Path(path).as_posix()}?mode=ro", uri=True)


def store_days(con, window=False):
    """(order_date, store_id, net_revenue, precipitation_sum, temp_max) rows."""
    sql = ("SELECT order_date, store_id, SUM(net_revenue), "
           "MAX(precipitation_sum), MAX(temp_max) FROM daily_sales ")
    if window:
        sql += f"WHERE order_date BETWEEN '{WINDOW_START}' AND '{WINDOW_END}' "
    return con.execute(sql + "GROUP BY order_date, store_id").fetchall()


# --------------------------------------------------------------------------
# statistics, exactly as analysis/rain_analysis.py computes them
# --------------------------------------------------------------------------
def channel_mix(con, sd, window=False):
    """Channel share on rainy vs dry store-days + pooled two-proportion z."""
    rain = {(d, s): p > RAIN_MM for d, s, _, p, _ in sd}
    counts = {True: {}, False: {}}
    sql = "SELECT order_date, store_id, sales_channel FROM clean_orders"
    if window:
        sql += (f" WHERE order_date BETWEEN '{WINDOW_START}' "
                f"AND '{WINDOW_END}'")
    for d, s, ch in con.execute(sql):
        if (d, s) not in rain:
            continue
        side = counts[rain[(d, s)]]
        side[ch] = side.get(ch, 0) + 1
    n_rain, n_dry = sum(counts[True].values()), sum(counts[False].values())
    shares = {ch: (counts[False].get(ch, 0) / n_dry * 100,
                   counts[True].get(ch, 0) / n_rain * 100)
              for ch in ("in_store", "pickup", "ship_from_store")}
    p1 = counts[True]["pickup"] / n_rain
    p2 = counts[False]["pickup"] / n_dry
    pool = (counts[True]["pickup"] + counts[False]["pickup"]) / (n_rain + n_dry)
    z = (p1 - p2) / math.sqrt(pool * (1 - pool) * (1 / n_rain + 1 / n_dry))
    p = math.erfc(abs(z) / math.sqrt(2))
    # the deck's +3.7pp is the difference of the ROUNDED shares
    shift = round(p1 * 100, 1) - round(p2 * 100, 1)
    return {"lines": n_rain + n_dry, "rain": n_rain, "dry": n_dry,
            "shares": shares, "shift_pp": shift, "z": z, "p": p}


def threshold_lifts(sd, stores):
    """Median store-day revenue lift, rain vs dry, at each cutoff."""
    out = []
    for thr in THRESHOLDS:
        rainy = [rev for _, _, rev, p, _ in sd if p > thr]
        dry = [rev for _, _, rev, p, _ in sd if not p > thr]
        lift = (statistics.median(rainy) / statistics.median(dry) - 1) * 100
        agree = 0
        for s in stores:
            sr = [rev for _, st, rev, p, _ in sd if st == s and p > thr]
            sdry = [rev for _, st, rev, p, _ in sd if st == s and not p > thr]
            if sr and sdry and statistics.median(sr) > statistics.median(sdry):
                agree += 1
        out.append({"threshold": thr, "lift": lift, "agree": agree,
                    "of": len(stores)})
    return out


def store_mix(sd, stores):
    rows, shares, medians = [], [], []
    for s in stores:
        days = [r for r in sd if r[1] == s]
        n_rain = sum(1 for r in days if r[3] > RAIN_MM)
        share = n_rain / len(days)
        med = statistics.median(r[2] for r in days)
        rows.append({"store": s, "rain_days": n_rain, "days": len(days),
                     "share": share * 100, "median_revenue": med})
        shares.append(share)
        medians.append(med)
    rho, p = stats.spearmanr(shares, medians)
    return rows, float(rho), float(p)


def per_store_tests(sd, stores):
    hits, rows = [], []
    for s in stores:
        days = sorted(r for r in sd if r[1] == s)
        rev = [r[2] for r in days]
        rt, pt = stats.spearmanr(rev, [r[4] for r in days])
        rp, pp = stats.spearmanr(rev, [r[3] for r in days])
        rows.append({"store": s, "rho_temp": float(rt), "p_temp": float(pt),
                     "rho_precip": float(rp), "p_precip": float(pp)})
        if pt < 0.05:
            hits.append((s, "temp_max", float(rt), float(pt)))
        if pp < 0.05:
            hits.append((s, "precip", float(rp), float(pp)))
    return rows, hits


def crosswalk_scores(con):
    """Re-score the Tier-2 blocks exactly as src/crosswalk.py does."""
    legacy = pd.read_sql("SELECT * FROM products", con)
    new = pd.read_sql("SELECT * FROM new_products", con)

    def closeness(base, msrp):
        b, m = float(base), float(msrp)
        return max(0.0, 1.0 - abs(m - b) / b) if b > 0 else 0.0

    exact = {normalize_text(r["item_name"]) for _, r in new.iterrows()}
    block = {}
    for _, r in new.iterrows():
        block.setdefault((r["launch_date"], r["gross_margin"],
                          r["department"]), []).append(r)

    matched, possible, rejected, exhibit = [], [], [], None
    for _, lp in legacy.iterrows():
        if normalize_text(lp["product_name"]) in exact:
            continue
        cands = block.get((lp["launch_date"], lp["margin_rate"],
                           CATEGORY_TO_DEPARTMENT.get(
                               str(lp["category"]).lower(), "")), [])
        scored = []
        for c in cands:
            name = text_similarity(normalize_text(lp["product_name"]),
                                   normalize_text(c["item_name"]))
            sub = text_similarity(normalize_text(lp["subcategory"]),
                                  normalize_text(c["class"]))
            price = closeness(lp["base_price"], c["msrp"])
            scored.append((W_NAME * name + W_SUBCLASS * sub + W_PRICE * price,
                           lp["product_id"], c["new_product_id"],
                           name, sub, price))
        if not scored:
            continue
        scored.sort(reverse=True)
        top = scored[0]
        if top[1] == "P1076":
            exhibit = top
        if top[0] < MIN_SCORE:
            rejected.append(top)
        elif len(scored) > 1 and scored[0][0] - scored[1][0] < AMBIGUOUS_GAP:
            possible.append(top)
        else:
            matched.append(top)
        rejected.extend(scored[1:])
    return matched, possible, rejected, exhibit


# --------------------------------------------------------------------------
def scalar(con, sql):
    return con.execute(sql).fetchone()[0]


def money(x):
    return f"${x:,.2f}"


def build():
    ensure_snapshot()
    S = connect_ro(SNAP_DB)
    L = connect_ro(LIVE_DB)

    # ---------------- window + scale ----------------
    sd = store_days(S)
    stores = sorted({r[1] for r in sd})
    dates = sorted({r[0] for r in sd})

    fact("window_start", WINDOW_START, "July 7", "const",
         "frozen analysis window", "docs/DECISIONS.md section 5")
    fact("window_end", WINDOW_END, "August 7", "const",
         "frozen analysis window", "docs/DECISIONS.md section 5")
    fact("window_days", 32, "32 days", "const",
         "calendar days 07-07..08-07 inclusive", "docs/plan.md")
    fact("order_dates", len(dates), f"{len(dates)} selling days", "S",
         "COUNT(DISTINCT order_date) FROM daily_sales", "rocky_top.db@82d221e")
    fact("stores", len(stores), f"{len(stores)} stores", "S",
         "COUNT(DISTINCT store_id) FROM daily_sales", "rocky_top.db@82d221e")
    # bare count: callers supply the noun, so it reads correctly inline
    fact("store_days", len(sd), f"{len(sd)}", "S",
         "COUNT(*) over GROUP BY order_date, store_id (independent weather "
         "observations)", "rocky_top.db@82d221e")

    net = scalar(S, "SELECT SUM(net_revenue) FROM daily_sales")
    gross = scalar(S, "SELECT SUM(gross_revenue) FROM daily_sales")
    fact("net_revenue", round(net, 2), money(net), "S",
         "SUM(net_revenue) FROM daily_sales", "docs/DECISIONS.md revenue table")
    fact("gross_revenue", round(gross, 2), money(gross), "S",
         "SUM(gross_revenue) FROM daily_sales",
         "docs/DECISIONS.md revenue table")

    clean_rows = scalar(S, "SELECT COUNT(*) FROM clean_orders")
    daily_rows = scalar(S, "SELECT COUNT(*) FROM daily_sales")
    weather_rows = scalar(S, "SELECT COUNT(*) FROM weather_daily")
    fact("clean_rows", clean_rows, f"{clean_rows:,}", "S",
         "COUNT(*) FROM clean_orders", "rocky_top.db@82d221e")
    fact("daily_rows", daily_rows, f"{daily_rows:,}", "S",
         "COUNT(*) FROM daily_sales", "rocky_top.db@82d221e")
    fact("weather_rows", weather_rows, f"{weather_rows}", "S",
         "COUNT(*) FROM weather_daily", "rocky_top.db@82d221e")

    rej = dict(S.execute(
        "SELECT reason, COUNT(*) FROM rejected_rows GROUP BY reason").fetchall())
    rej_total = sum(rej.values())
    fact("rejected_total", rej_total, f"{rej_total}", "S",
         "COUNT(*) FROM rejected_rows", "rocky_top.db@82d221e")
    fact("rejected_breakdown", rej,
         f"{rej.get('duplicate_natural_key', 0)} duplicate rows quarantined",
         "S", "GROUP BY reason FROM rejected_rows", "rocky_top.db@82d221e")
    # the deck's "140 stale-file dupes + 4 within-file dupes" split lives in
    # source_file, not in `reason` (both carry duplicate_natural_key)
    by_file = dict(S.execute(
        "SELECT source_file, COUNT(*) FROM rejected_rows "
        "GROUP BY source_file ORDER BY COUNT(*) DESC").fetchall())
    fact("rejected_by_file", by_file,
         " + ".join(f"{n} from {f[7:17]}" for f, n in by_file.items()), "S",
         "GROUP BY source_file FROM rejected_rows", "rocky_top.db@82d221e")
    if by_file:
        top_file, top_n = next(iter(by_file.items()))
        fact("rejected_stale", top_n, f"{top_n}", "S",
             f"rejected rows from {top_file} (the re-sent file)",
             "docs/DECISIONS.md section 3")
        fact("rejected_other", rej_total - top_n, f"{rej_total - top_n}", "S",
             "rejected rows from every other file (within-file duplicates)",
             "docs/DECISIONS.md section 3")

    # ---------------- the $-sign day ----------------
    r0805 = S.execute(
        "SELECT SUM(line_revenue), COUNT(*) FROM clean_orders "
        "WHERE order_date = '2026-08-05'").fetchone()
    g0805 = scalar(S, "SELECT SUM(gross_revenue) FROM daily_sales "
                      "WHERE order_date = '2026-08-05'")
    fact("recovered_0805_net", round(r0805[0], 2), money(r0805[0]), "S",
         "SUM(line_revenue) FROM clean_orders WHERE order_date='2026-08-05'",
         "docs/DECISIONS.md Limitation 1")
    fact("recovered_0805_gross", round(g0805, 2), money(g0805), "S",
         "SUM(gross_revenue) FROM daily_sales WHERE order_date='2026-08-05'",
         "docs/DECISIONS.md Limitation 1")
    fact("recovered_0805_lines", r0805[1], f"{r0805[1]} order lines", "S",
         "COUNT(*) FROM clean_orders WHERE order_date='2026-08-05'",
         "data/raw/orders_2026-08-05.csv")

    # ---------------- incident count, derived not asserted ----------------
    ing = pd.read_csv(ROOT / "data" / "ingestion_log.csv", dtype=str)
    win = ing[ing["source_date_expected"].between(WINDOW_START, WINDOW_END)]
    bad = win[win["status"].isin(["stale", "empty", "failed"])]
    incident_dates = sorted(set(bad["source_date_expected"]))
    dq = pd.read_csv(ROOT / "data" / "data_quality_log.csv", dtype=str)
    migration = sorted(dq[dq["product_col"] == "new_product_id"]["file_name"])
    migration_date = re.search(r"(\d{4}-\d{2}-\d{2})", migration[0]).group(1)
    incident_dates.append(migration_date)
    # the $-day: the only raw file whose unit_price carries currency symbols
    dollar_dates = []
    headers = {}
    for path in sorted((ROOT / "data" / "raw").glob("orders_*.csv")):
        date = re.search(r"(\d{4}-\d{2}-\d{2})", path.name).group(1)
        if not (WINDOW_START <= date <= WINDOW_END):
            continue
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        headers[date] = lines[0] if lines else ""
        if any("$" in ln for ln in lines[1:]):
            dollar_dates.append(date)
    incident_dates += dollar_dates
    # header reorder: same column SET, different order than the previous file
    reorder_dates = []
    prev = None
    for date in sorted(headers):
        cur = headers[date].split(",")
        if prev and cur != prev and sorted(cur) == sorted(prev):
            reorder_dates.append(date)
        if cur:
            prev = cur
    incident_dates += reorder_dates
    incident_dates = sorted(set(incident_dates))
    fact("incident_dates", incident_dates, " / ".join(incident_dates), "L",
         "ingestion statuses + first new-ID file + currency-symbol scan + "
         "header-order diff, all restricted to the window",
         "data/ingestion_log.csv, data/data_quality_log.csv, data/raw/")
    fact("incident_count", len(incident_dates), f"{len(incident_dates)}", "L",
         "len(incident_dates)", "derived above")
    fact("incident_caught_at_source", len(incident_dates) - len(dollar_dates),
         f"{len(incident_dates) - len(dollar_dates)}", "L",
         "incidents minus the one found only in audit (the $-price day)",
         "docs/DECISIONS.md section 3")
    fact("migration_date", migration_date, "July 28", "L",
         "first data_quality_log row with product_col=new_product_id",
         "data/data_quality_log.csv")

    # ---------------- crosswalk ----------------
    cw = pd.read_sql("SELECT * FROM product_crosswalk", S)
    status = cw["match_status"].value_counts().to_dict()
    method = cw["match_method"].value_counts().to_dict()
    fact("cw_total", len(cw), f"{len(cw)}", "S",
         "COUNT(*) FROM product_crosswalk", "rocky_top.db@82d221e")
    fact("cw_matched", status.get("matched", 0), f"{status.get('matched', 0)}",
         "S", "GROUP BY match_status", "rocky_top.db@82d221e")
    fact("cw_possible", status.get("possible_match", 0),
         f"{status.get('possible_match', 0)}", "S", "GROUP BY match_status",
         "rocky_top.db@82d221e")
    fact("cw_unresolved", status.get("unresolved", 0),
         f"{status.get('unresolved', 0)}", "S", "GROUP BY match_status",
         "rocky_top.db@82d221e")
    fact("cw_exact", method.get("exact_name", 0), f"{method.get('exact_name', 0)}",
         "S", "GROUP BY match_method", "rocky_top.db@82d221e")
    fact("cw_fuzzy", method.get("attributes_fuzzy", 0),
         f"{method.get('attributes_fuzzy', 0)}", "S", "GROUP BY match_method",
         "rocky_top.db@82d221e")
    fact("cw_none", method.get("none", 0) + method.get("below_threshold", 0),
         f"{method.get('none', 0) + method.get('below_threshold', 0)}", "S",
         "GROUP BY match_method (none + below_threshold)",
         "rocky_top.db@82d221e")

    mapped = cw["new_product_id"].notna().sum()
    review = cw[cw["needs_review"] == 1]
    r_matched = len(review[review["match_status"] == "matched"])
    r_possible = len(review[review["match_status"] == "possible_match"])
    r_unres = len(review[review["match_status"] == "unresolved"])
    fact("cw_mapped", int(mapped), f"{mapped} of {len(cw)}", "S",
         "COUNT(new_product_id IS NOT NULL)", "rocky_top.db@82d221e")
    fact("cw_review", len(review), f"{len(review)}", "S",
         "COUNT(needs_review = 1)", "rocky_top.db@82d221e")
    fact("cw_review_split", [r_matched, r_possible, r_unres],
         f"{r_matched} medium-confidence, {r_possible} too-close-to-call, "
         f"{r_unres} no match", "S",
         "needs_review=1 split by match_status", "rocky_top.db@82d221e")
    fact("cw_flow_unblocked", r_matched + r_possible,
         f"{r_matched + r_possible} of {len(review)}", "S",
         "flagged rows that still carry a new_product_id",
         "docs/DECISIONS.md Limitations")

    # integrity: persisted here for the first time (closes Limitation 2)
    m = cw[cw["new_product_id"].notna()]
    uniq = m["new_product_id"].nunique()
    fact("cw_integrity", [int(uniq), int(len(m))],
         f"{uniq}/{len(m)} unique (1:1)", "S",
         "COUNT(DISTINCT new_product_id) vs COUNT(*) among mapped rows; "
         "src/crosswalk.py _validate() computes this but only prints it",
         "src/crosswalk.py:159-179 -- persisted here, not in the pipeline")

    decoys = sorted(cw[cw["match_status"] == "possible_match"]["product_id"])
    unres_ids = sorted(cw[cw["match_status"] == "unresolved"]["product_id"])
    fact("cw_decoys", decoys, ", ".join(decoys), "S",
         "product_id WHERE match_status='possible_match'",
         "data/reference/new_products.csv (the '... Alt' twins)")
    fact("cw_unresolved_ids", unres_ids, ", ".join(unres_ids), "S",
         "product_id WHERE match_status='unresolved'", "rocky_top.db@82d221e")

    matched_s, possible_s, rejected_s, exhibit = crosswalk_scores(S)
    acc = sorted([s[0] for s in matched_s] + [s[0] for s in possible_s])
    rej_scores = sorted(s[0] for s in rejected_s)
    lo, hi = max(acc[0], rej_scores[0]), min(acc[-1], rej_scores[-1])
    fact("cw_overlap", [round(lo, 3), round(hi, 3)], f"{lo:.3f} to {hi:.3f}",
         "S", "score range where accepted and rejected candidates overlap",
         "analysis/rain_analysis_output.md")
    # full distributions, for the score-overlap chart
    fact("cw_scores_accepted", [round(s, 3) for s in acc],
         f"{len(acc)} accepted candidate scores", "S",
         "composite scores of accepted matches (matched + possible_match)",
         "analysis/rain_analysis_output.md")
    fact("cw_scores_rejected", [round(s, 3) for s in rej_scores],
         f"{len(rej_scores)} rejected candidate scores", "S",
         "composite scores of runner-up candidates that were not accepted",
         "analysis/rain_analysis_output.md")
    weakest = min(matched_s)
    fact("cw_weakest", [weakest[1], round(weakest[0], 3)],
         f"{weakest[1]} at {weakest[0]:.3f}", "S",
         "lowest composite among accepted 'matched' rows",
         "analysis/rain_analysis_output.md")
    fact("cw_floor", MIN_SCORE, "0.60", "const",
         "MIN_SCORE in src/crosswalk.py", "src/crosswalk.py:49")
    fact("cw_strong_name", STRONG_NAME, "0.85", "const",
         "STRONG_NAME in src/crosswalk.py", "src/crosswalk.py:47")
    if exhibit:
        fact("p1076_name", round(exhibit[3], 2), f"{exhibit[3]:.2f}", "S",
             "token_set_ratio(product_name, item_name)", "src/crosswalk.py")
        fact("p1076_subclass", round(exhibit[4], 2), f"{exhibit[4]:.2f}", "S",
             "token_set_ratio(subcategory, class)", "src/crosswalk.py")
        fact("p1076_price", round(exhibit[5], 3), f"{exhibit[5]:.3f}", "S",
             "max(0, 1 - abs(msrp - base_price)/base_price)", "src/crosswalk.py")
        fact("p1076_composite", round(exhibit[0], 3), f"{exhibit[0]:.3f}", "S",
             "0.6*name + 0.2*subclass + 0.2*price", "src/crosswalk.py:61-68")
        fact("p1076_margin", round(exhibit[0] - MIN_SCORE, 3),
             f"{exhibit[0] - MIN_SCORE:.3f}", "S",
             "composite minus the 0.60 floor", "docs/plan.md P1076 card")

    # ---------------- weather findings ----------------
    mix = channel_mix(S, sd)
    fact("mix_lines", mix["lines"], f"{mix['lines']:,}", "S",
         "COUNT(*) FROM clean_orders in window", "rain_analysis_output.md")
    fact("mix_rain_lines", mix["rain"], f"{mix['rain']:,}", "S",
         "order lines on rainy store-days", "rain_analysis_output.md")
    fact("mix_dry_lines", mix["dry"], f"{mix['dry']:,}", "S",
         "order lines on dry store-days", "rain_analysis_output.md")
    for ch, key in [("in_store", "mix_instore"), ("pickup", "mix_pickup"),
                    ("ship_from_store", "mix_ship")]:
        d, r = mix["shares"][ch]
        fact(key, [round(d, 1), round(r, 1)], f"{d:.1f}% to {r:.1f}%", "S",
             f"{ch} share of order lines, dry vs rain",
             "rain_analysis_output.md 7a")
    fact("mix_shift_pp", round(mix["shift_pp"], 1),
         f"+{mix['shift_pp']:.1f} points", "S",
         "pickup share difference on the rounded shares",
         "rain_analysis_output.md 7a")
    fact("mix_z", round(mix["z"], 2), f"{mix['z']:.2f}", "S",
         "pooled two-proportion z on pickup share", "rain_analysis_output.md")
    fact("mix_p", round(mix["p"], 4), f"{mix['p']:.3f}", "S",
         "two-sided p for the z above", "rain_analysis_output.md")
    fact("rain_definition", "precipitation_sum > 1.0mm",
         "a store-day with more than 1mm of rain", "const",
         "strict >, store-day grain (three store-days sit at exactly 1.0mm)",
         "analysis/rain_analysis.py:37")

    lifts = threshold_lifts(sd, stores)
    fact("lifts", lifts,
         " / ".join(f"{l['threshold']:g}mm {l['lift']:+.1f}% "
                    f"({l['agree']}/{l['of']})" for l in lifts), "S",
         "median store-day revenue, rainy vs dry, at each cutoff; agreement "
         "counts stores whose own rainy median beats their dry median",
         "rain_analysis_output.md 7b")
    for l in lifts:
        # 0.4 -> lift_0_4, 1.0 -> lift_1, 10.0 -> lift_10 (no collisions)
        key = "lift_" + f"{l['threshold']:g}".replace(".", "_")
        fact(key, [round(l["lift"], 1), l["agree"], l["of"]],
             f"{l['lift']:+.1f}% ({l['agree']} of {l['of']} stores)", "S",
             f"median lift at >{l['threshold']:g}mm",
             "rain_analysis_output.md 7b")
    headline = next(l for l in lifts if l["threshold"] == 1.0)
    fact("lift_headline", round(headline["lift"], 1),
         f"{headline['lift']:+.0f}%", "S",
         "the 1mm lift, the claim that failed sensitivity",
         "rain_analysis_output.md 7b")

    mix_rows, rho, rho_p = store_mix(sd, stores)
    fact("store_mix", mix_rows,
         " / ".join(f"{r['store']} {r['share']:.0f}% ${r['median_revenue']:,.0f}"
                    for r in mix_rows), "S",
         "rain-day share and median daily revenue per store",
         "rain_analysis_output.md")
    top = max(mix_rows, key=lambda r: r["share"])
    bot = min(mix_rows, key=lambda r: r["share"])
    fact("storemix_rainiest",
         [top["store"], round(top["share"]), round(top["median_revenue"])],
         f"{top['store']}: {top['share']:.0f}% rainy days, "
         f"${top['median_revenue']:,.0f} median day", "S",
         "store with the highest rain-day share", "rain_analysis_output.md")
    fact("storemix_driest",
         [bot["store"], round(bot["share"]), round(bot["median_revenue"])],
         f"{bot['store']}: {bot['share']:.0f}% rainy days, "
         f"${bot['median_revenue']:,.0f} median day", "S",
         "store with the lowest rain-day share", "rain_analysis_output.md")
    fact("storemix_spearman", [round(rho, 3), round(rho_p, 2)],
         f"rho = {rho:.2f} (p = {rho_p:.2f}, n = {len(stores)})", "S",
         "Spearman, rain-day share vs median daily revenue across stores",
         "rain_analysis_output.md")

    test_rows, hits = per_store_tests(sd, stores)
    fact("tests_total", len(test_rows) * 2, f"{len(test_rows) * 2}", "S",
         "8 stores x 2 weather variables", "rain_analysis_output.md")
    fact("tests_hits", len(hits), f"{len(hits)}", "S",
         "tests significant at p < .05", "rain_analysis_output.md")
    if hits:
        s, var, r, p = hits[0]
        fact("tests_hit_detail", [s, var, round(r, 2), round(p, 3)],
             f"{s} vs temperature: rho = {r:.2f}, p = {p:.3f}", "S",
             "the single significant test", "rain_analysis_output.md")
    fact("tests_table", test_rows, "per-store Spearman table", "S",
         "store-day net revenue vs temp_max and precipitation_sum",
         "rain_analysis_output.md")

    boundary = sorted((d, s) for d, s, _, p, _ in sd if p == RAIN_MM)
    fact("boundary_days", [f"{s} {d[5:]}" for d, s in boundary],
         ", ".join(f"{s} {d[5:]}" for d, s in boundary), "S",
         "store-days sitting exactly on the 1.0mm cutoff",
         "docs/DECISIONS.md section 5")
    pilots = sorted(mix_rows, key=lambda r: -r["share"])[:2]
    fact("pilot_stores",
         [[p["store"], p["rain_days"], p["days"]] for p in pilots],
         " and ".join(f"{p['store']} ({p['rain_days']} of {p['days']} days)"
                      for p in pilots), "S",
         "the two highest rain-frequency stores; both operator-invariant",
         "docs/DECISIONS.md section 5")

    # ---------------- orphan + schema debt ----------------
    np_rows = S.execute(
        "SELECT COUNT(*), SUM(net_revenue) FROM daily_sales "
        "WHERE category = 'UNKNOWN'").fetchone()
    np_lines = scalar(S, "SELECT COUNT(*) FROM clean_orders "
                         "WHERE product_key = 'NP9999'")
    fact("np9999_revenue", round(np_rows[1], 2), money(np_rows[1]), "S",
         "SUM(net_revenue) FROM daily_sales WHERE category='UNKNOWN'",
         "docs/DECISIONS.md section 5")
    fact("np9999_lines", np_lines, f"{np_lines} order lines", "S",
         "COUNT(*) FROM clean_orders WHERE product_key='NP9999'",
         "data/raw/orders_2026-07-30.csv")

    ddl = dict(S.execute(
        "SELECT name, sql FROM sqlite_master WHERE type='table'").fetchall())
    declared = {"raw_orders", "stores", "products", "new_products",
                "ingestion_log", "product_crosswalk", "weather_daily",
                "rejected_rows", "clean_orders", "daily_sales"}
    bare = sorted(t for t in declared
                  if not re.search(r"PRIMARY KEY|UNIQUE|REFERENCES|NOT NULL",
                                   ddl.get(t) or "", re.I))
    fact("constraints_bare", [len(bare), len(declared)],
         f"{len(bare)} of {len(declared)} tables", "S",
         "tables in sqlite_master whose live DDL carries no PK/UNIQUE/FK/"
         "NOT NULL, i.e. rebuilt bare by to_sql(if_exists='replace')",
         "sql/01_schema.sql vs rocky_top.db@82d221e")
    fact("constraints_bare_tables", bare, ", ".join(bare), "S",
         "the affected table names", "sqlite_master")

    # ---------------- poison fixture ----------------
    meta_path = ROOT / "deck" / "out" / "fixture" / "poison_fixture_meta.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        # display is a bare noun phrase so callers supply their own verb
        # ("Executed {poison_meta}") without doubling it up
        fact("poison_meta", meta,
             f"{meta.get('date')} at commit {meta.get('commit')}",
             "file", "committed artifact from deck/poison_fixture.py",
             "deck/out/fixture/poison_fixture_meta.json")
    log_path = ROOT / "deck" / "out" / "fixture" / "poison_fixture_log.txt"
    if log_path.exists():
        log = log_path.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"nonnumeric\(unit_price=(\d+)\)", log)
        n = int(m.group(1)) if m else 0
        # bare count, so callers write their own verb ("flagged all {n}")
        fact("poison_gate", n, f"{n}", "file",
             "nonnumeric(unit_price=N) flag in the executed fixture log",
             "deck/out/fixture/poison_fixture_log.txt")

    # ---------------- live facts ----------------
    raw_files = sorted((ROOT / "data" / "raw").glob("orders_*.csv"))
    fact("live_raw_files", len(raw_files), f"{len(raw_files)}", "L",
         "count of data/raw/orders_*.csv", "worktree at 1f7fc1a")
    fact("live_ingestion_rows", len(ing), f"{len(ing)}", "L",
         "rows in data/ingestion_log.csv", "worktree at 1f7fc1a")
    fact("live_dq_rows", len(dq), f"{len(dq)}", "L",
         "rows in data/data_quality_log.csv", "worktree at 1f7fc1a")
    live_max = scalar(L, "SELECT MAX(order_date) FROM daily_sales")
    fact("live_last_date", live_max, live_max, "L",
         "MAX(order_date) FROM daily_sales", "worktree at 1f7fc1a")

    # ---------------- delta ledger ----------------
    sdl = store_days(L, window=True)
    live_map = {(d, s): p for d, s, _, p, _ in sdl}
    flips, revised = [], []
    for d, s, _, p, _ in sd:
        lp = live_map.get((d, s))
        if lp is None or lp == p:
            continue
        revised.append((d, s, p, lp))
        if (p > RAIN_MM) != (lp > RAIN_MM):
            flips.append({"date": d, "store": s, "locked": p, "live": lp,
                          "was": "rain" if p > RAIN_MM else "dry",
                          "now": "rain" if lp > RAIN_MM else "dry"})
    fact("d_revised", len(revised), f"{len(revised)} store-days", "L",
         "store-days whose precipitation_sum differs between the locked "
         "snapshot and today's database (Open-Meteo revises its archive)",
         "docs/DECISIONS.md Limitation 8")
    fact("d_flips", flips,
         "; ".join(f"{f['store']} {f['date'][5:]} {f['locked']}mm to "
                   f"{f['live']}mm ({f['was']} to {f['now']})" for f in flips)
         or "none", "L", "revisions that crossed the 1.0mm rain cutoff",
         "docs/DECISIONS.md Limitation 8")

    live_stores = sorted({r[1] for r in sdl})
    d_mix = channel_mix(L, sdl, window=True)
    d_lifts = threshold_lifts(sdl, live_stores)
    d_rows, d_rho, d_rho_p = store_mix(sdl, live_stores)
    fact("d_mix_shift", round(d_mix["shift_pp"], 1),
         f"+{d_mix['shift_pp']:.1f} points (z = {d_mix['z']:.2f}, "
         f"p = {d_mix['p']:.3f})", "L",
         "slide-7 channel shift recomputed on today's weather, same window "
         "and same conventions", "delta ledger")
    fact("d_lifts", d_lifts,
         " / ".join(f"{l['threshold']:g}mm {l['lift']:+.1f}% "
                    f"({l['agree']}/{l['of']})" for l in d_lifts), "L",
         "slide-8 threshold table recomputed on today's weather",
         "delta ledger")
    for r in d_rows:
        locked = next(x for x in mix_rows if x["store"] == r["store"])
        if r["rain_days"] != locked["rain_days"]:
            fact(f"d_share_{r['store'].lower()}",
                 [locked["rain_days"], r["rain_days"], r["days"]],
                 f"{r['store']}: {locked['rain_days']}/{locked['days']} rainy "
                 f"days locked, {r['rain_days']}/{r['days']} today", "L",
                 "per-store rain-day count, locked vs live",
                 "analysis/rain_analysis.py:5-8")

    # ---------------- invariants: S must equal L in-window ----------------
    checks = [
        ("net revenue", round(net, 2), round(scalar(
            L, f"SELECT SUM(net_revenue) FROM daily_sales WHERE order_date "
               f"BETWEEN '{WINDOW_START}' AND '{WINDOW_END}'"), 2)),
        ("clean_orders rows", clean_rows, scalar(
            L, f"SELECT COUNT(*) FROM clean_orders WHERE order_date "
               f"BETWEEN '{WINDOW_START}' AND '{WINDOW_END}'")),
        ("daily_sales rows", daily_rows, scalar(
            L, f"SELECT COUNT(*) FROM daily_sales WHERE order_date "
               f"BETWEEN '{WINDOW_START}' AND '{WINDOW_END}'")),
        ("crosswalk matched", status.get("matched", 0), scalar(
            L, "SELECT COUNT(*) FROM product_crosswalk "
               "WHERE match_status='matched'")),
        ("08-05 recovery", round(r0805[0], 2), round(scalar(
            L, "SELECT SUM(line_revenue) FROM clean_orders "
               "WHERE order_date='2026-08-05'"), 2)),
    ]
    failures = [(n, a, b) for n, a, b in checks if a != b]
    for n, a, b in checks:
        print(f"[invariant] {n}: snapshot {a} vs live-in-window {b} "
              f"-> {'OK' if a == b else 'MISMATCH'}")
    if failures:
        sys.exit(f"invariant check failed: {failures}")
    fact("invariants_checked", [c[0] for c in checks],
         f"{len(checks)} figures identical in the locked snapshot and today's "
         "database", "both",
         "window-filtered equality checks run at every facts build",
         "deck_v2/build_facts.py")

    S.close()
    L.close()

    OUT_JSON.write_text(json.dumps({
        "_meta": {
            "lock_commit": LOCK_COMMIT,
            "window": [WINDOW_START, WINDOW_END],
            "rain_rule": "store-day MAX(precipitation_sum) > 1.0mm, strict",
            "lift_rule": "medians of store-day net revenue",
            "generated_by": "deck_v2/build_facts.py",
        },
        "facts": FACTS,
    }, indent=2), encoding="utf-8")
    print(f"\n[written] {OUT_JSON} ({len(FACTS)} facts)")


if __name__ == "__main__":
    build()

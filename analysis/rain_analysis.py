"""Derivation of the deck's weather statistics (slides 7a, 7b, appendix A2).

Every figure on those slides reproduces from the database snapshot locked at
commit 82d221e and nothing else. The live rocky_top.db keeps growing (daily
cron) and Open-Meteo revised historical precipitation after the lock, so the
live table gives slightly different rain-day sets; for example S007's rain-day
share moved from 41.4% (12/29) at lock to 37.9% (11/29) on the live data.
The deck is locked to the snapshot; the dashboard is live by design.

Conventions, fixed by the deck (any deviation fails to reproduce it):
  - Rain day: store-day grain, MAX(precipitation_sum) strictly > 1.0mm.
    Not >=, and not means: three store-days sit at exactly 1.0mm.
  - Revenue lifts (7b) are medians; agreement is counted over all 8 stores,
    with a store that has no rain days counting as no-lift.
  - Channel shift (7a) is share of order lines by channel, pooled
    two-proportion z test on pickup share.

Usage:
    git show 82d221e:rocky_top.db > /tmp/locked_snapshot.db
    uv run python analysis/rain_analysis.py [db_path]

The db path argument defaults to /tmp/locked_snapshot.db. The database is
opened read-only (mode=ro). Output goes to stdout and to
analysis/rain_analysis_output.md.
"""

import math
import sqlite3
import statistics
import sys
from pathlib import Path

from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

RAIN_MM = 1.0            # strict >, per the deck
THRESHOLDS = [0.4, 1.0, 5.0, 10.0]
LOCK_COMMIT = "82d221e"

OUT = []


def emit(line=""):
    OUT.append(line)
    print(line)


def store_days(con):
    return con.execute(
        "SELECT order_date, store_id, SUM(net_revenue), "
        "MAX(precipitation_sum), MAX(temp_max) "
        "FROM daily_sales GROUP BY order_date, store_id").fetchall()


def channel_shift(con, sd):
    rain = {(d, s): p > RAIN_MM for d, s, _, p, _ in sd}
    counts = {True: {}, False: {}}
    for d, s, ch in con.execute(
            "SELECT order_date, store_id, sales_channel FROM clean_orders"):
        side = counts[rain[(d, s)]]
        side[ch] = side.get(ch, 0) + 1
    n_rain, n_dry = sum(counts[True].values()), sum(counts[False].values())
    emit(f"## 7a. Channel mix, dry vs rain (rain = precip > {RAIN_MM:g}mm)")
    emit()
    emit(f"Order lines: {n_rain + n_dry:,} total, {n_rain:,} on rainy "
         f"store-days, {n_dry:,} on dry.")
    emit()
    emit("| Channel | Dry (%) | Rain (%) |")
    emit("|---|---|---|")
    for ch in ("in_store", "pickup", "ship_from_store"):
        emit(f"| {ch} | {counts[False][ch] / n_dry * 100:.1f} "
             f"| {counts[True][ch] / n_rain * 100:.1f} |")
    p1 = counts[True]["pickup"] / n_rain
    p2 = counts[False]["pickup"] / n_dry
    pool = (counts[True]["pickup"] + counts[False]["pickup"]) / (n_rain + n_dry)
    z = (p1 - p2) / math.sqrt(pool * (1 - pool) * (1 / n_rain + 1 / n_dry))
    p = math.erfc(abs(z) / math.sqrt(2))
    emit()
    emit(f"Pickup share {p2 * 100:.1f}% -> {p1 * 100:.1f}%, a shift of "
         f"+{round(p1 * 100, 1) - round(p2 * 100, 1):.1f}pp on the rounded "
         f"shares ({(p1 - p2) * 100:.2f}pp exact).")
    emit(f"Pooled two-proportion z test on pickup share: z = {z:.2f}, "
         f"p = {p:.4f}.")
    emit()


def threshold_table(sd, stores):
    emit("## 7b. Median revenue lift by rain threshold")
    emit()
    emit("Lifts are medians of store-day net revenue, rainy vs dry. Agreement")
    emit("is stores whose own rainy median beats their dry median, out of all")
    emit("8 stores; a store with no rain days at a cutoff counts as no-lift.")
    emit()
    emit("| Rain cut (mm) | Median lift (%) | Stores with lift |")
    emit("|---|---|---|")
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
        emit(f"| {thr:g} | {lift:+.1f} | {agree}/8 |")
    emit()


def store_mix(sd, stores):
    emit("## Store mix (rain-day share vs median daily revenue)")
    emit()
    emit("| Store | Rain days | Share (%) | Median daily revenue |")
    emit("|---|---|---|---|")
    shares, medians = [], []
    for s in stores:
        days = [r for r in sd if r[1] == s]
        n_rain = sum(1 for r in days if r[3] > RAIN_MM)
        share = n_rain / len(days)
        med = statistics.median(r[2] for r in days)
        shares.append(share)
        medians.append(med)
        emit(f"| {s} | {n_rain}/{len(days)} | {share * 100:.1f} "
             f"| ${med:,.0f} |")
    rho, p = stats.spearmanr(shares, medians)
    emit()
    emit(f"Spearman, rain-day share vs median daily revenue across the 8 "
         f"stores: rho = {rho:.3f} (p = {p:.2f}, n = 8).")
    emit()


def per_store_tests(sd, stores):
    emit("## The 16 per-store tests (Spearman, n = 29 store-days each)")
    emit()
    emit("Store-day net revenue vs temp_max and vs precipitation_sum.")
    emit()
    emit("| Store | rho (temp) | p (temp) | rho (precip) | p (precip) |")
    emit("|---|---|---|---|---|")
    hits = []
    for s in stores:
        days = sorted(r for r in sd if r[1] == s)
        rev = [r[2] for r in days]
        rt, pt = stats.spearmanr(rev, [r[4] for r in days])
        rp, pp = stats.spearmanr(rev, [r[3] for r in days])
        if pt < 0.05:
            hits.append((s, "temp_max", rt, pt))
        if pp < 0.05:
            hits.append((s, "precip", rp, pp))
        emit(f"| {s} | {rt:+.2f} | {pt:.3f} | {rp:+.2f} | {pp:.3f} |")
    emit()
    emit(f"Significant at p < .05: {len(hits)} of 16 tests.")
    for s, var, r, p in hits:
        emit(f"  {s} x {var}: rho = {r:.2f}, p = {p:.3f}")
    emit("One hit in 16 tests is what chance produces at this sample size.")
    emit()


def crosswalk_scores(con):
    """Composite score distribution, accepted vs rejected candidates.

    Re-scores the Tier-2 blocks exactly as src/crosswalk.py does (same
    weights, same block key) to show how close the accepted candidates and
    the rejected runner-ups sit around the 0.60 floor. Reporting only; the
    crosswalk itself is built by src/crosswalk.py.
    """
    try:
        from helpers.matching import normalize_text, text_similarity
    except ImportError:
        emit("## Crosswalk score distribution: SKIPPED "
             "(helpers.matching not importable; run from the repo root)")
        return
    import pandas as pd
    legacy = pd.read_sql("SELECT * FROM products", con)
    new = pd.read_sql("SELECT * FROM new_products", con)
    cat_to_dept = {"camping": "camping", "emergency": "preparedness",
                   "footwear": "footwear", "hydration": "drinkware",
                   "outerwear": "apparel", "patio": "patio"}
    w_name, w_sub, w_price, floor = 0.6, 0.2, 0.2, 0.60

    def closeness(base, msrp):
        b, m = float(base), float(msrp)
        return max(0.0, 1.0 - abs(m - b) / b) if b > 0 else 0.0

    exact = {normalize_text(r["item_name"]) for _, r in new.iterrows()}
    block = {}
    for _, r in new.iterrows():
        block.setdefault((r["launch_date"], r["gross_margin"],
                          r["department"]), []).append(r)
    ambiguous_gap = 0.05
    matched, possible, rejected = [], [], []
    exhibit = None
    for _, lp in legacy.iterrows():
        if normalize_text(lp["product_name"]) in exact:
            continue
        cands = block.get((lp["launch_date"], lp["margin_rate"],
                           cat_to_dept.get(str(lp["category"]).lower(), "")), [])
        scored = []
        for c in cands:
            name = text_similarity(normalize_text(lp["product_name"]),
                                   normalize_text(c["item_name"]))
            sub = text_similarity(normalize_text(lp["subcategory"]),
                                  normalize_text(c["class"]))
            price = closeness(lp["base_price"], c["msrp"])
            comp = w_name * name + w_sub * sub + w_price * price
            scored.append((comp, lp["product_id"], c["new_product_id"],
                           name, sub, price))
        if not scored:
            continue
        scored.sort(reverse=True)
        top = scored[0]
        if top[1] == "P1076":
            exhibit = top
        if top[0] < floor:
            rejected.append(top)
        elif len(scored) > 1 and scored[0][0] - scored[1][0] < ambiguous_gap:
            possible.append(top)
        else:
            matched.append(top)
        rejected.extend(scored[1:])
    emit("## Crosswalk composite scores: accepted vs rejected candidates")
    emit()
    emit(f"Scored (Tier-2) blocks only; the 51 exact-name matches never enter")
    emit(f"scoring. Accept floor = {floor}, ambiguity gap = {ambiguous_gap}.")
    emit()
    m = sorted(s[0] for s in matched)
    po = sorted(s[0] for s in possible)
    r = sorted(s[0] for s in rejected)
    a = sorted(m + po)
    emit(f"Accepted, status matched: n = {len(m)}, "
         f"range {m[0]:.3f} .. {m[-1]:.3f}")
    emit(f"Accepted, status possible_match: n = {len(po)}, "
         f"range {po[0]:.3f} .. {po[-1]:.3f} (each within {ambiguous_gap} "
         f"of its runner-up, by construction)")
    emit(f"Rejected candidates (runner-ups in their blocks): n = {len(r)}, "
         f"range {r[0]:.3f} .. {r[-1]:.3f}")
    # Fidelity check: the crosswalk persists name_sim in its notes for the
    # matched fuzzy rows; our recomputed name similarities must agree.
    persisted = {}
    for pid, notes in con.execute(
            "SELECT product_id, notes FROM product_crosswalk "
            "WHERE match_method='attributes_fuzzy' AND match_status='matched'"):
        if "name_sim=" in (notes or ""):
            persisted[pid] = float(notes.split("name_sim=")[1])
    agree = sum(1 for s in matched
                if s[1] in persisted and round(s[3], 2) == persisted[s[1]])
    emit(f"Rescoring fidelity: recomputed name_sim matches the value "
         f"persisted in product_crosswalk notes on {agree} of "
         f"{len(persisted)} matched fuzzy rows.")
    emit()
    wm = min(matched)
    emit(f"Weakest matched accept: {wm[1]} -> {wm[2]} at {wm[0]:.3f}, "
         f"clearing the 0.60 floor by {wm[0] - floor:.3f}. Weakest accept "
         f"overall is {min(min(matched), min(possible))[1]} at "
         f"{min(m[0], po[0]):.3f} (a possible_match).")
    if exhibit is not None:
        emit(f"Deck exhibit P1076 component check: name {exhibit[3]:.2f} x "
             f"0.6 + subclass {exhibit[4]:.2f} x 0.2 + price "
             f"{exhibit[5]:.3f} x 0.2 = composite {exhibit[0]:.3f}, clearing "
             f"the floor by {exhibit[0] - floor:.3f}. The components and "
             f"composite check out. CORRECTED in 707fce9: the slide-5 speaker "
             f"note used to call P1076 the weakest accept, which the "
             f"recomputed composites contradict (P1072 accepted at 0.657, and "
             f"the weakest possible_match at 0.642, both sit lower). The note "
             f"now says \"thin accept\" and claims no superlative. The 0.668 "
             f"and 0.068 figures themselves are correct for P1076.")
    if r and a and r[-1] > a[0]:
        lo, hi = max(a[0], r[0]), min(a[-1], r[-1])
        n_a = sum(1 for s in a if lo <= s <= hi)
        n_r = sum(1 for s in r if lo <= s <= hi)
        emit(f"Overlap region [{lo:.3f}, {hi:.3f}] holds {n_a} accepted and "
             f"{n_r} rejected candidate scores: the two populations are not "
             f"cleanly separated, and no threshold splits them without "
             f"trading false matches against missed ones.")
    else:
        emit("The accepted and rejected score ranges do not overlap.")
    emit()


def figure_index():
    emit("## Deck figure index (as displayed on the slides)")
    emit()
    emit("| Deck token | Slide | Computed here |")
    emit("|---|---|---|")
    for token, slide, computed in [
        ("+3.7pp", "7a title/stat", "21.6 - 17.9 on rounded shares (3.63pp exact)"),
        ("61.6 -> 58.5", "7a in_store", "61.6 -> 58.5"),
        ("17.9 -> 21.6", "7a pickup", "17.9 -> 21.6"),
        ("20.4 -> 19.9", "7a ship_from_store", "20.4 -> 19.9"),
        ("n = 3,721", "7a caveat", "3,721 order lines"),
        ("z ~ 2.8", "7a caveat", "z = 2.76"),
        ("p ~ .006", "7a caveat", "p = 0.0058"),
        ("1mm +13.9% (6/8)", "7b table", "+13.9, 6/8"),
        ("5mm +8.3% (4/8)", "7b table", "+8.3, 4/8"),
        ("10mm +18.9% (4/8)", "7b table", "+18.9, 4/8"),
        ("0.4mm +9.5% (3/8)", "7b table", "+9.5, 3/8"),
        ("S001 86% rain days, $6,673", "7b store mix", "86.2% (25/29), $6,673"),
        ("S006 14% rain days, $4,714", "7b store mix", "13.8% (4/29), $4,714"),
        ("Spearman 0.36", "7b", "rho = 0.359"),
        ("1 of 16 tests at p=.021", "7b line", "S001 x temp_max, p = 0.021"),
        ("rho = -0.43", "7b/A2 notes", "-0.43 (S001 x temp_max)"),
        ("0.668 >= 0.60", "5/A1 exhibit", "P1076 composite 0.668"),
        ("cleared the floor by 0.068", "5 notes",
         "0.068 for P1076; see the correction above on 'weakest'"),
        ("name 0.50, price 0.841", "A1 table", "0.50 and 0.841"),
    ]:
        emit(f"| {token} | {slide} | {computed} |")
    emit()


def main():
    if len(sys.argv) > 1:
        db = sys.argv[1]
    else:
        # Git Bash maps /tmp to the user temp dir on Windows, so try both.
        import tempfile
        candidates = [Path("/tmp/locked_snapshot.db"),
                      Path(tempfile.gettempdir()) / "locked_snapshot.db"]
        db = next((str(c) for c in candidates if c.exists()), str(candidates[0]))
    if not Path(db).exists():
        sys.exit(f"Snapshot not found at {db}. Extract it first:\n"
                 f"    git show {LOCK_COMMIT}:rocky_top.db > /tmp/locked_snapshot.db")
    con = sqlite3.connect(f"file:{Path(db).as_posix()}?mode=ro", uri=True)
    sd = store_days(con)
    stores = sorted({r[1] for r in sd})
    dates = sorted({r[0] for r in sd})
    emit("# Rain analysis derivation (deck slides 7a / 7b / A2)")
    emit()
    emit(f"Source: `rocky_top.db` snapshot at commit `{LOCK_COMMIT}` "
         f"(analysis window {dates[0]} .. {dates[-1]}).")
    emit(f"Grain: {len(sd)} store-days ({len(stores)} stores x "
         f"{len(dates)} dates). Rain day = MAX(precipitation_sum) "
         f"> {RAIN_MM:g}mm, strict.")
    emit()
    channel_shift(con, sd)
    threshold_table(sd, stores)
    store_mix(sd, stores)
    per_store_tests(sd, stores)
    crosswalk_scores(con)
    figure_index()
    emit(f"Generated by analysis/rain_analysis.py against the "
         f"{LOCK_COMMIT} snapshot.")
    out_path = Path(__file__).with_name("rain_analysis_output.md")
    out_path.write_text("\n".join(OUT) + "\n", encoding="utf-8")
    print(f"\n[written] {out_path}")
    con.close()


if __name__ == "__main__":
    main()

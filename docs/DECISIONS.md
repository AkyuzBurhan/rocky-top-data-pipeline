# DECISIONS.md — Design Decisions, Incidents, and Limitations

Rocky Top Outfitters pipeline (BZAN 545 final project). Sections follow the
grading rubric. Each incident below states **verified facts only** (what
happened, where the evidence is, how the pipeline responded).

---

## 1. Ingestion & Automation

The daily transient `orders.csv` is downloaded by `src/capture.py`, preserved
unchanged as `data/raw/orders_YYYY-MM-DD.csv`, and every attempt is logged to
`data/ingestion_log.csv` (run_id, timestamp, source URL, expected vs found
date, status, row count, SHA-256 file hash, error message). A GitHub Actions
workflow (`.github/workflows/daily_capture.yml`) runs daily at 13:00 UTC in two
stages: capture + commit the raw file first, then rebuild the full pipeline and
commit the refreshed database and logs. Daily `Daily capture` / `Daily build`
commits are visible in git history (e.g. commits `4d410a0` / `93800ac` for
2026-08-07).

### How much of the log is scheduled, and how much is backfill

Worth stating plainly, because the log does not look like 33 daily runs and we
would rather say so than have someone notice. 28 of the 33 rows in
`data/ingestion_log.csv` share one `run_timestamp`, `2026-08-03T23:56:18Z`, and
all 28 record the old `tiny.utk.edu` URL. They are a single backfill executed
when we consolidated into this repository. Scheduled per-day capture **in this
repository** begins 2026-08-04 and accounts for the remaining five rows
(08-04, 08-05, 08-06, 08-07, 08-08), each recording the
`raw.githubusercontent.com` URL and each corroborated by a `github-actions[bot]`
commit at the same timestamp to the second.

The earlier days were captured daily in the predecessor repository
(`jdyess-cell/BZAN-545-Final-Project`) and carried over intact at the 08-03
consolidation, which is why the raw files exist for dates no scheduled run in
this repository covers. [UNVERIFIED: the predecessor's Actions run history
cannot be checked from this repository's contents.] What this repository can
show on its own is 32 preserved raw files, none overwritten, and five scheduled
runs.

One clarification, since the commit pattern invites the wrong reading: there is
no `Daily build` commit for 08-04 or 08-05, and that is not a failed build. The
workflow at the time (`f66da7c`, named `Daily orders capture`) had only a capture
stage. The build stage was added on 08-05 in commit `8c3ef8f`.

### Incident: source URL migration (2026-08-03 → 2026-08-04)

- The original source URL was `https://tiny.utk.edu/RToutfitters/daily/orders.csv`
  (`helpers/config.py` as of commit `1c87604`, 2026-08-03).
- Commit `5a2414f` ("github actions", 2026-08-03 22:21 ET) changed
  `ORDERS_URL` in `helpers/config.py` to
  `https://raw.githubusercontent.com/AdamSpannbauer/su26-bzan545-current-orders/refs/heads/master/orders.csv`.
- The switch is visible in `data/ingestion_log.csv`: all backfill rows
  (run_timestamp 2026-08-03T23:56:18Z) record the tiny.utk.edu URL; every live
  capture from 2026-08-04T15:26:39Z onward records the raw.githubusercontent.com
  URL.
- The comment in `helpers/config.py` states the tiny.utk.edu address is a short
  link that redirects to the GitHub raw URL, and the direct URL is used so it
  is reachable from GitHub Actions. [UNVERIFIED: the redirect itself cannot be
  confirmed from repo contents alone.]

### Incident: 2026-08-06 source outage (HTTP 404)

- `data/ingestion_log.csv` (run_id `9fc82e0a...`, run_timestamp
  2026-08-06T15:17:43Z) records `status=failed`, `rows_loaded=0`, no file hash,
  and the captured error string:
  `404 Client Error: Not Found for url: https://raw.githubusercontent.com/AdamSpannbauer/su26-bzan545-current-orders/refs/heads/master/orders.csv`.
- No `data/raw/orders_2026-08-06.csv` exists; the day is absent from
  `clean_orders` and `daily_sales` (29 distinct order dates over the
  2026-07-07..2026-08-07 window: 08-06 failed, 08-03 empty, and the 07-24 file
  contained only duplicate 07-23 data).
- Pipeline response: `src/capture.py` wraps the download in try/except, logs
  the failure honestly (`status=failed` + error message), and does not crash —
  the next day's capture (2026-08-07, run_id `826a4637...`) succeeded with 125
  rows.

### Why we decided this

The source returned 404. We log the run as failed with rows_loaded=0 and move on.

Retrying was the obvious alternative and we rejected it. A 404 means the file is not there. Retrying produces three identical failures and a longer log. Timeouts and connection resets look different in the response and would be worth handling on their own terms, but we have not seen one.

Backfilling from 08-05 was the tempting option and the worse one. It would have kept the revenue series unbroken, which is exactly the problem. Every downstream number would still reconcile, the dashboard would look healthy, and nobody would know 08-06 never arrived. A gap in the data is a fact and the analysis should see it.

The cost is that daily_sales has no row for 08-06 and any comparison spanning that date has to account for it. ingestion_log records the failure with a timestamp, so the gap is explainable rather than mysterious.

### Incident: 2026-08-07 column reorder in orders CSV

- `data/raw/orders_2026-08-07.csv` has a different column order
  (`order_date,order_id,new_product_id,store_id,sales_channel,loyalty_member,quantity,discount_pct,unit_price`)
  than every earlier file
  (`order_id,order_date,store_id,...,quantity,unit_price,discount_pct,...`).
- Ingestion is **header-based, not positional**: `helpers/io.py
  read_orders_csv()` uses `pandas.read_csv` (columns addressed by name), and
  `src/load_raw.py` maps each named column into the fixed `raw_orders` schema
  ("order does not matter for to_sql", `RAW_ORDERS_COLUMNS`).
- Result: the file loaded normally — `data/ingestion_log.csv` shows
  `status=success, rows_loaded=125`, and `data/data_quality_log.csv`
  (run_date 2026-08-07) shows zero NA counts and only the expected
  `schema_new_product_col` flag. No Limitations entry needed for this incident.

---

## 2. SQL Modeling & Loading

Schema: `sql/01_schema.sql` defines 10 tables in four layers — raw
(`raw_orders`, all TEXT, both product columns kept), reference (`stores`,
`products`, `new_products`), team-created (`ingestion_log`,
`product_crosswalk`, `weather_daily`, `rejected_rows`), and clean/analytics
(`clean_orders` with a natural-key UNIQUE constraint, `daily_sales` with a
4-column primary key). `src/init_db.py` applies it idempotently
(`CREATE TABLE IF NOT EXISTS`); `src/load_raw.py` and `src/transform.py`
load/rebuild the tables.

### Runnable proof the required tables exist

`src/verify_tables.py` (run 2026-08-08, actual output):

```
OK      raw_orders           4027 rows
OK      stores                  8 rows
OK      products               80 rows
OK      new_products           80 rows
OK      ingestion_log          33 rows
OK      product_crosswalk      80 rows
OK      weather_daily         264 rows
OK      rejected_rows         144 rows
OK      clean_orders         3883 rows
OK      daily_sales          1414 rows
PASS: all 10 required tables exist in rocky_top.db
```

Note the `ingestion_log` **table** is a mirror, not the source of truth. The log is
written to `data/ingestion_log.csv` (33 rows) by `helpers/logs.py`, and
`src/load_raw.py` (`_sync_ingestion_log_table`) refreshes the SQLite table from that
CSV on every run — which is why both show 33 rows.

### SQLite vs UTK MySQL trade-off

Facts as implemented:

- The pipeline runs entirely against local SQLite (`rocky_top.db`), because
  GitHub Actions cannot reach the UTK MySQL server (VPN-only) — documented in
  `docs/PROJECT_GUIDE.md` §1 and `helpers/db.py`.
- `src/extract_reference.py` (VPN, manual) writes reference tables to CSV +
  team MySQL DB + SQLite. A `publish_to_utk.py` step to push **final** tables
  to the team DB is listed as "still to add" in `docs/PROJECT_GUIDE.md` §6 and
  does not exist in the repo.
- Consequences of this design: the committed `rocky_top.db` is the single
  source of truth for analytics; the UTK team DB holds only reference tables
  and goes stale relative to SQLite until a manual publish exists; SQLite is a
  single-file, effectively single-writer database, so there is no multi-user
  concurrent access story.

---

## 3. Monitoring & Data Quality

Two append-only CSV logs (written by `helpers/logs.py`):

- `data/ingestion_log.csv` — file-level: one row per capture/backfill attempt
  with status vocabulary `success | stale | empty | missing | failed`
  (`helpers/config.py`).
- `data/data_quality_log.csv` — row/cell-level: one fixed-schema row per raw
  file (per-column NA counts, duplicates, negative quantity/price, bad
  discount, orphan store/product, and a `flags` string), computed by
  `helpers/dq.py` and written by `src/check_quality.py`. Both scripts are
  idempotent (a logged date/file is skipped on re-runs).

### Incident: 2026-07-24 stale source file

- `data/ingestion_log.csv` (run_id `7e5369c2...`): `source_date_expected=2026-07-24`,
  `source_date_found=2026-07-23`, `status=stale`, 140 rows. Its `file_hash`
  (`ebea0940...`) is byte-identical to the 2026-07-23 row's hash — the source
  re-published the previous day's file unchanged.
- `data/data_quality_log.csv` row for `orders_2026-07-24.csv` carries the flag
  `stale(expected=2026-07-24,found=2026-07-23)`.
- Pipeline response: the file was still preserved
  (`data/raw/orders_2026-07-24.csv`) and loaded into `raw_orders`; during
  cleaning, `src/transform.py` de-duplicates on the natural key
  (order_id, order_date, store_id, product_key), so the 140 duplicate rows were
  quarantined into `rejected_rows` (reason `duplicate_natural_key`; 144 rows
  total there = 140 stale + 4 duplicates from 2026-07-16). No data was
  silently deleted, and 2026-07-24 has no real sales data.

### Why we decided this

The 07-24 file contained 140 rows, all of them 07-23 orders already loaded the day before. All 140 went to rejected_rows. None reached clean_orders.

The check caught it on arrival. src/capture.py compares the file's internal order date against the expected date and returns status=stale when they disagree; helpers/dq.py writes stale(expected=2026-07-24,found=2026-07-23) to the quality log. The run is recorded in ingestion_log.csv as stale, 140 rows.

Deduplicating instead would have answered the wrong question. It assumes a legitimate delivery that happens to overlap. This was yesterday's file republished under today's name, and the useful signal is that the source failed to update. Absorbing the duplicates quietly would have buried that. Letting the UNIQUE constraint on clean_orders reject them downstream works mechanically and fails as a record: the rows vanish with no explanation and the incident becomes a count discrepancy somebody has to reverse-engineer later.

The check is a date comparison, so a file republished with the date corrected but the rows unchanged would pass it. We store a SHA-256 of every file (helpers/io.py:29, written at src/load_raw.py:86) but nothing compares one day's hash against the previous day's. That second signal is in the log and goes unused.

### Incident: 2026-08-03 empty file

- `data/raw/orders_2026-08-03.csv` contains a header row and zero data rows.
- `data/ingestion_log.csv` (run_id `3b55269f...`): `status=empty`,
  `rows_loaded=0`, `source_date_found` blank. `data/data_quality_log.csv`
  flags the file `empty`.
- Pipeline response: `src/capture.py classify_file()` returns `empty` for a
  0-row file; `src/load_raw.py` logs it and loads no rows ("empty, logged, no
  rows to load"). The date is simply absent from `clean_orders`/`daily_sales`.

### Why we decided this

orders_2026-08-03.csv arrived with headers and no rows. The loader records status=empty and continues. Not a failure, not a success.

Empty and failed describe different upstream conditions. Failed means we could not reach the source. Empty means the source answered and had nothing to give. One is infrastructure, the other is either a real zero-sales day or a vendor-side problem. Collapsing them into one status throws away the distinction at the moment you need it.

We also rejected skipping the file silently, which would have left no trace that 08-03 was attempted at all. The file sits in data/raw/ with the other 31, so the empty file is itself the evidence.

What we cannot do from inside the pipeline is tell an empty file apart from a genuine zero-sales day. Both produce status=empty and no rows. Separating them needs a signal from the source that we do not have.

### Incident: 2026-08-05 prices arriving as "$157.12" strings

- Every one of the 155 data rows in `data/raw/orders_2026-08-05.csv` has a
  `$`-prefixed `unit_price` (e.g. `$72.70`). No other raw file contains `$`.
- **The DQ checks did not flag it**: the `data/data_quality_log.csv` row for
  `orders_2026-08-05.csv` shows `na_unit_price=0` and only the routine
  `schema_new_product_col` flag — `helpers/dq.py` reads values as strings, so
  `"$72.70"` is neither NA nor negative, and no non-numeric check exists.
- **`src/transform.py` does not handle it**: `_to_float()` uses
  `pd.to_numeric(errors="coerce")`, which turns every `$` value into NaN.
  Before the fix, all 155 `clean_orders` rows for 2026-08-05 had
  `unit_price = NULL` and `line_revenue = NULL`, and every `daily_sales` row
  for that date reported `net_revenue = 0.0` while `units_sold` stayed
  positive. The day's revenue was silently lost. Fixed in commit `3676313`;
  see Limitation 1.
- **Recovered:** $56,970.09 net (155 rows). We first computed this by hand
  from `data/raw/orders_2026-08-05.csv`, stripping the `$` and summing
  `unit_price * quantity`. The pipeline now produces the same figure on its
  own. Gross equivalent $61,474.35. The day was recoverable in about fifteen
  minutes because the bronze layer preserved the original bytes. See
  "Revenue, 2026-07-07 through 2026-08-07" at the end of this document for
  the corrected totals.

---

## 4. Product ER & Migration

### Incident: 2026-07-28 product-system migration (P#### → NP####)

- Files through `data/raw/orders_2026-07-27.csv` use column `product_id` with
  legacy IDs (`P####`). From `data/raw/orders_2026-07-28.csv` onward the
  column is `new_product_id` with `NP####` IDs.
- Every affected file is flagged `schema_new_product_col` in
  `data/data_quality_log.csv` (rows for 2026-07-28 through 2026-08-07).
- Pipeline response: `raw_orders` keeps both columns plus a
  `product_id_source` flag (`sql/01_schema.sql`); `src/transform.py` resolves
  each row's product **by value and flag, not by header** (new-system if the
  flag says `new_system`, the `new_product_id` column was used, or the value
  starts with `NP`), and maps legacy IDs to new IDs via the crosswalk.
  `helpers/io.py detect_product_column()` documents that from 2026-07-31 a
  header can say `product_id` while holding NP values
  ([UNVERIFIED in raw data: no committed raw file shows a mislabeled header +
  `product_id_source` column; the 2026-07-31..08-07 files all use the
  `new_product_id` header, and no DQ row sets `has_source_flag=1`]).

### Why we decided this

We scored each old product against candidates on name, subclass, and price, weighted 0.6 / 0.2 / 0.2, and accepted a match at 0.60 or above. Name carries the most weight because it is the field that changed. Launch date, margin, and department came through the migration untouched, so those three are the block key that narrows the candidate set, and name is what actually distinguishes one candidate from another once you are inside a block. Prices moved on plenty of products that are otherwise the same item, so price votes but does not decide.

The 0.60 cut is a judgment call and we want to be clear about that. Matched and rejected scores are not cleanly separated; the recomputed composites overlap between 0.642 and 0.939 (`analysis/rain_analysis_output.md`), so no threshold splits them without trading false matches against missed ones. We set the cut where a reviewer could still work through what fell near it. The second threshold, 0.85 on name alone, does a different job. It does not decide matches. It sorts unambiguous accepted matches into confident and needs-a-look, which produced 10 of the 18 review rows. The ambiguity rule contributes 4 more: when the top two candidates in a block score within 0.05 of each other, the row is accepted as `possible_match` and queued regardless of name score. The other 4 are products with no candidate at all.

### Entity-resolution method and results (verified against `data/reference/product_crosswalk.csv` and `src/crosswalk.py`)

- Catalogs: 80 legacy products (`data/reference/products.csv`), 80 new
  products (`data/reference/new_products.csv`).
- Match methods: **51 exact_name, 25 attributes_fuzzy, 4 none**.
  Match statuses: **72 matched, 4 possible_match, 4 unresolved**.
- Scoring (`src/crosswalk.py`): within a candidate block keyed on
  (`launch_date`, `gross_margin`, `department`), combined score =
  `0.6 * name_similarity + 0.2 * subclass_similarity + 0.2 * price_closeness`
  (`W_NAME, W_SUBCLASS, W_PRICE`), with `MIN_SCORE = 0.60` (below it nothing
  is claimed → unresolved) and `AMBIGUOUS_GAP = 0.05` (top-2 candidates closer
  than this → `possible_match`).
- The ambiguity gap flagged **all four planted decoy pairs**: `new_products`
  contains literal "… Alt" twins (NP5077–NP5080 mirror NP5073–NP5076), and
  P1077–P1080 are exactly the four `possible_match` rows in
  `data/reference/product_crosswalk.csv`, each noting its two close candidates
  (for P1078 the chosen candidate is the "Alt" item, NP5078).
- The 4 unresolved legacy products (P1069, P1071, P1073, P1075) each have the
  note `no candidate sharing launch_date+margin+department` — no new-catalog
  row shares their block key (discontinued items; their sales are recovered in
  `daily_sales` via `category_source = legacy_recovered`).
- Integrity check: `_validate()` in `src/crosswalk.py` verifies no new product
  is assigned to two legacy products — the run prints
  `integrity: 76/76 new ids unique -> OK (1:1)` — but this result is **printed
  to stdout only and never persisted** to any table or log. See Limitations.
- 18 rows carry `needs_review = 1` (10 matched-medium, 4 possible_match,
  4 unresolved) in `data/reference/product_crosswalk.csv`.

### Why we decided this

We checked the mapping against brand, which is not in the scoring model or the block key, so it never saw the field it is validating. Brand labels are not identical across systems. Three were relabeled in the migration, so a literal string comparison fails on 28 of 76 pairs. What holds is the mapping: 8 legacy brands map to 8 new labels, one to one, with no product crossing brands. A scoring model that had used brand would just be agreeing with itself here.

Ambiguity we handled by keeping it visible rather than resolving it. 72 products matched outright, 4 more mapped to a new ID but stayed marked `possible_match`, and 4 old products came out `unresolved` with no candidate sharing launch date, margin, and department. All four planted "Alt" decoys landed in `possible_match`, which is the behavior we wanted. They score high enough to be worth a look and not high enough to accept quietly. Four new-system IDs went unassigned, and those are the losing halves of the decoy pairs rather than new products. Orders against unresolved products keep their revenue through a `legacy_recovered` path, so an unmatched product costs us a product-level breakout and not a line in the revenue total.

---

## 5. Business Analysis

Facts about what exists:

- Business question (README.md): which stores and product categories are most
  weather-sensitive, and what inventory/promotion recommendations follow.
- The analytics-ready table `daily_sales` exists in `rocky_top.db` at grain
  `order_date × store_id × category × category_source`, with `units_sold`,
  `net_revenue`, `gross_revenue`, `discount_given`, and four weather columns
  joined from `weather_daily`. Every row has weather. The frozen
  2026-07-07..2026-08-07 analysis window covers 1,367 of those rows; the live
  table grows daily as the cron runs. The build prints grain-uniqueness and
  revenue-reconciliation checks (`src/transform.py build_daily_sales`).
- Weather data: Open-Meteo archive API, cached per store as JSON under
  `data/weather_cache/` (8 files, one per store), loaded to `weather_daily`
  by `src/weather.py`. The table holds one row per store per calendar date
  in the range, not per order date: 8 stores × 33 calendar dates = 264 rows.
  The three calendar dates with no orders are 2026-07-24 (stale republish),
  2026-08-03 (empty file), and 2026-08-06 (404), which is why 30 order dates
  sit inside a 33-day range. The console message prints the order-date count,
  so `8 stores x 30 dates` and 264 rows are consistent.
- **The business-facing artifact is `dashboard/app.py`,** a 598-line Streamlit
  board added in commit `2f4aef6`. It shows KPI tiles with sparklines, revenue
  by store and by category, weather-sensitivity correlations at the store-day
  grain, a warning when the rain-threshold result is sensitive to where the
  threshold is drawn, and an inventory and promotion playbook tied to the
  channel-shift finding. Run it with
  `uv run streamlit run dashboard/app.py`.

### Why we decided this

Three decisions sit behind this section: the window, what we claim about revenue, and what we claim about channel.

The window is frozen at 2026-07-07 through 2026-08-07. The pipeline runs on a daily cron, so the database grows every morning. An open window would mean every figure in the deck was stale by the time we presented and anyone rerunning our code would get different numbers than the slides. Freezing costs the most recent days and buys reproducibility. The live dashboard reads the full table and is ahead of the deck by design.

We do not claim rain increases revenue. At a 1mm threshold, mean store-day net revenue ran 10% higher on rainy days, with 6 of 8 stores agreeing. At 10mm the mean gap widened to 18% (the deck's 18.9% is the same comparison on medians), but agreement, counted on per-store median lifts as on slide 7b, fell to 4 of 8 stores, a coin flip. The point estimate moved with the cutoff and the cross-store consistency fell apart with it. We dropped the claim rather than report the threshold that flattered it. dashboard/app.py:516-525 computes both thresholds and renders the warning, so the fragility is visible on the board instead of buried here.

The board and the slides will not print the same numbers, and that is a definition difference rather than a disagreement. The board reads the live table and uses `precipitation_sum >= 1.0mm` with means; slides 7a and 7b use strict `> 1.0mm` with medians over the window frozen at 07-07 to 08-07. Three store-days sit at exactly 1.0mm (S004 07-09, S008 07-20, S005 08-05), so the operator alone moves the rain set. Side by side:

| Figure | Slides (locked, strict `>`, medians) | Board (live, `>=`, means) |
|---|---|---|
| Pickup share shift | 17.9 to 21.6, +3.7pp | 17.8 to 21.6, +3.8pp |
| Revenue lift at 1mm | +13.9%, 6 of 8 stores | +8.2%, 6 of 8 stores |
| Revenue lift at 10mm | +18.9%, 4 of 8 stores | +16.6%, 3 of 8 stores |

The pattern is the argument. The finding we report survives both definitions and both windows almost unchanged. The finding we killed moves by 5 to 6 points and loses a store of agreement depending on which definition you pick, which is the same instability that got it killed. The board now carries a note saying which definition it uses and why it differs, so anyone comparing the two screens gets the answer without asking.

We do claim rain shifts channel mix. Figures are computed on the analysis window frozen at commit `82d221e`, with rain defined as `precipitation_sum > 1.0mm` at store-day grain, matching the deck. Across 3,721 order lines, 1,568 on rainy store-days and 2,153 on dry, pickup share rises from 17.9% to 21.6%, a shift of +3.7 points (z ≈ 2.8, p ≈ .006). In-store falls 3.1 points, ship-from-store 0.5. The derivation is committed at `analysis/rain_analysis_output.md`. The direction holds at every cutoff tested from 0.4 to 10mm; significance does not survive past 5mm (p = .10 at 5mm, p = .46 at 10mm), as the rainy line count thins. Customers change how they buy, not whether they buy.

Sample size is the limit worth stating. 1,367 daily_sales rows look like a lot, but weather varies by store and date, not by category, so 232 independent store-day observations sit behind every weather result here. Eight stores, 29 dates. One unusual week is a meaningful fraction of that.

One reconciliation note. The dashboard reports $1,373.7K because it filters to the six named categories. Three rows carrying $930.45 sit under UNKNOWN, all tracing to product key NP9999, which appears in four order lines in orders_2026-07-30.csv and in no other file. NP9999 is in neither products nor new_products, so it has no crosswalk row. This is a referential integrity gap, not an entity-resolution failure: the four unresolved products in §4 are in the crosswalk with match_status = 'unresolved'. The pipeline kept the revenue and labelled the category UNKNOWN rather than dropping the rows. The ingestion check fired: the `data_quality_log.csv` row for `orders_2026-07-30.csv` (run 2026-08-04) records `orphan_product=4` and carries the `orphans` flag, and those four lines are exactly the NP9999 lines. Nobody acted on the flag. We rediscovered the gap by tracing the difference between the dashboard total and the reconciliation figure. The detection worked; the follow-through did not, and that is the part of the monitoring loop we would fix first.

---

## 6. Limitations & Technical Debt

1. **Resolved: currency-formatted prices were dropped without warning.**

   On 2026-08-05 the source file delivered `unit_price` as `$157.12` instead of
   `157.12`. `helpers/dq.py` had no check for non-numeric values, so the file
   passed all three quality gates, and `src/transform.py` coerced the strings to
   NaN. The result was 155 rows in `clean_orders` with NULL `unit_price` and
   `line_revenue`, and `daily_sales` reporting $0.00 net revenue for the whole
   day. Nothing in the pipeline flagged it. We found it by auditing the revenue
   series by hand, not through any automated signal.

   Commit `3676313` fixed both halves. `_clean_numeric_str()` in
   `src/transform.py` strips `$` and `,` before coercion, and `_nonnumeric()` in
   `helpers/dq.py` counts values that are present but unparseable, emitting a
   `nonnumeric(unit_price=N)` flag. We tested the gate instead of trusting it:
   `deck/out/fixture/poison_fixture_log.txt` shows the flag firing on 5 injected
   currency strings and the parser recovering all 5. The day now reports
   $56,970.09 net.

   **The gap that remained, and how we closed it.** `src/check_quality.py` skips
   any file already recorded in the quality log. That is correct for a daily
   pipeline and wrong for a check added after the fact: the non-numeric gate had
   only ever fired on the synthetic fixture, never on real data. If an earlier
   file had carried the same formatting, this gate would not have told us.

   So we asked it. `src/verify_dq_history.py` re-runs the current gate over every
   file in `data/raw/` in memory and diffs each result against the row already in
   the log. Actual output:

   ```
   re-checked 32 file(s) in raw/ against the current gate
   KNOWN      orders_2026-08-05.csv
              gate now adds: nonnumeric(unit_price=155)
              documented in DECISIONS.md Limitation 1
   PASS: 1 known difference(s), no undocumented ones. The quality log was not modified.
   ```

   2026-08-05 is the only affected day, and the gate catches all 155 rows of it.
   No other historical file carries unparseable numerics.

   **What is still true.** The script writes nothing, on purpose. The 2026-08-05
   row in `data/data_quality_log.csv` records `na_unit_price=0` with no
   non-numeric flag, and that row is the evidence that no check fired at the time.
   Regenerating the log would replace the record of the miss with a clean row and
   erase the incident. So the gate is verified against history but the history
   itself is left as it happened, and `check_quality.py` still will not re-check a
   logged file on its own. A future check added after ingestion has the same blind
   spot until someone runs the verifier again.
2. **Crosswalk integrity check is not persisted.** `_validate()`
   (`src/crosswalk.py`) confirms 1:1 assignment (76/76 unique new IDs) but
   only prints to stdout; nothing writes it to a table, log, or file, so
   there is no durable evidence of the check passing for any given build.
3. **Two capture crons must be disabled after the course ends.**

   This repo carries one workflow, `.github/workflows/daily_capture.yml`, on a
   daily cron at 13:00 UTC. The predecessor repo,
   `jdyess-cell/BZAN-545-Final-Project`, carries its own `Collect Daily Orders`
   cron that was never disabled when we consolidated on 2026-08-03. It has been
   firing and failing daily since. Two repos, one workflow each, both on the
   shutdown list.

   [UNVERIFIED] The predecessor's run history cannot be checked from this repo's
   contents. This rests on the migration timeline in §1 and on `README.md`.
4. **SQLite is single-user and the UTK team DB goes stale.** No
   `publish_to_utk.py` exists yet, so final tables live only in the committed
   `rocky_top.db`; the team MySQL DB holds only reference tables. Multi-user
   SQL access to the finished analytics tables is therefore limited to
   whoever has the repo file.
5. **`status=missing` is defined but never produced.** `helpers/config.py`
   defines `STATUS_MISSING` ("no file for the expected date"), but no code
   path emits it — a day with no capture attempt leaves no log row at all
   (there is no row for a date unless capture/backfill ran).
6. **Weather archive lag.** `src/weather.py` documents that the Open-Meteo
   ERA5 archive lags by a few days, so the most recent dates may join as NULL
   (currently every `daily_sales` row has weather).
7. **Header-mislabel path is untested by data.** The
   `header_mislabeled_product` flag (`helpers/dq.py`) and the
   `product_id_source` logic exist in code, but no committed raw file
   exercises them (no DQ row has `has_source_flag=1`).
8. **Weather raw is not preserved.**

   Raw-first preservation is a property of the orders feed, not of the pipeline.
   The weather source is the exception, and we should not claim otherwise.

   `_purge_stale_cache()` (`src/weather.py:35-42`) unlinks every prior cache file
   for a store whenever the date range changes. Because the cache key *is* the
   date range (`{store_id}_{start}_{end}.json`), and the range is derived from
   the order dates in `clean_orders`, every new order date changes the key. Each
   run therefore deletes the previous pull and refetches the full history. Unlike
   `data/raw/`, where each day's file is kept forever, the weather cache holds
   exactly one snapshot per store: the most recent one. Prior responses are gone,
   not archived.

   The deletions are visible in git. Commit `b191765` ("Daily build: 2026-08-08")
   removed all eight `data/weather_cache/*_2026-07-07_2026-08-07.json` files and
   added the `*_2026-08-08.json` replacements; `93800ac` did the same from
   `08-05` to `08-07`. Both are bot commits from the daily Action.

   This matters because Open-Meteo revises its archive. Comparing the cache at
   the locked snapshot `82d221e` against the current files, over the 256
   store-days the two have in common:

   - 5 store-days had `precipitation_sum` revised.
   - 2 of those crossed the deck's rain threshold (store-day grain, strictly
     `> 1.0mm`) and flipped classification:
     2026-08-07 S007, 2.3mm to 0.9mm, rain to dry; and
     2026-08-07 S008, 0.4mm to 3.7mm, dry to rain.

   All five revisions fall on 2026-08-07, the newest date at lock time, which is
   the behaviour you would expect from a preliminary ERA5 value being settled
   later. The consequence is that a rain-day figure computed today will not
   always match one computed from the same code last week, and we cannot
   reconstruct the earlier answer, because the inputs that produced it were
   deleted rather than kept.

   `analysis/rain_analysis.py:5-8` already records the symptom, noting that
   S007's rain-day share moved from 41.4% (12/29) at lock to 37.9% (11/29) on
   live data. It attributes this to Open-Meteo revising history, which is the
   upstream cause. The local cause is this limitation: the pipeline discards its
   own prior pull, so a revision upstream becomes unrecoverable here. The deck is
   reproducible only because it is pinned to the `82d221e` database snapshot, not
   because the weather inputs were preserved.

   **Fixed going forward, not retroactively.** The deletion loop is gone from
   `src/weather.py`; `_fetch_store` now writes the new cache file and leaves the
   old ones alone, so pulls accumulate the way `data/raw/` accumulates order
   files. The cost is disk, roughly 8 small JSON files per run.

   What that does not do is bring anything back. The five revisions measured
   above happened while the purge was live, so the pre-revision responses were
   already deleted; they survive only inside committed `rocky_top.db` snapshots,
   which is luck rather than design. Preservation starts from this commit. The
   deck remains reproducible because it is pinned to `82d221e`, not because its
   weather inputs were kept.
9. **The stored file hash is not portable across machines.**

   `helpers/io.file_hash()` (`helpers/io.py:29`) hashes the bytes of the file as
   it sits in the working tree. Git rewrites line endings on checkout when
   `core.autocrlf` is on, so the same committed file hashes differently on a
   Windows clone than on a Linux one. Three of our 32 raw files (2026-07-07,
   07-08, 07-09) hash differently on disk today than the value recorded in
   `data/ingestion_log.csv`, because those three rows were written from a
   checkout with different line-ending settings than the other 29. No data
   changed; the hash function saw different bytes.

   This matters for one specific reason. Section 3 notes that we store a hash of
   every file but never compare one day's against the previous day's, and calls
   that the second stale-file signal we are not using. That comparison would only
   be trustworthy within a single machine. Run across machines, or in Actions
   against rows written locally, it would report differences that are line-ending
   artefacts rather than republished content.

   Not fixed. The fix is to normalize line endings before hashing, or to hash the
   git blob rather than the working-tree file. The 2026-07-24 stale detection is
   unaffected: it compares a hash to the previous day's, and both rows were
   written in the same backfill run on the same machine.

## AI-Use Disclosure

All AI use below is for the final project. **No AI assistance was used on any
quiz or assessment**, per course policy.

### Tools and what they were used for

| Tool | Used for |
|---|---|
| Claude (chat) | Repository audit, verification of revenue and crosswalk figures, project planning, drafting |
| Claude Code | Repo sweep against the rubric, factual sections of this document, `src/verify_tables.py`, `docs/CONTEXT.md`, `audit_gaps.md` |
| Claude (Burhan) | `dashboard/app.py`, the Streamlit weather-sensitivity dashboard |
| [Jack: fill in] | [Jack: fill in] |
| [James: fill in] | [James: fill in] |

### What was AI-generated

- `src/verify_tables.py` was written by Claude Code from a specification we wrote,
  then reviewed line by line before committing.
- The factual sections of this document (what happened, evidence paths, how the
  pipeline responded) were drafted by Claude Code from repository contents. The
  "Why we decided this" sections are the team's own writing, not model output. Any
  section still blank at submission was not finished in time. We left those empty
  rather than have a model fill them in.
- `audit_gaps.md` is an AI-generated audit against the submission checklist.
- `dashboard/app.py` was built with AI assistance and reviewed before merging.

### What was not

- The pipeline itself: `src/capture.py`, `src/load_raw.py`, `src/transform.py`,
  `src/crosswalk.py`, `src/weather.py`, `helpers/`, and `sql/01_schema.sql` were
  written by the team over the course of the project.
- All design decisions: SQLite over the UT MySQL server, the entity-resolution
  scoring weights and thresholds, the department-level category taxonomy, and the
  decision to document rather than resolve the four ambiguous product matches.

### How AI output was verified

Figures in this document were checked against database queries and source files
rather than accepted as written. This caught real errors. An early AI-assisted
summary described the entity-resolution score as `0.6 * name + 0.4 * price`;
reading `src/crosswalk.py` showed the actual weights are `0.6 * name +
0.2 * subclass + 0.2 * price`. The recovered 2026-08-05 revenue figure was also
computed incorrectly on the first attempt, by applying `discount_pct` to a
`unit_price` that already had the discount applied. Both were corrected before
being committed.

The pipeline was run from a clean clone to confirm the repository reproduces
independently of any AI-assisted work.



---

## Revenue, 2026-07-07 through 2026-08-07

The window is frozen so every figure in this document and in the presentation
is reproducible from the same data. The pipeline has kept running since, so
the live database and the dashboard are ahead of these numbers by design.

| Figure | Value | Source |
|---|---|---|
| Net revenue | $1,374,672.31 | `daily_sales`, reconciles to `clean_orders.line_revenue` |
| Gross revenue | $1,479,057.85 | `daily_sales`, before discounts |

Before commit `3676313` these read $1,317,702.22 and roughly $1,417,583. The
difference is the 2026-08-05 currency-string day described in Limitation 1.
That day's $56,970.09 used to be a figure we recovered by hand from the raw
file. The pipeline now produces it on its own, so no manual adjustment is left
in the arithmetic.

### Gross vs net in this dataset

`unit_price` in the source orders file is **already discounted**. Verified against
`data/reference/products.csv`: P1076 has `base_price` 686.08, and orders show
651.78 at 5% off, 583.17 at 15%, 548.86 at 20%, 617.47 at 10%. Each equals
`base_price * (1 - discount_pct/100)`.

Net revenue is therefore `unit_price * quantity`, with no further discount applied.
`gross_revenue` is reverse-computed as `net / (1 - discount_pct/100)`, which is why
gross carries repeating decimals while net is clean to two decimal places.

Applying `discount_pct` to `unit_price` double-discounts and understates revenue.
Any analysis built directly on the raw orders files needs to account for this.

### What the reconciliation check does and does not prove

The pipeline reported `daily_sales` net revenue matching `clean_orders` line revenue
exactly. That proved `daily_sales` aggregated `clean_orders` faithfully. It could not
detect loss upstream of `clean_orders`: the 2026-08-05 nulls were present on both
sides of the comparison, so the check passed on data that was missing a full day.

Three separate checks passed on 2026-08-05: the missing-value check (a `$` is not a
null), the transform (silent coercion), and the reconciliation (same nulled data on
both sides). The gap was that none of them tested parseability.


---

## Limitation: declared constraints are absent from the live database

`sql/01_schema.sql` declares primary keys, unique constraints, not-nulls, and
foreign keys. `src/init_db.py` creates the tables correctly. But every table
written by pandas with `to_sql(..., if_exists="replace")` is **dropped and
recreated from the DataFrame schema**, discarding all constraints.

Verified by reading `sqlite_master` from `rocky_top.db`: **8 of the 10 tables are
a bare column list** with pandas default types. The two exceptions are the tables
that are never replaced — `raw_orders`, which is appended to
(`src/load_raw.py:106-108`), and `ingestion_log`, which is DELETE-then-appended
(`src/load_raw.py:50-52`). Both keep the DDL `init_db.py` created. Every table
below is one of the eight.

| Declared | Line | Enforced by |
|---|---|---|
| `PRIMARY KEY (order_date, store_id, category, category_source)` on `daily_sales` | 143 | Python grain check in `transform.py` |
| `UNIQUE (order_id, order_date, store_id, product_key)` on `clean_orders` | 121 | Natural-key dedup in `transform.py` |
| `PRIMARY KEY (product_id, new_product_id)` on `product_crosswalk` | 84 | `_validate()` 1:1 integrity check |
| `REFERENCES stores(store_id)` | 89, 110 | Orphan checks in `check_quality.py` |

**Effect.** Every correctness guarantee we designed into SQL is enforced in
application code instead. The pipeline produces correct results, but the database
would accept an incorrect write. The 140 duplicate rows from the 2026-07-24 stale
file were rejected by transform logic; the declared `UNIQUE` constraint would have
rejected them at insert, and did not exist to do so.

**Fix, not implemented.** Create each table from DDL and append, or `DELETE` and
append, rather than `if_exists="replace"`. This is the first thing we would fix
with more time.

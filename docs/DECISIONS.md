# DECISIONS.md — Design Decisions, Incidents, and Limitations

Rocky Top Outfitters pipeline (BZAN 545 final project). Sections follow the
grading rubric. Each incident below states **verified facts only** (what
happened, where the evidence is, how the pipeline responded). The
"Why we decided this" subsections are intentionally left blank for the team
to write by hand.

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

### Why we decided this

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

### Why we decided this

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

`src/verify_tables.py` (run 2026-08-07, actual output):

```
OK      raw_orders           3865 rows
OK      stores                  8 rows
OK      products               80 rows
OK      new_products           80 rows
OK      ingestion_log           0 rows
OK      product_crosswalk      80 rows
OK      weather_daily         256 rows
OK      rejected_rows         144 rows
OK      clean_orders         3721 rows
OK      daily_sales          1367 rows
PASS: all 10 required tables exist in rocky_top.db
```

Note the `ingestion_log` **table** has 0 rows — the ingestion log is populated
only as `data/ingestion_log.csv` (33 rows); no code inserts into the SQLite
table. See Limitations.

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

### Why we decided this

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

### Incident: 2026-08-03 empty file

- `data/raw/orders_2026-08-03.csv` contains a header row and zero data rows.
- `data/ingestion_log.csv` (run_id `3b55269f...`): `status=empty`,
  `rows_loaded=0`, `source_date_found` blank. `data/data_quality_log.csv`
  flags the file `empty`.
- Pipeline response: `src/capture.py classify_file()` returns `empty` for a
  0-row file; `src/load_raw.py` logs it and loads no rows ("empty, logged, no
  rows to load"). The date is simply absent from `clean_orders`/`daily_sales`.

### Why we decided this

### Incident: 2026-08-05 prices arriving as "$157.12" strings

- Every one of the 155 data rows in `data/raw/orders_2026-08-05.csv` has a
  `$`-prefixed `unit_price` (e.g. `$72.70`). No other raw file contains `$`.
- **The DQ checks did not flag it**: the `data/data_quality_log.csv` row for
  `orders_2026-08-05.csv` shows `na_unit_price=0` and only the routine
  `schema_new_product_col` flag — `helpers/dq.py` reads values as strings, so
  `"$72.70"` is neither NA nor negative, and no non-numeric check exists.
- **`src/transform.py` does not handle it**: `_to_float()` uses
  `pd.to_numeric(errors="coerce")`, which turns every `$` value into NaN.
  Verified in `rocky_top.db`: all 155 `clean_orders` rows for 2026-08-05 have
  `unit_price = NULL` and `line_revenue = NULL`, and every `daily_sales` row
  for 2026-08-05 reports `net_revenue = 0.0` while `units_sold` is positive.
  The day's revenue is silently lost. Recorded in Limitations below.
- **Recovered from raw:** $56,970.09 net (155 rows), computed from
  `data/raw/orders_2026-08-05.csv` by stripping the `$` and summing
  `unit_price * quantity`. Gross equivalent $61,474.35. The day was
  recoverable in about fifteen minutes because the bronze layer preserved
  the original bytes. See "Verified revenue figures" at the end of this
  document for the corrected totals.

### Why we decided this

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

---

## 5. Business Analysis

Facts about what exists:

- Business question (README.md): which stores and product categories are most
  weather-sensitive, and what inventory/promotion recommendations follow.
- The analytics-ready table `daily_sales` exists in `rocky_top.db`: 1,367 rows
  at grain `order_date × store_id × category × category_source`, with
  `units_sold`, `net_revenue`, `gross_revenue`, `discount_given`, and four
  weather columns joined from `weather_daily` (all 1,367 rows have weather).
  The build prints grain-uniqueness and revenue-reconciliation checks
  (`src/transform.py build_daily_sales`).
- Weather data: Open-Meteo archive API, cached per store as JSON under
  `data/weather_cache/` (8 files, one per store, covering
  2026-07-07..2026-08-07), loaded to `weather_daily` (256 rows = 8 stores ×
  32 dates) by `src/weather.py`.
- **No business-facing report, dashboard, or visuals exist in the repo.**
  `docs/PROJECT_GUIDE.md` §6 lists "The business dashboard" as still to add.
  See audit_gaps.md.

### Why we decided this

---

## 6. Limitations & Technical Debt

1. **`$`-formatted prices are not parsed (2026-08-05).** `helpers/dq.py` has
   no non-numeric check, so the file passed DQ clean; `src/transform.py`
   coerces `"$72.70"` to NaN. Result (verified in `rocky_top.db`): all 155
   `clean_orders` rows for 2026-08-05 have NULL `unit_price`/`line_revenue`,
   and `daily_sales` reports `net_revenue = 0.0` for the whole day. Revenue
   for 2026-08-05 is silently missing from every analysis built on
   `daily_sales`.
2. **Crosswalk integrity check is not persisted.** `_validate()`
   (`src/crosswalk.py`) confirms 1:1 assignment (76/76 unique new IDs) but
   only prints to stdout; nothing writes it to a table, log, or file, so
   there is no durable evidence of the check passing for any given build.
3. **The `ingestion_log` SQLite table is always empty (0 rows).** The schema
   defines it (`sql/01_schema.sql`) and `docs/PROJECT_GUIDE.md` lists it among
   the database tables, but all logging code (`helpers/logs.py`) writes only
   to `data/ingestion_log.csv`. Documentation and schema overstate what the
   database contains.
4. **The GitHub Action must be disabled after the course ends.**
   `.github/workflows/daily_capture.yml` runs on a daily cron with
   `contents: write` permission and pushes two commits per day. Once the
   course source feed is retired it will 404 daily (as on 2026-08-06) and
   keep committing log rows forever unless the workflow is disabled.
5. **SQLite is single-user and the UTK team DB goes stale.** No
   `publish_to_utk.py` exists yet, so final tables live only in the committed
   `rocky_top.db`; the team MySQL DB holds only reference tables. Multi-user
   SQL access to the finished analytics tables is therefore limited to
   whoever has the repo file.
6. **`status=missing` is defined but never produced.** `helpers/config.py`
   defines `STATUS_MISSING` ("no file for the expected date"), but no code
   path emits it — a day with no capture attempt leaves no log row at all
   (there is no row for a date unless capture/backfill ran).
7. **Weather archive lag.** `src/weather.py` documents that the Open-Meteo
   ERA5 archive lags by a few days, so the most recent dates may join as NULL
   (currently all 1,367 `daily_sales` rows do have weather).
8. **Header-mislabel path is untested by data.** The
   `header_mislabeled_product` flag (`helpers/dq.py`) and the
   `product_id_source` logic exist in code, but no committed raw file
   exercises them (no DQ row has `has_source_flag=1`).

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
  pipeline responded) were drafted by Claude Code from repository contents. Every
  "Why we decided this" section was written by the team.
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

## Verified revenue figures

Window 2026-07-07 through 2026-08-07. All figures net unless stated.

| Figure | Value | Source |
|---|---|---|
| Pipeline net revenue | $1,317,702.22 | `daily_sales`, reconciles to `clean_orders` |
| 2026-08-05 recovered net | $56,970.09 | `data/raw/orders_2026-08-05.csv`, 155 rows |
| **True net revenue** | **$1,374,672.31** | pipeline + recovered day |
| Pipeline gross revenue | ~$1,417,583 | `daily_sales.gross_revenue` |
| 2026-08-05 recovered gross | $61,474.35 | recovered, reverse-computed |
| **True gross revenue** | **~$1,479,057** | pipeline + recovered day |

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

The pipeline reports `daily_sales` net revenue matching `clean_orders` line revenue
exactly. That proves `daily_sales` aggregates `clean_orders` faithfully. It cannot
detect loss upstream of `clean_orders`: the 2026-08-05 nulls are present on both
sides of the comparison, so the check passes on data that is missing a full day.

Three separate checks passed on 2026-08-05: the missing-value check (a `$` is not a
null), the transform (silent coercion), and the reconciliation (same nulled data on
both sides). The gap is that none of them tested parseability.

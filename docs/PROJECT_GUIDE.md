# Rocky Top Outfitters Pipeline — Team Guide

This guide explains the project so **every team member can understand and run
it**. It covers: the big picture, how to run everything step by step, and then
every file and its important functions (what it is for, what it does, how to run
it, and how to see its result).

---

## 1. Big picture

We build a daily data pipeline that turns a changing `orders.csv` feed into
trusted analytics. The business question is:

> Which stores and product categories are most weather-sensitive, and what
> inventory/promotion recommendations follow?

### Three databases (know which is which)

| Database | What it is | Who reads/writes |
|----------|------------|------------------|
| **SQLite** (`rocky_top.db`, a local file) | Our **automation engine**. The whole pipeline runs here. No network needed. | Every script reads/writes it. |
| **UTK team MySQL** (`<netid>_bzan545`) | The "real" SQL home on the UTK server. We **publish** final tables here. | `extract_reference.py` (write), `publish_to_utk.py` (write, later step). Needs campus/VPN. |
| **Instructor MySQL DB** | Source of the reference tables (`stores`, `products`, `new_products`). | `extract_reference.py` (read). Needs campus/VPN. |

Because GitHub Actions can't reach the UTK network, the pipeline runs on
**SQLite**, and we sync to the UTK team DB manually when on VPN. The instructor
said SQLite is fine for automation.

### Two kinds of output (know where results live)

- **CSV files on disk** (open in Excel): `data/raw/*.csv`, `data/reference/*.csv`,
  `data/ingestion_log.csv`, `data/data_quality_log.csv`.
- **Tables inside `rocky_top.db`** (open with SQL / a SQLite viewer):
  `raw_orders`, `stores`, `products`, `new_products`, `clean_orders`,
  `product_crosswalk`, `weather_daily`, `rejected_rows`, `daily_sales`,
  `ingestion_log`.

Rule of thumb: **logs are CSV** (easy to eyeball), **modeled/analytics data is
in the database** (because this is a SQL project).

### The data flow

```
orders.csv (daily, transient)
      │  capture.py  (download + preserve + log)
      ▼
data/raw/orders_YYYY-MM-DD.csv
      │  load_raw.py     -> raw_orders (+ ingestion_log)
      │  check_quality.py-> data_quality_log.csv
      ▼
UTK reference (stores/products/new_products)
      │  extract_reference.py (VPN) -> data/reference/*.csv + team DB + SQLite
      │  reference.py               -> loads those CSVs into SQLite
      ▼
crosswalk.py  -> product_crosswalk   (legacy <-> new product matching)
transform.py  -> clean_orders        (typed, deduped, product resolved via crosswalk)
weather.py    -> weather_daily       (Open-Meteo, per store per date)
      ▼
transform.py  -> daily_sales         (analytics-ready: date x store x category x
                                      category_source; net/gross revenue + weather)
      ▼
dashboard / report
```

Tip: `run_pipeline.py` runs every SQLite step above in the correct order with a
single command — see below.

---

## 2. How to run the project (step by step)

### One-time setup

```bash
uv sync                                         # install dependencies into .venv
cp credentials.example.json credentials.json    # then edit it (see below)
```

`credentials.json` (git-ignored, never commit it) needs at least:

```json
{ "host": "mariadb-compx0.oit.utk.edu", "port": 3306,
  "username": "YOUR_NETID", "password": "YOUR_DB_PASSWORD" }
```

The team DB name is auto-derived from your `username` as `<username>_bzan545`,
so no NetID is stored in the repo and you don't have to add it. Add
`"team_db": "..."` to override it, or `"source_db": "..."` only if reading
reference from a separate instructor DB.

### Easiest: one command

```bash
uv run python -m src.run_pipeline            # rebuild everything, in the right order
uv run python -m src.run_pipeline --capture  # also download today's file first
uv run python -m src.run_pipeline --no-weather  # skip the network weather step
```

`run_pipeline` runs all the SQLite steps in the correct order (it handles the
"weather before daily_sales" ordering for you). Reference extraction still runs
separately because it needs the UTK VPN (see below).

### Full run, step by step (what run_pipeline does)

```bash
# 1) Get reference tables from UTK (ON CAMPUS / VPN, run occasionally)
uv run python -m src.extract_reference

# 2) Load reference CSVs into SQLite (no VPN needed)
uv run python -m src.reference

# 3) Capture today's orders file (daily; also runs in GitHub Actions)
uv run python -m src.capture

# 4) Load all raw files -> raw_orders (+ ingestion_log)
uv run python -m src.load_raw

# 5) Data-quality checks -> data_quality_log.csv
uv run python -m src.check_quality

# 6) Build the product crosswalk (legacy <-> new)
uv run python -m src.crosswalk

# 7) Weather (needs network) -> weather_daily
uv run python -m src.weather

# 8) Build clean_orders + daily_sales (run AFTER crosswalk and weather)
uv run python -m src.transform
```

Every command prints a one-line summary of what it did. You can run each step
on its own; they are **idempotent** (safe to re-run — they don't double-load).
Note: `transform` builds **both** `clean_orders` and `daily_sales`, so run it
after `crosswalk` (for product mapping) and after `weather` (so the weather join
has data).

### Rebuilding from scratch

Everything is rebuildable from `data/raw/` + `data/reference/`. To reset:

```bash
rm rocky_top.db data/ingestion_log.csv data/data_quality_log.csv
# then run steps 2 and 4-8 again
```

You do **not** need to delete tables by hand: `clean_orders`,
`product_crosswalk`, `weather_daily`, and `rejected_rows` are fully rebuilt
(replaced) each run.

### How to look inside the database

Any of these work:

```bash
# quick row counts / peek from the command line
uv run python -c "import pandas as pd, sqlalchemy; e=sqlalchemy.create_engine('sqlite:///rocky_top.db'); print(pd.read_sql('SELECT * FROM clean_orders LIMIT 5', e))"
```

or open `rocky_top.db` in a SQLite viewer (e.g. "DB Browser for SQLite", or the
data viewer in Positron/VS Code) and click through the tables.

---

## 3. The files

Layout:

```
helpers/   shared building blocks (imported by scripts)
src/       the pipeline steps you run
sql/       the database schema
data/      raw files, reference CSVs, logs, weather cache
docs/      this guide + decision/quality notes
```

### `sql/01_schema.sql`

- **Purpose:** defines every table in `rocky_top.db`.
- **What it does:** `CREATE TABLE IF NOT EXISTS` for all tables across four
  layers — raw (`raw_orders`), reference (`stores`, `products`,
  `new_products`), team-created (`ingestion_log`, `product_crosswalk`,
  `weather_daily`, `rejected_rows`), and clean/analytics (`clean_orders`,
  `daily_sales`).
- **How to run:** you don't run it directly; `init_db.py` runs it.
- **How to see the result:** after `init_db`, the 10 tables exist (empty).

---

### `helpers/config.py`

- **Purpose:** one place for all non-secret settings (paths, the orders URL,
  table/column names, status words like `success`/`stale`/`empty`).
- **What it does / how it works:** defines constants other files import, e.g.
  `RAW_DIR`, `SQLITE_PATH`, `ORDERS_URL`, `REFERENCE_TABLES`, `TEAM_DB_SUFFIX`.
  Paths are computed relative to the repo root so scripts work from anywhere.
- **How to see it:** it has no output; it's imported everywhere. If a path or
  URL is wrong, change it here once.

---

### `helpers/db.py`

- **Purpose:** create database connections ("engines").
- **How it works:** reads `credentials.json`, then builds SQLAlchemy engines.
- **Key functions:**
  - `get_sqlite_engine()` — connection to the local `rocky_top.db`. No network.
    This is what the pipeline uses.
  - `get_team_engine()` — connection to our UTK team DB (`<netid>_bzan545`).
  - `get_source_engine()` — connection to the reference source DB (instructor's
    if `source_db` is set, otherwise the team DB).
  - `create_mysql_utk_engine(...)` — the low-level UTK MySQL builder
    (generalized from the class helper).
- **How to see it:** no direct output. Test it with:
  `uv run python -c "from helpers import db, sqlalchemy; print(db.get_sqlite_engine())"`

---

### `helpers/io.py`

- **Purpose:** small file/reading helpers used across the pipeline.
- **Key functions:**
  - `file_hash(path)` — SHA-256 of a file's bytes; used to detect duplicate or
    unchanged daily files.
  - `expected_date_from_filename(name)` — pulls the date out of
    `orders_2026-08-03.csv` -> `"2026-08-03"` (also handles `orders_20260803.csv`).
  - `read_orders_csv(path)` — reads an orders CSV as **all text** (we don't
    trust types yet); an empty file returns 0 rows.
  - `detect_product_column(df)` — decides whether a file uses `product_id` or
    `new_product_id`, and whether the `product_id_source` flag is present. It
    does **not** trust the header alone.
  - `utc_now_iso()` — current UTC timestamp as text (for logs/tables).
- **How to see it:** used internally; no standalone output.

---

### `helpers/logs.py`

- **Purpose:** write the two CSV logs (append-only) and support idempotency.
- **Key functions:**
  - `append_ingestion_log(row)` — adds one row to `data/ingestion_log.csv`
    (file-level: status, rows, hash, freshness).
  - `append_dq_log(row)` — adds one row to `data/data_quality_log.csv`
    (row/cell-level: NA counts, duplicates, flags).
  - `already_logged_dates()` / `already_logged_files(path)` — used so re-runs
    don't log the same day/file twice.
- **How to see it:** open the two CSVs in `data/`.

---

### `helpers/dq.py`

- **Purpose:** compute the data-quality checks for one file.
- **Key function:** `run_quality_checks(path, expected_date, store_ids,
  product_ids)` — returns one dict (one row) with fixed columns: per-column NA
  counts, duplicate rows, duplicate `order_id`, negative quantity/price, bad
  discount, orphan store/product, and a `flags` string (e.g.
  `stale(...)`, `schema_new_product_col`, `duplicates`, `empty`,
  `ref_not_loaded`). Counts are raw numbers (not percentages).
- **How to see it:** the results end up in `data/data_quality_log.csv` (written
  by `check_quality.py`).

---

### `helpers/matching.py`

- **Purpose:** text normalization + fuzzy similarity for entity resolution
  (mirrors the class ER demo helpers).
- **Key functions:**
  - `normalize_text(value)` — lowercase, strip, replace punctuation with spaces,
    collapse spaces. `"SummitRunner Jacket 200"` -> `"summitrunner jacket 200"`.
  - `text_similarity(a, b, method="token_set_ratio")` — a 0..1 fuzzy score
    (uses `fuzzywuzzy`). Used to compare product names.
  - `token_set` / `overlap_count` — token helpers.
- **How to see it:** used inside `crosswalk.py`; no standalone output.

---

### `src/init_db.py`

- **Purpose:** create the SQLite database from the schema.
- **What it does:** runs `sql/01_schema.sql` against `rocky_top.db`.
- **How to run:** `uv run python -m src.init_db`
- **How to see the result:** it prints the 10 tables it created. (Other scripts
  call it automatically, so you rarely run it alone.)

---

### `src/capture.py`

- **Purpose:** download today's transient `orders.csv`, preserve it, and log the
  attempt. **This is the daily step** (and what GitHub Actions runs).
- **What it does / how it works:** GETs the orders URL, saves it to
  `data/raw/orders_YYYY-MM-DD.csv`, then classifies it (`success` / `stale` /
  `empty` / `failed`) and appends one row to `ingestion_log.csv`.
- **Key functions:**
  - `capture(expected_date=None)` — the whole download + log step.
  - `classify_file(path, expected_date)` — decides the status by reading the
    saved file (kept separate so it's testable without the network).
- **How to run:** `uv run python -m src.capture` (or `... 2026-08-03` for a date).
- **How to see the result:** a new file in `data/raw/` and a new row in
  `data/ingestion_log.csv`. The console prints e.g.
  `[capture] orders_2026-08-03.csv: status=empty rows=0`.

---

### `src/load_raw.py`

- **Purpose:** load every file in `data/raw/` into the `raw_orders` table, and
  log each file in `ingestion_log`.
- **What it does / how it works:** for each `orders_*.csv`, it maps whatever
  columns exist into the wide `raw_orders` schema (missing columns become NULL),
  and appends the rows unchanged. It is **idempotent by date**: a day already in
  `raw_orders` is skipped, so mixed file names (`orders_20260718.csv` vs
  `orders_2026-07-18.csv`) won't double-load.
- **Key functions:** `load_raw()`, `_loaded_dates(engine)` (which dates are
  already loaded).
- **How to run:** `uv run python -m src.load_raw`
- **How to see the result:** console prints `files loaded=…, skipped=…,
  raw_orders now has … rows`. Inspect the `raw_orders` table and
  `data/ingestion_log.csv`.

---

### `src/check_quality.py`

- **Purpose:** run the row/cell-level data-quality checks on every raw file and
  write `data_quality_log.csv`.
- **What it does:** for each new file, calls `dq.run_quality_checks(...)` and
  appends a row. If the reference tables are loaded, it also fills the orphan
  columns; otherwise rows are flagged `ref_not_loaded`.
- **How to run:** `uv run python -m src.check_quality`
- **How to see the result:** open `data/data_quality_log.csv` (one row per file;
  look at the `flags` column). Console prints a per-file summary.

---

### `src/extract_reference.py`

- **Purpose:** pull the reference tables (`stores`, `products`, `new_products`)
  out of UTK MySQL **in code** (no manual copy/paste). **Run on campus/VPN.**
- **What it does:** `SELECT * FROM <table>` from the source DB, then writes each
  result to (1) `data/reference/<table>.csv`, (2) our team DB, and (3) SQLite.
- **How to run:** `uv run python -m src.extract_reference`
- **How to see the result:** three CSVs appear in `data/reference/`; console
  prints `stores: 8 rows -> CSV + team DB + SQLite`, etc.

---

### `src/reference.py`

- **Purpose:** load the reference CSVs into SQLite (the network-free half, used
  by the automated pipeline).
- **Key function:** `load_reference_into_sqlite()` — reads
  `data/reference/{stores,products,new_products}.csv` and replaces those tables
  in SQLite.
- **How to run:** `uv run python -m src.reference`
- **How to see the result:** console prints `loaded stores: 8 rows into SQLite`,
  etc. The `stores`/`products`/`new_products` tables are now populated.

---

### `src/crosswalk.py`

- **Purpose:** reconcile legacy `products` with `new_products` across the
  product migration (entity resolution) -> `product_crosswalk`.
- **How it works (method):** builds the crosswalk from the two **reference**
  catalogs (not from orders). For each legacy product:
  1. **exact normalized name** -> `matched` / `high`.
  2. otherwise **block** on preserved attributes (`launch_date` + `margin` +
     mapped `department`), then **score** candidates by fuzzy name similarity
     (`product_name` vs `item_name`), token similarity (`subcategory` vs
     `class`), and price closeness (`base_price` vs `msrp`). If even the best
     candidate scores below `MIN_SCORE` (0.60), nothing is claimed -> `unresolved`.
  3. no candidate at all -> `unresolved`.
  It then flags anything that is **not** a high-confidence match with
  `needs_review = 1`, and prints an integrity check (no new product assigned to
  two legacy products).
- **Key functions:** `build_crosswalk(engine)`, `_score(legacy, new)`,
  `_price_closeness(...)`, `_validate(cw)`.
- **How to run:** `uv run python -m src.crosswalk`
- **How to see the result:** the `product_crosswalk` table and
  `data/reference/product_crosswalk.csv`. Console prints e.g.
  `status: {'matched': 72, 'unresolved': 4, 'possible_match': 4}` and how many
  rows `need human review`. Filter the CSV on `needs_review = 1` to review.

---

### `src/transform.py`

- **Purpose:** build the two modeled tables — `clean_orders` and `daily_sales`.
- **Key functions:**
  - `build_clean_orders(engine)` — turns `raw_orders` into cleaned rows. Resolves
    each order's product **by value/flag, not header** (new-system if
    `product_id_source == new_system`, or the value starts with `NP`, or the
    `new_product_id` column was used), maps legacy IDs to new IDs via the
    crosswalk, fixes types, computes `line_revenue = quantity * unit_price` (this
    is the **net** paid, since `unit_price` is already post-discount), maps
    loyalty `Y/N -> 1/0`, and drops bad-date/duplicate rows into `rejected_rows`
    (never silently deleted).
  - `build_daily_sales(engine)` — aggregates `clean_orders` to the analytics
    grain **order_date × store_id × category × category_source**. Category is the
    new-system **department** (via `product_key`); discontinued products are
    recovered from their legacy category (`category_source = legacy_recovered`)
    and the orphan `NP9999` becomes `UNKNOWN` (`category_source = unknown`).
    Reports `net_revenue`, `gross_revenue`, `discount_given`, joins `weather_daily`
    on `(date, store)`, and prints grain + revenue **reconciliation** checks.
  - `_record_rejected(...)` — writes dropped rows to `rejected_rows`.
- **How to run:** `uv run python -m src.transform` (run **after** `crosswalk` and
  `weather`). It builds both tables.
- **How to see the result:** console prints `clean_orders rebuilt: N rows ...`
  and `daily_sales rebuilt: N rows ... grain unique: True ... reconciliation ...
  MATCH`. Inspect the `clean_orders`, `daily_sales`, and `rejected_rows` tables.

---

### `src/weather.py`

- **Purpose:** fetch daily weather per store from Open-Meteo -> `weather_daily`.
- **How it works:** for each store's lat/long and the date range in
  `clean_orders`, calls the Open-Meteo archive API, **caches** the raw JSON under
  `data/weather_cache/`, and writes one row per store per date.
- **Key functions:** `fetch_weather(engine)`, `_fetch_store(...)` (uses the cache
  if present), `_purge_stale_cache(...)` (keeps only one cache file per store as
  the date range grows, so `data/weather_cache/` doesn't accumulate old files).
- **How to run:** `uv run python -m src.weather` (needs network).
- **How to see the result:** console prints
  `weather_daily rebuilt: N rows (8 stores x ~28 dates ...)`; one cached JSON per
  store appears in `data/weather_cache/`; inspect the `weather_daily` table.

---

### `src/run_pipeline.py`

- **Purpose:** the single command that (re)builds everything in the right order.
- **What it does / how it works:** only calls the existing step functions —
  `init_db -> reference -> load_raw -> check_quality -> crosswalk ->
  clean_orders -> weather -> daily_sales`. No business logic lives here, so it
  never duplicates what the individual scripts do. The weather step is wrapped so
  a network hiccup can't block the rest of the build.
- **How to run:** `uv run python -m src.run_pipeline`
  (`--capture` to download today's file first, `--no-weather` to skip weather).
- **How to see the result:** it runs each step (each prints its own summary) and
  ends with `[pipeline] done`. Afterwards every table in `rocky_top.db` is fresh.

---

### `.github/workflows/daily_capture.yml`

- **Purpose:** run the whole pipeline automatically every day on GitHub's
  servers (no one has to be at their computer).
- **What it does / how it works:** two stages. **Stage 1** captures today's
  `orders.csv` and commits it immediately (so the transient file is never lost).
  **Stage 2** runs `run_pipeline` and commits the refreshed database + logs. It
  fires on a daily cron and can also be run by hand from the **Actions** tab
  (`workflow_dispatch`). No secrets are needed — it uses SQLite + the committed
  reference CSVs + the public Open-Meteo API, never the UTK MySQL server.
- **Why daily runs matter:** each run stamps its own real timestamp in
  `ingestion_log` / `data_quality_log`, which is the evidence of genuine
  day-by-day monitoring (a one-time backfill would show identical timestamps).
- **Requirements:** in the repo, Settings → Actions → General → Workflow
  permissions = **Read and write**; and `data/reference/*.csv` must be committed.
- **How to see the result:** the **Actions** tab shows each run's logs; the repo
  gets a daily `Daily capture` + `Daily build` commit containing the new raw
  file, the refreshed `rocky_top.db`, and updated logs.

---

## 4. Data quirks this pipeline handles (good to know)

- **Product migration:** early files use `product_id` (`P####`); later files use
  `new_product_id` (`NP####`). We resolve products by value/flag, not header.
- **Stale file:** `orders_2026-07-24.csv` actually contains `2026-07-23` data
  (a copy of the 23rd). Flagged `stale`; its rows are de-duplicated out of
  `clean_orders`.
- **Empty file:** `orders_2026-08-03.csv` has a header and 0 rows -> `empty`.
- **Duplicates:** `2026-07-16` has 4 duplicate rows -> removed in `clean_orders`,
  kept in `rejected_rows`.
- **Orphan product:** `NP9999` appears in orders but is in no catalog; flagged in
  the data-quality log, and in `daily_sales` it is the only thing left as
  `category = UNKNOWN` (`category_source = unknown`).
- **Discontinued products:** legacy styles 268/270/272/274 have no new-catalog
  equivalent -> `unresolved` in the crosswalk. Their real sales are still
  categorized in `daily_sales` by recovering the department from their legacy
  category (`category_source = legacy_recovered`), so no revenue is lost.
- **Revenue is net-of-discount:** `unit_price` is already the post-discount price
  (verified: `unit_price = base_price * (1 - discount_pct/100)`). So `net_revenue`
  = `quantity * unit_price`, and `daily_sales` also reports `gross_revenue` (list
  price) and `discount_given` = gross − net.

---

## 5. Done since the first draft

- `daily_sales` analytics table + `build_daily_sales` (category resolution with
  `category_source`, net/gross revenue, weather join, reconciliation checks).
- `run_pipeline.py` — one command that runs every step in the right order.
- GitHub Actions **daily full pipeline** (`.github/workflows/daily_capture.yml`):
  capture + commit, then rebuild + commit db/logs, so monitoring logs get a real
  timestamp every day.
- Weather cache cleanup (one file per store).

## 6. Still to add (later steps)

- `publish_to_utk.py` — push final tables to the team DB (on VPN).
- `verify_tables.py` — a runnable "the SQL tables exist" demo.
- `manual_overrides.csv` support in the crosswalk (make human review decisions
  permanent) — optional.
- The business dashboard.

When those land, this guide will be updated.

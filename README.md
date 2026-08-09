# Rocky Top Outfitters — Data Pipeline

Daily data pipeline: ingest the transient `orders.csv` feed, preserve it raw,
clean it, reconcile the product-system migration, enrich with weather, monitor
pipeline health, and produce analytics for:

> Which stores and product categories are most weather-sensitive, and what
> inventory or promotion recommendations follow?

## Quick start

```bash
uv sync                                     # create .venv and install deps
uv run python -m src.run_pipeline           # build the database end to end
uv run python -m src.verify_tables          # confirm all 10 SQL tables exist
uv run streamlit run dashboard/app.py       # weather-sensitivity dashboard
```

**Use the `-m` module form.** Running `python src/run_pipeline.py` fails with
`ModuleNotFoundError: No module named 'src'`, because the scripts use
package-style imports.

The pipeline runs from a clean clone with no credentials and no network, because
reference CSVs and Open-Meteo responses are both committed.

## Credentials

`credentials.json` is **only** needed for `src/extract_reference.py`, which pulls
reference tables from the UT MySQL server and requires the UT VPN. Those tables
are already committed under `data/reference/`, so nothing in Quick start needs it.

```bash
cp credentials.example.json credentials.json   # only for VPN reference extraction
```

`credentials.json` is git-ignored. Never commit it.

## Layout

```
helpers/             shared package (config, db, io, dq, logs, matching)
src/                 pipeline scripts
sql/                 schema
dashboard/           Streamlit dashboard
deck/                presentation build + executed fixture artifacts
docs/                decisions, project guide, working context
data/raw/            preserved daily orders_YYYY-MM-DD.csv files
data/reference/      stores, products, new_products, product_crosswalk
data/weather_cache/  cached Open-Meteo responses, one JSON per store
rocky_top.db         SQLite database, rebuilt by run_pipeline
```

## Pipeline stages

`src/run_pipeline.py` runs these in dependency order. It calls the step functions
and holds no business logic of its own.

| Order | Script | Does |
|---|---|---|
| 1 | `src/init_db.py` | Create `rocky_top.db` from `sql/01_schema.sql`. Safe to re-run. |
| 2 | `src/reference.py` | Load committed reference CSVs into SQLite. Network-free. |
| 3 | `src/load_raw.py` | Load every file in `data/raw/` into `raw_orders`. Idempotent and column-order agnostic. |
| 4 | `src/check_quality.py` | Row and cell-level checks per file, writes `data/data_quality_log.csv`. |
| 5 | `src/crosswalk.py` | Build `product_crosswalk` by attribute blocking plus fuzzy scoring. |
| 6 | `src/transform.py` | Build `clean_orders`, resolving product IDs by value and flag rather than column header. |
| 7 | `src/weather.py` | Fetch and cache Open-Meteo daily weather, build `weather_daily`. |
| 8 | `src/transform.py` | Build `daily_sales` with grain and reconciliation checks. |

Run outside the pipeline:

| Script | Does |
|---|---|
| `src/capture.py` | Download today's orders file, preserve it raw, log the attempt. Needs no database, so it runs unattended in GitHub Actions. |
| `src/extract_reference.py` | Pull reference tables from UT MySQL. Manual, needs VPN. |
| `src/verify_tables.py` | Assert all 10 required tables exist. Exits nonzero if any are missing. |
| `src/verify_dq_history.py` | Re-run the current quality gate over every file in `data/raw/` and diff against the logged result. Writes nothing. Exits nonzero on an undocumented flag. |

`src/weather.py` requires network access. A clean clone reproduces offline from
the committed cache, but only while the order-date range still matches: cache
files are named `{store_id}_{start}_{end}.json`, and each daily run of the
pipeline writes a new file for the new range **without deleting the previous
one**. So in GitHub Actions, where each daily capture extends the range, all 8
stores are re-fetched from Open-Meteo and the new cache files are committed back
by the build step, while earlier cache files remain in the repo as an audit
trail. An earlier version of `_fetch_store` deleted older-range files before
writing; see `docs/DECISIONS.md` Limitation 8 for why that behavior was removed
(short version: Open-Meteo revises its archive, and deleting the previous pull
destroyed the only record of what the API had said before a revision).

## Documentation

- **`docs/DECISIONS.md`** — design decisions, incidents, limitations, verified
  revenue figures, AI-use disclosure. Start here.
- `docs/PROJECT_GUIDE.md` — architecture and table reference.
- `docs/CONTEXT.md` — internal working notes.
- `audit_gaps.md` — audit against the submission checklist.

## Known limitations

Documented in full in `docs/DECISIONS.md`. The main ones:

- **SQLite lives in the repo**, so it is not a guaranteed single source of truth.
  Clone without pulling and you are working from stale data.
- **The Open-Meteo archive lags by a few days**, so the most recent order dates
  may have no weather row and join as NULL.

`data/ingestion_log.csv` is the authoritative ingestion log; the `ingestion_log` SQL
table is refreshed from that CSV on every `load_raw` run.

## After the course

The daily capture cron stays live through grading week by decision, while the
analysis window is locked at 2026-08-07. The live dashboard reads the full table,
so it will show figures past the deck's window by design.

Disable the daily GitHub Action in `.github/workflows/daily_capture.yml`. It will
otherwise keep committing to this repo indefinitely.

The predecessor repo (`jdyess-cell/BZAN-545-Final-Project`) has its own
`Collect Daily Orders` cron that was never disabled at the 08-03 consolidation;
it has been firing and failing daily since. Disable that workflow too.

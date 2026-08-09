# audit_gaps.md — Internal Submission Triage (not for polish)

> **Snapshot as of 2026-08-07. Superseded by the repo state at HEAD; see
> docs/DECISIONS.md for current state.**

Audited 2026-08-07 against the submission checklist and rubric. Submission due
2026-08-09 23:59; live presentation 2026-08-10. Every status cites repo
evidence; nothing here is a fix — findings only.

---

## 1. Checklist sweep

| # | Checklist item | Status | Evidence / what's missing |
|---|----------------|--------|---------------------------|
| 1 | Repeatable ingestion + raw preservation | **SATISFIED** | `src/capture.py`, idempotent `src/load_raw.py`; 31 preserved files in `data/raw/`; daily GH Action commits (`4d410a0`, `93800ac`) |
| 2 | Cleaned data + SQL loading | **SATISFIED** (with caveat) | `sql/01_schema.sql`, `src/transform.py`; `clean_orders` = 3,721 rows in `rocky_top.db`. Caveat: 2026-08-05 `unit_price` all NULL from `$` strings (see DECISIONS.md §6.1) |
| 3 | SQL access + runnable Python demo proving required tables exist | **SATISFIED** | `src/verify_tables.py` committed in `43bc6d8`; passes with exit 0 (both path and `-m` forms by design) |
| 4 | Ingestion log + monitoring/failure-handling docs | **SATISFIED** | Logs exist (`data/ingestion_log.csv`, `data/data_quality_log.csv`, growing daily via cron). Incident/failure-handling narrative committed in `docs/DECISIONS.md` §3 (`43bc6d8`); "Why" sections filled or removed on `connor/pre-submission-fixes` |
| 5 | Weather API data stored/cached | **SATISFIED** | 8 JSON files in `data/weather_cache/` (one per store, 2026-07-07..2026-08-07); `weather_daily` = 256 rows; `src/weather.py` uses the cache |
| 6 | Product crosswalk + documented ER decisions | **SATISFIED** | Crosswalk itself is strong: `product_crosswalk` table + `data/reference/product_crosswalk.csv` (80 rows, 72/4/4). `docs/DECISIONS.md` was committed at the exact path `src/crosswalk.py` line 5 references (`43bc6d8`); §4 ER "Why we decided this" rationale written on `connor/pre-submission-fixes` |
| 7 | Analytics-ready daily sales table | **SATISFIED** (with caveat) | `daily_sales` = 1,367 rows, grain-unique, revenue reconciles, weather joined 1,367/1,367. Caveat: 2026-08-05 `net_revenue = 0.0` (the `$`-price day) |
| 8 | Business-facing report with visuals + recommendations | **RESOLVED** | `dashboard/app.py` (Streamlit board: KPI tiles, revenue by store and category, weather-sensitivity views, inventory/promotion playbook) added in commit `2f4aef6` |
| 9 | Documentation of design decisions, limitations, gaps, known data issues | **SATISFIED** | `docs/PROJECT_GUIDE.md` §4 lists data quirks; DECISIONS.md committed with incidents + limitations (`43bc6d8`), "Why" sections filled or removed on `connor/pre-submission-fixes`. README rewritten with current status and the `-m` run commands (`8b0d36e`) |
| 10 | AI-use disclosure | **RESOLVED** | "AI-Use Disclosure" section written in `docs/DECISIONS.md`, added in commit `6fb4393` |

## 2. Reproducibility from a clean clone (actually tested 2026-08-07)

Tested by cloning this repo to a temp directory and running the commands.

- `uv sync` — **works**, exit 0 (installs 18 packages; `uv.lock` committed;
  Python 3.13 satisfied `requires-python >=3.11`).
- `uv run python src/run_pipeline.py` (the path form) — **FAILS**:

  ```
  ModuleNotFoundError: No module named 'src'
  ```

  Every script uses package-style imports (`from src import ...`,
  `from helpers import ...`), so only the module form works. A grader who
  types the path form gets a stack trace.
- `uv run python -m src.run_pipeline` (the form documented in
  `docs/PROJECT_GUIDE.md`) — **works end-to-end, exit 0**, no
  `credentials.json` needed, no network needed (weather served from the
  committed cache). Actual tail of output:

  ```
  [crosswalk] built 80 rows -> product_crosswalk (+ CSV). status: {'matched': 72, 'unresolved': 4, 'possible_match': 4}
  [transform] clean_orders rebuilt: 3721 rows (dropped 0 bad-date, 144 duplicate)
  [weather] weather_daily rebuilt: 256 rows (8 stores x 29 dates, 2026-07-07..2026-08-07)
  [transform] daily_sales rebuilt: 1367 rows (grain: order_date x store_id x category x category_source)
  [transform]   grain unique: True
  [transform]   reconciliation net_revenue: daily_sales=1,317,702.22 vs clean_orders line_revenue=1,317,702.22 -> MATCH
  [transform]   weather-joined rows: 1367/1367
  [pipeline] done
  ```
- `uv run python src/verify_tables.py` — works (both path and `-m` forms by
  design), exit 0, prints all 10 tables + row counts.

### Things a grader cloning fresh could trip over

1. **Path-form command fails** (above). [FIXED since this snapshot: `README.md`
   now leads with a Quick start showing the `-m` forms and states outright that
   the path form fails.]
2. ~~**Stale README** — a grader reading `README.md` first is told the repo is
   at "Step 0" with everything "[coming next]".~~ [FIXED since this snapshot:
   README was rewritten in `8b0d36e` and no longer says this.]
3. **`credentials.json` looks required but isn't.** The SQLite pipeline never
   reads it (`helpers/db.py` only loads it for the MySQL engines, i.e.
   `src/extract_reference.py`). [FIXED since this snapshot: README now has a
   Credentials section saying it is needed only for `src/extract_reference.py`
   on the UT VPN, and that nothing in Quick start needs it.]
4. **`src/crosswalk.py` references `docs/DECISIONS.md`** (line 5 and the
   `_validate` console message) — that path does not exist; the new file is
   at the repo root.
5. **`ingestion_log` in SQL** — a grader checking "ingestion log in SQL" finds a
   populated table: `data/ingestion_log.csv` is the source of truth and is
   mirrored into the `ingestion_log` table on every `load_raw` run.
   `docs/PROJECT_GUIDE.md` §1 lists `ingestion_log` among the DB tables, which
   is accurate.
6. Minor: two comments in `.github/workflows/daily_capture.yml` are in
   Turkish (lines 25, 37) — harmless, but visible to a grader.
7. No absolute paths anywhere (`helpers/config.py` resolves everything from
   the repo root) and no untracked dependencies — verified clean.

## 3. Prioritized gaps (by rubric points at risk)

| P | Gap | Rubric line at risk | Est. effort |
|---|-----|--------------------|-------------|
| ~~P0~~ | **CLOSED: business report exists.** `dashboard/app.py` (Streamlit: KPI tiles, revenue by store and category, weather-sensitivity views, inventory/promotion playbook) added in `2f4aef6`; it carries a dynamic zero-revenue banner, and the 2026-08-05 day itself now reconciles at $56,970.09. | Business analysis **5 pts**, plus Overall impression (6) | done |
| **P0** | **Partly closed: AI-use disclosure section exists, two rows still blank.** "AI-Use Disclosure" section written in `docs/DECISIONS.md` (`6fb4393`), but the tools table at `docs/DECISIONS.md:392-393` still carries literal `[Jack: fill in]` and `[James: fill in]` rows. The section ships blank for two of four members on an explicit checklist item. Only Jack and James can fill these. | Documentation **5 pts** bucket; explicit checklist item | Jack + James, unowned as of this snapshot |
| ~~P0~~ | **CLOSED: the why's are written and the audit files are committed.** `docs/DECISIONS.md` carries 6 filled "Why we decided this" sections, and `DECISIONS.md`, `CONTEXT.md` and `audit_gaps.md` are all committed (`43bc6d8`, `cfee8f1`), as is `src/verify_tables.py`. | Documentation 5, Product ER 8, Monitoring 8 | done |
| **P1** | **2026-08-05 `$`-price day: decide and state the position.** Currently revenue for that day is silently 0.0 in `daily_sales` and *no doc mentioned it before this audit*. Options: (a) document as a known issue in DECISIONS.md/report (already drafted; aligns with the instructor's "honest limitations" philosophy), or (b) also fix parsing + add a non-numeric DQ check. Unstated, it's a live-demo landmine: any grader summing August revenue sees a zero day. | Monitoring 8, Business analysis 5 | doc-only: done, review 15 min; code fix: 1–2 h |
| **P1** | **Stale README** — rewrite status, layout, and add the correct run commands (`-m` forms) + `verify_tables.py` mention; note `credentials.json` is only needed for VPN reference extraction. | Documentation 5, Overall impression 6 | 30–45 min |
| **P2** | **Path-form run command fails** — either document "-m only" prominently in README (cheap) or make scripts path-runnable. | Documentation 5 | doc: included above; code: 30 min |
| ~~P2~~ | **CLOSED — `ingestion_log` in SQL.** The CSV is the source of truth and is mirrored into the `ingestion_log` table on every `load_raw` run. | SQL modeling 8, Monitoring 8 | done |
| ~~P2~~ | **CLOSED: `docs/DECISIONS.md` path mismatch.** `43bc6d8` committed the file at `docs/DECISIONS.md`, the exact path `src/crosswalk.py` references. | Documentation 5 | done |
| **P3** | **Disable the GitHub Action after the course** (`.github/workflows/daily_capture.yml`, daily cron + `contents: write`). Not graded, but it will 404-and-commit daily forever. Put it on the team calendar for after 2026-08-10. | — | 5 min (later) |
| **P3** | Turkish comments in the workflow; `STATUS_MISSING` defined but never emitted (`helpers/config.py`) — cosmetic/consistency notes for the presentation Q&A. | Overall impression 6 | optional |

**Bottom line:** the pipeline, monitoring, and ER layers are genuinely strong
and reproduce cleanly from a fresh clone with one command. The submission's
two hard holes are the missing business report (5 pts, zero artifact today)
and the missing AI-use disclosure (explicit requirement). The highest-leverage
honesty item is the 2026-08-05 `$`-price day, which currently zeroes a full
day of revenue with no flag anywhere — exactly the kind of unstated limitation
the instructor says he grades against.

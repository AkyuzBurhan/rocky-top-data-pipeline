# CONTEXT.md — Where the Project Stands (internal, not a deliverable)

> **Snapshot as of 2026-08-07. Superseded by the repo state at HEAD; see
> docs/DECISIONS.md for current state.**

Last updated: 2026-08-07 (Friday), after the documentation/audit session.
Read this first; then [DECISIONS.md](DECISIONS.md) for the full incident
write-ups and [audit_gaps.md](../audit_gaps.md) for the graded-checklist sweep
and reproducibility test. This file does not restate them.

---

## 1. STATE

**Hard deadlines:** submission **Sun 2026-08-09 23:59**; graded live
presentation **Mon 2026-08-10**.

**Done and verified working:**

- Full pipeline (capture → raw → DQ → crosswalk → clean → weather →
  daily_sales) runs end-to-end from a **clean clone** with
  `uv sync && uv run python -m src.run_pipeline`, exit 0, no credentials, no
  network (weather cache committed). Output recorded in
  [audit_gaps.md](../audit_gaps.md) §2.
- Daily GitHub Actions automation is live and committing (commits `4d410a0`,
  `93800ac` on 2026-08-07).
- `src/verify_tables.py` proves all 10 required tables exist; passes both
  invocation forms. Committed in `43bc6d8`.
- [DECISIONS.md](DECISIONS.md) has facts for all seven incidents + 7
  limitations. Committed in `43bc6d8`, at `docs/DECISIONS.md`. All 7 "Why we
  decided this" sections have since been written.

**Outstanding (see [audit_gaps.md](../audit_gaps.md) §3 for the full table):**

- **P0** — Business report with visuals + recommendations: **no artifact
  exists at all** (5 rubric pts).
- **P0** — AI-use disclosure: not written (explicit checklist requirement;
  empty heading waiting in [DECISIONS.md](DECISIONS.md)).
- **P0** — Fill the "Why" sections; commit `DECISIONS.md`,
  `src/verify_tables.py` (and `audit_gaps.md` if we want it in the repo).
- **P1** — Decide the 2026-08-05 `$`-price position (document-only vs code
  fix) — see §4 below.
- **P1** — Rewrite the stale `README.md` (still says "Step 0 done", no run
  commands, implies credentials are required).
- **P2/P3** — `docs/DECISIONS.md` path
  mismatch in `src/crosswalk.py`, disable the GitHub Action after 08-10.

## 2. VERIFIED FACTS

Every number below was checked against repo contents on 2026-08-07 and can be
defended at the presentation. Details in [DECISIONS.md](DECISIONS.md).

| Fact | Value | Evidence |
|------|-------|----------|
| Raw files preserved | 32 (`orders_2026-07-07` … `08-08`; **no 08-06 file** — 404 day) | `data/raw/` |
| Ingestion log rows / DQ log rows | 33 / 31 | `data/ingestion_log.csv`, `data/data_quality_log.csv` |
| Table row counts | raw_orders 4,027; clean_orders 3,883; daily_sales 1,414; weather_daily 264; rejected_rows 144; crosswalk 80; stores 8; products 80; new_products 80; **ingestion_log 33** | `src/verify_tables.py` output, pasted in [DECISIONS.md](DECISIONS.md) §2 |
| rejected_rows = 144 | 140 stale-copy rows (07-24 file = byte-identical 07-23 file, same SHA-256) + 4 dup rows from 07-16 | `data/ingestion_log.csv` (hash `ebea0940…` twice), `rocky_top.db` rejected_rows |
| Crosswalk methods | 51 exact_name / 25 attributes_fuzzy / 4 none | `data/reference/product_crosswalk.csv` |
| Crosswalk statuses | 72 matched / 4 possible_match / 4 unresolved; 18 rows needs_review=1 | same |
| Scoring | 0.6·name + 0.2·subclass + 0.2·price within block (launch_date, gross_margin, department); MIN_SCORE=0.60; AMBIGUOUS_GAP=0.05 | `src/crosswalk.py` |
| Decoys caught | all 4 planted "… Alt" pairs (P1077–P1080 → possible_match); NP5077–5080 are literal "Alt" twins of NP5073–5076; P1078's *chosen* match is the Alt (NP5078) | `data/reference/new_products.csv`, `product_crosswalk.csv` |
| Unresolved | P1069/71/73/75, note "no candidate sharing launch_date+margin+department"; sales recovered as `category_source=legacy_recovered` | `product_crosswalk.csv`, `src/transform.py` |
| Integrity check | 76/76 new IDs unique (1:1) — **stdout only, never persisted** | `src/crosswalk.py _validate()`, clean-clone run output |
| Revenue reconciliation | daily_sales net = clean_orders line_revenue = **$1,434,503.62** → MATCH; grain unique: True; weather joined 1,414/1,414 | `rocky_top.db` at HEAD (the $1,317,702.22 figure in the [audit_gaps.md](../audit_gaps.md) §2 clean-clone transcript is the 2026-08-07 value, before the `$`-price fix) |
| 2026-08-05 `$` prices | all 155 rows `$`-prefixed → 155 NULL unit_price in clean_orders → **net_revenue = 0.0 for the whole day** with positive units_sold; DQ flagged nothing | `data/raw/orders_2026-08-05.csv`, `rocky_top.db`, `data/data_quality_log.csv` |
| 08-07 column reorder | handled — ingestion is header-based, not positional | `helpers/io.py`, `src/load_raw.py`, log rows for 08-07 |
| Path-form command | `uv run python src/run_pipeline.py` **fails** (`ModuleNotFoundError: No module named 'src'`); only `-m` form works | tested from clean clone, [audit_gaps.md](../audit_gaps.md) §2 |

## 3. CORRECTIONS

Things we believed (or our own docs claim) that turned out wrong:

1. **"URL migration happened ~2026-08-05."** Actually commit `5a2414f`
   changed `ORDERS_URL` on **2026-08-03 22:21 ET**; first live capture on the
   new URL was **2026-08-04T15:26:39Z** (`data/ingestion_log.csv` row 30).
2. **"The `$`-price day is just a potential limitations entry."** It is a live
   data-loss bug: DQ passed the file clean and `daily_sales` reports $0.00
   revenue for 2026-08-05. Nothing in the repo mentioned it before this audit.
3. **`docs/PROJECT_GUIDE.md` lists `ingestion_log` among the SQLite tables.**
   Correct as listed: `data/ingestion_log.csv` is the source of truth and is
   mirrored into the `ingestion_log` table on every `load_raw` run.
4. **README implies `credentials.json` is needed to run the project.** It is
   only read by the MySQL engines (`helpers/db.py`), i.e. by
   `src/extract_reference.py` on VPN. The whole SQLite pipeline runs without it
   (proven by the clean-clone test).
5. **Feared the 08-07 column reorder would break positional ingestion.**
   Ingestion is header-based; the file loaded normally (no Limitations entry).
6. **`README.md` says the repo is at "Step 0" with helpers/src/sql "coming
   next".** All of it is built and running daily.
7. **`src/crosswalk.py` points readers to `docs/DECISIONS.md`.** That path did
   not exist when this was written; `43bc6d8` committed the file at exactly
   that path, so the reference now resolves ([DECISIONS.md](DECISIONS.md)).
8. **`docs/PROJECT_GUIDE.md` §4 says the 07-31+ files mislabel NP values under
   a `product_id` header.** No committed raw file shows this (all use the
   `new_product_id` header; no DQ row has `has_source_flag=1`). Marked
   [UNVERIFIED] in DECISIONS.md — don't claim it in the presentation.

## 4. OPEN QUESTIONS

| # | Question | Owner |
|---|----------|-------|
| 1 | 2026-08-05 `$` prices: document-only (matches instructor's "honest limitations" philosophy) **or** fix `_to_float` + add a non-numeric DQ check (1–2 h)? The report must handle the $0 day either way (exclude/flag it). | Team decision Sat morning — whoever builds the report has the casting vote |
| 2 | Report format: notebook, HTML, or slides-with-charts? What tool? | Report owner (TBD Sat morning) |
| 3 | Who writes which "Why we decided this" sections in [DECISIONS.md](DECISIONS.md)? (7 blanks: 3 ingestion/monitoring incidents, $-prices, migration, ER method, SQLite trade-off) | Suggest: whoever wrote each piece of code writes its Why — Connor + Burhan to split; confirm with other two teammates |
| 4 | AI-use disclosure: one combined statement or per-member? What does the course policy require it to contain? | All four members — needs input from everyone; [UNVERIFIED: course policy text is not in the repo] |
| 5 | ~~Empty `ingestion_log` table: load the CSV into SQLite or correct the docs?~~ Settled: the CSV is the source of truth and is mirrored into the `ingestion_log` table on every `load_raw` run. | Closed |
| 6 | Should `audit_gaps.md` be committed (internal triage in a graded repo) or kept local? | Team decision before submission |
| 7 | Presentation demo: live `uv run python -m src.run_pipeline` + `verify_tables.py`, or pre-recorded/screenshots? (Live run is fast and worked from a clean clone — but source may 404 again, so don't demo `--capture`.) | Presenter (TBD) |
| 8 | Disable the GitHub Action after 08-10 (daily cron + `contents: write` will 404-and-commit forever). Who owns the repo settings? | Repo owner |

## 5. SCHEDULE

Working backward from Sun 08-09 23:59 submission and Mon 08-10 presentation.
Only two contributors are identifiable from git history (Connor, Burhan);
**[T3]/[T4] slots below need names Sat morning.**

### Saturday 08-08

| Task (from [audit_gaps.md](../audit_gaps.md) §3) | Est. | Owner |
|---|---|---|
| 10:00 team sync: decide open questions #1, #2, #3, #6; assign [T3]/[T4] | 30 min | all |
| **Business report** — weather-sensitivity by store/category from `daily_sales`, visuals + 2–3 recommendations; handle the 08-05 $0 day | 3–5 h | report owner + [T3] |
| ($-price code fix, only if #1 = fix) + re-run pipeline, re-verify reconciliation | 1–2 h | Burhan |
| Fill "Why we decided this" sections | 1–2 h | split per open question #3 |
| Rewrite `README.md` (status, `-m` run commands, `verify_tables.py`, credentials note) | 45 min | Connor |
| P2 cleanups if time: `ingestion_log` decision, `crosswalk.py` path comment | 40 min | [T4] |

### Sunday 08-09

| Task | Est. | Owner |
|---|---|---|
| AI-use disclosure — everyone sends their paragraph by noon | 30 min | all four |
| Final clean-clone test: `uv sync && uv run python -m src.run_pipeline` + `verify_tables.py` on a fresh machine | 30 min | Connor |
| Commit everything (DECISIONS.md, verify_tables.py, report, README; audit_gaps.md per #6) — **by ~20:00, not 23:50** | 30 min | Burhan |
| Presentation dry run: demo plan (#7), who says what, Q&A prep from §2 facts + §3 corrections | 1–1.5 h | all four |

### Monday 08-10

- Presentation. Bring §2 (defensible numbers) and the limitations story:
  stale/empty/404/$-prices all detected-or-documented, decoys caught,
  1:1 integrity — honesty is the grading criterion.
- After grades: disable the GitHub Action (open question #8).

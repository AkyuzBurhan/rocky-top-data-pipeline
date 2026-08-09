# deck_v2 — plain-language rebuild of the final presentation

A parallel deck to `deck/`. **Nothing in `deck/` is modified** — the python-pptx
build and its exported `.pptx` / `.pdf` remain the untouched fallback.

Same story, same numbers, same rehearsed Q&A beats as v1. What changed is the
delivery: plain English instead of engineering vocabulary, charts instead of number
tables, a consequence attached to every technical beat, and airtime rebalanced so
every presenter gets at least three continuous minutes.

## Files

| File | What it is |
|---|---|
| **`deck.html`** | **The presentation.** Open this. 20 slides, self-contained. |
| **`deck.pdf`** | **The backup**, and the Canvas submission. Same 20 slides, static. |
| `build_facts.py` | Generates `facts.json` from the locked DB snapshot + the live DB |
| `facts.json` | **Every number the deck is allowed to say**, with derivation and anchor |
| `deck.template.html` | The deck source, with `{{fact_id}}` tokens instead of numbers |
| `build_deck.py` | Resolves those tokens → `deck.html` |
| `slides.md` | Slide text, speaker notes, handoff lines, reveal order (the script) |
| `qa_pack.md` | Per-member Q&A prep — the rubric's 4 unearnable-by-slides points |
| `timing.md` | CORE and CORE+DEPTH minute-by-minute, cut order, handoff scripts |
| `make_charts.py` | Renders `assets/*.png\|svg` from `facts.json` (light + dark) |
| `check_facts.py` | Gate: no number reaches a slide without a fact id behind it |
| `export_pdf.ps1` | Re-exports `deck.pdf` from `deck.html` via headless Chrome |

## Build

```bash
uv run python deck_v2/build_facts.py    # facts.json (+ extracts the snapshot)
uv run python deck_v2/make_charts.py    # chart assets
uv run python deck_v2/build_deck.py     # deck.html
uv run python deck_v2/check_facts.py    # must print 0 failures
```

Then re-export the PDF:

```bash
powershell -File deck_v2/export_pdf.ps1
```

## Presenting

Open `deck.html` locally in Chrome. Arrow keys / Space / PageDown advance;
Home and End jump to the ends; swipe works on a tablet. `deck.html#7` deep-links
to slide 7. Press **E** to edit any text in place, then Ctrl+S to download an
edited copy (the original file is never overwritten).

Animations are **reveals, never carriers**: every slide's final state holds all
of its content. So the PDF loses nothing, and a stuck animation costs nothing.
Under headless automation the deck detects `navigator.webdriver` and skips
straight to final states, which is why the export can't catch a half-faded slide.

## Where the numbers come from

Two databases, on purpose:

- **S — the locked snapshot**, `git show 82d221e:rocky_top.db`. Every deck figure
  comes from here, so slides reproduce exactly what the team rehearsed and what
  `analysis/rain_analysis_output.md` documents. Extracted automatically; gitignored
  because it is reproducible from git.
- **L — the live database** in this worktree. Supplies the "has it run since?" facts
  and the **delta ledger**: the same statistics recomputed on today's data, so
  presenters know which numbers moved before an instructor asks.

Conventions are lifted from `analysis/rain_analysis.py`, not re-derived — rain is a
store-day with **strictly more than 1.0mm**, lifts are **medians**, agreement counts
all 8 stores. Any deviation fails to reproduce the locked figures.

`build_facts.py` **asserts** that window-invariant facts (revenue, row counts,
crosswalk, the 08-05 recovery) are identical in S and L, and exits nonzero if not.
Only weather-derived numbers have moved since the lock, and the delta ledger says by
how much.

It also **persists the crosswalk 1:1 integrity check**, which `src/crosswalk.py`
computes but only prints to stdout — closing one of the limitations the deck names.

## Design

"Audit Ledger" — bone paper with faint ruling, an orange signal rule down the left
margin, Bricolage Grotesque headlines over IBM Plex Mono evidence type, and IBM Plex
Sans body. The charts are drawn in the same IBM Plex Sans and the same palette
(`deck_v2/assets/fonts/` is bundled for matplotlib), so they read as part of the page
rather than as pasted-in images.

The recurring motif is the incident dot: **filled = caught on arrival, hollow = got
through**. It appears on the cover, in the timeline chart, and in the incident table,
so one visual idea carries the deck's argument.

Slides are authored on a fixed 1920×1080 stage and scaled as a whole, so the 16:9
layout is identical on a laptop, a projector, or a phone (it letterboxes; it never
reflows).

Run `check_facts.py` before every render.

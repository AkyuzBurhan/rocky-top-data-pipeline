# BZAN 545 Final Presentation: Locked Plan

Source of truth for the deck build. Every figure below is final and verified against source. Transcribe exactly, to the cent and decimal. Do not recompute, round differently, or "correct" anything.

## Constraints

- 25:00 max, hard cut at 27:30. Content budget 21:00, slack 4:00.
- Four speakers. Loads (minutes): Connor 6.5, Burhan 6.5, Jack 5.5, James 2.5.
- Presentation order across teams is randomized; deck locked the night before.

## Slide plan

Assertion titles below are the verbatim slide titles.

| # | Assertion title | Evidence / visual | Speaker | Min |
|---|---|---|---|---|
| 1 | 32 days live: five failures handled at source, one caught by audit, zero revenue lost. And when our headline finding failed its own test, we reported that too | Timeline strip 07-07 → 08-07, six incident markers: five caught at source, one (08-05) caught by audit only | Connor | 1.0 |
| 2 | Two design choices did the protective work: raw-first capture and header-based reads | One-row architecture diagram: capture → raw → transform → SQLite → dashboard. Corner box: SQLite-in-repo ← Actions can't reach campus MySQL behind VPN; cost = not a guaranteed single source of truth | Jack | 2.5 |
| 3 | Six incidents in 32 days; five handled at the layer where they occurred | Incident table: date / failure / detection layer / outcome. Rows: 07-24 stale · 07-28 ID migration · 08-03 empty · 08-05 dollar sign · 08-06 404 · 08-07 column reorder. Footnote: 144 rejected = 140 stale-file dupes + 4 within-file dupes 07-16; checks earn their keep on ordinary days too | Burhan | 2.0 |
| 4 | A dollar sign beat three checks and zeroed $57K. Raw-first made the miss recoverable and the fix verifiable | Arc: passed 3 checks (present ≠ parseable · silent coercion · symmetric nulls) → found by grep in pre-submission audit; no check fired, nobody saw it on the dashboard (say so plainly) → derived twice independently to $56,970.09 → parser fixed + non-numeric gate added. Leads with the miss; the fix is the resolution beat, not the headline | Jack | 3.0 |
| 5 | The matcher grades its own confidence: 76 of 80 mapped, and all 18 it's less than sure of are flagged with a reason | Funnel: 51 exact → high · 25 fuzzy → (11 high, 10 matched-medium, 4 possible-medium) · 4 → low. Mechanism box below the funnel. P1076 as talk-track exhibit. Handoff line: "the flag is advisory; back to that in limitations" | Burhan | 2.5 |
| 6 | Weather attaches at store-day: 1,367 rows carry only 232 independent weather observations | Join diagram, 8 stores × 29 dates, NULL tail from archive lag | James | 2.5 |
| 7a | The one robust weather effect: rain moved orders from in-store to pickup (+3.7pp) | Channel table: in_store 61.6 → 58.5 · pickup 17.9 → 21.6 · ship_from_store 20.4 → 19.9. n = 3,721 orders, z ≈ 2.8, p ≈ .006. Caveat unprompted, on-slide: within-store-day orders aren't independent → suggestive, not confirmed | Connor | 2.0 |
| 7b | The apparent 14% rain-day revenue lift fails threshold sensitivity and is at least partly a store-mix artifact | Threshold table: 1mm +13.9% (6/8) · 5mm +8.3% (4/8) · 10mm +18.9% (4/8) · 0.4mm +9.5% (3/8). Store mix: S001 86% rain days, $6,673 vs S006 14%, $4,714. Spearman 0.36. Line: "1 of 16 tests at p=.021 is what chance produces." Callback: a number that only holds at one threshold isn't a finding; same rule the crosswalk runs on | Connor | 2.0 |
| 8 | Staff and stock pickup capacity against the forecast: the recommendation that needs no demand claim | Single recommendation + one low-regret pilot | Connor | 1.0 |
| 9 | Five limitations, each verified. The biggest: correctness lives in Python, not the database | (1) SQLite-in-repo; (2) weather lag; (3) schema constraints: declared PKs/FKs don't exist in the live DB, anchored by the sqlite_master read; (4) advisory flag: 14 of 18 flagged rows flow unblocked (WHERE new_product_id IS NOT NULL), 4 unresolved degrade via legacy-key retention; (5) checks are enumerated, not anomaly-based: 08-05's discovery-by-grep is the evidence. Do not mention retired items (ingestion_log, currency parsing) | Burhan | 2.0 |
| 10 | The deliverable isn't the dashboard. It's a process that notices when it's wrong | Closing line: "$1,374,672.31, and we know the provenance of every dollar, including the $57K that briefly read as zero" | Connor | 0.5 |

Content total: 21.0 minutes.

## Slide 5 mechanism box

- Two thresholds, two jobs. Composite (0.6·name + 0.2·subclass + 0.2·price) ≥ 0.60 decides accept vs reject. name_sim ≥ 0.85 decides high vs medium confidence.
- Review queue = everything not high (14 medium + 4 low = 18).
- Three-threshold motif available in the talk track: MIN_SCORE, STRONG_NAME, and the rain cut that killed the revenue claim; one sentence on 7b, don't belabor.
- P1076 exhibit (talk track): a 0.50 name similarity still cleared the floor because subclass and price carried the composite to 0.668, 0.068 above the cut, and the match was auto-flagged for review; thin acceptance plus automatic review is the whole design in one product.

## Opening script (slide 1 speaker notes, verbatim as a script)

"In 32 days of live operation the pipeline handled five data failures at the source. It missed one: a dollar sign that turned $57K into zero. We found it, fixed it, and proved the fix against raw. Then our biggest analytical finding failed its own sensitivity test, so we killed it and kept the negative result. Everything in this talk is about a process that notices when it's wrong."

Tease both honesty beats, spoil neither: no pickup numbers, no threshold table until 7a/7b.

## Directed-question prep

Everyone preps all seven; James first in rehearsal. Deck mapping: Q1 → slide 4 notes; Q2 and Q3 → slide 5; Q4 and Q5 → slide 9; Q6 → slide 7a; Q7 → slide 7b.

| # | Question | Target | Answer core |
|---|---|---|---|
| 1 | Walk me through 08-05 | Not Jack | Present ≠ parseable · silent coercion · symmetric nulls. Found by grep in audit; no check fired. Double-derived to the cent; parser fixed; non-numeric gate added; fix verified against raw. |
| 2 | "P1076 matched at 0.50 name similarity against a 0.60 floor. Explain" | Not Burhan | "The floor applies to the composite, not the name. P1076's name scored 0.50, but subclass matched exactly and price closeness was 0.841, putting the composite at 0.668. Its block had one candidate. And because name similarity was under the 0.85 confidence threshold, it came out medium and landed in the review queue: the system flagged its own thin accept." |
| 3 | "72 matched but 18 need review; which is it?" | Anyone | Orthogonal axes: status = decision made, confidence = name-evidence strength. 10 of the 72 are medium: committed downstream, queued for audit. |
| 4 | Schema declares PKs/FKs; enforced? | Anyone | No: to_sql(if_exists="replace") recreates bare tables; verified in sqlite_master. Guarantees live in Python; known debt; alternative was DDL-then-append. |
| 5 | "If nothing reads the flag, what's it for?" | Not Burhan | Audit deliverable. Flag-and-proceed vs block-and-lose-revenue, with stated cost. Twin-swap risk bounded to the 4 possible_match (P1077-P1080); the 10 matched-medium carry a smaller, different risk (false positive in a single-candidate block), not zero. |
| 6 | Pickup shift is p=.006; why only "suggestive"? | Not Connor | Orders within a store-day share weather; non-independence shrinks effective n and widens true SE beyond the z-test's assumption. |
| 7 | Why present a result that failed? | Anyone | The sensitivity test is the result: a threshold-dependent number isn't a finding. Same rule the crosswalk enforces with explicit thresholds. |

## P1076 backup card (Q2; also the appendix component-breakdown card)

| Component | Value | Weight | Contribution |
|---|---|---|---|
| name_sim | 0.50 | 0.6 | 0.300 |
| subclass (cooler = cooler) | 1.00 | 0.2 | 0.200 |
| price (686.08 → 795.23) | 0.841 | 0.2 | 0.168 |
| Composite | | | 0.668 ≥ 0.60 |

- Formula, source-verified in src/crosswalk.py: max(0.0, 1.0 - abs(msrp - base_price) / base_price), normalized by legacy price: 1 - 109.15/686.08 = 0.841.
- If probed on the asymmetry (686 → 795 = 0.841 vs 795 → 686 = 0.863): intentional framing; the legacy product is the query, so the metric reads "how far did the price move from what it was." Symmetric alternative (mean denominator) gives 0.853 → composite 0.671; changes nothing about the accept or the tier. Immaterial here.

## Appendix contents

- P1076 component-breakdown card (table above).
- Full threshold sensitivity table (the four rows from 7b: 0.4mm, 1mm, 5mm, 10mm).
- Labeled placeholder for the poison-fixture gate screenshot (test still pending).

## Cut order (if rehearsal runs past 22:00)

1. Fold 8 into 7b's closing bullet, -1.0
2. Slide 10 → Connor's closing sentence, -0.5
3. Compress 3 onto slide 2's diagram, -1.0 (costs Burhan airtime; only under real pressure)

Untouchable: 4, 5, 7a, 7b, 9.

## Open items (Connor's, outside deck scope)

1. Poison-fixture test: push a synthetic $-priced file through, screenshot the gate firing. "Cannot recur silently" is a claim until this runs, and verify-before-acting is Adam's #1 flagged issue.
2. Timed run-through against the 21:00 budget, cut order in hand.

## Logistics

- Deck locked the night before; randomized order means slide 1 works cold at 10:00 AM.
- PowerPoint, PDF export for Canvas (Canvas previews HTML, not PDF, from other formats).
- Win+P → Extend (not Duplicate) for presenter view.
- Streamlit Community Cloud sleeps after 12 hours; open the dashboard before class so slide 7's chart isn't waiting on a cold start.

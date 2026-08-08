"""
All deck content, transcribed from ../plan.md (source of truth). Figures are
plan.md verbatim, to the cent and decimal. Strings not present in plan.md are
composed and carry a provenance citation in the Phase-2 readout:
  - slide 3 cell text        <- docs/DECISIONS.md incident entries + data logs
  - slide 5 branch labels    <- product_crosswalk.csv match_method values
  - slide 6 / 8 / A3 labels  <- plan.md's own words, rearranged
No em dashes (U+2014) anywhere, including notes; " · " is the separator.
"""

# Window anchoring (Connor's item 11; permanent per item 17).
WINDOW_LABEL = "07-07 to 08-07 · 32 days"
WINDOW_FOOTLINE = ("Window 07-07 to 08-07; deck locked against verified "
                   "08-07 data.")
WINDOW_NOTE = ("- If asked whether it has run since: give the run days "
               "elapsed since 08-07; the deck is locked against verified "
               "08-07 data")

# --- cover ----------------------------------------------------------------
COVER_KICKER = "BZAN 545 · Rocky Top Outfitters data pipeline"
COVER_TITLE_1 = "A process that notices"
COVER_TITLE_2 = "when it's wrong"          # orange full stop appended
# Jack's and James's surnames are not recoverable from the repo (DECISIONS.md
# carries literal "[Jack: fill in]" blanks); placeholders flagged in readout.
COVER_ROSTER = ("Connor Kersting · Jack Dyess · Burhan Akyuz · James Zhou")
COVER_DATE = "August 2026"
COVER_NOTES = [
    "Connor · pre-start",
    "- Open the dashboard before class: Streamlit Community Cloud sleeps "
    "after 12 hours; slide 7's chart must not cold-start",
    "- Win+P -> Extend (not Duplicate) for presenter view",
    "- Deck locked the night before; randomized order, slide 1 works cold "
    "at 10:00 AM",
]

# --- slide 1 --------------------------------------------------------------
S1_TITLE = ("32 days live: five failures handled at source, one caught by "
            "audit, zero revenue lost. And when our headline finding "
            "failed its own test, we reported that too")
# incident dates with day offsets from 07-07 (window day 0..31)
S1_INCIDENTS = [("07-24", 17), ("07-28", 21), ("08-03", 27),
                ("08-05", 29), ("08-06", 30), ("08-07", 31)]
S1_MISSED = "08-05"
LEGEND_CAUGHT = "handled at source"
LEGEND_MISSED = "caught by audit"
S1_NOTES = [
    "Connor, 1:00",
    "Opening script, verbatim:",
    '"In 32 days of live operation the pipeline handled five data failures '
    "at the source. It missed one: a dollar sign that turned $57K into "
    "zero. We found it, fixed it, and proved the fix against raw. Then our "
    "biggest analytical finding failed its own sensitivity test, so we "
    "killed it and kept the negative result. Everything in this talk is "
    'about a process that notices when it\'s wrong."',
    "- Tease both honesty beats, spoil neither: no pickup numbers, no "
    "threshold table until 7a/7b",
    "- Handoff: Jack on the two design choices that did the protective work",
]

# --- slide 2 --------------------------------------------------------------
S2_TITLE = ("Two design choices did the protective work: raw-first capture "
            "and header-based reads")
S2_STAGES = ["capture", "raw", "transform", "SQLite", "dashboard"]
S2_TAG_RAW = "raw-first capture"
S2_TAG_TRANSFORM = "header-based reads"
S2_CORNER = ("SQLite-in-repo ← Actions can't reach campus MySQL behind "
             "VPN; cost = not a guaranteed single source of truth")
S2_NOTES = [
    "Jack, 2:30",
    "- Two design choices did the protective work; everything on slide 3 "
    "traces back to them",
    "- Raw-first: the transient feed is preserved verbatim before any "
    "parse touches it; every later recovery reads from raw",
    "- Header-based reads: columns resolved by name, never by position",
    "- Corner box: SQLite-in-repo because Actions can't reach campus MySQL "
    "behind the VPN; stated cost = not a guaranteed single source of truth",
    "- Handoff: 'Burhan walks the month of incidents those choices absorbed'",
    "Q (not Jack) · What if a column had been renamed instead of "
    "reordered? Not caught at load: load_raw.py:101-103 backfills a "
    "missing expected column with NULLs instead of raising, so the day "
    "would load with NULL prices and surface as missing revenue "
    "downstream; reorder-proof is not rename-proof.",
]

# --- slide 3 --------------------------------------------------------------
S3_TITLE = ("Six incidents in 32 days; five handled at the layer where "
            "they occurred")
# (date, failure, detection layer, outcome, missed)
# Cell text composed from docs/DECISIONS.md; citations in the readout.
# 08-07 detection-cell wording is Connor-directed (item 4b), exact wording
# pending his approval; figures plan.md / raw-file verbatim.
S3_ROWS = [
    ("07-24", "Stale file re-served: 07-23 data again",
     "Capture · stale-file check",
     "Flagged; 140 duplicate rows quarantined", False),
    ("07-28", "Product-ID migration, P#### → NP####",
     "Quality flag · new-ID schema",
     "Crosswalk built; legacy keys retained", False),
    ("08-03", "Empty file: header row, zero data rows",
     "Capture · empty-file check",
     "Logged empty; nothing invented", False),
    ("08-05", 'Prices arrived as "$157.12" strings',
     "Audit grep; no check fired",
     "$56,970.09 recovered from raw; parser fixed, non-numeric gate added",
     True),
    ("08-06", "Source URL returned 404",
     "Capture · HTTP status",
     "Logged failed; clean recovery 08-07", False),
    ("08-07", "Column reorder in orders CSV",
     "Design · header-based reads (absorbed; auditable in raw)",
     "Zero impact; loaded correctly", False),
]
S3_FOOTNOTE = ("144 rejected = 140 stale-file dupes + 4 within-file dupes "
               "07-16; checks earn their keep on ordinary days too")
S3_NOTES = [
    "Burhan, 2:00",
    "- Six incidents, 32 days; five handled at the layer where they occurred",
    "- Walk the layers: capture handled stale (07-24), empty (08-03), 404 "
    "(08-06); the quality flag handled the ID migration (07-28); "
    "header-based reads absorbed the column reorder (08-07)",
    "- 08-05 is the open dot: the one that got through the pipeline",
    "- Footnote beat: 144 rejected = 140 stale-file dupes + 4 within-file "
    "dupes (07-16); checks earn their keep on ordinary days too",
    "- Handoff: 'the one that got through is Jack's story'",
    "If asked whether anything detected the reorder: no, nothing alerted; "
    "header-based reads made it a non-event, and the raw files document "
    "the change.",
    "Q (not Jack) · What if a column had been renamed instead of "
    "reordered? Not caught at load: load_raw.py:101-103 backfills a "
    "missing expected column with NULLs instead of raising, so the day "
    "would load with NULL prices and surface as missing revenue "
    "downstream; reorder-proof is not rename-proof.",
    "Cut order 3 (only under real pressure): compress this table onto "
    "slide 2's diagram, -1.0; costs Burhan airtime",
]

# --- slide 4 --------------------------------------------------------------
S4_TITLE = ("A dollar sign beat three checks and zeroed $57K. Raw-first "
            "made the miss recoverable and the fix verifiable")
S4_CHECKS_LABEL = "passed 3 checks"
S4_CHECKS = ["present ≠ parseable", "silent coercion", "symmetric nulls"]
S4_MISS = ("Found by grep in pre-submission audit. No check fired; nobody "
           "saw it on the dashboard.")
S4_AMOUNT = "$56,970.09"
S4_AMOUNT_LABEL = "derived twice independently"
S4_FIX = "parser fixed + non-numeric gate added"
S4_NOTES = [
    "Jack, 3:00",
    "- Lead with the miss: a dollar sign beat three checks and zeroed $57K",
    "- The three checks it passed: present ≠ parseable · silent coercion "
    "· symmetric nulls",
    "- Say it plainly: no check fired, and nobody saw it on the dashboard; "
    "found by grep in the pre-submission audit",
    "- Raw-first is why it was recoverable: derived twice independently to "
    "$56,970.09",
    "- Resolution beat, not the headline: parser fixed + non-numeric gate "
    "added; fix verified against raw",
    "- Handoff: 'Burhan on the matcher that grades its own confidence'",
    "Q1 (not Jack) · Walk me through 08-05: present ≠ parseable · silent "
    "coercion · symmetric nulls. Found by grep in audit; no check fired. "
    "Double-derived to the cent; parser fixed; non-numeric gate added; "
    "fix verified against raw.",
]

# --- slide 5 --------------------------------------------------------------
S5_TITLE = ("The matcher grades its own confidence: 76 of 80 mapped, and "
            "all 18 it's less than sure of are flagged with a reason")
S5_SOURCE = ("80", "legacy products")
# branch labels <- product_crosswalk.csv match_method / notes (see readout)
S5_TIERS = [("51", "exact name"), ("25", "fuzzy within block"),
            ("4", "no candidate")]
S5_CHIP_CAPTION = "confidence tier"
S5_CHIPS = [("51", "→  high"), ("11", "→  high"),
            ("10", "→  matched · medium"), ("4", "→  possible · medium"),
            ("4", "→  low")]
S5_STAT_MAPPED = ("76", " / 80", "legacy products mapped")
S5_STAT_REVIEW = ("18", "flagged for review, with a reason")
# the two bracket groups overlap on the middle two chips by design:
# 76 + 18 = 94 on an 80-product slide; the 14 shared rows explain it
S5_OVERLAP = "14 both mapped and flagged"
S5_MECHANISM_1 = ("Two thresholds, two jobs. Composite (0.6·name + "
                  "0.2·subclass + 0.2·price) ≥ 0.60 decides accept vs "
                  "reject. name_sim ≥ 0.85 decides high vs medium "
                  "confidence.")
S5_MECHANISM_2 = "Review queue = everything not high (14 medium + 4 low = 18)."
S5_NOTES = [
    "Burhan, 2:30",
    "- Funnel: 80 legacy -> 51 exact high · 25 fuzzy (11 high, 10 "
    "matched-medium, 4 possible-medium) · 4 low",
    "- Two thresholds, two jobs: composite >= 0.60 accept vs reject; "
    "name_sim >= 0.85 high vs medium",
    "- Review queue = everything not high: 14 medium + 4 low = 18",
    "- P1076 exhibit: weakest accept cleared the floor by 0.068 and got "
    "flagged; thin acceptance plus automatic review is the whole design "
    "in one product",
    "- Three-threshold motif: MIN_SCORE, STRONG_NAME, and the rain cut "
    "that killed the revenue claim; one sentence on 7b, don't belabor",
    "- Handoff: 'the flag is advisory; back to that in limitations'",
    "Q2 (not Burhan) · P1076 matched at 0.50 name similarity against a "
    "0.60 floor: 'The floor applies to the composite, not the name. "
    "P1076's name scored 0.50, but subclass matched exactly and price "
    "closeness was 0.841, putting the composite at 0.668. Its block had "
    "one candidate. And because name similarity was under the 0.85 "
    "confidence threshold, it came out medium and landed in the review "
    "queue: the system flagged its own weakest accept.'",
    "72 vs 76, say it without hesitating: 72 = status matched (51 + 11 + "
    "10); 76 = anything with a new_product_id (72 + the 4 possible_match)",
    "Q3 (anyone) · 72 matched but 18 need review, which is it? Orthogonal "
    "axes: status = decision made, confidence = name-evidence strength. "
    "10 of the 72 are medium: committed downstream, queued for audit.",
]

# --- slide 6 --------------------------------------------------------------
S6_TITLE = ("Weather attaches at store-day: 1,367 rows carry only 232 "
            "independent weather observations")
S6_LEFT = ("232", "independent weather observations", "8 stores × 29 dates")
S6_RIGHT = ("1,367", "daily_sales rows · category grain")
S6_JOIN_LABEL = "attaches at store-day"
S6_NULL_TAIL = "NULL tail · archive lag"
S6_NOTES = [
    "James, 2:30",
    "- Weather joins at store-day grain: 8 stores × 29 dates = 232 "
    "independent observations",
    "- 1,367 analysis rows share those 232 observations; rows are not "
    "independent evidence about weather",
    "- NULL tail: most recent days lag the weather archive; left NULL, "
    "never imputed",
    "- This is why every weather claim gets an independence caveat; "
    "Connor takes the findings",
    "- Grain: daily_sales is store × day × category (7 categories); 232 "
    "store-days × ~5.9 category rows = 1,367 rows over 07-07 to 08-07",
    "- Why 1,367 rows share only 232 weather observations: weather joins "
    "on (store, day), so every category row of a store-day inherits that "
    "store-day's single weather row",
    "- NULL-tail status at lock: the archive-lag mechanism is real "
    "(weather.py: the ERA5 archive trails by a few days) but in the "
    "locked 08-07 build the archive had caught up; zero NULL weather "
    "rows at lock",
    "- Handoff: 'Connor, with the one effect that survived'",
]

# --- slide 7a -------------------------------------------------------------
S7A_TITLE = ("The one robust weather effect: rain moved orders from "
             "in-store to pickup (+3.7pp)")
S7A_TABLE_HEADER = ["Channel", "Dry (%)", "Rain (%)"]
S7A_TABLE = [("in_store", "61.6", "58.5"),
             ("pickup", "17.9", "21.6"),
             ("ship_from_store", "20.4", "19.9")]
S7A_STAT = ("+3.7pp", "rain moved orders from in-store to pickup")
S7A_CAVEAT_1 = "n = 3,721 orders, z ≈ 2.8, p ≈ .006"
S7A_CAVEAT_2 = ("Within-store-day orders aren't independent → suggestive, "
                "not confirmed")
S7A_NOTES = [
    "Connor, 2:00",
    "- One robust weather effect: rain shifts channel mix, in-store to "
    "pickup, +3.7pp",
    "- Mix shift, not new demand: in_store 61.6 -> 58.5, pickup 17.9 -> "
    "21.6, ship_from_store 20.4 -> 19.9",
    "- Caveat unprompted, before anyone asks: n = 3,721, z ~ 2.8, p ~ "
    ".006, but within-store-day orders aren't independent -> suggestive, "
    "not confirmed",
    "Q6 (not Connor) · p=.006, why only suggestive? Orders within a "
    "store-day share weather; non-independence shrinks effective n and "
    "widens true SE beyond the z-test's assumption.",
    "If the live dashboard shows different numbers: the dashboard "
    "redeploys on push and moves daily; the deck is locked at verified "
    "08-07 data, per the window label on slides 1 and 3.",
]

# --- slide 7b -------------------------------------------------------------
S7B_TITLE = ("The apparent 14% rain-day revenue lift fails threshold "
             "sensitivity and is at least partly a store-mix artifact")
S7B_TABLE_HEADER = ["Rain cut (mm)", "Revenue lift (%)", "Stores with lift"]
S7B_TABLE = [("1", "+13.9", "6/8"),
             ("5", "+8.3", "4/8"),
             ("10", "+18.9", "4/8"),
             ("0.4", "+9.5", "3/8")]
S7B_MIX_LABEL = "store mix"
S7B_MIX_1 = "S001 · 86% rain days · $6,673"
S7B_MIX_2 = "S006 · 14% rain days · $4,714"
S7B_SPEARMAN = "Spearman 0.36"
S7B_LINE = "1 of 16 tests at p=.027 is what chance produces."
S7B_NOTES = [
    "Connor, 2:00",
    "- The 14% rain-day revenue lift fails its own sensitivity test: "
    "+13.9% at 1mm, +8.3% at 5mm, +18.9% at 10mm, +9.5% at 0.4mm; stores "
    "agreeing 6/8, 4/8, 4/8, 3/8",
    "- Store-mix artifact: S001 86% rain days at $6,673 average vs S006 "
    "14% at $4,714; Spearman 0.36",
    "- The line: 1 of 16 tests at p=.027 is what chance produces",
    "- Callback: a number that only holds at one threshold isn't a "
    "finding; same rule the crosswalk runs on",
    "Q7 (anyone) · Why present a result that failed? The sensitivity test "
    "is the result: a threshold-dependent number isn't a finding. Same "
    "rule the crosswalk enforces with explicit thresholds.",
    "Row order is deliberate: the original 1mm claim first, then the "
    "spread that kills it; A2 sorts ascending for reference.",
]

# --- slide 8 --------------------------------------------------------------
S8_TITLE = ("Staff and stock pickup capacity against the forecast: the "
            "recommendation that needs no demand claim")
S8_REC_LABEL = "The recommendation"
S8_REC = ("Staff and pre-stage pickup capacity when rain is in the "
          "forecast. Whatever total demand does, the mix moves toward "
          "pickup.")
S8_PILOT_LABEL = "The pilot"
# the "2pp" threshold is the slide's one orange element
S8_PILOT_LEAD = "One low-regret pilot: "
S8_PILOT_A = ("for two weeks, on forecast-rain days, reassign one "
              "associate to pickup staging at the two highest "
              "rain-frequency stores. Measure pickup share and pickup "
              "wait time; scale only if share moves at least ")
S8_PILOT_THRESH = "2pp"
S8_PILOT_B = ", otherwise stop. Reallocation, not spend."
S8_NOTES = [
    "Connor, 1:00",
    "- Recommendation depends only on the 7a mix shift; survives the "
    "killed revenue finding by construction",
    "- Provenance: dashboard app.py:503-504 ('staff and pre-stage pickup "
    "capacity when rain is in the forecast; the demand doesn't vanish in "
    "the rain, it moves channels') and app.py:565-566 ('the reliable "
    "lever is channel readiness')",
    "- Pilot stores by rain-day frequency (precip >= 1mm, store-day "
    "grain): S001 86.2% (25/29 days), S002 72.4% (21/29); next is S005 "
    "at 44.8%",
    "- 2pp is pre-registered before the pilot runs: below the observed "
    "3.7pp to allow attenuation, above noise; wait time is the guardrail "
    "so a share gain can't hide service degradation",
    "Cut order 1 (first cut if rehearsal runs past 22:00): fold this "
    "slide into 7b's closing bullet, -1.0",
]

# --- slide 9 --------------------------------------------------------------
S9_TITLE = ("Five limitations, each verified. The biggest: correctness "
            "lives in Python, not the database")
# (main text, code_runs) - code_runs mark spans set in IBM Plex Mono
S9_ITEMS = [
    "SQLite-in-repo: a binary DB in git isn't mergeable and isn't a "
    "guaranteed single source of truth",
    "Weather lag: the archive trails by a few days, so the newest "
    "store-days can carry NULL weather until backfill",
    "Schema constraints: declared PKs/FKs don't exist in the live DB, "
    "anchored by the sqlite_master read",
    "Advisory flag: 14 of 18 flagged rows flow unblocked (WHERE "
    "new_product_id IS NOT NULL), 4 unresolved degrade via legacy-key "
    "retention",
    "Checks are enumerated, not anomaly-based: 08-05's discovery-by-grep "
    "is the evidence",
]
S9_ORANGE_SPAN = "14 of 18"      # the one orange element
S9_NOTES = [
    "Burhan, 2:00",
    "- Five limitations, all verified; no hand-waving, each has an anchor",
    "- Biggest: correctness lives in Python, not the database; to_sql "
    "replace recreates bare tables",
    "- SQLite-in-repo and weather lag: known, stated on slides 2 and 6",
    "- Advisory flag: 14 of 18 flow unblocked (WHERE new_product_id IS "
    "NOT NULL); 4 unresolved degrade via legacy-key retention",
    "- Checks are enumerated, not anomaly-based: 08-05's discovery-by-grep "
    "is the evidence",
    "- Handoff: 'Connor closes'",
    "Q4 (anyone) · Schema declares PKs/FKs; enforced? No: "
    "to_sql(if_exists='replace') recreates bare tables; verified in "
    "sqlite_master. Guarantees live in Python; known debt; alternative "
    "was DDL-then-append.",
    "Q5 (not Burhan) · If nothing reads the flag, what's it for? Audit "
    "deliverable. Flag-and-proceed vs block-and-lose-revenue, with stated "
    "cost. Twin-swap risk bounded to the 4 possible_match (P1077-P1080); "
    "the 10 matched-medium carry a smaller, different risk (false "
    "positive in a single-candidate block), not zero.",
]

# --- slide 10 -------------------------------------------------------------
S10_TITLE = ("The deliverable isn't the dashboard. It's a process that "
             "notices when it's wrong")
S10_AMOUNT = "$1,374,672.31"
S10_LINE = ("and we know the provenance of every dollar, including the "
            "$57K that briefly read as zero")
S10_NOTES = [
    "Connor, 0:30",
    "- Closing line: '$1,374,672.31, and we know the provenance of every "
    "dollar, including the $57K that briefly read as zero'",
    "- The deliverable isn't the dashboard; it's the process",
    "If the live dashboard shows different numbers: the dashboard "
    "redeploys on push and moves daily; the deck is locked at verified "
    "08-07 data, per the window label on slides 1 and 3.",
    "Cut order 2: this slide folds into Connor's closing sentence, -0.5",
]

# --- appendix -------------------------------------------------------------
A1_TITLE = "Appendix · P1076 component breakdown"
A1_HEADER = ["Component", "Value", "Weight", "Contribution"]
A1_ROWS = [("name_sim", "0.50", "0.6", "0.300"),
           ("subclass (cooler = cooler)", "1.00", "0.2", "0.200"),
           ("price (686.08 → 795.23)", "0.841", "0.2", "0.168"),
           ("Composite", "", "", "0.668 ≥ 0.60")]
A1_FOOTNOTE = ("Formula, source-verified in src/crosswalk.py: max(0.0, 1.0 "
               "- abs(msrp - base_price) / base_price), normalized by "
               "legacy price: 1 - 109.15/686.08 = 0.841.")
A1_NOTES = [
    "Appendix · backup for Q2 (not presented)",
    "- The floor applies to the composite, not the name; 0.668 >= 0.60 "
    "accepts, name_sim 0.50 < 0.85 sends it to review as medium",
    "- If probed on the asymmetry (686 -> 795 = 0.841 vs 795 -> 686 = "
    "0.863): intentional framing; the legacy product is the query, so the "
    "metric reads 'how far did the price move from what it was.' "
    "Symmetric alternative (mean denominator) gives 0.853 -> composite "
    "0.671; changes nothing about the accept or the tier. Immaterial here.",
]

A2_TITLE = "Appendix · threshold sensitivity, full table"
A2_HEADER = ["Rain cut (mm)", "Revenue lift (%)", "Stores with lift"]
A2_ROWS = [("0.4", "+9.5", "3/8"),
           ("1", "+13.9", "6/8"),
           ("5", "+8.3", "4/8"),
           ("10", "+18.9", "4/8")]
A2_NOTES = [
    "Appendix · backup for Q7 (not presented)",
    "- Same four rows as 7b, ascending by threshold; the headline claim "
    "only holds at the 1mm cut",
]

A3_TITLE = "Appendix · poison-fixture gate"
# filled from deck/out/fixture/poison_fixture_meta.json at build time
A3_GATE_LINE = "Gate fired: nonnumeric(unit_price=5) · parser recovered 5/5"
A3_CAPTION = ("Executed {date} against pipeline code at commit {commit}: "
              "synthetic $-priced file (orders_2026-08-08.csv, 5 rows) run "
              "through the real quality gate (helpers/dq.py) and parser "
              "(src/transform.py). Artifacts: deck/out/fixture/"
              "poison_fixture_log.txt · rerun: python deck/poison_fixture.py")
A3_NOTES = [
    "Appendix · executed poison-fixture test (not presented)",
    "- Synthetic $-priced file: the gate flags nonnumeric(unit_price=5) "
    "while na_unit_price=0 shows the old blind spot; parser recovers 5/5 "
    "values to the cent",
    "- Anchors slide 3's 'parser fixed, non-numeric gate added' and the "
    "opening claim that 08-05 cannot recur silently",
    "- Rerun: python deck/poison_fixture.py (fixture in OS temp; touches "
    "nothing in data/ or rocky_top.db)",
]

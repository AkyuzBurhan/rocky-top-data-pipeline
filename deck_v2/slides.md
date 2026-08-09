---
deck: Rocky Top Outfitters — a pipeline that notices when it's wrong
course: BZAN 545 final project
date: 2026-08-10
presenters: [Connor, Jack, Burhan, James]
aspect: 16:9
primary_artifact: HTML
backup_artifact: PDF export (also the Canvas submission)

render_contract:
  - Every number on a slide is a {fact_id}. Never type a literal.
    Resolve from deck_v2/facts.json -> facts[id].display. check_facts.py enforces this.
  - One assertion per slide. Body text under ~15 words. Notes carry everything else.
  - Charts are pre-generated images from deck_v2/assets/. Do not re-plot in JS —
    canvas-drawn charts can vanish in the PDF export.
  - No pie charts, no dual axes, no legend where a direct label works.
  - Animations are REVEALS, never CARRIERS: each slide's final state holds 100% of
    its content, so the PDF (frozen end states) loses nothing and a stuck animation
    costs nothing.
  - Diagrams marked `native` are laid out in HTML/SVG by the renderer (they are
    layout, not data). If they come out weak, regenerate those three only with
    visual-explainer and embed as static SVG, restyled to this deck's theme.

tiers:
  CORE: minimum that scores full marks on all five rubric criteria (~15:30)
  DEPTH: adds credibility if time allows (~21:00 total)
  CUT-FIRST: folds into a neighbouring slide without breaking the narrative
---


## SLIDE 1 — [CORE] — Connor — 0:45

title: The feed broke six times in {window_days}. We lost zero dollars.
body: Five failures caught on arrival. One got through. We found it and recovered every cent.
stat: {net_revenue} — every dollar accounted for
asset: a_timeline.png
reveal: [title, timeline_axis, marks_caught, mark_missed, stat]

notes: |
  Opening script, verbatim:

  "In {window_days} of live operation, the feed we depend on broke six times.
  Five of those were caught the moment they arrived. One got through: a dollar
  sign that turned fifty-seven thousand dollars into zero. We found it, got every
  cent back, and proved the fix. Then our headline finding failed its own test,
  so we killed it. Everything in this talk is about a process that notices when
  it's wrong."

  - Tease both honesty beats. Spoil neither: no pickup numbers, no threshold table.
  - The open mark on the timeline is 08-05. Don't explain it yet — Jack owns it.
  - If asked "has it run since?": yes, through {live_last_date}; the deck is locked
    to a dated snapshot so it reproduces. Delta card if pressed.

handoff: "Jack built the front door — the two habits that did the protective work."


## SLIDE 2 — [CORE] — Jack — 1:15

title: Two habits did all the protective work: keep the original, never trust column order.
body: Everything that follows traces back to these two decisions.
asset: native — five-step flow (collect → keep original → clean → database → dashboard)
callout: Database lives in the repo, because our automation can't reach the campus server.
reveal: [title, flow_steps_left_to_right, tag_raw_first, tag_header_based, callout]

notes: |
  - Two design choices did the protective work; everything on the next slide
    traces back to them.
  - Keep the original: the daily file is a one-shot download — it's replaced at the
    source every morning. We save it byte-for-byte before anything parses it.
    Every recovery we've done reads from that copy.
  - Never trust column order: we look up columns by name, not by position.
  - The callout is a trade-off, said in one line: the database sits in the repo
    because GitHub's automation can't reach the campus MySQL server behind the VPN.
    Cost: it's not a guaranteed single source of truth. We state it, we don't hide it.
  - Do NOT go deeper into the code here. High-level only.

handoff: "Here's the month those two decisions had to absorb."


## SLIDE 3 — [CORE] — Jack — 1:30

title: Five of six failures were caught the moment they arrived.
body: One table, one month, plain English.
asset: native — incident table
table:
  header: [When, What went wrong, Caught by, What happened]
  rows:
    - ["Jul 24", "Yesterday's file sent again", "Arrival check", "Flagged; {rejected_stale} duplicate rows set aside"]
    - ["Jul 28", "Every product ID changed", "Quality flag", "Mapping rebuilt; nothing lost"]
    - ["Aug 3", "File arrived empty", "Arrival check", "Logged empty; nothing invented"]
    - ["Aug 5", "Prices arrived as text", "Nothing — found in audit", "{recovered_0805_net} recovered; gate added"]
    - ["Aug 6", "Source vanished (404)", "Arrival check", "Logged failed; clean the next day"]
    - ["Aug 7", "Columns shuffled", "Design absorbed it", "Zero impact"]
footnote: {rejected_total} rows set aside, never deleted — {rejected_stale} from the re-sent file, {rejected_other} from an ordinary day.
reveal: [title, rows_one_at_a_time, footnote]

notes: |
  - Six incidents in {window_days}. Five caught at the layer where they happened.
  - Walk the rows fast — the audience reads faster than you talk. Land on Aug 5.
  - Aug 5 is the open row: the one that got through. That's the next slide.
  - Footnote beat: quarantined, never deleted. We can always answer "where did
    those rows go?" The 4 from an ordinary day matter too — the checks earn their
    keep when nothing dramatic is happening.
  - If asked whether anything detected the Aug 7 column shuffle: no, nothing
    alerted. Reading by name made it a non-event, and the raw files document it.
  - If asked about a column RENAME instead of a reorder: honest answer — not caught
    at load. We backfill a missing expected column with NULLs instead of raising, so
    it would surface downstream as missing revenue. Reorder-proof is not rename-proof.

handoff: "The one that got through is worth three minutes on its own."


## SLIDE 4 — [CORE] — Jack — 1:30

title: A dollar sign turned $57K into $0. We got every cent back.
body: Three separate checks passed it. The preserved original is why recovery took minutes.
beats:
  - label: Passed three checks
    items: ["A “$” isn't a missing value", "The parser silently gave up", "Totals matched — both sides were empty"]
  - label: Found by
    items: ["A hand audit. No check fired. Nobody saw it on the dashboard."]
  - label: Recovered
    items: ["{recovered_0805_net} across {recovered_0805_lines}, derived twice independently"]
asset: native — three-beat arc
reveal: [title, beat_checks, beat_found, beat_recovered]

notes: |
  - Lead with the miss, not the fix. The fix is the resolution beat.
  - The three checks, in plain words: a dollar sign isn't a blank, so the
    missing-value check counted zero. The parser hit "$157.12", couldn't read it,
    and quietly turned it into nothing. And our totals-match check passed, because
    the same nothing was on both sides of the comparison.
  - Say it plainly: no check fired, and nobody saw it on the dashboard. We found it
    by grepping the raw files during a pre-submission audit.
  - Keeping the original is why it was recoverable: we recomputed it by hand from
    the saved file, then the fixed pipeline produced the identical number on its own.
  - Resolution beat, one sentence: parser fixed at the single point every number
    flows through, plus a new check that counts values that are present but
    unreadable.
  - Q1 target (directed at anyone but Jack): the three checks, found by audit,
    double-derived to the cent, gate added, fix verified against raw.

handoff: "That recovery worked because the originals were still there. Burhan hit a different problem — one morning every product ID in the feed had changed."


## SLIDE 4b — [DEPTH] — Jack — 1:15

title: We attacked our own fix with a poisoned file. It caught all five.
body: A fix you haven't tested is a claim, not a fix.
asset: poison_fixture_log.png
caption: Executed {poison_meta} — synthetic price-as-text file through the real check and the real parser.
reveal: [title, image, caption]

notes: |
  - "Cannot happen again" is a claim until you try to make it happen.
  - We built a synthetic file with five planted text prices and pushed it through
    the actual quality check and the actual parser — not a copy, the real ones.
  - The check flagged all five. The parser recovered all five to the cent.
  - The log, the screenshot, and the commit it ran at are committed in the repo.
  - If cut: fold one sentence into slide 4's recovery beat — "and we proved it by
    pushing a poisoned file through the real gate."

handoff: "That recovery worked because the originals were still there. Burhan hit a different problem — one morning every product ID in the feed had changed."


## SLIDE 5 — [CORE] — Burhan — 3:00

title: Every product got a new ID overnight. We re-matched {cw_mapped} and flagged every doubt.
body: The matcher grades its own confidence instead of hiding it.
funnel:
  source: [{cw_total}, "products in the old catalogue"]
  branches:
    - ["{cw_exact}", "same name — certain"]
    - ["{cw_fuzzy}", "matched on evidence"]
    - ["{cw_none}", "no candidate at all"]
  outcome: ["{cw_mapped} mapped", "{cw_review} flagged for a human, each with a reason"]
mechanism: Two thresholds, two jobs. One decides match or no match. The other decides confident or check-this.
asset: native — funnel
reveal: [title, funnel_source, funnel_branches, funnel_outcome, mechanism]

notes: |
  - Set the business stakes first: on July 28 the product catalogue was renumbered.
    Every ID in the feed changed. Without a mapping, you cannot compare this month's
    sales to last month's — trend analysis just stops.
  - The funnel: {cw_total} old products in. {cw_exact} had an identical name, so
    those are certain. {cw_fuzzy} needed evidence — we compared them only against
    candidates that shared the facts the migration didn't change (launch date,
    margin, department), then scored name, subcategory and price. {cw_none} had no
    candidate at all — those are discontinued products, and their sales still count
    through the old category.
  - Two thresholds, two jobs — this is the sentence that matters. One threshold
    decides accept or reject. A separate, higher one decides whether we're confident
    or whether a human should look. {cw_review} rows carry a doubt flag with a
    written reason.
  - P1076 as the exhibit: its name only scored {p1076_name} — but subcategory
    matched exactly and price was close, so the combined score reached
    {p1076_composite}, clearing the bar by {p1076_margin}. And because the name was
    weak, it was automatically sent to review. Thin acceptance plus automatic review
    is the whole design in one product.
  - Integrity: {cw_integrity} — no new product got claimed by two old ones.
  - Do NOT say P1076 is the weakest accept. It isn't ({cw_weakest} is lower).
  - Q2 (directed at anyone but Burhan): the bar applies to the combined score, not
    the name alone.
  - Q3 (anyone): status and confidence are different axes — status is the decision,
    confidence is how strong the name evidence was.

handoff: "Every sale in the weather analysis rides on those matches. James put the weather on them."


## SLIDE 5b — [DEPTH] — Burhan — 1:30

title: Four decoy products were planted in the data. The matcher hesitated on exactly those four.
body: Calibrated doubt — not false confidence, not false alarms.
stat: {cw_decoys} → flagged as too close to call
asset: a_scores.png
caption: Accepted and rejected scores overlap between {cw_overlap}. No threshold separates them cleanly.
reveal: [title, decoy_stat, chart, caption]

notes: |
  - The new catalogue contains four near-identical twins — literally named "Alt".
  - All four landed in the too-close-to-call bucket, because the top two candidates
    scored within a hair of each other. That's the behaviour we wanted: close enough
    to be worth a look, not close enough to accept quietly.
  - The chart is the honest part: accepted and rejected scores overlap. There is no
    magic cutoff. We put ours where a reviewer could still work through what fell
    near it, and we say that out loud rather than pretending the data is cleaner
    than it is.
  - If cut: one sentence on slide 5 — "four planted decoys, all four flagged."

handoff: "Every sale in the weather analysis rides on those matches. James put the weather on them."


## SLIDE 6 — [CORE] — James — 3:00

title: A month of sales is {daily_rows} rows — but only {store_days} independent weather readings.
body: Weather varies by store and day, not by product category.
asset: native — join diagram ({stores} stores × {order_dates})
note_on_slide: Every category row in a store-day inherits that store-day's one weather reading.
reveal: [title, stores_axis, dates_axis, join_arrow, row_count, note]

notes: |
  - Weather comes from Open-Meteo, the free archive of the same reanalysis dataset
    used in climate research. No API key, and we cache every response, so the whole
    project reproduces offline from what's committed.
  - Each store gets its own city's weather from its own coordinates — not a chain
    average. Days are set to store-local time so a "rain day" is the day customers
    actually experienced.
  - The number that matters: {stores} stores × {order_dates} = {store_days}
    independent observations. Our sales table has {daily_rows} rows because it's
    broken out by category, but weather doesn't vary by category — every category
    row in a store-day carries the same single reading.
  - So {daily_rows} rows is not {daily_rows} pieces of evidence about weather.
    Treating it that way would overstate every weather claim we make. That's why
    every finding in the next two slides carries a caveat.
  - Why {order_dates} and not {window_days}: the three missing days are the incident
    days — the re-sent file, the empty file, and the 404. The missing days show
    up here too.
  - Archive lag, if asked: the archive trails reality by a few days, so the newest
    dates can arrive with no weather and fill in later. At lock there were none.

handoff: "{store_days} honest observations. So what did weather actually do? Connor."


## SLIDE 6b — [DEPTH] — James — 1:15

title: The weather archive quietly rewrote its own history. We keep receipts now.
body: {d_revised} changed after we locked. Two crossed our rain line.
detail: {d_flips}
reveal: [title, revision_count, flips, fix]

notes: |
  - Our cache was named by date range, and the range grows every day a new order
    arrives. The original code deleted the previous file before writing the new one
    — so every run destroyed the only record of what the archive had said before.
  - That matters because the archive revises itself: {d_revised} have different
    rainfall today than when we locked, and two of them crossed our rain threshold.
    Both are the last date in our window, which is exactly how a preliminary value
    behaves before it settles.
  - Found it in audit, removed the deletion, pulls accumulate now the way the order
    files do.
  - The honest part: that doesn't bring anything back. The revisions happened while
    the deletion was live. Our numbers reproduce because they're pinned to a
    database snapshot — which is luck, not design.
  - So are the numbers wrong? No — they're dated, and we can say by exactly how
    much. The channel finding moves from {mix_shift_pp} to {d_mix_shift} and stays
    significant. Nothing changes direction.
  - If cut: this becomes the delta-card answer in Q&A, not a slide.

handoff: "{store_days} honest observations. So what did weather actually do? Connor."


## SLIDE 7 — [CORE] — Connor — 1:45

title: Rain doesn't change how much people buy. It changes how they pick it up.
body: Pickup rises {mix_shift_pp} on rainy days. Total demand barely moves.
asset: a_channel.png
caveat: {mix_lines} orders, {mix_z}σ, p = {mix_p} — but orders in the same store-day aren't independent, so: suggestive, not proven.
reveal: [title, dumbbell_dry, dumbbell_rain_slide, pickup_highlight, caveat]

notes: |
  - This is the one weather effect that survived every test we ran.
  - In-store goes {mix_instore}. Pickup goes {mix_pickup}. Ship-from-store is flat
    at {mix_ship}. It's a mix shift, not new demand — the same customers, buying a
    different way.
  - Give the caveat before anyone asks for it. That's the whole credibility play:
    the numbers are strong, but orders within the same store-day share the same
    weather and the same staffing, so they aren't independent observations. That
    shrinks the real sample below {mix_lines} and widens the true error bar beyond
    what the test assumes. Direction and size are stable. Certainty is capped.
  - Q6 (directed at anyone but Connor): why only suggestive at p = {mix_p}? Because
    non-independence, not because the effect is small.
  - If the live dashboard is on screen and disagrees: it uses a slightly different
    rain definition and averages instead of medians, and it reads the live table.
    The shift holds either way. Delta card has the exact numbers.

handoff: —


## SLIDE 8 — [CORE] — Connor — 1:00 (absorbs slide 9 if cut)

title: The {lift_headline} rain revenue boost fell apart under testing — so we don't claim it.
body: Move the rain cutoff and the number swings. That's not a finding.
asset: a_lift.png
detail: Rainiest store is also the richest — {storemix_rainiest} vs {storemix_driest}.
reveal: [title, bar_1mm, bars_other_thresholds, agreement_row, storemix_detail]

notes: |
  - We had a clean-looking result: {lift_1} on rainy days at a 1mm cutoff.
  - Then we moved the cutoff, which is the test any real effect should survive.
    {lift_5}. {lift_10}. {lift_0_4}. The estimate swings and the number of stores
    agreeing collapses. A result that depends on where you draw the line isn't a
    result.
  - Second reason we dropped it: store mix. {storemix_rainiest} — it's both the
    rainiest store and the highest-earning one. {storemix_driest}. Pooling across
    stores lets that difference impersonate a rain effect. Correlation across the
    eight stores is {storemix_spearman} — suggestive of exactly that confound, and
    far too small a sample to prove it either way.
  - The line to land: the sensitivity test IS the result. Same rule the product
    matcher runs on — an answer that only holds at one threshold isn't an answer.
  - Q7 (anyone): why present a result that failed? Because reporting the cutoff
    that flattered it would have been the dishonest option.
  - If slide 9 is cut, close here with the recommendation in one sentence (below).

handoff: "Everything you've seen has a cost column. Burhan — what we'd fix first."


## SLIDE 8b — [DEPTH] — Connor — 1:00

title: We ran {tests_total} tests. One came back significant — exactly what chance predicts.
body: Reporting that one as a finding would be the fishing.
detail: {tests_hit_detail}
asset: a_tests.png
reveal: [title, test_grid, single_hit, detail]

notes: |
  - {tests_total} tests: {stores} stores against two weather variables.
  - Exactly {tests_hits} came back significant. At this sample size, that is what
    randomness produces on its own — you expect roughly one in twenty at p < .05,
    and we ran sixteen.
  - We're showing this because the alternative is showing you the one hit and
    calling it a discovery. That's how weather-sensitivity claims get made, and
    it's why most of them don't replicate.
  - If cut: the line on slide 8 already carries it — "one hit in sixteen tests is
    what chance produces."

handoff: "Everything you've seen has a cost column. Burhan — what we'd fix first."


## SLIDE 9 — [CUT-FIRST] — Connor — 0:30

title: The bet worth making anyway: staff pickup when rain is forecast.
body: Reallocation, not spend. It needs no claim about total demand.
pilot: Two weeks. Rainy-forecast days. One associate moved to pickup at {pilot_stores}. Scale only if pickup share moves 2 points; otherwise stop.
reveal: [title, recommendation, pilot]

notes: |
  - This recommendation depends only on the mix shift — the finding that held. It
    survives the result we killed, by construction.
  - Why these two stores: they have the most rainy days, so they generate the most
    test days fastest.
  - The 2-point bar is set before the pilot runs: below the {mix_shift_pp} we
    observed, to allow for real-world attenuation, but above noise. Wait time is the
    guardrail — a share gain that comes with worse service isn't a win.
  - It's a reallocation, not a spend. That's what makes it worth doing on a
    suggestive finding rather than a proven one.
  - If cut: say the recommendation as one sentence at the end of slide 8.


## SLIDE 10 — [CORE] — Burhan — 1:15

title: What we'd fix first: our safety rules live in Python, not in the database.
body: Three limitations, each verified, none of them a surprise to us.
items:
  - "{constraints_bare} lost their declared keys when rebuilt. The code enforces them instead."
  - "{cw_flow_unblocked} flagged product matches flow through unblocked — the flag warns, it doesn't stop."
  - "Our checks catch the failures we thought of. Aug 5 was found by hand."
reveal: [title, item_1, item_2, item_3]

notes: |
  - Frame these as understood, not confessed. Each one has an anchor in the repo.
  - Biggest one: we declared primary keys and uniqueness rules in our schema, but
    the tables get rebuilt from scratch each run, and that drops the rules. We
    verified it by reading the database's own table definitions. So every guarantee
    we designed lives in Python instead. The pipeline is correct; the database would
    accept an incorrect write. Fix is known — build from the schema and append,
    rather than replace.
  - The review flag warns, it doesn't block. We chose that over blocking and losing
    revenue, and the cost is stated: {cw_flow_unblocked} flow through.
  - Our checks are a list of things we thought to check. The Aug 5 miss is the
    evidence — nothing anomaly-based would have needed us to imagine it first.
  - One more if asked, and it's the best one: a sale for a product in no catalogue,
    {np9999_lines} worth {np9999_revenue}. The check fired and logged it. Nobody
    acted on it. We found it tracing a total mismatch. Detection worked;
    follow-through didn't. That's the part of the loop we'd fix first.
  - Q4 (anyone): declared keys aren't enforced — verified, known debt, fix known.
  - Q5 (anyone but Burhan): the flag is an audit deliverable; risk is bounded to
    the four too-close-to-call rows, and the ten medium ones carry a smaller,
    different risk. Not zero, and we don't claim zero.

handoff: "Connor closes."


## SLIDE 11 — [CUT-FIRST] — Connor — 0:15

title: {net_revenue} — and we can show where every dollar came from.
body: Including the $57K that briefly read as zero.
reveal: [title, body]

notes: |
  - The deliverable isn't the dashboard. It's a process that notices when it's wrong.
  - If cut: this is Connor's closing sentence over slide 10.


## APPENDIX — not presented, Q&A backup only

### A1 — How P1076 cleared the bar
table:
  header: [Component, Score, Weight, Contribution]
  rows:
    - [Name similarity, "{p1076_name}", "0.6", "0.300"]
    - [Subcategory, "{p1076_subclass}", "0.2", "0.200"]
    - [Price closeness, "{p1076_price}", "0.2", "0.168"]
    - [Combined, "", "", "{p1076_composite} — clears {cw_floor} by {p1076_margin}"]

### A2 — Full threshold sensitivity
table:
  header: [Rain cutoff, Revenue lift, Stores agreeing]
  rows:
    - ["0.4mm", "{lift_0_4}", ""]
    - ["1mm", "{lift_1}", ""]
    - ["5mm", "{lift_5}", ""]
    - ["10mm", "{lift_10}", ""]

### A3 — Delta card: locked slides vs today's data
rows:
  - ["Pickup shift", "{mix_shift_pp}", "{d_mix_shift}"]
  - ["Threshold table", "see A2", "{d_lifts}"]
  - ["Revisions", "—", "{d_revised}: {d_flips}"]
note: Revenue, row counts and the entire product mapping are identical in both — asserted on every facts build.

### A4 — The poison-fixture test
asset: poison_fixture_log.png
caption: Executed {poison_meta}. Gate flagged all {poison_gate}; parser recovered all {poison_gate}.

# Team primer — what every slide actually means

Read this before you read the script or the Q&A pack. Everyone reads all of it,
including the parts that aren't your slides — the instructor directs questions at
whoever he wants.

No jargon without a translation. If a sentence here doesn't make sense, that's a
bug in this document, not in you.

**Time to read: about 25 minutes.**

---

# PART 1 — Eight ideas that unlock the whole deck

Learn these eight and every slide becomes obvious. Most of the deck is just these
ideas applied to different parts of the project.

---

## Idea 1 — What the project actually is

A robot that does the same chores every morning.

Every day at 9am, a GitHub server wakes up and:

1. Downloads one file of yesterday's orders from a web address.
2. **Saves that file untouched**, forever.
3. Reads it, cleans it up, and loads it into a database.
4. Attaches the weather for each store and day.
5. Writes down what happened, in a log.

That's it. The "pipeline" is those five steps on a timer.

The file it downloads is **transient** — it gets replaced at the source every
morning. If you don't grab today's copy today, it's gone. That single fact is why
step 2 exists, and step 2 is why we recovered $57,000 later.

---

## Idea 2 — "Keep the original" (raw-first)

Before we change anything, we save an untouched copy.

> **The analogy:** photocopy the receipt before you write on it. If you spill
> coffee on your notes, the receipt is still in the drawer.

We have 33 of those saved order files. We've never edited one.

**Why it earned its keep:** on August 5th, our cleaning code destroyed a day's
revenue. The database said $0. But the original file still had the real numbers
in it, so we got all $56,970.09 back in about fifteen minutes. Without the saved
copy, that money would have been unrecoverable — the source had already replaced
the file.

---

## Idea 3 — "Never trust column order"

A spreadsheet has columns. There are two ways to find the price column:

- **By position:** "price is the 9th column." Fast, and breaks the moment anyone
  reorders the file.
- **By name:** "find the column called `unit_price`." Slower to write, survives
  reordering.

We do it by name.

On August 7th the supplier shuffled the column order with no warning. Because we
look up columns by name, **nothing happened.** The file loaded correctly and we
only noticed because we went looking.

> **The honest limit:** reorder-proof is not *rename*-proof. If they'd renamed
> `unit_price` to `price`, our code would have quietly filled that column with
> blanks instead of raising an error. We know this. It's on our limitations list.

---

## Idea 4 — The $57,000 bug, and why three checks missed it

**What happened:** on August 5th the supplier sent prices as `$157.12` instead of
`157.12`. A dollar sign, and a piece of text where a number should be.

Computers treat `157.12` (a number) and `"$157.12"` (text) as completely different
things. You can multiply the first. You can't multiply the second.

Our code tried to convert the text into a number, failed, and — because of how it
was written — **silently replaced it with nothing** rather than complaining. All
155 orders that day ended up with no price. Revenue for the day: $0.00. Units
sold: still positive. A day where we apparently gave away 155 items for free.

**Now the important part: three separate safety checks all said the file was fine.**

| The check | What it looks for | Why it missed this |
|---|---|---|
| **Missing values** | Blank cells | `"$157.12"` isn't blank. It's *present*. It counted as healthy data. |
| **The converter** | Turns text into numbers | It was told "if you can't convert something, just put nothing there." It did exactly that, without a word. |
| **Reconciliation** | Do the summary totals match the line-by-line totals? | **Yes — because both were computed from the same broken data.** Zero equals zero. The check passed on a day that was missing entirely. |

That third one is the subtle one and it's worth understanding, because it's the
best story in the deck. A "do the totals match?" check only proves that two
calculations agree with each other. It cannot tell you that both are wrong in the
same way.

**How we actually found it:** a person searching the raw files by hand, weeks
later, during a pre-submission audit. No automated check fired. Nobody spotted it
on the dashboard.

**What we changed:** the converter now strips `$` and `,` before converting, and
there's a new check that counts values that are *present but unreadable* — the
exact gap that existed before.

---

## Idea 5 — The poison file (this is slide 04b, and it's simpler than it sounds)

**The problem:** we fixed the bug. How does anyone know the fix works?

We could say "trust us, we fixed it." That's a claim, not evidence.

**What we did instead:** we deliberately attacked our own fix.

1. We made a **fake order file** — 5 rows, with the prices written the bad way on
   purpose: `$19.99`, `$157.12`, `$72.70`, `$8.45`, `$249.00`.
2. We fed it to the **real** checking code and the **real** cleaning code. Not a
   copy, not a simulation — the same code that runs every morning.
3. We watched what happened.

**The result:**
- The new check **flagged all 5** — it reported `nonnumeric(unit_price=5)`.
- The old missing-value check *still said the file was clean* — which proves the
  old blind spot was real, not imagined.
- The cleaner **recovered all 5 values** correctly, to the cent.

We saved the log, and it's the screenshot on that slide.

> **"Poison" just means "deliberately contaminated test input."** It's the same
> idea as testing a smoke alarm by holding a match under it, instead of assuming
> it works because it's on the ceiling.

**Why this slide matters:** it turns "this can't happen again" from a promise into
something we demonstrated. It also runs in a temporary folder — it never touches
the real data or the real database.

**If asked:** *"A fix you haven't tested is a claim, not a fix. So we built a file
designed to break it, ran it through the real code, and it caught all five."*

---

## Idea 6 — The weather, and why our sample is 232 and not 1,367

This underpins every weather slide, so it's worth getting right.

**Where weather comes from:** a free public archive called Open-Meteo. You give it
a latitude and longitude and a date range; it gives you back daily maximum
temperature, minimum temperature, and total rainfall. We use each store's own
coordinates, so a store in one city gets that city's weather, not a chain average.

**Store-day:** one store, on one day. That's the unit weather comes in. Store S001
on July 14th had one temperature and one rainfall figure.

- 8 stores × 29 days with sales = **232 store-days.** That's how many weather
  readings we actually have.

**So why does the sales table have 1,367 rows?** Because sales are broken out by
*category* as well — camping, footwear, apparel, and so on. One store-day
generates roughly 6 rows, one per category it sold.

But **the weather doesn't change between categories.** Camping and footwear at
store S001 on July 14th share the exact same rainfall number.

> **The analogy:** eight friends each report the weather from their own town, once
> a day, for 29 days. That's 232 independent reports. If each friend texts you six
> times a day about it, you now have 1,392 texts — but still only 232 pieces of
> information.

**Why we make a slide out of it:** because it would be easy, and wrong, to say
"n = 1,367" and sound ten times more certain than we are. Our honest sample is
232. Every weather claim in the deck is caveated because of this.

---

## Idea 7 — The rain calculations (the part everyone finds hardest)

Take this one in five small steps. None of them is difficult alone.

### Step 1 — What counts as a "rainy day"?

Weather data doesn't say "rainy." It says a number of millimetres. So *we* had to
choose a line. We chose: **more than 1.0mm of rain in that store-day.**

That number is a judgement call and we say so out loud. There's nothing magic
about 1mm. Three store-days sat at exactly 1.0mm, so even "more than" versus "1mm
or more" changes which days count.

**This choice becomes the whole story of slide 08.** Hold on to it.

### Step 2 — Median vs average, and why we use the median

- **Average (mean):** add everything up, divide by how many. One enormous day
  drags it upward.
- **Median:** line the values up smallest to largest, take the middle one. One
  enormous day barely moves it.

Store-day revenue is *skewed* — a few big days, lots of ordinary ones. So we used
**medians**, which describe a typical day rather than a day distorted by outliers.

> The live dashboard uses averages. That's why the board and the slides print
> slightly different numbers. It's a definition difference, and it's documented —
> not a disagreement.

### Step 3 — The finding that HELD: rain changes *how* people buy

Every order records a **channel** — how the customer got the goods:
- **in-store** — bought it in the shop
- **pickup** — ordered online, collected at the shop
- **ship-from-store** — ordered online, posted out

Compare the mix on rainy store-days vs dry ones:

| Channel | Dry days | Rainy days | Change |
|---|---|---|---|
| In-store | 61.6% | 58.5% | −3.1 points |
| **Pickup** | **17.9%** | **21.6%** | **+3.7 points** |
| Ship-from-store | 20.4% | 19.9% | −0.5 points |

Total demand barely moves. The **mix** moves — out of the shop, into pickup.
People still want the stuff; they just don't want to stand in the rain.

**"Points" vs "percent":** going from 17.9% to 21.6% is a rise of **3.7
percentage points**. (It's also a ~21% increase *relative* to 17.9. We say
"points" because it's unambiguous.)

### Step 4 — What "p = 0.006" means, and why we still hedge

**A p-value answers one question:** if rain genuinely had no effect at all, how
often would pure luck hand us a gap this big?

p = 0.006 means: about 6 times in 1,000. Rare. So it's unlikely to be luck.

**But** that calculation assumes every order is an independent observation — that
each one is a separate roll of the dice. Ours aren't. All 130 orders at one store
on one day share that day's weather, that day's staffing, that day's promotion.
They're not 130 independent facts; they're closer to one fact with 130 receipts
(this is Idea 6 again).

Non-independence means the true uncertainty is **wider** than the test reports. So
the honest phrasing is **"suggestive, not proven"** — and we say it before anyone
asks, which is the single strongest credibility move in the talk.

### Step 5 — The finding we KILLED: rain and revenue

Here's the tempting one. Compare typical (median) store-day revenue, rainy vs dry:

**At our 1mm line: rainy days were 13.9% higher, and 6 of our 8 stores showed it.**

That looks like a real result. So we tested it the way any real result should be
tested: **we moved the line.**

| Where we draw "rainy" | Revenue lift | Stores agreeing |
|---|---|---|
| more than 0.4mm | +9.5% | 3 of 8 |
| **more than 1mm** | **+13.9%** | **6 of 8** |
| more than 5mm | +8.3% | 4 of 8 |
| more than 10mm | +18.9% | 4 of 8 |

The number bounces between +8% and +19% depending on an arbitrary choice we made.
Store agreement collapses from 6 to 3.

**A real effect shouldn't wobble like that.** If your answer changes when you nudge
a definition, you haven't found an effect — you've found an artefact of your own
setup. So we dropped the claim.

**The second reason we dropped it — the store-mix confound.**

Look at two stores:

| Store | How often it rains there | Typical daily revenue |
|---|---|---|
| S001 | 86% of days (25 of 29) | $6,673 |
| S006 | 14% of days (4 of 29) | $4,714 |

S001 is both our **rainiest** store and our **richest** store.

So when you pool all stores together and compare "rainy days" to "dry days," your
rainy pile is stuffed with S001 days and your dry pile is stuffed with S006 days.
You think you're measuring rain. You're partly measuring *which store you're
looking at.* That's a **confound** — a second explanation you can't separate out.

> **The analogy:** you notice people carrying umbrellas earn more. Umbrellas don't
> pay well. It's just that it rains more in the city, and city jobs pay more.

**Spearman 0.36, p = 0.38** — one more check. This measures whether rainier
stores *tend* to be richer stores across all 8. 0.36 is a mild positive tendency
(1.0 would be perfect, 0 would be none). But p = 0.38 means: with only 8 stores,
you'd see a pattern this strong by chance about 38% of the time. **So: consistent
with the confound, nowhere near enough data to prove it.** We say both halves.

### Step 6 — "16 tests, one hit" (slide 08b)

We tested 8 stores against 2 weather variables (temperature and rainfall) = **16
tests.** Exactly one came back "significant."

Here's the trap. The usual bar is p < 0.05, which means **a 1-in-20 chance of a
false alarm on each test.** Run 16 tests, and you should *expect* about one false
alarm even if weather does nothing whatsoever.

We got exactly one. That's not a discovery — that's the noise floor.

**Why we show the whole grid:** because the alternative is showing you the one lit
square and calling it a finding. That's how most weather-sensitivity claims get
made, and it's why most don't replicate. Showing all 16 is us marking our own
homework in public.

---

## Idea 8 — The product renumbering and the "crosswalk"

**What happened:** on July 28th, the supplier renumbered their entire catalogue.
Product `P1055` became something like `NP5055`. Every ID in the daily file changed
overnight.

**Why that's a problem:** if you can't tell that old P1055 and new NP5055 are the
same jacket, you can't compare this month's sales to last month's. Trend analysis
just stops.

**A crosswalk is a translation table** — old ID on the left, new ID on the right.
We had to build one for 80 products.

**How we built it, in three tiers:**

1. **51 products had an identical name** in both catalogues. Certain. Done.
2. **25 needed evidence.** For these we:
   - First **narrowed the candidates**: only compare against new products that
     share the facts the renumbering *didn't* change — same launch date, same
     profit margin, same department. This cuts thousands of comparisons down to a
     handful, which is both faster and more accurate.
   - Then **scored** each candidate:
     `score = 0.6 × (name similarity) + 0.2 × (subcategory match) + 0.2 × (price closeness)`
   - Name carries the most weight because it's the field most likely to identify
     the product. Price votes but doesn't decide, because prices genuinely changed.
3. **4 products had no candidate at all** — discontinued in the migration. Their
   sales still count; they just fall back to their old category.

**Two thresholds doing two different jobs** — this is the sentence that matters:

- **0.60 on the combined score** decides *match or no match.*
- **0.85 on the name alone** decides *confident, or should a human look at this?*

They're different questions. The second one doesn't reject anything; it just
raises a hand. That's how we ended up with **18 rows flagged for review**, each
with a written reason.

**The worked example (P1076, appendix A1)** — this is the one you'll be asked
about:

| Component | Score | Weight | Contributes |
|---|---|---|---|
| Name similarity | 0.50 | 0.6 | 0.300 |
| Subcategory | 1.00 | 0.2 | 0.200 |
| Price closeness | 0.841 | 0.2 | 0.168 |
| **Combined** | | | **0.668** |

The name only scored 0.50 — barely half. So why did we accept it?

**Because the 0.60 bar applies to the combined score, not the name.** Subcategory
matched perfectly and the price was close, dragging the total to 0.668 — clearing
the bar by 0.068. And because the *name* was under 0.85, it was automatically sent
to the review pile. **The system flagged its own weak match.** That's the whole
design philosophy in one product.

> Don't say P1076 was our *weakest* accept — it wasn't. P1072 at 0.657 was lower.
> Just say it was a *thin* accept.

**The decoys (slide 05b):** the dataset contained four deliberately planted
near-duplicates — products literally named "... Alt" that mirror four real ones.
They're a trap. Our matcher flagged **exactly those four** as "too close to call"
rather than guessing. That's the system behaving correctly: close enough to be
worth a look, not close enough to accept quietly.

---

# PART 2 — Slide by slide

For each: what's on screen, what it means, and the one sentence to remember.

---

### Cover
Title, team, and the six incident dots. **Filled = caught on arrival. Hollow = got
through.** That dot language repeats all through the deck.

---

### Slide 01 — "The feed broke 6 times in 32 days. We lost zero dollars." *(Connor)*
**On screen:** a timeline of the month with six markers; five filled, one hollow.
**Means:** in 32 days of real operation, six things went wrong with our incoming
data. Five were caught immediately. One wasn't, and we found it later by hand.
**Remember:** *this pipeline catches its own mistakes — and we're honest about the
one it missed.*

---

### Slide 02 — "Two habits did all the protective work" *(Jack)*
**On screen:** the five pipeline steps, with two highlighted.
**Means:** Ideas 2 and 3 above — keep the original, and look up columns by name.
Everything on the next slide traces back to these two decisions.
**Also on screen:** the database lives in the code repository, because GitHub's
servers can't reach the university's database behind the VPN. Stated cost: it
isn't a guaranteed single source of truth.
**Remember:** *design, not heroics.*

---

### Slide 03 — "5 of 6 failures were caught the moment they arrived" *(Jack)*
**On screen:** the six incidents as a table.

| When | What happened |
|---|---|
| Jul 24 | The supplier re-sent yesterday's file with today's name. Our check compares the date *inside* the file to the date we expected, spotted the mismatch, and quarantined all 140 duplicate rows. |
| Jul 28 | The product renumbering (Idea 8). Flagged, mapping rebuilt, nothing lost. |
| Aug 3 | The file arrived with column headers and zero rows. Logged as "empty" — which is deliberately different from "failed." Empty means the source answered and had nothing; failed means we couldn't reach it. |
| Aug 5 | The $57K dollar-sign day (Idea 4). Nothing caught it. |
| Aug 6 | The web address returned "404 Not Found." Logged as failed; the next day was clean. |
| Aug 7 | Columns shuffled. Absorbed by design (Idea 3); zero impact. |

**"144 rows set aside, never deleted"** — 140 from the re-sent file, 4 ordinary
duplicates from July 16th. We never silently delete a row; we move it aside with a
written reason, so you can always answer "where did those go?"
**Remember:** *the checks work at the door, and they earn their keep on quiet days too.*

---

### Slide 04 — "A dollar sign turned $57K into $0" *(Jack)*
**On screen:** three beats — the checks it passed, how we found it, what we recovered.
**Means:** Idea 4, in full.
**Remember:** *the preserved original is the only reason this was recoverable.*

---

### Slide 04b — "We attacked our own fix with a poisoned file" *(Jack, optional)*
**On screen:** the actual log from that test.
**Means:** Idea 5.
**Remember:** *a fix you haven't tested is a claim, not a fix.*

---

### Slide 05 — "Every product got a new ID overnight" *(Burhan)*
**On screen:** a funnel — 80 old products in; 51 certain, 25 matched on evidence,
4 with no candidate; 76 mapped, 18 flagged.
**Means:** Idea 8.
**Watch the two numbers:** **76** = products that got a new ID. **18** = products
carrying a doubt flag. They overlap — 14 products are both mapped *and* flagged.
That's not a contradiction: *mapped* is the decision, *flagged* is how confident
we were.
**Remember:** *the matcher grades its own confidence instead of hiding it.*

---

### Slide 05b — "Four decoy products were planted" *(Burhan, optional)*
**On screen:** every candidate score, accepted vs rejected, with the overlap shaded.
**Means:** the decoys (Idea 8) — and the honest bit: accepted and rejected scores
**overlap between 0.64 and 0.94.** There is no cut-off that cleanly separates good
matches from bad ones. Any line trades false matches against missed ones. We put
ours where a human reviewer could still work through what fell near it.
**Remember:** *calibrated doubt — we flagged the traps instead of guessing.*

---

### Slide 06 — "1,367 rows, but only 232 weather readings" *(James)*
**On screen:** 232 little squares, drawn out so you can count them, next to 1,367.
**Means:** Idea 6.
**Remember:** *weather varies by store and day, not by product category — so the
honest sample is 232.*

---

### Slide 06b — "The weather archive rewrote its own history" *(James, optional)*
**On screen:** two store-days that changed after we locked our numbers.
**Means:** weather archives publish an early estimate and correct it later —
normal, and not a mistake by anyone. Since we locked, 5 store-days changed and 2
crossed our rain line (S007 went 2.3mm → 0.9mm, so rainy became dry; S008 went
0.4mm → 3.7mm, dry became rainy).
**The honest part:** our cache used to delete the previous download every run, so
we destroyed our own record of what the archive said before. We found that in the
audit and fixed it — but it doesn't recover the old data. Our numbers reproduce
only because they're pinned to a saved snapshot, which is luck, not design.
**Remember:** *even the data source needs auditing.*

---

### Slide 07 — "Rain changes how they pick it up" *(Connor)*
**On screen:** pickup +3.7 points, ship −0.5, in-store −3.1.
**Means:** Idea 7, steps 3 and 4.
**Remember:** *not more demand — different demand. Suggestive, not proven.*

---

### Slide 08 — "The +14% boost fell apart under testing" *(Connor)*
**On screen:** the same comparison at four different rain cut-offs.
**Means:** Idea 7, step 5.
**Remember:** *a number that only holds at one threshold isn't a finding — the
sensitivity test IS the result.*

---

### Slide 08b — "16 tests, one hit" *(Connor, optional)*
**On screen:** a grid of 16 squares, one lit.
**Means:** Idea 7, step 6.
**Remember:** *one hit in sixteen is what chance produces.*

---

### Slide 09 — "Staff pickup when rain is forecast" *(Connor, optional)*
**On screen:** the pilot, the success bar, and "$0 new spend."
**Means:** the only recommendation that survives everything we killed, because it
depends solely on the channel shift. Two weeks, forecast-rain days, one associate
moved to pickup staging at our two rainiest stores. **Scale only if pickup share
moves 2 points, otherwise stop** — and that bar is set *before* the pilot runs, so
we can't move the goalposts afterwards. Waiting time is watched as a guardrail, so
a share gain that comes with worse service doesn't count as a win.
**Remember:** *reallocation, not spend — which is what makes it worth doing on a
suggestive finding.*

---

### Slide 10 — "Our safety rules live in Python, not the database" *(Burhan)*
**On screen:** three limitations.

**Limitation 1, explained properly** — this is the most technical claim in the deck:

SQL databases let you declare rules that the database itself enforces: *this
column must be unique*, *this must refer to a real store*. We wrote all of those
rules in our schema file, and they're correct.

But our code rebuilds several tables each run using a shortcut
(`to_sql(..., if_exists="replace")`) that **deletes the table and recreates it
from scratch** — and the recreated version has no rules attached. So **8 of our 10
tables have no enforced rules in the live database.** Our Python code checks the
same things, so the data is correct. But the *database* would accept a bad write
if anything ever bypassed our code.

> **The analogy:** we have a strict door policy written down and a bouncer who
> follows it perfectly — but the door itself has no lock. Nothing bad has
> happened. It still isn't how you'd build it.

**Limitation 2:** 14 of the 18 flagged product matches flow through unblocked. The
flag warns; it doesn't stop anything. We chose that over blocking, which would
have lost revenue — and we state the cost rather than hiding it.

**Limitation 3:** our checks catch the failures we thought to check for. August 5th
was found by a human, not a check. Anything we didn't imagine, we won't catch.

**One more if it comes up (the best one):** four order lines referenced product
`NP9999`, which exists in neither catalogue — $930.45 of sales. The pipeline kept
the money and labelled the category "UNKNOWN" rather than dropping it, and **the
quality check fired and logged it.** Nobody acted on the flag. We rediscovered it
by tracing a mismatch in totals. *The detection worked; the follow-through didn't
— and that's the part of the loop we'd fix first.*

**Remember:** *named, bounded, and we know the fix.*

---

### Slide 11 — "$1,374,672.31" *(Connor)*
**Means:** total sales across the frozen window, and we can trace every dollar —
including the $57K that briefly read as zero.
**Remember:** *the deliverable isn't the dashboard, it's a process that notices
when it's wrong.*

---

# PART 3 — Two things everyone must be able to say

## 1. Why our slides don't match a fresh run (the "delta card")

Our pipeline runs daily and the database grows. If the slides read live data,
every number would drift between rehearsal and presentation. So the deck is
pinned to a **saved copy of the database from a specific date.**

Since then, Open-Meteo revised its own historical rainfall (Idea/Slide 06b). Five
store-days changed; two crossed our rain line. So:

| | On the slides | On today's data |
|---|---|---|
| Pickup shift | +3.7 points | +3.4 points |
| Revenue, row counts, product mapping | — | **identical** |

**The one sentence:** *"The slides are locked to a dated snapshot so they're
reproducible. Five store-days have since been revised by the weather archive
itself — two crossed our rain cut-off. The finding holds; the third decimal
moved."*

## 2. Answer for your own layer — and let others answer for theirs

Criterion 4 is 4 of the 20 points, and it's awarded for **individual**
understanding. When the instructor directs a question at someone, that person
answers. If they hesitate, three seconds of silence costs less than a teammate
jumping in — a rescue transfers their points away.

If a question lands on you and you genuinely don't know:

> *"That's James's layer — James?"*

That is a strong answer. Guessing is the only way to actually lose these points.

---

## Quick glossary

| If someone says | They mean |
|---|---|
| Pipeline | The daily robot: download → save → clean → store |
| Raw / bronze layer | The untouched saved copies of the original files |
| Ingestion | Downloading and loading the daily file |
| Idempotent | Running it twice can't double-count anything |
| Schema | The blueprint of what tables and columns exist |
| Schema drift | The supplier quietly changing the file's shape |
| Crosswalk | The old-ID → new-ID translation table |
| Entity resolution | Deciding whether two records are the same real thing |
| Fuzzy matching | Scoring how similar two names are, rather than requiring identical |
| Blocking | Only comparing candidates that already share some unchanged fact |
| Quarantine / rejected rows | Suspect rows set aside with a reason, never deleted |
| Orphan | A record pointing at something that doesn't exist in any catalogue |
| Reconciliation | Checking that totals match across two layers |
| Store-day | One store, one day — the unit weather comes in |
| Grain | What one row of a table represents |
| Median | The middle value; resists outliers |
| Percentage point | The gap between two percentages (17.9% → 21.6% = 3.7 points) |
| p-value | How often pure luck would produce a result this big |
| Confound | A second explanation you can't rule out |
| Sensitivity test | Re-running with a definition nudged, to see if the answer survives |
| Threshold | A line we chose; not a fact of nature |

---

## Addendum — say-aloud lines added after final review

Two spoken lines only. Nothing on the slides changed for either one.

1. **Jack, on slide 02:** “We considered enforcing our data rules inside the
   database itself; we rejected it because our automation can't reach the
   campus database server, so the rules live in Python instead — that
   trade-off comes back on slide 10.”

2. **Jack, on slide 04b:** “This is a receipt, not code — the log of the test
   firing, saved and committed.”

# Connor — speaking script

Everything you say out loud, in order, with timings. Numbers here match
`facts.json` exactly; nothing is from memory.

Your total: **5:15 of talking**, in two blocks — the open (1:00) and the findings
run (4:15) — plus two handoffs and a one-line close.

**Delivery rules**
- The slide is the evidence. You are the argument. Never read the slide.
- Full stop after every number. The room needs a beat to absorb a figure.
- Where it says `[pause]`, actually stop. It will feel too long. It isn't.
- If you blank: the next sentence is always the *consequence* of the last number.

---

## BLOCK 1 — THE OPEN (0:45) · slides: cover, then 01

You are first, cold, at 10:00. This is the only part you should be able to
deliver with the screen switched off.

### On the cover (0:20)

The cover now shows the business question. Speak it — don't leave it as decoration.

> "Good morning. We're Rocky Top Outfitters — a daily data pipeline for an
> outdoor retailer with eight stores.
>
> Our question was simple: does weather change what people buy? `[pause]`
>
> An honest answer needed something first — a pipeline we could trust.
> I want to start with the part most projects leave out." `[pause — advance]`

### On slide 01 (0:30)

> "In thirty-two days of live operation, the feed we depend on broke six times.
>
> Five of those were caught the moment they arrived. `[pause]`
>
> One got through — a dollar sign that turned fifty-seven thousand dollars into
> zero. We found it, got every cent back, and proved the fix.
>
> Then our biggest analytical finding failed its own sensitivity test, so we
> killed it and kept the negative result. `[pause]`
>
> Everything in this talk is about a process that notices when it's wrong."

**Do not** say the pickup number, the threshold table, or how we found the
dollar sign. You are teasing two honesty beats. Jack and I spend them later.

### Handoff → Jack (0:15)

> "Jack built the front door — the two habits that did the protective work."

---

## → Jack, Burhan, James speak (~11 minutes). Your re-entry cue:

James ends with: *"232 honest observations. So what did weather actually do?
Connor."*

Be standing and facing the room before he finishes that sentence.

---

## BLOCK 2 — THE FINDINGS RUN (4:15) · slides 07, 08, 08b, 09

Treat these four slides as **one argument**, not four topics:
*what held → what didn't → how we know → what to do about it.*

### Slide 07 — the finding that held (1:45)

> "One weather effect survived everything we threw at it. It isn't the one we
> expected. `[pause]`
>
> Rain doesn't change how much people buy. It changes how they pick it up.
>
> On rainy days, pickup rises from seventeen-nine percent of orders to
> twenty-one-six. That's a shift of three point seven points. In-store falls
> three point one. Ship-from-store barely moves. `[pause]`
>
> So it's a mix shift, not new demand. The same customers, buying a different
> way.
>
> Now — the caveat, before anyone asks for it." `[pause]`
>
> "That's three thousand seven hundred orders, and the test says p equals
> point-zero-zero-six. But orders inside the same store-day share the same
> weather and the same staffing, so they aren't independent observations. That
> shrinks the real sample and widens the true error bar beyond what the test
> assumes.
>
> The direction is stable. The size is stable. The certainty is capped by the
> design. So: suggestive, not proven."

> **Why you volunteer the caveat:** it is the single highest-credibility move in
> your block. Saying it before you're challenged converts a weakness into
> evidence of rigour. Do not skip it to save time.

### Slide 08 — the finding we killed (1:00)

> "Here's the one we wanted. `[pause]`
>
> At a one-millimetre rain cut-off, rainy days looked almost fourteen percent
> better on revenue, and six of our eight stores agreed. That is a clean-looking
> result.
>
> So we moved the cut-off — which is the test any real effect should survive.
>
> At five millimetres it's plus eight. At ten, plus nineteen. At nought-point-four,
> plus nine and a half. And the number of stores agreeing collapses to four,
> four, and three. `[pause]`
>
> The estimate swings with the line you draw. So it isn't a finding.
>
> There's a second reason. Our rainiest store, S001, has rain on eighty-six
> percent of days — and it's also our highest-earning store. Pooling across
> stores lets that difference impersonate a rain effect.
>
> We dropped the claim rather than report the cut-off that flattered it."

### Slide 08b — we didn't go fishing (1:00)

> "One more thing on discipline. `[pause]`
>
> We ran sixteen tests — eight stores against two weather variables. Exactly one
> came back significant: one store against temperature, at p equals
> point-zero-two-one.
>
> At this sample size, one hit in sixteen is what randomness produces on its own.
> `[pause]`
>
> We're showing you the whole grid, because the alternative is showing you the
> one lit square and calling it a discovery. That's how most weather-sensitivity
> claims get made — and it's why most of them don't replicate."

### Slide 09 — the recommendation (0:30)

> "So what should the business actually do?
>
> Staff and pre-stage pickup capacity when rain is in the forecast. That's the
> one recommendation that depends only on the finding that held — it needs no
> claim about total demand at all. `[pause]`
>
> Concretely: two weeks, on forecast-rain days, move one associate to pickup
> staging at our two rainiest stores. Scale it only if pickup share moves two
> points. Otherwise stop.
>
> It's a reallocation, not a spend. That's what makes it worth doing on a
> suggestive finding."

### Handoff → Burhan (0:15)

> "Everything you've seen has a cost column. Burhan — what we'd fix first."

---

## BLOCK 3 — THE CLOSE (0:15) · slide 11

Burhan hands back with *"Connor closes."*

> "One-point-three-seven million dollars — and we can show where every dollar
> came from. `[pause]` Including the fifty-seven thousand that briefly read as
> zero.
>
> The deliverable isn't the dashboard. It's a process that notices when it's
> wrong. Thank you."

---

## If something goes wrong

| What happens | What you do |
|---|---|
| HTML deck misbehaves | Switch to `deck.pdf`. **Don't apologise or explain** — the PDF holds identical content. Keep talking through the switch. |
| Projector won't take 16:9 | The stage letterboxes; nothing reflows. Present as-is. |
| You lose your place | Look at the slide title. Every title is a complete sentence — say it in your own words, then give its number. |
| Someone asks a question mid-talk | "Great question — I'll hit that in two slides." Then actually hit it. |
| You're running long at slide 08 | Fold 09 into one sentence at the end of 08, drop slide 11, close over Burhan's slide. Saves 0:45. |
| Dashboard is on screen and disagrees | "The board reads live data and uses a slightly different rain definition — the shift holds either way." Move on. Delta card if pressed. |

---

## The numbers you must not fumble

Say these out loud until they're automatic. These five are the ones you'll be
challenged on.

| | |
|---|---|
| Pickup shift | **17.9% → 21.6%, +3.7 points** |
| Significance | **3,721 orders, p = .006 — suggestive, not proven** |
| The killed lift | **+13.9% at 1mm, 6 of 8 stores — collapses to +8.3 / +18.9 / +9.5** |
| The store confound | **S001: 86% rainy days, $6,673 median. S006: 14%, $4,714** |
| The close | **$1,374,672.31** |

---

## The delta card — one sentence, memorised

If anyone compares a slide to live data or a fresh run:

> "The slides are locked to a dated snapshot so they're reproducible. Five
> store-days have since been revised by the weather archive itself — two crossed
> our rain cut-off. The finding holds; the third decimal moved."

Backup detail, only if pushed: pickup is +3.4 today versus +3.7 locked; revenue,
row counts and the entire product mapping are identical in both, and the build
asserts that on every run.

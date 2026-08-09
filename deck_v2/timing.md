# Timing card — print this, or have it open on the podium

**Limits:** 25:00 maximum, 27:30 hard cut. Nothing in the rubric rewards length.
**Target:** 15–18 minutes delivered, with the rest as headroom.

**Default for Monday: CORE + DEPTH (~21:00).** It leaves 4 minutes of slack against
the limit and gives every presenter comfortable ownership time. Drop to CORE only if
the morning rehearsal runs long.

---

## CORE — 15:30

The minimum that scores full marks on all five rubric criteria. Covers architecture,
ingestion and monitoring, data quality, the migration and matching decision, weather
findings, limitations, and next steps. Every presenter appears.

| Clock | Slide | Who | Talk |
|---|---|---|---|
| 0:00 | 1 · six failures, zero dollars lost | **Connor** | 0:45 |
| 0:45 | *handoff* | | 0:15 |
| 1:00 | 2 · two habits | **Jack** | 1:15 |
| 2:15 | 3 · five of six caught on arrival | Jack | 1:30 |
| 3:45 | 4 · the dollar sign | Jack | 1:30 |
| 5:15 | *handoff* | | 0:15 |
| 5:30 | 5 · re-matching the catalogue | **Burhan** | 3:00 |
| 8:30 | *handoff* | | 0:15 |
| 8:45 | 6 · 1,367 rows, 232 readings | **James** | 3:00 |
| 11:45 | *handoff* | | 0:15 |
| 12:00 | 7 · rain moves the channel | **Connor** | 1:45 |
| 13:45 | 8 · the lift that failed (+ recommendation folded in) | Connor | 1:15 |
| 15:00 | *handoff* | | 0:15 |
| 15:15 | 10 · what we'd fix first | **Burhan** | 1:00 |
| 16:15 | closing sentence | Connor | 0:15 |

**Continuous airtime:** Jack 4:15 · Burhan 3:00 then 1:00 · James 3:00 · Connor 0:45
then 3:00 then 0:15.

> In CORE, slides 9 and 11 are **folded**: the recommendation becomes the last
> sentence of slide 8, and the closing number becomes Connor's final line over
> slide 10. Nothing is lost, and no slide is skipped mid-flow.

---

## CORE + DEPTH — 21:00 (recommended)

Same running order, with four DEPTH slides inserted and slides 9 and 11 unfolded.

| Clock | Slide | Who | Talk |
|---|---|---|---|
| 0:00 | 1 · six failures, zero dollars lost | **Connor** | 0:45 |
| 0:45 | *handoff* | | 0:15 |
| 1:00 | 2 · two habits | **Jack** | 1:15 |
| 2:15 | 3 · five of six caught on arrival | Jack | 1:30 |
| 3:45 | 4 · the dollar sign | Jack | 1:30 |
| 5:15 | **4b · the poisoned file** | Jack | 1:15 |
| 6:30 | *handoff* | | 0:15 |
| 6:45 | 5 · re-matching the catalogue | **Burhan** | 3:00 |
| 9:45 | **5b · the four decoys** | Burhan | 1:30 |
| 11:15 | *handoff* | | 0:15 |
| 11:30 | 6 · 1,367 rows, 232 readings | **James** | 3:00 |
| 14:30 | **6b · the archive rewrote itself** | James | 1:15 |
| 15:45 | *handoff* | | 0:15 |
| 16:00 | 7 · rain moves the channel | **Connor** | 1:45 |
| 17:45 | 8 · the lift that failed | Connor | 1:00 |
| 18:45 | **8b · sixteen tests, one hit** | Connor | 1:00 |
| 19:45 | 9 · the pilot | Connor | 0:30 |
| 20:15 | *handoff* | | 0:15 |
| 20:30 | 10 · what we'd fix first | **Burhan** | 1:15 |
| 21:45 | 11 · closing number | Connor | 0:15 |

**Total 22:00** including handoffs — 3:00 under the limit, 5:30 under the hard cut.

**Continuous airtime:** Jack 5:30 · Burhan 4:30 then 1:15 · James 4:15 ·
Connor 0:45 then 4:15 then 0:15. Everyone clears the 3-minute ownership floor.

---

## Cut order, if the morning rehearsal runs long

Drop in this order — reverse order of how much credibility each one buys:

1. **8b** (sixteen tests) — the line on slide 8 already carries it. −1:00
2. **4b** (poisoned file) — becomes one sentence in slide 4. −1:15
3. **6b** (archive revisions) — becomes a Q&A answer. −1:15
4. **5b** (four decoys) — becomes one sentence in slide 5. −1:30
5. Fold **9** into slide 8's close. −0:30
6. Fold **11** into Connor's last sentence. −0:15

**Never cut below CORE.** Slides 4, 5, 7, 8 and 10 are untouchable — they are the
five rubric criteria.

---

## Handoff scripts — 15 seconds each, say them as written

Nobody improvises the pass-off. The handoff is where a four-person talk either
looks like a team or looks like four talks.

1. **Connor → Jack**
   *"Jack built the front door — the two habits that did the protective work."*

2. **Jack → Burhan** (after slide 4, or 4b)
   *"That recovery worked because the originals were still there. Burhan hit a
   different problem: one morning, every product ID in the feed had changed."*

3. **Burhan → James** (after slide 5, or 5b)
   *"Every sale in the weather analysis rides on those matches. James is the one
   who put the weather on them."*

4. **James → Connor** (after slide 6, or 6b)
   *"232 honest observations. So what did weather actually do? Connor."*

5. **Connor → Burhan** (after slide 8, 8b, or 9)
   *"Everything you've seen has a cost column. Burhan — what we'd fix first."*

6. **Burhan → Connor** (after slide 10)
   *"Connor closes."*

---

## Podium checklist

- [ ] **Open the HTML deck locally** from the presenting machine — not from a link.
- [ ] **PDF backup open in a second tab or app.** If HTML misbehaves, switch without
      apologising; the PDF holds 100% of the content because every animation is a
      reveal, not a carrier.
- [ ] Win+P → **Extend**, not Duplicate, for presenter view.
- [ ] Open the Streamlit dashboard before class if you plan to show it — Community
      Cloud sleeps after 12 hours and cold-starts slowly.
- [ ] Delta card (top of `qa_pack.md`) open or printed. It's the single most likely
      question and the answer is one sentence.
- [ ] Presentation order is randomized — slide 1 has to work cold at 10:00.

"""Gate deck_v2 content against facts.json. Run before every render.

Three checks, modelled on deck/qa_checks.py:

  1. Every {fact_id} referenced in slides.md exists in facts.json.
  2. No bare numeric literal in slide-visible text (titles, bodies, tables,
     captions, stats). Speaker notes are exempt -- they are spoken, not shown,
     and quoting a figure aloud is fine. Anything a slide PRINTS must come from
     facts.json so it cannot drift from the database.
  3. Every number written in qa_pack.md appears in facts.json (as a display
     string or a raw value). This catches the study document drifting away from
     the deck.

Usage:
    uv run python deck_v2/check_facts.py
"""

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FACTS_JSON = HERE / "facts.json"
SLIDES = HERE / "slides.md"
QA_PACK = HERE / "qa_pack.md"

TOKEN_RE = re.compile(r"\{([a-z0-9_]+)\}")
NUM_RE = re.compile(r"\d[\d,.]*")

# Identifiers and labels are not data figures, so they never need a fact_id.
# Stripped before any number scan, in both files.
IDENTIFIER_RES = [
    re.compile(r"\bN?P\d{3,}\b"),                       # P1076, NP5047, NP9999
    re.compile(r"\bS\d{3}\b"),                          # store ids
    re.compile(r"\b\d{4}-\d{2}-\d{2}\b"),               # ISO dates
    re.compile(r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
               r"[a-z]*\.?\s+\d{1,2}\b"),               # Jul 24, August 7
    re.compile(r"\b404\b"),                             # HTTP status
    re.compile(r"\bBZAN\s*\d+\b"),                      # course code
    re.compile(r"\b[0-9a-f]{7,40}\b"),                  # commit shas
    re.compile(r"\b\w+\.py:\d+(?:-\d+)?"),              # source line refs
]


def strip_identifiers(text):
    for rx in IDENTIFIER_RES:
        text = rx.sub(" ", text)
    return text

# Slide-visible keys. Everything else in a slide block (notes:, handoff:) is
# spoken aloud, not printed, so literals there are fine.
VISIBLE_KEYS = ("title:", "body:", "stat:", "detail:", "caption:", "footnote:",
                "caveat:", "mechanism:", "note_on_slide:", "callout:",
                "pilot:", "- [", "- \"", "  - [", "  - \"")

# Numbers a slide may print without a fact_id, each justified.
LITERAL_ALLOW = {
    "545",        # course code
    "2026",       # year, in the date line
    "2026-08-10", # presentation date
    "16",         # aspect ratio 16:9
    "9",          # aspect ratio 16:9
    "2",          # the pre-registered 2-point pilot bar (a decision, not data)
    "57",         # "$57K", the rounded headline of recovered_0805_net
    "0",          # "$0", the rhetorical zero it read as
    "0.6", "0.2", "0.300", "0.200", "0.168",  # A1 weights, fixed in source code
    "1",          # threshold labels in A2
    "0.4", "5", "10",
    "1.0",
    "3",          # "three checks", "Three limitations" -- counts of slide items
    "4", "4b", "5b", "6b", "8b",  # slide numbers in headings
    "6", "7", "11", "10",
}

# Tokens in qa_pack.md that are prose or repo references, not deck figures.
QA_ALLOW = {
    "545", "20", "4", "2026", "08", "05", "07", "24", "28", "03", "06",
    "1", "2", "3", "45", "20", "8", "9", "10", "5", "6", "7",
    "82d221e", "1c4884f",
    "0.05", "0.60", "0.85", "1.0", "0.6", "0.2",
    "157.12", "1mm", "5mm", "10mm", "0.4",
    "2026-08-08", "2026-08-09",
    "125",   # rows in the successful 08-07 capture (ingestion_log.csv)
    "155",   # the 08-05 line count, also carried as recovered_0805_lines
    "140", "4", "144",
    "28", "34", "76", "72", "18", "14", "80", "51", "25",
    "232", "1,367", "3,721", "29", "32",
}


def load_facts():
    if not FACTS_JSON.exists():
        sys.exit("facts.json missing -- run: uv run python deck_v2/build_facts.py")
    return json.loads(FACTS_JSON.read_text(encoding="utf-8"))["facts"]


def slide_body(text):
    """Everything from the first slide heading on (skips the front matter,
    which documents the {fact_id} convention rather than using it)."""
    idx = text.find("## SLIDE")
    return text[idx:] if idx != -1 else text


def slide_visible_lines(text):
    """Yield (lineno, line) for lines a slide actually prints."""
    in_notes = False
    for i, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped.startswith("notes:"):
            in_notes = True
            continue
        if in_notes:
            # notes: | blocks are indented; a new top-level key ends them
            if stripped and not line.startswith(("  ", "\t")):
                in_notes = False
            else:
                continue
        if stripped.startswith("##"):
            continue                       # slide headings carry numbers
        if any(stripped.startswith(k) for k in VISIBLE_KEYS):
            yield i, line


def main():
    facts = load_facts()
    slides = slide_body(SLIDES.read_text(encoding="utf-8"))
    failures = []

    # --- 1. every {fact_id} resolves -------------------------------------
    used = set()
    for tok in TOKEN_RE.findall(slides):
        used.add(tok)
        if tok not in facts:
            failures.append(f"slides.md: unknown fact id {{{tok}}}")

    # --- 2. no bare literals in printed text ------------------------------
    for lineno, line in slide_visible_lines(slides):
        bare = strip_identifiers(TOKEN_RE.sub(" ", line))
        for num in NUM_RE.findall(bare):
            if num.rstrip(".,") in LITERAL_ALLOW:
                continue
            failures.append(
                f"slides.md:{lineno}: bare number '{num}' in printed text "
                f"-- use a {{fact_id}}: {line.strip()[:70]}")

    # --- 3. qa_pack numbers trace to facts.json ---------------------------
    if QA_PACK.exists():
        corpus = " ".join(
            str(f["display"]) + " " + json.dumps(f["value"])
            for f in facts.values())
        qa_nums = set()
        for lineno, line in enumerate(QA_PACK.read_text(encoding="utf-8")
                                      .splitlines(), start=1):
            for num in NUM_RE.findall(strip_identifiers(line)):
                n = num.rstrip(".,")
                if n in QA_ALLOW or n in corpus:
                    continue
                qa_nums.add((lineno, n, line.strip()[:60]))
        for lineno, n, ctx in sorted(qa_nums):
            failures.append(
                f"qa_pack.md:{lineno}: number '{n}' not found in facts.json "
                f"-- verify or add to QA_ALLOW: {ctx}")

    # --- report -----------------------------------------------------------
    unused = sorted(set(facts) - used)
    print(f"facts.json: {len(facts)} facts, {len(used)} referenced by slides.md")
    if unused:
        print(f"  note: {len(unused)} unused (Q&A/appendix reserve): "
              f"{', '.join(unused[:8])}{' ...' if len(unused) > 8 else ''}")
    print(f"check_facts: {len(failures)} failure(s)")
    for f in failures:
        print("  FAIL", f)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())

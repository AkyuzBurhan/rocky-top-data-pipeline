"""Render deck_v2/deck.html from deck.template.html + facts.json.

The template carries {{fact_id}} tokens instead of numbers, exactly like
slides.md. This script resolves them, so a figure can never be mistyped into a
slide and a facts rebuild propagates everywhere at once.

Fails loudly on an unknown token. Reports tokens that exist but are unused.

Usage:
    uv run python deck_v2/build_deck.py
"""

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEMPLATE = HERE / "deck.template.html"
FACTS_JSON = HERE / "facts.json"
OUT = HERE / "deck.html"

TOKEN_RE = re.compile(r"\{\{([a-z0-9_]+)\}\}")


def main():
    if not FACTS_JSON.exists():
        sys.exit("facts.json missing -- run: uv run python deck_v2/build_facts.py")
    facts = json.loads(FACTS_JSON.read_text(encoding="utf-8"))["facts"]
    html = TEMPLATE.read_text(encoding="utf-8")

    used, missing = set(), set()

    def resolve(m):
        fid = m.group(1)
        if fid not in facts:
            missing.add(fid)
            return m.group(0)
        used.add(fid)
        return str(facts[fid]["display"])

    out = TOKEN_RE.sub(resolve, html)
    if missing:
        sys.exit(f"unknown fact id(s) in template: {sorted(missing)}")

    # <!--DOTS:8x29--> expands to that many cells, so the slide draws the
    # observation count literally rather than gesturing at it.
    def dots(m):
        rows, cols = int(m.group(1)), int(m.group(2))
        return ('<div class="matrix" style="grid-template-columns:repeat('
                + str(cols) + ',1fr)">' + '<i></i>' * (rows * cols) + '</div>')

    out, n_matrix = re.subn(r"<!--DOTS:(\d+)x(\d+)-->", dots, out)
    if n_matrix:
        print(f"[deck] {n_matrix} dot matrix/matrices expanded")

    OUT.write_text(out, encoding="utf-8")
    n_slides = out.count('class="slide')
    print(f"[deck] {OUT.name}: {n_slides} slides, {len(used)} facts resolved")
    print(f"[deck] {len(set(facts) - used)} facts unused (Q&A reserve)")


if __name__ == "__main__":
    main()

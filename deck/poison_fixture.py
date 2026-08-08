"""
Poison-fixture test for the non-numeric gate (Connor item 24, executed).

Writes a synthetic raw orders CSV with $-prefixed unit_price strings to a
temp path (never data/raw/), runs the real quality gate
(helpers.dq.run_quality_checks) and the real parser
(src.transform._to_float) against it, and captures the result as a log
artifact + PNG for appendix slide A3.

Read-only with respect to the repo: nothing under data/ or rocky_top.db is
touched; the fixture lives in the OS temp directory and the outputs go to
deck/out/fixture/ (gitignored).

Exit codes: 0 = gate fired and parser recovered all values; 2 = gate did
NOT fire (slide 3's "non-numeric gate added" claim would be false - stop).

Usage: python deck/poison_fixture.py
"""

import csv
import json
import subprocess
import sys
import tempfile
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "out" / "fixture"
sys.path.insert(0, str(ROOT))

from helpers import dq                          # noqa: E402
from src.transform import _to_float             # noqa: E402
import pandas as pd                             # noqa: E402

FIXTURE_DATE = "2026-08-08"
HEADER = ["order_id", "order_date", "store_id", "new_product_id", "quantity",
          "unit_price", "discount_pct", "sales_channel", "loyalty_member"]
ROWS = [
    ["TEST-0001", FIXTURE_DATE, "S001", "NP5046", "1", "$19.99", "0", "in_store", "Y"],
    ["TEST-0002", FIXTURE_DATE, "S002", "NP5072", "2", "$157.12", "5", "pickup", "N"],
    ["TEST-0003", FIXTURE_DATE, "S003", "NP5046", "1", "$72.70", "0", "ship_from_store", "Y"],
    ["TEST-0004", FIXTURE_DATE, "S004", "NP5051", "3", "$8.45", "10", "in_store", "N"],
    ["TEST-0005", FIXTURE_DATE, "S005", "NP5060", "1", "$249.00", "0", "pickup", "Y"],
]


def pipeline_code_commit():
    """Short sha of the last commit touching the pipeline code under test."""
    return subprocess.run(
        ["git", "log", "-1", "--format=%h", "--", "src/", "helpers/"],
        cwd=ROOT, capture_output=True, text=True).stdout.strip()


def render_log_png(text, png_path):
    from PIL import Image, ImageDraw, ImageFont
    font_path = (Path.home() / "AppData/Local/Microsoft/Windows/Fonts"
                 / "IBMPlexMono-Regular.ttf")
    scale = 2
    font = ImageFont.truetype(str(font_path), 15 * scale)
    lines = text.splitlines()
    pad = 24 * scale
    line_h = 22 * scale
    width = pad * 2 + int(max(font.getlength(ln) for ln in lines))
    height = pad * 2 + line_h * len(lines)
    img = Image.new("RGB", (width, height), "#F7F6F3")
    drw = ImageDraw.Draw(img)
    for i, ln in enumerate(lines):
        drw.text((pad, pad + i * line_h), ln, font=font, fill="#1A1A1A")
    img.save(png_path)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tmp = Path(tempfile.mkdtemp(prefix="poison_fixture_"))
    fixture = tmp / f"orders_{FIXTURE_DATE}.csv"
    with open(fixture, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(ROWS)

    # reference sets from the committed CSVs, read-only
    stores = set(pd.read_csv(ROOT / "data/reference/stores.csv")["store_id"])
    prods = (set(pd.read_csv(ROOT / "data/reference/products.csv")["product_id"])
             | set(pd.read_csv(ROOT / "data/reference/new_products.csv")["new_product_id"]))

    row = dq.run_quality_checks(fixture, FIXTURE_DATE, stores, prods)
    flags = row["flags"]
    gate_fired = "nonnumeric(unit_price=5" in flags

    raw_prices = [r[5] for r in ROWS]
    parsed = _to_float(pd.Series(raw_prices))
    recovered = int(parsed.notna().sum())
    expected = [19.99, 157.12, 72.70, 8.45, 249.00]
    parse_ok = recovered == 5 and all(
        abs(a - b) < 1e-9 for a, b in zip(parsed.tolist(), expected))

    sha = pipeline_code_commit()
    today = date.today().isoformat()
    log = "\n".join([
        f"poison fixture · executed {today} · pipeline code at commit {sha}",
        f"fixture: {fixture}  (5 rows, every unit_price a $-prefixed string)",
        "",
        ">>> dq.run_quality_checks(fixture, expected_date='2026-08-08')",
        f"    n_rows={row['n_rows']}  na_unit_price={row['na_unit_price']}"
        f"  (isna() sees a healthy file)",
        f"    flags: {flags}",
        "",
        ">>> transform._to_float(raw.unit_price)   # the fixed parser",
        f"    {raw_prices}",
        f"    -> {[round(v, 2) for v in parsed.tolist()]}   ({recovered}/5 recovered)",
        "",
        f"GATE {'FIRED' if gate_fired else '*** DID NOT FIRE ***'}: "
        + ("the file reads clean to null checks but is flagged "
           "nonnumeric(unit_price=5); the parser recovers every value."
           if gate_fired else "the 08-05 failure class would recur silently."),
        "no repo state touched: fixture in OS temp, no writes to data/ or "
        "rocky_top.db",
    ])
    (OUT / "poison_fixture_log.txt").write_text(log, encoding="utf-8")
    render_log_png(log, OUT / "poison_fixture_log.png")
    (OUT / "poison_fixture_meta.json").write_text(json.dumps({
        "date": today, "commit": sha, "flags": flags,
        "gate_fired": gate_fired, "parse_ok": parse_ok,
        "fixture": str(fixture),
    }, indent=2), encoding="utf-8")
    print(log)
    return 0 if (gate_fired and parse_ok) else 2


if __name__ == "__main__":
    sys.exit(main())

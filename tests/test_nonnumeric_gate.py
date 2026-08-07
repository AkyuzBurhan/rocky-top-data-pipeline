"""
Poison-fixture test for the non-numeric price gate in helpers/dq.py.

Reproduces the 2026-08-05 silent-failure class: unit_price arriving as "$72.70"
strings passes the NA check (the value is non-null) but breaks numeric parsing,
so the day's revenue was silently lost. This test proves the new nonnumeric()
flag catches that class of fault.

Run:  uv run python tests/test_nonnumeric_gate.py
  or: uv run pytest tests/test_nonnumeric_gate.py
"""
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from helpers import io, dq, config  # noqa: E402


def _sample_orders_file():
    """First real daily orders file with a usable unit_price column."""
    for f in sorted(config.RAW_DIR.glob("orders_*.csv")):
        df = io.read_orders_csv(f)
        if len(df) > 5 and "unit_price" in df.columns:
            return f
    raise RuntimeError("no suitable orders fixture found in data/raw/")


def test_nonnumeric_gate_catches_dollar_prices(tmp_path=None):
    src = _sample_orders_file()
    expected = io.expected_date_from_filename(src.name)

    # --- control: untouched file must NOT raise the nonnumeric flag ---
    clean = dq.run_quality_checks(src, expected, None, None)
    assert "nonnumeric" not in clean["flags"], f"false positive: {clean['flags']}"

    # --- poison: prefix three unit_price values with "$" ---
    df = io.read_orders_csv(src).copy()
    idx = df.index[:3]
    df.loc[idx, "unit_price"] = ["$" + str(v) for v in df.loc[idx, "unit_price"]]
    out = pathlib.Path(tmp_path or "/tmp") / "orders_poison.csv"
    df.to_csv(out, index=False)
    poison = dq.run_quality_checks(out, expected, None, None)

    # the OLD na_unit_price check is blind: a "$63.94" string is non-null
    assert poison["na_unit_price"] == 0, "NA check unexpectedly caught it"
    # the NEW gate fires with the exact count of poisoned values
    assert "nonnumeric(unit_price=3)" in poison["flags"], poison["flags"]

    print("PASS  control flags:", clean["flags"] or "(none)")
    print("PASS  poison  flags:", poison["flags"], "| na_unit_price =", poison["na_unit_price"])
    print("PASS  the $-string fault is flagged, not silently zeroed.")


if __name__ == "__main__":
    test_nonnumeric_gate_catches_dollar_prices()

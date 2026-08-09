"""Render deck_v2 chart assets from facts.json. No number is typed here.

Every chart reads deck_v2/facts.json, so a chart can never disagree with a
slide. Charts are exported as PNG (2x, transparent) and SVG, in a light and a
dark variant, because the deck theme is chosen in the render session.

Design rules (they match the deck's constraints):
  - direct labels, no legends where a label works
  - no dual axes, no pie charts
  - categorical charts sorted by value; the threshold chart stays in cutoff
    order, because thresholds are a scale and reordering them would hide the
    very instability the slide is about

Usage:
    uv run python deck_v2/make_charts.py
"""

import json
import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                      # noqa: E402
from matplotlib import font_manager                  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ASSETS = HERE / "assets"
FACTS = json.loads((HERE / "facts.json").read_text(encoding="utf-8"))["facts"]

# Palette is the deck's, so charts sit on the bone paper as native elements
# rather than as pasted-in images. Warm greys, one signal colour.
ORANGE = "#FF8200"        # UT Knoxville orange, carried over from the v1 deck
# MUTED_L mirrors the --muted CSS variable in deck.template.html; if one moves,
# move the other or the chart greys drift away from the deck chrome.
MUTED_L, INK_L = "#7A7367", "#16181D"     # warm grey / ink on bone paper
MUTED_D, INK_D = "#7e8695", "#f2f4f8"     # kept for a dark theme if ever needed

THEMES = {"light": (INK_L, MUTED_L), "dark": (INK_D, MUTED_D)}

# Register the bundled IBM Plex Sans so chart type matches the deck body face.
_font_dir = HERE / "assets" / "fonts"
if _font_dir.is_dir():
    for _ttf in _font_dir.glob("*.ttf"):
        font_manager.fontManager.addfont(str(_ttf))
_available = {f.name for f in font_manager.fontManager.ttflist}
FONT = next((f for f in ("IBM Plex Sans", "Segoe UI", "DejaVu Sans")
             if f in _available), "sans-serif")


def val(fid):
    return FACTS[fid]["value"]


def new_fig(w, h, ink):
    fig, ax = plt.subplots(figsize=(w, h))
    fig.patch.set_alpha(0)
    ax.patch.set_alpha(0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=ink, length=0)
    return fig, ax


def save(fig, name, theme):
    ASSETS.mkdir(parents=True, exist_ok=True)
    suffix = "" if theme == "light" else "_dark"
    for ext, dpi in (("png", 200), ("svg", None)):
        fig.savefig(ASSETS / f"{name}{suffix}.{ext}", transparent=True,
                    bbox_inches="tight", pad_inches=0.08,
                    **({"dpi": dpi} if dpi else {}))
    plt.close(fig)
    print(f"  {name}{suffix}.png / .svg")


# --------------------------------------------------------------------------
def chart_timeline(theme):
    """The month as a strip: five failures caught, one that got through."""
    ink, muted = THEMES[theme]
    dates = val("incident_dates")
    labels = {"2026-07-24": "file re-sent", "2026-07-28": "IDs changed",
              "2026-08-03": "empty file", "2026-08-05": "prices as text",
              "2026-08-06": "source gone", "2026-08-07": "columns moved"}
    missed = "2026-08-05"
    start, end = val("window_start"), val("window_end")

    def day(d):
        from datetime import date
        y, m, dd = map(int, d.split("-"))
        y0, m0, d0 = map(int, start.split("-"))
        return (date(y, m, dd) - date(y0, m0, d0)).days

    span = day(end)
    fig, ax = new_fig(12, 3.1, ink)
    ax.plot([0, span], [0, 0], color=muted, lw=1.5, zorder=1, alpha=.5)

    # Incidents cluster in the last week, so caught-labels alternate between
    # two heights and carry leader lines. The missed one drops below the axis,
    # alone, which is the whole point of the chart.
    caught_heights, k = (52, 25), 0
    for d in dates:
        x, is_missed = day(d), d == missed
        ax.scatter([x], [0], s=200, zorder=4, marker="o",
                   facecolor="none" if is_missed else ORANGE,
                   edgecolor=ORANGE, linewidths=2.6)
        if is_missed:
            h, va, col, weight = -46, "top", ink, "bold"
        else:
            h, va, col, weight = caught_heights[k % 2], "bottom", muted, "normal"
            k += 1
        ax.annotate("", (x, 0), xytext=(0, h * 0.95), zorder=2,
                    textcoords="offset points",
                    arrowprops=dict(arrowstyle="-", color=muted,
                                    lw=.9, alpha=.45))
        ax.annotate(f"{labels.get(d, '')}\n{d[5:].replace('-', '/')}",
                    (x, 0), xytext=(0, h), textcoords="offset points",
                    ha="center", va=va, fontsize=10.5, color=col,
                    fontfamily=FONT, fontweight=weight, linespacing=1.45)

    ax.annotate(start[5:].replace("-", "/"), (0, 0), xytext=(-9, 0),
                textcoords="offset points", ha="right", va="center",
                fontsize=9.5, color=muted, fontfamily=FONT)
    # no right-edge date label: the window ends on an incident marker, and a
    # second 08/07 next to it just collides with the one on the leader line
    ax.text(0, 1.02, "caught on arrival", fontsize=11, color=ORANGE,
            fontfamily=FONT, fontweight="bold", ha="left", va="top",
            transform=ax.get_xaxis_transform())
    ax.text(0, -0.02, "found later, by hand", fontsize=11, color=ink,
            fontfamily=FONT, fontweight="bold", ha="left", va="bottom",
            transform=ax.get_xaxis_transform())

    ax.set_xlim(-4, span + 4)
    ax.set_ylim(-1, 1)
    ax.set_yticks([])
    ax.set_xticks([])
    save(fig, "a_timeline", theme)


def chart_channel(theme):
    """How the channel mix MOVES when it rains.

    A dumbbell on a shared 0-70% axis buries the story: the shift is ~3 points
    against an in-store share near 60%, so every row renders as a dot. The
    assertion on the slide is about the CHANGE, so the chart plots the change
    directly -- diverging bars in percentage points, with the underlying
    from/to shares as context on each row.
    """
    ink, muted = THEMES[theme]
    rows = [("In-store", val("mix_instore")),
            ("Pickup", val("mix_pickup")),
            ("Ship from store", val("mix_ship"))]
    rows = [(name, dry, rain, rain - dry) for name, (dry, rain) in rows]
    rows.sort(key=lambda r: r[3], reverse=True)          # sorted by value

    span = max(abs(r[3]) for r in rows)
    fig, ax = new_fig(10, 3.5, ink)
    ax.axvline(0, color=muted, lw=1.4, alpha=.55, zorder=1)

    for i, (name, dry, rain, delta) in enumerate(rows):
        y = len(rows) - i
        hot = name == "Pickup"
        col = ORANGE if hot else muted
        ax.barh(y, delta, height=.44, color=col, alpha=1 if hot else .40,
                zorder=2)
        # channel name in a fixed left gutter, so every row lines up
        ax.text(-span * 1.32, y, name, ha="right", va="center",
                fontsize=12.5, color=ink if hot else muted, fontfamily=FONT,
                fontweight="bold" if hot else "normal")
        side = 1 if delta >= 0 else -1
        ax.text(delta + side * span * .06, y, f"{delta:+.1f} pts",
                ha="left" if side > 0 else "right", va="center",
                fontsize=13 if hot else 11.5, color=ink if hot else muted,
                fontfamily=FONT, fontweight="bold" if hot else "normal")
        ax.text(-span * 1.32, y - .34, f"{dry:.1f}%  →  {rain:.1f}%",
                ha="right", va="center", fontsize=10, color=muted,
                fontfamily=FONT)

    ax.text(0, len(rows) + .74, "  more on rainy days  →", ha="left",
            fontsize=10.5, color=muted, fontfamily=FONT, style="italic")
    ax.text(0, len(rows) + .74, "←  less on rainy days  ", ha="right",
            fontsize=10.5, color=muted, fontfamily=FONT, style="italic")

    ax.set_xlim(-span * 2.35, span * 1.5)
    ax.set_ylim(.35, len(rows) + 1.05)
    ax.set_xticks([])
    ax.set_yticks([])
    save(fig, "a_channel", theme)


def chart_lift(theme):
    """The revenue 'lift' at four cutoffs -- the point is that it swings."""
    ink, muted = THEMES[theme]
    lifts = val("lifts")                     # cutoff order, deliberately
    xs = range(len(lifts))
    fig, ax = new_fig(9.5, 3.8, ink)

    for i, l in zip(xs, lifts):
        headline = l["threshold"] == 1.0
        ax.bar(i, l["lift"], width=.52, zorder=2,
               color=ORANGE if headline else muted,
               alpha=1 if headline else .45)
        ax.text(i, l["lift"] + .9, f"{l['lift']:+.1f}%", ha="center",
                fontsize=12, fontfamily=FONT,
                fontweight="bold" if headline else "normal",
                color=ink if headline else muted)
        ax.text(i, -1.6, f"{l['threshold']:g}mm", ha="center", fontsize=11,
                color=ink if headline else muted, fontfamily=FONT,
                fontweight="bold" if headline else "normal")
        ax.text(i, -3.4, f"{l['agree']} of {l['of']} stores agree",
                ha="center", fontsize=9.5, color=muted, fontfamily=FONT)

    ax.axhline(0, color=muted, lw=1, alpha=.5)
    ax.text(0, max(l["lift"] for l in lifts) + 4.4,
            "same data, four defensible definitions of “a rainy day”",
            fontsize=11, color=muted, fontfamily=FONT, ha="left")
    ax.set_xlim(-.6, len(lifts) - .4)
    ax.set_ylim(-4.6, max(l["lift"] for l in lifts) + 6)
    ax.set_xticks([])
    ax.set_yticks([])
    save(fig, "a_lift", theme)


def chart_scores(theme):
    """Accepted vs rejected match scores -- they overlap, so the cut is a call."""
    ink, muted = THEMES[theme]
    acc = val("cw_scores_accepted")
    rej = val("cw_scores_rejected")
    floor = val("cw_floor")
    lo, hi = val("cw_overlap")

    fig, ax = new_fig(9.5, 3.0, ink)
    ax.axvspan(lo, hi, color=muted, alpha=.30, zorder=1)
    ax.axvline(floor, color=ink, lw=1.5, ls=(0, (4, 3)), zorder=2, alpha=.75)

    ax.scatter(acc, [1] * len(acc), s=95, color=ORANGE, zorder=3, alpha=.85)
    ax.scatter(rej, [0] * len(rej), s=95, facecolor="none",
               edgecolor=muted, linewidths=1.8, zorder=3)

    ax.text(min(acc + rej) - .035, 1, "accepted", ha="right", va="center",
            fontsize=11.5, color=ink, fontfamily=FONT, fontweight="bold")
    ax.text(min(acc + rej) - .035, 0, "rejected", ha="right", va="center",
            fontsize=11.5, color=muted, fontfamily=FONT)
    # label sits left of the line so it never crosses the overlap band
    ax.text(floor - .008, 1.62, f"our cut-off, {floor:.2f}", ha="right",
            va="center", fontsize=10.5, color=ink, fontfamily=FONT)
    ax.text((lo + hi) / 2, -.62, f"they overlap here: {lo:.2f} to {hi:.2f}",
            ha="center", fontsize=10.5, color=ink, fontfamily=FONT)
    # the cut-off label anchors the left end and the overlap caption carries
    # the scale, so axis ticks here would only collide with the dashed line
    ax.set_xlim(min(acc + rej) - .17, max(acc + rej) + .03)
    ax.set_ylim(-.95, 1.95)
    ax.set_yticks([])
    ax.set_xticks([])
    save(fig, "a_scores", theme)


def chart_tests(theme):
    """16 tests, one hit -- what chance produces at this sample size."""
    ink, muted = THEMES[theme]
    rows = val("tests_table")
    fig, ax = new_fig(9.0, 3.2, ink)

    for i, r in enumerate(rows):
        for j, key in enumerate(("p_temp", "p_precip")):
            hit = r[key] < 0.05
            ax.scatter([i], [1 - j], s=560, marker="s", zorder=2,
                       color=ORANGE if hit else muted,
                       alpha=1 if hit else .85)
            if hit:
                ax.annotate(f"p = {r[key]:.3f}", (i, 1 - j), xytext=(0, 26),
                            textcoords="offset points", ha="center",
                            fontsize=11, color=ink, fontfamily=FONT,
                            fontweight="bold")
        ax.text(i, -.75, r["store"], ha="center", fontsize=9.5, color=muted,
                fontfamily=FONT)

    ax.text(-.85, 1, "temperature", ha="right", va="center", fontsize=11,
            color=muted, fontfamily=FONT)
    ax.text(-.85, 0, "rainfall", ha="right", va="center", fontsize=11,
            color=muted, fontfamily=FONT)
    ax.text(len(rows) - .5, 1.85,
            "one square lit, out of sixteen", ha="right", fontsize=11,
            color=ink, fontfamily=FONT)
    ax.set_xlim(-3.0, len(rows) - .3)
    ax.set_ylim(-1.2, 2.1)
    ax.set_xticks([])
    ax.set_yticks([])
    save(fig, "a_tests", theme)


def copy_fixture():
    src = ROOT / "deck" / "out" / "fixture" / "poison_fixture_log.png"
    if src.exists():
        ASSETS.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, ASSETS / "poison_fixture_log.png")
        print("  poison_fixture_log.png (copied from deck/out/fixture/)")


if __name__ == "__main__":
    print(f"[charts] font: {FONT}")
    for theme in THEMES:
        print(f"[charts] {theme}")
        chart_timeline(theme)
        chart_channel(theme)
        chart_lift(theme)
        chart_scores(theme)
        chart_tests(theme)
    copy_fixture()
    print("\n[done] assets in deck_v2/assets/")

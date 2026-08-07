"""
Build a self-contained, designed HTML weather-sensitivity report from the
analytics-ready `daily_sales` table. All values are baked into the HTML (a
snapshot), so the file opens anywhere with no server and no dependencies.

Run:  uv run python dashboard/build_report.py
Output: dashboard/report.html
"""

import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "rocky_top.db"
OUT = ROOT / "dashboard" / "report.html"

CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
               "#e87ba4", "#008300", "#4a3aa7", "#e34948"]
BLUE, GRAY, RED = (42, 120, 214), (238, 241, 244), (227, 73, 72)


def _lerp(a, b, t):
    return tuple(round(a[i] + (b[i] - a[i]) * t) for i in range(3))


def _hex(rgb):
    return "#%02x%02x%02x" % rgb


def div_color(v, vmax=0.6):
    if v is None or pd.isna(v):
        return "#f4f5f7"
    t = max(-1.0, min(1.0, v / vmax))
    rgb = _lerp(GRAY, BLUE, -t) if t < 0 else _lerp(GRAY, RED, t)
    return _hex(rgb)


def _ink(v, vmax=0.6):
    return "#ffffff" if (v is not None and not pd.isna(v) and abs(v) / vmax > 0.55) else "#3a3a38"


def load():
    con = sqlite3.connect(DB_PATH)
    ds = pd.read_sql("SELECT * FROM daily_sales", con)
    con.close()
    return (ds.groupby(["order_date", "store_id", "category"], as_index=False)
            .agg(units_sold=("units_sold", "sum"),
                 net_revenue=("net_revenue", "sum"),
                 gross_revenue=("gross_revenue", "sum"),
                 discount_given=("discount_given", "sum"),
                 temp_max=("temp_max", "mean"),
                 precipitation_sum=("precipitation_sum", "mean")))


def sensitivity(df, wcol, min_days=10):
    rows = []
    for (s, c), sub in df.groupby(["store_id", "category"]):
        sub = sub.dropna(subset=[wcol, "units_sold"])
        if len(sub) < min_days:
            continue
        rows.append({"store_id": s, "category": c,
                     "corr": sub["units_sold"].corr(sub[wcol])})
    return pd.DataFrame(rows)


def heatmap_html(tbl, title, subtitle):
    if tbl.empty:
        return f'<div class="card"><div class="card-h">{title}</div><p class="muted">Not enough data.</p></div>'
    pivot = tbl.pivot(index="category", columns="store_id", values="corr")
    cats = list(pivot.index)
    stores = list(pivot.columns)
    cols = "120px " + " ".join(["1fr"] * len(stores))
    cells = [f'<div class="hm-corner"></div>']
    for s in stores:
        cells.append(f'<div class="hm-col">{s}</div>')
    for cat in cats:
        cells.append(f'<div class="hm-row">{cat}</div>')
        for s in stores:
            v = pivot.loc[cat, s]
            txt = "" if pd.isna(v) else f"{v:+.2f}"
            cells.append(
                f'<div class="hm-cell" style="background:{div_color(v)};color:{_ink(v)}" '
                f'title="{cat} @ {s}: {txt}">{txt}</div>')
    grid = f'<div class="hm" style="grid-template-columns:{cols}">' + "".join(cells) + "</div>"
    legend = ('<div class="hm-legend"><span>cooler / drier</span>'
              '<div class="hm-bar"></div><span>hotter / wetter</span></div>')
    return (f'<div class="card"><div class="card-h">{title}</div>'
            f'<div class="muted small">{subtitle}</div>{grid}{legend}</div>')


def combo_cards(temp_t, precip_t):
    picks = []
    for tbl, kind, driver in [(temp_t, "temp", "temperature"),
                              (precip_t, "precip", "precipitation")]:
        if tbl.empty:
            continue
        for r in tbl.assign(a=tbl["corr"].abs()).sort_values("a", ascending=False).head(2).itertuples():
            picks.append((r, kind, driver))
    picks = sorted(picks, key=lambda x: abs(x[0].corr), reverse=True)[:3]
    out = []
    for r, kind, driver in picks:
        c = _hex(RED) if r.corr > 0 else _hex(BLUE)
        if kind == "temp":
            rec = ("Warm-weather driven — stock up and promote ahead of hot days."
                   if r.corr > 0 else
                   "Cool-weather driven — feature on cold days; ease stock in heat.")
        else:
            rec = ("Rain-driven — keep rain-relevant stock ready; run wet-day promos."
                   if r.corr > 0 else
                   "Dry-day seller — plan promos around clear-weather windows.")
        out.append(
            f'<div class="card combo"><div class="combo-name">{r.category} '
            f'<span class="at">@ {r.store_id}</span></div>'
            f'<div class="combo-corr" style="color:{c}">{r.corr:+.2f}</div>'
            f'<div class="muted small">{driver} correlation</div>'
            f'<div class="combo-rec">{rec}</div></div>')
    return "".join(out)


def revenue_bars(df):
    rev = df.groupby("category", as_index=False)["net_revenue"].sum().sort_values("net_revenue", ascending=False)
    mx = rev["net_revenue"].max()
    cmap = {c: CATEGORICAL[i % len(CATEGORICAL)] for i, c in enumerate(sorted(df["category"].unique()))}
    bars = []
    for r in rev.itertuples():
        w = 100 * r.net_revenue / mx
        bars.append(
            f'<div class="bar-row"><div class="bar-label">{r.category}</div>'
            f'<div class="bar-track"><div class="bar-fill" style="width:{w:.1f}%;background:{cmap[r.category]}"></div></div>'
            f'<div class="bar-val">${r.net_revenue:,.0f}</div></div>')
    return '<div class="card"><div class="card-h">Net revenue by category</div>' + "".join(bars) + "</div>"


def build():
    df = load()
    dates = sorted(df["order_date"].unique())
    dmin, dmax = dates[0], dates[-1]
    dfx = df[df["category"] != "UNKNOWN"]
    temp_t = sensitivity(dfx, "temp_max")
    precip_t = sensitivity(dfx, "precipitation_sum")

    # headline
    headline = "Weather signals are moderate; the strongest combinations are highlighted below."
    if not temp_t.empty:
        s = temp_t.assign(a=temp_t["corr"].abs()).sort_values("a", ascending=False).iloc[0]
        d = "warmer" if s["corr"] > 0 else "cooler"
        headline = (f"Most weather-sensitive: <b>{s['category']}</b> at <b>{s['store_id']}</b> "
                    f"sells more in <b>{d}</b> weather (corr {s['corr']:+.2f}).")

    net = df["net_revenue"].sum()
    gross = df["gross_revenue"].sum()
    disc = df["discount_given"].sum()
    ndays, nstores = df["order_date"].nunique(), df["store_id"].nunique()

    html = TEMPLATE.format(
        dmin=dmin, dmax=dmax, headline=headline,
        net=f"${net:,.0f}", gross=f"${gross:,.0f}", disc=f"${disc:,.0f}",
        coverage=f"{ndays}d × {nstores} stores",
        heat_temp=heatmap_html(temp_t, "Temperature sensitivity",
                               "Correlation of daily units with max temperature, per store × category."),
        heat_precip=heatmap_html(precip_t, "Precipitation sensitivity",
                                 "Correlation of daily units with precipitation, per store × category."),
        combos=combo_cards(temp_t, precip_t),
        bars=revenue_bars(dfx),
    )
    OUT.write_text(html)
    print(f"[report] wrote {OUT}  ({ndays} days, {nstores} stores, {dmin}..{dmax})")


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Rocky Top Outfitters — Weather Sensitivity</title>
<style>
  :root {{
    --bg:#eef0f3; --card:#ffffff; --ink:#0b0b0b; --ink2:#52514e; --muted:#8a8f98;
    --border:#e6e8eb; --accent:#2a78d6;
  }}
  * {{ box-sizing:border-box; }}
  body {{ margin:0; background:var(--bg); color:var(--ink);
    font-family:system-ui,-apple-system,"Segoe UI",sans-serif; -webkit-font-smoothing:antialiased; }}
  .wrap {{ max-width:1180px; margin:0 auto; padding:36px 28px 64px; }}
  .top {{ display:flex; align-items:flex-end; justify-content:space-between; gap:16px; margin-bottom:6px; }}
  h1 {{ font-size:26px; font-weight:800; margin:0; letter-spacing:-0.01em; }}
  .badge {{ font-size:12px; color:var(--ink2); background:var(--card); border:1px solid var(--border);
    border-radius:999px; padding:6px 12px; white-space:nowrap; }}
  .answer {{ font-size:15px; color:var(--ink2); margin:8px 0 24px; }}
  .grid-kpi {{ display:grid; grid-template-columns:repeat(4,1fr); gap:16px; margin-bottom:8px; }}
  .card {{ background:var(--card); border:1px solid var(--border); border-radius:16px;
    padding:18px 20px; box-shadow:0 1px 2px rgba(11,11,11,.04); }}
  .kpi .k-label {{ font-size:11px; text-transform:uppercase; letter-spacing:.07em; color:var(--muted); font-weight:700; }}
  .kpi .k-val {{ font-size:27px; font-weight:800; margin-top:8px; font-variant-numeric:tabular-nums; }}
  .card-h {{ font-size:16px; font-weight:800; margin-bottom:2px; }}
  .muted {{ color:var(--muted); }} .small {{ font-size:12.5px; }}
  .sec {{ font-size:18px; font-weight:800; margin:30px 0 12px; }}
  .grid-2 {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; }}
  .grid-3 {{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; }}
  /* heatmap */
  .hm {{ display:grid; gap:3px; margin-top:14px; }}
  .hm-corner {{ }}
  .hm-col {{ text-align:center; font-size:12px; color:var(--muted); font-weight:600; padding-bottom:2px; }}
  .hm-row {{ font-size:12.5px; color:var(--ink2); display:flex; align-items:center; }}
  .hm-cell {{ aspect-ratio:1.6/1; border-radius:6px; display:flex; align-items:center; justify-content:center;
    font-size:11.5px; font-weight:600; font-variant-numeric:tabular-nums; }}
  .hm-legend {{ display:flex; align-items:center; gap:10px; margin-top:14px; font-size:11.5px; color:var(--muted); }}
  .hm-bar {{ flex:0 0 160px; height:10px; border-radius:6px;
    background:linear-gradient(90deg,#2a78d6, #eef1f4, #e34948); }}
  /* combos */
  .combo-name {{ font-size:15px; font-weight:700; }} .at {{ color:var(--muted); font-weight:600; }}
  .combo-corr {{ font-size:26px; font-weight:800; margin:6px 0 2px; font-variant-numeric:tabular-nums; }}
  .combo-rec {{ color:var(--ink2); font-size:13px; line-height:1.4; margin-top:8px; }}
  /* bars */
  .bar-row {{ display:grid; grid-template-columns:110px 1fr 96px; align-items:center; gap:12px; margin:10px 0; }}
  .bar-label {{ font-size:13px; color:var(--ink2); }}
  .bar-track {{ background:#f1f2f4; border-radius:8px; height:16px; overflow:hidden; }}
  .bar-fill {{ height:100%; border-radius:8px; }}
  .bar-val {{ text-align:right; font-size:13px; font-weight:600; font-variant-numeric:tabular-nums; }}
  .foot {{ color:var(--muted); font-size:12px; margin-top:26px; line-height:1.5; }}
  @media (max-width:820px) {{ .grid-kpi,.grid-2,.grid-3 {{ grid-template-columns:1fr; }} }}
</style></head>
<body><div class="wrap">
  <div class="top">
    <div><h1>Rocky Top Outfitters</h1>
    <div class="muted small" style="margin-top:4px">Weather-Sensitivity Report</div></div>
    <div class="badge">Data {dmin} → {dmax}</div>
  </div>
  <div class="answer">{headline}</div>

  <div class="grid-kpi">
    <div class="card kpi"><div class="k-label">Net revenue</div><div class="k-val">{net}</div></div>
    <div class="card kpi"><div class="k-label">Gross (list) revenue</div><div class="k-val">{gross}</div></div>
    <div class="card kpi"><div class="k-label">Discount given</div><div class="k-val">{disc}</div></div>
    <div class="card kpi"><div class="k-label">Coverage</div><div class="k-val">{coverage}</div></div>
  </div>

  <div class="sec">Weather sensitivity</div>
  <div class="grid-2">{heat_temp}{heat_precip}</div>

  <div class="sec">Top weather-sensitive combinations</div>
  <div class="grid-3">{combos}</div>

  <div class="sec">Revenue</div>
  {bars}

  <div class="foot">Weather sensitivity = Pearson correlation between a store-category's daily units
  sold and that store's daily weather. Correlations are moderate over ~28 days — treat them as
  directional signals to test, not guarantees. UNKNOWN (orphan / discontinued products) is excluded
  from the analysis. Source: <code>daily_sales</code> in rocky_top.db.</div>
</div></body></html>"""


if __name__ == "__main__":
    build()

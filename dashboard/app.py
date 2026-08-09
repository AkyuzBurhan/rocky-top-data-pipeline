"""
Rocky Top Outfitters — Weather-Sensitivity KPI Board (Streamlit, dark tile grid).

Business question:
    Which stores and product categories are most weather-sensitive, and what
    inventory / promotion recommendations follow?

Layout (Geckoboard-style dark board, interactive):
    Filters (store / category / date) at the top — every tile reacts.
    Row 1 : Net revenue (+sparkline) · Units sold (+sparkline) ·
            Kept-after-discount % · Weather sensitivity by category (table)
    Row 2 : Revenue by store · Revenue by category (bar list) ·
            Avg order value (gauge) · Top products

Reads live from rocky_top.db (clean_orders, daily_sales, products, new_products).

Run:  uv run streamlit run dashboard/app.py
"""

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# --- dark board palette ---------------------------------------------------
BG, TILE, BORDER = "#0f1424", "#1b2138", "#2a3350"
INK, MUTED = "#ffffff", "#8b93a7"
BLUE, GREEN, RED, YELLOW = "#4aa3ff", "#46d17f", "#f2645a", "#f2c14e"
WARM = "#f2864b"  # heat / warm-weather (orange)
CAT_COLORS = ["#4aa3ff", "#f2645a", "#46d17f", "#f2c14e", "#e87ba4", "#9085e9"]

DB_PATH = Path(__file__).resolve().parent.parent / "rocky_top.db"

CAT_ORDER = ["patio", "camping", "apparel", "footwear", "drinkware", "preparedness"]
CAT_COLOR = {c: CAT_COLORS[i % len(CAT_COLORS)] for i, c in enumerate(CAT_ORDER)}
CATEGORY_TO_DEPARTMENT = {
    "camping": "camping", "emergency": "preparedness", "footwear": "footwear",
    "hydration": "drinkware", "outerwear": "apparel", "patio": "patio",
}

st.set_page_config(page_title="Rocky Top Outfitters — KPI Board",
                   layout="wide", initial_sidebar_state="collapsed")

st.markdown(f"""
<style>
#MainMenu, footer, header {{visibility: hidden;}}
.stApp {{background: {BG};}}
.block-container {{padding: 1.1rem 1.4rem 2rem; max-width: 1500px;}}
html, body, [class*="css"] {{font-family: system-ui, -apple-system, "Segoe UI", sans-serif;}}

/* bordered containers become dark tiles */
div[data-testid="stVerticalBlockBorderWrapper"] {{
    background: {TILE}; border: 1px solid {BORDER} !important;
    border-radius: 14px; padding: 6px 4px;
}}
div[data-testid="stVerticalBlockBorderWrapper"]:hover {{ border-color: #3a4569 !important; }}

.tl {{font-size:14px; font-weight:700; color:{INK}; letter-spacing:.01em; margin:2px 2px 8px;}}
.big {{font-size:40px; font-weight:800; color:{INK}; line-height:1.0; margin:2px 2px 0;
      font-variant-numeric:tabular-nums;}}
.big .u {{font-size:22px; color:{MUTED}; font-weight:700;}}
.sub {{font-size:13px; color:{MUTED}; margin:2px 2px 0;}}
.delta {{font-size:13px; font-weight:700; margin:6px 2px 0;}}
.up {{color:{GREEN};}} .down {{color:{RED};}}

.lrow {{display:flex; justify-content:space-between; align-items:center;
       padding:7px 2px; border-bottom:1px solid #232b45; font-size:14px;}}
.lrow:last-child {{border-bottom:none;}}
.lrow .k {{color:#c7cde0;}} .lrow .v {{color:{INK}; font-weight:700; font-variant-numeric:tabular-nums;}}

.brow {{margin:9px 2px;}}
.brow .top {{display:flex; justify-content:space-between; font-size:14px; margin-bottom:5px;}}
.brow .top .k {{color:#c7cde0; font-weight:600;}} .brow .top .v {{color:{INK}; font-weight:700;}}
.bar {{height:7px; border-radius:4px; background:#232b45;}}
.bar > span {{display:block; height:7px; border-radius:4px;}}

.trow {{display:flex; justify-content:space-between; align-items:center;
       padding:7px 2px; border-bottom:1px solid #232b45; font-size:14px;}}
.trow:last-child {{border-bottom:none;}}
.trow .k {{color:#c7cde0;}}
.pill {{font-weight:800; font-variant-numeric:tabular-nums; padding:1px 8px; border-radius:6px;}}

div[data-testid="stMetricValue"]{{color:{INK};}}
</style>
""", unsafe_allow_html=True)


# --------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def load_data():
    con = sqlite3.connect(str(DB_PATH))
    daily = pd.read_sql("SELECT * FROM daily_sales", con, parse_dates=["order_date"])
    prod = pd.read_sql("""
        SELECT o.order_date, o.store_id, o.product_key, o.legacy_product_id,
               o.quantity, o.unit_price, o.discount_pct, o.line_revenue,
               o.sales_channel,
               np.item_name AS np_name, np.department AS np_dept,
               p.product_name AS p_name, p.category AS p_cat
        FROM clean_orders o
        LEFT JOIN new_products np ON o.product_key      = np.new_product_id
        LEFT JOIN products     p  ON o.legacy_product_id = p.product_id
    """, con, parse_dates=["order_date"])
    con.close()
    prod["product_name"] = prod["np_name"].fillna(prod["p_name"]).fillna(prod["product_key"])
    prod["category"] = (prod["np_dept"]
                        .fillna(prod["p_cat"].map(CATEGORY_TO_DEPARTMENT))
                        .fillna("UNKNOWN"))
    prod["net_revenue"] = prod["line_revenue"]
    prod["gross_revenue"] = prod["quantity"] * prod["unit_price"] / (1 - prod["discount_pct"] / 100.0)
    prod["discount_given"] = prod["gross_revenue"] - prod["net_revenue"]
    # attach each order's store-day precipitation (same for all categories that
    # store-day) so the channel-vs-rain analysis can run on order-level rows
    precip = (daily.groupby(["order_date", "store_id"], as_index=False)["precipitation_sum"]
              .first())
    prod = prod.merge(precip, on=["order_date", "store_id"], how="left")
    return daily, prod


daily_all, prod_all = load_data()
daily_all = daily_all[daily_all["category"] != "UNKNOWN"].copy()
prod_all = prod_all[prod_all["category"] != "UNKNOWN"].copy()

ALL_STORES = sorted(daily_all["store_id"].unique().tolist())
ALL_CATS = [c for c in CAT_ORDER if c in daily_all["category"].unique()]
DMIN, DMAX = daily_all["order_date"].min().date(), daily_all["order_date"].max().date()


def money(x, k=False):
    if k and abs(x) >= 1000:
        return f"${x/1000:,.1f}K"
    return f"${x:,.0f}"


# --- header + filters ------------------------------------------------------
hc1, hc2 = st.columns([2.4, 1])
with hc1:
    st.markdown(f'<div style="font-size:22px;font-weight:800;color:{INK};margin-bottom:2px;">'
                '🏔️ Rocky Top Outfitters — Weather Sensitivity Board</div>'
                f'<div style="font-size:13px;color:{MUTED};">Which stores &amp; categories are '
                'most weather-sensitive — and what to stock and promote because of it.</div>',
                unsafe_allow_html=True)

f1, f2, f3 = st.columns([1.1, 1.3, 1.1])
with f1:
    sel_stores = st.multiselect("Stores", ALL_STORES, default=ALL_STORES, placeholder="All stores")
with f2:
    sel_cats = st.multiselect("Categories", ALL_CATS, default=ALL_CATS, placeholder="All categories")
with f3:
    sel_dates = st.date_input("Date range", value=(DMIN, DMAX), min_value=DMIN, max_value=DMAX)

sel_stores = sel_stores or ALL_STORES
sel_cats = sel_cats or ALL_CATS
if isinstance(sel_dates, (list, tuple)) and len(sel_dates) == 2:
    d0, d1 = pd.Timestamp(sel_dates[0]), pd.Timestamp(sel_dates[1])
else:
    d0, d1 = pd.Timestamp(DMIN), pd.Timestamp(DMAX)


def flt(df):
    return df[df["store_id"].isin(sel_stores) & df["category"].isin(sel_cats)
             & df["order_date"].between(d0, d1)].copy()


daily, prod = flt(daily_all), flt(prod_all)
if daily.empty:
    st.warning("No data for this selection — widen the filters above.")
    st.stop()

# --- derived metrics -------------------------------------------------------
net = daily["net_revenue"].sum()
gross = daily["gross_revenue"].sum()
disc = daily["discount_given"].sum()
units = int(daily["units_sold"].sum())
n_orders = len(prod)
kept_pct = net / gross * 100 if gross else 0
aov = net / n_orders if n_orders else 0


def pct(a, b):
    """Percent string, or an em dash when the denominator is zero (avoids nan%)."""
    return f"{a / b * 100:.1f}%" if b else "—"


daily_by_day = daily.groupby("order_date").agg(
    net=("net_revenue", "sum"), units=("units_sold", "sum")).reset_index()
last_day = daily_by_day["order_date"].max()
prev_day = last_day - pd.Timedelta(days=7)
net_today = daily_by_day.loc[daily_by_day["order_date"] == last_day, "net"].sum()
net_prev = daily_by_day.loc[daily_by_day["order_date"] == prev_day, "net"].sum()
units_today = int(daily_by_day.loc[daily_by_day["order_date"] == last_day, "units"].sum())
units_prev = int(daily_by_day.loc[daily_by_day["order_date"] == prev_day, "units"].sum())

# window label + zero-revenue anomaly detection (units sold but $0 net -> the
# 2026-08-05 source-formatting class of issue). Dynamic, so it fires only if a
# malformed day actually slips through -- not hardcoded to one date.
win_min = daily_by_day["order_date"].min().strftime("%b %d")
win_max = daily_by_day["order_date"].max().strftime("%b %d")
n_win_days = daily_by_day["order_date"].nunique()
anomaly_days = daily_by_day.loc[
    (daily_by_day["units"] > 0) & (daily_by_day["net"] == 0), "order_date"]


def spark(x, y, color):
    fig = go.Figure(go.Scatter(x=x, y=y, mode="lines", line=dict(color=color, width=2.5),
                               fill="tozeroy", fillcolor=color.replace(")", ",0.13)").replace("rgb", "rgba")
                               if color.startswith("rgb") else "rgba(74,163,255,0.13)",
                               hovertemplate="%{x|%b %d}<br>%{y:,.0f}<extra></extra>"))
    fig.update_layout(height=150, margin=dict(l=0, r=0, t=10, b=0),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      xaxis=dict(visible=False), yaxis=dict(visible=False), showlegend=False)
    return fig


def delta_html(cur, prev, fmt):
    d = cur - prev
    cls = "up" if d >= 0 else "down"
    arrow = "▲" if d >= 0 else "▼"
    return f'<div class="delta {cls}">{arrow} {fmt(abs(d))} vs same day last week</div>'


# --- window label + zero-revenue banner (above both tabs) ------------------
st.markdown(f'<div style="font-size:12.5px;color:{MUTED};margin:2px 2px 8px;">'
            f'Showing <b style="color:#c7cde0;">{win_min} → {win_max}</b> · '
            f'{n_win_days} days · {len(sel_stores)} stores · {len(sel_cats)} categories '
            '<span style="color:#6b7183;">(window grows as the daily pipeline adds days)</span>'
            '</div>', unsafe_allow_html=True)

if len(anomaly_days):
    days_str = ", ".join(pd.to_datetime(anomaly_days).dt.strftime("%Y-%m-%d"))
    st.markdown(
        f'<div style="background:rgba(242,193,78,0.10);border:1px solid rgba(242,193,78,0.35);'
        f'border-radius:10px;padding:10px 14px;font-size:13px;color:#f2c14e;margin:0 2px 12px;">'
        f'⚠️ <b>{days_str}</b> shows $0 net revenue with positive units — a source-side price '
        f'formatting issue (non-numeric price strings), not a real zero. The pipeline recovers '
        f'these from the preserved raw layer; a lingering $0 means the DB predates that rebuild. '
        f'See <code>docs/DECISIONS.md</code> → “Verified revenue figures”.</div>',
        unsafe_allow_html=True)

# ==========================================================================
# TABS
# ==========================================================================
tab_board, tab_weather = st.tabs(["📊  Board", "🌦️  Weather deep-dive"])

# ==========================================================================
# TAB 1 — BOARD
# ==========================================================================
board = tab_board.container()

# ---- ROW 1 ----
r1 = board.columns(4, gap="small")

with r1[0]:
    with st.container(border=True):
        st.markdown('<div class="tl">Total net revenue</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="big">{money(net, k=True)}</div>'
                    f'<div class="sub">{daily["order_date"].nunique()} selling days · '
                    f'{last_day.strftime("%b %d")} latest</div>'
                    + delta_html(net_today, net_prev, lambda v: money(v)),
                    unsafe_allow_html=True)
        st.plotly_chart(spark(daily_by_day["order_date"], daily_by_day["net"], BLUE),
                        use_container_width=True, config={"displayModeBar": False})

with r1[1]:
    with st.container(border=True):
        st.markdown('<div class="tl">Units sold</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="big">{units:,}</div>'
                    f'<div class="sub">{n_orders:,} order lines</div>'
                    + delta_html(units_today, units_prev, lambda v: f"{int(v)}"),
                    unsafe_allow_html=True)
        st.plotly_chart(spark(daily_by_day["order_date"], daily_by_day["units"], GREEN),
                        use_container_width=True, config={"displayModeBar": False})

with r1[2]:
    with st.container(border=True):
        st.markdown('<div class="tl">Revenue kept after discounts</div>', unsafe_allow_html=True)
        kept_disp = (f'{kept_pct:.1f}<span class="u">%</span>' if gross
                     else '<span class="u">n/a</span>')
        st.markdown(f'<div class="big">{kept_disp}</div>'
                    f'<div class="sub">net {money(net, k=True)} of gross {money(gross, k=True)}</div>',
                    unsafe_allow_html=True)
        st.markdown(f'<div class="tl" style="margin-top:14px;">Discount given</div>'
                    f'<div class="big" style="font-size:30px;">{money(disc, k=True)}</div>'
                    f'<div class="sub">{pct(disc, gross)} of gross revenue</div>',
                    unsafe_allow_html=True)

with r1[3]:
    with st.container(border=True):
        st.markdown('<div class="tl">Weather sensitivity by category</div>', unsafe_allow_html=True)
        rows = []
        n_obs = 0
        for c in sel_cats:
            sub = (daily[daily["category"] == c]
                   .groupby(["order_date", "store_id"], as_index=False)
                   .agg(rev=("net_revenue", "sum"), w=("temp_max", "mean")))
            if len(sub) >= 3 and sub["w"].nunique() > 1 and sub["rev"].nunique() > 1:
                rows.append((c, sub["rev"].corr(sub["w"])))
                n_obs = max(n_obs, len(sub))
        rows.sort(key=lambda t: t[1], reverse=True)
        html = ""
        for c, r in rows:
            col = WARM if r >= 0.1 else (BLUE if r <= -0.1 else MUTED)
            bg = "rgba(242,134,75,0.16)" if r >= 0.1 else ("rgba(74,163,255,0.16)" if r <= -0.1 else "rgba(139,147,167,0.12)")
            tag = "warm-driven" if r >= 0.1 else ("cool-driven" if r <= -0.1 else "neutral")
            html += (f'<div class="trow"><span class="k">{c}<br>'
                     f'<span style="font-size:11px;color:{MUTED};">{tag}</span></span>'
                     f'<span class="pill" style="color:{col};background:{bg};">{r:+.2f}</span></div>')
        st.markdown(html, unsafe_allow_html=True)
        st.markdown(f'<div class="sub" style="margin-top:6px;">r = corr(store-day revenue, max temp) · n≈{n_obs}</div>',
                    unsafe_allow_html=True)

# ---- ROW 2 ----
r2 = board.columns(4, gap="small")

with r2[0]:
    with st.container(border=True):
        st.markdown('<div class="tl">Revenue by store</div>', unsafe_allow_html=True)
        byst = daily.groupby("store_id")["net_revenue"].sum().sort_values(ascending=False)
        html = "".join(f'<div class="lrow"><span class="k">{s}</span>'
                       f'<span class="v">{money(v, k=True)}</span></div>'
                       for s, v in byst.items())
        st.markdown(html, unsafe_allow_html=True)

with r2[1]:
    with st.container(border=True):
        st.markdown('<div class="tl">Revenue by category</div>', unsafe_allow_html=True)
        bycat = daily.groupby("category")["net_revenue"].sum().sort_values(ascending=False)
        mx = bycat.max()
        html = ""
        for c, v in bycat.items():
            w = v / mx * 100 if mx else 0
            html += (f'<div class="brow"><div class="top"><span class="k">{c}</span>'
                     f'<span class="v">{money(v, k=True)}</span></div>'
                     f'<div class="bar"><span style="width:{w:.0f}%;background:{CAT_COLOR.get(c, BLUE)};"></span></div></div>')
        st.markdown(html, unsafe_allow_html=True)

with r2[2]:
    with st.container(border=True):
        st.markdown('<div class="tl">Avg order value</div>', unsafe_allow_html=True)
        gmax = max(80, (aov // 20 + 1) * 20)
        fig = go.Figure(go.Indicator(
            mode="gauge+number", value=aov,
            number={"prefix": "$", "font": {"size": 34, "color": INK}},
            gauge={
                "axis": {"range": [0, gmax], "tickcolor": MUTED, "tickwidth": 1},
                "bar": {"color": GREEN, "thickness": 0.28},
                "bgcolor": "rgba(0,0,0,0)", "borderwidth": 0,
                "steps": [{"range": [0, gmax * 0.45], "color": "#232b45"},
                          {"range": [gmax * 0.45, gmax], "color": "#2c3760"}],
            }))
        fig.update_layout(height=200, margin=dict(l=14, r=14, t=6, b=0),
                          paper_bgcolor="rgba(0,0,0,0)", font=dict(color=MUTED))
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        st.markdown(f'<div class="sub" style="text-align:center;margin-top:-8px;">'
                    f'{n_orders:,} orders · {money(net, k=True)} net</div>', unsafe_allow_html=True)

with r2[3]:
    with st.container(border=True):
        st.markdown('<div class="tl">Top products by revenue</div>', unsafe_allow_html=True)
        topp = (prod.groupby("product_name")["net_revenue"].sum()
                .sort_values(ascending=False).head(6))
        html = "".join(
            f'<div class="lrow"><span class="k" style="max-width:70%;overflow:hidden;'
            f'text-overflow:ellipsis;white-space:nowrap;">{name}</span>'
            f'<span class="v">{money(v, k=True)}</span></div>'
            for name, v in topp.items())
        st.markdown(html, unsafe_allow_html=True)


# ==========================================================================
# TAB 2 — WEATHER DEEP-DIVE
# ==========================================================================
def corr_table(weather_col, value_col):
    """Per-category Pearson correlation between a measure (net revenue OR units
    sold) and a weather variable, at STORE-DAY grain: one observation per
    (store, day), so each observation has its own local temperature and the
    weather value is not repeated across categories. Aggregating instead to
    chain-day (averaging stores) smooths noise and inflates r on a tiny n=~28;
    store-day gives the honest, higher-n estimate. Sorted most-positive first."""
    out = []
    for c in sel_cats:
        sub = (daily[daily["category"] == c]
               .groupby(["order_date", "store_id"], as_index=False)
               .agg(val=(value_col, "sum"), w=(weather_col, "mean")))
        if len(sub) >= 3 and sub["w"].nunique() > 1 and sub["val"].nunique() > 1:
            out.append({"category": c, "r": sub["val"].corr(sub["w"]), "n": len(sub)})
    return pd.DataFrame(out).sort_values("r", ascending=False) if out else pd.DataFrame()


def corr_bar(df, title, pos_label, neg_label, pos_color, neg_color):
    d = df.sort_values("r")
    colors = [pos_color if v >= 0 else neg_color for v in d["r"]]
    fig = go.Figure(go.Bar(
        x=d["r"], y=d["category"], orientation="h", marker_color=colors,
        text=[f"{v:+.2f}" for v in d["r"]], textposition="outside",
        textfont=dict(color=INK),
        hovertemplate="%{y}: r = %{x:+.2f}<extra></extra>"))
    fig.update_layout(
        title=dict(text=title, font=dict(size=14, color=INK), x=0, y=0.97),
        height=300, margin=dict(l=6, r=24, t=42, b=34),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(range=[-1, 1], zeroline=True, zerolinecolor="#3a4569",
                   gridcolor="#232b45", color=MUTED, tickformat="+.1f"),
        yaxis=dict(color=INK), font=dict(color=MUTED, size=12))
    fig.add_annotation(x=0.62, y=-0.16, xref="x", yref="paper", showarrow=False,
                       text=pos_label, font=dict(size=11, color=pos_color))
    fig.add_annotation(x=-0.62, y=-0.16, xref="x", yref="paper", showarrow=False,
                       text=neg_label, font=dict(size=11, color=neg_color))
    return fig


def recommend(cat, tr, pr):
    """Turn a category's temperature & precipitation correlations (store-day
    grain) into a stock / promotion note. Signals at this grain are modest, so
    the bar is 0.10 (not 0.15) and the language is deliberately hedged — these
    are directional tilts worth testing, not strong effects."""
    T, P = 0.10, 0.10
    temp_txt, precip_txt, tag, tag_col = "", "", "weather-neutral", MUTED
    if tr >= T:
        temp_txt = ("leans <b>warm</b> — a modest tilt toward selling more on hot "
                    "days; worth testing a pre-heat stock/promo, but expect small effects.")
        tag, tag_col = "leans warm", WARM
    elif tr <= -T:
        temp_txt = ("leans <b>cool</b> — a modest tilt toward selling more on cooler "
                    "days; worth testing a cool-spell hold/promo, but expect small effects.")
        tag, tag_col = "leans cool", BLUE
    if pr >= P:
        precip_txt = " Rain nudges it up slightly too."
        if tag == "weather-neutral":
            tag, tag_col = "leans wet", BLUE
    elif pr <= -P:
        precip_txt = " It dips a little in the rain."
        if tag == "weather-neutral":
            tag, tag_col = "leans dry", YELLOW
    if not temp_txt and not precip_txt:
        body = ("no meaningful weather signal in this window — treat demand as a "
                "steady baseline; weather is not a useful lever here.")
    else:
        body = (temp_txt or f"is flat to temperature (r={tr:+.2f}).") + precip_txt
    return tag, tag_col, body


with tab_weather:
    st.markdown(f'<div style="font-size:18px;font-weight:800;color:{INK};margin:4px 0 2px;">'
                'Does weather drive our sales — and what should we do about it?</div>',
                unsafe_allow_html=True)

    # ======================================================================
    # HEADLINE (robust): channel mix shifts with rain
    # ======================================================================
    CH_NAMES = {"pickup": "Pickup", "in_store": "In-store",
                "ship_from_store": "Ship-from-store"}
    RAIN_MM = 1.0
    pc = prod.dropna(subset=["precipitation_sum"]).copy()
    pc["rain"] = pc["precipitation_sum"] >= RAIN_MM
    sd_rain = pc.groupby(["order_date", "store_id"])["rain"].max()
    n_rain, n_dry = int(sd_rain.sum()), int((~sd_rain).sum())

    def _rain_lift(mm):
        """Mean store-day net revenue lift on rain vs dry days at threshold mm,
        and how many stores agree (rain>dry). Used to show the revenue signal is
        threshold-fragile."""
        s = pc.assign(r=pc["precipitation_sum"] >= mm)
        sd = s.groupby(["order_date", "store_id"], as_index=False).agg(
            rev=("net_revenue", "sum"), r=("r", "max"))
        if sd["r"].nunique() < 2:
            return None
        dry, rn = sd.loc[~sd.r, "rev"].mean(), sd.loc[sd.r, "rev"].mean()
        agree = sum(1 for st_ in sd.store_id.unique()
                    if sd[(sd.store_id == st_) & sd.r]["rev"].mean()
                    > sd[(sd.store_id == st_) & ~sd.r]["rev"].mean())
        return (rn / dry - 1) * 100, agree, sd.store_id.nunique()

    with st.container(border=True):
        st.markdown(
            f'<div style="font-size:16px;font-weight:800;color:{INK};margin:2px 0 2px;">'
            f'The robust finding: on rainy days, customers shift to '
            f'<span style="color:{GREEN};">pickup</span></div>'
            f'<div style="font-size:12.5px;color:{MUTED};margin-bottom:8px;">Order channel mix on '
            f'dry vs rainy store-days (rain ≥ {RAIN_MM:g}mm; {n_rain} rain vs {n_dry} dry store-days '
            'in this selection). Unlike the revenue correlation below, the direction of this shift '
            'holds at every rain cutoff tested (0.5–10&nbsp;mm); significance does not survive past '
            '5mm (p = .10 at 5mm, p = .46 at 10mm).</div>', unsafe_allow_html=True)
        if sd_rain.nunique() == 2 and pc["sales_channel"].notna().any():
            sh = (pc.groupby("rain")["sales_channel"].value_counts(normalize=True).unstack() * 100)
            html = ""
            for ch in [c for c in ["pickup", "in_store", "ship_from_store"] if c in sh.columns]:
                dry, rain = sh.loc[False, ch], sh.loc[True, ch]
                delta = rain - dry
                hi = ch == "pickup"
                dcol = GREEN if delta > 0 else (RED if delta < 0 else MUTED)
                html += (
                    f'<div style="display:flex;align-items:center;gap:14px;margin:8px 2px;">'
                    f'<span style="width:135px;font-size:14px;color:{"#ffffff" if hi else "#c7cde0"};'
                    f'font-weight:{"800" if hi else "600"};">{CH_NAMES.get(ch, ch)}</span>'
                    f'<span style="font-size:14px;color:{MUTED};font-variant-numeric:tabular-nums;">'
                    f'{dry:.1f}% <span style="color:#4b5468;">→</span> '
                    f'<b style="color:{INK};">{rain:.1f}%</b></span>'
                    f'<span style="font-size:13px;font-weight:700;color:{dcol};'
                    f'font-variant-numeric:tabular-nums;">{delta:+.1f} pts</span></div>')
            st.markdown(html, unsafe_allow_html=True)
            st.markdown(f'<div style="font-size:12.5px;color:#c7cde0;margin-top:6px;">'
                        '<b>So what:</b> staff and pre-stage <b>pickup</b> capacity when rain is in '
                        'the forecast; the demand doesn’t vanish in the rain, it moves channels.</div>',
                        unsafe_allow_html=True)
        else:
            st.info("This selection has no dry/rain contrast to compare channels.")

    # ======================================================================
    # SECONDARY (honest): revenue / units correlation — weak & fragile
    # ======================================================================
    st.markdown(f'<div style="font-size:16px;font-weight:800;color:{INK};margin:16px 0 2px;">'
                'Revenue / units vs weather — weak, and it fails a sensitivity check</div>',
                unsafe_allow_html=True)

    l1, l10 = _rain_lift(1.0), _rain_lift(10.0)
    if l1 and l10:
        st.markdown(
            f'<div style="background:rgba(242,193,78,0.08);border:1px solid rgba(242,193,78,0.30);'
            f'border-radius:8px;padding:8px 12px;font-size:12.5px;color:#d9c07a;margin-bottom:8px;">'
            f'⚠️ Why this is <b>not</b> our headline: the rain revenue “lift” swings '
            f'<b style="color:{INK};">{l1[0]:+.0f}%</b> at ≥1&nbsp;mm to '
            f'<b style="color:{INK};">{l10[0]:+.0f}%</b> at ≥10&nbsp;mm, and stores agreeing drops '
            f'<b style="color:{INK};">{l1[1]}/{l1[2]} → {l10[1]}/{l10[2]}</b>. A result that flips '
            'with the threshold is not a reliable finding.</div>', unsafe_allow_html=True)

    measure_label = st.radio(
        "Correlate weather with", ["Net revenue", "Units sold"],
        horizontal=True, index=0,
        help="Net revenue = business impact, but it mixes in product price — a few "
             "high-priced sales can inflate it. Units sold = price-neutral demand "
             "signal, fairer across cheap vs expensive categories. Compare both.")
    value_col = "net_revenue" if measure_label == "Net revenue" else "units_sold"

    st.markdown(f'<div style="font-size:13px;color:{MUTED};margin:2px 0 6px;">Correlation (r) '
                f'between each category’s <b style="color:#c7cde0;">{measure_label.lower()}</b> and '
                'the weather at <b style="color:#c7cde0;">store-day grain</b>. Positive = higher in '
                'warm / wet conditions; negative = higher in cool / dry. Shown for completeness — most '
                'categories sit near zero.</div>', unsafe_allow_html=True)

    ct = corr_table("temp_max", value_col)
    cp = corr_table("precipitation_sum", value_col)

    wc = st.columns(2, gap="medium")
    with wc[0]:
        with st.container(border=True):
            if not ct.empty:
                st.plotly_chart(corr_bar(ct, f"{measure_label} vs temperature",
                                         "warm-weather ▶", "◀ cool-weather", WARM, BLUE),
                                use_container_width=True, config={"displayModeBar": False})
            else:
                st.info("Not enough days in this selection for a temperature signal.")
    with wc[1]:
        with st.container(border=True):
            if not cp.empty:
                st.plotly_chart(corr_bar(cp, f"{measure_label} vs precipitation",
                                         "rain-driven ▶", "◀ dry-driven", BLUE, YELLOW),
                                use_container_width=True, config={"displayModeBar": False})
            else:
                st.info("Not enough days in this selection for a precipitation signal.")

    # --- recommendation panel ---
    st.markdown(f'<div style="font-size:16px;font-weight:800;color:{INK};margin:16px 0 4px;">'
                '💡 Inventory &amp; promotion playbook</div>'
                f'<div style="font-size:12.5px;color:{MUTED};margin:0 2px 8px;">The reliable lever is '
                '<b style="color:#c7cde0;">channel readiness</b> (pickup on rain days, above). The '
                'per-category weather tilts below are <b style="color:#c7cde0;">weak</b> — modest, '
                'directional hints worth testing, not firm rules.</div>', unsafe_allow_html=True)

    tr_map = dict(zip(ct["category"], ct["r"])) if not ct.empty else {}
    pr_map = dict(zip(cp["category"], cp["r"])) if not cp.empty else {}
    # order by strength of the temperature signal (most actionable first)
    ordered = sorted(sel_cats, key=lambda c: -abs(tr_map.get(c, 0)))

    rec_cols = st.columns(2, gap="small")
    for i, c in enumerate(ordered):
        tr, pr = tr_map.get(c, 0.0), pr_map.get(c, 0.0)
        tag, tag_col, body = recommend(c, tr, pr)
        with rec_cols[i % 2]:
            with st.container(border=True):
                st.markdown(
                    f'<div style="display:flex;justify-content:space-between;align-items:center;">'
                    f'<span style="font-size:15px;font-weight:800;color:{INK};text-transform:capitalize;">{c}</span>'
                    f'<span class="pill" style="color:{tag_col};background:rgba(255,255,255,0.06);">{tag}</span></div>'
                    f'<div style="font-size:12px;color:{MUTED};margin:4px 0 6px;">'
                    f'temp r <b style="color:{INK};">{tr:+.2f}</b> &nbsp;·&nbsp; '
                    f'precip r <b style="color:{INK};">{pr:+.2f}</b></div>'
                    f'<div style="font-size:13.5px;color:#c7cde0;line-height:1.5;">'
                    f'<b style="text-transform:capitalize;">{c}</b> {body}</div>',
                    unsafe_allow_html=True)

    n_note = int(ct["n"].max()) if not ct.empty else 0
    st.markdown(f'<div style="font-size:11.5px;color:{MUTED};margin-top:10px;">'
                f'Computed at store-day grain (~{n_note} observations per category, not chain-day '
                'n≈28 — aggregating stores would smooth noise and inflate r). Still directional, not '
                'causal: store-days within a day share demand shocks (weekday, promotions), so treat '
                'these as hypotheses to test, not fixed rules.</div>', unsafe_allow_html=True)

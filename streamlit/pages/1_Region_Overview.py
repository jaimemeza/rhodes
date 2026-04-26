import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.snowflake import get_snowflake_connection
from utils.queries import (
    fetch_region_year,
    fetch_pipeline_by_region,
    fetch_cancel_trend,
)
from utils.styles import apply_global_styles

st.set_page_config(page_title="Region Overview · Rhodes", layout="wide",
                   initial_sidebar_state="collapsed")
apply_global_styles()

# ── Brand colors ───────────────────────────────────────────────────────
GREEN       = "#5a8c3e"
GREEN_LIGHT = "#7aa55c"
AMBER       = "#c75a3e"
GRAY        = "#8e8e93"
SURFACE     = "#f5f5f7"
TEXT        = "#1c1c1e"
TEXT_MUTED  = "#6e6e73"

# ── Header ─────────────────────────────────────────────────────────────
st.title("Region Overview")
st.caption(
    "Year-over-year volume, target attainment, and margin posture by region. "
    "YoY uses same-period comparison (apples-to-apples)."
)

# ── Data ───────────────────────────────────────────────────────────────
conn        = get_snowflake_connection()
df          = fetch_region_year(conn)
pipeline_df = fetch_pipeline_by_region(conn)
cancel_df   = fetch_cancel_trend(conn)

if df.empty:
    st.error("No data returned from mart_region_year.")
    st.stop()
if pipeline_df.empty:
    st.error("No data returned from pipeline query.")
    st.stop()
if cancel_df.empty:
    st.error("No data returned from cancel trend query.")
    st.stop()

df_2024 = df[df["contract_year"] == df["contract_year"].max()]
regions = sorted(df_2024["region"].unique())

years_in_data = sorted(df["contract_year"].unique())
current_year  = int(years_in_data[-1])
prior_year    = int(years_in_data[0]) if len(years_in_data) > 1 else current_year - 1

_af = df[df["contract_year"] == current_year]["annualization_factor"]
months_elapsed = (
    round(12.0 / float(_af.iloc[0]))
    if not _af.empty and float(_af.iloc[0]) > 1 else 12
)
MONTH_ABBR = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
month_abbr = MONTH_ABBR[months_elapsed - 1]


# ── Helpers ────────────────────────────────────────────────────────────
def get_row(region: str, year: int):
    """Return the single-row Series for region + year, or None."""
    sub = df[(df["region"] == region) & (df["contract_year"] == year)]
    return sub.iloc[0] if not sub.empty else None


def fmt_millions(v) -> str:
    try:
        return f"${float(v)/1_000_000:.1f}M"
    except (TypeError, ValueError):
        return "—"


def fmt_thousands(v) -> str:
    try:
        return f"${float(v)/1_000:.0f}k"
    except (TypeError, ValueError):
        return "—"


def yoy_parts(pct):
    """Return (arrow, pct_str, color) for a fractional YoY value."""
    try:
        val = float(pct)
        if pd.isna(val):
            raise ValueError
    except (TypeError, ValueError):
        return "−", "n/a", GRAY
    if val > 0:
        return "▲", f"{val*100:.1f}%", GREEN_LIGHT
    if val < 0:
        return "▼", f"{abs(val)*100:.1f}%", AMBER
    return "−", "0.0%", GRAY


def build_volume_tile(row) -> str:
    """HTML for one volume KPI tile (left group, Zone 1)."""
    region   = row["region"]
    closings = int(row["contracts_closed"])
    arrow, pct_str, yoy_color = yoy_parts(row.get("same_period_yoy_pct"))
    try:
        ytd_frac = float(row["target_attainment_ytd_pct"])
        bar_w    = min(100.0, ytd_frac * 100)
        ytd_text = f"{ytd_frac * 100:.0f}%"
        target   = int(row["sales_target_units"])
    except (TypeError, ValueError):
        bar_w, ytd_text, target = 0.0, "—", 0

    return f"""
<div style="background:{SURFACE}; border-radius:10px; padding:16px 14px;
            min-height:130px;">
  <div style="font-size:13px; color:{TEXT_MUTED}; margin-bottom:6px;">{region}</div>
  <div style="display:flex; align-items:baseline; gap:8px; margin-bottom:8px;">
    <span style="font-size:36px; font-weight:700; color:{TEXT};
                 line-height:1;">{closings}</span>
    <span style="font-size:14px; font-weight:600;
                 color:{yoy_color};">{arrow} {pct_str} YoY</span>
  </div>
  <div style="background:#e5e5ea; border-radius:4px; height:12px; margin-bottom:6px;">
    <div style="background:{GREEN}; border-radius:4px; height:12px;
                width:{bar_w:.0f}%;"></div>
  </div>
  <div style="font-size:12px; color:{TEXT_MUTED};">
    {closings} of {target} units · YTD {ytd_text}
  </div>
</div>"""


def build_revenue_tile(row) -> str:
    """HTML for one revenue tile (right group, Zone 1)."""
    region     = row["region"]
    closed_val = fmt_millions(row["closed_value"])
    closed_n   = int(row["closed_contracts"])
    pipe_n     = int(row["pipeline_contracts"])
    pipe_val   = fmt_millions(row["pipeline_value"])
    avg_price  = fmt_thousands(row["avg_contract_price"])
    try:
        avg_days = f"{float(row['avg_days_to_close']):.0f}d"
    except (TypeError, ValueError):
        avg_days = "—"

    return f"""
<div style="background:{SURFACE}; border-radius:10px; padding:16px 14px;
            min-height:130px;">
  <div style="font-size:13px; color:{TEXT_MUTED}; margin-bottom:6px;">{region}</div>
  <div style="font-size:36px; font-weight:700; color:{TEXT}; line-height:1;
              margin-bottom:4px;">{closed_val}</div>
  <div style="font-size:13px; color:{TEXT_MUTED}; margin-bottom:8px;">
    YTD Revenue · {closed_n} units
  </div>
  <hr style="border:none; border-top:1px solid #e5e5ea; margin:6px 0;">
  <div style="font-size:12px; color:{TEXT_MUTED}; line-height:1.7;">
    Pipeline: {pipe_n} contracts · {pipe_val}<br>
    Avg price: {avg_price} · Avg close: {avg_days}
  </div>
</div>"""


# ── ZONE 1: Six KPI tiles ──────────────────────────────────────────────
tile_cols = st.columns([1, 1, 1, 0.08, 1, 1, 1])

for i, region in enumerate(regions):
    r = df_2024[df_2024["region"] == region]
    if r.empty:
        continue
    with tile_cols[i]:
        st.markdown(build_volume_tile(r.iloc[0]), unsafe_allow_html=True)

with tile_cols[3]:
    st.markdown(
        '<div style="border-left:1px solid #d1d1d6; height:120px; '
        'margin:auto;"></div>',
        unsafe_allow_html=True,
    )

for i, region in enumerate(regions):
    p = pipeline_df[pipeline_df["region"] == region]
    if p.empty:
        continue
    with tile_cols[i + 4]:
        st.markdown(build_revenue_tile(p.iloc[0]), unsafe_allow_html=True)


# ── ZONE 2: Two charts side by side ────────────────────────────────────
col_left, col_right = st.columns([6, 4])

# Bar chart data
y_prior, y_curr, cd_prior, cd_curr = [], [], [], []
for region in regions:
    r_curr   = get_row(region, current_year)
    sp_prior = int(r_curr["same_period_closed_prior_year"]) if r_curr is not None else 0
    c_curr   = int(r_curr["contracts_closed"])              if r_curr is not None else 0
    y_prior.append(sp_prior)
    y_curr.append(c_curr)
    cd_prior.append((region, prior_year,   sp_prior))
    cd_curr.append( (region, current_year, c_curr))

fig = go.Figure()
fig.add_trace(go.Bar(
    name=f"Jan–{month_abbr} {prior_year}",
    x=regions,
    y=y_prior,
    marker_color=GRAY,
    customdata=cd_prior,
    hovertemplate=(
        "<b>%{customdata[0]}</b><br>"
        f"Jan–{month_abbr} %{{customdata[1]}}<br>"
        "Closed: %{customdata[2]}<br>"
        "<extra></extra>"
    ),
))
fig.add_trace(go.Bar(
    name=f"Jan–{month_abbr} {current_year}",
    x=regions,
    y=y_curr,
    marker_color=GREEN,
    customdata=cd_curr,
    hovertemplate=(
        "<b>%{customdata[0]}</b><br>"
        f"Jan–{month_abbr} %{{customdata[1]}}<br>"
        "Closed: %{customdata[2]}<br>"
        "<extra></extra>"
    ),
))
fig.update_layout(
    barmode="group",
    bargap=0.25,
    bargroupgap=0.08,
    plot_bgcolor="#ffffff",
    paper_bgcolor="#ffffff",
    font=dict(family="sans-serif", color=TEXT),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    xaxis=dict(title=None, tickfont=dict(size=13)),
    yaxis=dict(title="Closed contracts", gridcolor="#e8e8e8"),
    margin=dict(t=40, b=20, l=10, r=10),
    height=350,
)

# Cancel rate chart (quarterly bars)
REGION_COLORS = {
    "Rio Grande Valley": GREEN,
    "South Texas":       GRAY,
    "Coastal Bend":      AMBER,
}
quarters = (
    cancel_df.sort_values("sort_key")["quarter_label"]
    .unique()
    .tolist()
)
fig2 = go.Figure()
for region in regions:
    rdf = cancel_df[cancel_df["region"] == region].sort_values("sort_key")
    if rdf.empty:
        continue
    fig2.add_trace(go.Bar(
        name=region,
        x=rdf["quarter_label"],
        y=rdf["cancel_rate"] * 100,
        marker_color=REGION_COLORS.get(region, GRAY),
        opacity=0.85,
        customdata=list(zip(
            [region] * len(rdf),
            rdf["quarter_label"],
            rdf["cancel_rate"] * 100,
        )),
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "%{customdata[1]}: %{customdata[2]:.1f}%<br>"
            "<extra></extra>"
        ),
    ))
fig2.update_layout(
    barmode="group",
    bargap=0.2,
    bargroupgap=0.05,
    plot_bgcolor="#ffffff",
    paper_bgcolor="#ffffff",
    font=dict(family="sans-serif", color=TEXT),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    xaxis=dict(
        title=None,
        tickfont=dict(size=12),
        categoryorder="array",
        categoryarray=quarters,
    ),
    yaxis=dict(
        title="Cancel rate (%)",
        range=[0, 25],
        gridcolor="#e8e8e8",
        ticksuffix="%",
    ),
    margin=dict(t=40, b=20, l=10, r=10),
    height=350,
)

with col_left:
    st.caption(
        f"Jan–{month_abbr} {prior_year} vs Jan–{month_abbr} {current_year}"
        " · same-period closed contracts"
    )
    st.plotly_chart(fig, use_container_width=True)

with col_right:
    st.caption("Cancellation rate by quarter · last 4 quarters")
    st.plotly_chart(fig2, use_container_width=True)


# ── ZONE 3: Detail + About collapsed ───────────────────────────────────
with st.expander("Show detail table", expanded=False):
    DISPLAY_COLS = [
        "region",
        "contract_year",
        "contracts_closed",
        "sales_target_units",
        "target_attainment_ytd_pct",
        "cancel_rate",
        "same_period_yoy_pct",
        "margin_attainment_delta",
    ]
    display_df = df[DISPLAY_COLS].copy()
    PCT_COLS = [
        "target_attainment_ytd_pct",
        "cancel_rate",
        "same_period_yoy_pct",
        "margin_attainment_delta",
    ]
    for col in PCT_COLS:
        display_df[col] = display_df[col] * 100
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "region": st.column_config.TextColumn("Region"),
            "contract_year": st.column_config.NumberColumn("Year", format="%d"),
            "contracts_closed": st.column_config.NumberColumn("Closed", format="%d"),
            "sales_target_units": st.column_config.NumberColumn("Target", format="%d"),
            "target_attainment_ytd_pct": st.column_config.NumberColumn(
                "YTD attainment", format="%.1f%%"
            ),
            "cancel_rate": st.column_config.NumberColumn(
                "Cancel rate", format="%.1f%%"
            ),
            "same_period_yoy_pct": st.column_config.NumberColumn(
                "YoY (same period)", format="%+.1f%%"
            ),
            "margin_attainment_delta": st.column_config.NumberColumn(
                "Margin Δ vs target", format="%+.1f%%"
            ),
        },
    )

with st.expander("About these numbers", expanded=False):
    st.markdown(f"""
**Year boundaries**

Year boundaries (`current_year`, `prior_year`, `months_elapsed`) are derived
dynamically from `MAX(contract_date)` in the mart. For the current dataset that
resolves to {current_year} / {prior_year} / {months_elapsed} months. As new data
arrives, these update automatically without model changes.

**Same-period YoY**

*YoY (same period)* compares January–{month_abbr} {current_year} closings directly
against January–{month_abbr} {prior_year} closings — the same calendar window in
both years. This is an apples-to-apples measurement; no extrapolation is involved.
For trend-aware forward projections, see the **Forecast** page.

**Margin attainment delta**

*Margin Δ vs target* is `avg_estimated_margin_pct − margin_target_pct`. The estimated
margin is a documented proxy (revenue net of agent commission ÷ contract price) — the
dataset has no construction cost column by design. Large deltas reflect the proxy
definition, not literal accounting outperformance. See the README for full context.
""")

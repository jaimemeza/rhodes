import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.snowflake import get_snowflake_connection
from utils.queries import (
    fetch_region_year,
    fetch_pipeline_by_region,
    fetch_cancel_trend,
)

st.set_page_config(page_title="Region Overview · Rhodes", layout="wide")

# ── Brand colors ───────────────────────────────────────────────────────
GREEN    = "#5a8c3e"
SOFT_POS = "#7aa55c"
SOFT_NEG = "#c75a3e"
GRAY     = "#8e8e93"
TEXT     = "#1c1c1e"

st.markdown("""
<style>
.kpi-card    { background:#f5f5f7; border-radius:10px; padding:20px 24px 16px 24px; }
.kpi-region  { font-size:15px; font-weight:600; color:#5a8c3e; margin-bottom:4px; }
.kpi-number  { font-size:40px; font-weight:700; color:#1c1c1e; line-height:1.1; }
.kpi-yoy     { font-size:15px; margin:6px 0 4px 0; }
.kpi-divider { border:none; border-top:1px solid #d1d1d6; margin:12px 0 10px 0; }
.kpi-bar-bg  { background:#e5e5ea; border-radius:6px; height:12px; margin-bottom:6px; }
.kpi-units   { font-size:13px; color:#1c1c1e; margin-bottom:2px; }
.kpi-caveat  { font-size:11px; color:#8e8e93; font-style:italic; }
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────
st.title("Region Overview")
st.caption(
    "Year-over-year volume, target attainment, and margin posture by region. "
    "YoY uses same-period comparison (apples-to-apples)."
)

# ── Data ───────────────────────────────────────────────────────────────
conn = get_snowflake_connection()
df   = fetch_region_year(conn)

if df.empty:
    st.error("No data returned from mart_region_year.")
    st.stop()

REGIONS = sorted(df["region"].unique())

# Derive year context from data — no hardcoded years
years_in_data  = sorted(df["contract_year"].unique())
current_year   = int(years_in_data[-1])
prior_year     = int(years_in_data[0]) if len(years_in_data) > 1 else current_year - 1

_af = df[df["contract_year"] == current_year]["annualization_factor"]
months_elapsed = round(12.0 / float(_af.iloc[0])) if not _af.empty and float(_af.iloc[0]) > 1 else 12
MONTH_ABBR = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
month_abbr = MONTH_ABBR[months_elapsed - 1]


def get_row(region: str, year: int):
    """Return the single-row Series for region + year, or None."""
    sub = df[(df["region"] == region) & (df["contract_year"] == year)]
    return sub.iloc[0] if not sub.empty else None


def yoy_label(pct) -> str:
    """Format a fractional YoY value as a colored chevron string."""
    try:
        val = float(pct)
        if pd.isna(val):
            raise ValueError
    except (TypeError, ValueError):
        return f'<span style="color:{GRAY}">— no prior year data</span>'
    if val > 0:
        color, arrow = SOFT_POS, "▲"
    elif val < 0:
        color, arrow = SOFT_NEG, "▼"
    else:
        color, arrow = GRAY, "−"
    return f'<span style="color:{color}">{arrow} {abs(val)*100:.1f}% YoY (same period)</span>'


def build_kpi_card(region: str, r_curr, r_prev) -> str:
    if r_curr is None:
        return f"""
<div class="kpi-card">
  <div class="kpi-region">{region}</div>
  <div class="kpi-number">—</div>
  <div class="kpi-yoy" style="color:{GRAY}">no current year data</div>
</div>"""

    closings = int(r_curr["contracts_closed"])
    yoy_html = yoy_label(r_curr.get("same_period_yoy_pct"))

    try:
        ytd_frac = float(r_curr["target_attainment_ytd_pct"])
        bar_w    = min(100.0, ytd_frac * 100)
        ytd_text = f"{ytd_frac * 100:.0f}%"
        target   = int(r_curr["sales_target_units"])
    except (TypeError, ValueError):
        bar_w, ytd_text, target = 0.0, "—", 0

    return f"""
<div class="kpi-card">
  <div class="kpi-region">{region}</div>
  <div class="kpi-number">{closings}</div>
  <div class="kpi-yoy">{yoy_html}</div>
  <hr class="kpi-divider">
  <div class="kpi-bar-bg">
    <div style="background:#5a8c3e; border-radius:6px; height:12px; width:{bar_w:.0f}%;"></div>
  </div>
  <div class="kpi-units">{closings} of {target} units · YTD attainment {ytd_text}</div>
</div>"""


# ── KPI cards ──────────────────────────────────────────────────────────
cols = st.columns(len(REGIONS))
for col, region in zip(cols, REGIONS):
    with col:
        st.markdown(
            build_kpi_card(region, get_row(region, current_year), get_row(region, prior_year)),
            unsafe_allow_html=True,
        )

# ── Bar chart ──────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
st.subheader(
    f"Jan–{month_abbr} {prior_year} vs Jan–{month_abbr} {current_year}"
    " — same-period closed contracts"
)

y_prior, y_curr, cd_prior, cd_curr = [], [], [], []
for region in REGIONS:
    r_curr = get_row(region, current_year)
    sp_prior = int(r_curr["same_period_closed_prior_year"]) if r_curr is not None else 0
    c_curr   = int(r_curr["contracts_closed"])              if r_curr is not None else 0
    y_prior.append(sp_prior)
    y_curr.append(c_curr)
    cd_prior.append((region, prior_year,   sp_prior))
    cd_curr.append( (region, current_year, c_curr))

fig = go.Figure()

fig.add_trace(go.Bar(
    name=f"Jan–{month_abbr} {prior_year}",
    x=REGIONS,
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
    x=REGIONS,
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
    height=380,
)

st.plotly_chart(fig, use_container_width=True)
st.caption(
    f"Both bars cover January–{month_abbr} only — a direct same-period comparison, "
    "no extrapolation. Annual targets shown as attainment % in the cards above."
)

# ── Detail table ───────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
st.subheader("Detail by region and year")

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
        "cancel_rate": st.column_config.NumberColumn("Cancel rate", format="%.1f%%"),
        "same_period_yoy_pct": st.column_config.NumberColumn(
            "YoY (same period)", format="%+.1f%%"
        ),
        "margin_attainment_delta": st.column_config.NumberColumn(
            "Margin Δ vs target", format="%+.1f%%"
        ),
    },
)

# ── Pipeline & YTD revenue ─────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
st.subheader("Active Pipeline & YTD Revenue")
st.caption(
    "Under Contract = signed but not yet closed. "
    f"YTD revenue = contract value of closed deals in {current_year}."
)

pipeline_df = fetch_pipeline_by_region(conn)


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


def build_pipeline_card(row) -> str:
    region_name   = row["region"]
    pipe_n        = int(row["pipeline_contracts"])
    pipe_val      = fmt_millions(row["pipeline_value"])
    closed_n      = int(row["closed_contracts"])
    closed_val    = fmt_millions(row["closed_value"])
    avg_price     = fmt_thousands(row["avg_contract_price"])
    avg_days      = (
        f"{float(row['avg_days_to_close']):.0f} days"
        if row["avg_days_to_close"] is not None else "—"
    )
    avg_upgrade   = (
        f"{float(row['avg_upgrade_capture'])*100:.1f}%"
        if row["avg_upgrade_capture"] is not None else "—"
    )
    return f"""
<div class="kpi-card">
  <div class="kpi-region">{region_name}</div>
  <div style="margin-top:10px; font-size:12px; color:{GRAY}; text-transform:uppercase;
              letter-spacing:.05em;">Pipeline</div>
  <div style="font-size:20px; font-weight:600; color:{TEXT};">
    {pipe_n} contracts &nbsp;·&nbsp; {pipe_val}
  </div>
  <div style="margin-top:10px; font-size:12px; color:{GRAY}; text-transform:uppercase;
              letter-spacing:.05em;">YTD Revenue</div>
  <div style="font-size:20px; font-weight:600; color:{GREEN};">
    {closed_val} &nbsp;·&nbsp; {closed_n} units
  </div>
  <div style="margin-top:12px; font-size:12px; color:{TEXT}; line-height:1.7;">
    Avg contract price: <b>{avg_price}</b><br>
    Avg days to close: <b>{avg_days}</b><br>
    Avg upgrade capture: <b>{avg_upgrade}</b>
  </div>
</div>"""


p_cols = st.columns(len(REGIONS))
for col, region in zip(p_cols, REGIONS):
    row = pipeline_df[pipeline_df["region"] == region]
    if not row.empty:
        with col:
            st.markdown(
                build_pipeline_card(row.iloc[0]),
                unsafe_allow_html=True,
            )

# ── Cancellation rate trend ────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
st.subheader("Cancellation Rate — Last 12 Months")
st.caption(
    "Monthly cancel rate per region. "
    "Identifies whether current-year rates are a trend or a spike."
)

cancel_df = fetch_cancel_trend(conn)

REGION_COLORS = {
    "Rio Grande Valley": GREEN,
    "South Texas":       GRAY,
    "Coastal Bend":      SOFT_NEG,
}

fig2 = go.Figure()
for region in REGIONS:
    rdf = cancel_df[cancel_df["region"] == region].sort_values("month_start")
    if rdf.empty:
        continue
    fig2.add_trace(go.Scatter(
        name=region,
        x=rdf["month_start"],
        y=rdf["cancel_rate"] * 100,
        mode="lines+markers",
        line=dict(color=REGION_COLORS.get(region, GRAY), width=2),
        marker=dict(size=6),
        customdata=list(zip(
            [region] * len(rdf),
            rdf["cancel_rate"] * 100,
        )),
        hovertemplate=(
            "<b>%{customdata[0]}</b><br>"
            "%{x|%b %Y}: %{customdata[1]:.1f}%<br>"
            "<extra></extra>"
        ),
    ))

fig2.update_layout(
    plot_bgcolor="#ffffff",
    paper_bgcolor="#ffffff",
    font=dict(family="sans-serif", color=TEXT),
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    xaxis=dict(
        title=None,
        tickformat="%b %Y",
        tickfont=dict(size=12),
        gridcolor="#e8e8e8",
    ),
    yaxis=dict(
        title="Cancel rate (%)",
        range=[0, 20],
        gridcolor="#e8e8e8",
        ticksuffix="%",
    ),
    margin=dict(t=40, b=20, l=10, r=10),
    height=340,
)

st.plotly_chart(fig2, use_container_width=True)

# ── About these numbers ────────────────────────────────────────────────
with st.expander("About these numbers"):
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

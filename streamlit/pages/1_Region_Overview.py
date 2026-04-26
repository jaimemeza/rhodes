import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.snowflake import get_snowflake_connection
from utils.queries import fetch_region_year

st.set_page_config(page_title="Region Overview · Rhodes", layout="wide")

# ── Brand colors ───────────────────────────────────────────────────────
GREEN    = "#5a8c3e"
SOFT_POS = "#7aa55c"
SOFT_NEG = "#c75a3e"
GRAY     = "#8e8e93"
TEXT     = "#1c1c1e"

st.markdown("""
<style>
.kpi-card   { background:#f5f5f7; border-radius:10px; padding:20px 24px 16px 24px; }
.kpi-region { font-size:15px; font-weight:600; color:#1c1c1e; margin-bottom:4px; }
.kpi-number { font-size:40px; font-weight:700; color:#5a8c3e; line-height:1.1; }
.kpi-yoy    { font-size:15px; margin:6px 0 2px 0; }
.kpi-pace   { font-size:13px; color:#1c1c1e; margin-bottom:4px; }
.kpi-caveat { font-size:11px; color:#8e8e93; font-style:italic; }
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────
st.title("Region Overview")
st.caption(
    "Year-over-year volume, target attainment, and margin posture by region. "
    "2024 figures are annualized projections from 9 months of data."
)

# ── Data ───────────────────────────────────────────────────────────────
conn = get_snowflake_connection()
df   = fetch_region_year(conn)

if df.empty:
    st.error("No data returned from mart_region_year.")
    st.stop()

REGIONS = sorted(df["region"].unique())


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
        return f'<span style="color:{GRAY}">— no prior year</span>'
    if val > 0:
        color, arrow = SOFT_POS, "▲"
    elif val < 0:
        color, arrow = SOFT_NEG, "▼"
    else:
        color, arrow = GRAY, "−"
    return f'<span style="color:{color}">{arrow} {abs(val) * 100:.1f}% YoY</span>'


def build_kpi_card(region: str, r2024, r2023) -> str:
    if r2024 is None:
        closings = "—"
        yoy      = f'<span style="color:{GRAY}">no 2024 data</span>'
        pace     = "—"
    else:
        closings = str(int(r2024["contracts_closed_annualized"]))
        yoy      = yoy_label(r2024.get("closed_yoy_pct"))
        try:
            pace = f"{float(r2024['target_attainment_annualized_pct']) * 100:.0f}% on pace to annual target"
        except (TypeError, ValueError):
            pace = "—"
    return f"""
<div class="kpi-card">
  <div class="kpi-region">{region}</div>
  <div class="kpi-number">{closings}</div>
  <div class="kpi-yoy">{yoy}</div>
  <div class="kpi-pace">{pace}</div>
  <div class="kpi-caveat">Pace projection — assumes constant monthly volume</div>
</div>"""


# ── KPI cards ──────────────────────────────────────────────────────────
cols = st.columns(len(REGIONS))
for col, region in zip(cols, REGIONS):
    with col:
        st.markdown(
            build_kpi_card(region, get_row(region, 2024), get_row(region, 2023)),
            unsafe_allow_html=True,
        )

# ── Bar chart ──────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
st.subheader("2023 vs 2024 (annualized) — closed contracts")

y_2023, y_2024, cd_2023, cd_2024 = [], [], [], []
for region in REGIONS:
    r23 = get_row(region, 2023)
    r24 = get_row(region, 2024)
    c23     = int(r23["contracts_closed"])             if r23 is not None else 0
    c24_ann = int(r24["contracts_closed_annualized"])  if r24 is not None else 0
    c24_raw = int(r24["contracts_closed"])             if r24 is not None else 0
    y_2023.append(c23)
    y_2024.append(c24_ann)
    cd_2023.append((region, c23))
    cd_2024.append((region, c24_raw, c24_ann))

fig = go.Figure()

fig.add_trace(go.Bar(
    name="2023 (actual)",
    x=REGIONS,
    y=y_2023,
    marker_color=GRAY,
    customdata=cd_2023,
    hovertemplate=(
        "<b>%{customdata[0]}</b><br>"
        "Year: 2023<br>"
        "Closed: %{customdata[1]}<br>"
        "<extra></extra>"
    ),
))

fig.add_trace(go.Bar(
    name="2024 (annualized)",
    x=REGIONS,
    y=y_2024,
    marker_color=GREEN,
    customdata=cd_2024,
    hovertemplate=(
        "<b>%{customdata[0]}</b><br>"
        "Year: 2024<br>"
        "Actual closings (9 mo): %{customdata[1]}<br>"
        "Annualized projection: %{customdata[2]}<br>"
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
    "2024 bar = raw closings × 12/9 (linear pace projection). "
    "Annual targets are shown as attainment % in the cards above."
)

# ── Detail table ───────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
st.subheader("Detail by region and year")

DISPLAY_COLS = [
    "region",
    "contract_year",
    "contracts_closed",
    "contracts_closed_annualized",
    "sales_target_units",
    "target_attainment_annualized_pct",
    "target_attainment_ytd_pct",
    "cancel_rate",
    "closed_yoy_pct",
    "margin_attainment_delta",
]

display_df = df[DISPLAY_COLS].copy()

# Scale fractional values to percentage points so format strings render correctly
PCT_COLS = [
    "target_attainment_annualized_pct",
    "target_attainment_ytd_pct",
    "cancel_rate",
    "closed_yoy_pct",
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
        "contracts_closed_annualized": st.column_config.NumberColumn(
            "Closed (annualized)", format="%d"
        ),
        "sales_target_units": st.column_config.NumberColumn("Target", format="%d"),
        "target_attainment_annualized_pct": st.column_config.NumberColumn(
            "Pace attainment", format="%.1f%%"
        ),
        "target_attainment_ytd_pct": st.column_config.NumberColumn(
            "YTD attainment", format="%.1f%%"
        ),
        "cancel_rate": st.column_config.NumberColumn("Cancel rate", format="%.1f%%"),
        "closed_yoy_pct": st.column_config.NumberColumn(
            "YoY (annualized)", format="%+.1f%%"
        ),
        "margin_attainment_delta": st.column_config.NumberColumn(
            "Margin Δ vs target", format="%+.1f%%"
        ),
    },
)

# ── About these numbers ────────────────────────────────────────────────
with st.expander("About these numbers"):
    st.markdown("""
**Annualization**

The 2024 dataset covers January through September 2024 (9 months). Annualized figures
multiply raw 9-month counts by 12/9 to project the full calendar year, assuming the
monthly pace observed so far holds through December. This is a **linear extrapolation**
— it does not adjust for seasonality, trend, or lumpiness in closing activity. For a
trend-aware forward projection, see the **Forecast** page, which uses Snowflake Cortex
FORECAST on the monthly time series.

**Margin attainment delta**

*Margin Δ vs target* is `avg_estimated_margin_pct − margin_target_pct`. The estimated
margin column is a documented proxy: revenue net of agent commission expressed as a
fraction of contract price. The dataset has no construction cost column by design — this
is the closest available measure of deal quality. As a result, large positive deltas
should not be read as "beating the margin target by X percentage points" in an accounting
sense. See the README for the full proxy definition and rationale.
""")

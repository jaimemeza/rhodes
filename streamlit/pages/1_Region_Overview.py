import plotly.graph_objects as go
import streamlit as st

from utils.snowflake import get_snowflake_connection
from utils.queries import fetch_region_year

st.set_page_config(page_title="Region Overview · Rhodes", layout="wide")

# ── Brand colors ───────────────────────────────────────────────────────
GREEN = "#5a8c3e"
SOFT_POS = "#7aa55c"
SOFT_NEG = "#c75a3e"
GRAY = "#8e8e93"
SURFACE = "#f5f5f7"
TEXT = "#1c1c1e"

st.markdown("""
<style>
.kpi-card {
    background: #f5f5f7;
    border-radius: 10px;
    padding: 20px 24px 16px 24px;
    height: 100%;
}
.kpi-region { font-size: 15px; font-weight: 600; color: #1c1c1e; margin-bottom: 4px; }
.kpi-number { font-size: 40px; font-weight: 700; color: #5a8c3e; line-height: 1.1; }
.kpi-yoy    { font-size: 15px; margin: 6px 0 2px 0; }
.kpi-pace   { font-size: 13px; color: #1c1c1e; margin-bottom: 4px; }
.kpi-caveat { font-size: 11px; color: #8e8e93; font-style: italic; }
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────
st.title("Region Overview")
st.caption(
    "Year-over-year volume, target attainment, and margin posture by region. "
    "2024 figures are annualized projections from 9 months of data."
)

# ── Data ───────────────────────────────────────────────────────────────
try:
    conn = get_snowflake_connection()
    df = fetch_region_year(conn)
except Exception as e:
    st.error(f"Failed to load data: {e}")
    st.stop()

REGIONS = sorted(df["region"].unique())

def row(df, region, year):
    """Return the single row for a given region + year, or None."""
    mask = (df["region"] == region) & (df["contract_year"] == year)
    sub = df[mask]
    return sub.iloc[0] if not sub.empty else None


def yoy_label(pct):
    """Format a fractional YoY change as a colored chevron + percentage string."""
    if pct is None or (hasattr(pct, '__class__') and str(pct) == 'nan'):
        return f'<span style="color:{GRAY}">— no prior year</span>'
    try:
        val = float(pct)
    except (TypeError, ValueError):
        return f'<span style="color:{GRAY}">— no prior year</span>'
    if val > 0:
        color = SOFT_POS
        arrow = "▲"
    elif val < 0:
        color = SOFT_NEG
        arrow = "▼"
    else:
        color = GRAY
        arrow = "−"
    return f'<span style="color:{color}">{arrow} {abs(val)*100:.1f}% YoY</span>'


def build_kpi_card(region: str, r2024, r2023) -> str:
    """Return the HTML for one region KPI card."""
    if r2024 is None:
        closings = "—"
        yoy = f'<span style="color:{GRAY}">no 2024 data</span>'
        pace = "—"
    else:
        closings = str(int(r2024["contracts_closed_annualized"]))
        yoy = yoy_label(r2024.get("closed_yoy_pct"))
        attainment = r2024.get("target_attainment_annualized_pct")
        try:
            pace = f"{float(attainment)*100:.0f}% on pace to annual target"
        except (TypeError, ValueError):
            pace = "—"

    return f"""
<div class="kpi-card">
  <div class="kpi-region">{region}</div>
  <div class="kpi-number">{closings}</div>
  <div class="kpi-yoy">{yoy}</div>
  <div class="kpi-pace">{pace}</div>
  <div class="kpi-caveat">Pace projection — assumes constant monthly volume</div>
</div>
"""


# ── KPI cards ──────────────────────────────────────────────────────────
cols = st.columns(len(REGIONS))
for col, region in zip(cols, REGIONS):
    r2024 = row(df, region, 2024)
    r2023 = row(df, region, 2023)
    with col:
        st.markdown(build_kpi_card(region, r2024, r2023), unsafe_allow_html=True)

# ── Bar chart ──────────────────────────────────────────────────────────
st.markdown("<br>", unsafe_allow_html=True)
st.subheader("2023 vs 2024 (annualized) — closed contracts")

# Build parallel lists in alphabetical region order
r2023_vals, r2024_vals = [], []
r2023_raw, r2024_raw = [], []
for region in REGIONS:
    r23 = row(df, region, 2023)
    r24 = row(df, region, 2024)
    r2023_vals.append(int(r23["contracts_closed"]) if r23 is not None else 0)
    r2024_vals.append(int(r24["contracts_closed_annualized"]) if r24 is not None else 0)
    r2023_raw.append(int(r23["contracts_closed"]) if r23 is not None else 0)
    r2024_raw.append(int(r24["contracts_closed"]) if r24 is not None else 0)

fig = go.Figure()

fig.add_trace(go.Bar(
    name="2023 (actual)",
    x=REGIONS,
    y=r2023_vals,
    marker_color=GRAY,
    customdata=list(zip(r2023_raw, r2023_raw)),
    hovertemplate=(
        "<b>%{x}</b><br>"
        "Year: 2023<br>"
        "Closed: %{y}<br>"
        "<extra></extra>"
    ),
))

fig.add_trace(go.Bar(
    name="2024 (annualized)",
    x=REGIONS,
    y=r2024_vals,
    marker_color=GREEN,
    customdata=list(zip(r2024_raw, r2024_vals)),
    hovertemplate=(
        "<b>%{x}</b><br>"
        "Year: 2024<br>"
        "Actual closings (9 mo): %{customdata[0]}<br>"
        "Annualized projection: %{customdata[1]}<br>"
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
    "Annual target lines not shown here; see attainment % in cards above."
)

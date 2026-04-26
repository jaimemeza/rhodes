import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.snowflake import get_snowflake_connection
from utils.queries import fetch_consultant_performance, fetch_consultant_region

st.set_page_config(page_title="Consultants · Rhodes", layout="wide")

GREEN       = "#5a8c3e"
GREEN_LIGHT = "#7aa55c"
AMBER       = "#c75a3e"
GRAY        = "#8e8e93"
SURFACE     = "#f5f5f7"
TEXT        = "#1c1c1e"
TEXT_MUTED  = "#6e6e73"

st.title("Consultants")
st.caption(
    "Individual sales consultant performance with year-over-year trends. "
    "2024 figures cover Jan–Sep (same period as 2023 comparison)."
)

conn      = get_snowflake_connection()
df        = fetch_consultant_performance(conn)
region_df = fetch_consultant_region(conn)

if df.empty:
    st.error("No data returned from mart_consultant_performance.")
    st.stop()

df = df.copy()
df["cancel_pct"]         = (df["cancel_rate"] * 100).round(1)
df["cancel_prior_pct"]   = (df["cancel_rate_prior_year"] * 100).round(1)
df["cancel_current_pct"] = (df["cancel_rate_current_year"] * 100).round(1)
df["cancel_delta_pp"]    = (df["cancel_rate_yoy_delta"] * 100).round(1)
df["cash_pct"]           = (df["cash_buyer_rate"] * 100).round(1)


def _fmt_pct(v) -> str:
    try:
        f = float(v)
        return "n/a" if pd.isna(f) else f"{f:.1f}%"
    except (TypeError, ValueError):
        return "n/a"


# ── SECTION 1: Call-out cards ──────────────────────────────────────────
df_with_delta  = df.dropna(subset=["cancel_delta_pp"])
top_volume     = df.loc[df["closed_current_year"].idxmax()]
most_improved  = df_with_delta.loc[df_with_delta["cancel_delta_pp"].idxmin()]
needs_attn     = df_with_delta.loc[df_with_delta["cancel_delta_pp"].idxmax()]

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(f"""
<div style="background:{SURFACE}; border-radius:10px; padding:16px 14px;
            min-height:125px;">
  <div style="font-size:13px; color:{TEXT_MUTED}; margin-bottom:6px;">
    Top Performer 2024</div>
  <div style="font-size:22px; font-weight:700; color:{GREEN}; line-height:1.2;
              margin-bottom:4px;">{top_volume['sales_consultant']}</div>
  <div style="font-size:18px; font-weight:600; color:{TEXT};">
    {int(top_volume['closed_current_year'])} closings</div>
  <div style="font-size:12px; color:{TEXT_MUTED}; margin-top:4px;">
    Most closed contracts Jan–Sep 2024</div>
</div>""", unsafe_allow_html=True)

with col2:
    st.markdown(f"""
<div style="background:{SURFACE}; border-radius:10px; padding:16px 14px;
            min-height:125px;">
  <div style="font-size:13px; color:{TEXT_MUTED}; margin-bottom:6px;">
    Most Improved</div>
  <div style="font-size:22px; font-weight:700; color:{GREEN_LIGHT};
              line-height:1.2; margin-bottom:4px;">
    {most_improved['sales_consultant']}</div>
  <div style="font-size:16px; font-weight:600; color:{GREEN_LIGHT};">
    {abs(most_improved['cancel_delta_pp']):.1f}pp lower cancel rate</div>
  <div style="font-size:12px; color:{TEXT_MUTED}; margin-top:4px;">
    {_fmt_pct(most_improved['cancel_prior_pct'])} →
    {_fmt_pct(most_improved['cancel_current_pct'])}</div>
  <div style="font-size:12px; color:{TEXT_MUTED};">
    Year-over-year cancel rate improvement</div>
</div>""", unsafe_allow_html=True)

with col3:
    st.markdown(f"""
<div style="background:{SURFACE}; border-radius:10px; padding:16px 14px;
            min-height:125px;">
  <div style="font-size:13px; color:{TEXT_MUTED}; margin-bottom:6px;">
    Needs Attention</div>
  <div style="font-size:22px; font-weight:700; color:{AMBER}; line-height:1.2;
              margin-bottom:4px;">{needs_attn['sales_consultant']}</div>
  <div style="font-size:16px; font-weight:600; color:{AMBER};">
    +{needs_attn['cancel_delta_pp']:.1f}pp higher cancel rate</div>
  <div style="font-size:12px; color:{TEXT_MUTED}; margin-top:4px;">
    {_fmt_pct(needs_attn['cancel_prior_pct'])} →
    {_fmt_pct(needs_attn['cancel_current_pct'])}</div>
  <div style="font-size:12px; color:{TEXT_MUTED};">
    Largest cancel rate increase vs. prior year</div>
</div>""", unsafe_allow_html=True)


# ── SECTION 2: YoY scatter ─────────────────────────────────────────────
st.markdown("**Volume: prior year vs. current year (same period)**")
st.caption("Dots above the diagonal improved YoY; below declined.")

x_min   = max(0, int(df["closed_prior_year"].min()) - 2)
x_max   = int(df["closed_prior_year"].max()) + 2
x_range = [x_min, x_max]

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=df["closed_prior_year"],
    y=df["closed_current_year"],
    text=df["sales_consultant"],
    mode="markers+text",
    textposition="top center",
    textfont=dict(size=10, color=TEXT),
    marker=dict(
        size=14,
        color=GREEN,
        opacity=0.8,
        line=dict(width=1.5, color="white"),
    ),
    hovertemplate=(
        "<b>%{text}</b><br>"
        "2023: %{x} closings<br>"
        "2024: %{y} closings<extra></extra>"
    ),
    showlegend=False,
))
fig.add_shape(
    type="line",
    x0=x_range[0], y0=x_range[0],
    x1=x_range[1], y1=x_range[1],
    line=dict(dash="dot", color=GRAY, width=1),
)
fig.update_layout(
    plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
    font=dict(family="sans-serif", color=TEXT),
    xaxis=dict(title="Prior year closings (Jan–Sep 2023)",
               gridcolor="#e8e8e8"),
    yaxis=dict(title="Current year closings (Jan–Sep 2024)",
               gridcolor="#e8e8e8"),
    margin=dict(t=20, b=50, l=10, r=10),
    height=380,
)
st.plotly_chart(fig, use_container_width=True)


# ── SECTION 3: Leaderboard table ───────────────────────────────────────
st.markdown("**Consultant leaderboard**")
leaderboard = (
    df[["sales_consultant", "closed_current_year", "closed_prior_year",
        "cancel_current_pct", "cancel_delta_pp", "avg_days_to_close",
        "cash_pct", "regions_worked"]]
    .sort_values("closed_current_year", ascending=False)
    .copy()
)
st.dataframe(
    leaderboard,
    use_container_width=True,
    hide_index=True,
    height=280,
    column_config={
        "sales_consultant":    st.column_config.TextColumn("Consultant"),
        "closed_current_year": st.column_config.NumberColumn("2024 YTD",
                                                              format="%d"),
        "closed_prior_year":   st.column_config.NumberColumn("2023 same period",
                                                              format="%d"),
        "cancel_current_pct":  st.column_config.NumberColumn("2024 Cancel %",
                                                              format="%.1f%%"),
        "cancel_delta_pp":     st.column_config.NumberColumn("Cancel Δ (pp)",
                                                              format="%+.1f"),
        "avg_days_to_close":   st.column_config.NumberColumn("Avg close days",
                                                              format="%.0f"),
        "cash_pct":            st.column_config.NumberColumn("Cash buyer %",
                                                              format="%.1f%%"),
        "regions_worked":      st.column_config.NumberColumn("Regions",
                                                              format="%d"),
    },
)


# ── SECTION 4: Region drill-down ───────────────────────────────────────
st.markdown("**Regional breakdown by consultant**")
selected = st.selectbox(
    "Select consultant",
    options=sorted(df["sales_consultant"].unique()),
    index=0,
)
filtered = region_df[region_df["sales_consultant"] == selected].copy()
if not filtered.empty:
    filtered["cancel_pct"]  = (filtered["cancel_rate"] * 100).round(1)
    filtered["revenue_M"]   = (filtered["total_contract_value"] / 1e6).round(2)
    st.dataframe(
        filtered[["region", "contracts", "closed_contracts",
                  "cancel_pct", "avg_days_to_close", "revenue_M"]],
        use_container_width=True,
        hide_index=True,
        height=175,
        column_config={
            "region":            st.column_config.TextColumn("Region"),
            "contracts":         st.column_config.NumberColumn("Contracts",
                                                                format="%d"),
            "closed_contracts":  st.column_config.NumberColumn("Closed",
                                                                format="%d"),
            "cancel_pct":        st.column_config.NumberColumn("Cancel %",
                                                                format="%.1f%%"),
            "avg_days_to_close": st.column_config.NumberColumn("Avg close days",
                                                                format="%.0f"),
            "revenue_M":         st.column_config.NumberColumn("Revenue $M",
                                                                format="$%.2f"),
        },
    )
else:
    st.write("No regional breakdown available for this consultant.")

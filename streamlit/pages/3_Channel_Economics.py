import plotly.graph_objects as go
import streamlit as st

from utils.snowflake import get_snowflake_connection
from utils.queries import (
    fetch_channel_economics,
    fetch_pipeline_by_region,
    fetch_region_year,
)

st.set_page_config(page_title="Revenue & Channels · Rhodes", layout="wide")

GREEN       = "#5a8c3e"
GREEN_LIGHT = "#7aa55c"
AMBER       = "#c75a3e"
GRAY        = "#8e8e93"
SURFACE     = "#f5f5f7"
TEXT        = "#1c1c1e"
TEXT_MUTED  = "#6e6e73"

st.title("Revenue & Channels")
st.caption(
    "Acquisition channel cost vs. quality — which channels deliver "
    "the best buyers at the lowest commission cost."
)

conn        = get_snowflake_connection()
channel_df  = fetch_channel_economics(conn)
region_df   = fetch_region_year(conn)      # noqa: F841 — available for future use
pipeline_df = fetch_pipeline_by_region(conn)  # noqa: F841

if channel_df.empty:
    st.error("No data returned from mart_channel_economics.")
    st.stop()

channel_df = channel_df.copy()
channel_df["commission_pct"] = (channel_df["avg_commission_rate"] * 100).round(2)
channel_df["cancel_pct"]     = (channel_df["cancel_rate"] * 100).round(2)
channel_df["revenue_M"]      = (channel_df["total_contract_value"] / 1e6).round(1)


# ── SECTION 1: Headline KPI cards ──────────────────────────────────────
best_cancel  = channel_df.loc[channel_df["cancel_pct"].idxmin()]
costliest    = channel_df.loc[channel_df["commission_pct"].idxmax()]
highest_vol  = channel_df.loc[channel_df["contracts"].idxmax()]


def _kpi_card(label: str, value: str, subline: str) -> str:
    return f"""
<div style="background:{SURFACE}; border-radius:10px; padding:16px 14px;
            min-height:110px;">
  <div style="font-size:13px; color:{TEXT_MUTED}; margin-bottom:6px;">
    {label}</div>
  <div style="font-size:20px; font-weight:700; color:{TEXT}; line-height:1.2;
              margin-bottom:6px;">{value}</div>
  <div style="font-size:12px; color:{TEXT_MUTED};">{subline}</div>
</div>"""


col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(_kpi_card(
        "Lowest Cancel Rate",
        f"{best_cancel['buyer_source']} · {best_cancel['cancel_pct']:.1f}%",
        f"avg commission: {best_cancel['commission_pct']:.1f}%",
    ), unsafe_allow_html=True)
with col2:
    st.markdown(_kpi_card(
        "Highest Commission Cost",
        f"{costliest['buyer_source']} · {costliest['commission_pct']:.1f}%",
        f"cancel rate: {costliest['cancel_pct']:.1f}%",
    ), unsafe_allow_html=True)
with col3:
    st.markdown(_kpi_card(
        "Highest Volume",
        f"{highest_vol['buyer_source']} · {int(highest_vol['contracts'])} contracts",
        f"cancel rate: {highest_vol['cancel_pct']:.1f}%",
    ), unsafe_allow_html=True)


# ── SECTION 2: Quadrant scatter ────────────────────────────────────────
st.markdown("**Channel quality vs. cost**")
st.caption(
    "Lower-left = high efficiency (cheap + low cancel). "
    "Size = contract volume."
)

x_mid = float(channel_df["commission_pct"].median())
y_mid = float(channel_df["cancel_pct"].median())

fig = go.Figure()
fig.add_trace(go.Scatter(
    x=channel_df["commission_pct"],
    y=channel_df["cancel_pct"],
    mode="markers+text",
    text=channel_df["buyer_source"],
    textposition="top center",
    textfont=dict(size=11, color=TEXT),
    marker=dict(
        size=channel_df["contracts"],
        sizemode="area",
        sizeref=0.5,
        sizemin=4,
        color=channel_df["cancel_pct"],
        colorscale=[[0, "#5a8c3e"], [0.5, "#f5a623"], [1.0, "#c75a3e"]],
        showscale=True,
        colorbar=dict(title="Cancel %", thickness=12),
        line=dict(width=1.5, color="white"),
    ),
    hovertemplate=(
        "<b>%{text}</b><br>"
        "Commission: %{x:.2f}%<br>"
        "Cancel: %{y:.1f}%<br>"
        "Contracts: %{marker.size}<extra></extra>"
    ),
    showlegend=False,
))

fig.add_hline(y=y_mid, line_dash="dot", line_color="#d1d1d6", line_width=1)
fig.add_vline(x=x_mid, line_dash="dot", line_color="#d1d1d6", line_width=1)

_qa = dict(showarrow=False, font=dict(size=10, color=TEXT_MUTED),
           xref="paper", yref="paper")
fig.add_annotation(x=0.02, y=0.04, text="High efficiency",
                   xanchor="left",  yanchor="bottom", **_qa)
fig.add_annotation(x=0.98, y=0.96, text="Low efficiency",
                   xanchor="right", yanchor="top",    **_qa)
fig.add_annotation(x=0.98, y=0.04, text="Cheap, risky",
                   xanchor="right", yanchor="bottom", **_qa)
fig.add_annotation(x=0.02, y=0.96, text="Expensive, safe",
                   xanchor="left",  yanchor="top",    **_qa)

fig.update_layout(
    plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
    font=dict(family="sans-serif", color=TEXT),
    xaxis=dict(title="Avg commission rate (%)", gridcolor="#e8e8e8"),
    yaxis=dict(title="Cancel rate (%)", gridcolor="#e8e8e8"),
    margin=dict(t=30, b=50, l=10, r=60),
    height=420,
)
st.plotly_chart(fig, use_container_width=True)


# ── SECTION 3: Channel detail table ────────────────────────────────────
st.markdown("**Channel detail**")
display_df = (
    channel_df[["buyer_source", "contracts", "closed_contracts",
                 "cancel_pct", "commission_pct", "revenue_M"]]
    .sort_values("cancel_pct")
    .copy()
)
st.dataframe(
    display_df,
    use_container_width=True,
    hide_index=True,
    height=350,
    column_config={
        "buyer_source":     st.column_config.TextColumn("Channel"),
        "contracts":        st.column_config.NumberColumn("Contracts", format="%d"),
        "closed_contracts": st.column_config.NumberColumn("Closed", format="%d"),
        "cancel_pct":       st.column_config.NumberColumn("Cancel rate %",
                                                           format="%.1f%%"),
        "commission_pct":   st.column_config.NumberColumn("Avg commission %",
                                                           format="%.1f%%"),
        "revenue_M":        st.column_config.NumberColumn("Revenue $M",
                                                           format="$%.1f"),
    },
)

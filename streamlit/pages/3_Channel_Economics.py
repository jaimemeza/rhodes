import plotly.graph_objects as go
import streamlit as st

from utils.snowflake import get_snowflake_connection
from utils.queries import fetch_channel_economics

st.set_page_config(page_title="Channel Economics · Rhodes", layout="wide")

GREEN       = "#5a8c3e"
AMBER       = "#c75a3e"
GRAY        = "#8e8e93"
TEXT        = "#1c1c1e"
TEXT_MUTED  = "#6e6e73"

st.title("Channel Economics")
st.caption(
    "Cost vs. quality by acquisition channel — commission rate (x) against "
    "cancel rate (y). Bubble size = YTD closed revenue. "
    "Lower-left is ideal: cheap and reliable."
)

conn = get_snowflake_connection()
df   = fetch_channel_economics(conn)

if df.empty:
    st.error("No data returned from mart_channel_economics.")
    st.stop()

df = df.copy()
df["cancelled_contracts"] = df["cancelled_contracts"].fillna(0).astype(int)

med_comm   = float(df["avg_commission_rate"].median())
med_cancel = float(df["cancel_rate"].median())


def _color(row):
    if row["cancel_rate"] <= med_cancel and row["avg_commission_rate"] <= med_comm:
        return GREEN
    if row["cancel_rate"] > med_cancel:
        return AMBER
    return GRAY


df["_color"]  = df.apply(_color, axis=1)
df["_bubble"] = (
    (df["total_contract_value"] / df["total_contract_value"].max()) ** 0.5 * 50 + 12
)


# ── ZONE 1: Scatter (hero) ──────────────────────────────────────────────
fig = go.Figure()
fig.add_trace(go.Scatter(
    x=df["avg_commission_rate"] * 100,
    y=df["cancel_rate"] * 100,
    mode="markers+text",
    text=df["buyer_source"],
    textposition="top center",
    textfont=dict(size=11, color=TEXT),
    marker=dict(
        size=df["_bubble"],
        color=df["_color"],
        opacity=0.85,
        line=dict(width=1.5, color="#ffffff"),
    ),
    customdata=list(zip(
        df["buyer_source"],
        df["contracts"].astype(int),
        df["closed_contracts"].astype(int),
        df["cancelled_contracts"],
        df["avg_commission_rate"] * 100,
        df["cancel_rate"] * 100,
        df["total_contract_value"] / 1_000_000,
        df["total_commission_paid"] / 1_000,
    )),
    hovertemplate=(
        "<b>%{customdata[0]}</b><br>"
        "Commission: %{customdata[4]:.1f}%<br>"
        "Cancel rate: %{customdata[5]:.1f}%<br>"
        "Contracts: %{customdata[1]} total · "
        "%{customdata[2]} closed · %{customdata[3]} cancelled<br>"
        "Revenue: $%{customdata[6]:.1f}M · "
        "Commission paid: $%{customdata[7]:.0f}k<br>"
        "<extra></extra>"
    ),
    showlegend=False,
))

fig.add_hline(
    y=med_cancel * 100,
    line_dash="dash", line_color="#d1d1d6", line_width=1,
    annotation_text=f"Median cancel {med_cancel*100:.1f}%",
    annotation_position="top right",
    annotation_font_size=11,
    annotation_font_color=TEXT_MUTED,
)
fig.add_vline(
    x=med_comm * 100,
    line_dash="dash", line_color="#d1d1d6", line_width=1,
    annotation_text=f"Median commission {med_comm*100:.1f}%",
    annotation_position="top right",
    annotation_font_size=11,
    annotation_font_color=TEXT_MUTED,
)

fig.update_layout(
    plot_bgcolor="#ffffff",
    paper_bgcolor="#ffffff",
    font=dict(family="sans-serif", color=TEXT),
    xaxis=dict(
        title="Avg commission rate (%)",
        ticksuffix="%",
        gridcolor="#e8e8e8",
    ),
    yaxis=dict(
        title="Cancel rate (%)",
        ticksuffix="%",
        rangemode="tozero",
        gridcolor="#e8e8e8",
    ),
    margin=dict(t=30, b=50, l=60, r=20),
    height=440,
)

st.plotly_chart(fig, use_container_width=True)


# ── ZONE 2: Commission rate + cancel rate bars ──────────────────────────
df_s = df.sort_values("total_contract_value", ascending=False)

col_left, col_right = st.columns(2)

with col_left:
    st.caption("Avg commission rate by channel · sorted by revenue volume")
    fig_comm = go.Figure(go.Bar(
        x=df_s["buyer_source"],
        y=df_s["avg_commission_rate"] * 100,
        marker_color=df_s["_color"].tolist(),
        hovertemplate="<b>%{x}</b><br>Commission: %{y:.1f}%<extra></extra>",
    ))
    fig_comm.update_layout(
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
        font=dict(family="sans-serif", color=TEXT),
        xaxis=dict(title=None, tickfont=dict(size=12)),
        yaxis=dict(
            title="Commission rate (%)",
            ticksuffix="%",
            gridcolor="#e8e8e8",
        ),
        margin=dict(t=10, b=20, l=10, r=10),
        height=300,
    )
    st.plotly_chart(fig_comm, use_container_width=True)

with col_right:
    st.caption("Cancel rate by channel · sorted by revenue volume")
    fig_cancel = go.Figure(go.Bar(
        x=df_s["buyer_source"],
        y=df_s["cancel_rate"] * 100,
        marker_color=df_s["_color"].tolist(),
        hovertemplate="<b>%{x}</b><br>Cancel rate: %{y:.1f}%<extra></extra>",
    ))
    fig_cancel.update_layout(
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
        font=dict(family="sans-serif", color=TEXT),
        xaxis=dict(title=None, tickfont=dict(size=12)),
        yaxis=dict(
            title="Cancel rate (%)",
            ticksuffix="%",
            rangemode="tozero",
            gridcolor="#e8e8e8",
        ),
        margin=dict(t=10, b=20, l=10, r=10),
        height=300,
    )
    st.plotly_chart(fig_cancel, use_container_width=True)


# ── ZONE 3: Detail table ────────────────────────────────────────────────
DISPLAY_COLS = [
    "buyer_source", "contracts", "closed_contracts", "cancelled_contracts",
    "cancel_rate", "avg_commission_rate", "avg_days_to_close",
    "avg_contract_price", "avg_upgrade_capture_pct",
    "total_contract_value", "total_commission_paid",
]
with st.expander("Show detail table", expanded=False):
    display_df = df[DISPLAY_COLS].copy()
    for col in ["cancel_rate", "avg_commission_rate", "avg_upgrade_capture_pct"]:
        display_df[col] = display_df[col] * 100
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "buyer_source":
                st.column_config.TextColumn("Channel"),
            "contracts":
                st.column_config.NumberColumn("Contracts", format="%d"),
            "closed_contracts":
                st.column_config.NumberColumn("Closed", format="%d"),
            "cancelled_contracts":
                st.column_config.NumberColumn("Cancelled", format="%d"),
            "cancel_rate":
                st.column_config.NumberColumn("Cancel rate", format="%.1f%%"),
            "avg_commission_rate":
                st.column_config.NumberColumn("Avg commission", format="%.1f%%"),
            "avg_days_to_close":
                st.column_config.NumberColumn("Days to close", format="%.0f"),
            "avg_contract_price":
                st.column_config.NumberColumn("Avg price", format="$%.0f"),
            "avg_upgrade_capture_pct":
                st.column_config.NumberColumn("Upgrade capture", format="%.1f%%"),
            "total_contract_value":
                st.column_config.NumberColumn("Revenue", format="$%.0f"),
            "total_commission_paid":
                st.column_config.NumberColumn("Commission paid", format="$%.0f"),
        },
    )

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from utils.snowflake import get_snowflake_connection
from utils.queries import fetch_region_month, fetch_forecast_results

st.set_page_config(page_title="Forecast · Rhodes", layout="wide")

GREEN       = "#5a8c3e"
GREEN_LIGHT = "#7aa55c"
AMBER       = "#c75a3e"
GRAY        = "#8e8e93"
BLUE        = "#2563eb"  # noqa: F841 — reserved for future use
SURFACE     = "#f5f5f7"
TEXT        = "#1c1c1e"
TEXT_MUTED  = "#6e6e73"

REGION_COLOR = {
    "Rio Grande Valley": GREEN,
    "South Texas":       GRAY,
    "Coastal Bend":      AMBER,
}
REGION_FILL = {
    "Rio Grande Valley": "rgba(90,140,62,0.15)",
    "South Texas":       "rgba(142,142,147,0.15)",
    "Coastal Bend":      "rgba(199,90,62,0.15)",
}

FORECAST_START_MS = pd.Timestamp("2024-09-15").timestamp() * 1000
FORECAST_END_MS   = pd.Timestamp("2025-01-01").timestamp() * 1000

st.title("Forecast")
st.caption(
    "Snowflake Cortex FORECAST — trained on 21 months of closing history. "
    "Projections cover Oct–Dec 2024. Confidence bands reflect model uncertainty; "
    "wider bands indicate lower confidence."
)

conn    = get_snowflake_connection()
hist_df = fetch_region_month(conn)
fore_df = fetch_forecast_results(conn)

if hist_df.empty:
    st.error("No data returned from mart_region_month.")
    st.stop()
if fore_df.empty:
    st.warning(
        "Forecast tables are empty. "
        "Run `sql/setup/02_cortex_forecast.sql` to generate Cortex predictions."
    )
    st.stop()

hist_df                  = hist_df.copy()
hist_df["month_start"]   = pd.to_datetime(hist_df["month_start"])
hist_df["year"]          = hist_df["month_start"].dt.year

targets = (
    hist_df[["region", "sales_target_units"]]
    .drop_duplicates("region")
    .set_index("region")["sales_target_units"]
)

ALL_REGIONS = ["Coastal Bend", "Rio Grande Valley", "South Texas"]


def _jan_sep_2024(region: str) -> int:
    mask = (hist_df["region"] == region) & (hist_df["year"] == 2024)
    return int(hist_df[mask]["contracts_closed"].sum())


def _oct_dec_vol(region: str) -> int:
    sub = fore_df[(fore_df["metric"] == "volume") & (fore_df["region"] == region)]
    return round(float(sub["forecast"].sum()))


def _add_conf_band(fig, x, upper, lower, fill_color):
    """Shaded confidence band: add upper trace first, lower fills to it."""
    fig.add_trace(go.Scatter(
        x=x, y=upper,
        mode="lines", line=dict(width=0),
        showlegend=False,
    ))
    fig.add_trace(go.Scatter(
        x=x, y=lower,
        fill="tonexty", fillcolor=fill_color,
        mode="lines", line=dict(width=0),
        showlegend=False,
    ))


tab1, tab2 = st.tabs(["Contract Volume", "Close Time"])

# ══════════════════════════════════════════════════════════════════════
# TAB 1 — Contract Volume
# ══════════════════════════════════════════════════════════════════════
with tab1:
    vol_fore = fore_df[fore_df["metric"] == "volume"].copy()
    vol_fore["forecast_month"] = pd.to_datetime(vol_fore["forecast_month"])

    # ── Section A: Summary cards ────────────────────────────────────────
    card_cols = st.columns(3)
    for i, region in enumerate(ALL_REGIONS):
        jan_sep  = _jan_sep_2024(region)
        oct_dec  = _oct_dec_vol(region)
        year_end = jan_sep + oct_dec
        target   = int(targets.get(region, 0))
        gap      = year_end - target
        g_color  = GREEN_LIGHT if gap >= 0 else AMBER
        g_label  = (
            f"+{gap} units above target" if gap >= 0
            else f"−{abs(gap)} units to target"
        )
        with card_cols[i]:
            st.markdown(f"""
<div style="background:{SURFACE}; border-radius:10px; padding:16px 14px;
            min-height:155px;">
  <div style="font-size:13px; color:{TEXT_MUTED}; margin-bottom:6px;">
    {region}</div>
  <div style="font-size:36px; font-weight:700; color:{TEXT}; line-height:1;
              margin-bottom:4px;">~{year_end}</div>
  <div style="font-size:13px; color:{TEXT_MUTED}; margin-bottom:6px;">
    est. year-end closings</div>
  <div style="font-size:13px; font-weight:600; color:{g_color};
              margin-bottom:8px;">{g_label}</div>
  <hr style="border:none; border-top:1px solid #e5e5ea; margin:6px 0;">
  <div style="font-size:12px; color:{TEXT_MUTED}; line-height:1.7;">
    Oct–Dec Cortex forecast: +{oct_dec} closings<br>
    Jan–Sep actual: {jan_sep} closings
  </div>
</div>""", unsafe_allow_html=True)

    with st.expander("How this is calculated", expanded=False):
        st.write(
            "Jan–Sep actual closings (from mart_region_month) plus Cortex FORECAST "
            "Oct–Dec projection. Cortex was trained on 21 months of monthly closing "
            "history per region. Coastal Bend has very wide confidence intervals due "
            "to low volume (avg ~4 closings/month)."
        )

    # ── Section B: Time series with forecast overlay ────────────────────
    selected_regions = st.multiselect(
        "Regions",
        options=ALL_REGIONS,
        default=ALL_REGIONS,
    )

    fig = go.Figure()
    for region in selected_regions:
        color = REGION_COLOR.get(region, GRAY)
        fill  = REGION_FILL.get(region, "rgba(142,142,147,0.15)")
        h = hist_df[hist_df["region"] == region].sort_values("month_start")
        f = vol_fore[vol_fore["region"] == region].sort_values("forecast_month")

        fig.add_trace(go.Scatter(
            name=f"{region} (actual)",
            x=h["month_start"], y=h["contracts_closed"],
            mode="lines+markers",
            line=dict(color=color, width=2),
            marker=dict(size=5),
        ))
        if not f.empty:
            _add_conf_band(fig, f["forecast_month"],
                           f["upper_bound"], f["lower_bound"], fill)
            fig.add_trace(go.Scatter(
                name=f"{region} (forecast)",
                x=f["forecast_month"], y=f["forecast"],
                mode="lines+markers",
                line=dict(dash="dash", color=color, width=2),
                marker=dict(symbol="diamond", size=7),
            ))

        if region in targets.index:
            monthly = float(targets[region]) / 12
            x_end   = (f["forecast_month"].max() if not f.empty
                       else h["month_start"].max())
            fig.add_trace(go.Scatter(
                name=f"{region} monthly target pace",
                x=[h["month_start"].min(), x_end],
                y=[monthly, monthly],
                mode="lines",
                line=dict(dash="dot", color=color, width=1),
                opacity=0.4,
                showlegend=False,
            ))

    fig.add_vrect(
        x0=FORECAST_START_MS, x1=FORECAST_END_MS,
        fillcolor="rgba(240,244,255,0.6)",
        layer="below", line_width=0,
        annotation_text="Forecast →",
        annotation_position="top left",
        annotation_font_size=11,
        annotation_font_color=TEXT_MUTED,
    )
    fig.update_layout(
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
        font=dict(family="sans-serif", color=TEXT),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="left", x=0),
        xaxis=dict(title=None, gridcolor="#e8e8e8"),
        yaxis=dict(title="Monthly closings", gridcolor="#e8e8e8"),
        margin=dict(t=80, b=20, l=10, r=10),
        height=420,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        "Dashed lines = Cortex forecast. Shaded band = confidence interval. "
        "Dotted horizontal = monthly target pace (annual ÷ 12)."
    )

    # ── Section C: Methodology comparison table ─────────────────────────
    st.caption("Linear pace projection vs. Cortex forecast vs. annual target")
    rows = []
    for region in ALL_REGIONS:
        jan_sep = _jan_sep_2024(region)
        oct_dec = _oct_dec_vol(region)
        target  = int(targets.get(region, 0))
        cortex  = jan_sep + oct_dec
        rows.append({
            "Region":                 region,
            "Jan–Sep Actual":         jan_sep,
            "Linear Pace (×12/9)":    round(jan_sep * 12 / 9),
            "Cortex Year-End Est.":   cortex,
            "Annual Target":          target,
            "Gap (Cortex)":           cortex - target,
        })
    st.dataframe(
        pd.DataFrame(rows),
        use_container_width=True,
        hide_index=True,
        height=175,
        column_config={
            "Region":
                st.column_config.TextColumn("Region"),
            "Jan–Sep Actual":
                st.column_config.NumberColumn("Jan–Sep Actual", format="%d"),
            "Linear Pace (×12/9)":
                st.column_config.NumberColumn("Linear Pace (×12/9)", format="%d"),
            "Cortex Year-End Est.":
                st.column_config.NumberColumn("Cortex Year-End", format="%d"),
            "Annual Target":
                st.column_config.NumberColumn("Annual Target", format="%d"),
            "Gap (Cortex)":
                st.column_config.NumberColumn("Gap (Cortex)", format="%+d"),
        },
    )

# ══════════════════════════════════════════════════════════════════════
# TAB 2 — Close Time
# ══════════════════════════════════════════════════════════════════════
with tab2:
    st.caption(
        "Average days from contract to close, per region. Longer close times "
        "signal buyer financing stress or operational friction. "
        "Coastal Bend excluded — insufficient monthly volume for a reliable "
        "close-time forecast (avg 3.7 closings/month produces zero-width "
        "confidence intervals)."
    )

    close_hist = hist_df[hist_df["avg_days_to_close"].notna()].copy()
    close_fore = fore_df[
        (fore_df["metric"] == "days_to_close") &
        (fore_df["region"] != "Coastal Bend")
    ].copy()
    close_fore["forecast_month"] = pd.to_datetime(close_fore["forecast_month"])

    fig2 = go.Figure()
    for region in ["Rio Grande Valley", "South Texas"]:
        color = REGION_COLOR.get(region, GRAY)
        fill  = REGION_FILL.get(region, "rgba(142,142,147,0.15)")
        h = close_hist[close_hist["region"] == region].sort_values("month_start")
        f = close_fore[close_fore["region"] == region].sort_values("forecast_month")

        fig2.add_trace(go.Scatter(
            name=f"{region} (actual)",
            x=h["month_start"], y=h["avg_days_to_close"],
            mode="lines+markers",
            line=dict(color=color, width=2),
            marker=dict(size=5),
        ))
        if not f.empty:
            _add_conf_band(fig2, f["forecast_month"],
                           f["upper_bound"], f["lower_bound"], fill)
            fig2.add_trace(go.Scatter(
                name=f"{region} (forecast)",
                x=f["forecast_month"], y=f["forecast"],
                mode="lines+markers",
                line=dict(dash="dash", color=color, width=2),
                marker=dict(symbol="diamond", size=7),
            ))

    fig2.add_vline(
        x=FORECAST_START_MS,
        line_dash="dot", line_color=GRAY,
        annotation_text="Forecast →",
        annotation_position="top right",
        annotation_font_size=11,
        annotation_font_color=TEXT_MUTED,
    )
    fig2.update_layout(
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
        font=dict(family="sans-serif", color=TEXT),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="left", x=0),
        xaxis=dict(title=None, gridcolor="#e8e8e8"),
        yaxis=dict(title="Avg days to close", range=[80, 180],
                   gridcolor="#e8e8e8"),
        margin=dict(t=80, b=20, l=10, r=10),
        height=380,
    )
    st.plotly_chart(fig2, use_container_width=True)

    for region in ["Rio Grande Valley", "South Texas"]:
        h = close_hist[close_hist["region"] == region].sort_values("month_start")
        f = close_fore[close_fore["region"] == region].sort_values("forecast_month")
        if h.empty or f.empty:
            continue
        oct_row = f[f["forecast_month"] == f["forecast_month"].min()]
        if oct_row.empty:
            continue
        recent_avg   = float(
            h[h["month_start"].dt.year == 2024]["avg_days_to_close"].mean()
        )
        forecast_oct = float(oct_row.iloc[0]["forecast"])
        delta        = forecast_oct - recent_avg
        if delta < -3:
            direction_text = f"improved by {abs(delta):.0f} days"
        elif delta > 3:
            direction_text = f"worsened by {abs(delta):.0f} days"
        else:
            direction_text = "remained stable"
        st.info(
            f"**{region}** close times have {direction_text} — Cortex projects "
            f"approximately {forecast_oct:.0f} days in Oct 2024, compared to a "
            f"2024 average of {recent_avg:.0f} days."
        )

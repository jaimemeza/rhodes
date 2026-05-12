import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st
from sklearn.linear_model import LinearRegression

from utils.postgres import get_connection
from utils.queries import fetch_region_month
from utils.styles import apply_global_styles

st.set_page_config(page_title="Forecast · Rhodes", layout="wide",
                   initial_sidebar_state="collapsed")
apply_global_styles()

GREEN       = "#5a8c3e"
GREEN_LIGHT = "#7aa55c"
AMBER       = "#c75a3e"
GRAY        = "#8e8e93"
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

ALL_REGIONS = ["Coastal Bend", "Rio Grande Valley", "South Texas"]
FORECAST_PERIODS = 3


def build_forecast(df: pd.DataFrame, region: str) -> pd.DataFrame:
    sub = df[df["region"] == region].sort_values("month_start").copy()
    sub["t"] = np.arange(len(sub))
    X = sub[["t"]].values
    y = sub["contracts_closed"].astype(float).values
    model = LinearRegression().fit(X, y)
    future_t = np.arange(len(sub), len(sub) + FORECAST_PERIODS).reshape(-1, 1)
    last_date = sub["month_start"].max()
    future_dates = pd.date_range(
        start=last_date + pd.DateOffset(months=1),
        periods=FORECAST_PERIODS, freq="MS"
    )
    forecast = model.predict(future_t)
    residuals = y - model.predict(X)
    std = residuals.std()
    return pd.DataFrame({
        "region":         region,
        "forecast_month": future_dates,
        "forecast":       np.maximum(forecast, 0),
        "upper_bound":    np.maximum(forecast + 1.96 * std, 0),
        "lower_bound":    np.maximum(forecast - 1.96 * std, 0),
    })


conn    = get_connection()
hist_df = fetch_region_month(conn)

if hist_df.empty:
    st.error("No data returned from mart_region_month.")
    st.stop()

hist_df["month_start"] = pd.to_datetime(hist_df["month_start"])
hist_df["year"]        = hist_df["month_start"].dt.year

targets = (
    hist_df[["region", "sales_target_units"]]
    .drop_duplicates("region")
    .set_index("region")["sales_target_units"]
)

fore_df = pd.concat([build_forecast(hist_df, r) for r in ALL_REGIONS])

st.title("Forecast")
st.caption(
    "Linear regression forecast trained on closing history per region. "
    f"Projections cover the next {FORECAST_PERIODS} months. "
    "Confidence bands show 95% confidence interval."
)

tab1, tab2 = st.tabs(["Contract Volume", "Close Time"])

with tab1:
    card_cols = st.columns(3)
    for i, region in enumerate(ALL_REGIONS):
        ytd      = int(hist_df[(hist_df["region"] == region) &
                               (hist_df["year"] == hist_df["year"].max())]
                       ["contracts_closed"].sum())
        forecast = int(fore_df[fore_df["region"] == region]["forecast"].sum().round())
        year_end = ytd + forecast
        target   = int(targets.get(region, 0))
        gap      = year_end - target
        g_color  = GREEN_LIGHT if gap >= 0 else AMBER
        g_label  = (f"+{gap} units above target" if gap >= 0
                    else f"−{abs(gap)} units to target")
        with card_cols[i]:
            st.markdown(f"""
<div style="background:{SURFACE}; border-radius:10px; padding:14px 16px;
            min-height:155px;">
  <div style="font-size:12px; color:{TEXT_MUTED}; margin-bottom:6px;">
    {region}</div>
  <div style="font-size:28px; font-weight:700; color:{TEXT}; line-height:1;
              margin-bottom:4px;">~{year_end}</div>
  <div style="font-size:12px; color:{TEXT_MUTED}; margin-bottom:6px;">
    est. year-end closings</div>
  <div style="font-size:13px; font-weight:600; color:{g_color};
              margin-bottom:8px;">{g_label}</div>
  <hr style="border:none; border-top:1px solid #e5e5ea; margin:6px 0;">
  <div style="font-size:12px; color:{TEXT_MUTED}; line-height:1.7;">
    Forecast next {FORECAST_PERIODS}mo: +{forecast} closings<br>
    YTD actual: {ytd} closings
  </div>
</div>""", unsafe_allow_html=True)

    selected_regions = st.multiselect(
        "Regions", options=ALL_REGIONS, default=ALL_REGIONS
    )

    fig = go.Figure()
    for region in selected_regions:
        color = REGION_COLOR.get(region, GRAY)
        fill  = REGION_FILL.get(region, "rgba(142,142,147,0.15)")
        h = hist_df[hist_df["region"] == region].sort_values("month_start")
        f = fore_df[fore_df["region"] == region].sort_values("forecast_month")

        fig.add_trace(go.Scatter(
            name=f"{region} (actual)",
            x=h["month_start"], y=h["contracts_closed"],
            mode="lines+markers",
            line=dict(color=color, width=2),
            marker=dict(size=5),
        ))
        fig.add_trace(go.Scatter(
            x=f["forecast_month"], y=f["upper_bound"],
            mode="lines", line=dict(width=0), showlegend=False,
        ))
        fig.add_trace(go.Scatter(
            x=f["forecast_month"], y=f["lower_bound"],
            fill="tonexty", fillcolor=fill,
            mode="lines", line=dict(width=0), showlegend=False,
        ))
        fig.add_trace(go.Scatter(
            name=f"{region} (forecast)",
            x=f["forecast_month"], y=f["forecast"],
            mode="lines+markers",
            line=dict(dash="dash", color=color, width=2),
            marker=dict(symbol="diamond", size=7),
        ))

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
    st.caption("Dashed = forecast. Shaded band = 95% confidence interval.")

with tab2:
    fig2 = go.Figure()
    for region in ["Rio Grande Valley", "South Texas"]:
        color = REGION_COLOR.get(region, GRAY)
        h = hist_df[hist_df["region"] == region].sort_values("month_start")
        fig2.add_trace(go.Scatter(
            name=region,
            x=h["month_start"], y=h["avg_days_to_close"],
            mode="lines+markers",
            line=dict(color=color, width=2),
            marker=dict(size=5),
        ))
    fig2.update_layout(
        plot_bgcolor="#ffffff", paper_bgcolor="#ffffff",
        font=dict(family="sans-serif", color=TEXT),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="left", x=0),
        xaxis=dict(title=None, gridcolor="#e8e8e8"),
        yaxis=dict(title="Avg days to close", gridcolor="#e8e8e8"),
        margin=dict(t=80, b=20, l=10, r=10),
        height=380,
    )
    st.plotly_chart(fig2, use_container_width=True)
    st.caption("Coastal Bend excluded — insufficient monthly volume for reliable trend.")

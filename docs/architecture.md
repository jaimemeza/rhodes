# Architecture

## Data flow

```text
seed_data/
  Homebuilder_Sales.csv          (600 rows, raw contract records)
  Regional_Manager_Lookup.xlsx   (region → manager mapping)
        │
        ▼  ingestion/load_raw.py (COPY INTO via temp stage)
RHODES.RAW.HOMEBUILDER_SALES
        │
        ▼  dbt run (RHODES_TRANSFORMER / RHODES_TRANSFORM_WH)
RHODES.STAGING
  stg_homebuilder_sales          view — type casts, rename, derive flags
  stg_regional_manager           view — Excel lookup normalized to CSV seed
        │
        ▼
RHODES.ANALYTICS
  ── core ──
  dim_region                     table — 3 regions + manager
  dim_community                  table — community × region lookup
  dim_consultant                 table — unique consultants
  fct_home_sales                 table — one row per contract, enriched flags
                                         (is_closed, is_cancelled, is_under_contract,
                                          days_to_close, estimated_margin_pct,
                                          upgrade_capture_pct)
  ── aggregates ──
  mart_region_year               table — YoY analysis per region × year
  mart_region_month              table — monthly time series (Cortex FORECAST input)
  mart_channel_economics         table — buyer source cost vs. quality
  mart_consultant_performance    table — individual YoY performance
  mart_consultant_region         table — consultant × region drill-down
  ── Cortex results ──
  forecast_results               table — volume forecast Oct–Dec 2024
  close_time_forecast_results    table — close-time forecast Oct–Dec 2024
        │
        ▼  Streamlit (RHODES_READER / RHODES_BI_WH)
Dashboard pages
  1_Region_Overview              KPI tiles, YoY bar chart, quarterly cancel trend
  2_Forecast                     Cortex FORECAST volume + close-time projections
  3_Channel_Economics            Commission vs. cancel quadrant, channel table
  4_Consultants                  Leaderboard, YoY scatter, regional drill-down
  5_Ask_a_Question               Cortex COMPLETE with keyword-routed context
```

## Role model

Three least-privilege roles follow the load / transform / read separation:

- **RHODES_LOADER** — write access to `RAW` only (used by the ingestion script).
- **RHODES_TRANSFORMER** — read `RAW`, full DDL+DML on `STAGING` and `ANALYTICS` (used by dbt).
- **RHODES_READER** — read `ANALYTICS`, `SNOWFLAKE.CORTEX_USER` database role (used by Streamlit).

ML model creation (`SNOWFLAKE.ML.FORECAST`) requires ACCOUNTADMIN. In production, `CREATE SNOWFLAKE.ML.FORECAST ON SCHEMA` should be granted to RHODES_TRANSFORMER to remove that dependency.

## dbt model conventions

- Staging models are **views** materialized in `RHODES.STAGING`.
- Core and aggregate marts are **tables** materialized in `RHODES.ANALYTICS`.
- Schema routing uses a `generate_schema_name` macro so `+schema: ANALYTICS` in `dbt_project.yml` maps to `RHODES.ANALYTICS` rather than `RHODES.RHODES_ANALYTICS_DEV`.
- All Snowflake identifiers are UPPERCASE in SQL; dbt model file names are lowercase.

## YoY methodology

2024 data ends Sep 30. Rather than annualizing, all year-over-year headlines compare Jan–Sep 2024 against Jan–Sep 2023 directly (`same_period_closed_prior_year` in `mart_region_year`). Annualized columns exist in the mart for reference but are not used in headline KPIs.

## Margin proxy

The dataset has no construction cost column. `estimated_margin_pct` is defined as `(contract_price - commission_paid) / contract_price`. This is documented as a proxy wherever it appears in the dashboard.

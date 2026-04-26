-- =============================================================================
-- Rhodes Pipeline · Cortex FORECAST setup (idempotent)
-- Run as ACCOUNTADMIN — ML model creation requires privileges beyond the
-- standard RHODES_TRANSFORMER grants. For production, grant CREATE
-- SNOWFLAKE.ML.FORECAST ON SCHEMA to RHODES_TRANSFORMER explicitly.
-- Creates two ML models + stores results in RHODES.ANALYTICS
-- =============================================================================
USE ROLE ACCOUNTADMIN;
USE WAREHOUSE RHODES_TRANSFORM_WH;
USE DATABASE RHODES;
USE SCHEMA ANALYTICS;

-- ── Volume forecast ──────────────────────────────────────────────────────────
-- Train on 21 months of monthly closed contracts per region (Jan 2023 – Sep 2024)

CREATE OR REPLACE SNOWFLAKE.ML.FORECAST region_volume_forecast(
    INPUT_DATA => SYSTEM$QUERY_REFERENCE('
        SELECT region, month_start, contracts_closed
        FROM RHODES.ANALYTICS.MART_REGION_MONTH
        ORDER BY region, month_start
    '),
    SERIES_COLNAME   => 'REGION',
    TIMESTAMP_COLNAME => 'MONTH_START',
    TARGET_COLNAME   => 'CONTRACTS_CLOSED'
);

-- Generate 3-month forecast (Oct, Nov, Dec 2024)
CALL region_volume_forecast!FORECAST(
    FORECASTING_PERIODS => 3,
    CONFIG_OBJECT => {'prediction_interval': 0.9}
);

CREATE OR REPLACE TABLE RHODES.ANALYTICS.FORECAST_RESULTS AS
SELECT
    series::varchar    AS region,
    ts::date           AS forecast_month,
    forecast::float    AS forecast,
    lower_bound::float AS lower_bound,
    upper_bound::float AS upper_bound
FROM TABLE(result_scan(last_query_id()));

-- ── Close-time forecast ──────────────────────────────────────────────────────
-- Train on avg_days_to_close per region.
-- Coastal Bend included in training but excluded from dashboard display
-- (3-4 closings/month → near-zero confidence intervals → misleading).

CREATE OR REPLACE SNOWFLAKE.ML.FORECAST region_close_time_forecast(
    INPUT_DATA => SYSTEM$QUERY_REFERENCE('
        SELECT region, month_start, avg_days_to_close
        FROM RHODES.ANALYTICS.MART_REGION_MONTH
        WHERE avg_days_to_close IS NOT NULL
        ORDER BY region, month_start
    '),
    SERIES_COLNAME   => 'REGION',
    TIMESTAMP_COLNAME => 'MONTH_START',
    TARGET_COLNAME   => 'AVG_DAYS_TO_CLOSE'
);

CALL region_close_time_forecast!FORECAST(
    FORECASTING_PERIODS => 3,
    CONFIG_OBJECT => {'prediction_interval': 0.9}
);

CREATE OR REPLACE TABLE RHODES.ANALYTICS.CLOSE_TIME_FORECAST_RESULTS AS
SELECT
    series::varchar    AS region,
    ts::date           AS forecast_month,
    forecast::float    AS forecast,
    lower_bound::float AS lower_bound,
    upper_bound::float AS upper_bound
FROM TABLE(result_scan(last_query_id()));

-- ── Verify ───────────────────────────────────────────────────────────────────
SELECT 'volume' AS metric, * FROM RHODES.ANALYTICS.FORECAST_RESULTS
UNION ALL
SELECT 'days_to_close', * FROM RHODES.ANALYTICS.CLOSE_TIME_FORECAST_RESULTS
ORDER BY metric, region, forecast_month;

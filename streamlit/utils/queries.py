import pandas as pd
import streamlit as st


@st.cache_data(ttl=600)
def fetch_session_info(_conn) -> pd.DataFrame:
    """Returns CURRENT_USER, CURRENT_ROLE, CURRENT_WAREHOUSE, CURRENT_DATABASE for the active session."""
    cur = _conn.cursor()
    try:
        cur.execute("""
            SELECT
                CURRENT_USER()      AS "USER",
                CURRENT_ROLE()      AS "ROLE",
                CURRENT_WAREHOUSE() AS "WAREHOUSE",
                CURRENT_DATABASE()  AS "DATABASE"
        """)
        cols = [c[0] for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)
    finally:
        cur.close()


@st.cache_data(ttl=600)
def fetch_region_year(_conn) -> pd.DataFrame:
    """Returns mart_region_year, sorted alphabetically by region then year."""
    query = """
        select
            region,
            contract_year,
            contracts,
            contracts_closed,
            contracts_cancelled,
            cancel_rate,
            contracts_annualized,
            contracts_closed_annualized,
            avg_contract_price,
            avg_days_to_close,
            avg_estimated_margin_pct,
            avg_upgrade_capture_pct,
            avg_commission_rate,
            sales_target_units,
            margin_target_pct,
            target_attainment_annualized_pct,
            target_attainment_ytd_pct,
            margin_attainment_delta,
            prior_year_closed_annualized,
            closed_yoy_delta,
            closed_yoy_pct,
            cancel_rate_yoy_delta,
            annualization_factor,
            same_period_closed_prior_year,
            same_period_yoy_pct
        from rhodes.analytics.mart_region_year
        order by region, contract_year
    """
    cur = _conn.cursor()
    try:
        cur.execute(query)
        cols = [c[0].lower() for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)
    finally:
        cur.close()


@st.cache_data(ttl=600)
def fetch_pipeline_by_region(_conn) -> pd.DataFrame:
    """
    Returns active pipeline (Under Contract) and YTD closed value per region.
    Queries fct_home_sales directly — not materialized in a mart because
    pipeline state changes frequently in production.
    """
    query = """
        select
            region,
            count_if(is_under_contract)                            as pipeline_contracts,
            sum(iff(is_under_contract, contract_price, 0))         as pipeline_value,
            count_if(is_closed)                                    as closed_contracts,
            sum(iff(is_closed, contract_price, 0))                 as closed_value,
            avg(iff(is_closed, contract_price, null))              as avg_contract_price,
            avg(iff(is_closed, days_to_close, null))               as avg_days_to_close,
            avg(iff(is_closed, upgrade_capture_pct, null))         as avg_upgrade_capture
        from rhodes.analytics.fct_home_sales
        where contract_date < '2024-10-01'
          and year(contract_date) = (
              select year(max(contract_date))
              from rhodes.analytics.fct_home_sales
              where contract_date < '2024-10-01'
          )
        group by region
        order by region
    """
    cur = _conn.cursor()
    try:
        cur.execute(query)
        cols = [c[0].lower() for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)
    finally:
        cur.close()


@st.cache_data(ttl=3600)
def fetch_region_month(_conn) -> pd.DataFrame:
    """Returns mart_region_month for time-series history and forecast input."""
    query = """
        select region, month_start, contracts_closed,
               cancel_rate, avg_days_to_close,
               sales_target_units
        from rhodes.analytics.mart_region_month
        order by region, month_start
    """
    cur = _conn.cursor()
    try:
        cur.execute(query)
        cols = [c[0].lower() for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)
    finally:
        cur.close()


@st.cache_data(ttl=3600)
def fetch_forecast_results(_conn) -> pd.DataFrame:
    """Returns volume and close-time Cortex FORECAST results, unioned."""
    query = """
        select 'volume'        as metric,
               region, forecast_month, forecast,
               lower_bound, upper_bound
        from rhodes.analytics.forecast_results
        union all
        select 'days_to_close' as metric,
               region, forecast_month, forecast,
               lower_bound, upper_bound
        from rhodes.analytics.close_time_forecast_results
        order by metric, region, forecast_month
    """
    cur = _conn.cursor()
    try:
        cur.execute(query)
        cols = [c[0].lower() for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)
    finally:
        cur.close()


@st.cache_data(ttl=600)
def fetch_channel_economics(_conn) -> pd.DataFrame:
    """Returns mart_channel_economics, sorted by total_contract_value descending."""
    query = """
        select
            buyer_source,
            contracts,
            closed_contracts,
            cancelled_contracts,
            cancel_rate,
            avg_commission_rate,
            avg_days_to_close,
            avg_contract_price,
            avg_upgrade_capture_pct,
            total_contract_value,
            total_commission_paid
        from rhodes.analytics.mart_channel_economics
        order by total_contract_value desc
    """
    cur = _conn.cursor()
    try:
        cur.execute(query)
        cols = [c[0].lower() for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)
    finally:
        cur.close()


@st.cache_data(ttl=600)
def fetch_consultant_region(_conn) -> pd.DataFrame:
    """Returns mart_consultant_region for consultant × region drill-down."""
    query = """
        select sales_consultant, region, contracts,
               closed_contracts, cancelled_contracts,
               cancel_rate, avg_days_to_close,
               total_contract_value
        from rhodes.analytics.mart_consultant_region
        order by sales_consultant, closed_contracts desc
    """
    cur = _conn.cursor()
    try:
        cur.execute(query)
        cols = [c[0].lower() for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)
    finally:
        cur.close()


@st.cache_data(ttl=600)
def fetch_consultant_performance(_conn) -> pd.DataFrame:
    """Returns mart_consultant_performance with YoY columns, sorted by closings."""
    query = """
        select sales_consultant, closed_contracts,
               closed_prior_year, closed_current_year,
               closed_current_year_annualized,
               cancel_rate, cancel_rate_prior_year,
               cancel_rate_current_year, cancel_rate_yoy_delta,
               avg_days_to_close, cash_buyer_rate, regions_worked
        from rhodes.analytics.mart_consultant_performance
        order by closed_contracts desc
    """
    cur = _conn.cursor()
    try:
        cur.execute(query)
        cols = [c[0].lower() for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)
    finally:
        cur.close()


@st.cache_data(ttl=600)
def fetch_monthly_closings(_conn) -> pd.DataFrame:
    """Returns monthly closings per region for the two most recent years,
    Jan-Sep only (same-period comparison)."""
    query = """
        select
            region,
            year(month_start)          as year,
            monthname(month_start)     as month_name,
            month(month_start)         as month_num,
            contracts_closed
        from rhodes.analytics.mart_region_month
        where month(month_start) <= 9
          and year(month_start) in (
              select distinct year(month_start)
              from rhodes.analytics.mart_region_month
              where month_start < '2024-10-01'
              order by 1 desc
              limit 2
          )
        order by region, year, month_num
    """
    cur = _conn.cursor()
    try:
        cur.execute(query)
        cols = [c[0].lower() for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)
    finally:
        cur.close()


@st.cache_data(ttl=600)
def fetch_cancel_trend(_conn) -> pd.DataFrame:
    """
    Returns monthly cancellation rate per region for the last 12 months.
    Used for the cancel rate sparklines.
    """
    query = """
        select
            region,
            date_trunc('month', contract_date)::date            as month_start,
            count(*)                                            as contracts,
            count_if(is_cancelled)                              as cancellations,
            count_if(is_cancelled) / nullif(count(*), 0)::float as cancel_rate
        from rhodes.analytics.fct_home_sales
        where year(contract_date) = (
              select year(max(contract_date))
              from rhodes.analytics.fct_home_sales
              where contract_date < '2024-10-01'
          )
          and contract_date < '2024-10-01'
        group by region, date_trunc('month', contract_date)::date
        order by region, month_start
    """
    cur = _conn.cursor()
    try:
        cur.execute(query)
        cols = [c[0].lower() for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)
    finally:
        cur.close()

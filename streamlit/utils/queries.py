import pandas as pd
import streamlit as st


@st.cache_data(ttl=600)
def fetch_session_info(_conn) -> pd.DataFrame:
    """Returns basic connection info for the active Postgres session."""
    cur = _conn.cursor()
    try:
        cur.execute('SELECT current_user AS "USER", current_database() AS "DATABASE"')
        cols = [c[0].lower() for c in cur.description]
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
            cancel_rate::float,
            contracts_annualized,
            contracts_closed_annualized,
            avg_contract_price::float,
            avg_days_to_close::float,
            avg_estimated_margin_pct::float,
            avg_upgrade_capture_pct::float,
            avg_commission_rate::float,
            sales_target_units,
            margin_target_pct::float,
            target_attainment_annualized_pct::float,
            target_attainment_ytd_pct::float,
            margin_attainment_delta::float,
            prior_year_closed_annualized,
            closed_yoy_delta,
            closed_yoy_pct::float,
            cancel_rate_yoy_delta::float,
            annualization_factor::float,
            same_period_closed_prior_year,
            same_period_yoy_pct::float
        from analytics.mart_region_year
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
            count(*) filter (where is_under_contract)                                    as pipeline_contracts,
            sum(case when is_under_contract then contract_price else 0 end)::float      as pipeline_value,
            count(*) filter (where is_closed)                                            as closed_contracts,
            sum(case when is_closed then contract_price else 0 end)::float               as closed_value,
            avg(case when is_closed then contract_price else null end)::float            as avg_contract_price,
            avg(case when is_closed then days_to_close else null end)::float             as avg_days_to_close,
            avg(case when is_closed then upgrade_capture_pct else null end)::float      as avg_upgrade_capture
        from analytics.fct_home_sales
        where contract_date < '2024-10-01'
          and extract(year from contract_date::date) = (
              select extract(year from max(contract_date::date))
              from analytics.fct_home_sales
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
               cancel_rate::float, avg_days_to_close::float,
               sales_target_units
        from analytics.mart_region_month
        order by region, month_start
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
            cancel_rate::float,
            avg_commission_rate::float,
            avg_days_to_close::float,
            avg_contract_price::float,
            avg_upgrade_capture_pct::float,
            total_contract_value::float,
            total_commission_paid::float
        from analytics.mart_channel_economics
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
               cancel_rate::float, avg_days_to_close::float,
               total_contract_value::float
        from analytics.mart_consultant_region
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
               closed_current_year_annualized::float,
               cancel_rate::float, cancel_rate_prior_year::float,
               cancel_rate_current_year::float, cancel_rate_yoy_delta::float,
               avg_days_to_close::float, cash_buyer_rate::float, regions_worked
        from analytics.mart_consultant_performance
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
def fetch_cancel_trend(_conn) -> pd.DataFrame:
    """
    Returns monthly cancellation rate per region for the last 12 months.
    Used for the cancel rate sparklines.
    """
    query = """
        select
            region,
            date_trunc('month', contract_date::date)::date                  as month_start,
            count(*)                                                        as contracts,
            count(*) filter (where is_cancelled)                            as cancellations,
            count(*) filter (where is_cancelled)::float
                / nullif(count(*), 0)                                       as cancel_rate
        from analytics.fct_home_sales
        where extract(year from contract_date::date) = (
              select extract(year from max(contract_date::date))
              from analytics.fct_home_sales
              where contract_date < '2024-10-01'
          )
          and contract_date < '2024-10-01'
        group by region, date_trunc('month', contract_date::date)::date
        order by region, month_start
    """
    cur = _conn.cursor()
    try:
        cur.execute(query)
        cols = [c[0].lower() for c in cur.description]
        return pd.DataFrame(cur.fetchall(), columns=cols)
    finally:
        cur.close()

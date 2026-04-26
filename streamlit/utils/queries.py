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
    """Returns mart_region_year, sorted by region name then year."""
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
            annualization_factor
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

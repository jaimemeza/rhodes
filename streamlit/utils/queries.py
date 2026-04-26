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

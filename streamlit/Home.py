import streamlit as st

from utils.snowflake import get_snowflake_connection
from utils.queries import fetch_session_info
from utils.styles import apply_global_styles

st.set_page_config(
    page_title="Rhodes Sales Analytics",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="collapsed",
)
apply_global_styles()

# Attempt connection once; reuse cached resource on every page.
_conn_error = None
_session = None
try:
    conn = get_snowflake_connection()
    _session = fetch_session_info(conn)
except Exception as e:
    _conn_error = e

# ── Sidebar ────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### Rhodes Sales Analytics")
    st.caption("Regional performance · 2023–2024")
    st.divider()
    with st.expander("Connection", expanded=False):
        if _session is not None:
            st.caption(f"**Role:** {_session['ROLE'].iloc[0]}")
            st.caption(f"**Warehouse:** {_session['WAREHOUSE'].iloc[0]}")
            st.caption(f"**Database:** {_session['DATABASE'].iloc[0]}")
        else:
            st.error("Not connected")

# ── Main ───────────────────────────────────────────────────────────────
st.title("Rhodes Homes Sales Analytics")

if _conn_error:
    st.error(
        "**Snowflake connection failed.**\n\n"
        f"`{_conn_error}`\n\n"
        "Common fixes:\n"
        "- Confirm `.streamlit/secrets.toml` exists in the `streamlit/` directory.\n"
        "- Verify `private_key` is a complete PEM string with newlines preserved "
        "(no single-line encoding).\n"
        "- Check the account identifier is `flkmkxj-in29512`.\n"
        "- Confirm STREAMLIT_USER has the RHODES_READER role assigned."
    )

st.markdown(
    "This dashboard summarizes home sale contract performance across the three Rhodes Homes "
    "sales regions (South Texas, Rio Grande Valley, Coastal Bend) for 2023 and Jan–Sep 2024. "
    "Use the sidebar to navigate between views."
)

st.markdown("""
- **Region Overview** — Year-over-year volume, close rate, margin attainment, and target pace by region.
- **Forecast** — Snowflake Cortex FORECAST projection of monthly contract volume through year-end.
- **Channel Economics** — Acquisition channel cost (commission rate) vs. quality (cancel rate).
- **Consultants** — Individual performance leaderboard with year-over-year deltas.
- **Ask a Question** — Natural-language queries answered by Cortex using pre-computed context.
""")

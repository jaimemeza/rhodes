import streamlit as st


def apply_global_styles():
    """Call at the top of every page after set_page_config."""
    st.markdown("""
<style>
.block-container {
    padding-top: 2rem;
    padding-left: 2rem;
    padding-right: 2rem;
    max-width: 1400px;
}
html, body, [class*="css"] {
    font-size: 14px;
}
[data-testid="stSidebar"] {
    min-width: 160px !important;
    max-width: 180px !important;
}
[data-testid="stVerticalBlock"] > div {
    gap: 0.5rem;
}
</style>
""", unsafe_allow_html=True)

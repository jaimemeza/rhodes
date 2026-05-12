import psycopg2
import streamlit as st


@st.cache_resource
def get_connection():
    cfg = st.secrets["postgres"]
    conn = psycopg2.connect(
        host=cfg["host"],
        port=cfg["port"],
        dbname=cfg["database"],
        user=cfg["user"],
        password=cfg["password"],
    )
    conn.autocommit = True
    return conn

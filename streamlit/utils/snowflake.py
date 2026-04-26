from cryptography.hazmat.primitives import serialization
import snowflake.connector
import streamlit as st

CORTEX_MODEL = "claude-4-sonnet"


@st.cache_resource
def get_snowflake_connection():
    cfg = st.secrets["snowflake"]

    private_key = serialization.load_pem_private_key(
        cfg["private_key"].encode("utf-8"),
        password=None,
    )
    pkb = private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    return snowflake.connector.connect(
        account   = cfg["account"],
        user      = cfg["user"],
        role      = cfg["role"],
        warehouse = cfg["warehouse"],
        database  = cfg["database"],
        schema    = cfg["schema"],
        private_key = pkb,
    )
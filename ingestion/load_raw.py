import pandas as pd
from sqlalchemy import create_engine, text
import os

DB_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://flux:changeme@localhost:5432/rhodes_homes"
)

def get_engine():
    return create_engine(DB_URL)

def create_raw_schema(engine):
    with engine.connect() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS raw"))
        conn.commit()
        print("✅ Schema 'raw' ready")

def load_sales(engine):
    df = pd.read_csv("ingestion/seed_data/Homebuilder_Sales.csv")
    df.columns = df.columns.str.lower()
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS raw.homebuilder_sales CASCADE"))
        conn.commit()
    df.to_sql("homebuilder_sales", engine, schema="raw", if_exists="replace", index=False)
    print(f"✅ Loaded {len(df)} rows into raw.homebuilder_sales")

def load_regional_manager(engine):
    df = pd.read_excel("ingestion/seed_data/Regional_Manager_Lookup.xlsx")
    df.columns = df.columns.str.lower()
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS raw.regional_manager_lookup CASCADE"))
        conn.commit()
    df.to_sql("regional_manager_lookup", engine, schema="raw", if_exists="replace", index=False)
    print(f"✅ Loaded {len(df)} rows into raw.regional_manager_lookup")

if __name__ == "__main__":
    engine = get_engine()
    create_raw_schema(engine)
    load_sales(engine)
    load_regional_manager(engine)
    print("✅ Ingestion complete")

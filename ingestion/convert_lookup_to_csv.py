"""Convert Regional_Manager_Lookup.xlsx to a dbt-ready seed CSV.

This is a one-off utility. Re-run only if the source XLSX changes.
The output CSV at dbt/seeds/regional_manager_lookup.csv is committed to the
repo and is the dbt seed source of truth.

Usage:
    pip install -r ingestion/requirements.txt
    python ingestion/convert_lookup_to_csv.py
"""

import re
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
XLSX_PATH = REPO_ROOT / "ingestion" / "seed_data" / "Regional_Manager_Lookup.xlsx"
CSV_PATH = REPO_ROOT / "dbt" / "seeds" / "regional_manager_lookup.csv"
SHEET_NAME = "Regional Lookup"


def to_snake_case(col: str) -> str:
    col = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", col)
    col = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", col)
    return col.lower()


def main() -> None:
    df = pd.read_excel(XLSX_PATH, sheet_name=SHEET_NAME, engine="openpyxl")
    df.columns = [to_snake_case(c) for c in df.columns]
    CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(CSV_PATH, index=False)
    print(f"Written {len(df)} rows to {CSV_PATH}")


if __name__ == "__main__":
    main()

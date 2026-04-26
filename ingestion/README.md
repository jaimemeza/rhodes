# Ingestion

Loads the raw CSV into `RHODES.RAW.HOMEBUILDER_SALES` via a Snowflake internal stage.

## Files

- `load_raw.py` — main loader script
- `seed_data/Homebuilder_Sales.csv` — 600 contract rows, Jan 2023 – Sep 2024
- `seed_data/Regional_Manager_Lookup.xlsx` — region → manager mapping (consumed by dbt seed)
- `pyproject.toml` — package definition with `snowflake-connector-python` dependency

## Setup

```bash
cd ingestion
pip install -e .
```

Requires a `profiles.yml` or environment variables for Snowflake auth. The script uses key-pair auth via `SNOWFLAKE_PRIVATE_KEY_PATH` (or inline PEM). See `../dbt/profiles.yml.example` for the key-pair format.

## Running

```bash
python load_raw.py
```

The script:

1. Creates `RHODES.RAW.HOMEBUILDER_SALES` if it doesn't exist (schema inferred from CSV headers).
2. Creates a temporary named stage, uploads the CSV, runs `COPY INTO`, then drops the stage.
3. Prints row count on success.

Re-running is safe — the `COPY INTO` skips files already loaded unless `FORCE=TRUE` is passed.

## Alternative: Snowsight UI

The raw table can also be loaded via the Snowsight **Load Data** wizard. Upload `Homebuilder_Sales.csv`, let Snowsight infer the schema, and target `RHODES.RAW.HOMEBUILDER_SALES`. The dbt models expect exact column names as defined in `dbt/models/staging/sources.yml`.

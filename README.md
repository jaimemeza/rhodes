# Rhodes Homes Sales Analytics

Take-home assessment: end-to-end data pipeline + analytics dashboard for a residential home builder with three South Texas sales regions (Rio Grande Valley, South Texas, Coastal Bend), covering Jan 2023 – Sep 2024.

## Stack

| Layer | Tool |
| ----- | ---- |
| Data warehouse | Snowflake (account `flkmkxj-in29512`) |
| Transformation | dbt Core |
| ML / NL | Snowflake Cortex FORECAST + COMPLETE |
| Dashboard | Streamlit |
| Auth | Key-pair authentication (RSA 2048) |

## Repository layout

```text
├── sql/setup/
│   ├── 01_account_setup.sql        # Warehouses, schemas, roles, service users
│   └── 02_cortex_forecast.sql      # ML forecast model creation + result tables
├── ingestion/
│   ├── load_raw.py                 # Bulk-loads CSV into RHODES.RAW
│   ├── seed_data/
│   │   ├── Homebuilder_Sales.csv
│   │   └── Regional_Manager_Lookup.xlsx
│   └── pyproject.toml
├── dbt/
│   ├── models/staging/             # stg_homebuilder_sales, stg_regional_manager
│   ├── models/marts/core/          # dim_community, dim_consultant, dim_region, fct_home_sales
│   └── models/marts/agg/           # mart_region_year, mart_region_month, mart_channel_economics,
│                                   # mart_consultant_performance, mart_consultant_region
└── streamlit/
    ├── Home.py
    ├── pages/
    │   ├── 1_Region_Overview.py
    │   ├── 2_Forecast.py
    │   ├── 3_Channel_Economics.py
    │   ├── 4_Consultants.py
    │   └── 5_Ask_a_Question.py
    └── utils/
        ├── snowflake.py            # get_snowflake_connection(), CORTEX_MODEL
        └── queries.py              # Cached query helpers
```

## Reproducing from scratch

### 1. Account setup

Run `sql/setup/01_account_setup.sql` as ACCOUNTADMIN. This creates three warehouses (`RHODES_LOAD_WH`, `RHODES_TRANSFORM_WH`, `RHODES_BI_WH`), three schemas (`RAW`, `STAGING`, `ANALYTICS`), three roles (`RHODES_LOADER`, `RHODES_TRANSFORMER`, `RHODES_READER`), and two service users (`DBT_USER`, `STREAMLIT_USER`).

### 2. Load raw data

```bash
cd ingestion
pip install -e .
python load_raw.py
```

Bulk-loads `Homebuilder_Sales.csv` (600 rows) into `RHODES.RAW.HOMEBUILDER_SALES` via a temporary stage. Alternatively, load via Snowsight UI — the schema is inferred automatically.

### 3. Run dbt

```bash
cd dbt
dbt deps
dbt seed          # loads regional_manager_lookup.csv into RHODES.ANALYTICS.DIM_REGION
dbt run
dbt test          # 158 tests across 9 models + 1 seed + 1 source
```

Configure `dbt/profiles.yml` using the service account key. See `dbt/profiles.yml.example`.

### 4. Cortex forecasts

Run `sql/setup/02_cortex_forecast.sql` as ACCOUNTADMIN. Creates two `SNOWFLAKE.ML.FORECAST` models trained on monthly region data and stores results in `FORECAST_RESULTS` and `CLOSE_TIME_FORECAST_RESULTS`. Generates a 3-month (Oct–Dec 2024) forward projection with 90% prediction intervals.

### 5. Streamlit

```bash
cd streamlit
pip install -r requirements.txt
# Copy and fill in secrets:
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
streamlit run Home.py
```

## Dashboard pages

| Page | What it answers |
| ---- | --------------- |
| **Region Overview** | YoY volume, target attainment, margin posture, pipeline, quarterly cancel trend |
| **Forecast** | Cortex FORECAST projection of Oct–Dec 2024 contract volume and close time per region |
| **Channel Economics** | Acquisition channel cost (commission rate) vs. quality (cancel rate) quadrant analysis |
| **Consultants** | Individual performance leaderboard, YoY scatter, regional breakdown |
| **Ask a Question** | Free-text NL queries answered by Cortex COMPLETE, grounded in live warehouse data |

## Key design decisions

**Same-period YoY.** 2024 data covers Jan–Sep only. All YoY comparisons use the same 9-month window in 2023 rather than annualizing 2024 — apples-to-apples. Annualized figures are available in the mart for reference but not surfaced in headlines.

**Margin proxy.** The dataset has no construction cost column. Margin is modeled as `(contract_price - commission_paid) / contract_price`, labeled explicitly as a proxy throughout. Large margin-vs-target deltas reflect this approximation.

**Cortex model.** `claude-4-sonnet` is used for Cortex COMPLETE (NL queries). Cortex FORECAST uses the platform's built-in ML model.

**Coastal Bend close-time forecast.** CB has 3–4 closings/month, producing near-zero confidence intervals that are visually misleading. The close-time forecast chart excludes CB and displays a note explaining the exclusion. Volume forecast retains all three regions.

**Role model.** LOADER writes only to RAW; TRANSFORMER reads RAW and writes STAGING + ANALYTICS; READER reads only ANALYTICS and has `SNOWFLAKE.CORTEX_USER`. ML model creation requires ACCOUNTADMIN privileges beyond these grants.

select
    region,
    regional_manager,
    sales_target_units,
    margin_target_pct
from {{ ref('regional_manager_lookup') }}

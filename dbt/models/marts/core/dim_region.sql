{{ config(schema='analytics', materialized='table') }}

with source as (

    select * from {{ ref('stg_regional_manager') }}

),

final as (

    select
        {{ dbt_utils.generate_surrogate_key(['region']) }} as region_sk,
        region,
        regional_manager,
        sales_target_units,
        margin_target_pct
    from source

)

select * from final

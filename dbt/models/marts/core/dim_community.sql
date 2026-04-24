{{ config(schema='analytics', materialized='table') }}

with sales as (

    select distinct
        community,
        city,
        region
    from {{ ref('stg_homebuilder_sales') }}

),

final as (

    select
        {{ dbt_utils.generate_surrogate_key(['community']) }} as community_sk,
        community,
        city,
        region
    from sales

)

select * from final

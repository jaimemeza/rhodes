{{ config(schema='analytics', materialized='table') }}

with sales as (

    select distinct sales_consultant
    from {{ ref('stg_homebuilder_sales') }}

),

final as (

    select
        {{ dbt_utils.generate_surrogate_key(['sales_consultant']) }} as consultant_sk,
        sales_consultant
    from sales

)

select * from final

{{ config(schema='analytics', materialized='table') }}

with sales as (

    select * from {{ ref('stg_homebuilder_sales') }}

),

regions as (

    select * from {{ ref('dim_region') }}

),

consultants as (

    select * from {{ ref('dim_consultant') }}

),

communities as (

    select * from {{ ref('dim_community') }}

),

enriched as (

    select
        -- natural key
        sales.contract_id,

        -- foreign keys to dims
        regions.region_sk,
        sales.region,
        consultants.consultant_sk,
        communities.community_sk,

        -- dates
        sales.contract_date,
        sales.close_date,
        sales.days_to_close,

        -- product
        sales.plan_name,
        sales.sqft,
        sales.bedrooms,
        sales.bathrooms,

        -- pricing
        sales.base_price,
        sales.upgrade_amount,
        sales.incentive_amount,
        sales.contract_price,
        sales.agent_commission,

        -- status flags
        sales.status,
        sales.is_closed,
        sales.is_cancelled,
        sales.is_under_contract,

        -- attribution
        sales.sales_consultant,
        sales.buyer_source,
        sales.loan_type,

        -- calculated metrics
        sales.contract_price / nullif(sales.sqft, 0)
            as price_per_sqft,

        (sales.contract_price - sales.agent_commission) / nullif(sales.contract_price, 0)
            as estimated_margin_pct,

        (sales.contract_price - sales.base_price) / nullif(sales.contract_price, 0)
            as upgrade_capture_pct

    from sales
    left join regions     on sales.region           = regions.region
    left join consultants on sales.sales_consultant = consultants.sales_consultant
    left join communities on sales.community        = communities.community

)

select * from enriched

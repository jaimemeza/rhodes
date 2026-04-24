{{ config(schema='analytics', materialized='table') }}

with sales as (

    select *
    from {{ ref('fct_home_sales') }}
    -- Extract was cut on 2024-10-02, so Oct 2024 has a single partial-month row.
    -- Exclude to avoid biasing trends and forecast input.
    where contract_date < '2024-10-01'

),

regions as (

    select * from {{ ref('dim_region') }}

),

by_region_month as (

    select
        s.region_sk,
        date_trunc('month', s.contract_date)::date  as month_start,
        count(*)                                     as contracts,
        count_if(s.is_closed)                        as contracts_closed,
        count_if(s.is_cancelled)                     as contracts_cancelled,
        count_if(s.is_under_contract)                as contracts_under_contract,
        count_if(s.is_closed) / nullif(count(*), 0)::float
                                                     as close_rate,
        count_if(s.is_cancelled) / nullif(count(*), 0)::float
                                                     as cancel_rate,
        avg(iff(s.is_closed, s.contract_price, null))
                                                     as avg_contract_price,
        avg(iff(s.is_closed, s.price_per_sqft, null))
                                                     as avg_price_per_sqft,
        avg(iff(s.is_closed, s.estimated_margin_pct, null))
                                                     as avg_estimated_margin_pct,
        avg(iff(s.is_closed, s.upgrade_capture_pct, null))
                                                     as avg_upgrade_capture_pct,
        avg(iff(s.is_closed, s.days_to_close, null))
                                                     as avg_days_to_close
    from sales s
    group by 1, 2

)

select
    b.region_sk,
    r.region,
    b.month_start,
    b.contracts,
    b.contracts_closed,
    b.contracts_cancelled,
    b.contracts_under_contract,
    b.close_rate,
    b.cancel_rate,
    b.avg_contract_price,
    b.avg_price_per_sqft,
    b.avg_estimated_margin_pct,
    b.avg_upgrade_capture_pct,
    b.avg_days_to_close,
    r.sales_target_units,
    r.margin_target_pct
from by_region_month b
join regions r on b.region_sk = r.region_sk

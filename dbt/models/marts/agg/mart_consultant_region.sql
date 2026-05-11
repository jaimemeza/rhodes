{{ config(schema='analytics', materialized='table') }}

with sales as (

    select *
    from {{ ref('fct_home_sales') }}
    where contract_date < '2024-10-01'

)

select
    consultant_sk,
    sales_consultant,
    region_sk,
    region,
    count(*)                                                           as contracts,
    count(*) filter (where is_closed)                                  as closed_contracts,
    count(*) filter (where is_cancelled)                               as cancelled_contracts,
    count(*) filter (where is_cancelled) / nullif(count(*), 0)::float  as cancel_rate,
    avg(case when is_closed then days_to_close else null end)           as avg_days_to_close,
    sum(case when is_closed then contract_price else 0 end)             as total_contract_value,
    avg(case when is_closed then contract_price else null end)          as avg_contract_price
from sales
group by 1, 2, 3, 4

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
    count(*)                                            as contracts,
    count_if(is_closed)                                 as closed_contracts,
    count_if(is_cancelled)                              as cancelled_contracts,
    count_if(is_cancelled) / nullif(count(*), 0)::float as cancel_rate,
    avg(iff(is_closed, days_to_close, null))             as avg_days_to_close,
    sum(iff(is_closed, contract_price, 0))              as total_contract_value,
    avg(iff(is_closed, contract_price, null))            as avg_contract_price
from sales
group by 1, 2, 3, 4

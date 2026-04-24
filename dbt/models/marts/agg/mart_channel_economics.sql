{{ config(schema='analytics', materialized='table') }}

with sales as (

    select *
    from {{ ref('fct_home_sales') }}
    where contract_date < '2024-10-01'

)

select
    buyer_source,
    count(*)                                                     as contracts,
    count_if(is_closed)                                          as closed_contracts,
    count_if(is_cancelled)                                       as cancelled_contracts,
    count_if(is_cancelled) / nullif(count(*), 0)::float          as cancel_rate,
    avg(iff(is_closed, commission_rate, null))                   as avg_commission_rate,
    avg(iff(is_closed, days_to_close, null))                     as avg_days_to_close,
    avg(iff(is_closed, contract_price, null))                    as avg_contract_price,
    avg(iff(is_closed, upgrade_capture_pct, null))               as avg_upgrade_capture_pct,
    sum(iff(is_closed, contract_price, 0))                       as total_contract_value,
    sum(iff(is_closed, agent_commission, 0))                     as total_commission_paid
from sales
group by 1

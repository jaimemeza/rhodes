{{ config(schema='analytics', materialized='table') }}

with sales as (

    select *
    from {{ ref('fct_home_sales') }}
    where contract_date < '2024-10-01'

)

select
    buyer_source,
    count(*)                                                     as contracts,
    count(*) filter (where is_closed)                                 as closed_contracts,
    count(*) filter (where is_cancelled)                              as cancelled_contracts,
    count(*) filter (where is_cancelled) / nullif(count(*), 0)::float as cancel_rate,
    avg(case when is_closed then commission_rate else null end)        as avg_commission_rate,
    avg(case when is_closed then days_to_close else null end)          as avg_days_to_close,
    avg(case when is_closed then contract_price else null end)         as avg_contract_price,
    avg(case when is_closed then upgrade_capture_pct else null end)    as avg_upgrade_capture_pct,
    sum(case when is_closed then contract_price else 0 end)            as total_contract_value,
    sum(case when is_closed then agent_commission else 0 end)          as total_commission_paid
from sales
group by 1

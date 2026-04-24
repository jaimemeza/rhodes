{{ config(schema='analytics', materialized='table') }}

with sales as (

    select *
    from {{ ref('fct_home_sales') }}
    where contract_date < '2024-10-01'

),

-- All-time aggregates (existing)
overall as (

    select
        consultant_sk,
        sales_consultant,
        count(*)                                                     as total_contracts,
        count_if(is_closed)                                          as closed_contracts,
        count_if(is_cancelled)                                       as cancelled_contracts,
        count_if(is_cancelled) / nullif(count(*), 0)::float          as cancel_rate,
        count(distinct region)                                       as regions_worked,
        avg(iff(is_closed, days_to_close, null))                     as avg_days_to_close,
        sum(iff(is_closed, contract_price, 0))                       as total_contract_value,
        avg(iff(is_closed, contract_price, null))                    as avg_contract_price,
        avg(iff(is_closed, estimated_margin_pct, null))              as avg_estimated_margin_pct,
        avg(iff(is_closed, upgrade_capture_pct, null))               as avg_upgrade_capture_pct,
        avg(iff(is_closed, commission_rate, null))                   as avg_commission_rate,
        count_if(is_closed and loan_type = 'Cash') / nullif(count_if(is_closed), 0)::float
                                                                     as cash_buyer_rate
    from sales
    group by 1, 2

),

-- 2023 only
y2023 as (

    select
        consultant_sk,
        count_if(is_closed)                                          as closed_2023,
        count_if(is_cancelled) / nullif(count(*), 0)::float          as cancel_rate_2023
    from sales
    where year(contract_date) = 2023
    group by 1

),

-- 2024 only (Jan–Sep)
y2024 as (

    select
        consultant_sk,
        count_if(is_closed)                                          as closed_2024,
        count_if(is_cancelled) / nullif(count(*), 0)::float          as cancel_rate_2024
    from sales
    where year(contract_date) = 2024
    group by 1

)

select
    o.*,
    coalesce(y2023.closed_2023, 0)                                   as closed_2023,
    coalesce(y2024.closed_2024, 0)                                   as closed_2024,
    round(coalesce(y2024.closed_2024, 0) * 12.0/9)::integer          as closed_2024_annualized,
    -- Volume YoY: annualized 2024 vs 2023, expressed as % change
    round(
        (coalesce(y2024.closed_2024, 0) * 12.0/9 - coalesce(y2023.closed_2023, 0))
        / nullif(coalesce(y2023.closed_2023, 0), 0)::float
    , 4)                                                             as volume_yoy_pct,
    y2023.cancel_rate_2023,
    y2024.cancel_rate_2024,
    round(y2024.cancel_rate_2024 - y2023.cancel_rate_2023, 4)        as cancel_rate_yoy_delta
from overall o
left join y2023 using (consultant_sk)
left join y2024 using (consultant_sk)

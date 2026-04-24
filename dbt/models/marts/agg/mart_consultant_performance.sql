{{ config(schema='analytics', materialized='table') }}

with sales as (

    select *
    from {{ ref('fct_home_sales') }}
    where contract_date < '2024-10-01'

),

by_consultant as (

    select
        consultant_sk,
        sales_consultant,
        count(*)                                              as total_contracts,
        count_if(is_closed)                                   as closed_contracts,
        count_if(is_cancelled)                                as cancelled_contracts,
        count_if(is_cancelled) / nullif(count(*), 0)::float   as cancel_rate,
        count(distinct region)                                as regions_worked,
        avg(iff(is_closed, days_to_close, null))               as avg_days_to_close,
        sum(iff(is_closed, contract_price, 0))                as total_contract_value,
        avg(iff(is_closed, contract_price, null))              as avg_contract_price,
        avg(iff(is_closed, estimated_margin_pct, null))        as avg_estimated_margin_pct,
        avg(iff(is_closed, upgrade_capture_pct, null))         as avg_upgrade_capture_pct,
        count_if(is_closed and loan_type = 'Cash') / nullif(count_if(is_closed), 0)::float
                                                              as cash_buyer_rate
    from sales
    group by 1, 2

)

select * from by_consultant

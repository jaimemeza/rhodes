{{ config(schema='analytics', materialized='table') }}

with sales as (

    select *
    from {{ ref('fct_home_sales') }}
    where contract_date < '2024-10-01'

),

regions as (

    select * from {{ ref('dim_region') }}

),

by_region_year as (

    select
        region_sk,
        year(contract_date)                                         as contract_year,
        count(*)                                                    as contracts,
        count_if(is_closed)                                         as contracts_closed,
        count_if(is_cancelled)                                      as contracts_cancelled,
        count_if(is_cancelled) / nullif(count(*), 0)::float         as cancel_rate,
        avg(iff(is_closed, contract_price, null))                   as avg_contract_price,
        avg(iff(is_closed, days_to_close, null))                    as avg_days_to_close,
        avg(iff(is_closed, estimated_margin_pct, null))             as avg_estimated_margin_pct,
        avg(iff(is_closed, upgrade_capture_pct, null))              as avg_upgrade_capture_pct,
        avg(iff(is_closed, commission_rate, null))                  as avg_commission_rate
    from sales
    group by 1, 2

),

annualized as (

    select
        b.*,
        -- Annualization factor: 2024 has 9 months of data, 2023 has 12.
        case when contract_year = 2024 then 12.0/9 else 1.0 end     as annualization_factor
    from by_region_year b

)

select
    a.region_sk,
    r.region,
    a.contract_year,
    a.contracts,
    a.contracts_closed,
    a.contracts_cancelled,
    a.cancel_rate,
    -- Annualized projections — apples-to-apples with annual targets
    round(a.contracts * a.annualization_factor)::integer            as contracts_annualized,
    round(a.contracts_closed * a.annualization_factor)::integer     as contracts_closed_annualized,
    a.avg_contract_price,
    a.avg_days_to_close,
    a.avg_estimated_margin_pct,
    a.avg_upgrade_capture_pct,
    a.avg_commission_rate,
    -- Target context
    r.sales_target_units,
    r.margin_target_pct,
    round(a.contracts_closed * a.annualization_factor / nullif(r.sales_target_units, 0), 4)
        as target_attainment_pct,
    a.annualization_factor
from annualized a
join regions r on a.region_sk = r.region_sk

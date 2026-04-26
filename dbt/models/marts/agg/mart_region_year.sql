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
        year(contract_date)                                            as contract_year,
        count(*)                                                       as contracts,
        count_if(is_closed)                                            as contracts_closed,
        count_if(is_cancelled)                                         as contracts_cancelled,
        count_if(is_cancelled) / nullif(count(*), 0)::float            as cancel_rate,
        avg(iff(is_closed, contract_price, null))                      as avg_contract_price,
        avg(iff(is_closed, days_to_close, null))                       as avg_days_to_close,
        avg(iff(is_closed, estimated_margin_pct, null))                as avg_estimated_margin_pct,
        avg(iff(is_closed, upgrade_capture_pct, null))                 as avg_upgrade_capture_pct,
        avg(iff(is_closed, commission_rate, null))                     as avg_commission_rate
    from sales
    group by 1, 2

),

with_annualization as (

    select
        b.*,
        case when contract_year = 2024 then 12.0/9 else 1.0 end        as annualization_factor
    from by_region_year b

),

with_targets as (

    select
        a.*,
        r.region,
        r.sales_target_units,
        r.margin_target_pct,
        round(a.contracts        * a.annualization_factor)::integer    as contracts_annualized,
        round(a.contracts_closed * a.annualization_factor)::integer    as contracts_closed_annualized
    from with_annualization a
    join regions r on a.region_sk = r.region_sk

),

with_attainment as (

    select
        *,
        round(contracts_closed_annualized / nullif(sales_target_units, 0)::float, 4)
            as target_attainment_annualized_pct,
        round(contracts_closed            / nullif(sales_target_units, 0)::float, 4)
            as target_attainment_ytd_pct,
        round(avg_estimated_margin_pct - margin_target_pct, 4)
            as margin_attainment_delta
    from with_targets

),

with_yoy as (

    select
        *,
        lag(contracts_closed_annualized) over (partition by region_sk order by contract_year)
            as prior_year_closed_annualized,
        contracts_closed_annualized
            - lag(contracts_closed_annualized) over (partition by region_sk order by contract_year)
            as closed_yoy_delta,
        round(
            (contracts_closed_annualized
                - lag(contracts_closed_annualized) over (partition by region_sk order by contract_year))
            / nullif(lag(contracts_closed_annualized) over (partition by region_sk order by contract_year), 0)::float
        , 4)
            as closed_yoy_pct,
        round(
            cancel_rate
            - lag(cancel_rate) over (partition by region_sk order by contract_year)
        , 4)
            as cancel_rate_yoy_delta
    from with_attainment

)

select
    region_sk,
    region,
    contract_year,
    contracts,
    contracts_closed,
    contracts_cancelled,
    cancel_rate,
    contracts_annualized,
    contracts_closed_annualized,
    avg_contract_price,
    avg_days_to_close,
    avg_estimated_margin_pct,
    avg_upgrade_capture_pct,
    avg_commission_rate,
    sales_target_units,
    margin_target_pct,
    target_attainment_annualized_pct,
    target_attainment_ytd_pct,
    margin_attainment_delta,
    prior_year_closed_annualized,
    closed_yoy_delta,
    closed_yoy_pct,
    cancel_rate_yoy_delta,
    annualization_factor
from with_yoy

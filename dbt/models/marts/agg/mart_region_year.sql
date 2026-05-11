{{ config(schema='analytics', materialized='table') }}

with sales as (

    select *
    from {{ ref('fct_home_sales') }}
    where contract_date < '2024-10-01'

),

bounds as (

    select
        max(contract_date)                                         as latest_contract_date,
        extract(year from max(contract_date::date))                as current_year,
        extract(year from max(contract_date::date)) - 1            as prior_year,
        extract(month from max(contract_date::date))               as months_elapsed
    from sales

),

regions as (

    select * from {{ ref('dim_region') }}

),

by_region_year as (

    select
        region_sk,
        extract(year from contract_date::date)                     as contract_year,
        count(*)                                                   as contracts,
        count(*) filter (where is_closed)                          as contracts_closed,
        count(*) filter (where is_cancelled)                       as contracts_cancelled,
        count(*) filter (where is_cancelled) / nullif(count(*), 0)::float
                                                                   as cancel_rate,
        avg(case when is_closed then contract_price else null end)  as avg_contract_price,
        avg(case when is_closed then days_to_close else null end)   as avg_days_to_close,
        avg(case when is_closed then estimated_margin_pct else null end)
                                                                   as avg_estimated_margin_pct,
        avg(case when is_closed then upgrade_capture_pct else null end)
                                                                   as avg_upgrade_capture_pct,
        avg(case when is_closed then commission_rate else null end) as avg_commission_rate
    from sales
    group by 1, 2

),

with_annualization as (

    select
        b.*,
        case when b.contract_year = bo.current_year
             then 12.0 / bo.months_elapsed
             else 1.0
        end                                                        as annualization_factor
    from by_region_year b
    cross join bounds bo

),

with_targets as (

    select
        a.*,
        r.region,
        r.sales_target_units,
        r.margin_target_pct,
        round(a.contracts        * a.annualization_factor)::integer as contracts_annualized,
        round(a.contracts_closed * a.annualization_factor)::integer as contracts_closed_annualized
    from with_annualization a
    join regions r on a.region_sk = r.region_sk

),

with_attainment as (

    select
        *,
        round((contracts_closed_annualized / nullif(sales_target_units, 0)::float)::numeric, 4)
            as target_attainment_annualized_pct,
        round((contracts_closed            / nullif(sales_target_units, 0)::float)::numeric, 4)
            as target_attainment_ytd_pct,
        round((avg_estimated_margin_pct - margin_target_pct)::numeric, 4)
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
            (
                (contracts_closed_annualized
                    - lag(contracts_closed_annualized) over (partition by region_sk order by contract_year))
                / nullif(lag(contracts_closed_annualized) over (partition by region_sk order by contract_year), 0)::float
            )::numeric
        , 4)
            as closed_yoy_pct,
        round(
            (
                cancel_rate
                - lag(cancel_rate) over (partition by region_sk order by contract_year)
            )::numeric
        , 4)
            as cancel_rate_yoy_delta
    from with_attainment

),

prior_year_same_period as (

    select
        region_sk,
        count(*) filter (where is_closed)                          as same_period_closed_prior_year
    from sales
    cross join bounds
    where extract(year from contract_date::date)  = bounds.prior_year
      and extract(month from contract_date::date) <= bounds.months_elapsed
    group by region_sk

)

select
    w.region_sk,
    w.region,
    w.contract_year,
    w.contracts,
    w.contracts_closed,
    w.contracts_cancelled,
    w.cancel_rate,
    w.contracts_annualized,
    w.contracts_closed_annualized,
    w.avg_contract_price,
    w.avg_days_to_close,
    w.avg_estimated_margin_pct,
    w.avg_upgrade_capture_pct,
    w.avg_commission_rate,
    w.sales_target_units,
    w.margin_target_pct,
    w.target_attainment_annualized_pct,
    w.target_attainment_ytd_pct,
    w.margin_attainment_delta,
    w.prior_year_closed_annualized,
    w.closed_yoy_delta,
    w.closed_yoy_pct,
    w.cancel_rate_yoy_delta,
    w.annualization_factor,
    py.same_period_closed_prior_year,
    case when w.contract_year = bo.current_year
        then round(
            (
                (w.contracts_closed - py.same_period_closed_prior_year)
                / nullif(py.same_period_closed_prior_year, 0)::float
            )::numeric
        , 4)
        else null
    end                                                            as same_period_yoy_pct
from with_yoy w
left join prior_year_same_period py on w.region_sk = py.region_sk
cross join bounds bo

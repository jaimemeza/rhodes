{{ config(schema='analytics', materialized='table') }}

/*
  Year boundaries and annualization are derived from MAX(contract_date), not
  hardcoded. As new data arrives, current_year/prior_year/months_elapsed
  update automatically. The one fixed value, contract_date < '2024-10-01',
  is the documented partial-month exclusion (extract boundary on the static
  snapshot), not a year assumption.
*/

with sales as (

    select *
    from {{ ref('fct_home_sales') }}
    where contract_date < '2024-10-01'

),

bounds as (

    select
        max(contract_date)               as latest_contract_date,
        year(max(contract_date))         as current_year,
        year(max(contract_date)) - 1     as prior_year,
        month(max(contract_date))        as months_elapsed
    from sales

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
        case when b.contract_year = bo.current_year
             then 12.0 / bo.months_elapsed
             else 1.0
        end                                                            as annualization_factor
    from by_region_year b
    cross join bounds bo

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

),

-- Prior-year closings through the same month as current-year partial data.
-- Cross join with bounds supplies prior_year and months_elapsed as scalars.
prior_year_same_period as (

    select
        region_sk,
        count_if(is_closed)                                            as same_period_closed_prior_year
    from sales
    cross join bounds
    where year(contract_date)  = bounds.prior_year
      and month(contract_date) <= bounds.months_elapsed
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
    iff(w.contract_year = bo.current_year,
        round(
            (w.contracts_closed - py.same_period_closed_prior_year)
            / nullif(py.same_period_closed_prior_year, 0)::float
        , 4),
        null
    )                                                                   as same_period_yoy_pct
from with_yoy w
left join prior_year_same_period py on w.region_sk = py.region_sk
cross join bounds bo

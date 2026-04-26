{{ config(schema='analytics', materialized='table') }}

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

-- All-time aggregates
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

y_prior_year as (

    select
        consultant_sk,
        count_if(is_closed)                                          as closed_prior_year,
        count_if(is_cancelled) / nullif(count(*), 0)::float          as cancel_rate_prior_year
    from sales
    cross join bounds
    where year(contract_date) = bounds.prior_year
    group by 1

),

y_current_year as (

    select
        consultant_sk,
        count_if(is_closed)                                          as closed_current_year,
        count_if(is_cancelled) / nullif(count(*), 0)::float          as cancel_rate_current_year
    from sales
    cross join bounds
    where year(contract_date) = bounds.current_year
    group by 1

)

select
    o.*,
    coalesce(yp.closed_prior_year, 0)                                    as closed_prior_year,
    coalesce(yc.closed_current_year, 0)                                  as closed_current_year,
    round(coalesce(yc.closed_current_year, 0) * (12.0 / bo.months_elapsed))::integer
                                                                         as closed_current_year_annualized,
    round(
        (coalesce(yc.closed_current_year, 0) * (12.0 / bo.months_elapsed) - coalesce(yp.closed_prior_year, 0))
        / nullif(coalesce(yp.closed_prior_year, 0), 0)::float
    , 4)                                                                 as volume_yoy_pct,
    yp.cancel_rate_prior_year,
    yc.cancel_rate_current_year,
    round(yc.cancel_rate_current_year - yp.cancel_rate_prior_year, 4)   as cancel_rate_yoy_delta
from overall o
cross join bounds bo
left join y_prior_year  yp using (consultant_sk)
left join y_current_year yc using (consultant_sk)

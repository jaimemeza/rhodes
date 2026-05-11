{{ config(schema='analytics', materialized='table') }}

with sales as (

    select *
    from {{ ref('fct_home_sales') }}
    where contract_date < '2024-10-01'

),

bounds as (

    select
        max(contract_date)                                        as latest_contract_date,
        extract(year from max(contract_date::date))               as current_year,
        extract(year from max(contract_date::date)) - 1           as prior_year,
        extract(month from max(contract_date::date))              as months_elapsed
    from sales

),

overall as (

    select
        consultant_sk,
        sales_consultant,
        count(*)                                                   as total_contracts,
        count(*) filter (where is_closed)                          as closed_contracts,
        count(*) filter (where is_cancelled)                       as cancelled_contracts,
        count(*) filter (where is_cancelled) / nullif(count(*), 0)::float
                                                                   as cancel_rate,
        count(distinct region)                                     as regions_worked,
        avg(case when is_closed then days_to_close else null end)   as avg_days_to_close,
        sum(case when is_closed then contract_price else 0 end)     as total_contract_value,
        avg(case when is_closed then contract_price else null end)  as avg_contract_price,
        avg(case when is_closed then estimated_margin_pct else null end)
                                                                   as avg_estimated_margin_pct,
        avg(case when is_closed then upgrade_capture_pct else null end)
                                                                   as avg_upgrade_capture_pct,
        avg(case when is_closed then commission_rate else null end) as avg_commission_rate,
        count(*) filter (where is_closed and loan_type = 'Cash') / nullif(count(*) filter (where is_closed), 0)::float
                                                                   as cash_buyer_rate
    from sales
    group by 1, 2

),

y_prior_year as (

    select
        consultant_sk,
        count(*) filter (where is_closed)                          as closed_prior_year,
        count(*) filter (where is_cancelled) / nullif(count(*), 0)::float
                                                                   as cancel_rate_prior_year
    from sales
    cross join bounds
    where extract(year from contract_date::date) = bounds.prior_year
    group by 1

),

y_current_year as (

    select
        consultant_sk,
        count(*) filter (where is_closed)                          as closed_current_year,
        count(*) filter (where is_cancelled) / nullif(count(*), 0)::float
                                                                   as cancel_rate_current_year
    from sales
    cross join bounds
    where extract(year from contract_date::date) = bounds.current_year
    group by 1

)

select
    o.*,
    coalesce(yp.closed_prior_year, 0)                                  as closed_prior_year,
    coalesce(yc.closed_current_year, 0)                                as closed_current_year,
    round(coalesce(yc.closed_current_year, 0) * (12.0 / bo.months_elapsed))::integer
                                                                       as closed_current_year_annualized,
    round(
            (
                (coalesce(yc.closed_current_year, 0) * (12.0 / bo.months_elapsed) - coalesce(yp.closed_prior_year, 0))
                / nullif(coalesce(yp.closed_prior_year, 0), 0)::float
            )::numeric
        , 4)                                                           as volume_yoy_pct,
    yp.cancel_rate_prior_year,
    yc.cancel_rate_current_year,
    round((yc.cancel_rate_current_year - yp.cancel_rate_prior_year)::numeric, 4) as cancel_rate_yoy_delta
from overall o
cross join bounds bo
left join y_prior_year  yp using (consultant_sk)
left join y_current_year yc using (consultant_sk)

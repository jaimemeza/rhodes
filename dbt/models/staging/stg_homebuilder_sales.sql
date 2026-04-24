with source as (

    select * from {{ source('rhodes_raw', 'homebuilder_sales') }}

),

renamed as (

    select
        -- identifiers
        contract_id,

        -- location / product
        region,
        community,
        city,
        plan_name,
        sqft,
        bedrooms,
        bathrooms,

        -- pricing
        base_price,
        upgrade_amount,
        incentive_amount,
        contract_price,

        -- dates
        contract_date,
        close_date,
        days_to_close,

        -- status
        status,
        status = 'Closed'         as is_closed,
        status = 'Cancelled'      as is_cancelled,
        status = 'Under Contract' as is_under_contract,

        -- people / finance
        sales_consultant,
        buyer_source,
        loan_type,
        agent_commission,

        -- derived integrity columns (validated by model-level tests)
        datediff('day', contract_date, close_date)      as days_to_close_calc,
        base_price + upgrade_amount - incentive_amount   as contract_price_calc

    from source

)

select * from renamed

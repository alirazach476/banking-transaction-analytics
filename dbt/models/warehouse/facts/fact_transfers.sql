{{
    config(
        unique_key='transfer_id',
        incremental_strategy='delete+insert'
    )
}}

with staged as (
    select * from {{ ref('stg_transfers') }}
    {% if is_incremental() %}
    where updated_at > (select coalesce(max(updated_at), '1900-01-01'::timestamptz) from {{ this }})
    {% endif %}
),

dim_customer as (
    select customer_key, customer_id
    from {{ ref('dim_customer') }}
    where is_current
),

dim_account as (
    select account_key, account_id from {{ ref('dim_account') }}
),

dim_date as (
    select date_key, calendar_date from {{ ref('dim_date') }}
)

select
    s.transfer_id,
    dc.customer_key,
    sa.account_key as source_account_key,
    da.account_key as destination_account_key,
    dd.date_key,
    s.transfer_timestamp,
    s.amount,
    s.currency,
    s.transfer_type,
    s.transfer_status,
    s.destination_country,
    s.updated_at,
    current_timestamp as loaded_at
from staged s
left join dim_customer dc on s.customer_id = dc.customer_id
left join dim_account sa on s.source_account_id = sa.account_id
left join dim_account da on s.destination_account_id = da.account_id
left join dim_date dd on s.transfer_timestamp::date = dd.calendar_date

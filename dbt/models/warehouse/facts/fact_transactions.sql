{{
    config(
        unique_key='transaction_id',
        incremental_strategy='delete+insert'
    )
}}

with staged as (
    select * from {{ ref('stg_transactions') }}
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

dim_branch as (
    select branch_key, branch_id from {{ ref('dim_branch') }}
),

dim_merchant as (
    select merchant_key, merchant_id from {{ ref('dim_merchant') }}
),

dim_channel as (
    select channel_key, channel_name from {{ ref('dim_channel') }}
),

dim_txn_type as (
    select transaction_type_key, transaction_type from {{ ref('dim_transaction_type') }}
),

dim_date as (
    select date_key, calendar_date from {{ ref('dim_date') }}
)

select
    s.transaction_id,
    dc.customer_key,
    da.account_key,
    db.branch_key,
    dm.merchant_key,
    dch.channel_key,
    dtt.transaction_type_key,
    dd.date_key,
    s.transaction_timestamp,
    s.transaction_type,
    s.amount,
    s.currency,
    s.channel,
    s.transaction_status,
    s.reference_type,
    s.is_injected_anomaly,
    s.anomaly_type,
    s.updated_at,
    current_timestamp as loaded_at
from staged s
left join dim_customer dc on s.customer_id = dc.customer_id
left join dim_account da on s.account_id = da.account_id
left join dim_branch db on s.branch_id = db.branch_id
left join dim_merchant dm on s.merchant_id = dm.merchant_id
left join dim_channel dch on coalesce(s.channel, 'Unknown') = dch.channel_name
left join dim_txn_type dtt on s.transaction_type = dtt.transaction_type
left join dim_date dd on s.transaction_timestamp::date = dd.calendar_date

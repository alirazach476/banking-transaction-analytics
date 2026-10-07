{{
    config(
        unique_key='atm_txn_id',
        incremental_strategy='delete+insert'
    )
}}

with staged as (
    select * from {{ ref('stg_atm_transactions') }}
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

dim_card as (
    select card_key, card_id from {{ ref('dim_card') }}
),

dim_branch as (
    select branch_key, branch_id from {{ ref('dim_branch') }}
),

dim_txn_type as (
    select transaction_type_key, transaction_type from {{ ref('dim_transaction_type') }}
),

dim_date as (
    select date_key, calendar_date from {{ ref('dim_date') }}
)

select
    s.atm_txn_id,
    dc.customer_key,
    da.account_key,
    dcard.card_key,
    db.branch_key,
    dtt.transaction_type_key,
    dd.date_key,
    s.atm_id,
    s.transaction_timestamp,
    s.transaction_type,
    s.amount,
    s.transaction_status,
    s.updated_at,
    current_timestamp as loaded_at
from staged s
left join dim_customer dc on s.customer_id = dc.customer_id
left join dim_account da on s.account_id = da.account_id
left join dim_card dcard on s.card_id = dcard.card_id
left join dim_branch db on s.branch_id = db.branch_id
left join dim_txn_type dtt on s.transaction_type = dtt.transaction_type
left join dim_date dd on s.transaction_timestamp::date = dd.calendar_date

with card_txns as (
    select
        card_txn_id as payment_id,
        'Card' as payment_method,
        transaction_timestamp,
        transaction_timestamp::date as payment_date,
        amount,
        currency,
        transaction_status as payment_status,
        customer_id,
        account_id,
        merchant_id,
        card_id as instrument_id
    from {{ ref('stg_card_transactions') }}
),

atm_txns as (
    select
        atm_txn_id as payment_id,
        'ATM' as payment_method,
        transaction_timestamp,
        transaction_timestamp::date as payment_date,
        amount,
        'USD' as currency,
        transaction_status as payment_status,
        customer_id,
        account_id,
        null::text as merchant_id,
        card_id as instrument_id
    from {{ ref('stg_atm_transactions') }}
    where transaction_type <> 'Balance Inquiry'
),

combined as (
    select * from card_txns
    union all
    select * from atm_txns
)

select
    payment_id,
    payment_method,
    transaction_timestamp,
    payment_date,
    amount,
    currency,
    payment_status,
    customer_id,
    account_id,
    merchant_id,
    instrument_id,
    case when payment_status = 'Completed' then amount else 0 end as completed_amount,
    current_timestamp as refreshed_at
from combined

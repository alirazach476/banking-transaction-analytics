with source as (
    select * from {{ source('raw', 'card_transactions') }}
    where card_txn_id is not null
      and trim(card_txn_id) <> ''
),

deduped as (
    select
        *,
        row_number() over (
            partition by trim(card_txn_id)
            order by
                nullif(trim(updated_at), '')::timestamptz desc nulls last,
                _ingested_at desc nulls last
        ) as row_num
    from source
)

select
    trim(card_txn_id) as card_txn_id,
    trim(card_id) as card_id,
    trim(merchant_id) as merchant_id,
    trim(customer_id) as customer_id,
    trim(account_id) as account_id,
    replace(nullif(trim("timestamp"), ''), 'T', ' ')::timestamptz as transaction_timestamp,
    nullif(trim(amount), '')::numeric(18, 2) as amount,
    {{ standardize_status('status', 'card') }} as transaction_status,
    upper(trim(currency)) as currency,
    replace(nullif(trim(updated_at), ''), 'T', ' ')::timestamptz as updated_at,
    _ingested_at,
    _source_file,
    _source_system
from deduped
where row_num = 1

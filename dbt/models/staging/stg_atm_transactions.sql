with source as (
    select * from {{ source('raw', 'atm_transactions') }}
    where atm_txn_id is not null
      and trim(atm_txn_id) <> ''
),

deduped as (
    select
        *,
        row_number() over (
            partition by trim(atm_txn_id)
            order by
                nullif(trim(updated_at), '')::timestamptz desc nulls last,
                _ingested_at desc nulls last
        ) as row_num
    from source
)

select
    trim(atm_txn_id) as atm_txn_id,
    trim(card_id) as card_id,
    trim(atm_id) as atm_id,
    trim(branch_id) as branch_id,
    trim(customer_id) as customer_id,
    trim(account_id) as account_id,
    replace(nullif(trim("timestamp"), ''), 'T', ' ')::timestamptz as transaction_timestamp,
    nullif(trim(amount), '')::numeric(18, 2) as amount,
    initcap(trim(transaction_type)) as transaction_type,
    {{ standardize_status('status', 'atm') }} as transaction_status,
    replace(nullif(trim(updated_at), ''), 'T', ' ')::timestamptz as updated_at,
    _ingested_at,
    _source_file,
    _source_system
from deduped
where row_num = 1

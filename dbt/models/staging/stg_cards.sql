with source as (
    select * from {{ source('raw', 'cards') }}
    where card_id is not null
      and trim(card_id) <> ''
),

deduped as (
    select
        *,
        row_number() over (
            partition by trim(card_id)
            order by _ingested_at desc nulls last
        ) as row_num
    from source
)

select
    trim(card_id) as card_id,
    trim(customer_id) as customer_id,
    trim(account_id) as account_id,
    initcap(trim(card_type)) as card_type,
    nullif(trim(issue_date), '')::date as issue_date,
    nullif(trim(expiry_date), '')::date as expiry_date,
    {{ standardize_status('card_status', 'card') }} as card_status,
    _ingested_at,
    _source_file,
    _source_system
from deduped
where row_num = 1

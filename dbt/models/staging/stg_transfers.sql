with source as (
    select * from {{ source('raw', 'transfers') }}
    where transfer_id is not null
      and trim(transfer_id) <> ''
),

deduped as (
    select
        *,
        row_number() over (
            partition by trim(transfer_id)
            order by
                nullif(trim(updated_at), '')::timestamptz desc nulls last,
                _ingested_at desc nulls last
        ) as row_num
    from source
)

select
    trim(transfer_id) as transfer_id,
    trim(source_account_id) as source_account_id,
    trim(destination_account_id) as destination_account_id,
    trim(customer_id) as customer_id,
    replace(nullif(trim(transfer_timestamp), ''), 'T', ' ')::timestamptz as transfer_timestamp,
    nullif(trim(amount), '')::numeric(18, 2) as amount,
    upper(trim(currency)) as currency,
    initcap(trim(transfer_type)) as transfer_type,
    {{ standardize_status('status', 'transfer') }} as transfer_status,
    trim(destination_country) as destination_country,
    replace(nullif(trim(updated_at), ''), 'T', ' ')::timestamptz as updated_at,
    _ingested_at,
    _source_file,
    _source_system
from deduped
where row_num = 1

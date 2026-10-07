with source as (
    select * from {{ source('raw', 'transactions') }}
    where transaction_id is not null
      and trim(transaction_id) <> ''
),

deduped as (
    select
        *,
        row_number() over (
            partition by trim(transaction_id)
            order by
                nullif(trim(updated_at), '')::timestamptz desc nulls last,
                _ingested_at desc nulls last
        ) as row_num
    from source
)

select
    trim(transaction_id) as transaction_id,
    trim(account_id) as account_id,
    trim(customer_id) as customer_id,
    replace(nullif(trim(transaction_timestamp), ''), 'T', ' ')::timestamptz as transaction_timestamp,
    initcap(trim(transaction_type)) as transaction_type,
    nullif(trim(amount), '')::numeric(18, 2) as amount,
    upper(trim(currency)) as currency,
    trim(channel) as channel,
    nullif(trim(merchant_id), '') as merchant_id,
    nullif(trim(branch_id), '') as branch_id,
    {{ standardize_status('transaction_status', 'transaction') }} as transaction_status,
    lower(trim(reference_type)) as reference_type,
    case lower(trim(is_injected_anomaly))
        when 'true' then true
        when '1' then true
        when 'yes' then true
        else false
    end as is_injected_anomaly,
    nullif(trim(anomaly_type), '') as anomaly_type,
    replace(nullif(trim(updated_at), ''), 'T', ' ')::timestamptz as updated_at,
    _ingested_at,
    _source_file,
    _source_system
from deduped
where row_num = 1

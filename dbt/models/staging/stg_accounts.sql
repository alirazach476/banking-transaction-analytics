with source as (
    select * from {{ source('raw', 'accounts') }}
    where account_id is not null
      and trim(account_id) <> ''
),

deduped as (
    select
        *,
        row_number() over (
            partition by trim(account_id)
            order by _ingested_at desc nulls last
        ) as row_num
    from source
)

select
    trim(account_id) as account_id,
    trim(customer_id) as customer_id,
    initcap(trim(account_type)) as account_type,
    trim(branch_id) as branch_id,
    nullif(trim(open_date), '')::date as open_date,
    nullif(trim(close_date), '')::date as close_date,
    upper(trim(currency)) as currency,
    nullif(trim(current_balance), '')::numeric(18, 2) as current_balance,
    {{ standardize_status('account_status', 'account') }} as account_status,
    _ingested_at,
    _source_file,
    _source_system
from deduped
where row_num = 1

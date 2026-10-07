with source as (
    select * from {{ source('raw', 'merchants') }}
    where merchant_id is not null
      and trim(merchant_id) <> ''
),

deduped as (
    select
        *,
        row_number() over (
            partition by trim(merchant_id)
            order by _ingested_at desc nulls last
        ) as row_num
    from source
)

select
    trim(merchant_id) as merchant_id,
    trim(merchant_name) as merchant_name,
    trim(merchant_category) as merchant_category,
    trim(city) as city,
    trim(region) as region,
    {{ standardize_status('merchant_status', 'merchant') }} as merchant_status,
    _ingested_at,
    _source_file,
    _source_system
from deduped
where row_num = 1

with source as (
    select * from {{ source('raw', 'customers') }}
    where customer_id is not null
      and trim(customer_id) <> ''
),

deduped as (
    select
        *,
        row_number() over (
            partition by trim(customer_id)
            order by _ingested_at desc nulls last
        ) as row_num
    from source
)

select
    trim(customer_id) as customer_id,
    trim(first_name) as first_name,
    trim(last_name) as last_name,
    nullif(trim(date_of_birth), '')::date as date_of_birth,
    trim(gender) as gender,
    initcap(trim(customer_type)) as customer_type,
    nullif(trim(registration_date), '')::date as registration_date,
    {{ standardize_status('customer_status', 'customer') }} as customer_status,
    trim(city) as city,
    trim(region) as region,
    trim(country) as country,
    _ingested_at,
    _source_file,
    _source_system
from deduped
where row_num = 1

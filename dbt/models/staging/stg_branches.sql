with source as (
    select * from {{ source('raw', 'branches') }}
    where branch_id is not null
      and trim(branch_id) <> ''
),

deduped as (
    select
        *,
        row_number() over (
            partition by trim(branch_id)
            order by _ingested_at desc nulls last
        ) as row_num
    from source
)

select
    trim(branch_id) as branch_id,
    trim(branch_name) as branch_name,
    trim(city) as city,
    trim(region) as region,
    trim(country) as country,
    initcap(trim(branch_type)) as branch_type,
    nullif(trim(opening_date), '')::date as opening_date,
    {{ standardize_status('branch_status', 'branch') }} as branch_status,
    _ingested_at,
    _source_file,
    _source_system
from deduped
where row_num = 1

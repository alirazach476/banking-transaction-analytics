with channels as (
    select distinct coalesce(channel, 'Unknown') as channel_name
    from {{ ref('stg_transactions') }}
)

select
    row_number() over (order by channel_name) as channel_key,
    channel_name,
    case
        when channel_name ilike '%atm%' then 'Self-Service'
        when channel_name ilike '%mobile%' then 'Digital'
        when channel_name ilike '%internet%' then 'Digital'
        when channel_name ilike '%branch%' then 'Branch'
        when channel_name ilike '%phone%' then 'Contact Center'
        else 'Other'
    end as channel_group,
    current_timestamp as loaded_at
from channels

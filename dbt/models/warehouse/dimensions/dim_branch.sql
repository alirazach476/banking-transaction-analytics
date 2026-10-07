select
    row_number() over (order by branch_id) as branch_key,
    branch_id,
    branch_name,
    city,
    region,
    country,
    branch_type,
    opening_date,
    branch_status,
    current_timestamp as loaded_at
from {{ ref('stg_branches') }}

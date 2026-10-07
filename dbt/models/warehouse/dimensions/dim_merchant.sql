select
    row_number() over (order by merchant_id) as merchant_key,
    merchant_id,
    merchant_name,
    merchant_category,
    city,
    region,
    merchant_status,
    current_timestamp as loaded_at
from {{ ref('stg_merchants') }}

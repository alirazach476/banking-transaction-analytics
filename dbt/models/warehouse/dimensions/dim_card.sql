select
    row_number() over (order by card_id) as card_key,
    card_id,
    customer_id,
    account_id,
    card_type,
    issue_date,
    expiry_date,
    card_status,
    current_timestamp as loaded_at
from {{ ref('stg_cards') }}

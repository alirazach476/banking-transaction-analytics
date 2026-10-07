select
    row_number() over (order by account_id) as account_key,
    account_id,
    customer_id,
    account_type,
    branch_id,
    open_date,
    close_date,
    currency,
    current_balance,
    account_status,
    current_timestamp as loaded_at
from {{ ref('stg_accounts') }}

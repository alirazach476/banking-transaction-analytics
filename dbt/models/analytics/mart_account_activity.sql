with metrics as (
    select * from {{ ref('int_account_transaction_metrics') }}
),

accounts as (
    select
        account_id,
        customer_id,
        account_type,
        branch_id,
        currency,
        current_balance,
        account_status,
        open_date
    from {{ ref('stg_accounts') }}
)

select
    a.account_id,
    a.customer_id,
    a.account_type,
    a.branch_id,
    a.currency,
    a.current_balance,
    a.account_status,
    a.open_date,
    m.transaction_count,
    m.completed_count,
    m.failed_count,
    m.total_amount,
    m.total_completed_amount,
    round(m.avg_completed_amount, 2) as avg_completed_amount,
    m.first_transaction_at,
    m.last_transaction_at,
    m.days_since_last_transaction,
    case
        when m.transaction_count = 0 or m.days_since_last_transaction > 90 then 'Inactive'
        when m.transaction_count < 10 then 'Low Activity'
        when m.transaction_count between 10 and 49 then 'Medium Activity'
        when m.transaction_count between 50 and 199 then 'High Activity'
        when m.transaction_count >= 200 then 'Premium Activity'
        else 'Unknown'
    end as activity_segment,
    current_timestamp as refreshed_at
from accounts a
left join metrics m on a.account_id = m.account_id

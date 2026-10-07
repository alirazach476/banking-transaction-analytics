with enriched as (
    select * from {{ ref('int_transaction_enriched') }}
),

account_spine as (
    select account_id, customer_id, branch_id, account_type, account_status
    from {{ ref('stg_accounts') }}
)

select
    a.account_id,
    a.customer_id,
    a.branch_id,
    a.account_type,
    a.account_status,
    count(e.transaction_id) as transaction_count,
    count(e.transaction_id) filter (where e.transaction_status = 'Completed') as completed_count,
    count(e.transaction_id) filter (where e.transaction_status = 'Failed') as failed_count,
    coalesce(sum(e.amount), 0) as total_amount,
    coalesce(sum(e.completed_amount), 0) as total_completed_amount,
    coalesce(avg(e.amount) filter (where e.transaction_status = 'Completed'), 0) as avg_completed_amount,
    min(e.transaction_timestamp) as first_transaction_at,
    max(e.transaction_timestamp) as last_transaction_at,
    coalesce(
        extract(day from (current_timestamp - max(e.transaction_timestamp))),
        9999
    )::int as days_since_last_transaction
from account_spine a
left join enriched e on a.account_id = e.account_id
group by
    a.account_id,
    a.customer_id,
    a.branch_id,
    a.account_type,
    a.account_status

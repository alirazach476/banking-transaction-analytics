with enriched as (
    select * from {{ ref('int_transaction_enriched') }}
),

customer_spine as (
    select customer_id from {{ ref('stg_customers') }}
),

-- Use dataset as-of date (max txn timestamp) — not wall-clock CURRENT_DATE —
-- so synthetic historical windows segment correctly in demos.
as_of as (
    select coalesce(max(transaction_timestamp), current_timestamp) as as_of_ts
    from enriched
)

select
    cs.customer_id,
    count(e.transaction_id) as transaction_count,
    count(e.transaction_id) filter (where e.transaction_status = 'Completed') as completed_count,
    count(e.transaction_id) filter (where e.transaction_status = 'Failed') as failed_count,
    count(e.transaction_id) filter (where e.transaction_status = 'Pending') as pending_count,
    coalesce(sum(e.amount), 0) as total_amount,
    coalesce(sum(e.completed_amount), 0) as total_completed_amount,
    coalesce(avg(e.amount) filter (where e.transaction_status = 'Completed'), 0) as avg_completed_amount,
    coalesce(max(e.amount), 0) as max_amount,
    min(e.transaction_timestamp) as first_transaction_at,
    max(e.transaction_timestamp) as last_transaction_at,
    coalesce(
        extract(day from ((select as_of_ts from as_of) - max(e.transaction_timestamp))),
        9999
    )::int as days_since_last_transaction,
    count(distinct e.channel) as distinct_channels,
    count(distinct e.account_id) as distinct_accounts
from customer_spine cs
left join enriched e on cs.customer_id = e.customer_id
group by cs.customer_id

with enriched as (
    select * from {{ ref('int_transaction_enriched') }}
),

branches as (
    select * from {{ ref('stg_branches') }}
),

branch_metrics as (
    select
        branch_id,
        count(*) as transaction_count,
        count(*) filter (where transaction_status = 'Completed') as completed_count,
        count(*) filter (where transaction_status = 'Failed') as failed_count,
        coalesce(sum(completed_amount), 0) as total_completed_amount,
        count(distinct customer_id) as active_customers,
        count(distinct account_id) as active_accounts
    from enriched
    where branch_id is not null
    group by branch_id
)

select
    b.branch_id,
    b.branch_name,
    b.city,
    b.region,
    b.country,
    b.branch_type,
    b.branch_status,
    coalesce(bm.transaction_count, 0) as transaction_count,
    coalesce(bm.completed_count, 0) as completed_count,
    coalesce(bm.failed_count, 0) as failed_count,
    coalesce(bm.total_completed_amount, 0) as total_completed_amount,
    coalesce(bm.active_customers, 0) as active_customers,
    coalesce(bm.active_accounts, 0) as active_accounts,
    round(
        100.0 * coalesce(bm.failed_count, 0) / nullif(coalesce(bm.transaction_count, 0), 0),
        2
    ) as failure_rate_pct,
    current_timestamp as refreshed_at
from branches b
left join branch_metrics bm on b.branch_id = bm.branch_id

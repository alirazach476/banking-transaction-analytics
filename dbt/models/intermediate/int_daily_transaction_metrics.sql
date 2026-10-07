with enriched as (
    select * from {{ ref('int_transaction_enriched') }}
)

select
    transaction_date,
    count(*) as transaction_count,
    count(*) filter (where transaction_status = 'Completed') as completed_count,
    count(*) filter (where transaction_status = 'Failed') as failed_count,
    count(*) filter (where transaction_status = 'Pending') as pending_count,
    count(*) filter (where transaction_status = 'Reversed') as reversed_count,
    coalesce(sum(amount), 0) as total_amount,
    coalesce(sum(completed_amount), 0) as total_completed_amount,
    coalesce(avg(amount) filter (where transaction_status = 'Completed'), 0) as avg_completed_amount,
    count(distinct customer_id) as active_customers,
    count(distinct account_id) as active_accounts,
    count(distinct channel) as active_channels,
    count(*) filter (where is_injected_anomaly) as anomaly_count
from enriched
where transaction_date is not null
group by transaction_date

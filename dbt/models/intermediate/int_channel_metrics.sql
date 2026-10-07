with enriched as (
    select * from {{ ref('int_transaction_enriched') }}
)

select
    coalesce(channel, 'Unknown') as channel,
    transaction_date,
    count(*) as transaction_count,
    count(*) filter (where transaction_status = 'Completed') as completed_count,
    count(*) filter (where transaction_status = 'Failed') as failed_count,
    coalesce(sum(amount), 0) as total_amount,
    coalesce(sum(completed_amount), 0) as total_completed_amount,
    coalesce(avg(amount) filter (where transaction_status = 'Completed'), 0) as avg_completed_amount,
    count(distinct customer_id) as active_customers,
    round(
        100.0 * count(*) filter (where transaction_status = 'Failed')
        / nullif(count(*), 0),
        2
    ) as failure_rate_pct
from enriched
group by coalesce(channel, 'Unknown'), transaction_date

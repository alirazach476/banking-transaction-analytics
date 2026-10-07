with channel_daily as (
    select * from {{ ref('int_channel_metrics') }}
),

channel_summary as (
    select
        channel,
        sum(transaction_count) as transaction_count,
        sum(completed_count) as completed_count,
        sum(failed_count) as failed_count,
        sum(total_completed_amount) as total_completed_amount,
        avg(avg_completed_amount) as avg_completed_amount,
        max(active_customers) as peak_daily_active_customers,
        min(transaction_date) as first_seen_date,
        max(transaction_date) as last_seen_date
    from channel_daily
    group by channel
)

select
    cs.channel,
    dc.channel_group,
    cs.transaction_count,
    cs.completed_count,
    cs.failed_count,
    cs.total_completed_amount,
    round(cs.avg_completed_amount, 2) as avg_completed_amount,
    cs.peak_daily_active_customers,
    cs.first_seen_date,
    cs.last_seen_date,
    round(100.0 * cs.failed_count / nullif(cs.transaction_count, 0), 2) as failure_rate_pct,
    round(
        100.0 * cs.completed_count / nullif(cs.transaction_count, 0),
        2
    ) as success_rate_pct,
    current_timestamp as refreshed_at
from channel_summary cs
left join {{ ref('dim_channel') }} dc on cs.channel = dc.channel_name

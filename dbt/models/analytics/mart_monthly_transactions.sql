with daily as (
    select * from {{ ref('int_daily_transaction_metrics') }}
),

monthly as (
    select
        date_trunc('month', transaction_date)::date as month_start,
        sum(transaction_count) as transaction_count,
        sum(completed_count) as completed_count,
        sum(failed_count) as failed_count,
        sum(pending_count) as pending_count,
        sum(reversed_count) as reversed_count,
        sum(total_amount) as total_amount,
        sum(total_completed_amount) as total_completed_amount,
        avg(avg_completed_amount) as avg_completed_amount,
        max(active_customers) as peak_daily_active_customers,
        sum(anomaly_count) as anomaly_count
    from daily
    group by date_trunc('month', transaction_date)::date
)

select
    month_start,
    to_char(month_start, 'YYYY-MM') as month_label,
    transaction_count,
    completed_count,
    failed_count,
    pending_count,
    reversed_count,
    total_amount,
    total_completed_amount,
    round(avg_completed_amount, 2) as avg_completed_amount,
    peak_daily_active_customers,
    anomaly_count,
    round(
        100.0 * failed_count / nullif(transaction_count, 0),
        2
    ) as failure_rate_pct,
    lag(total_completed_amount, 1) over (order by month_start) as prev_month_completed_amount,
    round(
        100.0 * (total_completed_amount - lag(total_completed_amount, 1) over (order by month_start))
        / nullif(lag(total_completed_amount, 1) over (order by month_start), 0),
        2
    ) as mom_completed_amount_pct_change,
    current_timestamp as refreshed_at
from monthly

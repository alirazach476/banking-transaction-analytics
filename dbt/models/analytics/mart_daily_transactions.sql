with daily as (
    select * from {{ ref('int_daily_transaction_metrics') }}
)

select
    transaction_date,
    transaction_count,
    completed_count,
    failed_count,
    pending_count,
    reversed_count,
    total_amount,
    total_completed_amount,
    avg_completed_amount,
    active_customers,
    active_accounts,
    active_channels,
    anomaly_count,
    lag(total_completed_amount, 1) over (order by transaction_date) as prev_day_completed_amount,
    round(
        100.0 * (total_completed_amount - lag(total_completed_amount, 1) over (order by transaction_date))
        / nullif(lag(total_completed_amount, 1) over (order by transaction_date), 0),
        2
    ) as dod_completed_amount_pct_change,
    lag(total_completed_amount, 30) over (order by transaction_date) as same_day_prev_month_amount,
    round(
        100.0 * (total_completed_amount - lag(total_completed_amount, 30) over (order by transaction_date))
        / nullif(lag(total_completed_amount, 30) over (order by transaction_date), 0),
        2
    ) as mom_completed_amount_pct_change,
    round(
        avg(total_completed_amount) over (
            order by transaction_date
            rows between 6 preceding and current row
        ),
        2
    ) as rolling_7d_avg_completed_amount,
    round(
        avg(total_completed_amount) over (
            order by transaction_date
            rows between 29 preceding and current row
        ),
        2
    ) as rolling_30d_avg_completed_amount,
    round(
        avg(transaction_count::numeric) over (
            order by transaction_date
            rows between 6 preceding and current row
        ),
        2
    ) as rolling_7d_avg_transaction_count,
    round(
        avg(transaction_count::numeric) over (
            order by transaction_date
            rows between 29 preceding and current row
        ),
        2
    ) as rolling_30d_avg_transaction_count,
    current_timestamp as refreshed_at
from daily

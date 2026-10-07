-- Daily transaction trends with 7-day rolling averages
-- Demonstrates: date dimension, SUM() OVER, rolling window

WITH daily AS (
    SELECT
        d.calendar_date,
        d.day_name,
        d.is_weekend,
        COUNT(*) AS transaction_count,
        SUM(ft.amount) AS transaction_value,
        AVG(ft.amount) AS avg_transaction_value,
        SUM(CASE WHEN ft.transaction_status = 'Completed' THEN 1 ELSE 0 END) AS completed_count,
        SUM(CASE WHEN ft.transaction_status = 'Failed' THEN 1 ELSE 0 END) AS failed_count
    FROM warehouse.fact_transactions ft
    INNER JOIN warehouse.dim_date d ON ft.date_key = d.date_key
    GROUP BY d.calendar_date, d.day_name, d.is_weekend
),

rolling AS (
    SELECT
        calendar_date,
        day_name,
        is_weekend,
        transaction_count,
        transaction_value,
        avg_transaction_value,
        completed_count,
        failed_count,
        AVG(transaction_count) OVER (
            ORDER BY calendar_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS rolling_7d_avg_count,
        AVG(transaction_value) OVER (
            ORDER BY calendar_date
            ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
        ) AS rolling_7d_avg_value,
        SUM(transaction_value) OVER (
            ORDER BY calendar_date
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS cumulative_value
    FROM daily
)

SELECT
    calendar_date,
    day_name,
    is_weekend,
    transaction_count,
    ROUND(transaction_value, 2) AS transaction_value,
    ROUND(avg_transaction_value, 2) AS avg_transaction_value,
    ROUND(rolling_7d_avg_count, 1) AS rolling_7d_avg_count,
    ROUND(rolling_7d_avg_value, 2) AS rolling_7d_avg_value,
    ROUND(cumulative_value, 2) AS cumulative_value,
    ROUND(completed_count::numeric / NULLIF(transaction_count, 0) * 100, 2) AS success_rate_pct
FROM rolling
ORDER BY calendar_date;

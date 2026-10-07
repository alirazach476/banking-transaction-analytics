-- Monthly transaction growth — MoM and YoY
-- Demonstrates: DATE_TRUNC, LAG(), CTEs

WITH monthly AS (
    SELECT
        DATE_TRUNC('month', d.calendar_date)::date AS month_start,
        COUNT(*) AS transaction_count,
        SUM(ft.amount) AS transaction_value,
        AVG(ft.amount) AS avg_transaction_value
    FROM warehouse.fact_transactions ft
    INNER JOIN warehouse.dim_date d ON ft.date_key = d.date_key
    GROUP BY DATE_TRUNC('month', d.calendar_date)
),

growth AS (
    SELECT
        month_start,
        transaction_count,
        transaction_value,
        avg_transaction_value,
        LAG(transaction_value) OVER (ORDER BY month_start) AS prior_month_value,
        LAG(transaction_value, 12) OVER (ORDER BY month_start) AS prior_year_value,
        LAG(transaction_count) OVER (ORDER BY month_start) AS prior_month_count
    FROM monthly
)

SELECT
    month_start,
    transaction_count,
    ROUND(transaction_value, 2) AS transaction_value,
    ROUND(avg_transaction_value, 2) AS avg_transaction_value,
    ROUND(prior_month_value, 2) AS prior_month_value,
    ROUND(
        (transaction_value - prior_month_value)
        / NULLIF(prior_month_value, 0) * 100,
        2
    ) AS mom_value_growth_pct,
    ROUND(
        (transaction_count - prior_month_count)
        / NULLIF(prior_month_count::numeric, 0) * 100,
        2
    ) AS mom_count_growth_pct,
    ROUND(
        (transaction_value - prior_year_value)
        / NULLIF(prior_year_value, 0) * 100,
        2
    ) AS yoy_value_growth_pct
FROM growth
ORDER BY month_start;

-- Top customers by total transaction value
-- Synthetic NovaBank data — portfolio analytics query
-- Demonstrates: JOINs, aggregation, RANK(), DENSE_RANK()

WITH customer_totals AS (
    SELECT
        dc.customer_id,
        dc.customer_type,
        dc.region,
        COUNT(*) AS transaction_count,
        SUM(ft.amount) AS total_transaction_value,
        AVG(ft.amount) AS avg_transaction_value,
        MAX(ft.transaction_timestamp) AS last_transaction_at
    FROM warehouse.fact_transactions ft
    INNER JOIN warehouse.dim_customer dc
        ON ft.customer_key = dc.customer_key
        AND dc.is_current = TRUE
    WHERE ft.transaction_status = 'Completed'
    GROUP BY dc.customer_id, dc.customer_type, dc.region
),

ranked AS (
    SELECT
        *,
        RANK() OVER (ORDER BY total_transaction_value DESC) AS value_rank,
        DENSE_RANK() OVER (ORDER BY transaction_count DESC) AS volume_rank,
        PERCENT_RANK() OVER (ORDER BY total_transaction_value) AS value_percentile
    FROM customer_totals
)

SELECT
    customer_id,
    customer_type,
    region,
    transaction_count,
    ROUND(total_transaction_value, 2) AS total_transaction_value,
    ROUND(avg_transaction_value, 2) AS avg_transaction_value,
    last_transaction_at,
    value_rank,
    volume_rank,
    ROUND(value_percentile::numeric, 4) AS value_percentile
FROM ranked
WHERE value_rank <= 25
ORDER BY value_rank;

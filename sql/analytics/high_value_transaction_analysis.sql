-- High-value transaction analysis with percentiles and z-scores
-- Demonstrates: NTILE(), window stats, filtering

WITH customer_stats AS (
    SELECT
        customer_key,
        AVG(amount) AS customer_avg,
        STDDEV(amount) AS customer_std,
        PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY amount) AS customer_p95
    FROM warehouse.fact_transactions
    WHERE transaction_status = 'Completed'
    GROUP BY customer_key
),

enriched AS (
    SELECT
        ft.transaction_id,
        dc.customer_id,
        dc.customer_type,
        ft.transaction_timestamp,
        ft.amount,
        ch.channel_name,
        dtt.transaction_type,
        cs.customer_avg,
        cs.customer_std,
        cs.customer_p95,
        CASE
            WHEN cs.customer_std > 0
            THEN (ft.amount - cs.customer_avg) / cs.customer_std
            ELSE 0
        END AS z_score,
        NTILE(100) OVER (ORDER BY ft.amount) AS amount_percentile
    FROM warehouse.fact_transactions ft
    INNER JOIN warehouse.dim_customer dc
        ON ft.customer_key = dc.customer_key AND dc.is_current = TRUE
    INNER JOIN warehouse.dim_channel ch ON ft.channel_key = ch.channel_key
    INNER JOIN warehouse.dim_transaction_type dtt
        ON ft.transaction_type_key = dtt.transaction_type_key
    INNER JOIN customer_stats cs ON ft.customer_key = cs.customer_key
    WHERE ft.transaction_status = 'Completed'
)

SELECT
    transaction_id,
    customer_id,
    customer_type,
    transaction_timestamp,
    amount,
    channel_name,
    transaction_type,
    ROUND(customer_avg, 2) AS customer_avg,
    ROUND(z_score, 2) AS z_score,
    amount_percentile,
    CASE
        WHEN amount >= customer_p95 THEN 'Above customer P95'
        WHEN ABS(z_score) >= 3 THEN 'Statistical outlier (3σ)'
        WHEN amount_percentile >= 99 THEN 'Global top 1%'
        ELSE 'Elevated'
    END AS high_value_category
FROM enriched
WHERE amount >= customer_p95
   OR ABS(z_score) >= 3
   OR amount_percentile >= 99
ORDER BY amount DESC
LIMIT 200;

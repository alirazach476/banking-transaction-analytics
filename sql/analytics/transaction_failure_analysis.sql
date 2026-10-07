-- Transaction failure analysis by channel, type, and hour
-- Demonstrates: CASE, GROUP BY, conditional aggregation

WITH failures AS (
    SELECT
        ft.transaction_id,
        ft.transaction_timestamp,
        EXTRACT(HOUR FROM ft.transaction_timestamp) AS hour_of_day,
        ft.amount,
        ft.transaction_status,
        ch.channel_name,
        dtt.transaction_type,
        dc.customer_type,
        dc.region
    FROM warehouse.fact_transactions ft
    INNER JOIN warehouse.dim_channel ch ON ft.channel_key = ch.channel_key
    INNER JOIN warehouse.dim_transaction_type dtt
        ON ft.transaction_type_key = dtt.transaction_type_key
    INNER JOIN warehouse.dim_customer dc
        ON ft.customer_key = dc.customer_key AND dc.is_current = TRUE
),

summary AS (
    SELECT
        channel_name,
        transaction_type,
        region,
        COUNT(*) AS total_attempts,
        SUM(CASE WHEN transaction_status = 'Failed' THEN 1 ELSE 0 END) AS failed_count,
        SUM(CASE WHEN transaction_status = 'Completed' THEN 1 ELSE 0 END) AS completed_count,
        SUM(CASE WHEN transaction_status = 'Reversed' THEN 1 ELSE 0 END) AS reversed_count,
        AVG(CASE WHEN transaction_status = 'Failed' THEN amount END) AS avg_failed_amount
    FROM failures
    GROUP BY channel_name, transaction_type, region
)

SELECT
    channel_name,
    transaction_type,
    region,
    total_attempts,
    failed_count,
    ROUND(failed_count::numeric / NULLIF(total_attempts, 0) * 100, 2) AS failure_rate_pct,
    ROUND(completed_count::numeric / NULLIF(total_attempts, 0) * 100, 2) AS success_rate_pct,
    ROUND(reversed_count::numeric / NULLIF(total_attempts, 0) * 100, 2) AS reversal_rate_pct,
    ROUND(avg_failed_amount, 2) AS avg_failed_amount
FROM summary
WHERE failed_count > 0
ORDER BY failure_rate_pct DESC, failed_count DESC
LIMIT 50;

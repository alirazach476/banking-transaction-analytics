-- Anomaly candidates: rapid transactions and statistical outliers
-- Demonstrates: window COUNT, RANGE BETWEEN, multi-rule flagging
-- Terminology: potential anomalies — not confirmed fraud

WITH ordered_txns AS (
    SELECT
        ft.transaction_id,
        dc.customer_id,
        ft.transaction_timestamp,
        ft.amount,
        ch.channel_name,
        EXTRACT(HOUR FROM ft.transaction_timestamp) AS hour_of_day
    FROM warehouse.fact_transactions ft
    INNER JOIN warehouse.dim_customer dc
        ON ft.customer_key = dc.customer_key AND dc.is_current = TRUE
    INNER JOIN warehouse.dim_channel ch ON ft.channel_key = ch.channel_key
),

rapid AS (
    SELECT
        *,
        COUNT(*) OVER (
            PARTITION BY customer_id
            ORDER BY transaction_timestamp
            RANGE BETWEEN INTERVAL '10 minutes' PRECEDING AND CURRENT ROW
        ) AS txns_in_10_min,
        COUNT(*) OVER (
            PARTITION BY customer_id
            ORDER BY transaction_timestamp
            RANGE BETWEEN INTERVAL '24 hours' PRECEDING AND CURRENT ROW
        ) AS txns_in_24_hours
    FROM ordered_txns
),

customer_baseline AS (
    SELECT
        customer_id,
        AVG(amount) AS avg_amount,
        STDDEV(amount) AS std_amount
    FROM ordered_txns
    GROUP BY customer_id
),

scored AS (
    SELECT
        r.*,
        cb.avg_amount,
        cb.std_amount,
        CASE WHEN cb.std_amount > 0
             THEN (r.amount - cb.avg_amount) / cb.std_amount
             ELSE 0 END AS z_score
    FROM rapid r
    INNER JOIN customer_baseline cb ON r.customer_id = cb.customer_id
)

SELECT
    transaction_id,
    customer_id,
    transaction_timestamp,
    amount,
    channel_name,
    hour_of_day,
    txns_in_10_min,
    txns_in_24_hours,
    ROUND(z_score, 2) AS z_score,
    ARRAY_REMOVE(ARRAY[
        CASE WHEN txns_in_10_min >= 5 THEN 'Rapid Transactions' END,
        CASE WHEN txns_in_24_hours >= 20 THEN 'Unusually High Frequency' END,
        CASE WHEN ABS(z_score) >= 3 THEN 'Unusually High Amount' END,
        CASE WHEN hour_of_day BETWEEN 0 AND 5 AND amount > 500 THEN 'Unusual Transaction Time' END
    ], NULL) AS potential_anomaly_reasons
FROM scored
WHERE txns_in_10_min >= 5
   OR txns_in_24_hours >= 20
   OR ABS(z_score) >= 3
   OR (hour_of_day BETWEEN 0 AND 5 AND amount > 500)
ORDER BY txns_in_10_min DESC, ABS(z_score) DESC
LIMIT 500;

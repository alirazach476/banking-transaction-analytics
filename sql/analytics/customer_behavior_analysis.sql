-- Customer behavior: sequence, lag comparison, activity segments
-- Demonstrates: LAG(), LEAD(), ROW_NUMBER(), cohort-style patterns

WITH txn_sequence AS (
    SELECT
        ft.transaction_id,
        dc.customer_id,
        dc.customer_type,
        ft.transaction_timestamp,
        ft.amount,
        ch.channel_name,
        ROW_NUMBER() OVER (
            PARTITION BY dc.customer_id
            ORDER BY ft.transaction_timestamp
        ) AS txn_sequence_num,
        LAG(ft.amount) OVER (
            PARTITION BY dc.customer_id
            ORDER BY ft.transaction_timestamp
        ) AS previous_amount,
        LAG(ft.transaction_timestamp) OVER (
            PARTITION BY dc.customer_id
            ORDER BY ft.transaction_timestamp
        ) AS previous_timestamp,
        LEAD(ft.amount) OVER (
            PARTITION BY dc.customer_id
            ORDER BY ft.transaction_timestamp
        ) AS next_amount
    FROM warehouse.fact_transactions ft
    INNER JOIN warehouse.dim_customer dc
        ON ft.customer_key = dc.customer_key AND dc.is_current = TRUE
    INNER JOIN warehouse.dim_channel ch ON ft.channel_key = ch.channel_key
    WHERE ft.transaction_status = 'Completed'
),

customer_summary AS (
    SELECT
        customer_id,
        customer_type,
        COUNT(*) AS transaction_count,
        SUM(amount) AS total_value,
        AVG(amount) AS avg_amount,
        STDDEV(amount) AS std_amount,
        MAX(transaction_timestamp) AS last_txn,
        MIN(transaction_timestamp) AS first_txn,
        COUNT(DISTINCT channel_name) AS channels_used
    FROM txn_sequence
    GROUP BY customer_id, customer_type
),

segmented AS (
    SELECT
        cs.*,
        CASE
            WHEN transaction_count = 0 THEN 'Inactive'
            WHEN transaction_count < 10 THEN 'Low Activity'
            WHEN transaction_count BETWEEN 10 AND 49 THEN 'Medium Activity'
            WHEN transaction_count BETWEEN 50 AND 199 THEN 'High Activity'
            ELSE 'Premium Activity'
        END AS activity_segment
    FROM customer_summary cs
)

SELECT
    activity_segment,
    customer_type,
    COUNT(*) AS customer_count,
    ROUND(AVG(transaction_count), 1) AS avg_txn_count,
    ROUND(AVG(total_value), 2) AS avg_total_value,
    ROUND(AVG(channels_used), 1) AS avg_channels_used,
    ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY total_value), 2) AS median_total_value
FROM segmented
GROUP BY activity_segment, customer_type
ORDER BY
    CASE activity_segment
        WHEN 'Inactive' THEN 1
        WHEN 'Low Activity' THEN 2
        WHEN 'Medium Activity' THEN 3
        WHEN 'High Activity' THEN 4
        WHEN 'Premium Activity' THEN 5
    END,
    customer_type;

-- Customer transaction sequence with previous/next comparison
-- Demonstrates: ROW_NUMBER(), LAG(), LEAD(), running SUM

WITH sequenced AS (
    SELECT
        dc.customer_id,
        ft.transaction_id,
        ft.transaction_timestamp,
        ft.amount,
        dtt.transaction_type,
        ch.channel_name,
        ROW_NUMBER() OVER (
            PARTITION BY dc.customer_id
            ORDER BY ft.transaction_timestamp, ft.transaction_id
        ) AS txn_seq,
        LAG(ft.transaction_id) OVER w AS prev_transaction_id,
        LAG(ft.amount) OVER w AS prev_amount,
        LAG(ft.transaction_timestamp) OVER w AS prev_timestamp,
        LEAD(ft.amount) OVER w AS next_amount,
        ft.amount - LAG(ft.amount) OVER w AS amount_change_from_prev,
        SUM(ft.amount) OVER (
            PARTITION BY dc.customer_id
            ORDER BY ft.transaction_timestamp, ft.transaction_id
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS running_total_amount,
        COUNT(*) OVER (
            PARTITION BY dc.customer_id
            ORDER BY ft.transaction_timestamp
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS running_txn_count
    FROM warehouse.fact_transactions ft
    INNER JOIN warehouse.dim_customer dc
        ON ft.customer_key = dc.customer_key AND dc.is_current = TRUE
    INNER JOIN warehouse.dim_transaction_type dtt
        ON ft.transaction_type_key = dtt.transaction_type_key
    INNER JOIN warehouse.dim_channel ch ON ft.channel_key = ch.channel_key
    WINDOW w AS (
        PARTITION BY dc.customer_id
        ORDER BY ft.transaction_timestamp, ft.transaction_id
    )
)

SELECT
    customer_id,
    txn_seq,
    transaction_id,
    transaction_timestamp,
    amount,
    transaction_type,
    channel_name,
    prev_transaction_id,
    prev_amount,
    EXTRACT(EPOCH FROM (transaction_timestamp - prev_timestamp)) / 60 AS minutes_since_prev,
    amount_change_from_prev,
    ROUND(running_total_amount, 2) AS running_total_amount,
    running_txn_count
FROM sequenced
WHERE txn_seq <= 5  -- first 5 transactions per customer (sample)
   OR ABS(amount_change_from_prev) > COALESCE(prev_amount, 0) * 5  -- sudden jumps
ORDER BY customer_id, txn_seq
LIMIT 1000;

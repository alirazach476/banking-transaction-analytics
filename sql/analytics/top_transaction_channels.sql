-- Channel performance ranking
-- Demonstrates: dimension join, percentages, window functions

WITH channel_stats AS (
    SELECT
        ch.channel_name,
        COUNT(*) AS transaction_count,
        SUM(ft.amount) AS transaction_value,
        AVG(ft.amount) AS avg_transaction,
        SUM(CASE WHEN ft.transaction_status = 'Completed' THEN 1 ELSE 0 END) AS completed_count,
        SUM(CASE WHEN ft.transaction_status = 'Failed' THEN 1 ELSE 0 END) AS failed_count
    FROM warehouse.fact_transactions ft
    INNER JOIN warehouse.dim_channel ch ON ft.channel_key = ch.channel_key
    GROUP BY ch.channel_name
),

with_shares AS (
    SELECT
        *,
        ROUND(
            transaction_count::numeric
            / SUM(transaction_count) OVER () * 100,
            2
        ) AS pct_of_volume,
        ROUND(
            transaction_value / SUM(transaction_value) OVER () * 100,
            2
        ) AS pct_of_value,
        RANK() OVER (ORDER BY transaction_value DESC) AS channel_rank
    FROM channel_stats
)

SELECT
    channel_name,
    transaction_count,
    ROUND(transaction_value, 2) AS transaction_value,
    ROUND(avg_transaction, 2) AS avg_transaction,
    ROUND(completed_count::numeric / NULLIF(transaction_count, 0) * 100, 2) AS success_rate_pct,
    ROUND(failed_count::numeric / NULLIF(transaction_count, 0) * 100, 2) AS failure_rate_pct,
    pct_of_volume,
    pct_of_value,
    channel_rank
FROM with_shares
ORDER BY channel_rank;

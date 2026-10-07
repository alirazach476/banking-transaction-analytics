-- Top branches by transaction value with deposit/withdrawal split
-- Demonstrates: CASE, GROUP BY, RANK(), dimension joins

WITH branch_metrics AS (
    SELECT
        db.branch_id,
        db.branch_name,
        db.city,
        db.region,
        COUNT(*) AS transaction_count,
        SUM(ft.amount) AS total_value,
        SUM(CASE WHEN dtt.transaction_type = 'Deposit' THEN ft.amount ELSE 0 END) AS deposit_value,
        SUM(CASE WHEN dtt.transaction_type = 'Withdrawal' THEN ft.amount ELSE 0 END) AS withdrawal_value,
        SUM(CASE WHEN ft.transaction_status = 'Failed' THEN 1 ELSE 0 END) AS failed_count,
        AVG(ft.amount) AS avg_transaction_value
    FROM warehouse.fact_transactions ft
    INNER JOIN warehouse.dim_branch db ON ft.branch_key = db.branch_key
    INNER JOIN warehouse.dim_transaction_type dtt
        ON ft.transaction_type_key = dtt.transaction_type_key
    WHERE db.branch_id IS NOT NULL
    GROUP BY db.branch_id, db.branch_name, db.city, db.region
),

ranked AS (
    SELECT
        *,
        RANK() OVER (ORDER BY total_value DESC) AS branch_rank,
        ROUND(
            failed_count::numeric / NULLIF(transaction_count, 0) * 100,
            2
        ) AS failure_rate_pct
    FROM branch_metrics
)

SELECT *
FROM ranked
ORDER BY branch_rank
LIMIT 20;

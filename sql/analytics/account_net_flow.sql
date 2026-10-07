-- Account net flow: inflows, outflows, net position
-- Demonstrates: conditional SUM, JOINs to account dimension

WITH flows AS (
    SELECT
        da.account_id,
        da.account_type,
        da.currency,
        dc.customer_id,
        SUM(CASE
            WHEN dtt.transaction_type IN ('Deposit', 'Refund', 'Interest')
            THEN ft.amount ELSE 0
        END) AS total_inflows,
        SUM(CASE
            WHEN dtt.transaction_type IN ('Withdrawal', 'Payment', 'Fee', 'Bill Payment', 'Transfer')
            THEN ft.amount ELSE 0
        END) AS total_outflows,
        COUNT(*) AS transaction_count,
        MAX(ft.transaction_timestamp) AS last_activity_at
    FROM warehouse.fact_transactions ft
    INNER JOIN warehouse.dim_account da
        ON ft.account_key = da.account_key AND da.is_current = TRUE
    INNER JOIN warehouse.dim_customer dc
        ON da.customer_key = dc.customer_key AND dc.is_current = TRUE
    INNER JOIN warehouse.dim_transaction_type dtt
        ON ft.transaction_type_key = dtt.transaction_type_key
    WHERE ft.transaction_status = 'Completed'
    GROUP BY da.account_id, da.account_type, da.currency, dc.customer_id
)

SELECT
    account_id,
    customer_id,
    account_type,
    currency,
    transaction_count,
    ROUND(total_inflows, 2) AS total_inflows,
    ROUND(total_outflows, 2) AS total_outflows,
    ROUND(total_inflows - total_outflows, 2) AS net_flow,
    ROUND(
        (total_inflows - total_outflows) / NULLIF(total_inflows + total_outflows, 0) * 100,
        2
    ) AS net_flow_ratio_pct,
    last_activity_at
FROM flows
ORDER BY ABS(total_inflows - total_outflows) DESC
LIMIT 100;

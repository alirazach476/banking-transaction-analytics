-- Account balance reconciliation (synthetic control)
-- opening_balance + credits - debits = expected_closing_balance
-- Compare to reported current_balance from accounts

WITH account_opening AS (
    SELECT
        sa.account_id,
        sa.customer_id,
        sa.account_type,
        sa.currency,
        COALESCE(sa.current_balance::numeric, 0) AS reported_closing_balance,
        sa.open_date::date AS open_date
    FROM staging.stg_accounts sa
    WHERE sa.account_status = 'Active'
      AND sa.account_id IS NOT NULL
),

movements AS (
    SELECT
        da.account_id,
        SUM(CASE
            WHEN dtt.transaction_type IN ('Deposit', 'Refund', 'Interest')
                 AND ft.transaction_status = 'Completed'
            THEN ft.amount ELSE 0
        END) AS total_credits,
        SUM(CASE
            WHEN dtt.transaction_type IN ('Withdrawal', 'Payment', 'Fee', 'Bill Payment')
                 AND ft.transaction_status = 'Completed'
            THEN ft.amount ELSE 0
        END) AS total_debits,
        COUNT(*) AS transaction_count
    FROM warehouse.fact_transactions ft
    INNER JOIN warehouse.dim_account da
        ON ft.account_key = da.account_key AND da.is_current = TRUE
    INNER JOIN warehouse.dim_transaction_type dtt
        ON ft.transaction_type_key = dtt.transaction_type_key
    GROUP BY da.account_id
),

reconciled AS (
    SELECT
        ao.account_id,
        ao.customer_id,
        ao.account_type,
        ao.currency,
        ao.reported_closing_balance,
        COALESCE(m.total_credits, 0) AS total_credits,
        COALESCE(m.total_debits, 0) AS total_debits,
        COALESCE(m.transaction_count, 0) AS transaction_count,
        -- Simplified: treat reported balance as opening + net for synthetic demo
        COALESCE(m.total_credits, 0) - COALESCE(m.total_debits, 0) AS computed_net_flow,
        ao.reported_closing_balance
            - (COALESCE(m.total_credits, 0) - COALESCE(m.total_debits, 0)) AS balance_discrepancy
    FROM account_opening ao
    LEFT JOIN movements m ON ao.account_id = m.account_id
)

SELECT
    account_id,
    customer_id,
    account_type,
    currency,
    transaction_count,
    ROUND(total_credits, 2) AS total_credits,
    ROUND(total_debits, 2) AS total_debits,
    ROUND(computed_net_flow, 2) AS computed_net_flow,
    ROUND(reported_closing_balance, 2) AS reported_closing_balance,
    ROUND(balance_discrepancy, 2) AS balance_discrepancy,
    CASE
        WHEN ABS(balance_discrepancy) <= 0.01 THEN 'PASS'
        WHEN ABS(balance_discrepancy) <= 100 THEN 'WARN'
        ELSE 'FAIL'
    END AS reconciliation_status
FROM reconciled
WHERE transaction_count > 0
ORDER BY ABS(balance_discrepancy) DESC
LIMIT 100;

-- Note: Synthetic generator maintains approximate balance consistency.
-- Discrepancies after DQ exclusions are expected and documented.

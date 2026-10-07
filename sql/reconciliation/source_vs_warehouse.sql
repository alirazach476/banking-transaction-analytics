-- Source vs warehouse reconciliation
-- Compares raw source counts/amounts to warehouse fact aggregates
-- Synthetic NovaBank data — banking-style control report

WITH source_metrics AS (
    SELECT
        'transactions' AS source_name,
        COUNT(DISTINCT transaction_id) AS source_count,
        SUM(
            CASE
                WHEN amount ~ '^-?[0-9]+(\\.[0-9]+)?$'
                THEN amount::numeric
                ELSE 0
            END
        ) AS source_value
    FROM raw.transactions
    WHERE transaction_id IS NOT NULL
      AND transaction_id <> ''
),

warehouse_metrics AS (
    SELECT
        'transactions' AS source_name,
        COUNT(DISTINCT transaction_id) AS warehouse_count,
        SUM(amount) AS warehouse_value
    FROM warehouse.fact_transactions
),

customer_source AS (
    SELECT
        'customers' AS source_name,
        COUNT(DISTINCT customer_id) AS source_count,
        NULL::numeric AS source_value
    FROM raw.customers
    WHERE customer_id IS NOT NULL
),

customer_warehouse AS (
    SELECT
        'customers' AS source_name,
        COUNT(DISTINCT customer_id) AS warehouse_count,
        NULL::numeric AS warehouse_value
    FROM warehouse.dim_customer
    WHERE is_current = TRUE
),

combined AS (
    SELECT
        s.source_name,
        'transaction_count' AS metric_name,
        s.source_count::numeric AS source_value,
        w.warehouse_count::numeric AS warehouse_value
    FROM source_metrics s
    INNER JOIN warehouse_metrics w ON s.source_name = w.source_name

    UNION ALL

    SELECT
        s.source_name,
        'transaction_value' AS metric_name,
        s.source_value,
        w.warehouse_value
    FROM source_metrics s
    INNER JOIN warehouse_metrics w ON s.source_name = w.source_name

    UNION ALL

    SELECT
        cs.source_name,
        'customer_count' AS metric_name,
        cs.source_count::numeric,
        cw.warehouse_count::numeric
    FROM customer_source cs
    INNER JOIN customer_warehouse cw ON cs.source_name = cw.source_name
)

SELECT
    source_name,
    metric_name,
    source_value,
    warehouse_value,
    warehouse_value - source_value AS difference,
    CASE
        WHEN metric_name = 'transaction_value'
            AND ABS(warehouse_value - source_value) <= 0.01 THEN 'PASS'
        WHEN metric_name <> 'transaction_value'
            AND warehouse_value = source_value THEN 'PASS'
        WHEN warehouse_value <= source_value
            AND metric_name = 'transaction_count' THEN 'WARN'  -- orphans excluded
        ELSE 'FAIL'
    END AS status,
    CASE
        WHEN metric_name = 'transaction_count' AND warehouse_value < source_value
        THEN 'Difference may reflect DQ exclusions (orphan FKs, invalid amounts)'
        ELSE NULL
    END AS notes
FROM combined
ORDER BY source_name, metric_name;

-- Persist results via Python: python -m src.validation.reconciliation

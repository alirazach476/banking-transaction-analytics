-- EXPLAIN ANALYZE examples for NovaBank performance tuning
-- Replace placeholder timings with actual output from your database.
-- Do NOT fabricate performance numbers.

-- =============================================================================
-- Query 1: Daily aggregation by date_key
-- Expected issue at scale: Seq Scan on fact_transactions
-- Optimization: idx_fact_txn_date_key
-- =============================================================================

EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT
    d.calendar_date,
    COUNT(*) AS txn_count,
    SUM(f.amount) AS txn_value
FROM warehouse.fact_transactions f
INNER JOIN warehouse.dim_date d ON f.date_key = d.date_key
WHERE d.calendar_date BETWEEN '2024-01-01' AND '2024-12-31'
GROUP BY d.calendar_date
ORDER BY d.calendar_date;

-- Record: Execution Time: _____ ms (before index) → _____ ms (after index)

-- =============================================================================
-- Query 2: Customer transaction history (last 90 days)
-- Optimization: idx_fact_txn_customer_ts
-- =============================================================================

EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT
    f.transaction_id,
    f.transaction_timestamp,
    f.amount,
    f.transaction_status
FROM warehouse.fact_transactions f
INNER JOIN warehouse.dim_customer dc
    ON f.customer_key = dc.customer_key AND dc.is_current = TRUE
WHERE dc.customer_id = 'CUST-000001'
  AND f.transaction_timestamp >= CURRENT_DATE - INTERVAL '90 days'
ORDER BY f.transaction_timestamp DESC
LIMIT 100;

-- Record: Execution Time: _____ ms

-- =============================================================================
-- Query 3: Anomaly monitoring by severity
-- Optimization: idx_anomalies_severity, idx_anomalies_timestamp
-- =============================================================================

EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT
    severity,
    DATE_TRUNC('day', transaction_timestamp) AS anomaly_date,
    COUNT(*) AS anomaly_count,
    SUM(amount) AS anomalous_value
FROM monitoring.transaction_anomalies
WHERE transaction_timestamp >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY severity, DATE_TRUNC('day', transaction_timestamp)
ORDER BY anomaly_date, severity;

-- Record: Execution Time: _____ ms

-- =============================================================================
-- Query 4: Channel failure rate (mart vs fact)
-- Compare mart_channel_performance (pre-aggregated) vs on-the-fly
-- =============================================================================

EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT
    channel,
    transaction_count,
    failure_rate
FROM analytics.mart_channel_performance
ORDER BY failure_rate DESC;

-- Record: Execution Time: _____ ms (mart should be faster than fact scan)

-- =============================================================================
-- Query 5: Rolling 7-day average (window function)
-- Optimization: pre-compute in mart_daily_transactions.rolling_7d_avg_count
-- =============================================================================

EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
WITH daily AS (
    SELECT
        d.calendar_date,
        COUNT(*) AS transaction_count
    FROM warehouse.fact_transactions f
    INNER JOIN warehouse.dim_date d ON f.date_key = d.date_key
    GROUP BY d.calendar_date
)
SELECT
    calendar_date,
    transaction_count,
    AVG(transaction_count) OVER (
        ORDER BY calendar_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS rolling_7d_avg
FROM daily
ORDER BY calendar_date;

-- Record: Execution Time: _____ ms

-- =============================================================================
-- Documentation template (fill after running EXPLAIN ANALYZE)
-- =============================================================================
-- | Query | Problem              | Optimization              | Before | After |
-- |-------|----------------------|---------------------------|--------|-------|
-- | Q1    | Seq Scan on fact     | idx_fact_txn_date_key     | ___ ms | ___ ms|
-- | Q2    | Filter on customer   | idx_fact_txn_customer_ts  | ___ ms | ___ ms|
-- | Q3    | Seq Scan monitoring  | idx_anomalies_severity    | ___ ms | ___ ms|
-- | Q4    | N/A (mart)           | Use pre-aggregated mart   | ___ ms | ___ ms|
-- | Q5    | Window over full scan| Use mart rolling columns  | ___ ms | ___ ms|

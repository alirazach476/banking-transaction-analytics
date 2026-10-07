-- Recommended PostgreSQL indexes for NovaBank analytics workloads
-- Run after initial data load; use CONCURRENTLY in production when live traffic exists

-- Fact transactions — primary analytical table
CREATE INDEX IF NOT EXISTS idx_fact_txn_date_key
    ON warehouse.fact_transactions (date_key);

CREATE INDEX IF NOT EXISTS idx_fact_txn_customer_ts
    ON warehouse.fact_transactions (customer_key, transaction_timestamp);

CREATE INDEX IF NOT EXISTS idx_fact_txn_account_key
    ON warehouse.fact_transactions (account_key);

CREATE INDEX IF NOT EXISTS idx_fact_txn_channel_date
    ON warehouse.fact_transactions (channel_key, date_key);

CREATE INDEX IF NOT EXISTS idx_fact_txn_status
    ON warehouse.fact_transactions (transaction_status);

CREATE INDEX IF NOT EXISTS idx_fact_txn_updated_at
    ON warehouse.fact_transactions (updated_at);

CREATE INDEX IF NOT EXISTS idx_fact_txn_failed
    ON warehouse.fact_transactions (transaction_timestamp)
    WHERE transaction_status = 'Failed';

-- Dimensions
CREATE INDEX IF NOT EXISTS idx_dim_customer_id_current
    ON warehouse.dim_customer (customer_id)
    WHERE is_current = TRUE;

CREATE INDEX IF NOT EXISTS idx_dim_account_id
    ON warehouse.dim_account (account_id);

CREATE INDEX IF NOT EXISTS idx_dim_date_calendar
    ON warehouse.dim_date (calendar_date);

-- Monitoring
CREATE INDEX IF NOT EXISTS idx_anomalies_timestamp
    ON monitoring.transaction_anomalies (transaction_timestamp);

CREATE INDEX IF NOT EXISTS idx_anomalies_severity
    ON monitoring.transaction_anomalies (severity);

CREATE INDEX IF NOT EXISTS idx_anomalies_customer
    ON monitoring.transaction_anomalies (customer_id);

-- Analytics marts
CREATE INDEX IF NOT EXISTS idx_mart_daily_txn_date
    ON analytics.mart_daily_transactions (transaction_date);

CREATE INDEX IF NOT EXISTS idx_mart_customer_activity_segment
    ON analytics.mart_customer_activity (activity_segment);

-- Audit
CREATE INDEX IF NOT EXISTS idx_pipeline_runs_start
    ON audit.pipeline_runs (start_time DESC);

CREATE INDEX IF NOT EXISTS idx_dq_results_run
    ON audit.data_quality_results (run_id);

ANALYZE warehouse.fact_transactions;
ANALYZE monitoring.transaction_anomalies;

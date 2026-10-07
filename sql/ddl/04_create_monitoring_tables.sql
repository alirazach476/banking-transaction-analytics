CREATE TABLE IF NOT EXISTS monitoring.transaction_anomalies (
    anomaly_id          BIGSERIAL PRIMARY KEY,
    transaction_id      TEXT NOT NULL,
    customer_id         TEXT,
    account_id          TEXT,
    transaction_timestamp TIMESTAMPTZ,
    amount              NUMERIC(18, 2),
    rule_based_score    NUMERIC(8, 4),
    ml_anomaly_score    NUMERIC(8, 4),
    anomaly_reason      TEXT,
    severity            TEXT CHECK (severity IN ('Low', 'Medium', 'High', 'Critical')),
    z_score             NUMERIC(12, 4),
    is_injected_anomaly BOOLEAN DEFAULT FALSE,
    detected_at         TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_anomalies_txn
    ON monitoring.transaction_anomalies (transaction_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_customer
    ON monitoring.transaction_anomalies (customer_id);
CREATE INDEX IF NOT EXISTS idx_anomalies_severity
    ON monitoring.transaction_anomalies (severity);
CREATE INDEX IF NOT EXISTS idx_anomalies_detected
    ON monitoring.transaction_anomalies (detected_at);

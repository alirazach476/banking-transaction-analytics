-- Payment lifecycle (SYNTHETIC). Raw landing tables follow the existing bronze convention (TEXT),
-- plus typed result tables in the payments schema.

CREATE TABLE IF NOT EXISTS raw.payment_transactions (
    payment_id TEXT, card_id TEXT, customer_id TEXT, account_id TEXT, merchant_id TEXT,
    merchant_category TEXT, merchant_country TEXT, card_country TEXT, channel TEXT,
    amount TEXT, currency TEXT, billing_currency TEXT, is_international TEXT,
    authorization_ts TEXT, card_status TEXT, card_expiry_date TEXT,
    synthetic_fraud_pattern TEXT, is_synthetic TEXT, dq_defect TEXT,
    _ingested_at TIMESTAMPTZ DEFAULT NOW(), _source_file TEXT
);

CREATE TABLE IF NOT EXISTS raw.payment_lifecycle_events (
    event_id TEXT, payment_id TEXT, event_type TEXT, event_ts TEXT, amount TEXT,
    currency TEXT, event_status TEXT, reason_code TEXT, response_ms TEXT,
    is_synthetic TEXT, dq_defect TEXT,
    _ingested_at TIMESTAMPTZ DEFAULT NOW(), _source_file TEXT
);

CREATE TABLE IF NOT EXISTS raw.payment_settlements (
    settlement_id TEXT, payment_id TEXT, batch_id TEXT, settlement_ts TEXT,
    settlement_amount TEXT, settlement_currency TEXT, is_synthetic TEXT,
    _ingested_at TIMESTAMPTZ DEFAULT NOW(), _source_file TEXT
);

CREATE TABLE IF NOT EXISTS raw.fx_rates_synthetic (
    rate_date TEXT, base_currency TEXT, quote_currency TEXT, rate TEXT, source TEXT,
    _ingested_at TIMESTAMPTZ DEFAULT NOW(), _source_file TEXT
);

CREATE TABLE IF NOT EXISTS payments.reconciliation_runs (
    recon_run_id   BIGSERIAL PRIMARY KEY,
    run_id         TEXT,
    as_of          TIMESTAMPTZ,
    sla_days       INT,
    cleared_payments BIGINT,
    matched        BIGINT,
    pending        BIGINT,
    missing        BIGINT,
    duplicate      BIGINT,
    amount_mismatch BIGINT,
    currency_mismatch BIGINT,
    late           BIGINT,
    fx_rate_missing BIGINT,
    unmatched_settlements BIGINT,
    settlement_success_rate NUMERIC(10, 6),
    amount_at_risk NUMERIC(20, 2),
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

-- Investigation queue: one row per open exception. Business key (payment_id, settlement_id, issue_type)
-- makes reconciliation re-runs idempotent (upsert keeps analyst-set status/notes).
CREATE TABLE IF NOT EXISTS payments.investigation_queue (
    payment_id     TEXT NOT NULL,
    settlement_id  TEXT NOT NULL DEFAULT '',
    issue_type     TEXT NOT NULL,
    amount_at_risk NUMERIC(20, 2),
    currency       TEXT,
    issue_flags    TEXT,
    priority       TEXT CHECK (priority IN ('HIGH', 'MEDIUM', 'LOW')),
    status         TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'IN_REVIEW', 'RESOLVED', 'FALSE_POSITIVE')),
    notes          TEXT,
    first_detected_at TIMESTAMPTZ DEFAULT NOW(),
    last_detected_at  TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (payment_id, settlement_id, issue_type)
);

CREATE INDEX IF NOT EXISTS idx_invq_status_priority ON payments.investigation_queue (status, priority, amount_at_risk DESC);
CREATE INDEX IF NOT EXISTS idx_invq_issue ON payments.investigation_queue (issue_type);

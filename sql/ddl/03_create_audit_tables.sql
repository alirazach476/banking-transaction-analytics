CREATE TABLE IF NOT EXISTS audit.pipeline_runs (
    run_id              TEXT PRIMARY KEY,
    pipeline_name       TEXT NOT NULL,
    start_time          TIMESTAMPTZ NOT NULL,
    end_time            TIMESTAMPTZ,
    status              TEXT NOT NULL,
    rows_processed      BIGINT DEFAULT 0,
    rows_failed         BIGINT DEFAULT 0,
    mode                TEXT,
    notes               TEXT
);

CREATE TABLE IF NOT EXISTS audit.data_quality_results (
    result_id           BIGSERIAL PRIMARY KEY,
    run_id              TEXT REFERENCES audit.pipeline_runs(run_id),
    check_name          TEXT NOT NULL,
    table_name          TEXT NOT NULL,
    check_type          TEXT NOT NULL,
    expected_result     TEXT,
    actual_result       TEXT,
    status              TEXT NOT NULL,
    failed_rows         BIGINT DEFAULT 0,
    execution_time_ms   NUMERIC,
    checked_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit.source_ingestion (
    ingestion_id        BIGSERIAL PRIMARY KEY,
    run_id              TEXT REFERENCES audit.pipeline_runs(run_id),
    source_name         TEXT NOT NULL,
    source_system       TEXT,
    source_file         TEXT,
    rows_read           BIGINT,
    rows_loaded         BIGINT,
    rows_rejected       BIGINT,
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    status              TEXT
);

CREATE TABLE IF NOT EXISTS audit.pipeline_watermarks (
    pipeline_name       TEXT NOT NULL,
    source_name         TEXT NOT NULL,
    last_watermark      TIMESTAMPTZ NOT NULL,
    updated_at          TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (pipeline_name, source_name)
);

CREATE TABLE IF NOT EXISTS audit.reconciliation_results (
    reconciliation_id   BIGSERIAL PRIMARY KEY,
    run_id              TEXT REFERENCES audit.pipeline_runs(run_id),
    source_name         TEXT NOT NULL,
    metric_name         TEXT NOT NULL,
    source_value        NUMERIC,
    warehouse_value     NUMERIC,
    difference          NUMERIC,
    status              TEXT NOT NULL,
    checked_at          TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit.balance_reconciliation (
    balance_recon_id    BIGSERIAL PRIMARY KEY,
    run_id              TEXT REFERENCES audit.pipeline_runs(run_id),
    account_id          TEXT NOT NULL,
    opening_balance     NUMERIC,
    total_credits       NUMERIC,
    total_debits        NUMERIC,
    expected_closing    NUMERIC,
    reported_closing    NUMERIC,
    difference          NUMERIC,
    status              TEXT NOT NULL,
    checked_at          TIMESTAMPTZ DEFAULT NOW()
);

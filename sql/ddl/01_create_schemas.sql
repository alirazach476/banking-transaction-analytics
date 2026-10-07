-- NovaBank schema bootstrap
-- Synthetic banking data only — not real customer or financial records.

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS intermediate;
CREATE SCHEMA IF NOT EXISTS warehouse;
CREATE SCHEMA IF NOT EXISTS analytics;
CREATE SCHEMA IF NOT EXISTS audit;
CREATE SCHEMA IF NOT EXISTS monitoring;

COMMENT ON SCHEMA raw IS 'Raw source data exactly as ingested from synthetic banking systems';
COMMENT ON SCHEMA staging IS 'Cleaned and standardized staging layer (dbt)';
COMMENT ON SCHEMA warehouse IS 'Dimensional data warehouse (star schema)';
COMMENT ON SCHEMA analytics IS 'Business-facing analytics marts';
COMMENT ON SCHEMA audit IS 'Pipeline execution, DQ, reconciliation, watermarks';
COMMENT ON SCHEMA monitoring IS 'Transaction anomaly detection results (prototype)';

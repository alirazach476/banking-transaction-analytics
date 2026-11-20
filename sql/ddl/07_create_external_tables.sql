-- External financial intelligence (public sources only). raw = as scraped/snapshotted,
-- staging = typed/deduplicated views, analytics = dbt marts (Phase 5).

CREATE SCHEMA IF NOT EXISTS external_raw;
CREATE SCHEMA IF NOT EXISTS external_staging;
CREATE SCHEMA IF NOT EXISTS external_analytics;

-- One row per fetch. Never updated: this is the historical snapshot log.
CREATE TABLE IF NOT EXISTS external_raw.http_snapshots (
    snapshot_id       BIGSERIAL PRIMARY KEY,
    source_name       TEXT NOT NULL,
    source_url        TEXT NOT NULL,
    source_domain     TEXT NOT NULL,
    extracted_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    http_status       INT,
    extraction_status TEXT NOT NULL CHECK (extraction_status IN ('SUCCESS', 'UNCHANGED', 'FAILED', 'BLOCKED_ROBOTS')),
    parser_version    TEXT,
    content_hash      TEXT,
    changed           BOOLEAN,
    records_parsed    INT DEFAULT 0,
    records_new       INT DEFAULT 0,
    attempts          INT DEFAULT 1,
    error_message     TEXT
);
CREATE INDEX IF NOT EXISTS idx_snap_url_time ON external_raw.http_snapshots (source_url, extracted_at DESC);

CREATE TABLE IF NOT EXISTS external_raw.exchange_rates (
    base_currency   TEXT NOT NULL,
    target_currency TEXT NOT NULL,
    effective_date  DATE NOT NULL,
    rate            NUMERIC(20, 8) NOT NULL CHECK (rate > 0),
    source          TEXT NOT NULL,
    extracted_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    snapshot_id     BIGINT REFERENCES external_raw.http_snapshots (snapshot_id),
    PRIMARY KEY (base_currency, target_currency, effective_date, source)
);

CREATE TABLE IF NOT EXISTS external_raw.economic_indicators (
    indicator_id     TEXT NOT NULL,
    indicator_name   TEXT,
    country          TEXT NOT NULL,
    observation_date DATE NOT NULL,
    value            NUMERIC(24, 8) NOT NULL,
    unit             TEXT,
    source           TEXT NOT NULL,
    publication_date DATE,
    extracted_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    snapshot_id      BIGINT REFERENCES external_raw.http_snapshots (snapshot_id),
    PRIMARY KEY (indicator_id, country, observation_date, source)
);

CREATE TABLE IF NOT EXISTS external_raw.industry_announcements (
    url_hash      TEXT PRIMARY KEY,
    source        TEXT NOT NULL,
    category      TEXT,
    title         TEXT NOT NULL,
    url           TEXT NOT NULL,
    published_at  TIMESTAMPTZ,
    summary       TEXT,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    snapshot_id   BIGINT REFERENCES external_raw.http_snapshots (snapshot_id)
);

-- Latest successful snapshot per URL, and a convenient typed FX view.
CREATE OR REPLACE VIEW external_staging.stg_latest_snapshots AS
SELECT DISTINCT ON (source_url) *
FROM external_raw.http_snapshots
WHERE extraction_status IN ('SUCCESS', 'UNCHANGED')
ORDER BY source_url, extracted_at DESC;

CREATE OR REPLACE VIEW external_staging.stg_exchange_rates AS
SELECT base_currency, target_currency, effective_date, rate, source, extracted_at
FROM external_raw.exchange_rates;

CREATE OR REPLACE VIEW external_staging.stg_economic_indicators AS
SELECT indicator_id, indicator_name, country, observation_date, value, unit, source, publication_date
FROM external_raw.economic_indicators;

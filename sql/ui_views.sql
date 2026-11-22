-- Objects backing the analytics UI (idempotent). All data is SYNTHETIC. Values are converted to USD with raw.fx_rates_synthetic
-- (USD per one unit of the currency, by date, last available rate on or before the transaction date). Rows whose currency has no
-- rate (unknown or null currency) keep amount_usd NULL and are excluded from value metrics (still counted in volume).
CREATE SCHEMA IF NOT EXISTS ui;
CREATE SCHEMA IF NOT EXISTS monitoring;

CREATE TABLE IF NOT EXISTS monitoring.anomaly_investigations (
    anomaly_id      bigint PRIMARY KEY,
    status          text NOT NULL DEFAULT 'NEW' CHECK (status IN ('NEW','INVESTIGATING','CONFIRMED_FRAUD','FALSE_POSITIVE','CLOSED')),
    assignee        text,
    note            text,
    updated_at      timestamptz NOT NULL DEFAULT now()
);

DROP MATERIALIZED VIEW IF EXISTS ui.payments_usd CASCADE;
CREATE MATERIALIZED VIEW ui.payments_usd AS
WITH fx AS (
    SELECT base_currency AS cur, rate_date::date AS d, rate::numeric AS r FROM raw.fx_rates_synthetic WHERE quote_currency = 'USD'
), pairs AS (
    SELECT DISTINCT currency AS cur, payment_date AS d FROM intermediate.int_payment_outcomes WHERE currency IS NOT NULL
), rates AS (
    SELECT p.cur, p.d, (SELECT f.r FROM fx f WHERE f.cur = p.cur AND f.d <= p.d ORDER BY f.d DESC LIMIT 1) AS r FROM pairs p
)
SELECT o.payment_id, o.payment_date, t.authorization_ts,
       CASE upper(trim(o.channel)) WHEN 'POS CONTACTLESS' THEN 'POS Contactless' WHEN 'POS CHIP' THEN 'POS Chip' WHEN 'E-COMMERCE' THEN 'E-commerce'
            WHEN 'MOBILE WALLET' THEN 'Mobile Wallet' WHEN 'RECURRING' THEN 'Recurring' ELSE coalesce(initcap(o.channel), 'Unknown') END AS channel,
       coalesce(o.merchant_category, 'Unknown') AS merchant_category, t.merchant_id, t.customer_id, t.card_id, o.currency, o.amount,
       CASE WHEN o.currency = 'USD' THEN o.amount WHEN r.r IS NOT NULL THEN o.amount * r.r END AS amount_usd,
       o.is_international, o.authorized, o.declined, o.decline_reason, o.response_ms, o.cleared, o.settled, o.reversed, o.refunded, o.charged_back,
       (lower(t.synthetic_fraud_pattern) IN ('true','t','1')) AS synthetic_fraud_label
FROM intermediate.int_payment_outcomes o
LEFT JOIN staging.stg_payment_transactions t USING (payment_id)
LEFT JOIN rates r ON r.cur = o.currency AND r.d = o.payment_date;
CREATE UNIQUE INDEX ON ui.payments_usd (payment_id);
CREATE INDEX ON ui.payments_usd (payment_date);
CREATE INDEX ON ui.payments_usd (merchant_id);
CREATE INDEX ON ui.payments_usd (customer_id);

DROP MATERIALIZED VIEW IF EXISTS ui.merchant_stats CASCADE;
CREATE MATERIALIZED VIEW ui.merchant_stats AS
SELECT merchant_id, count(*) AS payments, coalesce(sum(amount_usd), 0) AS value_usd, sum(authorized::int)::float / nullif(sum(authorized::int + declined::int), 0) AS approval_rate,
       sum(declined::int) AS declined, sum(charged_back::int) AS chargebacks
FROM ui.payments_usd WHERE merchant_id IS NOT NULL GROUP BY 1;
CREATE UNIQUE INDEX ON ui.merchant_stats (merchant_id);

DROP MATERIALIZED VIEW IF EXISTS ui.core_txn_usd CASCADE;
CREATE MATERIALIZED VIEW ui.core_txn_usd AS
WITH fx AS (
    SELECT base_currency AS cur, rate_date::date AS d, rate::numeric AS r FROM raw.fx_rates_synthetic WHERE quote_currency = 'USD'
), pairs AS (
    SELECT DISTINCT currency AS cur, transaction_timestamp::date AS d FROM warehouse.fact_transactions WHERE currency IS NOT NULL
), rates AS (
    SELECT p.cur, p.d, (SELECT f.r FROM fx f WHERE f.cur = p.cur AND f.d <= p.d ORDER BY f.d DESC LIMIT 1) AS r FROM pairs p
)
SELECT f.transaction_id, f.transaction_timestamp AS ts, f.transaction_timestamp::date AS d, f.transaction_type, coalesce(f.channel, 'Unknown') AS channel,
       f.transaction_status AS status, f.amount, f.currency,
       CASE WHEN f.currency = 'USD' THEN f.amount WHEN r.r IS NOT NULL THEN f.amount * r.r END AS amount_usd,
       c.customer_id, b.branch_id, m.merchant_id, f.is_injected_anomaly, f.anomaly_type
FROM warehouse.fact_transactions f
LEFT JOIN warehouse.dim_customer c ON c.customer_key = f.customer_key
LEFT JOIN warehouse.dim_branch b ON b.branch_key = f.branch_key
LEFT JOIN warehouse.dim_merchant m ON m.merchant_key = f.merchant_key
LEFT JOIN rates r ON r.cur = f.currency AND r.d = f.transaction_timestamp::date;
CREATE UNIQUE INDEX ON ui.core_txn_usd (transaction_id);
CREATE INDEX ON ui.core_txn_usd (d);
CREATE INDEX ON ui.core_txn_usd (customer_id);
CREATE INDEX ON ui.core_txn_usd (branch_id);
CREATE INDEX ON ui.core_txn_usd (merchant_id);

CREATE TABLE IF NOT EXISTS ui.city_centroids (
    city text NOT NULL, country text NOT NULL, lat double precision NOT NULL, lon double precision NOT NULL, population bigint, source text NOT NULL,
    PRIMARY KEY (city, country)
);

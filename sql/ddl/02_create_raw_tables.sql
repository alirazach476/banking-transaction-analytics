-- Raw layer tables — schemas mirror source-system CSVs (intentionally imperfect)

CREATE TABLE IF NOT EXISTS raw.customers (
    customer_id         TEXT,
    first_name          TEXT,
    last_name           TEXT,
    date_of_birth       TEXT,
    gender              TEXT,
    customer_type       TEXT,
    registration_date   TEXT,
    customer_status     TEXT,
    city                TEXT,
    region              TEXT,
    country             TEXT,
    _ingested_at        TIMESTAMPTZ DEFAULT NOW(),
    _source_file        TEXT,
    _source_system      TEXT DEFAULT 'customer_system'
);

CREATE TABLE IF NOT EXISTS raw.accounts (
    account_id          TEXT,
    customer_id         TEXT,
    account_type        TEXT,
    branch_id           TEXT,
    open_date           TEXT,
    close_date          TEXT,
    currency            TEXT,
    current_balance     TEXT,
    account_status      TEXT,
    _ingested_at        TIMESTAMPTZ DEFAULT NOW(),
    _source_file        TEXT,
    _source_system      TEXT DEFAULT 'core_banking'
);

CREATE TABLE IF NOT EXISTS raw.branches (
    branch_id           TEXT,
    branch_name         TEXT,
    city                TEXT,
    region              TEXT,
    country             TEXT,
    branch_type         TEXT,
    opening_date        TEXT,
    branch_status       TEXT,
    _ingested_at        TIMESTAMPTZ DEFAULT NOW(),
    _source_file        TEXT,
    _source_system      TEXT DEFAULT 'branch_system'
);

CREATE TABLE IF NOT EXISTS raw.merchants (
    merchant_id         TEXT,
    merchant_name       TEXT,
    merchant_category   TEXT,
    city                TEXT,
    region              TEXT,
    merchant_status     TEXT,
    _ingested_at        TIMESTAMPTZ DEFAULT NOW(),
    _source_file        TEXT,
    _source_system      TEXT DEFAULT 'card_system'
);

CREATE TABLE IF NOT EXISTS raw.cards (
    card_id             TEXT,
    customer_id         TEXT,
    account_id          TEXT,
    card_type           TEXT,
    issue_date          TEXT,
    expiry_date         TEXT,
    card_status         TEXT,
    _ingested_at        TIMESTAMPTZ DEFAULT NOW(),
    _source_file        TEXT,
    _source_system      TEXT DEFAULT 'card_system'
);

CREATE TABLE IF NOT EXISTS raw.transactions (
    transaction_id      TEXT,
    account_id          TEXT,
    customer_id         TEXT,
    transaction_timestamp TEXT,
    transaction_type    TEXT,
    amount              TEXT,
    currency            TEXT,
    channel             TEXT,
    merchant_id         TEXT,
    branch_id           TEXT,
    transaction_status  TEXT,
    reference_type      TEXT,
    is_injected_anomaly TEXT,
    anomaly_type        TEXT,
    updated_at          TEXT,
    _ingested_at        TIMESTAMPTZ DEFAULT NOW(),
    _source_file        TEXT,
    _source_system      TEXT DEFAULT 'core_banking'
);

CREATE TABLE IF NOT EXISTS raw.transfers (
    transfer_id         TEXT,
    source_account_id   TEXT,
    destination_account_id TEXT,
    customer_id         TEXT,
    transfer_timestamp  TEXT,
    amount              TEXT,
    currency            TEXT,
    transfer_type       TEXT,
    status              TEXT,
    destination_country TEXT,
    updated_at          TEXT,
    _ingested_at        TIMESTAMPTZ DEFAULT NOW(),
    _source_file        TEXT,
    _source_system      TEXT DEFAULT 'core_banking'
);

CREATE TABLE IF NOT EXISTS raw.atm_transactions (
    atm_txn_id          TEXT,
    card_id             TEXT,
    atm_id              TEXT,
    branch_id           TEXT,
    customer_id         TEXT,
    account_id          TEXT,
    "timestamp"         TEXT,
    amount              TEXT,
    transaction_type    TEXT,
    status              TEXT,
    updated_at          TEXT,
    _ingested_at        TIMESTAMPTZ DEFAULT NOW(),
    _source_file        TEXT,
    _source_system      TEXT DEFAULT 'atm_system'
);

CREATE TABLE IF NOT EXISTS raw.card_transactions (
    card_txn_id         TEXT,
    card_id             TEXT,
    merchant_id         TEXT,
    customer_id         TEXT,
    account_id          TEXT,
    "timestamp"         TEXT,
    amount              TEXT,
    status              TEXT,
    currency            TEXT,
    updated_at          TEXT,
    _ingested_at        TIMESTAMPTZ DEFAULT NOW(),
    _source_file        TEXT,
    _source_system      TEXT DEFAULT 'card_system'
);

-- Idempotency helpers: unique indexes on business keys (nulls allowed for dirty data)
CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_customers_id
    ON raw.customers (customer_id) WHERE customer_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_accounts_id
    ON raw.accounts (account_id) WHERE account_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_branches_id
    ON raw.branches (branch_id) WHERE branch_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_merchants_id
    ON raw.merchants (merchant_id) WHERE merchant_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_cards_id
    ON raw.cards (card_id) WHERE card_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_transactions_id
    ON raw.transactions (transaction_id) WHERE transaction_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_transfers_id
    ON raw.transfers (transfer_id) WHERE transfer_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_atm_txn_id
    ON raw.atm_transactions (atm_txn_id) WHERE atm_txn_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS uq_raw_card_txn_id
    ON raw.card_transactions (card_txn_id) WHERE card_txn_id IS NOT NULL;

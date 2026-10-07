# NovaBank Data Dictionary

> **Disclaimer:** This project uses synthetic banking data generated solely for demonstrating data engineering, analytics, and transaction-monitoring capabilities. It does not represent real customer or banking data.

Synthetic ID examples use fictional formats. No real PANs or account numbers appear anywhere.

---

## Schema: `raw`

Raw tables mirror source CSVs with TEXT columns and ingestion metadata.

### `raw.customers`

| Column | Type | Nullable | Description | Example |
|--------|------|----------|-------------|---------|
| customer_id | TEXT | Yes* | Natural customer identifier | `CUST-000042` |
| first_name | TEXT | Yes | Synthetic given name | `Alex` |
| last_name | TEXT | Yes | Synthetic surname | `Rivera` |
| date_of_birth | TEXT | Yes | Birth date (ISO string) | `1985-03-14` |
| gender | TEXT | Yes | M/F/Other | `F` |
| customer_type | TEXT | Yes | Retail, Premium, Business, Student | `Retail` |
| registration_date | TEXT | Yes | Account opening with bank | `2021-06-01` |
| customer_status | TEXT | Yes | Active, Inactive, Suspended, Closed | `Active` |
| city | TEXT | Yes | City | `Springfield` |
| region | TEXT | Yes | State/province | `Midwest` |
| country | TEXT | Yes | Country | `US` |
| _ingested_at | TIMESTAMPTZ | No | Load timestamp | `2026-01-15T08:00:00Z` |
| _source_file | TEXT | Yes | Source CSV path | `customer_system/customers.csv` |
| _source_system | TEXT | Yes | Source system code | `customer_system` |

**Grain:** One row per customer record in source extract.  
**Primary key (business):** `customer_id`

---

### `raw.accounts`

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| account_id | TEXT | Account identifier | `ACCT-000123` |
| customer_id | TEXT | FK to customer | `CUST-000042` |
| account_type | TEXT | Checking, Savings, Business, Student, Premium Savings | `Checking` |
| branch_id | TEXT | Home branch | `BR-0012` |
| open_date | TEXT | Account open date | `2021-06-01` |
| close_date | TEXT | Close date if closed | `` |
| currency | TEXT | ISO currency | `USD` |
| current_balance | TEXT | Balance as string from source | `4523.18` |
| account_status | TEXT | Active, Closed, Frozen | `Active` |

---

### `raw.transactions`

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| transaction_id | TEXT | Unique event ID | `TXN-000987654` |
| account_id | TEXT | FK account | `ACCT-000123` |
| customer_id | TEXT | FK customer | `CUST-000042` |
| transaction_timestamp | TEXT | Event time | `2024-11-03T14:22:00` |
| transaction_type | TEXT | Deposit, Withdrawal, etc. | `Payment` |
| amount | TEXT | Monetary amount | `87.50` |
| currency | TEXT | Currency code | `USD` |
| channel | TEXT | ATM, Branch, Mobile App, etc. | `Mobile App` |
| merchant_id | TEXT | Optional merchant | `MER-00456` |
| branch_id | TEXT | Optional branch | `BR-0012` |
| transaction_status | TEXT | Completed, Pending, Failed, Reversed | `Completed` |
| reference_type | TEXT | Reference classification | `POS` |
| is_injected_anomaly | TEXT | Generator flag (true/false) | `false` |
| anomaly_type | TEXT | Injected anomaly category | `high_amount` |
| updated_at | TEXT | Change watermark for incremental | `2024-11-03T14:22:00` |

**Grain:** One row per financial transaction event in core banking source.

---

### Other raw tables

| Table | Primary key | Purpose |
|-------|-------------|---------|
| `raw.branches` | branch_id | Branch locations |
| `raw.merchants` | merchant_id | Merchant directory |
| `raw.cards` | card_id | Tokenized cards (CARD-000001) |
| `raw.transfers` | transfer_id | Account transfers |
| `raw.atm_transactions` | atm_txn_id | ATM events |
| `raw.card_transactions` | card_txn_id | Card payment events |

---

## Schema: `warehouse`

### `warehouse.dim_customer` (SCD2)

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| customer_key | BIGINT | Surrogate PK | `10042` |
| customer_id | TEXT | Natural key | `CUST-000042` |
| customer_type | TEXT | Segment type | `Premium` |
| customer_status | TEXT | Current version status | `Active` |
| city, region, country | TEXT | Geography | `Springfield, Midwest, US` |
| registration_date | DATE | First registration | `2021-06-01` |
| effective_date | DATE | SCD2 start | `2024-01-01` |
| expiration_date | DATE | SCD2 end | `9999-12-31` |
| is_current | BOOLEAN | Current version flag | `true` |

---

### `warehouse.dim_account` (SCD2)

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| account_key | BIGINT | Surrogate PK | `50123` |
| account_id | TEXT | Natural key | `ACCT-000123` |
| customer_key | BIGINT | FK dim_customer | `10042` |
| branch_key | BIGINT | FK dim_branch | `12` |
| account_type | TEXT | Product type | `Checking` |
| currency | TEXT | Account currency | `USD` |
| account_status | TEXT | Status | `Active` |
| open_date | DATE | Open date | `2021-06-01` |
| close_date | DATE | Close date | NULL |
| effective_date, expiration_date, is_current | | SCD2 fields | |

---

### `warehouse.fact_transactions`

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| transaction_id | TEXT | Degenerate dimension / NK | `TXN-000987654` |
| date_key | INT | FK dim_date (YYYYMMDD) | `20241103` |
| customer_key | BIGINT | FK dim_customer | `10042` |
| account_key | BIGINT | FK dim_account | `50123` |
| branch_key | BIGINT | FK (nullable) | `12` |
| merchant_key | BIGINT | FK (nullable) | `456` |
| channel_key | INT | FK dim_channel | `3` |
| transaction_type_key | INT | FK dim_transaction_type | `4` |
| transaction_timestamp | TIMESTAMPTZ | Event time | `2024-11-03 14:22:00+00` |
| amount | NUMERIC(18,2) | Transaction amount | `87.50` |
| currency | TEXT | Currency | `USD` |
| transaction_status | TEXT | Normalized status | `Completed` |
| is_reversed | BOOLEAN | Reversal flag | `false` |
| is_anomaly | BOOLEAN | Injected or detected flag | `false` |
| updated_at | TIMESTAMPTZ | Incremental watermark | |

**Grain:** One row = one financial transaction event.

---

### `warehouse.dim_date`

| Column | Type | Example |
|--------|------|---------|
| date_key | INT | `20241103` |
| calendar_date | DATE | `2024-11-03` |
| day | INT | `3` |
| day_name | TEXT | `Sunday` |
| week | INT | `44` |
| month | INT | `11` |
| month_name | TEXT | `November` |
| quarter | INT | `4` |
| year | INT | `2024` |
| is_weekend | BOOLEAN | `true` |
| month_start_date | DATE | `2024-11-01` |
| month_end_date | DATE | `2024-11-30` |

---

## Schema: `analytics`

### `analytics.mart_customer_activity`

| Column | Type | Description |
|--------|------|-------------|
| customer_id | TEXT | Natural key |
| transaction_count | INT | Lifetime count in mart refresh window |
| total_amount | NUMERIC | Sum of amounts |
| days_since_last_transaction | INT | Recency |
| activity_segment | TEXT | Inactive / Low / Medium / High / Premium |

### `analytics.mart_daily_transactions`

Daily aggregates: `transaction_date`, `transaction_count`, `transaction_value`, `success_rate`, `failure_rate`, rolling averages, MoM fields.

---

## Schema: `audit`

### `audit.pipeline_runs`

| Column | Type | Description |
|--------|------|-------------|
| run_id | UUID | Pipeline execution ID |
| pipeline_name | TEXT | e.g. `novabank_pipeline` |
| start_time, end_time | TIMESTAMPTZ | Duration |
| status | TEXT | RUNNING, SUCCESS, FAILED |
| mode | TEXT | full, incremental |
| rows_processed | INT | Total rows |
| notes | TEXT | Error messages |

### `audit.data_quality_results`

| Column | Type | Description |
|--------|------|-------------|
| check_name | TEXT | e.g. `null_customer_id` |
| table_name | TEXT | Target table |
| check_type | TEXT | null, unique, referential, financial |
| expected_result | TEXT | Expected outcome |
| actual_result | TEXT | Observed outcome |
| status | TEXT | PASS, FAIL, WARN |
| failed_rows | INT | Count of violations |

### `audit.pipeline_watermarks`

| Column | Type | Description |
|--------|------|-------------|
| pipeline_name | TEXT | Ingestion pipeline |
| source_name | TEXT | e.g. `transactions` |
| last_watermark | TIMESTAMPTZ | Last processed timestamp |
| updated_at | TIMESTAMPTZ | Record update time |

### `audit.reconciliation_results`

| Column | Type | Description |
|--------|------|-------------|
| reconciliation_id | UUID | Run identifier |
| run_id | UUID | Pipeline run FK |
| source_name | TEXT | Entity reconciled |
| metric_name | TEXT | count, sum_amount |
| source_value | NUMERIC | Source metric |
| warehouse_value | NUMERIC | Warehouse metric |
| difference | NUMERIC | Delta |
| status | TEXT | PASS, FAIL |

---

## Schema: `monitoring`

### `monitoring.transaction_anomalies`

| Column | Type | Description | Example |
|--------|------|-------------|---------|
| anomaly_id | UUID | PK | `a1b2c3d4-...` |
| transaction_id | TEXT | FK transaction | `TXN-000987654` |
| customer_id | TEXT | Customer | `CUST-000042` |
| transaction_timestamp | TIMESTAMPTZ | Event time | |
| amount | NUMERIC | Amount | `50000.00` |
| rule_based_score | NUMERIC | Rule engine score | `0.85` |
| ml_anomaly_score | NUMERIC | Isolation Forest score | `-0.42` |
| anomaly_reason | TEXT | Pipe-separated reasons | `Unusually High Amount\|ML Detected Anomaly` |
| severity | TEXT | Low, Medium, High, Critical | `High` |
| detected_at | TIMESTAMPTZ | Detection run time | |

---

## Reference: Status Values

**Transaction status (normalized):** Completed, Pending, Failed, Reversed  
**Customer status:** Active, Inactive, Suspended, Closed  
**Channels:** ATM, Branch, Mobile App, Internet Banking, POS, Online  
**Card ID format:** `CARD-000001` (tokenized, not a PAN)

See [data_model.md](data_model.md) for relationships and [metrics.md](metrics.md) for derived fields.

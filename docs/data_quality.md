# NovaBank Data Quality

> **Disclaimer:** This project uses synthetic banking data generated solely for demonstrating data engineering, analytics, and transaction-monitoring capabilities. It does not represent real customer or banking data.

## Strategy

Data quality is **intentionally imperfect at source** and **standardized in the pipeline**. A small configurable percentage of dirty records demonstrates real-world engineering practices without making the dataset unusable.

Configuration (`config/settings.py` / `.env`):

| Parameter | Default | Effect |
|-----------|---------|--------|
| `DQ_DUPLICATE_RATE` | 0.01 | Duplicate business keys |
| `DQ_MISSING_RATE` | 0.005 | Null required fields |
| `DQ_INVALID_STATUS_RATE` | 0.01 | Invalid status strings |

---

## Intentional Dirty Data

The synthetic generator injects:

### Duplicate records

- Same `transaction_id` or `customer_id` appearing twice
- Tests deduplication in staging and unique constraints

### Missing values

- Null `customer_id`, `account_id`, or `amount` on sparse rows
- Caught by null checks; excluded or quarantined in staging

### Invalid statuses

- Mixed capitalization: `completed`, `Completed`, `COMPLETED`
- Unknown values: `COMPLETE`, `Success`
- Standardized via `standardize_status` macro and Python status maps

### Inconsistent formatting

- Timestamps as `2024-01-01`, `01/01/2024`, or ISO with timezone
- Currency codes with trailing spaces
- Branch names with inconsistent casing

### Invalid foreign keys

- `transaction.account_id` referencing non-existent account (~0.3% of rows)
- Referential integrity checks flag these; facts exclude orphan transactions

### Duplicate transaction events

- Same amount/timestamp/account (simulates replay)
- Deduplicated in `stg_transactions` using `ROW_NUMBER()` partition by business key

---

## Data Quality Rules

Implemented in `src/validation/checks.py` and dbt tests.

### Null checks

| Check | Rule |
|-------|------|
| `null_customer_id` | customer_id NOT NULL in staging after clean |
| `null_account_id` | account_id NOT NULL for transactions |
| `null_transaction_id` | transaction_id NOT NULL |
| `null_amount` | amount NOT NULL for monetary transactions |

### Uniqueness

| Entity | Key |
|--------|-----|
| customers | customer_id |
| accounts | account_id |
| transactions | transaction_id |
| branches | branch_id |
| merchants | merchant_id |

dbt: `unique` and `not_null` tests on staging/warehouse keys.

### Referential integrity

- Every `transaction.account_id` must exist in `stg_accounts`
- Every `transaction.customer_id` must exist in `stg_customers`
- Card transactions must reference valid `card_id` and `merchant_id`

Violations logged to `audit.data_quality_results` with `failed_rows` count.

### Financial validation

| Rule | Description |
|------|-------------|
| Positive amounts | `amount > 0` for standard transaction types |
| Valid currency | ISO 4217 codes (USD, EUR, GBP, etc.) |
| Valid timestamp | Parseable datetime, not future-dated beyond tolerance |
| Balance sanity | Account balance within configured min/max after generation |

Fee and reversal types may use signed amounts in source; staging normalizes to absolute values with `is_reversed` flag.

---

## Validation Execution

```powershell
python -m src.validation.run_validation
# or: make validate
```

Results persisted:

```sql
SELECT check_name, table_name, status, failed_rows
FROM audit.data_quality_results
ORDER BY execution_time DESC
LIMIT 20;
```

---

## dbt Tests

`dbt build` runs schema tests:

- `unique`, `not_null` on mart keys
- `accepted_values` on `activity_segment`, `transaction_status`
- `relationships` between facts and dimensions (where applicable)

---

## Handling Failures

| Severity | Behavior |
|----------|----------|
| PASS | No action |
| WARN | Logged; pipeline continues (e.g. raw duplicates below threshold) |
| FAIL | Logged; may block downstream in strict mode |

Portfolio default: WARN on raw-layer issues cleaned in staging; FAIL on warehouse integrity breaks.

---

## Data Quality Dashboard (Power BI Page 7)

Displays:

- Last pipeline run status
- Failed check count
- Reconciliation status
- Source vs warehouse row counts
- Data freshness (hours since last ingest)

See [dashboards/powerbi/dashboard_spec.md](../dashboards/powerbi/dashboard_spec.md).

---

## Engineering Maturity Signals

1. **Audit trail** — every check tied to `run_id`
2. **Idempotent cleaning** — same dirty source produces same clean output
3. **Documented injection rates** — reproducible demo of DQ tooling
4. **Separation of concerns** — raw preserves truth; staging cleans

Do not use dirty raw tables directly for executive reporting — always consume `analytics` marts or validated staging.

# NovaBank Reconciliation

> **Disclaimer:** This project uses synthetic banking data generated solely for demonstrating data engineering, analytics, and transaction-monitoring capabilities. It does not represent real customer or banking data.

Reconciliation verifies that data **survives the pipeline intact** — counts and monetary totals in the warehouse match authoritative source extracts.

---

## Source vs Warehouse Reconciliation

### Purpose

Compare aggregates between:

- **Source:** CSV files in `data/source/` (or deduplicated raw counts)
- **Warehouse:** `warehouse.fact_transactions` and related facts

### Metrics compared

| Metric | Source | Warehouse |
|--------|--------|-----------|
| Transaction count | COUNT distinct transaction_id in CSV | COUNT in fact_transactions |
| Transaction value | SUM(amount) in CSV | SUM(amount) in fact |
| Customer count | Distinct customer_id | Distinct customer_key (current dim) |

### Pass criteria

```text
difference = 0
```

Or within documented tolerance for known exclusions:

- Rows failing referential integrity (orphan FKs) excluded from facts
- Duplicate raw rows deduplicated to one fact row
- Invalid amounts quarantined

Tolerance env: `WATERMARK_TOLERANCE_SECONDS=0` (strict for counts); monetary tolerance ±0.01 for rounding.

### Results table

`audit.reconciliation_results`:

```sql
SELECT source_name, metric_name, source_value, warehouse_value,
       difference, status
FROM audit.reconciliation_results
WHERE run_id = :latest_run_id;
```

**Status values:** `PASS`, `FAIL`, `WARN`

### Implementation

- Python: `src/validation/reconciliation.py`
- SQL: `sql/reconciliation/source_vs_warehouse.sql`

Run manually:

```powershell
python -m src.validation.reconciliation
# or: make reconcile
```

---

## Balance Reconciliation

Simulated banking control for selected accounts.

### Formula

```text
expected_closing_balance =
    opening_balance
  + credits (deposits, refunds, interest)
  - debits (withdrawals, payments, fees, transfers out)
```

Compare `expected_closing_balance` to `reported_closing_balance` from `stg_accounts.current_balance` (or daily snapshot).

### Scope

- Sample of active accounts (e.g. 100 accounts per run)
- Period: calendar month or since account open
- Synthetic data — demonstrates control framework, not regulatory reporting

### Discrepancy handling

| Discrepancy | Action |
|-------------|--------|
| |delta| <= 0.01 | PASS (rounding) |
| |delta| > 0.01 | FAIL — logged with account_id |
| Missing transactions | FAIL — investigate ingest |

SQL: `sql/reconciliation/balance_reconciliation.sql`

### Limitations

- Generator maintains approximate balance consistency; small drift possible after DQ removals
- Not a substitute for core banking GL reconciliation
- Clearly labeled synthetic control in portfolio documentation

---

## Reconciliation in the Pipeline

Step 7 of `run_pipeline.py` executes after dbt and before insights.

Airflow task: `reconciliation` runs after `dbt_analytics`.

---

## Troubleshooting Failed Reconciliation

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| Count source > warehouse | Orphan FK exclusions | Review DQ referential report |
| Count warehouse > source | Duplicate fact rows | Check unique_key incremental |
| Sum mismatch | Currency parsing / TEXT cast | Re-run staging casts |
| Balance mismatch | Missing transfer legs | Verify fact_transfers linkage |

---

## Audit Trail

Each reconciliation run links to `run_id` from `audit.pipeline_runs` for traceability alongside DQ results and ingestion logs.

Power BI Page 7 surfaces reconciliation status for operational visibility.

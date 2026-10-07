# NovaBank Pipeline Documentation

> **Disclaimer:** This project uses synthetic banking data generated solely for demonstrating data engineering, analytics, and transaction-monitoring capabilities. It does not represent real customer or banking data.

## Pipeline Overview

The NovaBank pipeline is an **ELT** pattern: extract synthetic CSVs, load to `raw`, validate, transform with dbt, detect anomalies, reconcile, and emit insights.

Entry points:

- `python -m src.pipeline.run_pipeline` — full local run
- `make pipeline` — Makefile wrapper
- Airflow DAG `banking_daily_pipeline` — scheduled orchestration

---

## Pipeline Stages

```text
1. generate     Synthetic CSVs → data/source/**
2. ddl          Apply sql/ddl if needed
3. ingest       CSV → raw.* (idempotent)
4. validate     DQ checks → audit.data_quality_results
5. dbt build    staging → warehouse → analytics
6. anomaly      Detection → monitoring.transaction_anomalies
7. reconcile    Source vs warehouse → audit.reconciliation_results
8. insights     analysis/business_insights.md
```

Each run creates a row in `audit.pipeline_runs` with UUID `run_id`.

---

## Ingestion

**Module:** `src/ingestion/load_raw.py`

### Source mapping

| Logical name | Source path | Raw table | Business key |
|--------------|-------------|-----------|--------------|
| customers | customer_system/customers.csv | raw.customers | customer_id |
| accounts | core_banking/accounts.csv | raw.accounts | account_id |
| branches | branch_system/branches.csv | raw.branches | branch_id |
| merchants | card_system/merchants.csv | raw.merchants | merchant_id |
| cards | card_system/cards.csv | raw.cards | card_id |
| transactions | core_banking/transactions.csv | raw.transactions | transaction_id |
| transfers | core_banking/transfers.csv | raw.transfers | transfer_id |
| atm_transactions | atm_system/atm_transactions.csv | raw.atm_transactions | atm_txn_id |
| card_transactions | card_system/card_transactions.csv | raw.card_transactions | card_txn_id |

### Ingestion behavior

1. Read CSV with pandas
2. Append metadata: `_ingested_at`, `_source_file`, `_source_system`
3. Load via SQLAlchemy with conflict handling on business keys
4. Log row counts to `audit.source_ingestion`

Source systems intentionally differ in column names; staging models normalize them.

---

## Incremental Loading

**Mode flag:** `--mode incremental` or `PIPELINE_MODE=incremental`

### Watermark strategy

High-volume entities (`transactions`, `transfers`, `atm_transactions`, `card_transactions`) include `updated_at` in source CSVs.

Watermarks stored in `audit.pipeline_watermarks`:

```sql
SELECT pipeline_name, source_name, last_watermark
FROM audit.pipeline_watermarks
WHERE source_name = 'transactions';
```

**Incremental ingest logic:**

1. Read `last_watermark` for source (default `1900-01-01` if missing)
2. Filter CSV rows where `updated_at > last_watermark`
3. Upsert/delete+insert into raw
4. On success, set `last_watermark = MAX(updated_at)` from processed batch

**dbt incremental facts:** `fact_transactions` uses `incremental_strategy='delete+insert'` with `unique_key='transaction_id'` and filters staging on `updated_at > max(updated_at) in fact`.

### Initial load

`--mode full` (default) processes all historical rows regardless of watermark.

---

## Idempotency

Re-running the pipeline on the same data must **not duplicate** business records.

| Layer | Mechanism |
|-------|-----------|
| Raw | Partial unique indexes on business keys; upsert / delete-before-insert |
| Staging | dbt views — rebuilt each run |
| Warehouse facts | `unique_key` + incremental delete+insert |
| Dimensions SCD2 | Merge on change detection |
| Anomalies | Delete anomalies for run_id range or upsert on transaction_id |
| Audit | `run_id` UUID per execution; watermarks updated atomically |

**Ingestion idempotency:** For full mode, tables may truncate-and-reload or use `ON CONFLICT DO NOTHING` depending on entity. Transaction tables use business-key deduplication.

**Safe rerun scenario:** Airflow task retry after network blip re-processes the same batch without duplicate facts.

Documented tolerance: `WATERMARK_TOLERANCE_SECONDS=0` in `.env` (strict equality for reconciliation).

---

## dbt Execution

```bash
cd dbt && dbt build --profiles-dir .
```

Layers run in dependency order:

1. Staging views (`stg_*`)
2. Intermediate tables (`int_*`)
3. Warehouse dimensions and facts
4. Analytics marts
5. Tests (unique, not_null, relationships, accepted_values)

Profiles read `POSTGRES_*` from environment via `dbt/profiles.yml`.

---

## Anomaly Detection Stage

**Module:** `src/anomaly_detection/run_detection.py`

Loads from `warehouse.fact_transactions` (fallback: `raw.transactions`), runs:

1. Rule-based (`rule_based.py`)
2. Statistical z-score (`statistical.py`)
3. Isolation Forest (`ml_isolation_forest.py`)

Persists merged results to `monitoring.transaction_anomalies`.

---

## Reconciliation Stage

**Module:** `src/validation/reconciliation.py`

Compares source CSV aggregates vs warehouse fact aggregates. See [reconciliation.md](reconciliation.md).

---

## Configuration

All volumes and thresholds from `.env` via `config/settings.py`:

- `NUM_*` — entity counts
- `PIPELINE_MODE` — full | incremental
- `DQ_*` — dirty data injection rates
- `ANOMALY_*` — detection thresholds

---

## Airflow DAG

See `airflow/dags/banking_daily_pipeline.py`. Task graph mirrors stages above with parallel ingest tasks and sequential dbt layers.

**Docker path:** `/opt/airflow/project`  
**Local path:** project root when running tasks via BashOperator from mounted volume

---

## Failure Handling

- Pipeline run marked `FAILED` in `audit.pipeline_runs` with exception in `notes`
- DQ failures logged but may not halt pipeline (configurable WARN vs FAIL)
- dbt failure: logged as `SKIPPED_OR_FAILED`; pipeline continues for demo resilience
- Airflow: `retries=2`, `retry_delay=5 minutes` on ingest and transform tasks

---

## Embedded PostgreSQL

When Docker is unavailable:

```powershell
python scripts/start_embedded_postgres.py
```

Updates `.env` with dynamic port. Re-run bootstrap and pipeline against updated connection string.

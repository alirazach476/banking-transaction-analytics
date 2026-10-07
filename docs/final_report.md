# NovaBank Banking Transaction Analytics — Final Report

> **Disclaimer:** This project uses synthetic banking data generated solely for demonstrating data engineering, analytics, and transaction-monitoring capabilities. It does not represent real customer or banking data.

**Report date:** October 2026  
**Dataset profile:** Demo volumes (configurable scale-up to full portfolio targets)

---

## 1. Project Overview

NovaBank is a fictional retail bank requiring centralized transaction analytics, operational monitoring, and a prototype anomaly detection capability. This portfolio delivers a runnable **Banking Transaction Analytics Pipeline** using Python, PostgreSQL, dbt, Airflow, scikit-learn, and documented Power BI dashboards.

---

## 2. Business Problem

Fragmented source systems (core banking, cards, ATM, customers, branches) produce inconsistent CSV extracts. Management needs unified KPIs for transactions, customers, channels, branches, failures, and suspicious patterns — without building a production fraud engine.

---

## 3. Architecture

Multi-layer ELT platform:

```text
Source CSVs → Raw → DQ → dbt (staging/warehouse/analytics) → Anomaly → BI
```

Orchestrated via Python CLI, Makefile, and Airflow DAG `banking_daily_pipeline`. See [architecture.md](architecture.md).

---

## 4. Data Sources

Five simulated systems under `data/source/`:

- core_banking (accounts, transactions, transfers)
- card_system (cards, merchants, card_transactions)
- atm_system (atm_transactions)
- customer_system (customers)
- branch_system (branches)

Schemas differ by design; staging normalizes.

---

## 5. Dataset Statistics (Verified Demo Run)

Configurable via `.env`. **Actual counts from the verified end-to-end run:**

| Entity | Loaded / warehouse | Full portfolio target |
|--------|--------------------|----------------------|
| Customers | 5,000 | 100,000 |
| Accounts | 7,500 | 150,000 |
| Transactions (`fact_transactions`) | 101,600 | 2,000,000+ |
| Branches | 50 | 500 |
| Merchants | 1,000 | 20,000 |
| Cards | 10,000 | 200,000 |
| Transfers | 15,000 | 300,000+ |
| ATM transactions | 20,000 | 400,000+ |
| Card transactions | 40,000 | 800,000+ |
| Daily mart rows | 1,095 | — |
| Anomalies requiring review | 8,645 | — |
| Total transaction value | $81,172,698.21 | — |

Date range: 2023-01-01 to 2025-12-31 (configurable).  
Anomaly injection: ~2% at generation; detection is a multi-method prototype.

Scale-up: `make generate-data-full` or adjust `NUM_*` env vars.

**Reconciliation (distinct source keys vs warehouse):** PASS on customers, accounts, transaction counts and amounts.

---

## 6. Data Quality Strategy

Intentional dirty data at configurable rates (duplicates 1%, missing 0.5%, invalid status 1%). Validation in Python + dbt tests. Results in `audit.data_quality_results`. Raw preserved; staging cleans.

---

## 7. Warehouse Design

Kimball star schema in `warehouse`:

- Dimensions: customer (SCD2), account, branch, merchant, card, channel, transaction_type, date
- Facts: transactions, card_transactions, atm_transactions, transfers

**Grain:** One row in `fact_transactions` = one financial transaction event.

---

## 8. SCD Type 2

`dim_customer` implements SCD Type 2 with `effective_date`, `expiration_date`, `is_current` for meaningful attribute changes (e.g., status/type). `dim_account` is a current-state dimension with surrogate keys; extend to SCD2 when account attribute history is required.

---

## 9. Incremental Loading

`updated_at` watermarks in `audit.pipeline_watermarks`. Ingest and dbt facts support `--mode incremental` for large-scale reruns.

---

## 10. Reconciliation

Source vs warehouse count and sum reconciliation → `audit.reconciliation_results`. Balance reconciliation for sample accounts (opening + credits − debits vs reported). SQL: `sql/reconciliation/`.

---

## 11. dbt

36 models across staging, intermediate, warehouse, analytics. `dbt build` runs tests (unique, not_null, relationships, accepted_values). Packages: dbt_utils.

Key marts: `mart_daily_transactions`, `mart_customer_activity`, `mart_anomaly_monitoring`.

---

## 12. Airflow

DAG `banking_daily_pipeline` with parallel ingest, sequential dbt layers, reconciliation, anomaly detection, DQ tests, audit update. Docker Compose stack on ports 5432 (Postgres) and 8080 (Airflow UI).

---

## 13. SQL Analytics

10+ queries in `sql/analytics/` demonstrating CTEs, window functions, rankings, rolling averages, cohort-style analysis, and anomaly candidacy — portfolio-ready for technical interviews.

---

## 14. Anomaly Detection

Three-method prototype:

1. Rule-based (amount, frequency, rapid, night, failures, behavior change)
2. Z-score (per-customer, threshold 3.0)
3. Isolation Forest (contamination 0.02)

Output: `monitoring.transaction_anomalies`. Terminology: **potential anomaly**, not fraud.

---

## 15. Power BI

Seven-page dashboard specification with DAX measures and star-schema import model documented in `dashboards/powerbi/`. Connects to PostgreSQL `analytics` schema.

Pages: Executive overview, transactions, customers, accounts, channel/branch, anomaly monitoring, data quality.

---

## 16. Business Insights

Generated by `src/utils/generate_insights.py` into `analysis/business_insights.md` from live SQL against marts — values reflect actual demo run outputs, labeled synthetic.

---

## 17. Testing

pytest coverage:

- Data generation (IDs, distributions, relationships)
- Validation rules
- Anomaly scoring logic
- Pipeline components

Run: `make test`

---

## 18. Performance

Index recommendations in `sql/performance/recommended_indexes.sql`. EXPLAIN ANALYZE templates in `explain_examples.sql` — populate timings from local runs.

Pre-aggregated marts reduce BI query cost.

---

## 19. Limitations

- Batch-only; not real-time fraud
- Synthetic patterns ≠ production fraud
- dbt on Postgres; scale requires cloud warehouse
- Power BI `.pbix` not committed — specs only
- Balance reconciliation approximate after DQ exclusions
- Embedded Postgres uses dynamic ports

---

## 20. Future Improvements

1. Real-time ingest (Kafka + Flink)
2. Great Expectations integration
3. dbt snapshots for full SCD audit
4. Columnar warehouse migration (see [cloud_architecture.md](cloud_architecture.md))
5. Labeled fraud evaluation dataset (still synthetic)
6. CI/CD (GitHub Actions: pytest + dbt + sqlfluff)
7. Row-level security in Power BI for multi-tenant demo
8. Data catalog (OpenMetadata / Atlan)
9. Partitioned facts by month at full volume
10. Automated EXPLAIN regression suite

---

## Conclusion

NovaBank demonstrates end-to-end data engineering and analytics maturity: ingestion, quality, dimensional modeling, orchestration, reconciliation, SQL analytics, anomaly prototyping, and BI specification — entirely on **synthetic data** suitable for portfolio and interview use.

**License:** MIT, Copyright 2026 NovaBank Analytics Portfolio.

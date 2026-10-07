# NovaBank Interview Guide

> **Disclaimer:** This project uses synthetic banking data generated solely for demonstrating data engineering, analytics, and transaction-monitoring capabilities. It does not represent real customer or banking data.

Concise answers for portfolio interviews. Expand with live demos of pipeline, dbt docs, and SQL where possible.

---

## Data Engineering

### 1. What did you build?

An end-to-end **Banking Transaction Analytics Pipeline** for fictional NovaBank: synthetic multi-source CSV generation, idempotent PostgreSQL ingestion, data quality validation, dbt star-schema warehouse, analytics marts, batch anomaly detection, reconciliation, Airflow orchestration, Power BI specifications, and pytest coverage — all on Docker with an embedded Postgres fallback.

### 2. Why PostgreSQL?

PostgreSQL 16 offers mature SQL, JSON when needed, strong indexing, window functions, and free local development. It mirrors what many banks use for operational stores and mid-size warehouses. dbt supports Postgres natively; the same dbt project can target Redshift, BigQuery, or Snowflake later with minimal changes.

### 3. Why a data warehouse?

Operational source systems are normalized, inconsistent, and optimized for OLTP — not analytics. A warehouse **integrates** core banking, card, and ATM feeds into a **conformed dimensional model** with historical tracking (SCD2), enabling consistent KPIs, BI, and monitoring without hammering source systems.

### 4. Why star schema?

Star schemas denormalize dimensions around facts for **simple joins and fast aggregations** — ideal for BI tools and analysts. Clear grain definitions prevent double-counting. NovaBank's `fact_transactions` sits at transaction-event grain with role-playing dimensions (date, customer, account, channel, branch).

### 5. What is fact table grain?

**One row in the central transaction fact represents one financial transaction event.** Aggregations are derived by grouping; we do not mix order-line and order-header grains in the same fact.

### 6. Why surrogate keys?

Natural keys (`customer_id`) can change, collide after merges, or arrive dirty from source. Surrogate integer keys (`customer_key`) give stable joins, efficient indexes, and clean SCD2 versioning without composite primary keys on facts.

### 7. What is SCD Type 2?

When a dimension attribute changes (e.g. customer status Active → Suspended), we **insert a new row** with new surrogate key, effective/expiration dates, and `is_current` flag. Historical facts keep the old key — preserving "what was true at transaction time."

### 8. How does incremental loading work?

High-volume tables carry `updated_at`. We store `last_watermark` in `audit.pipeline_watermarks`. Incremental runs process only rows where `updated_at > watermark`, then advance the watermark. dbt facts use incremental materialization with `delete+insert` on `transaction_id`.

### 9. What is idempotency?

Re-running the same pipeline input produces the **same warehouse state** — no duplicate transactions. Achieved via unique business keys, upserts, dbt `unique_key`, and delete+insert incremental strategy.

### 10. How did you handle duplicates?

Raw duplicates injected at 1% rate. Staging dedupes with `ROW_NUMBER() OVER (PARTITION BY transaction_id ORDER BY updated_at DESC)`. Raw partial unique indexes prevent persistent duplicates on clean keys.

### 11. How did you handle late data?

Transactions arriving with older `updated_at` but new to the warehouse are picked up on next incremental run if watermark logic uses ingestion time or max source timestamp. dbt incremental filter re-processes changed keys. Watermark tolerance configurable via `.env`.

### 12. How did you perform reconciliation?

Compare source CSV count/sum to `warehouse.fact_transactions`. Persist deltas to `audit.reconciliation_results`. Balance reconciliation checks opening + credits − debits vs reported balance for sample accounts. SQL in `sql/reconciliation/`.

### 13. How would you scale to 100 million transactions?

Partition facts by month; incremental dbt only; columnar cloud warehouse (Redshift/BigQuery); separate OLAP from OLTP; pre-aggregate marts; index `(date_key)`, `(customer_key, timestamp)`; consider streaming ingest (Kafka → Flink) for near-real-time; move anomaly scoring to distributed Spark or dedicated feature store.

---

## SQL

### 14. Explain window functions.

Window functions compute over a **set of rows related to the current row** without collapsing groups like `GROUP BY`. Examples: `ROW_NUMBER()` for deduping, `SUM() OVER()` for running totals, `LAG()` for previous transaction, `AVG() OVER (ORDER BY date ROWS 6 PRECEDING)` for 7-day rolling average.

### 15. How would you find the customer's previous transaction?

```sql
SELECT
    transaction_id,
    LAG(transaction_id) OVER (
        PARTITION BY customer_key
        ORDER BY transaction_timestamp
    ) AS previous_transaction_id,
    LAG(amount) OVER (
        PARTITION BY customer_key
        ORDER BY transaction_timestamp
    ) AS previous_amount
FROM warehouse.fact_transactions;
```

### 16. How would you calculate daily transaction totals?

```sql
SELECT
    d.calendar_date,
    COUNT(*) AS transaction_count,
    SUM(f.amount) AS transaction_value
FROM warehouse.fact_transactions f
JOIN warehouse.dim_date d ON f.date_key = d.date_key
GROUP BY d.calendar_date
ORDER BY d.calendar_date;
```

Or consume `analytics.mart_daily_transactions`.

### 17. How would you calculate a rolling average?

```sql
SELECT
    calendar_date,
    transaction_count,
    AVG(transaction_count) OVER (
        ORDER BY calendar_date
        ROWS BETWEEN 6 PRECEDING AND CURRENT ROW
    ) AS rolling_7d_avg
FROM analytics.mart_daily_transactions;
```

### 18. How would you identify rapid transactions?

```sql
SELECT customer_key, transaction_timestamp, amount,
       COUNT(*) OVER (
           PARTITION BY customer_key
           ORDER BY transaction_timestamp
           RANGE BETWEEN INTERVAL '10 minutes' PRECEDING AND CURRENT ROW
       ) AS txns_in_10_min
FROM warehouse.fact_transactions
HAVING COUNT(*) OVER (...) >= 5;  -- use subquery/CTE in practice
```

See `sql/analytics/anomaly_candidates.sql`.

---

## Analytics

### 19. What are the main banking KPIs?

Total transaction value/count, average transaction, success/failure rates, active customers/accounts, deposits/withdrawals/transfers, channel and branch performance, anomaly count/rate, MoM/YoY growth — defined in [metrics.md](metrics.md).

### 20. How did you calculate transaction success rate?

```text
Success Rate = Completed Transactions / (Completed + Failed + Reversed)
```

Implemented in marts and DAX measure `Transaction Success Rate`. Excludes Pending from denominator or includes based on business rule — documented as completed-over-attempted.

### 21. How did you segment customers?

Behavioral segments from **transaction count and recency** in `mart_customer_activity`: Inactive (>90 days or zero txns), Low (<10), Medium (10–49), High (50–199), Premium (≥200). Thresholds documented in dbt model and [metrics.md](metrics.md).

---

## Anomaly Detection

### 22. How does your anomaly detection work?

Batch pipeline loads transactions, runs **rule-based** checks (amount, frequency, rapid, night, failures), **z-score** vs customer baseline, and **Isolation Forest** on multivariate features. Scores merge into `monitoring.transaction_anomalies` with severity and reasons.

### 23. Why use z-score?

Z-score standardizes deviation from a customer's normal spending: ` (x - mean) / std `. Simple, interpretable, works per-customer without labels. Threshold (default 3σ) is configurable. Limitation: assumes roughly normal distribution; heavy spenders need robust stats or medians.

### 24. Why use Isolation Forest?

Unsupervised algorithm that isolates outliers in feature space — captures multivariate patterns (high amount + odd hour + burst frequency) rules might miss. Fast on demo data. Good portfolio ML story with clear unsupervised limits.

### 25. What are the limitations?

- Not real-time; batch only
- Synthetic labels ≠ real fraud patterns
- Z-score sensitive to skew; IF needs contamination tuning
- No model governance, explainability requirements, or regulatory sign-off
- Geographic "unusual location" simplified in synthetic data
- False positives would overwhelm investigators at 2% contamination in production

### 26. Why is an anomaly not necessarily fraud?

Anomalies are **statistical or rule deviations** — large legitimate purchases, payroll deposits, travel spending, or business seasonality can trigger flags. Fraud requires investigation, labels, and legal process. We use **"potential anomaly"** / **"transaction requiring review"** — the prototype prioritizes recall for demo, not precision for prosecution.

---

## Demo Tips

1. Run `make pipeline` and show `audit.pipeline_runs`
2. Open dbt docs: `cd dbt && dbt docs generate && dbt docs serve`
3. Query `mart_customer_activity` for segments
4. Show Power BI spec pages 6–7 for monitoring maturity

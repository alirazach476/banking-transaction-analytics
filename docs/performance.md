# NovaBank Query Performance

> **Disclaimer:** This project uses synthetic banking data generated solely for demonstrating data engineering, analytics, and transaction-monitoring capabilities. It does not represent real customer or banking data.

## Performance Goals

Optimize common analytical patterns:

- Transaction filtering by date and customer
- Daily/monthly aggregations
- Customer activity lookups
- Anomaly feature window calculations
- Branch and channel rankings

Demo volumes (~100k transactions) run sub-second with proper indexes. Full scale (2M+ transactions) requires indexes and incremental strategies documented here.

---

## Recommended Indexes

Full DDL: `sql/performance/recommended_indexes.sql`

| Table | Index | Purpose |
|-------|-------|---------|
| fact_transactions | `(date_key)` | Date range scans |
| fact_transactions | `(customer_key, transaction_timestamp)` | Customer history |
| fact_transactions | `(account_key)` | Account activity |
| fact_transactions | `(channel_key, date_key)` | Channel dashboards |
| fact_transactions | `(transaction_status)` | Failure analysis |
| fact_transactions | `(transaction_id)` UNIQUE | Idempotent joins |
| dim_customer | `(customer_id) WHERE is_current` | Current customer lookup |
| dim_account | `(account_id) WHERE is_current` | Current account lookup |
| monitoring.transaction_anomalies | `(transaction_timestamp)` | Anomaly time series |
| monitoring.transaction_anomalies | `(severity)` | Severity filters |
| raw.transactions | `(updated_at)` | Incremental ingest |

Partial indexes on `is_current = true` reduce dimension scan size for SCD2 customer rows.

---

## Measured Results (Live Demo Run)

Captured with `python scripts/run_explain_analyze.py` after indexes were applied.
Full output: [explain_analyze_results.md](explain_analyze_results.md).

| Query | Problem before indexes | Optimization | Measured result |
|-------|------------------------|--------------|-----------------|
| Daily txn aggregates by `date_key` | Seq scan risk on 101k rows | `idx_fact_txn_date_key` | **~8.9 ms** — Index Scan + GroupAggregate |
| Top customers by amount | Full table aggregate | HashAggregate on fact | **~99 ms** over 101,600 rows |
| Anomalies by severity | Small monitoring table | Severity index available | Sub-second grouping |

Numbers are from the verified PostgreSQL demo environment — not fabricated.

---

## EXPLAIN ANALYZE Workflow

Template in `sql/performance/explain_examples.sql`.

### Steps

1. Run query with `EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)`
2. Identify `Seq Scan` on large tables
3. Add or adjust indexes
4. Re-run and compare `Execution Time`

### Example template

```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT
    d.calendar_date,
    COUNT(*) AS txn_count,
    SUM(f.amount) AS txn_value
FROM warehouse.fact_transactions f
JOIN warehouse.dim_date d ON f.date_key = d.date_key
WHERE d.calendar_date BETWEEN '2024-01-01' AND '2024-12-31'
GROUP BY d.calendar_date
ORDER BY d.calendar_date;
```

### Recording results

| Query | Problem | Optimization | Before (ms) | After (ms) |
|-------|---------|--------------|-------------|------------|
| Daily agg by date_key | Seq Scan on fact | Index on date_key | *TBD* | *TBD* |
| Customer last 90 days | Seq Scan | Index (customer_key, timestamp) | *TBD* | *TBD* |
| Anomaly by severity | Seq Scan on monitoring | Index on severity | *TBD* | *TBD* |

> **Note:** Fill timing columns with real `EXPLAIN ANALYZE` output after running against your local database. Do not fabricate numbers.

---

## dbt Performance

- **Incremental facts** — process only changed rows at scale
- **Materialization:** facts as tables, staging as views
- **Clustering (future):** PostgreSQL declarative partitioning by `date_key` month at 100M+ rows

---

## Aggregation Strategy

Pre-compute in marts rather than scanning facts in Power BI:

- `mart_daily_transactions` — daily KPIs
- `mart_monthly_transactions` — monthly rollups
- `int_daily_transaction_metrics` — shared intermediate

DirectQuery to facts acceptable at demo scale; import mode recommended for full volumes.

---

## Connection Pooling

Python pipeline uses SQLAlchemy engine with connection pooling. Airflow tasks spawn short-lived connections — limit concurrent dbt + ingest to avoid exhausting Postgres `max_connections`.

---

## Scale-Out Path

At 100M+ transactions:

1. Partition `fact_transactions` by month
2. Move historical partitions to read replicas
3. Migrate warehouse to cloud columnar store (Redshift, BigQuery, Synapse) — see [cloud_architecture.md](cloud_architecture.md)
4. Push rolling windows to streaming pre-aggregation (Flink, ksqlDB)

---

## Maintenance

```sql
ANALYZE warehouse.fact_transactions;
ANALYZE monitoring.transaction_anomalies;
```

Run after large bulk loads. Autovacuum handles routine cleanup on PostgreSQL 16.

# Phase 4 benchmarks (measured, this machine, 2026-11-20)

Script: `PYTHONPATH=. python scripts/phase4_benchmark.py` (raw numbers in `PHASE4_BENCHMARKS.json`).
Data: 1,928,246 synthetic lifecycle events (rows with injected invalid timestamps are excluded from the typed tables).
Median of 3 runs, warm cache, local embedded PostgreSQL, single machine. Not a production benchmark.

| Step | Result |
|---|---|
| COPY 4 raw payment CSVs (2.9M rows) | 31.4 s |
| Build typed heap table (no indexes) | 9.7 s |
| Build partitioned (monthly) table + 2 indexes | 18.6 s |
| Parquet export (zstd, partitioned by month) | 1.5 s, 25.2 MB (vs 179 MB CSV) |

| Query (ms) | PG heap | PG partitioned + indexed | DuckDB on Parquet |
|---|---|---|---|
| Point lookup by payment_id | 64.8 | 1.6 | 36.7 |
| One-month scan + group | 76.2 | 10.5 | 9.1 |
| Monthly decline rate (full scan) | 378.8 | 230.5 | 33.0 |

Takeaways: indexes/partition pruning matter for lookups and range scans in Postgres; full-table analytics are far faster on columnar Parquet.
Caveats: PySpark was NOT run (not installed; only Java 8 available), so no Spark comparison is claimed. Partitioned-table size is not reported
(`pg_total_relation_size` on a partitioned parent returns 0). Only the lifecycle-events table was tuned.

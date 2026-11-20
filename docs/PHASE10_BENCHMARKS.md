# Phase 10: scale benchmarks and test status (measured 2026-11-21, one Windows machine)

Not a controlled benchmark: single run per size, other work was occasionally running on the machine (the 1M run overlapped with light
editing and tool calls), no repeated trials. Use for order-of-magnitude planning only.

## Synthetic payment generation (chunked, vectorised, defects on; 6 CSV outputs: dirty + clean)
| Payments requested | Transactions | Events | Settlements | Wall time | Dirty CSV size |
|---|---|---|---|---|---|
| 500,000 (earlier run) | 493,199 | 1,918,653 | 454,881 | 120.3 s | 285 MB |
| 1,000,000 | 986,383 | 3,838,045 | 910,026 | 228.1 s | 596 MB |
| 2,000,000 | 1,972,164 | 7,674,599 | 1,819,854 | 457.0 s | 1,192 MB |

Time scales roughly linearly (about 0.23 ms per requested payment); memory stays bounded by the chunk size (200,000).

## Reconciliation and Parquet at scale (in memory / DuckDB)
| Payments | Cleared | Settlements | Reconcile | Exceptions found | CSV read | Parquet export (events) | Parquet size | DuckDB group-by on events |
|---|---|---|---|---|---|---|---|---|
| 1M | 901,889 | 910,026 | 12.7 s | 31,362 | 26.3 s | 5.1 s | 42.3 MB | 0.09 s |
| 2M | 1,803,374 | 1,819,854 | 31.6 s | 62,298 | 51.4 s | 8.3 s | 84.2 MB | 0.12 s |

Reconciliation runs here are the pure-Python path (`src/payments/reconciliation.py`) and are not the Postgres COPY + dbt path.
Postgres load/dbt timings at 1M/2M were NOT measured (the existing database holds the 500K dataset; reloading it would have overwritten
the data behind the API and extracts). At 500K the Postgres COPY load of all four payment CSVs took 31.4 s and `dbt build` of the payments models ~49 s.

## Not measured
PySpark (not installed), concurrent API load testing, Airflow scheduler runs, Tableau extract refresh.

## Test status
`pytest`: **83 passed** (full suite against the local database; 58 passed / 22 skipped on a clean clone with no DB). Database-dependent tests need the embedded
Postgres running with the payment data loaded and dbt models built; they skip when the database is unreachable.
dbt: `dbt build --select models/payments models/external` all models and tests pass; one source-freshness check passes.
Frontend: 1 vitest unit test; the React app builds. No browser/end-to-end UI test was run.


**Correction:** the 228.1 s / 457.0 s generation times above were measured while other jobs ran concurrently. An isolated re-run (docs/PG_SCALE_BENCHMARK.md) measured 112.8 s (1M) and 229.1 s (2M); use those. Spark vs DuckDB single-node comparison: docs/SPARK_BENCHMARK.md (Spark ran in a Linux container because native Windows Spark needs winutils).

# PySpark vs DuckDB on partitioned Parquet (measured)

1,924,391 lifecycle events; Spark 3.5.3 local[*] in a Linux container (apache/spark:3.5.3-python3; native Windows Spark needs winutils) (session startup 6.7 s, excluded below); median of 3 runs after one warm-up; same machine, no cluster. Single-node numbers say nothing about cluster scale-out.

| query | Spark SQL (ms) | DuckDB (ms) |
|---|---|---|
| q1_point_lookup | 503.9 | 34.1 |
| q2_one_month_scan | 308.1 | 19.6 |
| q3_monthly_decline_rate | 457.1 | 42.9 |

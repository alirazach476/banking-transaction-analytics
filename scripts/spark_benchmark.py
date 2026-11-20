"""PySpark (local mode) vs DuckDB on the same partitioned Parquet lifecycle-events dataset.

Reads data/processed/parquet/payment_lifecycle_events (written by scripts/phase4_benchmark.py), runs the three Phase 4 queries
on Spark SQL (local[*]) and DuckDB, and writes docs/SPARK_BENCHMARK.md. Spark 3.5.3 in Docker on one machine, so this measures
single-node overhead, not cluster scaling. Run: PYTHONPATH=. python scripts/spark_benchmark.py
"""
from __future__ import annotations

import os
import statistics
import time
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
PQ = Path(os.environ.get("PARQUET_DIR", ROOT / "data" / "processed" / "parquet" / "payment_lifecycle_events"))
OUT = Path(os.environ.get("BENCH_OUT", ROOT / "docs" / "SPARK_BENCHMARK.md"))
Q = {
    "q1_point_lookup": "SELECT * FROM t WHERE payment_id = 'PAY-0000250000'",
    "q2_one_month_scan": "SELECT event_type, count(*) c, avg(response_ms) FROM t WHERE event_ts >= '2024-03-01' AND event_ts < '2024-04-01' GROUP BY 1",
    "q3_monthly_decline_rate": "SELECT date_trunc('month', event_ts) m, sum(CASE WHEN event_status='DECLINED' THEN 1 ELSE 0 END)/count(*) FROM t WHERE event_type IN ('AUTH_RESPONSE','AUTH_DECLINED') GROUP BY 1 ORDER BY 1",
}


def med(fn, runs=3):
    ts = []
    for _ in range(runs):
        t0 = time.perf_counter(); fn(); ts.append((time.perf_counter() - t0) * 1000)
    return round(statistics.median(ts), 1)


def main():
    os.environ.setdefault("PYSPARK_PYTHON", os.sys.executable)
    from pyspark.sql import SparkSession
    t0 = time.perf_counter()
    spark = (SparkSession.builder.master("local[*]").appName("novabank-bench").config("spark.ui.enabled", "false")
             .config("spark.sql.shuffle.partitions", "8").config("spark.driver.memory", "3g").getOrCreate())
    spark.sparkContext.setLogLevel("ERROR")
    startup = round(time.perf_counter() - t0, 1)
    df = spark.read.parquet(PQ.as_posix())
    df.createOrReplaceTempView("t")
    n = df.count()
    res = {"rows": n, "spark_startup_s": startup, "spark_ms": {}, "duckdb_ms": {}}
    for k, q in Q.items():
        spark.sql(q).collect()  # warm-up
        res["spark_ms"][k] = med(lambda: spark.sql(q).collect())
    spark.stop()
    d = duckdb.connect()
    d.execute(f"CREATE VIEW t AS SELECT * FROM read_parquet('{PQ.as_posix()}/*/*.parquet', hive_partitioning=true)")
    for k, q in Q.items():
        res["duckdb_ms"][k] = med(lambda: d.execute(q).fetchall())
    lines = ["# PySpark vs DuckDB on partitioned Parquet (measured)", "",
             f"{n:,} lifecycle events; Spark 3.5.3 local[*] in a Linux container (apache/spark:3.5.3-python3; native Windows Spark needs winutils) (session startup {startup} s, excluded below); "
             "median of 3 runs after one warm-up; same machine, no cluster. Single-node numbers say nothing about cluster scale-out.", "",
             "| query | Spark SQL (ms) | DuckDB (ms) |", "|---|---|---|"]
    for k in Q:
        lines.append(f"| {k} | {res['spark_ms'][k]} | {res['duckdb_ms'][k]} |")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

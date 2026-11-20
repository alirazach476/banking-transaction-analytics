"""Phase 4: load payment CSVs, build typed heap vs partitioned+indexed tables in PostgreSQL,
export Parquet, and time the same queries on each. Writes docs/PHASE4_BENCHMARKS.md (measured, this machine)."""
from __future__ import annotations
import json, statistics, time
from pathlib import Path
import duckdb
from sqlalchemy import text
from src.payments.load import load_payment_sources
from src.utils.db import get_engine

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "source" / "payments"
PQ = ROOT / "data" / "processed" / "parquet"

QUERIES = {
    "q1_point_lookup": "SELECT * FROM {t} WHERE payment_id = 'PAY-0000250000'",
    "q2_one_month_scan": "SELECT event_type, count(*) c, avg(response_ms) FROM {t} WHERE event_ts >= '2024-03-01' AND event_ts < '2024-04-01' GROUP BY 1",
    "q3_monthly_decline_rate": "SELECT date_trunc('month', event_ts) m, count(*) FILTER (WHERE event_status='DECLINED')::float/count(*) FROM {t} WHERE event_type IN ('AUTH_RESPONSE','AUTH_DECLINED') GROUP BY 1 ORDER BY 1",
}

def timed(fn, runs=3):
    ts = []
    for _ in range(runs):
        t0 = time.perf_counter(); r = fn(); ts.append(time.perf_counter() - t0)
    return round(statistics.median(ts) * 1000, 1), r

def main():
    e = get_engine(); out = {}
    t0 = time.perf_counter(); counts = load_payment_sources(SRC, e); out["load_copy_s"] = round(time.perf_counter() - t0, 1); out["rows"] = counts
    with e.begin() as c:
        c.execute(text("DROP TABLE IF EXISTS payments.evt_heap"))
        c.execute(text("DROP TABLE IF EXISTS payments.evt_part CASCADE"))
        t0 = time.perf_counter()
        c.execute(text("""CREATE TABLE payments.evt_heap AS SELECT event_id, payment_id, event_type,
            event_ts::timestamp event_ts, CASE WHEN amount ~ '^-?[0-9]+(\.[0-9]+)?$' THEN amount::numeric END amount, currency, event_status,
            reason_code, CASE WHEN response_ms ~ '^[0-9]{1,9}$' THEN response_ms::int END response_ms, dq_defect
            FROM raw.payment_lifecycle_events WHERE event_ts ~ '^[0-9]{4}-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|30|31) ([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$'
              AND NOT (event_ts ~ '-(02-(30|31)|(04|06|09|11)-31)')"""))
        out["build_heap_s"] = round(time.perf_counter() - t0, 1)
        c.execute(text("""CREATE TABLE payments.evt_part (LIKE payments.evt_heap) PARTITION BY RANGE (event_ts)"""))
        mm = c.execute(text("SELECT date_trunc('month',min(event_ts)), date_trunc('month',max(event_ts)) FROM payments.evt_heap")).one()
        m = mm[0]
        while m <= mm[1]:
            import datetime as dt
            nxt = (m + dt.timedelta(days=32)).replace(day=1)
            c.execute(text(f"CREATE TABLE payments.evt_part_{m:%Y_%m} PARTITION OF payments.evt_part FOR VALUES FROM ('{m:%Y-%m-%d}') TO ('{nxt:%Y-%m-%d}')"))
            m = nxt
        t0 = time.perf_counter()
        c.execute(text("INSERT INTO payments.evt_part SELECT * FROM payments.evt_heap"))
        c.execute(text("CREATE INDEX ON payments.evt_part (payment_id)"))
        c.execute(text("CREATE INDEX ON payments.evt_part (event_type, event_ts)"))
        out["build_partitioned_indexed_s"] = round(time.perf_counter() - t0, 1)
    with e.connect().execution_options(isolation_level="AUTOCOMMIT") as c:
        c.execute(text("ANALYZE payments.evt_heap")); c.execute(text("ANALYZE payments.evt_part"))
        out["pg"] = {}
        for t in ("payments.evt_heap", "payments.evt_part"):
            for k, q in QUERIES.items():
                ms, _ = timed(lambda: c.execute(text(q.format(t=t))).fetchall())
                out["pg"][f"{t}:{k}"] = ms
        out["size_mb"] = {t: c.execute(text(f"SELECT pg_total_relation_size('{t}')/1e6")).scalar() for t in ("payments.evt_heap", "payments.evt_part")}
    # Parquet + DuckDB
    d = duckdb.connect(); PQ.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()
    d.execute(f"""COPY (SELECT event_id, payment_id, event_type, try_cast(event_ts AS TIMESTAMP) event_ts,
        try_cast(amount AS DECIMAL(18,2)) amount, currency, event_status, reason_code, try_cast(response_ms AS INT) response_ms,
        dq_defect, strftime(try_cast(event_ts AS TIMESTAMP),'%Y-%m') ym
        FROM read_csv('{(SRC/'payment_lifecycle_events.csv').as_posix()}', all_varchar=true)
        WHERE try_cast(event_ts AS TIMESTAMP) IS NOT NULL)
        TO '{(PQ/'payment_lifecycle_events').as_posix()}' (FORMAT parquet, PARTITION_BY (ym), COMPRESSION zstd, OVERWRITE_OR_IGNORE)""")
    out["parquet_export_s"] = round(time.perf_counter() - t0, 1)
    out["parquet_mb"] = round(sum(p.stat().st_size for p in (PQ/'payment_lifecycle_events').rglob('*.parquet')) / 1e6, 1)
    glob = (PQ / 'payment_lifecycle_events').as_posix() + "/*/*.parquet"
    out["duckdb_parquet"] = {}
    for k, q in QUERIES.items():
        ms, _ = timed(lambda: d.execute(q.format(t=f"read_parquet('{glob}', hive_partitioning=true)")).fetchall())
        out["duckdb_parquet"][k] = ms
    print(json.dumps(out, indent=2, default=str))
    (ROOT / "docs" / "PHASE4_BENCHMARKS.json").write_text(json.dumps(out, indent=2, default=str))

if __name__ == "__main__":
    main()

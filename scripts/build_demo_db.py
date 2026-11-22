"""Snapshot the relations the analytics API reads from PostgreSQL into one DuckDB file for the hosted, read-only demo.

The hosted app (Vercel) cannot run PostgreSQL, so the same FastAPI routers run against this file (env DEMO_DUCKDB).
All of it is SYNTHETIC data plus pipeline metadata; nothing here is real customer data.

Run (needs the local PostgreSQL with the UI objects): PYTHONPATH=. python scripts/build_demo_db.py [--out deploy/vercel/data/demo.duckdb]
"""
from __future__ import annotations

import argparse
import decimal
from pathlib import Path

import duckdb
import pandas as pd
from sqlalchemy import text

from src.utils.db import get_engine

RELATIONS = [
    "ui.payments_usd", "ui.core_txn_usd", "ui.merchant_stats", "ui.city_centroids",
    "monitoring.transaction_anomalies", "monitoring.anomaly_investigations",
    "warehouse.dim_customer", "warehouse.dim_merchant", "warehouse.dim_branch", "warehouse.fact_transactions",
    "analytics.mart_customer_activity", "analytics.mart_branch_performance",
    "audit.pipeline_runs", "audit.data_quality_results", "audit.source_ingestion", "audit.reconciliation_results",
    "payments.reconciliation_runs", "payments.investigation_queue",
    "raw.fx_rates_synthetic",
]


def normalise(df: pd.DataFrame, tz: str) -> pd.DataFrame:
    """Make pandas types DuckDB-friendly: Decimal -> float, tz-aware timestamps -> wall-clock timestamps in the session zone (what the UI shows)."""
    for c in df.columns:
        col = df[c]
        if str(col.dtype).startswith("datetime64") and getattr(col.dt, "tz", None) is not None:
            df[c] = col.dt.tz_convert(tz).dt.tz_localize(None)  # wall-clock time in the database session zone, as the UI shows it
        elif col.dtype == object and col.map(lambda v: isinstance(v, decimal.Decimal)).any():
            df[c] = col.map(lambda v: float(v) if isinstance(v, decimal.Decimal) else v)
        elif col.dtype == object and col.map(lambda v: hasattr(v, "tzinfo") and getattr(v, "tzinfo", None) is not None).any():
            df[c] = pd.to_datetime(col.map(lambda v: v.astimezone(pd.Timestamp(0, tz=tz).tzinfo).replace(tzinfo=None) if getattr(v, "tzinfo", None) else v))
    return df


def build(out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        out.unlink()
    con = duckdb.connect(str(out))
    eng = get_engine()
    with eng.connect() as c:
        tz = c.execute(text("SHOW timezone")).scalar()
    print("session time zone:", tz)
    for rel in RELATIONS:
        schema = rel.split(".")[0]
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        with eng.connect() as c:
            df = pd.read_sql(text(f"SELECT * FROM {rel}"), c)
        df = normalise(df, tz)
        con.register("_df", df)
        con.execute(f"CREATE TABLE {rel} AS SELECT * FROM _df")
        con.unregister("_df")
        print(f"{rel:42s} {len(df):>9,} rows")
    con.execute("DELETE FROM monitoring.anomaly_investigations")  # the demo is read-only and starts with no analyst notes
    con.execute("CHECKPOINT")
    con.close()
    print(f"{out}: {out.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="deploy/vercel/data/demo.duckdb")
    build(Path(ap.parse_args().out))

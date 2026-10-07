"""Verify key table row counts after pipeline run."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import get_settings
from sqlalchemy import text
from src.utils.db import get_engine

get_settings.cache_clear()
engine = get_engine()

tables = [
    ("raw", "customers"),
    ("raw", "accounts"),
    ("raw", "transactions"),
    ("raw", "transfers"),
    ("raw", "atm_transactions"),
    ("raw", "card_transactions"),
    ("warehouse", "dim_customer"),
    ("warehouse", "dim_account"),
    ("warehouse", "fact_transactions"),
    ("warehouse", "fact_transfers"),
    ("analytics", "mart_daily_transactions"),
    ("analytics", "mart_customer_activity"),
    ("analytics", "mart_channel_performance"),
    ("monitoring", "transaction_anomalies"),
    ("audit", "data_quality_results"),
    ("audit", "reconciliation_results"),
]

print("NovaBank pipeline verification (SYNTHETIC DATA)")
print("=" * 50)
with engine.connect() as conn:
    for schema, table in tables:
        exists = conn.execute(
            text(
                "SELECT EXISTS (SELECT 1 FROM information_schema.tables "
                "WHERE table_schema=:s AND table_name=:t)"
            ),
            {"s": schema, "t": table},
        ).scalar()
        if not exists:
            print(f"  MISSING  {schema}.{table}")
            continue
        cnt = conn.execute(text(f"SELECT COUNT(*) FROM {schema}.{table}")).scalar()
        print(f"  {schema}.{table}: {cnt:,}")
print("=" * 50)
print("OK")

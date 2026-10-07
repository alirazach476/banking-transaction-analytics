"""Capture real EXPLAIN ANALYZE results for docs/performance.md."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text
from config.settings import get_settings
from src.utils.db import get_engine

get_settings.cache_clear()
engine = get_engine()

queries = {
    "daily_txn_count": """
        EXPLAIN ANALYZE
        SELECT date_key, COUNT(*), SUM(amount)
        FROM warehouse.fact_transactions
        GROUP BY date_key
        ORDER BY date_key
        LIMIT 100
    """,
    "customer_activity": """
        EXPLAIN ANALYZE
        SELECT customer_key, COUNT(*), SUM(amount)
        FROM warehouse.fact_transactions
        GROUP BY customer_key
        ORDER BY SUM(amount) DESC
        LIMIT 20
    """,
    "anomaly_by_severity": """
        EXPLAIN ANALYZE
        SELECT severity, COUNT(*), SUM(amount)
        FROM monitoring.transaction_anomalies
        GROUP BY severity
    """,
}

out_lines = ["# EXPLAIN ANALYZE Results (live run)\n"]
out_lines.append(
    "> Synthetic NovaBank data. Numbers below are from an actual PostgreSQL run.\n"
)

with engine.connect() as conn:
    for name, sql in queries.items():
        out_lines.append(f"\n## {name}\n```\n")
        rows = conn.execute(text(sql)).fetchall()
        for r in rows:
            out_lines.append(str(r[0]) + "\n")
        out_lines.append("```\n")

path = get_settings().project_root / "docs" / "explain_analyze_results.md"
path.write_text("".join(out_lines), encoding="utf-8")
print(f"Wrote {path}")

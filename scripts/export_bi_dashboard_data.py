"""Export analytics marts to JSON for BI dashboard (canvas + HTML)."""
from __future__ import annotations

import json
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from config.settings import get_settings
from src.utils.db import get_engine

get_settings.cache_clear()


def _ser(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def q(conn, sql: str):
    rows = conn.execute(text(sql)).mappings().all()
    return [{k: _ser(v) for k, v in dict(r).items()} for r in rows]


def main():
    engine = get_engine()
    with engine.connect() as conn:
        kpis = q(
            conn,
            """
            SELECT
              (SELECT COUNT(*) FROM warehouse.fact_transactions) AS transaction_count,
              (SELECT COALESCE(SUM(amount::numeric),0) FROM warehouse.fact_transactions) AS total_value,
              (SELECT COALESCE(AVG(amount::numeric),0) FROM warehouse.fact_transactions) AS avg_value,
              (SELECT COUNT(*) FROM warehouse.dim_customer WHERE is_current) AS active_customers,
              (SELECT COUNT(*) FROM warehouse.dim_account) AS active_accounts,
              (SELECT COUNT(*) FROM monitoring.transaction_anomalies) AS anomaly_count,
              (SELECT COUNT(*) FILTER (WHERE transaction_status='Completed')
                 FROM warehouse.fact_transactions)::numeric
               / NULLIF((SELECT COUNT(*) FROM warehouse.fact_transactions),0) AS success_rate,
              (SELECT COUNT(*) FILTER (WHERE transaction_status='Failed')
                 FROM warehouse.fact_transactions)::numeric
               / NULLIF((SELECT COUNT(*) FROM warehouse.fact_transactions),0) AS failure_rate
            """,
        )[0]

        daily = q(
            conn,
            """
            SELECT transaction_date::text AS day,
                   transaction_count,
                   ROUND(total_amount::numeric, 2) AS transaction_value,
                   ROUND(total_completed_amount::numeric, 2) AS completed_value,
                   ROUND(rolling_7d_avg_transaction_count::numeric, 1) AS rolling_7d_count,
                   ROUND(rolling_30d_avg_completed_amount::numeric, 2) AS rolling_30d_value
            FROM analytics.mart_daily_transactions
            ORDER BY transaction_date
            """,
        )
        monthly = q(
            conn,
            """
            SELECT month_start::text AS month,
                   month_label,
                   transaction_count,
                   ROUND(total_amount::numeric, 2) AS transaction_value,
                   ROUND(total_completed_amount::numeric, 2) AS completed_value,
                   ROUND(avg_completed_amount::numeric, 2) AS avg_transaction_value,
                   ROUND(failure_rate_pct::numeric, 2) AS failure_rate_pct
            FROM analytics.mart_monthly_transactions
            ORDER BY month_start
            """,
        )

        channels = q(
            conn,
            """
            SELECT channel,
                   transaction_count,
                   total_completed_amount AS transaction_value,
                   ROUND(failure_rate_pct::numeric, 2) AS failure_rate_pct,
                   ROUND(success_rate_pct::numeric, 2) AS success_rate_pct
            FROM analytics.mart_channel_performance
            WHERE channel IS NOT NULL AND channel <> 'Unknown'
            ORDER BY transaction_count DESC
            """,
        )

        segments = q(
            conn,
            """
            SELECT activity_segment AS segment, COUNT(*) AS customers
            FROM analytics.mart_customer_activity
            GROUP BY 1 ORDER BY customers DESC
            """,
        )

        branches = q(
            conn,
            """
            SELECT branch_name, region, city,
                   transaction_count,
                   total_completed_amount AS transaction_value,
                   ROUND(failure_rate_pct::numeric, 2) AS failure_rate_pct,
                   active_customers
            FROM analytics.mart_branch_performance
            ORDER BY total_completed_amount DESC NULLS LAST
            LIMIT 15
            """,
        )

        txn_types = q(
            conn,
            """
            SELECT transaction_type,
                   COUNT(*) AS transaction_count,
                   ROUND(SUM(amount::numeric), 2) AS transaction_value
            FROM warehouse.fact_transactions
            GROUP BY 1 ORDER BY transaction_count DESC
            """,
        )

        anomalies = q(
            conn,
            """
            SELECT severity, COUNT(*) AS cnt,
                   ROUND(COALESCE(SUM(amount),0)::numeric, 2) AS amount
            FROM monitoring.transaction_anomalies
            GROUP BY 1
            ORDER BY cnt DESC
            """,
        )

        anomaly_sample = q(
            conn,
            """
            SELECT transaction_id, customer_id,
                   transaction_timestamp::text AS ts,
                   ROUND(amount::numeric, 2) AS amount,
                   severity, anomaly_reason,
                   ROUND(COALESCE(rule_based_score,0)::numeric, 2) AS score
            FROM monitoring.transaction_anomalies
            WHERE severity IN ('High','Critical')
            ORDER BY amount DESC NULLS LAST
            LIMIT 25
            """,
        )

        regions = q(
            conn,
            """
            SELECT COALESCE(c.region, 'Unknown') AS region,
                   COUNT(*) AS transaction_count,
                   ROUND(SUM(f.amount::numeric), 2) AS transaction_value
            FROM warehouse.fact_transactions f
            JOIN warehouse.dim_customer c
              ON f.customer_key = c.customer_key AND c.is_current
            GROUP BY 1 ORDER BY transaction_value DESC
            """,
        )

        failures = q(
            conn,
            """
            SELECT TO_CHAR(DATE_TRUNC('month', transaction_timestamp), 'YYYY-MM') AS month,
                   COUNT(*) FILTER (WHERE transaction_status='Failed') AS failed,
                   COUNT(*) FILTER (WHERE transaction_status='Reversed') AS reversed,
                   COUNT(*) AS total
            FROM warehouse.fact_transactions
            GROUP BY 1 ORDER BY 1
            """,
        )

    # Fallback monthly from daily if mart columns differ
    if monthly and "transaction_value" not in monthly[0]:
        # try alternate keys
        for row in monthly:
            for k in list(row.keys()):
                if "value" in k.lower() or "amount" in k.lower():
                    row["transaction_value"] = row[k]

    # daily may have different column names
    if daily and "transaction_value" not in daily[0]:
        for row in daily:
            for k in list(row.keys()):
                if "value" in k.lower() or "amount" in k.lower():
                    row["transaction_value"] = row.get(k)

    # sample daily for sparkline: last 90 points evenly
    daily_chart = daily
    if len(daily) > 90:
        step = max(1, len(daily) // 90)
        daily_chart = daily[::step][:90]

    payload = {
        "meta": {
            "bank": "NovaBank",
            "disclaimer": (
                "Synthetic banking data for demonstration only. "
                "Not real customer or financial records."
            ),
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "source": "PostgreSQL analytics + warehouse schemas",
        },
        "kpis": kpis,
        "daily": daily_chart,
        "monthly": monthly,
        "channels": channels,
        "segments": segments,
        "branches": branches,
        "txn_types": txn_types,
        "anomalies": anomalies,
        "anomaly_sample": anomaly_sample,
        "regions": regions,
        "failures": failures,
    }

    out_dir = get_settings().project_root / "dashboards" / "data"
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / "bi_dashboard.json"
    out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {out}")
    print(json.dumps({k: (len(v) if isinstance(v, list) else v) for k, v in payload.items() if k != "meta"}, default=str)[:500])
    return payload


if __name__ == "__main__":
    main()

"""
Generate business insights markdown from database aggregates.

All figures come from live SQL queries. Data is synthetic NovaBank data.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from config.settings import get_settings
from src.utils.db import get_engine, read_sql
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


def _table_exists(engine, schema: str, table: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = :s AND table_name = :t
                )
                """
            ),
            {"s": schema, "t": table},
        ).fetchone()
    return bool(row[0]) if row else False


def _safe_scalar(engine, query: str, default=0):
    try:
        df = read_sql(query)
        if df.empty:
            return default
        return df.iloc[0, 0]
    except Exception:
        return default


def _query_metrics(engine) -> dict:
    metrics: dict = {"sources_used": [], "notes": []}
    settings = get_settings()

    # Customer / account counts
    if _table_exists(engine, "analytics", "mart_customer_activity"):
        metrics["sources_used"].append("analytics.mart_customer_activity")
        metrics["customer_count"] = _safe_scalar(
            engine, "SELECT COUNT(*) FROM analytics.mart_customer_activity"
        )
    elif _table_exists(engine, "raw", "customers"):
        metrics["sources_used"].append("raw.customers")
        metrics["customer_count"] = _safe_scalar(
            engine, "SELECT COUNT(*) FROM raw.customers"
        )
        metrics["notes"].append("analytics mart unavailable; used raw.customers")
    else:
        metrics["customer_count"] = 0
        metrics["notes"].append("customers table missing")

    if _table_exists(engine, "analytics", "mart_channel_performance"):
        metrics["sources_used"].append("analytics.mart_channel_performance")
    if _table_exists(engine, "analytics", "mart_daily_transactions"):
        metrics["sources_used"].append("analytics.mart_daily_transactions")

    if _table_exists(engine, "warehouse", "fact_transactions"):
        metrics["sources_used"].append("warehouse.fact_transactions")
        txn_q = """
            SELECT COUNT(*) AS cnt,
                   COALESCE(SUM(amount::numeric), 0) AS total_amount,
                   COALESCE(AVG(amount::numeric), 0) AS avg_amount
            FROM warehouse.fact_transactions
        """
    elif _table_exists(engine, "raw", "transactions"):
        metrics["sources_used"].append("raw.transactions")
        txn_q = """
            SELECT COUNT(*) AS cnt,
                   COALESCE(SUM(
                       CASE WHEN amount ~ '^-?[0-9]*\\.?[0-9]+$'
                            THEN amount::numeric ELSE 0 END
                   ), 0) AS total_amount,
                   COALESCE(AVG(
                       CASE WHEN amount ~ '^-?[0-9]*\\.?[0-9]+$'
                            THEN amount::numeric END
                   ), 0) AS avg_amount
            FROM raw.transactions
        """
        metrics["notes"].append("warehouse unavailable; used raw.transactions")
    else:
        metrics["transaction_count"] = 0
        metrics["total_volume"] = 0
        metrics["avg_amount"] = 0
        metrics["notes"].append("transactions table missing")
        txn_q = None

    if txn_q:
        df = read_sql(txn_q)
        metrics["transaction_count"] = int(df.iloc[0]["cnt"])
        metrics["total_volume"] = float(df.iloc[0]["total_amount"])
        metrics["avg_amount"] = float(df.iloc[0]["avg_amount"])

    metrics["account_count"] = _safe_scalar(
        engine,
        "SELECT COUNT(*) FROM raw.accounts"
        if _table_exists(engine, "raw", "accounts")
        else "SELECT 0",
    )

    if _table_exists(engine, "monitoring", "transaction_anomalies"):
        metrics["sources_used"].append("monitoring.transaction_anomalies")
        df = read_sql(
            """
            SELECT severity, COUNT(*) AS cnt
            FROM monitoring.transaction_anomalies
            GROUP BY severity
            ORDER BY cnt DESC
            """
        )
        metrics["anomalies_by_severity"] = (
            df.set_index("severity")["cnt"].to_dict() if not df.empty else {}
        )
        metrics["anomaly_count"] = int(df["cnt"].sum()) if not df.empty else 0
    else:
        metrics["anomalies_by_severity"] = {}
        metrics["anomaly_count"] = 0
        metrics["notes"].append("monitoring.transaction_anomalies missing")

    # Channel breakdown from analytics mart or raw
    if _table_exists(engine, "analytics", "mart_channel_performance"):
        ch = read_sql(
            """
            SELECT channel, transaction_count
            FROM analytics.mart_channel_performance
            ORDER BY transaction_count DESC
            LIMIT 5
            """
        )
    elif _table_exists(engine, "raw", "transactions"):
        ch = read_sql(
            """
            SELECT channel, COUNT(*) AS transaction_count
            FROM raw.transactions
            WHERE channel IS NOT NULL AND TRIM(channel) <> ''
            GROUP BY channel
            ORDER BY transaction_count DESC
            LIMIT 5
            """
        )
    else:
        ch = None

    metrics["top_channels"] = (
        ch.to_dict("records") if ch is not None and not ch.empty else []
    )

    # Customer segments
    if _table_exists(engine, "analytics", "mart_customer_activity"):
        segs = read_sql(
            """
            SELECT activity_segment, COUNT(*) AS customer_count
            FROM analytics.mart_customer_activity
            GROUP BY activity_segment
            ORDER BY customer_count DESC
            """
        )
        metrics["segments"] = segs.to_dict("records") if not segs.empty else []

    # Top branch
    if _table_exists(engine, "analytics", "mart_branch_performance"):
        br = read_sql(
            """
            SELECT branch_name, region, transaction_count,
                   total_completed_amount, failure_rate_pct
            FROM analytics.mart_branch_performance
            ORDER BY total_completed_amount DESC NULLS LAST
            LIMIT 5
            """
        )
        metrics["top_branches"] = br.to_dict("records") if not br.empty else []

    # Channel failure rates
    if _table_exists(engine, "analytics", "mart_channel_performance"):
        fail = read_sql(
            """
            SELECT channel, failure_rate_pct, success_rate_pct, transaction_count
            FROM analytics.mart_channel_performance
            ORDER BY failure_rate_pct DESC NULLS LAST
            """
        )
        metrics["channel_quality"] = fail.to_dict("records") if not fail.empty else []
        total_ch = sum(float(r.get("transaction_count") or 0) for r in metrics["top_channels"])
        mobile = next(
            (
                float(r.get("transaction_count") or 0)
                for r in metrics["top_channels"]
                if str(r.get("channel", "")).lower().startswith("mobile")
            ),
            0.0,
        )
        metrics["mobile_share_pct"] = (
            round(100.0 * mobile / total_ch, 1) if total_ch else 0.0
        )

    metrics["generated_at"] = datetime.now(timezone.utc).isoformat()
    metrics["data_label"] = (
        "SYNTHETIC DATA — NovaBank demonstration dataset only. "
        "Not real customer or banking records."
    )
    return metrics


def _render_markdown(metrics: dict) -> str:
    lines = [
        "# NovaBank Business Insights",
        "",
        f"> **{metrics['data_label']}**",
        "",
        f"*Generated at: {metrics['generated_at']}*",
        "",
        "## Executive Summary",
        "",
        f"- **Customers:** {metrics.get('customer_count', 0):,}",
        f"- **Accounts:** {metrics.get('account_count', 0):,}",
        f"- **Transactions:** {metrics.get('transaction_count', 0):,}",
        f"- **Total transaction volume:** ${metrics.get('total_volume', 0):,.2f}",
        f"- **Average transaction amount:** ${metrics.get('avg_amount', 0):,.2f}",
        f"- **Transactions requiring review (anomalies):** {metrics.get('anomaly_count', 0):,}",
        "",
    ]

    if metrics.get("anomalies_by_severity"):
        lines.append("### Anomalies by Severity")
        lines.append("")
        for sev, cnt in metrics["anomalies_by_severity"].items():
            lines.append(f"- **{sev}:** {cnt:,}")
        lines.append("")

    if metrics.get("top_channels"):
        lines.append("## Top Channels by Volume")
        lines.append("")
        for row in metrics["top_channels"]:
            ch = row.get("channel", "Unknown")
            cnt = row.get("transaction_count", 0)
            lines.append(f"- **{ch}:** {int(cnt):,} transactions")
        if metrics.get("mobile_share_pct") is not None:
            lines.append("")
            lines.append(
                f"Mobile App represents **{metrics['mobile_share_pct']}%** of "
                "transaction volume among the top channels listed above."
            )
        lines.append("")

    if metrics.get("segments"):
        lines.append("## Customer Activity Segments")
        lines.append("")
        lines.append(
            "Thresholds: Inactive (>90 days since last txn relative to dataset "
            "as-of date, or 0 txns); Low (<10); Medium (10–49); High (50–199); "
            "Premium (≥200)."
        )
        lines.append("")
        for row in metrics["segments"]:
            lines.append(
                f"- **{row.get('activity_segment')}:** "
                f"{int(row.get('customer_count', 0)):,} customers"
            )
        lines.append("")

    if metrics.get("top_branches"):
        lines.append("## Top Branches by Completed Transaction Value")
        lines.append("")
        for row in metrics["top_branches"]:
            lines.append(
                f"- **{row.get('branch_name')}** ({row.get('region')}): "
                f"${float(row.get('total_completed_amount') or 0):,.2f} "
                f"across {int(row.get('transaction_count') or 0):,} txns "
                f"(failure rate {float(row.get('failure_rate_pct') or 0):.2f}%)"
            )
        lines.append("")

    if metrics.get("channel_quality"):
        lines.append("## Channel Success / Failure Rates")
        lines.append("")
        for row in metrics["channel_quality"]:
            lines.append(
                f"- **{row.get('channel')}:** "
                f"success {float(row.get('success_rate_pct') or 0):.2f}%, "
                f"failure {float(row.get('failure_rate_pct') or 0):.2f}% "
                f"({int(row.get('transaction_count') or 0):,} txns)"
            )
        lines.append("")

    if metrics.get("sources_used"):
        lines.append("## Data Sources Queried")
        lines.append("")
        for src in sorted(set(metrics["sources_used"])):
            lines.append(f"- `{src}`")
        lines.append("")

    if metrics.get("notes"):
        lines.append("## Notes")
        lines.append("")
        for note in metrics["notes"]:
            lines.append(f"- {note}")
        lines.append("")

    lines.append(
        "---\n"
        "*This report is for analytical demonstration. Anomaly flags are labeled "
        "'Potential anomaly' / 'Transaction requiring review' and must not be used "
        "as automated fraud decisions.*"
    )
    return "\n".join(lines)


def generate_insights(output_path: Path | None = None) -> Path:
    settings = get_settings()
    engine = get_engine()
    metrics = _query_metrics(engine)
    content = _render_markdown(metrics)

    out = output_path or (settings.project_root / "analysis" / "business_insights.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")
    logger.info("Business insights written to %s", out)
    return out


def main() -> Path:
    return generate_insights()


if __name__ == "__main__":
    main()

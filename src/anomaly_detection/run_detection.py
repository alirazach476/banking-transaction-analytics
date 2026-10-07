"""
Orchestrate anomaly detection and persist to monitoring.transaction_anomalies.

Terminology: "Potential anomaly" / "Transaction requiring review".
Analytical prototype — not a production fraud decision engine.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yaml
from sqlalchemy import text

from config.settings import get_settings
from src.anomaly_detection.ml_isolation_forest import detect_ml_anomalies
from src.anomaly_detection.rule_based import detect_rule_based_anomalies
from src.anomaly_detection.statistical import detect_statistical_anomalies
from src.utils.db import get_engine, run_ddl
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


def load_anomaly_config() -> dict[str, Any]:
    path = get_settings().project_root / "config" / "anomaly_config.yaml"
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def _table_exists(engine, schema: str, table: str) -> bool:
    q = """
        SELECT EXISTS (
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = :schema AND table_name = :table
        )
    """
    with engine.connect() as conn:
        row = conn.execute(text(q), {"schema": schema, "table": table}).fetchone()
    return bool(row[0]) if row else False


def load_transactions(engine=None) -> pd.DataFrame:
    """Load transactions from staging (preferred), enriched fact join, or raw."""
    engine = engine or get_engine()
    if _table_exists(engine, "staging", "stg_transactions"):
        q = """
            SELECT transaction_id, account_id, customer_id, transaction_timestamp,
                   transaction_type, amount, currency, channel, transaction_status,
                   is_injected_anomaly
            FROM staging.stg_transactions
            WHERE transaction_id IS NOT NULL
        """
        logger.info("Loading transactions from staging.stg_transactions")
    elif _table_exists(engine, "warehouse", "fact_transactions") and _table_exists(
        engine, "warehouse", "dim_customer"
    ):
        q = """
            SELECT
                f.transaction_id,
                a.account_id,
                c.customer_id,
                f.transaction_timestamp,
                f.transaction_type,
                f.amount,
                f.currency,
                f.channel,
                f.transaction_status,
                f.is_injected_anomaly
            FROM warehouse.fact_transactions f
            LEFT JOIN warehouse.dim_customer c
                ON f.customer_key = c.customer_key AND c.is_current
            LEFT JOIN warehouse.dim_account a
                ON f.account_key = a.account_key
        """
        logger.info("Loading transactions from warehouse fact+dims")
    else:
        q = """
            SELECT transaction_id, account_id, customer_id, transaction_timestamp,
                   transaction_type, amount, currency, channel, transaction_status,
                   is_injected_anomaly
            FROM raw.transactions
            WHERE transaction_id IS NOT NULL AND TRIM(transaction_id) <> ''
        """
        logger.info("Loading transactions from raw.transactions (warehouse unavailable)")

    df = pd.read_sql(text(q), engine)
    df["amount"] = pd.to_numeric(df["amount"], errors="coerce")
    df["transaction_timestamp"] = pd.to_datetime(
        df["transaction_timestamp"], errors="coerce"
    )
    if "is_injected_anomaly" in df.columns:
        df["is_injected_anomaly"] = (
            df["is_injected_anomaly"]
            .astype(str)
            .str.lower()
            .isin(["true", "1", "yes", "t"])
        )
    else:
        df["is_injected_anomaly"] = False
    return df


def _merge_results(
    rule_df: pd.DataFrame,
    stat_df: pd.DataFrame,
    ml_df: pd.DataFrame,
) -> pd.DataFrame:
    base = rule_df.copy()
    base = base.merge(stat_df, on="transaction_id", how="left", suffixes=("", "_stat"))
    base = base.merge(ml_df, on="transaction_id", how="left")

    if "z_score_stat" in base.columns:
        base["z_score"] = base["z_score"].fillna(base["z_score_stat"])
        base = base.drop(columns=["z_score_stat"], errors="ignore")

    all_reasons: list[str] = []
    for _, row in base.iterrows():
        parts: list[str] = []
        for r in row.get("reasons") or []:
            if r:
                parts.append(str(r))
        if row.get("statistical_reason"):
            parts.append(str(row["statistical_reason"]))
        if row.get("ml_anomaly_flag"):
            parts.append(
                f"Potential anomaly: ml_isolation_forest "
                f"(score={row.get('anomaly_score', 0):.4f})"
            )
        if parts:
            all_reasons.append("; ".join(parts))
        else:
            all_reasons.append(None)

    base["anomaly_reason"] = all_reasons
    base["is_flagged"] = base["is_potential_anomaly"] | base.get(
        "statistical_flag", False
    ).fillna(False) | base.get("ml_anomaly_flag", False).fillna(False)

    # Escalate severity if ML or statistical also flagged
    def _final_severity(row) -> str | None:
        if not row["is_flagged"]:
            return None
        sev = row.get("severity") or "Low"
        if row.get("ml_anomaly_flag") and sev in ("Low", "Medium"):
            return "High"
        if row.get("statistical_flag") and sev == "Low":
            return "Medium"
        return sev

    base["severity"] = base.apply(_final_severity, axis=1)
    base["ml_anomaly_score"] = base.get("anomaly_score", 0.0).fillna(0.0)
    return base


def _write_anomalies(
    engine,
    df: pd.DataFrame,
    mode: str = "full",
) -> int:
    flagged = df[df["is_flagged"]].copy()
    if flagged.empty:
        logger.info("No anomalies to persist")
        with engine.begin() as conn:
            if mode == "full":
                conn.execute(text("DELETE FROM monitoring.transaction_anomalies"))
        return 0

    out = flagged.rename(
        columns={
            "anomaly_score": "ml_anomaly_score_raw",
        }
    )
    out["detected_at"] = datetime.now(timezone.utc)
    out["ml_anomaly_score"] = out.get("ml_anomaly_score", 0.0)

    cols = [
        "transaction_id",
        "customer_id",
        "account_id",
        "transaction_timestamp",
        "amount",
        "rule_based_score",
        "ml_anomaly_score",
        "anomaly_reason",
        "severity",
        "z_score",
        "is_injected_anomaly",
        "detected_at",
    ]
    for c in cols:
        if c not in out.columns:
            out[c] = None
    out["is_injected_anomaly"] = out["is_injected_anomaly"].fillna(False).astype(bool)
    out["rule_based_score"] = pd.to_numeric(out["rule_based_score"], errors="coerce")
    out["ml_anomaly_score"] = pd.to_numeric(out["ml_anomaly_score"], errors="coerce")
    out["z_score"] = pd.to_numeric(out["z_score"], errors="coerce")
    out["amount"] = pd.to_numeric(out["amount"], errors="coerce")
    out = out[cols]

    with engine.begin() as conn:
        if mode == "full":
            conn.execute(text("DELETE FROM monitoring.transaction_anomalies"))
        else:
            ids = out["transaction_id"].tolist()
            if ids:
                conn.execute(
                    text(
                        "DELETE FROM monitoring.transaction_anomalies "
                        "WHERE transaction_id = ANY(:ids)"
                    ),
                    {"ids": ids},
                )

        out.to_sql(
            "_stg_anomalies",
            conn,
            schema="monitoring",
            if_exists="replace",
            index=False,
            method="multi",
            chunksize=2000,
        )
        insert_cols = ", ".join(f'"{c}"' for c in cols)
        # Cast boolean/timestamps from temp table text/bool variants
        select_cols = """
            "transaction_id", "customer_id", "account_id",
            "transaction_timestamp"::timestamptz,
            "amount"::numeric,
            "rule_based_score"::numeric,
            "ml_anomaly_score"::numeric,
            "anomaly_reason",
            "severity",
            "z_score"::numeric,
            COALESCE("is_injected_anomaly"::boolean, false),
            "detected_at"::timestamptz
        """
        conn.execute(
            text(
                f"""
                INSERT INTO monitoring.transaction_anomalies ({insert_cols})
                SELECT {select_cols} FROM monitoring._stg_anomalies
                """
            )
        )
        conn.execute(text("DROP TABLE IF EXISTS monitoring._stg_anomalies"))

    return len(out)


def run_detection(mode: str = "full", run_id: str | None = None) -> dict:
    settings = get_settings()
    engine = get_engine()
    run_ddl(engine)
    config = load_anomaly_config()
    run_id = run_id or str(uuid.uuid4())

    logger.info("Starting anomaly detection run_id=%s mode=%s", run_id, mode)
    txns = load_transactions(engine)
    if txns.empty:
        logger.warning("No transactions loaded; skipping detection")
        return {"run_id": run_id, "total": 0, "flagged": 0, "by_severity": {}}

    rule_df = detect_rule_based_anomalies(
        txns,
        config=config.get("rule_based"),
        full_config=config,
    )
    stat_df = detect_statistical_anomalies(txns, config=config.get("statistical"))
    ml_df = detect_ml_anomalies(
        txns, config=config.get("ml", {}).get("isolation_forest")
    )

    merged = _merge_results(rule_df, stat_df, ml_df)
    written = _write_anomalies(engine, merged, mode=mode)

    flagged = merged[merged["is_flagged"]]
    by_severity = (
        flagged["severity"].value_counts().to_dict() if not flagged.empty else {}
    )
    logger.info(
        "Anomaly detection complete: %s transactions requiring review (of %s)",
        written,
        len(txns),
    )
    for sev in ("Critical", "High", "Medium", "Low"):
        cnt = by_severity.get(sev, 0)
        if cnt:
            logger.info("  Severity %s: %s", sev, cnt)

    logger.info(
        "NOTE: Results labeled 'Potential anomaly' / 'Transaction requiring review' "
        "— analytical prototype only."
    )

    return {
        "run_id": run_id,
        "total": len(txns),
        "flagged": written,
        "by_severity": by_severity,
    }


def main(mode: str | None = None) -> dict:
    settings = get_settings()
    return run_detection(mode=mode or settings.pipeline_mode)


if __name__ == "__main__":
    import sys

    m = sys.argv[1] if len(sys.argv) > 1 else None
    main(m)

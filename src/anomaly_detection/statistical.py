"""
Statistical anomaly detection using per-customer z-scores.

Configurable threshold from config.settings AnomalySettings.zscore_threshold
and anomaly_config.yaml statistical section.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from config.settings import get_settings
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


def detect_statistical_anomalies(
    df: pd.DataFrame,
    config: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """
    Compute z-score per customer and flag statistical outliers.

    Returns transaction_id, z_score, statistical_flag, statistical_reason.
    """
    if df.empty:
        return pd.DataFrame(
            columns=[
                "transaction_id",
                "z_score",
                "statistical_flag",
                "statistical_reason",
            ]
        )

    settings = get_settings()
    min_history = 5
    threshold = settings.anomaly.zscore_threshold
    if config:
        min_history = int(config.get("min_history_transactions", min_history))
        threshold = float(config.get("zscore_threshold", threshold))

    work = df.copy()
    work["amount"] = pd.to_numeric(work["amount"], errors="coerce")
    work = work.dropna(subset=["transaction_id", "amount", "customer_id"])

    stats = (
        work.groupby("customer_id")["amount"]
        .agg(mean_amt="mean", std_amt="std", cnt="count")
        .reset_index()
    )
    merged = work.merge(stats, on="customer_id", how="left")
    merged["std_amt"] = merged["std_amt"].fillna(0).replace(0, np.nan)
    merged["z_score"] = (merged["amount"] - merged["mean_amt"]) / merged["std_amt"]
    merged["z_score"] = merged["z_score"].fillna(0)

    merged["statistical_flag"] = (
        (merged["cnt"] >= min_history) & (merged["z_score"].abs() >= threshold)
    )
    merged["statistical_reason"] = merged.apply(
        lambda r: (
            f"Potential anomaly: statistical z-score {r['z_score']:.2f} "
            f"(threshold={threshold})"
            if r["statistical_flag"]
            else None
        ),
        axis=1,
    )

    flagged = int(merged["statistical_flag"].sum())
    logger.info(
        "Statistical detection: %s/%s transactions exceed z-score threshold %.2f",
        flagged,
        len(merged),
        threshold,
    )

    return merged[
        ["transaction_id", "z_score", "statistical_flag", "statistical_reason"]
    ].drop_duplicates(subset=["transaction_id"])

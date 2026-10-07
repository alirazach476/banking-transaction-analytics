"""
Optional Isolation Forest anomaly detection.

Features: amount, hour_of_day, transactions_last_1_hour,
amount_vs_customer_avg, day_of_week.

Handles small datasets gracefully (skips or uses reduced estimators).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from config.settings import get_settings
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)

FEATURES = [
    "amount",
    "hour_of_day",
    "transactions_last_1_hour",
    "amount_vs_customer_avg",
    "day_of_week",
]

MIN_SAMPLES = 50


def _build_features(df: pd.DataFrame) -> pd.DataFrame:
    work = df.copy()
    work["amount"] = pd.to_numeric(work["amount"], errors="coerce")
    work["transaction_timestamp"] = pd.to_datetime(
        work["transaction_timestamp"], errors="coerce"
    )
    work = work.dropna(subset=["transaction_id", "amount", "transaction_timestamp"])
    work = work.sort_values(["customer_id", "transaction_timestamp"]).reset_index(drop=True)
    work["hour_of_day"] = work["transaction_timestamp"].dt.hour.astype(float)
    work["day_of_week"] = work["transaction_timestamp"].dt.dayofweek.astype(float)

    cust_avg = work.groupby("customer_id")["amount"].transform("mean")
    work["amount_vs_customer_avg"] = np.where(
        cust_avg > 0, work["amount"] / cust_avg, 1.0
    )

    counts = []
    for _, grp in work.groupby("customer_id"):
        ts = grp["transaction_timestamp"].values
        n = len(ts)
        c = np.zeros(n, dtype=float)
        for i in range(n):
            window_start = ts[i] - np.timedelta64(1, "h")
            c[i] = float(((ts >= window_start) & (ts <= ts[i])).sum())
        counts.extend(c)
    work["transactions_last_1_hour"] = counts
    return work


def detect_ml_anomalies(
    df: pd.DataFrame,
    config: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """
    Run IsolationForest when enough data; otherwise return neutral scores.

    Returns transaction_id, anomaly_score, ml_anomaly_flag.
    """
    empty_cols = ["transaction_id", "anomaly_score", "ml_anomaly_flag"]
    if df.empty:
        return pd.DataFrame(columns=empty_cols)

    settings = get_settings()
    ml_cfg = config or {}
    enabled = ml_cfg.get("enabled", True)
    contamination = float(
        ml_cfg.get("contamination", settings.anomaly.isolation_forest_contamination)
    )
    n_estimators = int(ml_cfg.get("n_estimators", 100))
    random_state = int(ml_cfg.get("random_state", settings.random_seed))

    work = _build_features(df)
    result = work[["transaction_id"]].copy()
    result["anomaly_score"] = 0.0
    result["ml_anomaly_flag"] = False

    if not enabled or len(work) < MIN_SAMPLES:
        logger.warning(
            "IsolationForest skipped: enabled=%s, rows=%s (min=%s)",
            enabled,
            len(work),
            MIN_SAMPLES,
        )
        return result

    try:
        from sklearn.ensemble import IsolationForest
    except ImportError:
        logger.warning("scikit-learn not available; skipping IsolationForest")
        return result

    X = work[FEATURES].fillna(0).values
    n_est = min(n_estimators, max(10, len(work) // 5))
    cont = min(max(contamination, 0.001), 0.5)

    try:
        model = IsolationForest(
            n_estimators=n_est,
            contamination=cont,
            random_state=random_state,
            n_jobs=-1,
        )
        model.fit(X)
        raw_scores = -model.score_samples(X)
        preds = model.predict(X)
        result["anomaly_score"] = raw_scores
        result["ml_anomaly_flag"] = preds == -1
        logger.info(
            "IsolationForest: %s/%s flagged (contamination=%.3f, estimators=%s)",
            int(result["ml_anomaly_flag"].sum()),
            len(result),
            cont,
            n_est,
        )
    except Exception as exc:
        logger.warning("IsolationForest failed gracefully: %s", exc)

    return result

"""
Rule-based transaction anomaly detection.

Labels results as "Potential anomaly" / "Transaction requiring review" —
this is an analytical prototype, NOT a production fraud engine.
"""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from config.settings import get_settings
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)

REVIEW_LABEL = "Transaction requiring review"


def _load_rule_config(config: dict[str, Any] | None) -> dict[str, Any]:
    if config is None:
        import yaml

        path = get_settings().project_root / "config" / "anomaly_config.yaml"
        with open(path, encoding="utf-8") as f:
            full = yaml.safe_load(f)
        config = full.get("rule_based", {})
    settings = get_settings()
    return {
        "high_amount_zscore": float(
            config.get("high_amount_zscore", settings.anomaly.zscore_threshold)
        ),
        "high_amount_multiplier": float(
            config.get("high_amount_multiplier", settings.anomaly.high_amount_multiplier)
        ),
        "high_frequency_daily_count": int(config.get("high_frequency_daily_count", 20)),
        "rapid_window_minutes": int(
            config.get("rapid_window_minutes", settings.anomaly.rapid_window_minutes)
        ),
        "rapid_count": int(config.get("rapid_count", settings.anomaly.rapid_count_threshold)),
        "night_hours": list(config.get("night_hours", [0, 1, 2, 3, 4, 5])),
        "night_min_amount": float(config.get("night_min_amount", 1000)),
        "failure_streak": int(config.get("failure_streak", 3)),
        "behavior_change_multiplier": float(config.get("behavior_change_multiplier", 10.0)),
        "severity_thresholds": config.get("_severity_thresholds", {"low": 1, "medium": 2, "high": 3, "critical": 4}),
        "weights": config.get("_weights", {}),
    }


def _prepare_transactions(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and enrich transaction dataframe for rule evaluation."""
    out = df.copy()
    out["amount"] = pd.to_numeric(out["amount"], errors="coerce")
    out["transaction_timestamp"] = pd.to_datetime(
        out["transaction_timestamp"], errors="coerce"
    )
    out["hour_of_day"] = out["transaction_timestamp"].dt.hour
    out["customer_id"] = out["customer_id"].astype(str)
    out = out.dropna(subset=["transaction_id", "amount", "transaction_timestamp"])
    out = out.sort_values(["customer_id", "transaction_timestamp"]).reset_index(drop=True)
    return out


def _customer_amount_stats(df: pd.DataFrame) -> pd.DataFrame:
    stats = (
        df.groupby("customer_id")["amount"]
        .agg(customer_avg="mean", customer_std="std", customer_count="count")
        .reset_index()
    )
    stats["customer_std"] = stats["customer_std"].fillna(0).replace(0, np.nan)
    return stats


def _count_last_24h(df: pd.DataFrame) -> pd.Series:
    counts = []
    for cust, grp in df.groupby("customer_id"):
        ts = grp["transaction_timestamp"].values
        n = len(ts)
        c = np.zeros(n, dtype=int)
        for i in range(n):
            window_start = ts[i] - np.timedelta64(24, "h")
            c[i] = int(((ts >= window_start) & (ts <= ts[i])).sum())
        counts.extend(c)
    return pd.Series(counts, index=df.index)


def _count_rapid_window(df: pd.DataFrame, window_minutes: int) -> pd.Series:
    delta = np.timedelta64(window_minutes, "m")
    counts = []
    for cust, grp in df.groupby("customer_id"):
        ts = grp["transaction_timestamp"].values
        n = len(ts)
        c = np.zeros(n, dtype=int)
        for i in range(n):
            window_start = ts[i] - delta
            c[i] = int(((ts >= window_start) & (ts <= ts[i])).sum())
        counts.extend(c)
    return pd.Series(counts, index=df.index)


def _recent_failures(df: pd.DataFrame, streak: int) -> pd.Series:
    status = df.get("transaction_status", pd.Series("", index=df.index)).astype(str).str.lower()
    is_fail = status.str.contains("fail", na=False)
    failures = []
    for cust, grp in df.groupby("customer_id"):
        fail_flags = is_fail.loc[grp.index].values
        n = len(fail_flags)
        recent = np.zeros(n, dtype=int)
        streak_count = 0
        for i in range(n):
            if fail_flags[i]:
                streak_count += 1
            else:
                streak_count = 0
            recent[i] = streak_count
        failures.extend(recent)
    return pd.Series(failures, index=df.index) >= streak


def _recent_avg_amount(df: pd.DataFrame, window: int = 10) -> pd.Series:
    avgs = []
    for cust, grp in df.groupby("customer_id"):
        amounts = grp["amount"].values
        n = len(amounts)
        ra = np.full(n, np.nan)
        for i in range(n):
            start = max(0, i - window)
            if i > start:
                ra[i] = amounts[start:i].mean()
        avgs.extend(ra)
    return pd.Series(avgs, index=df.index)


def _severity_from_score(score: float, thresholds: dict[str, int]) -> str:
    if score >= thresholds.get("critical", 4):
        return "Critical"
    if score >= thresholds.get("high", 3):
        return "High"
    if score >= thresholds.get("medium", 2):
        return "Medium"
    if score >= thresholds.get("low", 1):
        return "Low"
    return "Low"


def detect_rule_based_anomalies(
    df: pd.DataFrame,
    config: dict[str, Any] | None = None,
    full_config: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """
    Run rule-based anomaly checks on transactions.

    Returns dataframe with transaction_id, rule_based_score, reasons (list),
    severity, z_score, and review flags.
    """
    if df.empty:
        return pd.DataFrame(
            columns=[
                "transaction_id",
                "customer_id",
                "account_id",
                "transaction_timestamp",
                "amount",
                "rule_based_score",
                "reasons",
                "severity",
                "z_score",
                "is_potential_anomaly",
                "review_label",
            ]
        )

    cfg = _load_rule_config(config)
    if full_config:
        cfg["severity_thresholds"] = full_config.get("severity_thresholds", cfg["severity_thresholds"])
        weights = {}
        for name, meta in full_config.get("anomaly_types", {}).items():
            if meta.get("enabled", True):
                weights[name] = float(meta.get("weight", 0.1))
        cfg["weights"] = weights

    weights = cfg["weights"] or {
        "high_amount": 0.25,
        "high_frequency": 0.15,
        "rapid_transactions": 0.15,
        "night_activity": 0.10,
        "multiple_failures": 0.15,
        "sudden_behavior_change": 0.10,
    }

    prepared = _prepare_transactions(df)
    stats = _customer_amount_stats(prepared)
    prepared = prepared.merge(stats, on="customer_id", how="left")
    prepared["customer_std"] = prepared["customer_std"].fillna(0).replace(0, np.nan)
    prepared["z_score"] = (
        (prepared["amount"] - prepared["customer_avg"]) / prepared["customer_std"]
    ).fillna(0)
    prepared["transactions_last_24_hours"] = _count_last_24h(prepared)
    prepared["rapid_window_count"] = _count_rapid_window(
        prepared, cfg["rapid_window_minutes"]
    )
    prepared["recent_failure_streak"] = _recent_failures(prepared, cfg["failure_streak"])
    prepared["recent_avg_amount"] = _recent_avg_amount(prepared)

    reasons_col: list[list[str]] = []
    scores: list[float] = []

    for _, row in prepared.iterrows():
        reasons: list[str] = []
        score = 0.0

        if (
            abs(row["z_score"]) >= cfg["high_amount_zscore"]
            or row["amount"] > row["customer_avg"] * cfg["high_amount_multiplier"]
        ):
            reasons.append(
                f"Potential anomaly: high_amount (z={row['z_score']:.2f}, "
                f"amount={row['amount']:.2f} vs avg={row['customer_avg']:.2f})"
            )
            score += weights.get("high_amount", 0.25)

        if row["transactions_last_24_hours"] >= cfg["high_frequency_daily_count"]:
            reasons.append(
                f"Potential anomaly: high_frequency "
                f"({int(row['transactions_last_24_hours'])} txns in 24h)"
            )
            score += weights.get("high_frequency", 0.15)

        if row["rapid_window_count"] >= cfg["rapid_count"]:
            reasons.append(
                f"Potential anomaly: rapid_transactions "
                f"({int(row['rapid_window_count'])} in {cfg['rapid_window_minutes']}min)"
            )
            score += weights.get("rapid_transactions", 0.15)

        if (
            int(row["hour_of_day"]) in cfg["night_hours"]
            and row["amount"] >= cfg["night_min_amount"]
        ):
            reasons.append(
                f"Potential anomaly: night_activity "
                f"(hour={int(row['hour_of_day'])}, amount={row['amount']:.2f})"
            )
            score += weights.get("night_activity", 0.10)

        if row["recent_failure_streak"]:
            reasons.append("Potential anomaly: multiple_failures (recent failure streak)")
            score += weights.get("multiple_failures", 0.15)

        recent_avg = row["recent_avg_amount"]
        if (
            pd.notna(recent_avg)
            and recent_avg > 0
            and row["amount"] >= recent_avg * cfg["behavior_change_multiplier"]
        ):
            reasons.append(
                f"Potential anomaly: sudden_behavior_change "
                f"(amount={row['amount']:.2f} vs recent_avg={recent_avg:.2f})"
            )
            score += weights.get("sudden_behavior_change", 0.10)

        reasons_col.append(reasons)
        scores.append(score)

    prepared["reasons"] = reasons_col
    prepared["rule_based_score"] = scores
    prepared["severity"] = [
        _severity_from_score(s, cfg["severity_thresholds"]) if r else "Low"
        for s, r in zip(scores, reasons_col)
    ]
    prepared["is_potential_anomaly"] = [len(r) > 0 for r in reasons_col]
    prepared["review_label"] = [
        REVIEW_LABEL if r else None for r in reasons_col
    ]

    flagged = sum(prepared["is_potential_anomaly"])
    logger.info(
        "Rule-based detection: %s/%s transactions flagged as potential anomalies",
        flagged,
        len(prepared),
    )

    return prepared[
        [
            "transaction_id",
            "customer_id",
            "account_id",
            "transaction_timestamp",
            "amount",
            "rule_based_score",
            "reasons",
            "severity",
            "z_score",
            "is_potential_anomaly",
            "review_label",
        ]
    ]

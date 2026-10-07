"""Tests for anomaly detection modules."""

from __future__ import annotations

import pandas as pd

from src.anomaly_detection.rule_based import detect_rule_based_anomalies


def test_high_amount_detection(sample_transactions, high_amount_config):
    result = detect_rule_based_anomalies(
        sample_transactions,
        config=high_amount_config,
    )
    assert not result.empty
    outlier = result[result["transaction_id"] == "TXN-TEST-OUTLIER"]
    assert len(outlier) == 1
    row = outlier.iloc[0]
    assert row["is_potential_anomaly"]
    assert any("high_amount" in r for r in row["reasons"])
    assert row["rule_based_score"] > 0
    assert row["review_label"] == "Transaction requiring review"


def test_no_false_positives_on_normal_batch(sample_transactions, high_amount_config):
    normal = sample_transactions[sample_transactions["transaction_id"] != "TXN-TEST-OUTLIER"]
    result = detect_rule_based_anomalies(normal, config=high_amount_config)
    flagged = result[result["is_potential_anomaly"]]
    assert len(flagged) == 0


def test_empty_dataframe_returns_schema():
    result = detect_rule_based_anomalies(pd.DataFrame())
    assert list(result.columns) == [
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

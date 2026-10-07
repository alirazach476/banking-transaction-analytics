"""Tests for validation helpers and status standardization."""

from __future__ import annotations

import pandas as pd

from src.transformation.status_maps import normalize_status, standardize_status_column
from src.validation.checks import (
    evaluate_count_check,
    evaluate_reconciliation,
    standardize_check_status,
)


def test_evaluate_count_check_pass():
    status, expected, actual = evaluate_count_check(0, expected_zero=True)
    assert status == "PASS"
    assert expected == "0"
    assert actual == "0"


def test_evaluate_count_check_fail():
    status, _, actual = evaluate_count_check(3, expected_zero=True)
    assert status == "FAIL"
    assert actual == "3"


def test_evaluate_count_check_volume():
    status, expected, _ = evaluate_count_check(100, expected_zero=False)
    assert status == "PASS"
    assert expected == ">0"


def test_evaluate_reconciliation_pass():
    status, diff = evaluate_reconciliation(1000.0, 1000.0, tolerance=0.01)
    assert status == "PASS"
    assert diff == 0.0


def test_evaluate_reconciliation_fail():
    status, diff = evaluate_reconciliation(1000.0, 900.0, tolerance=0.01)
    assert status == "FAIL"
    assert diff == 100.0


def test_standardize_check_status():
    assert standardize_check_status("pass") == "PASS"
    assert standardize_check_status(" Fail ") == "FAIL"
    assert standardize_check_status("warning") == "WARNING"


def test_normalize_status_variants():
    assert normalize_status("completed") == "Completed"
    assert normalize_status("FAILED") == "Failed"
    assert normalize_status("ACTIVE") == "Active"
    assert normalize_status(None) is None


def test_standardize_status_column():
    series = pd.Series(["completed", "PENDING", "unknown_status"])
    out = standardize_status_column(series)
    assert out.iloc[0] == "Completed"
    assert out.iloc[1] == "Pending"
    assert out.iloc[2] == "Unknown_Status"

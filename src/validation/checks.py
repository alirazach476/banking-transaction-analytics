"""
Reusable data quality check helpers for validation and tests.
"""

from __future__ import annotations


def evaluate_count_check(actual: int, expected_zero: bool = True) -> tuple[str, str, str]:
    """
    Return (status, expected_label, actual_label) for count-based checks.
    """
    if expected_zero:
        status = "PASS" if actual == 0 else "FAIL"
        return status, "0", str(actual)
    status = "PASS" if actual > 0 else "FAIL"
    return status, ">0", str(actual)


def evaluate_reconciliation(
    source_value: float | None,
    warehouse_value: float | None,
    tolerance: float = 0.01,
) -> tuple[str, float | None]:
    """
    Compare source vs warehouse metric. Returns (status, difference).
    """
    if source_value is None or warehouse_value is None:
        return "UNKNOWN", None
    diff = abs(float(source_value) - float(warehouse_value))
    if diff <= tolerance:
        return "PASS", diff
    return "FAIL", diff


def standardize_check_status(raw: str) -> str:
    """Normalize DQ/reconciliation status strings."""
    mapping = {
        "pass": "PASS",
        "fail": "FAIL",
        "warning": "WARNING",
        "unknown": "UNKNOWN",
        "success": "SUCCESS",
        "running": "RUNNING",
    }
    return mapping.get(raw.strip().lower(), raw.upper())

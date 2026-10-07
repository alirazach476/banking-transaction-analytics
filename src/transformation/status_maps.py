"""
Status standardization maps for NovaBank source systems.

Source CSVs intentionally contain variant spellings/casing; these maps
normalize to canonical values used in validation and optional Python transforms.
"""

from __future__ import annotations

import pandas as pd

# Canonical status -> known source variants (lowercase keys for lookup)
STATUS_MAP: dict[str, list[str]] = {
    "Completed": ["completed", "complete", "COMPLETED", "Complete"],
    "Pending": ["pending", "PENDING"],
    "Failed": ["failed", "FAILED", "fail", "Fail"],
    "Reversed": ["reversed", "REVERSED"],
    "Active": ["active", "ACTIVE"],
    "Inactive": ["inactive", "INACTIVE"],
    "Suspended": ["suspended", "SUSPENDED"],
    "Closed": ["closed", "CLOSED"],
    "Frozen": ["frozen", "FROZEN"],
    "Blocked": ["blocked", "BLOCKED"],
    "Expired": ["expired", "EXPIRED"],
    "Open": ["open", "OPEN"],
    "Renovating": ["renovating", "RENOVATING"],
}

# Reverse lookup: any variant -> canonical
_VARIANT_TO_CANONICAL: dict[str, str] = {}
for canonical, variants in STATUS_MAP.items():
    _VARIANT_TO_CANONICAL[canonical.lower()] = canonical
    for v in variants:
        _VARIANT_TO_CANONICAL[v.lower()] = canonical


def normalize_status(value: str | None) -> str | None:
    """Return canonical status or original trimmed value if unknown."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = str(value).strip()
    if not s:
        return None
    return _VARIANT_TO_CANONICAL.get(s.lower(), s.title())


def standardize_status_column(series: pd.Series) -> pd.Series:
    """Apply normalize_status to a pandas Series."""
    return series.map(normalize_status)

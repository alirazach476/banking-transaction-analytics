"""
Controlled, labelled data-quality defects for the DIRTY payment feeds.

Each affected row receives a label in ``dq_defect`` (multiple labels joined by ';').
Clean copies are never passed through this module. Vectorised; rates are
fractions of rows. The defect catalogue is documented in docs/DATA_ENGINEERING.md.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.payments.config import DefectRates

DEFECT_LABELS = [
    "duplicate_record", "missing_value", "invalid_foreign_key",
    "inconsistent_capitalization", "invalid_timestamp", "invalid_currency",
    "incorrect_status",
]


def _tag(df: pd.DataFrame, idx: np.ndarray, label: str) -> None:
    cur = df["dq_defect"].to_numpy(dtype=object).copy()
    cur[idx] = np.where(cur[idx] == "", label, cur[idx] + ";" + label)
    df["dq_defect"] = cur


def _pick(rng: np.random.Generator, n: int, rate: float) -> np.ndarray:
    k = int(round(n * rate))
    return rng.choice(n, size=min(k, n), replace=False) if k > 0 else np.array([], dtype=int)


def _set(out: pd.DataFrame, col: str, idx: np.ndarray, values) -> None:
    vals = out[col].astype(object).to_numpy().copy()
    vals[idx] = values
    out[col] = vals


def inject_defects(
    df: pd.DataFrame,
    rates: DefectRates,
    rng: np.random.Generator,
    *,
    status_col: str | None = None,
    fk_cols: list[str] | None = None,
    ts_cols: list[str] | None = None,
    currency_cols: list[str] | None = None,
    nullable_cols: list[str] | None = None,
    case_cols: list[str] | None = None,
) -> pd.DataFrame:
    """Return a dirty copy of ``df`` plus a ``dq_defect`` label column."""
    out = df.copy().reset_index(drop=True)
    n = len(out)
    out["dq_defect"] = ""
    if n == 0:
        return out
    for c in ts_cols or []:
        out[c] = pd.to_datetime(out[c]).dt.strftime("%Y-%m-%d %H:%M:%S")

    for col in case_cols or []:
        idx = _pick(rng, n, rates.inconsistent_capitalization)
        if len(idx):
            cur = out[col].astype(str).to_numpy().astype("U64")[idx]
            flip = rng.random(len(idx)) < 0.5
            _set(out, col, idx, np.where(flip, np.char.lower(cur), np.char.upper(cur)))
            _tag(out, idx, "inconsistent_capitalization")
    if status_col:
        idx = _pick(rng, n, rates.incorrect_status)
        if len(idx):
            _set(out, status_col, idx, rng.choice(["APPROVD", "UNKNOWN", "DONE", "N/A"], len(idx)))
            _tag(out, idx, "incorrect_status")
    for col in ts_cols or []:
        idx = _pick(rng, n, rates.invalid_timestamp)
        if len(idx):
            _set(out, col, idx, rng.choice(["2024-13-45 99:00:00", "not-a-date", "0000-00-00 00:00:00"], len(idx)))
            _tag(out, idx, "invalid_timestamp")
    for col in currency_cols or []:
        idx = _pick(rng, n, rates.invalid_currency)
        if len(idx):
            _set(out, col, idx, rng.choice(["US$", "XXX", "usd1", "???"], len(idx)))
            _tag(out, idx, "invalid_currency")
    for col in fk_cols or []:
        idx = _pick(rng, n, rates.invalid_foreign_key)
        if len(idx):
            _set(out, col, idx, "INVALID-REF")
            _tag(out, idx, "invalid_foreign_key")
    for col in nullable_cols or []:
        idx = _pick(rng, n, rates.missing_value)
        if len(idx):
            _set(out, col, idx, None)
            _tag(out, idx, "missing_value")
    idx = _pick(rng, n, rates.duplicate_record)
    if len(idx):
        dups = out.iloc[idx].copy()
        dups["dq_defect"] = np.where(dups["dq_defect"] == "", "duplicate_record",
                                     dups["dq_defect"] + ";duplicate_record")
        out = pd.concat([out, dups], ignore_index=True)
    return out

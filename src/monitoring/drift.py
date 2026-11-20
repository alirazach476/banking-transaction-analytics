"""Drift and fairness helpers (pure functions, unit-tested)."""
from __future__ import annotations
import numpy as np
import pandas as pd


def psi(expected, actual, bins: int = 10, eps: float = 1e-6) -> float:
    """Population Stability Index using quantile bins of the *expected* (reference) sample.
    Rule of thumb: <0.1 stable, 0.1-0.25 moderate shift, >0.25 major shift."""
    e = pd.Series(expected).dropna().to_numpy(float)
    a = pd.Series(actual).dropna().to_numpy(float)
    if len(e) == 0 or len(a) == 0:
        return float("nan")
    edges = np.unique(np.quantile(e, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:  # near-constant / binary feature
        edges = np.array([-np.inf, np.median(e), np.inf]) if np.ptp(e) else np.array([-np.inf, np.inf])
    else:
        edges[0], edges[-1] = -np.inf, np.inf
    pe = np.histogram(e, edges)[0] / len(e) + eps
    pa = np.histogram(a, edges)[0] / len(a) + eps
    return float(np.sum((pa - pe) * np.log(pa / pe)))


def group_rates(df: pd.DataFrame, group: str, y: str, flag: str) -> pd.DataFrame:
    """Per-group base rate, flag (positive prediction) rate, TPR and FPR, with group size."""
    rows = []
    for k, g in df.groupby(group):
        pos, neg = g[g[y] == 1], g[g[y] == 0]
        rows.append({group: k, "n": len(g), "base_rate": g[y].mean(), "flag_rate": g[flag].mean(),
                     "tpr": pos[flag].mean() if len(pos) else np.nan, "fpr": neg[flag].mean() if len(neg) else np.nan})
    return pd.DataFrame(rows)

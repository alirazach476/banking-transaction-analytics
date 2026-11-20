"""Synthetic FX rate series (labelled SYNTHETIC; real rates come from Module B)."""

from __future__ import annotations

import numpy as np
import pandas as pd

from src.payments.constants import FX_ANCHORS, SETTLEMENT_CURRENCY


def generate_fx_rates(seed: int, start: str, end: str) -> pd.DataFrame:
    """Daily USD-per-unit rates as a seeded log random walk around fixed anchors."""
    days = pd.date_range(start, end, freq="D")
    rng = np.random.default_rng([seed, 9001])
    frames = []
    for ccy, (anchor, vol) in FX_ANCHORS.items():
        if vol == 0:
            rate = np.full(len(days), anchor)
        else:
            walk = np.cumsum(rng.normal(0, vol, size=len(days)))
            walk -= walk.mean()  # keep the series centred on the anchor
            rate = anchor * np.exp(walk)
        frames.append(
            pd.DataFrame(
                {
                    "rate_date": days.strftime("%Y-%m-%d"),
                    "base_currency": ccy,
                    "quote_currency": SETTLEMENT_CURRENCY,
                    "rate": np.round(rate, 6),
                    "source": "SYNTHETIC",
                }
            )
        )
    return pd.concat(frames, ignore_index=True)

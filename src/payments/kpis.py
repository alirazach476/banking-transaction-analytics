"""
Payment KPI calculations with explicit denominators (definitions: docs/BUSINESS_METRICS.md).

Unit of analysis is the *payment* (unique ``payment_id``), never the lifecycle event.
Inputs are the ``transactions`` and ``events`` frames produced by the generator
(or the cleaned warehouse equivalents).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def _safe_div(a: float, b: float) -> float | None:
    return float(a) / float(b) if b else None


def payment_outcomes(events: pd.DataFrame) -> pd.DataFrame:
    """One row per payment_id with boolean lifecycle flags and first-event timestamps."""
    ev = events.drop_duplicates("event_id") if "event_id" in events else events
    g = ev.groupby("payment_id")
    et = ev.pivot_table(index="payment_id", columns="event_type", values="event_ts", aggfunc="min")
    for c in ["AUTH_RESPONSE", "CLEARING", "SETTLEMENT", "REVERSAL", "REFUND", "CHARGEBACK"]:
        if c not in et:
            et[c] = pd.NaT
    resp = ev[ev["event_type"] == "AUTH_RESPONSE"].drop_duplicates("payment_id").set_index("payment_id")
    out = pd.DataFrame(index=et.index)
    out["authorized"] = resp["event_status"].reindex(out.index).eq("APPROVED")
    out["declined"] = resp["event_status"].reindex(out.index).eq("DECLINED")
    out["response_ms"] = resp["response_ms"].reindex(out.index)
    out["cleared"] = et["CLEARING"].notna()
    out["settled"] = et["SETTLEMENT"].notna()
    out["reversed"] = et["REVERSAL"].notna()
    out["refunded"] = et["REFUND"].notna()
    out["charged_back"] = et["CHARGEBACK"].notna()
    return out.reset_index()


def kpi_summary(events: pd.DataFrame) -> dict:
    """Headline KPIs.

    * approval_rate      = approved / (approved + declined) over payments WITH an AUTH_RESPONSE
    * decline_rate       = 1 - approval_rate (same denominator)
    * completion_rate    = cleared / approved
    * settlement_rate    = settled / cleared
    * reversal_rate      = reversed / approved
    * refund_rate        = refunded / settled
    * chargeback_rate    = charged back / settled
    """
    o = payment_outcomes(events)
    responded = int(o["authorized"].sum() + o["declined"].sum())
    approved = int(o["authorized"].sum())
    cleared = int(o["cleared"].sum())
    settled = int(o["settled"].sum())
    return {
        "payments": int(len(o)),
        "payments_with_response": responded,
        "approved": approved,
        "declined": int(o["declined"].sum()),
        "approval_rate": _safe_div(approved, responded),
        "decline_rate": _safe_div(o["declined"].sum(), responded),
        "completion_rate": _safe_div(cleared, approved),
        "settlement_rate": _safe_div(settled, cleared),
        "reversal_rate": _safe_div(o["reversed"].sum(), approved),
        "refund_rate": _safe_div(o["refunded"].sum(), settled),
        "chargeback_rate": _safe_div(o["charged_back"].sum(), settled),
        "avg_processing_ms": float(o["response_ms"].mean()) if o["response_ms"].notna().any() else None,
    }


def rate_by(transactions: pd.DataFrame, events: pd.DataFrame, by: str) -> pd.DataFrame:
    """Approval rate per dimension value (payment-level), with attempt counts."""
    o = payment_outcomes(events)
    m = transactions[["payment_id", by]].drop_duplicates("payment_id").merge(o, on="payment_id")
    m = m[m["authorized"] | m["declined"]]
    g = m.groupby(by).agg(attempts=("payment_id", "size"), approved=("authorized", "sum"))
    g["approval_rate"] = g["approved"] / g["attempts"]
    return g.reset_index().sort_values("attempts", ascending=False)

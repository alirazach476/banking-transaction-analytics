"""
Settlement reconciliation: expected vs actual settlement per cleared payment.

Definitions (see docs/BUSINESS_METRICS.md):
  * Population  = payments with a CLEARING event (one clearing per payment).
  * Expected    = round(clearing_amount * FX(clearing currency -> settlement ccy, clearing date), 2)
  * Actual      = settlement records for that payment_id.

Issue flags (non-exclusive) and a single ``primary_status`` chosen by priority:
  MISSING_SETTLEMENT > DUPLICATE_SETTLEMENT > CURRENCY_MISMATCH > AMOUNT_MISMATCH
  > LATE_SETTLEMENT > FX_RATE_MISSING > PENDING > MATCHED
  UNMATCHED_SETTLEMENT = settlement whose payment_id has no clearing record (reported separately).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.payments.constants import SETTLEMENT_CURRENCY


@dataclass
class ReconConfig:
    sla_days: int = 3
    amount_tolerance: float = 0.01
    settlement_currency: str = SETTLEMENT_CURRENCY
    as_of: pd.Timestamp | None = None  # default: latest timestamp seen


@dataclass
class ReconResult:
    detail: pd.DataFrame           # one row per cleared payment
    unmatched_settlements: pd.DataFrame
    summary: dict
    queue: pd.DataFrame            # investigation queue (issues only)


PRIORITY = [
    "MISSING_SETTLEMENT", "DUPLICATE_SETTLEMENT", "CURRENCY_MISMATCH",
    "AMOUNT_MISMATCH", "LATE_SETTLEMENT", "FX_RATE_MISSING", "PENDING", "MATCHED",
]


def _fx_lookup(clearing: pd.DataFrame, fx: pd.DataFrame, settle_ccy: str) -> np.ndarray:
    """Rate (settle_ccy per unit) on the clearing date; NaN if no rate on/before that date."""
    rates = fx[fx["quote_currency"] == settle_ccy].copy()
    rates["rate_date"] = pd.to_datetime(rates["rate_date"]).astype("datetime64[ns]")
    rates = rates.sort_values("rate_date")
    left = clearing[["payment_id", "currency", "clearing_date"]].copy()
    left["_ord"] = np.arange(len(left))
    left["clearing_date"] = left["clearing_date"].astype("datetime64[ns]")
    left = left.sort_values("clearing_date")
    merged = pd.merge_asof(left, rates[["rate_date", "base_currency", "rate"]],
                           left_on="clearing_date", right_on="rate_date",
                           left_by="currency", right_by="base_currency", direction="backward")
    merged = merged.sort_values("_ord")
    out = merged["rate"].to_numpy(dtype=float)
    out[(clearing["currency"].to_numpy() == settle_ccy)] = 1.0
    return out


def reconcile(clearing: pd.DataFrame, settlements: pd.DataFrame, fx: pd.DataFrame,
              cfg: ReconConfig | None = None) -> ReconResult:
    """Reconcile clearing records to settlements.

    ``clearing``: payment_id, clearing_ts, amount, currency
    ``settlements``: settlement_id, payment_id, settlement_ts, settlement_amount, settlement_currency
    ``fx``: rate_date, base_currency, quote_currency, rate
    """
    cfg = cfg or ReconConfig()
    clr = clearing.copy()
    clr["clearing_ts"] = pd.to_datetime(clr["clearing_ts"]).astype("datetime64[ns]")
    clr = clr.drop_duplicates("payment_id", keep="first").reset_index(drop=True)
    clr["clearing_date"] = clr["clearing_ts"].dt.normalize()
    stl = settlements.copy()
    stl["settlement_ts"] = pd.to_datetime(stl["settlement_ts"]).astype("datetime64[ns]")
    stl = stl.sort_values(["payment_id", "settlement_ts"])

    as_of = cfg.as_of
    if as_of is None:
        cands = [x for x in (clr["clearing_ts"].max() if len(clr) else None,
                             stl["settlement_ts"].max() if len(stl) else None) if x is not None and pd.notna(x)]
        as_of = max(cands) if cands else pd.Timestamp.now()

    if len(clr):
        rate = _fx_lookup(clr, fx, cfg.settlement_currency)
        clr["fx_rate"] = rate
        clr["expected_amount"] = np.round(clr["amount"].to_numpy(dtype=float) * rate, 2)
    else:
        clr["fx_rate"] = pd.Series(dtype=float)
        clr["expected_amount"] = pd.Series(dtype=float)

    agg = stl.groupby("payment_id").agg(
        settlement_count=("settlement_id", "size"),
        actual_amount_first=("settlement_amount", "first"),
        actual_amount_total=("settlement_amount", "sum"),
        actual_currency=("settlement_currency", "first"),
        first_settlement_ts=("settlement_ts", "min"),
    ).reset_index()
    d = clr.merge(agg, on="payment_id", how="left")
    d["settlement_count"] = d["settlement_count"].fillna(0).astype(int)
    due = d["clearing_ts"] + pd.Timedelta(days=cfg.sla_days)
    has = d["settlement_count"] > 0

    d["is_missing"] = ~has & (due < as_of)
    d["is_pending"] = ~has & ~d["is_missing"]
    d["is_duplicate"] = d["settlement_count"] > 1
    d["is_currency_mismatch"] = has & (d["actual_currency"] != cfg.settlement_currency)
    fx_missing = d["expected_amount"].isna()
    d["is_fx_missing"] = has & fx_missing
    amt_diff = (d["actual_amount_first"] - d["expected_amount"]).abs()
    # amount comparison only meaningful when currencies agree and a rate exists
    d["is_amount_mismatch"] = has & ~d["is_currency_mismatch"] & ~fx_missing & (amt_diff > cfg.amount_tolerance)
    lag = (d["first_settlement_ts"] - d["clearing_ts"]).dt.total_seconds() / 86400
    d["settlement_lag_days"] = lag
    d["is_late"] = has & (lag > cfg.sla_days)

    flags = {
        "MISSING_SETTLEMENT": "is_missing", "DUPLICATE_SETTLEMENT": "is_duplicate",
        "CURRENCY_MISMATCH": "is_currency_mismatch", "AMOUNT_MISMATCH": "is_amount_mismatch",
        "LATE_SETTLEMENT": "is_late", "FX_RATE_MISSING": "is_fx_missing", "PENDING": "is_pending",
    }
    status = np.full(len(d), "MATCHED", dtype=object)
    for name in reversed(PRIORITY[:-1]):  # lowest priority first so higher overwrites
        status[d[flags[name]].to_numpy()] = name
    d["primary_status"] = status
    d["amount_difference"] = np.where(
        d["is_duplicate"], d["actual_amount_total"] - d["expected_amount"],
        d["actual_amount_first"] - d["expected_amount"])
    d.loc[d["is_missing"], "amount_difference"] = -d.loc[d["is_missing"], "expected_amount"]
    exp = d["expected_amount"].fillna(0.0)
    # amount at risk (settlement currency): missing/late/currency-mismatch -> full expected amount;
    # duplicate/amount mismatch -> the over/under-payment; unknown FX -> 0 (cannot be valued)
    d["amount_at_risk"] = np.select(
        [d["primary_status"].isin(["MISSING_SETTLEMENT", "LATE_SETTLEMENT", "CURRENCY_MISMATCH"]),
         d["primary_status"].isin(["DUPLICATE_SETTLEMENT", "AMOUNT_MISMATCH"])],
        [exp, d["amount_difference"].abs().fillna(0.0)], default=0.0)

    cleared_ids = set(clr["payment_id"])
    um = stl[~stl["payment_id"].isin(cleared_ids)].drop_duplicates("settlement_id").copy()
    um["primary_status"] = "UNMATCHED_SETTLEMENT"
    um["amount_at_risk"] = um["settlement_amount"].abs()

    counts = d["primary_status"].value_counts().to_dict()
    total = len(d)
    summary = {
        "as_of": str(as_of), "cleared_payments": total,
        "matched": int(counts.get("MATCHED", 0)),
        "pending": int(counts.get("PENDING", 0)),
        "missing": int(counts.get("MISSING_SETTLEMENT", 0)),
        "duplicate": int(counts.get("DUPLICATE_SETTLEMENT", 0)),
        "amount_mismatch": int(counts.get("AMOUNT_MISMATCH", 0)),
        "currency_mismatch": int(counts.get("CURRENCY_MISMATCH", 0)),
        "late": int(counts.get("LATE_SETTLEMENT", 0)),
        "fx_rate_missing": int(counts.get("FX_RATE_MISSING", 0)),
        "unmatched_settlements": int(len(um)),
        # settlement success = matched / (cleared payments that are due, i.e. not pending)
        "settlement_success_rate": (round(counts.get("MATCHED", 0) / (total - counts.get("PENDING", 0)), 6)
                                    if total - counts.get("PENDING", 0) > 0 else None),
        "amount_at_risk": float(d["amount_at_risk"].sum() + um["amount_at_risk"].sum()),
    }

    issues = d[~d["primary_status"].isin(["MATCHED", "PENDING"])]
    q1 = pd.DataFrame({
        "payment_id": issues["payment_id"], "settlement_id": "", "issue_type": issues["primary_status"],
        "amount_at_risk": pd.to_numeric(issues["amount_at_risk"], errors="coerce").astype(float).round(2), "currency": cfg.settlement_currency,
        "issue_flags": issues[[v for v in flags.values()]].apply(
            lambda r: ",".join(k for k, v in zip(flags.keys(), r) if v), axis=1) if len(issues) else "",
    })
    q2 = pd.DataFrame({
        "payment_id": um["payment_id"], "settlement_id": um["settlement_id"], "issue_type": "UNMATCHED_SETTLEMENT",
        "amount_at_risk": um["amount_at_risk"].round(2), "currency": um["settlement_currency"],
        "issue_flags": "UNMATCHED_SETTLEMENT",
    })
    q = pd.concat([q1, q2], ignore_index=True)
    sev_w = {"DUPLICATE_SETTLEMENT": 3, "CURRENCY_MISMATCH": 3, "MISSING_SETTLEMENT": 3,
             "UNMATCHED_SETTLEMENT": 2, "AMOUNT_MISMATCH": 2, "LATE_SETTLEMENT": 1, "FX_RATE_MISSING": 1}
    q["priority"] = np.where((q["amount_at_risk"] >= 1000) | (q["issue_type"].map(sev_w).fillna(1) >= 3), "HIGH",
                             np.where(q["amount_at_risk"] >= 100, "MEDIUM", "LOW"))
    q["status"] = "OPEN"
    q = q.sort_values(["amount_at_risk"], ascending=False).reset_index(drop=True)
    q.insert(0, "queue_id", np.arange(1, len(q) + 1))
    return ReconResult(detail=d, unmatched_settlements=um, summary=summary, queue=q)

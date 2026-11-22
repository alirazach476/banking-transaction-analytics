from __future__ import annotations

import os

from fastapi import APIRouter

from .common import cached, one, q

router = APIRouter(tags=["meta"])

DEFINITIONS = {
    "payment_volume": "Number of card authorization attempts (one row per payment_id) in the period. Payments domain, synthetic.",
    "payment_value_usd": "Sum of attempted amount converted to USD with the dataset's synthetic FX table (last rate on or before the payment date). Payments whose currency has no rate are counted in volume but excluded from value.",
    "approval_rate": "Authorized / (authorized + declined). Payments without an authorization response are excluded from the denominator.",
    "decline_rate": "Declined / (authorized + declined). Approval rate + decline rate = 100%.",
    "avg_transaction_value": "Payment value (USD) / payments with a USD value.",
    "chargeback_rate": "Chargebacks / settled payments (disputes arrive 10-90 days after settlement, so recent periods are understated).",
    "core_volume": "Number of core-banking account transactions (deposits, withdrawals, payments, transfers, fees...) in the period. Synthetic.",
    "core_value_usd": "Sum of COMPLETED core-banking transactions converted to USD.",
    "core_failure_rate": "Failed / all core-banking transactions.",
    "anomaly_rate": "Flagged anomalies / core-banking transactions in the period. An anomaly is an alert from rules or an Isolation Forest model, NOT a confirmed fraud case.",
    "period_over_period": "Compared with the immediately preceding period of the same length. Counts/values: % change; rates: percentage-point change.",
}


@router.get("/meta")
@cached(ttl=300)
def meta():
    pay = one("""SELECT min(payment_date) d0, max(payment_date) d1, count(*) n, count(amount_usd) n_usd FROM ui.payments_usd""")
    core = one("""SELECT min(d) d0, max(d) d1, count(*) n, count(amount_usd) n_usd FROM ui.core_txn_usd""")
    an = one("SELECT count(*) n, min(transaction_timestamp)::date d0, max(transaction_timestamp)::date d1 FROM monitoring.transaction_anomalies")
    return {
        "domains": {
            "payments": {"label": "Card payments", "kind": "synthetic", **pay},
            "core": {"label": "Core banking", "kind": "synthetic", **core},
            "anomalies": {"label": "Anomaly alerts", "kind": "synthetic", **an},
            "external": {"label": "External aggregates (SBP, World Bank, BIS, ECB, FRED)", "kind": "real"},
        },
        "currency_note": "All value metrics are in USD, converted with the dataset's synthetic FX table.",
        "definitions": DEFINITIONS,
        "airflow_configured": bool(os.getenv("AIRFLOW_BASE_URL")),
        "auth": "api_key" if os.getenv("API_KEY") else "none (local development)",
    }

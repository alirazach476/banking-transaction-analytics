"""NovaBank payments API (FastAPI). Read-only analytics + model scoring over SYNTHETIC data.

Run: uvicorn src.api.main:app --reload     Docs: /docs     UI: /ui
Auth: if env API_KEY is set, send header X-API-Key. Unset => open (local development only).
"""
from __future__ import annotations

import json
import os
from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

import joblib
import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import text

from src.utils.db import get_engine

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "models"
CNP_CHANNELS = {"E-commerce", "Recurring"}
app = FastAPI(title="NovaBank Payments API", version="0.1.0",
              description="Synthetic-data payment analytics and model scoring. Not for real customer decisions.")


def require_key(x_api_key: str | None = Header(default=None)):
    expected = os.getenv("API_KEY")
    if expected and x_api_key != expected:
        raise HTTPException(401, "invalid or missing X-API-Key")


@lru_cache
def engine():
    return get_engine()


@lru_cache
def load_model(name: str):
    path = MODELS / f"{name}.joblib"
    if not path.exists():
        raise HTTPException(503, f"model {name} not trained; run scripts/phase6b_models.py")
    return joblib.load(path)


def _clean(r: dict) -> dict:
    return {k: (float(v) if hasattr(v, "quantize") else v) for k, v in r.items()}


def q(sql: str, **params) -> list[dict]:
    try:
        with engine().connect() as c:
            return [_clean(dict(r._mapping)) for r in c.execute(text(sql), params)]
    except Exception as exc:  # database down / table missing
        raise HTTPException(503, f"database unavailable: {type(exc).__name__}") from exc


@app.get("/health")
def health():
    return {"status": "ok", "synthetic_data_only": True}


@app.get("/models", dependencies=[Depends(require_key)])
def models():
    p = MODELS / "model_registry.json"
    return json.loads(p.read_text()) if p.exists() else {}


@app.get("/kpis/daily", dependencies=[Depends(require_key)])
def kpis_daily(start: date | None = None, end: date | None = None, limit: int = Query(366, le=5000)):
    return q("""SELECT payment_date, payments, approved, declined, cleared, settled, approval_rate, completion_rate,
                       settlement_rate, avg_response_ms FROM analytics.mart_payment_kpis_daily
                WHERE (CAST(:s AS date) IS NULL OR payment_date >= CAST(:s AS date))
                  AND (CAST(:e AS date) IS NULL OR payment_date <= CAST(:e AS date))
                ORDER BY payment_date DESC LIMIT :l""", s=start, e=end, l=limit)


@app.get("/kpis/summary", dependencies=[Depends(require_key)])
def kpis_summary():
    r = q("""SELECT sum(payments) payments, sum(approved) approved, sum(declined) declined, sum(cleared) cleared,
                    sum(settled) settled, min(payment_date) first_date, max(payment_date) last_date
             FROM analytics.mart_payment_kpis_daily""")[0]
    ap, de, cl, se = r["approved"], r["declined"], r["cleared"], r["settled"]
    return {"payments": int(r["payments"]), "first_date": r["first_date"], "last_date": r["last_date"],
            "approval_rate": ap / (ap + de), "completion_rate": cl / ap, "settlement_rate": se / cl,
            "definitions": "docs/BUSINESS_METRICS.md"}


@app.get("/decline-reasons", dependencies=[Depends(require_key)])
def decline_reasons(limit: int = Query(20, le=200)):
    return q("""SELECT decline_reason, sum(declined_payments)::int declined_payments, sum(declined_amount) declined_amount
                FROM analytics.mart_decline_reasons GROUP BY 1 ORDER BY 2 DESC LIMIT :l""", l=limit)


@app.get("/reconciliation/runs/latest", dependencies=[Depends(require_key)])
def recon_latest():
    rows = q("SELECT * FROM payments.reconciliation_runs ORDER BY created_at DESC LIMIT 1")
    if not rows:
        raise HTTPException(404, "no reconciliation run yet")
    return rows[0]


@app.get("/reconciliation/queue", dependencies=[Depends(require_key)])
def recon_queue(status: Literal["OPEN", "RESOLVED", "ANY"] = "OPEN", limit: int = Query(50, le=1000)):
    return q("""SELECT payment_id, settlement_id, issue_type, amount_at_risk, currency, priority, status, last_detected_at
                FROM payments.investigation_queue WHERE (:st = 'ANY' OR status = :st)
                ORDER BY priority, amount_at_risk DESC NULLS LAST LIMIT :l""", st=status, l=limit)


class DeclineRequest(BaseModel):
    amount: float = Field(gt=0, description="USD amount")
    hour: int = Field(ge=0, le=23)
    is_international: bool = False
    channel: str = "POS Chip"
    merchant_category: str = "Retail"
    card_status: str = "Active"


@app.post("/score/decline", dependencies=[Depends(require_key)])
def score_decline(r: DeclineRequest):
    m = load_model("decline_xgb")
    row = {"log_amt": float(np.log10(r.amount + 1)), "intl": float(r.is_international),
           "cnp": float(r.channel in CNP_CHANNELS), "night": float(r.hour < 5), "hour": r.hour,
           f"channel_{r.channel.title()}": 1.0, f"merchant_category_{r.merchant_category.title()}": 1.0,
           f"card_status_{r.card_status.title()}": 1.0}
    X = pd.DataFrame([row]).reindex(columns=m["features"], fill_value=0.0)
    return {"decline_probability": float(m["model"].predict_proba(X)[0, 1]), "model": "decline_xgb"}


class FraudRequest(BaseModel):
    amount: float = Field(gt=0)
    hour: int = Field(ge=0, le=23)
    is_international: bool = False
    channel: str = "POS Chip"
    foreign_merchant: bool = False
    card_txn_60m: int = Field(1, ge=1, description="payments on this card in the last 60 minutes incl. this one")
    card_amt_60m: float | None = None
    amt_vs_card_mean: float = Field(1.0, gt=0, description="amount divided by the card's historical mean amount")


@app.post("/score/fraud", dependencies=[Depends(require_key)])
def score_fraud(r: FraudRequest):
    m = load_model("fraud_xgb")
    row = {"log_amt": float(np.log10(r.amount + 1)), "intl": float(r.is_international),
           "cnp": float(r.channel in CNP_CHANNELS), "night": float(r.hour < 5), "hour": r.hour,
           "card_txn_60m": r.card_txn_60m,
           "card_amt_60m": r.card_amt_60m if r.card_amt_60m is not None else r.amount * r.card_txn_60m,
           "amt_vs_card_mean": r.amt_vs_card_mean, "foreign_merchant": float(r.foreign_merchant)}
    X = pd.DataFrame([row]).reindex(columns=m["features"], fill_value=0.0)
    p = float(m["model"].predict_proba(X)[0, 1])
    return {"fraud_probability": p, "flag": p >= m["threshold"], "threshold": m["threshold"], "model": "fraud_xgb"}


@app.get("/ui", include_in_schema=False)
def ui():
    return FileResponse(ROOT / "web" / "payments_dashboard.html")

"""NovaBank payments API (FastAPI). Read-only analytics + model scoring over SYNTHETIC data.

Run: uvicorn src.api.main:app --reload     Docs: /docs     UI: /ui
Auth: if env API_KEY is set, send header X-API-Key. Unset => open (local development only).
"""
from __future__ import annotations

import json
import os
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

import joblib
import numpy as np
import pandas as pd
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import text

from src.utils.db import get_engine

ROOT = Path(__file__).resolve().parents[2]
MODELS = ROOT / "models"
CNP_CHANNELS = {"E-commerce", "Recurring"}
@asynccontextmanager
async def lifespan(_app):
    """Warm the models at startup so the first scoring request is not slow (XGBoost import + model load)."""
    for name in ("decline_xgb", "fraud_xgb"):
        try:
            load_model(name)
        except Exception:  # models optional: scoring endpoints return 503 until trained
            pass
    yield


app = FastAPI(title="NovaBank Payments API", version="0.1.0", lifespan=lifespan,
              description="Synthetic-data payment analytics and model scoring. Not for real customer decisions.")


# ---------------------------------------------------------------- rate limiting (in-process sliding window)
# Per API key (or client IP). Limit from env RATE_LIMIT_PER_MIN (default 120; 0 disables). Single-process only:
# behind several workers/replicas use a shared store (e.g. Redis) or a gateway instead.
_hits: dict[str, deque] = defaultdict(deque)
EXEMPT = {"/health", "/ui", "/docs", "/openapi.json"}
EXEMPT_PREFIX = ("/app/",)


@app.middleware("http")
async def rate_limit(request: Request, call_next):
    limit = int(os.getenv("RATE_LIMIT_PER_MIN", "120"))
    if limit <= 0 or request.url.path in EXEMPT or request.url.path.startswith(EXEMPT_PREFIX):
        return await call_next(request)
    who = request.headers.get("x-api-key") or (request.client.host if request.client else "unknown")
    now = time.monotonic()
    dq = _hits[who]
    while dq and now - dq[0] > 60:
        dq.popleft()
    if len(dq) >= limit:
        retry = max(1, int(60 - (now - dq[0])))
        return JSONResponse({"detail": "rate limit exceeded"}, status_code=429, headers={"Retry-After": str(retry)})
    dq.append(now)
    return await call_next(request)


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


class CardFraudRequest(BaseModel):
    card_id: str
    authorization_ts: datetime
    amount: float = Field(gt=0)
    channel: str = "POS Chip"
    is_international: bool = False
    merchant_country: str | None = None
    card_country: str | None = None


@app.post("/score/fraud/card", dependencies=[Depends(require_key)])
def score_fraud_by_card(r: CardFraudRequest):
    """Fraud score with card features computed server-side from the card's payment history
    (payments strictly before authorization_ts; the current payment is added on top)."""
    h = q("""SELECT count(*) FILTER (WHERE authorization_ts > :t - interval '60 minutes') AS n60,
                    coalesce(sum(amount) FILTER (WHERE authorization_ts > :t - interval '60 minutes'), 0) AS a60,
                    avg(amount) AS prior_mean, count(*) AS prior_n
             FROM intermediate.int_card_payments WHERE card_id = :c AND authorization_ts < :t""",
          t=r.authorization_ts.replace(tzinfo=None), c=r.card_id)[0]
    n60, a60 = int(h["n60"]) + 1, float(h["a60"]) + r.amount
    ratio = r.amount / float(h["prior_mean"]) if h["prior_mean"] else 1.0
    foreign = bool(r.merchant_country and r.card_country and r.merchant_country.upper() != r.card_country.upper())
    res = score_fraud(FraudRequest(amount=r.amount, hour=r.authorization_ts.hour, is_international=r.is_international,
                                   channel=r.channel, foreign_merchant=foreign or r.is_international, card_txn_60m=n60,
                                   card_amt_60m=a60, amt_vs_card_mean=ratio))
    return {**res, "computed_features": {"card_txn_60m": n60, "card_amt_60m": a60, "amt_vs_card_mean": ratio,
                                         "prior_payments_on_card": int(h["prior_n"]), "foreign_merchant": foreign}}


@app.get("/ui", include_in_schema=False)
def ui():
    return FileResponse(ROOT / "web" / "payments_dashboard.html")


# React app (web/react-app, built with `npm run build`) is served at /app/ when its dist/ folder exists.
_dist = ROOT / "web" / "react-app" / "dist"
if _dist.exists():
    app.mount("/app", StaticFiles(directory=_dist, html=True), name="react-app")

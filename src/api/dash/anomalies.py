"""Fraud and anomaly intelligence (core-banking domain, SYNTHETIC).

An anomaly is an ALERT from statistical/rule checks or an Isolation Forest model. It is not confirmed fraud: investigation status
(NEW / INVESTIGATING / CONFIRMED_FRAUD / FALSE_POSITIVE / CLOSED) lives in monitoring.anomaly_investigations and defaults to NEW.
The synthetic data also carries injected-anomaly labels (warehouse.fact_transactions.is_injected_anomaly), used only to evaluate detection quality.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from .common import DR, cached, date_range, one, q, write

router = APIRouter(prefix="/anomalies", tags=["anomalies"])

METHOD = """CASE WHEN a.anomaly_reason LIKE '%ml_isolation_forest%' AND a.anomaly_reason ~ '(sudden_behavior_change|night_activity|high_amount|rapid_transactions|multiple_failures|statistical z-score)' THEN 'Rules + ML'
                  WHEN a.anomaly_reason LIKE '%ml_isolation_forest%' THEN 'ML (Isolation Forest)' ELSE 'Rule-based' END"""
W = "a.transaction_timestamp::date BETWEEN :a AND :b"


@router.get("/summary")
def summary(r: DR = Depends(date_range)):
    return _summary(r.d0, r.d1)


@cached(ttl=120)
def _summary(d0, d1):
    tot = one(f"SELECT count(*) alerts, count(*) FILTER (WHERE severity='High') high, count(*) FILTER (WHERE severity='Medium') medium, count(*) FILTER (WHERE severity='Low') low FROM monitoring.transaction_anomalies a WHERE {W}", a=d0, b=d1)
    txns = one("SELECT count(*) n FROM ui.core_txn_usd WHERE d BETWEEN :a AND :b", a=d0, b=d1)["n"]
    methods = q(f"SELECT {METHOD} method, count(*) alerts FROM monitoring.transaction_anomalies a WHERE {W} GROUP BY 1 ORDER BY 2 DESC", a=d0, b=d1)
    status = q(f"""SELECT coalesce(i.status,'NEW') status, count(*) alerts FROM monitoring.transaction_anomalies a
                   LEFT JOIN monitoring.anomaly_investigations i USING (anomaly_id) WHERE {W} GROUP BY 1 ORDER BY 2 DESC""", a=d0, b=d1)
    return {**tot, "transactions": txns, "rate": tot["alerts"] / txns if txns else None, "methods": methods, "investigation_status": status}


@router.get("/series")
def series(r: DR = Depends(date_range)):
    g = r.grain()
    return {"grain": g, "rows": _series(r.d0, r.d1, g)}


@cached(ttl=120)
def _series(d0, d1, g):
    return q(f"""SELECT date_trunc('{g}', a.transaction_timestamp)::date period, count(*) alerts, count(*) FILTER (WHERE severity='High') high,
                        count(*) FILTER (WHERE severity='Medium') medium, count(*) FILTER (WHERE severity='Low') low
                 FROM monitoring.transaction_anomalies a WHERE {W} GROUP BY 1 ORDER BY 1""", a=d0, b=d1)


@router.get("/categories")
@cached(ttl=120)
def categories(r: DR = Depends(date_range)):
    return _cats(r.d0, r.d1)


@cached(ttl=120)
def _cats(d0, d1):
    return q(f"""SELECT CASE WHEN rule LIKE 'statistical%' THEN 'statistical_z_score' ELSE regexp_replace(rule, '\\s*\\(.*', '') END category, count(*) alerts
                 FROM (SELECT unnest(string_to_array(replace(a.anomaly_reason, 'Potential anomaly: ', ''), '; ')) rule FROM monitoring.transaction_anomalies a WHERE {W}) t
                 GROUP BY 1 ORDER BY 2 DESC""", a=d0, b=d1)


@router.get("/score-distribution")
def score_distribution(r: DR = Depends(date_range)):
    return {"bin_width": 0.025, "rows": _scores(r.d0, r.d1)}


@cached(ttl=120)
def _scores(d0, d1):
    return q(f"""SELECT floor(ml_anomaly_score / 0.025) * 0.025 AS score_from, count(*) alerts, count(*) FILTER (WHERE severity='High') high
                 FROM monitoring.transaction_anomalies a WHERE {W} GROUP BY 1 ORDER BY 1""", a=d0, b=d1)


@router.get("/scatter")
def scatter(r: DR = Depends(date_range)):
    return {"note": "Random sample of up to 2,500 alerts; amount in USD.", "rows": _scatter(r.d0, r.d1)}


@cached(ttl=120)
def _scatter(d0, d1):
    return q(f"""SELECT a.anomaly_id, a.ml_anomaly_score score, a.severity, t.amount_usd amount_usd
                 FROM monitoring.transaction_anomalies a JOIN ui.core_txn_usd t USING (transaction_id)
                 WHERE {W} AND t.amount_usd IS NOT NULL ORDER BY md5(a.anomaly_id::text) LIMIT 2500""", a=d0, b=d1)


@router.get("/risk/customers")
def risk_customers(r: DR = Depends(date_range)):
    return {"weights": {"High": 3, "Medium": 2, "Low": 1}, "rows": _risk_c(r.d0, r.d1)}


@cached(ttl=120)
def _risk_c(d0, d1):
    return q(f"""SELECT a.customer_id, count(*) alerts, count(*) FILTER (WHERE a.severity='High') high,
                        sum(CASE a.severity WHEN 'High' THEN 3 WHEN 'Medium' THEN 2 ELSE 1 END) risk_points,
                        (SELECT count(*) FROM ui.core_txn_usd t WHERE t.customer_id = a.customer_id AND t.d BETWEEN :a AND :b) transactions
                 FROM monitoring.transaction_anomalies a WHERE {W} GROUP BY 1 ORDER BY 4 DESC, 2 DESC LIMIT 15""", a=d0, b=d1)


@router.get("/risk/merchants")
def risk_merchants(r: DR = Depends(date_range)):
    return {"note": "Merchants with at least 20 core-banking transactions in the period.", "rows": _risk_m(r.d0, r.d1)}


@cached(ttl=120)
def _risk_m(d0, d1):
    return q(f"""SELECT t.merchant_id, m.merchant_name, m.merchant_category, count(*) transactions, count(a.anomaly_id) alerts, count(a.anomaly_id)::float / count(*) alert_rate
                 FROM ui.core_txn_usd t LEFT JOIN monitoring.transaction_anomalies a USING (transaction_id) LEFT JOIN warehouse.dim_merchant m ON m.merchant_id = t.merchant_id
                 WHERE t.merchant_id IS NOT NULL AND t.d BETWEEN :a AND :b GROUP BY 1,2,3 HAVING count(*) >= 20 ORDER BY 6 DESC LIMIT 15""", a=d0, b=d1)


@router.get("/heatmap")
def heatmap(r: DR = Depends(date_range)):
    return {"note": "Day of week (1 = Monday) by hour of transaction.", "rows": _heat(r.d0, r.d1)}


@cached(ttl=120)
def _heat(d0, d1):
    return q(f"""SELECT extract(isodow FROM a.transaction_timestamp)::int AS dow, extract(hour FROM a.transaction_timestamp)::int AS hour, count(*) alerts
                 FROM monitoring.transaction_anomalies a WHERE {W} GROUP BY 1,2 ORDER BY 1,2""", a=d0, b=d1)


@router.get("/comparison")
def comparison(r: DR = Depends(date_range)):
    return _cmp(r.d0, r.d1)


@cached(ttl=120)
def _cmp(d0, d1):
    rows = q(f"""SELECT {METHOD} method, count(*) alerts, count(*) FILTER (WHERE t.is_injected_anomaly) matches_injected
                 FROM monitoring.transaction_anomalies a JOIN ui.core_txn_usd t USING (transaction_id) WHERE {W} GROUP BY 1""", a=d0, b=d1)
    injected = one("SELECT count(*) n FROM ui.core_txn_usd WHERE is_injected_anomaly AND d BETWEEN :a AND :b", a=d0, b=d1)["n"]
    det = {r["method"]: r for r in rows}

    def stat(name, methods):
        alerts = sum(det.get(m, {}).get("alerts", 0) for m in methods)
        hits = sum(det.get(m, {}).get("matches_injected", 0) for m in methods)
        return {"detector": name, "alerts": alerts, "true_positives": hits, "precision": hits / alerts if alerts else None, "recall": hits / injected if injected else None}
    return {"injected_total": injected, "detectors": [stat("Rule-based (incl. rules + ML)", ["Rule-based", "Rules + ML"]), stat("ML (Isolation Forest, incl. rules + ML)", ["ML (Isolation Forest)", "Rules + ML"]),
                                                       stat("Any detector", ["Rule-based", "Rules + ML", "ML (Isolation Forest)"])],
            "note": "Evaluated against the SYNTHETIC injected-anomaly labels only (what the generator planted); real-world precision/recall are unknown. Precision here treats unlabelled alerts as false positives, which understates real usefulness."}


class Investigation(BaseModel):
    status: str = Field(pattern="^(NEW|INVESTIGATING|CONFIRMED_FRAUD|FALSE_POSITIVE|CLOSED)$")
    assignee: str | None = Field(None, max_length=80)
    note: str | None = Field(None, max_length=1000)


@router.get("/{anomaly_id}")
def detail(anomaly_id: int):
    row = one("""SELECT a.*, coalesce(i.status,'NEW') investigation_status, i.assignee, i.note, i.updated_at, t.amount_usd, t.channel, t.transaction_type, t.status txn_status, t.merchant_id, t.branch_id
                 FROM monitoring.transaction_anomalies a LEFT JOIN monitoring.anomaly_investigations i USING (anomaly_id) LEFT JOIN ui.core_txn_usd t USING (transaction_id)
                 WHERE a.anomaly_id = :i""", i=anomaly_id)
    if not row:
        raise HTTPException(404, "anomaly not found")
    row["detection_method"] = one(f"SELECT {METHOD} m FROM monitoring.transaction_anomalies a WHERE a.anomaly_id = :i", i=anomaly_id)["m"]
    return row


@router.put("/{anomaly_id}/investigation")
def update_investigation(anomaly_id: int, body: Investigation):
    if not one("SELECT 1 x FROM monitoring.transaction_anomalies WHERE anomaly_id = :i", i=anomaly_id):
        raise HTTPException(404, "anomaly not found")
    write("""INSERT INTO monitoring.anomaly_investigations (anomaly_id, status, assignee, note, updated_at) VALUES (:i, :s, :a, :n, now())
             ON CONFLICT (anomaly_id) DO UPDATE SET status = :s, assignee = :a, note = :n, updated_at = now()""", i=anomaly_id, s=body.status, a=body.assignee, n=body.note)
    return {"anomaly_id": anomaly_id, "status": body.status}

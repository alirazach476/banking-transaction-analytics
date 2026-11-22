"""Executive overview: KPIs with prior-period comparison, time series and breakdowns. Definitions: see /v1/meta."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from .common import DR, cached, date_range, delta, one, q, safe_div

router = APIRouter(prefix="/overview", tags=["overview"])


@cached(ttl=120)
def _pay(d0, d1):
    return one("""SELECT count(*) n, coalesce(sum(amount_usd),0) value, count(amount_usd) n_usd, coalesce(sum(authorized::int),0) ap, coalesce(sum(declined::int),0) de,
                         coalesce(sum(settled::int),0) se, coalesce(sum(charged_back::int),0) cb
                  FROM ui.payments_usd WHERE payment_date BETWEEN :a AND :b""", a=d0, b=d1)


@cached(ttl=120)
def _core(d0, d1):
    r = one("""SELECT count(*) n, coalesce(sum((status='Completed')::int),0) completed, coalesce(sum((status='Failed')::int),0) failed,
                      coalesce(sum(amount_usd) FILTER (WHERE status='Completed'),0) value
               FROM ui.core_txn_usd WHERE d BETWEEN :a AND :b""", a=d0, b=d1)
    r["anomalies"] = one("SELECT count(*) n FROM monitoring.transaction_anomalies WHERE transaction_timestamp::date BETWEEN :a AND :b", a=d0, b=d1)["n"]
    return r


def kpi(key, label, cur, prior, unit, domain, rate=False, note=None):
    return {"key": key, "label": label, "value": cur, "prior": prior, "delta": delta(cur, prior, rate), "delta_unit": "pp" if rate else "%",
            "unit": unit, "domain": domain, "note": note}


@router.get("")
def overview(r: DR = Depends(date_range)):
    p, pp = _pay(r.d0, r.d1), _pay(r.p0, r.p1)
    c, cp = _core(r.d0, r.d1), _core(r.p0, r.p1)
    ar = lambda x: safe_div(x["ap"], x["ap"] + x["de"])
    dr = lambda x: safe_div(x["de"], x["ap"] + x["de"])
    avg = lambda x: safe_div(x["value"], x["n_usd"])
    return {
        "range": {"from": r.d0, "to": r.d1, "days": r.days, "prior_from": r.p0, "prior_to": r.p1},
        "headline": [
            kpi("payment_volume", "Transaction volume", p["n"], pp["n"], "count", "payments"),
            kpi("payment_value_usd", "Transaction value", p["value"], pp["value"], "usd", "payments", note=f"{p['n'] - p['n_usd']:,} payments without a USD rate excluded"),
            kpi("approval_rate", "Approval rate", ar(p), ar(pp), "ratio", "payments", rate=True),
            kpi("decline_rate", "Decline rate", dr(p), dr(pp), "ratio", "payments", rate=True),
            kpi("anomaly_rate", "Anomaly rate", safe_div(c["anomalies"], c["n"]), safe_div(cp["anomalies"], cp["n"]), "ratio", "core", rate=True, note="alerts, not confirmed fraud"),
            kpi("avg_transaction_value", "Average transaction value", avg(p), avg(pp), "usd", "payments"),
        ],
        "secondary": [
            kpi("chargeback_rate", "Chargeback rate", safe_div(p["cb"], p["se"]), safe_div(pp["cb"], pp["se"]), "ratio", "payments", rate=True),
            kpi("core_volume", "Core-banking transactions", c["n"], cp["n"], "count", "core"),
            kpi("core_value_usd", "Core-banking completed value", c["value"], cp["value"], "usd", "core"),
            kpi("core_failure_rate", "Core-banking failure rate", safe_div(c["failed"], c["n"]), safe_div(cp["failed"], cp["n"]), "ratio", "core", rate=True),
        ],
    }


@router.get("/series")
def series(r: DR = Depends(date_range)):
    return _series(r.d0, r.d1, r.grain())


@cached(ttl=120)
def _series(d0, d1, g):
    pay = q(f"""SELECT date_trunc('{g}', payment_date)::date period, count(*) volume, coalesce(sum(amount_usd),0) value,
                       coalesce(sum(authorized::int),0) approved, coalesce(sum(declined::int),0) declined
                FROM ui.payments_usd WHERE payment_date BETWEEN :a AND :b GROUP BY 1 ORDER BY 1""", a=d0, b=d1)
    core = q(f"""SELECT date_trunc('{g}', d)::date period, count(*) volume, coalesce(sum(amount_usd) FILTER (WHERE status='Completed'),0) value
                 FROM ui.core_txn_usd WHERE d BETWEEN :a AND :b GROUP BY 1 ORDER BY 1""", a=d0, b=d1)
    return {"grain": g, "payments": pay, "core": core}


@router.get("/breakdowns")
def breakdowns(r: DR = Depends(date_range)):
    return _breakdowns(r.d0, r.d1)


@cached(ttl=120)
def _breakdowns(d0, d1):
    channels = q("""SELECT channel, count(*) payments, coalesce(sum(amount_usd),0) value, sum(authorized::int)::float / nullif(sum(authorized::int + declined::int),0) approval_rate
                    FROM ui.payments_usd WHERE payment_date BETWEEN :a AND :b GROUP BY 1 ORDER BY 2 DESC""", a=d0, b=d1)
    cats = q("""SELECT merchant_category category, count(*) payments, coalesce(sum(amount_usd),0) value, sum(authorized::int)::float / nullif(sum(authorized::int + declined::int),0) approval_rate
                FROM ui.payments_usd WHERE payment_date BETWEEN :a AND :b GROUP BY 1 ORDER BY 3 DESC""", a=d0, b=d1)
    branches = q("""SELECT b.branch_id, b.branch_name, b.city, b.region, count(*) transactions,
                           coalesce(sum(t.amount_usd) FILTER (WHERE t.status='Completed'),0) value,
                           sum((t.status='Failed')::int)::float / count(*) failure_rate
                    FROM ui.core_txn_usd t JOIN warehouse.dim_branch b ON b.branch_id = t.branch_id
                    WHERE t.d BETWEEN :a AND :b GROUP BY 1,2,3,4 ORDER BY 6 DESC LIMIT 10""", a=d0, b=d1)
    segments = q("""SELECT activity_segment segment, count(*) customers FROM analytics.mart_customer_activity GROUP BY 1 ORDER BY 2 DESC""")
    alerts = q("""SELECT anomaly_id, transaction_id, customer_id, transaction_timestamp, amount, severity, ml_anomaly_score, anomaly_reason
                  FROM monitoring.transaction_anomalies WHERE severity = 'High' AND transaction_timestamp::date BETWEEN :a AND :b
                  ORDER BY transaction_timestamp DESC LIMIT 8""", a=d0, b=d1)
    return {"channels": channels, "categories": cats, "branches": branches,
            "segments": {"rows": segments, "note": "All-time customer activity segments from analytics.mart_customer_activity (not date filtered)."}, "alerts": alerts}

"""Customer analytics (core-banking domain, SYNTHETIC). Only COMPLETED transactions count toward activity and value (USD).

RFM (as of the end of the selected range): Recency = days since last completed transaction; Frequency = completed transactions in range;
Monetary = completed value in USD. Each is scored 1-5 by quintile (5 = best; for recency, 5 = most recent). Segments use R and the mean of F and M:
  Champions R>=4 & FM>=4 | Loyal R=3 & FM>=4 | At risk R<=2 & FM>=4 | Potential loyalists R>=4 & 2<=FM<4 | Need attention R=3 & FM<4 | Hibernating R<=2 & FM<4 | Promising otherwise (new, low volume).
CLV is an ESTIMATE, not an observation: average monthly completed USD value over the customer's active span x assumed revenue rate x assumed lifetime (months).
Defaults: revenue rate 1.5% of value, lifetime 36 months; both are parameters. The synthetic data has no revenue or churn ground truth.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from .common import DR, cached, date_range, one, q

router = APIRouter(prefix="/customers", tags=["customers"])

SEGMENT_SQL = """CASE WHEN r >= 4 AND (f + m) / 2.0 >= 4 THEN 'Champions' WHEN r = 3 AND (f + m) / 2.0 >= 4 THEN 'Loyal' WHEN r <= 2 AND (f + m) / 2.0 >= 4 THEN 'At risk'
                      WHEN r >= 4 AND (f + m) / 2.0 >= 2 THEN 'Potential loyalists' WHEN r = 3 THEN 'Need attention' WHEN r <= 2 THEN 'Hibernating' ELSE 'Promising' END"""

RFM_CTE = f"""WITH c AS (SELECT customer_id, max(d) last_d, count(*) freq, sum(amount_usd) monetary FROM ui.core_txn_usd
                   WHERE status = 'Completed' AND customer_id IS NOT NULL AND amount_usd IS NOT NULL AND d BETWEEN :a AND :b GROUP BY 1),
              s AS (SELECT customer_id, last_d, freq, monetary, (CAST(:b AS date) - last_d) recency, ntile(5) OVER (ORDER BY last_d) r, ntile(5) OVER (ORDER BY freq, monetary) f, ntile(5) OVER (ORDER BY monetary) m FROM c),
              g AS (SELECT *, {SEGMENT_SQL} segment FROM s)"""


@router.get("/rfm")
def rfm(r: DR = Depends(date_range)):
    return _rfm(r.d0, r.d1)


@cached(ttl=180)
def _rfm(d0, d1):
    seg = q(f"{RFM_CTE} SELECT segment, count(*) customers, sum(monetary) value, avg(freq) avg_frequency, avg(recency) avg_recency_days FROM g GROUP BY 1 ORDER BY 3 DESC", a=d0, b=d1)
    grid = q(f"{RFM_CTE} SELECT r, f, count(*) customers FROM g GROUP BY 1,2 ORDER BY 1,2", a=d0, b=d1)
    total = one("SELECT count(*) n FROM warehouse.dim_customer WHERE is_current")["n"]
    active = sum(s["customers"] for s in seg)
    return {"as_of": d1, "segments": seg, "grid": grid, "customers_total": total, "customers_without_completed_txn_in_range": total - active,
            "definition": __doc__.split("RFM (as of")[1].split("CLV is")[0].strip()}


@router.get("/trends")
def trends(r: DR = Depends(date_range)):
    return _trends(r.d0, r.d1, "month" if r.days > 120 else "week")


@cached(ttl=180)
def _trends(d0, d1, g):
    rows = q(f"""WITH first AS (SELECT customer_id, min(d) fd FROM ui.core_txn_usd WHERE status = 'Completed' AND customer_id IS NOT NULL GROUP BY 1)
                 SELECT date_trunc('{g}', t.d)::date period, count(DISTINCT t.customer_id) active_customers, coalesce(sum(t.amount_usd),0) value,
                        count(DISTINCT t.customer_id) FILTER (WHERE date_trunc('{g}', f.fd) = date_trunc('{g}', t.d)) new_customers
                 FROM ui.core_txn_usd t JOIN first f USING (customer_id) WHERE t.status = 'Completed' AND t.d BETWEEN :a AND :b GROUP BY 1 ORDER BY 1""", a=d0, b=d1)
    return {"grain": g, "rows": rows}


@router.get("/spend-distribution")
def spend_distribution(r: DR = Depends(date_range)):
    return _spend(r.d0, r.d1)


@cached(ttl=180)
def _spend(d0, d1):
    rows = q("""WITH c AS (SELECT customer_id, sum(amount_usd) v FROM ui.core_txn_usd WHERE status='Completed' AND amount_usd IS NOT NULL AND customer_id IS NOT NULL AND d BETWEEN :a AND :b GROUP BY 1)
                SELECT CASE WHEN v < 1000 THEN 1 WHEN v < 5000 THEN 2 WHEN v < 10000 THEN 3 WHEN v < 25000 THEN 4 WHEN v < 50000 THEN 5 WHEN v < 100000 THEN 6 ELSE 7 END bin, count(*) customers
                FROM c GROUP BY 1 ORDER BY 1""", a=d0, b=d1)
    labels = ["<1k", "1k-5k", "5k-10k", "10k-25k", "25k-50k", "50k-100k", "100k+"]
    got = {r["bin"]: r["customers"] for r in rows}
    return {"unit": "USD per customer in range", "rows": [{"label": labels[i - 1], "customers": got.get(i, 0)} for i in range(1, 8)]}


@router.get("/cohorts")
def cohorts():
    return _cohorts()


@cached(ttl=300)
def _cohorts():
    rows = q("""WITH first AS (SELECT customer_id, date_trunc('quarter', min(d))::date cohort FROM ui.core_txn_usd WHERE status='Completed' AND customer_id IS NOT NULL GROUP BY 1),
                act AS (SELECT DISTINCT customer_id, date_trunc('quarter', d)::date q FROM ui.core_txn_usd WHERE status='Completed' AND customer_id IS NOT NULL),
                size AS (SELECT cohort, count(*) n FROM first GROUP BY 1)
                SELECT f.cohort, ((extract(year FROM a.q) - extract(year FROM f.cohort)) * 4 + (extract(quarter FROM a.q) - extract(quarter FROM f.cohort)))::int offset_q,
                       count(*) active, s.n cohort_size
                FROM first f JOIN act a USING (customer_id) JOIN size s ON s.cohort = f.cohort GROUP BY 1,2,4 ORDER BY 1,2""")
    for r in rows:
        r["retention"] = r["active"] / r["cohort_size"]
    return {"note": "Cohort = quarter of a customer's first completed transaction; retention = share of the cohort with at least one completed transaction in the quarter at that offset. Later cohorts have fewer observable quarters.", "rows": rows}


@router.get("/clv")
def clv(r: DR = Depends(date_range), revenue_rate: float = Query(0.015, ge=0, le=0.2), lifetime_months: int = Query(36, ge=1, le=120)):
    return _clv(r.d0, r.d1, revenue_rate, lifetime_months)


@cached(ttl=180)
def _clv(d0, d1, rate, life):
    base = """WITH c AS (SELECT customer_id, sum(amount_usd) v, greatest(1, (max(d) - min(d)) / 30.0) months, count(*) n FROM ui.core_txn_usd
                         WHERE status='Completed' AND amount_usd IS NOT NULL AND customer_id IS NOT NULL AND d BETWEEN :a AND :b GROUP BY 1 HAVING count(*) >= 3),
                   e AS (SELECT customer_id, n, v / months monthly_value, v / months * :rate * :life clv FROM c)"""
    top = q(base + " SELECT e.customer_id, d.customer_type, e.n transactions, e.monthly_value, e.clv FROM e LEFT JOIN warehouse.dim_customer d ON d.customer_id = e.customer_id AND d.is_current ORDER BY clv DESC LIMIT 10", a=d0, b=d1, rate=rate, life=life)
    dist = q(base + " SELECT width_bucket(clv, 0, 2000, 10) bin, count(*) customers FROM e GROUP BY 1 ORDER BY 1", a=d0, b=d1, rate=rate, life=life)
    stats = one(base + " SELECT count(*) customers, avg(clv) mean, percentile_cont(0.5) WITHIN GROUP (ORDER BY clv) median, sum(clv) total FROM e", a=d0, b=d1, rate=rate, life=life)
    return {"assumptions": {"revenue_rate": rate, "lifetime_months": life, "min_completed_transactions": 3, "unit": "USD"}, "stats": stats, "top": top, "distribution": dist,
            "note": "ESTIMATE from the assumptions above, not observed revenue. Customers with fewer than 3 completed transactions in the range are excluded. Distribution bins are 0-200, 200-400 ... USD (last bin open-ended)."}


@router.get("/top")
def top(r: DR = Depends(date_range), limit: int = Query(15, le=100)):
    return q("""SELECT t.customer_id, d.customer_type, d.region, count(*) transactions, sum(t.amount_usd) FILTER (WHERE t.status='Completed') value
                FROM ui.core_txn_usd t LEFT JOIN warehouse.dim_customer d ON d.customer_id = t.customer_id AND d.is_current
                WHERE t.customer_id IS NOT NULL AND t.d BETWEEN :a AND :b GROUP BY 1,2,3 ORDER BY 5 DESC NULLS LAST LIMIT :l""", a=r.d0, b=r.d1, l=limit)


@router.get("/{customer_id}")
def customer(customer_id: str, r: DR = Depends(date_range)):
    prof = one("SELECT customer_id, first_name, last_name, customer_type, customer_status, gender, city, region, country, registration_date FROM warehouse.dim_customer WHERE customer_id = :c AND is_current", c=customer_id)
    if not prof:
        raise HTTPException(404, "customer not found")
    k = one("""SELECT count(*) transactions, count(*) FILTER (WHERE status='Completed') completed, count(*) FILTER (WHERE status='Failed') failed,
                      coalesce(sum(amount_usd) FILTER (WHERE status='Completed'),0) value, min(d) first_txn, max(d) last_txn
               FROM ui.core_txn_usd WHERE customer_id = :c AND d BETWEEN :a AND :b""", c=customer_id, a=r.d0, b=r.d1)
    monthly = q("""SELECT date_trunc('month', d)::date period, count(*) transactions, coalesce(sum(amount_usd) FILTER (WHERE status='Completed'),0) value
                   FROM ui.core_txn_usd WHERE customer_id = :c AND d BETWEEN :a AND :b GROUP BY 1 ORDER BY 1""", c=customer_id, a=r.d0, b=r.d1)
    channels = q("SELECT channel, count(*) transactions FROM ui.core_txn_usd WHERE customer_id = :c AND d BETWEEN :a AND :b GROUP BY 1 ORDER BY 2 DESC", c=customer_id, a=r.d0, b=r.d1)
    types = q("SELECT transaction_type, count(*) transactions FROM ui.core_txn_usd WHERE customer_id = :c AND d BETWEEN :a AND :b GROUP BY 1 ORDER BY 2 DESC", c=customer_id, a=r.d0, b=r.d1)
    alerts = one("SELECT count(*) alerts, count(*) FILTER (WHERE severity='High') high FROM monitoring.transaction_anomalies WHERE customer_id = :c", c=customer_id)
    pay = one("""SELECT count(*) payments, coalesce(sum(amount_usd),0) value, sum(declined::int) declined FROM ui.payments_usd WHERE customer_id = :c AND payment_date BETWEEN :a AND :b""", c=customer_id, a=r.d0, b=r.d1)
    return {"profile": prof, "kpis": k, "monthly": monthly, "channels": channels, "types": types, "alerts": alerts, "card_payments": pay,
            "note": "Core-banking and card-payment data are separate synthetic domains linked by customer_id."}

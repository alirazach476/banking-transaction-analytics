"""Merchant and branch analytics (SYNTHETIC). Merchant metrics come from the card-payments domain; branch metrics from core-banking transactions.

Merchant risk index = 0.5 x z(decline rate) + 0.5 x z(chargeback rate), z-scored across merchants with at least `min_payments` payments in the range.
It ranks merchants relative to each other; it is not a probability of fraud. Branch map markers use CITY centroids (GeoNames), not branch addresses.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from .common import DR, cached, date_range, one, q

router = APIRouter(tags=["merchants-branches"])


@router.get("/merchants/ranking")
def merchant_ranking(r: DR = Depends(date_range), sort: str = Query("risk", pattern="^(risk|value|payments|decline_rate|chargeback_rate)$"),
                     limit: int = Query(15, ge=1, le=100), min_payments: int = Query(200, ge=1)):
    return {"definition": __doc__.split("Merchant risk index")[1].split("Branch map")[0].strip(), "min_payments": min_payments, "rows": _mr(r.d0, r.d1, sort, limit, min_payments)}


@cached(ttl=180)
def _mr(d0, d1, sort, limit, minp):
    order = {"risk": "risk_index DESC", "value": "value DESC", "payments": "payments DESC", "decline_rate": "decline_rate DESC", "chargeback_rate": "chargeback_rate DESC NULLS LAST"}[sort]
    return q(f"""WITH m AS (SELECT merchant_id, count(*) payments, coalesce(sum(amount_usd),0) value, sum(declined::int)::float / nullif(sum(authorized::int + declined::int),0) decline_rate,
                                    sum(charged_back::int)::float / nullif(sum(settled::int),0) chargeback_rate, sum(charged_back::int) chargebacks
                             FROM ui.payments_usd WHERE merchant_id IS NOT NULL AND payment_date BETWEEN :a AND :b GROUP BY 1 HAVING count(*) >= :mp),
                      z AS (SELECT *, 0.5 * (decline_rate - avg(decline_rate) OVER ()) / nullif(stddev_pop(decline_rate) OVER (), 0)
                                    + 0.5 * (coalesce(chargeback_rate,0) - avg(coalesce(chargeback_rate,0)) OVER ()) / nullif(stddev_pop(coalesce(chargeback_rate,0)) OVER (), 0) risk_index FROM m)
                 SELECT z.*, d.merchant_name, d.merchant_category, d.city, d.region FROM z LEFT JOIN warehouse.dim_merchant d USING (merchant_id) ORDER BY {order} LIMIT :l""",
             a=d0, b=d1, mp=minp, l=limit)


@router.get("/merchants/{merchant_id}")
def merchant(merchant_id: str, r: DR = Depends(date_range)):
    prof = one("SELECT merchant_id, merchant_name, merchant_category, city, region, merchant_status FROM warehouse.dim_merchant WHERE merchant_id = :m", m=merchant_id)
    if not prof:
        raise HTTPException(404, "merchant not found")
    k = one("""SELECT count(*) payments, coalesce(sum(amount_usd),0) value, sum(authorized::int) approved, sum(declined::int) declined, sum(settled::int) settled, sum(charged_back::int) chargebacks
               FROM ui.payments_usd WHERE merchant_id = :m AND payment_date BETWEEN :a AND :b""", m=merchant_id, a=r.d0, b=r.d1)
    monthly = q("""SELECT date_trunc('month', payment_date)::date period, count(*) payments, coalesce(sum(amount_usd),0) value, sum(declined::int) declined
                   FROM ui.payments_usd WHERE merchant_id = :m AND payment_date BETWEEN :a AND :b GROUP BY 1 ORDER BY 1""", m=merchant_id, a=r.d0, b=r.d1)
    reasons = q("""SELECT coalesce(decline_reason,'UNSPECIFIED') reason, count(*) declined FROM ui.payments_usd WHERE merchant_id = :m AND declined AND payment_date BETWEEN :a AND :b GROUP BY 1 ORDER BY 2 DESC""", m=merchant_id, a=r.d0, b=r.d1)
    return {"profile": prof, "kpis": k, "monthly": monthly, "decline_reasons": reasons, "note": "Card-payment metrics (synthetic)."}


BR = """SELECT b.branch_id, b.branch_name, b.city, b.region, count(*) transactions, count(*) FILTER (WHERE t.status='Completed') completed, count(*) FILTER (WHERE t.status='Failed') failed,
              coalesce(sum(t.amount_usd) FILTER (WHERE t.status='Completed'),0) value, count(DISTINCT t.customer_id) customers
       FROM ui.core_txn_usd t JOIN warehouse.dim_branch b ON b.branch_id = t.branch_id WHERE t.d BETWEEN :a AND :b GROUP BY 1,2,3,4"""


@router.get("/branches/ranking")
def branch_ranking(r: DR = Depends(date_range)):
    return _br(r.d0, r.d1)


@cached(ttl=180)
def _br(d0, d1):
    rows = q(BR + " ORDER BY 8 DESC", a=d0, b=d1)
    for x in rows:
        x["completion_rate"] = x["completed"] / (x["completed"] + x["failed"]) if (x["completed"] + x["failed"]) else None
        x["failure_rate"] = x["failed"] / x["transactions"] if x["transactions"] else None
    return {"note": "Completion rate = completed / (completed + failed); failure rate = failed / all transactions (pending and reversed are in the denominator of failure rate only).", "rows": rows}


@router.get("/branches/map")
def branch_map(r: DR = Depends(date_range)):
    return _map(r.d0, r.d1)


@cached(ttl=180)
def _map(d0, d1):
    rows = q(f"""WITH b AS ({BR}) SELECT c.city, c.lat, c.lon, count(*) branches, sum(b.transactions) transactions, sum(b.value) value, sum(b.failed)::float / nullif(sum(b.transactions),0) failure_rate
                 FROM b JOIN ui.city_centroids c ON c.city = b.city AND c.country = 'United States' GROUP BY 1,2,3 ORDER BY 5 DESC""", a=d0, b=d1)
    unmatched = q("SELECT DISTINCT city FROM warehouse.dim_branch WHERE city NOT IN (SELECT city FROM ui.city_centroids WHERE country = 'United States')")
    return {"markers": rows, "unmapped_cities": [u["city"] for u in unmatched],
            "note": "Markers are CITY centroids from the GeoNames gazetteer (CC BY 4.0), not branch addresses; the dataset has no coordinates. Branches in the same city share one marker."}


@router.get("/branches/regions")
def branch_regions(r: DR = Depends(date_range)):
    return _reg(r.d0, r.d1)


@cached(ttl=180)
def _reg(d0, d1):
    rows = q(f"""WITH b AS ({BR}) SELECT region, count(*) branches, sum(transactions) transactions, sum(value) value, sum(failed)::float / nullif(sum(transactions),0) failure_rate, sum(customers) customer_branch_pairs
                 FROM b GROUP BY 1 ORDER BY 4 DESC""", a=d0, b=d1)
    custs = q("SELECT region, count(*) customers FROM warehouse.dim_customer WHERE is_current GROUP BY 1")
    return {"rows": rows, "customers_by_region": custs, "note": "Customers carry a region but no city or coordinates; region comparisons are shown as charts, not on the map."}


@router.get("/branches/{branch_id}")
def branch(branch_id: str, r: DR = Depends(date_range)):
    prof = one("SELECT branch_id, branch_name, city, region, country, branch_type, branch_status, opening_date FROM warehouse.dim_branch WHERE branch_id = :b", b=branch_id)
    if not prof:
        raise HTTPException(404, "branch not found")
    k = one("""SELECT count(*) transactions, count(*) FILTER (WHERE status='Completed') completed, count(*) FILTER (WHERE status='Failed') failed,
                      coalesce(sum(amount_usd) FILTER (WHERE status='Completed'),0) value, count(DISTINCT customer_id) customers
               FROM ui.core_txn_usd WHERE branch_id = :b AND d BETWEEN :a AND :c""", b=branch_id, a=r.d0, c=r.d1)
    monthly = q("""SELECT date_trunc('month', d)::date period, count(*) transactions, coalesce(sum(amount_usd) FILTER (WHERE status='Completed'),0) value, count(*) FILTER (WHERE status='Failed') failed
                   FROM ui.core_txn_usd WHERE branch_id = :b AND d BETWEEN :a AND :c GROUP BY 1 ORDER BY 1""", b=branch_id, a=r.d0, c=r.d1)
    return {"profile": prof, "kpis": k, "monthly": monthly}

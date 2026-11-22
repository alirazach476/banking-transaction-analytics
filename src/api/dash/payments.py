"""Payment intelligence (payments domain, SYNTHETIC). Filters: date range, channel, merchant category, merchant, status (approved/declined)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from .common import DR, cached, date_range, q

router = APIRouter(prefix="/payments", tags=["payments"])


class F:
    """Filter set shared by every payments endpoint; builds a parameterised WHERE clause (user values are bound, never interpolated)."""

    def __init__(self, r: DR = Depends(date_range), channel: list[str] | None = Query(None), category: list[str] | None = Query(None),
                 merchant: str | None = None, status: str | None = Query(None, pattern="^(approved|declined)$")):
        self.r, self.channel, self.category, self.merchant, self.status = r, channel, category, merchant, status

    def where(self):
        w, p = ["payment_date BETWEEN :a AND :b"], {"a": self.r.d0, "b": self.r.d1}
        if self.channel:
            w.append("channel = ANY(:ch)")
            p["ch"] = self.channel
        if self.category:
            w.append("merchant_category = ANY(:cat)")
            p["cat"] = self.category
        if self.merchant:
            w.append("merchant_id = :m")
            p["m"] = self.merchant
        if self.status == "approved":
            w.append("authorized")
        elif self.status == "declined":
            w.append("declined")
        return " AND ".join(w), p


@cached(ttl=300)
def _filters():
    return {"channels": [r["channel"] for r in q("SELECT channel, count(*) n FROM ui.payments_usd GROUP BY 1 ORDER BY 2 DESC")],
            "categories": [r["merchant_category"] for r in q("SELECT merchant_category, count(*) n FROM ui.payments_usd GROUP BY 1 ORDER BY 2 DESC")],
            "statuses": ["approved", "declined"],
            "not_applicable": "Card payments have no transaction type or branch; use the Transaction Explorer for core-banking transactions."}


@router.get("/filters")
def filters():
    return _filters()


AMOUNT_BIN = """CASE WHEN amount_usd < 5 THEN 1 WHEN amount_usd < 10 THEN 2 WHEN amount_usd < 25 THEN 3 WHEN amount_usd < 50 THEN 4 WHEN amount_usd < 100 THEN 5
                     WHEN amount_usd < 250 THEN 6 WHEN amount_usd < 500 THEN 7 WHEN amount_usd < 1000 THEN 8 WHEN amount_usd < 5000 THEN 9 ELSE 10 END"""
AMOUNT_LABELS = ["<5", "5-10", "10-25", "25-50", "50-100", "100-250", "250-500", "500-1k", "1k-5k", "5k+"]


@cached(ttl=120)
def _run(kind: str, where: str, frozen: tuple, grain: str):
    p = {k: (list(v) if isinstance(v, tuple) else v) for k, v in frozen}
    if kind == "kpis":
        return q(f"""SELECT count(*) payments, coalesce(sum(amount_usd),0) value, sum(authorized::int) approved, sum(declined::int) declined,
                            sum(cleared::int) cleared, sum(settled::int) settled, sum(reversed::int) reversed, sum(refunded::int) refunded, sum(charged_back::int) charged_back,
                            percentile_cont(0.5) WITHIN GROUP (ORDER BY response_ms) median_response_ms
                     FROM ui.payments_usd WHERE {where}""", **p)[0]
    if kind == "trend":
        return q(f"""SELECT date_trunc('{grain}', payment_date)::date period, count(*) payments, sum(authorized::int) approved, sum(declined::int) declined,
                            sum(authorized::int)::float / nullif(sum(authorized::int + declined::int),0) approval_rate
                     FROM ui.payments_usd WHERE {where} GROUP BY 1 ORDER BY 1""", **p)
    if kind == "channels":
        return q(f"""SELECT channel, count(*) payments, coalesce(sum(amount_usd),0) value, sum(authorized::int)::float / nullif(sum(authorized::int + declined::int),0) approval_rate
                     FROM ui.payments_usd WHERE {where} GROUP BY 1 ORDER BY 2 DESC""", **p)
    if kind == "amount":
        rows = q(f"SELECT {AMOUNT_BIN} bin, count(*) payments FROM ui.payments_usd WHERE {where} AND amount_usd IS NOT NULL GROUP BY 1 ORDER BY 1", **p)
        got = {r["bin"]: r["payments"] for r in rows}
        return [{"label": AMOUNT_LABELS[i - 1], "payments": got.get(i, 0)} for i in range(1, 11)]
    if kind == "post":
        return q(f"""SELECT date_trunc('month', payment_date)::date period, sum(settled::int) settled, sum(authorized::int) approved, sum(reversed::int) reversals,
                            sum(refunded::int) refunds, sum(charged_back::int) chargebacks
                     FROM ui.payments_usd WHERE {where} GROUP BY 1 ORDER BY 1""", **p)
    if kind == "failures":
        return q(f"""SELECT coalesce(decline_reason,'UNSPECIFIED') reason, count(*) declined, coalesce(sum(amount_usd),0) value
                     FROM ui.payments_usd WHERE {where} AND declined GROUP BY 1 ORDER BY 2 DESC""", **p)
    if kind == "failure_trend":
        return q(f"""WITH top AS (SELECT coalesce(decline_reason,'UNSPECIFIED') r FROM ui.payments_usd WHERE {where} AND declined GROUP BY 1 ORDER BY count(*) DESC LIMIT 5)
                     SELECT date_trunc('month', payment_date)::date period, coalesce(decline_reason,'UNSPECIFIED') reason, count(*) declined
                     FROM ui.payments_usd WHERE {where} AND declined AND coalesce(decline_reason,'UNSPECIFIED') IN (SELECT r FROM top) GROUP BY 1,2 ORDER BY 1""", **p)
    if kind == "categories":
        return q(f"""SELECT merchant_category category, count(*) payments, coalesce(sum(amount_usd),0) value, sum(declined::int) declined,
                            sum(authorized::int)::float / nullif(sum(authorized::int + declined::int),0) approval_rate
                     FROM ui.payments_usd WHERE {where} GROUP BY 1 ORDER BY 3 DESC""", **p)
    if kind == "heatmap":
        return q(f"""SELECT extract(isodow FROM authorization_ts)::int AS dow, extract(hour FROM authorization_ts)::int AS hour, count(*) payments,
                            sum(declined::int)::float / nullif(sum(authorized::int + declined::int),0) decline_rate
                     FROM ui.payments_usd WHERE {where} AND authorization_ts IS NOT NULL GROUP BY 1,2 ORDER BY 1,2""", **p)
    if kind == "sankey":
        return q(f"""SELECT count(*) attempts,
              count(*) FILTER (WHERE declined) declined,
              count(*) FILTER (WHERE NOT authorized AND NOT declined) no_response,
              count(*) FILTER (WHERE authorized AND NOT cleared AND reversed) reversed_before_clearing,
              count(*) FILTER (WHERE authorized AND NOT cleared AND NOT reversed) not_cleared,
              count(*) FILTER (WHERE authorized AND cleared AND NOT settled) cleared_not_settled,
              count(*) FILTER (WHERE authorized AND cleared AND settled AND charged_back) chargeback,
              count(*) FILTER (WHERE authorized AND cleared AND settled AND NOT charged_back AND refunded) refunded,
              count(*) FILTER (WHERE authorized AND cleared AND settled AND NOT charged_back AND NOT refunded) retained
            FROM ui.payments_usd WHERE {where}""", **p)[0]
    raise ValueError(kind)


def go(kind: str, f: F, grain: str = ""):
    w, p = f.where()
    frozen = tuple((k, tuple(v) if isinstance(v, list) else v) for k, v in sorted(p.items()))
    return _run(kind, w, frozen, grain)


@router.get("/kpis")
def kpis(f: F = Depends()):
    return go("kpis", f)


@router.get("/trend")
def trend(f: F = Depends()):
    g = f.r.grain()
    return {"grain": g, "rows": go("trend", f, g)}


@router.get("/channels")
def channels(f: F = Depends()):
    return go("channels", f)


@router.get("/amount-distribution")
def amount_distribution(f: F = Depends()):
    return {"unit": "USD", "rows": go("amount", f)}


@router.get("/post-authorization")
def post_authorization(f: F = Depends()):
    return {"note": "Chargebacks arrive 10-90 days after settlement; the most recent months are right-censored.", "rows": go("post", f)}


@router.get("/failures")
def failures(f: F = Depends()):
    return {"reasons": go("failures", f), "trend": go("failure_trend", f)}


@router.get("/categories")
def categories(f: F = Depends()):
    return go("categories", f)


@router.get("/heatmap")
def heatmap(f: F = Depends()):
    return {"note": "Hour of authorization (synthetic timestamps); dow 1 = Monday.", "rows": go("heatmap", f)}


@router.get("/lifecycle")
def lifecycle(f: F = Depends()):
    s = go("sankey", f)
    approved = s["attempts"] - s["declined"] - s["no_response"]
    settled = s["retained"] + s["refunded"] + s["chargeback"]
    cleared = settled + s["cleared_not_settled"]
    links = [("Authorization attempts", "Approved", approved), ("Authorization attempts", "Declined", s["declined"]), ("Authorization attempts", "No response", s["no_response"]),
             ("Approved", "Cleared", cleared), ("Approved", "Reversed before clearing", s["reversed_before_clearing"]), ("Approved", "Not cleared", s["not_cleared"]),
             ("Cleared", "Settled", settled), ("Cleared", "Cleared, not settled", s["cleared_not_settled"]),
             ("Settled", "Retained", s["retained"]), ("Settled", "Refunded", s["refunded"]), ("Settled", "Chargeback", s["chargeback"])]
    return {"links": [{"source": a, "target": b, "value": v} for a, b, v in links if v > 0], "totals": s,
            "note": "Built from payment-level lifecycle flags (synthetic events). Terminal states are mutually exclusive: a settled payment that was both refunded and charged back is shown as a chargeback."}

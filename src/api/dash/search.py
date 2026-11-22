"""Global search and the notification centre (both derived from real records; no placeholder items)."""
from __future__ import annotations

from fastapi import APIRouter, Query

from .common import cached, one, q

router = APIRouter(tags=["search"])


@router.get("/search")
def search(q_: str = Query(..., alias="q", min_length=2, max_length=60)):
    like = f"%{q_}%"
    return {
        "customers": q("""SELECT customer_id id, trim(coalesce(first_name,'') || ' ' || coalesce(last_name,'')) label, customer_type detail FROM warehouse.dim_customer
                          WHERE is_current AND (customer_id ILIKE :l OR first_name ILIKE :l OR last_name ILIKE :l) ORDER BY 1 LIMIT 5""", l=like),
        "merchants": q("""SELECT merchant_id id, merchant_name label, merchant_category detail FROM warehouse.dim_merchant
                          WHERE merchant_id ILIKE :l OR merchant_name ILIKE :l ORDER BY 1 LIMIT 5""", l=like),
        "branches": q("""SELECT branch_id id, branch_name label, city detail FROM warehouse.dim_branch WHERE branch_id ILIKE :l OR branch_name ILIKE :l OR city ILIKE :l ORDER BY 1 LIMIT 5""", l=like),
        "transactions": q("SELECT transaction_id id, transaction_id label, status detail FROM ui.core_txn_usd WHERE transaction_id ILIKE :l ORDER BY ts DESC LIMIT 5", l=like),
    }


@router.get("/notifications")
@cached(ttl=60)
def notifications():
    items = []
    n = one("""SELECT count(*) n FROM monitoring.transaction_anomalies a LEFT JOIN monitoring.anomaly_investigations i USING (anomaly_id)
               WHERE a.severity = 'High' AND coalesce(i.status, 'NEW') = 'NEW'""")["n"]
    if n:
        items.append({"level": "warning", "title": f"{n:,} high-severity anomaly alerts not yet investigated", "to": "/fraud", "domain": "synthetic"})
    f = one("SELECT count(*) n FROM audit.pipeline_runs WHERE status = 'FAILED'")["n"]
    if f:
        items.append({"level": "error", "title": f"{f} failed pipeline run(s) in the audit log", "to": "/engineering", "domain": "pipeline"})
    d = one("SELECT count(*) n FROM audit.data_quality_results WHERE status <> 'PASS'")["n"]
    if d:
        items.append({"level": "warning", "title": f"{d} data-quality check(s) not passing", "to": "/engineering", "domain": "pipeline"})
    o = one("SELECT count(*) n FROM payments.investigation_queue WHERE status = 'OPEN'")["n"]
    if o:
        items.append({"level": "info", "title": f"{o:,} open payment reconciliation exceptions", "to": "/engineering", "domain": "synthetic"})
    return {"items": items}

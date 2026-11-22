"""Generic server-side tables: whitelisted datasets and columns, bound parameters (no user text is interpolated into SQL),
multi-column sort, typed column filters, global search, date-range filter, pagination, CSV and XLSX export.

Query parameters: page (0-based), size (<=200), sort ("col:asc,col2:desc"), filters (JSON list of {id, op, value}), q (global search), from/to (date column).
Operators by column kind: text: eq, in, contains, startswith | num: eq, gte, lte, between | ts/date: gte, lte, between | bool: eq.
"""
from __future__ import annotations

import csv
import io
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import text

from .common import DR, DEFAULT_FROM, DEFAULT_TO, engine, q

router = APIRouter(prefix="/tables", tags=["tables"])

T, N, D, B = "text", "num", "ts", "bool"

DATASETS: dict[str, dict] = {
    "transactions": {
        "label": "Core-banking transactions (synthetic)",
        "from": "ui.core_txn_usd t LEFT JOIN monitoring.transaction_anomalies a ON a.transaction_id = t.transaction_id",
        "cols": {"transaction_id": ("t.transaction_id", T), "ts": ("t.ts", D), "transaction_type": ("t.transaction_type", T), "channel": ("t.channel", T), "status": ("t.status", T),
                 "amount": ("t.amount", N), "currency": ("t.currency", T), "amount_usd": ("t.amount_usd", N), "customer_id": ("t.customer_id", T), "branch_id": ("t.branch_id", T),
                 "merchant_id": ("t.merchant_id", T), "anomaly_severity": ("a.severity", T), "anomaly_score": ("a.ml_anomaly_score", N), "anomaly_reason": ("a.anomaly_reason", T),
                 "injected_anomaly_label": ("t.is_injected_anomaly", B)},
        "hidden": ["anomaly_reason", "injected_anomaly_label", "currency"], "date": "t.d", "search": ["t.transaction_id", "t.customer_id", "t.merchant_id", "t.branch_id"], "sort": "ts:desc", "id": "transaction_id"},
    "payments": {
        "label": "Card payments (synthetic)", "from": "ui.payments_usd p",
        "cols": {"payment_id": ("p.payment_id", T), "payment_date": ("p.payment_date", D), "channel": ("p.channel", T), "merchant_category": ("p.merchant_category", T), "merchant_id": ("p.merchant_id", T),
                 "customer_id": ("p.customer_id", T), "currency": ("p.currency", T), "amount": ("p.amount", N), "amount_usd": ("p.amount_usd", N), "authorized": ("p.authorized", B), "declined": ("p.declined", B),
                 "decline_reason": ("p.decline_reason", T), "cleared": ("p.cleared", B), "settled": ("p.settled", B), "refunded": ("p.refunded", B), "charged_back": ("p.charged_back", B), "response_ms": ("p.response_ms", N)},
        "hidden": ["currency", "cleared", "settled", "refunded"], "date": "p.payment_date", "search": ["p.payment_id", "p.merchant_id", "p.customer_id"], "sort": "payment_date:desc", "id": "payment_id"},
    "payment-failures": {
        "label": "Declined card payments (synthetic)", "from": "ui.payments_usd p", "where": "p.declined",
        "cols": {"payment_id": ("p.payment_id", T), "payment_date": ("p.payment_date", D), "decline_reason": ("p.decline_reason", T), "channel": ("p.channel", T), "merchant_category": ("p.merchant_category", T),
                 "merchant_id": ("p.merchant_id", T), "customer_id": ("p.customer_id", T), "amount": ("p.amount", N), "currency": ("p.currency", T), "amount_usd": ("p.amount_usd", N), "response_ms": ("p.response_ms", N)},
        "hidden": ["currency"], "date": "p.payment_date", "search": ["p.payment_id", "p.merchant_id", "p.customer_id"], "sort": "payment_date:desc", "id": "payment_id"},
    "customers": {
        "label": "Customers (synthetic; all-time activity)", "from": "analytics.mart_customer_activity c",
        "cols": {"customer_id": ("c.customer_id", T), "first_name": ("c.first_name", T), "last_name": ("c.last_name", T), "customer_type": ("c.customer_type", T), "customer_status": ("c.customer_status", T),
                 "region": ("c.region", T), "city": ("c.city", T), "activity_segment": ("c.activity_segment", T), "transaction_count": ("c.transaction_count", N), "completed_count": ("c.completed_count", N),
                 "failed_count": ("c.failed_count", N), "days_since_last_transaction": ("c.days_since_last_transaction", N), "last_transaction_at": ("c.last_transaction_at", D), "distinct_channels": ("c.distinct_channels", N)},
        "hidden": ["first_name", "last_name", "city", "distinct_channels"], "search": ["c.customer_id", "c.first_name", "c.last_name"], "sort": "transaction_count:desc", "id": "customer_id"},
    "merchants": {
        "label": "Merchants (synthetic; payment statistics all-time)", "from": "warehouse.dim_merchant m LEFT JOIN ui.merchant_stats s ON s.merchant_id = m.merchant_id",
        "cols": {"merchant_id": ("m.merchant_id", T), "merchant_name": ("m.merchant_name", T), "merchant_category": ("m.merchant_category", T), "city": ("m.city", T), "region": ("m.region", T),
                 "merchant_status": ("m.merchant_status", T), "payments": ("s.payments", N), "value_usd": ("s.value_usd", N), "approval_rate": ("s.approval_rate", N), "declined": ("s.declined", N), "chargebacks": ("s.chargebacks", N)},
        "hidden": ["city", "merchant_status"], "search": ["m.merchant_id", "m.merchant_name"], "sort": "value_usd:desc", "id": "merchant_id"},
    "branches": {
        "label": "Branches (synthetic; all-time)", "from": "analytics.mart_branch_performance b",
        "cols": {"branch_id": ("b.branch_id", T), "branch_name": ("b.branch_name", T), "city": ("b.city", T), "region": ("b.region", T), "branch_type": ("b.branch_type", T), "branch_status": ("b.branch_status", T),
                 "transaction_count": ("b.transaction_count", N), "completed_count": ("b.completed_count", N), "failed_count": ("b.failed_count", N), "failure_rate_pct": ("b.failure_rate_pct", N),
                 "active_customers": ("b.active_customers", N)},
        "hidden": ["branch_type", "branch_status"], "search": ["b.branch_id", "b.branch_name", "b.city"], "sort": "transaction_count:desc", "id": "branch_id"},
    "anomalies": {
        "label": "Anomaly alerts (synthetic; alerts, not confirmed fraud)",
        "from": "monitoring.transaction_anomalies a LEFT JOIN monitoring.anomaly_investigations i ON i.anomaly_id = a.anomaly_id",
        "cols": {"anomaly_id": ("a.anomaly_id", N), "transaction_id": ("a.transaction_id", T), "customer_id": ("a.customer_id", T), "transaction_timestamp": ("a.transaction_timestamp", D), "amount": ("a.amount", N),
                 "severity": ("a.severity", T), "ml_anomaly_score": ("a.ml_anomaly_score", N), "rule_based_score": ("a.rule_based_score", N), "investigation_status": ("coalesce(i.status, 'NEW')", T),
                 "assignee": ("i.assignee", T), "anomaly_reason": ("a.anomaly_reason", T), "z_score": ("a.z_score", N), "note": ("i.note", T)},
        "hidden": ["rule_based_score", "z_score", "note", "assignee"], "date": "a.transaction_timestamp", "search": ["a.transaction_id", "a.customer_id", "a.anomaly_reason"], "sort": "ml_anomaly_score:desc", "id": "anomaly_id"},
    "pipeline-runs": {
        "label": "Pipeline runs (audit.pipeline_runs)", "from": "audit.pipeline_runs r",
        "cols": {"run_id": ("r.run_id::text", T), "pipeline_name": ("r.pipeline_name", T), "status": ("r.status", T), "start_time": ("r.start_time", D), "end_time": ("r.end_time", D),
                 "duration_s": ("extract(epoch FROM (r.end_time - r.start_time))", N), "rows_processed": ("r.rows_processed", N), "rows_failed": ("r.rows_failed", N), "mode": ("r.mode", T), "notes": ("r.notes", T)},
        "hidden": ["mode"], "date": "r.start_time", "search": ["r.pipeline_name", "r.notes"], "sort": "start_time:desc", "id": "run_id", "no_default_range": True},
    "data-quality": {
        "label": "Data-quality check results (audit.data_quality_results)", "from": "audit.data_quality_results d",
        "cols": {"result_id": ("d.result_id::text", T), "check_name": ("d.check_name", T), "table_name": ("d.table_name", T), "check_type": ("d.check_type", T), "status": ("d.status", T), "failed_rows": ("d.failed_rows", N),
                 "expected_result": ("d.expected_result", T), "actual_result": ("d.actual_result", T), "execution_time_ms": ("d.execution_time_ms", N), "checked_at": ("d.checked_at", D)},
        "hidden": ["expected_result", "actual_result"], "date": "d.checked_at", "search": ["d.check_name", "d.table_name"], "sort": "checked_at:desc", "id": "result_id", "no_default_range": True},
}


def _spec(name: str) -> dict:
    if name not in DATASETS:
        raise HTTPException(404, f"unknown table {name}; available: {', '.join(DATASETS)}")
    return DATASETS[name]


def _clause(spec: dict, r: DR | None, search: str | None, filters: str | None):
    cols, where, p = spec["cols"], [], {}
    if spec.get("where"):
        where.append(spec["where"])
    if spec.get("date") and r is not None and not spec.get("no_default_range"):
        where.append(f"{spec['date']} BETWEEN :d0 AND :d1")
        p["d0"], p["d1"] = r.d0, r.d1
    elif spec.get("date") and r is not None and spec.get("no_default_range"):
        pass
    if search:
        where.append("(" + " OR ".join(f"{c}::text ILIKE :srch" for c in spec["search"]) + ")")
        p["srch"] = f"%{search}%"
    if filters:
        try:
            fl = json.loads(filters)
            assert isinstance(fl, list)
        except Exception:
            raise HTTPException(422, "filters must be a JSON list of {id, op, value}")
        for i, f in enumerate(fl):
            cid, op, val = f.get("id"), f.get("op"), f.get("value")
            if cid not in cols:
                raise HTTPException(422, f"unknown column {cid}")
            expr, kind = cols[cid]
            k = f"f{i}"
            if kind == T and op == "eq":
                where.append(f"{expr} = :{k}"); p[k] = str(val)
            elif kind == T and op == "in":
                where.append(f"{expr} = ANY(:{k})"); p[k] = [str(x) for x in val]
            elif kind == T and op == "contains":
                where.append(f"{expr} ILIKE :{k}"); p[k] = f"%{val}%"
            elif kind == T and op == "startswith":
                where.append(f"{expr} ILIKE :{k}"); p[k] = f"{val}%"
            elif kind in (N, D) and op in ("eq", "gte", "lte"):
                where.append(f"{expr} {'=' if op == 'eq' else '>=' if op == 'gte' else '<='} :{k}"); p[k] = val
            elif kind in (N, D) and op == "between" and isinstance(val, list) and len(val) == 2:
                where.append(f"{expr} BETWEEN :{k}a AND :{k}b"); p[k + "a"], p[k + "b"] = val
            elif kind == B and op == "eq":
                where.append(f"{expr} = :{k}"); p[k] = bool(val)
            else:
                raise HTTPException(422, f"operator {op} not valid for {cid} ({kind})")
    return (" WHERE " + " AND ".join(where)) if where else "", p


def _order(spec: dict, sort: str | None) -> str:
    items = []
    for part in (sort or spec["sort"]).split(","):
        col, _, d = part.partition(":")
        if col not in spec["cols"]:
            raise HTTPException(422, f"cannot sort by {col}")
        items.append(f"{spec['cols'][col][0]} {'DESC' if d.lower() == 'desc' else 'ASC'} NULLS LAST")
    return " ORDER BY " + ", ".join(items) + f", {spec['cols'][spec['id']][0]}"


def _select(spec: dict) -> str:
    return ", ".join(f'{e} AS "{n}"' for n, (e, _k) in spec["cols"].items())


@router.get("")
def catalogue():
    return [{"name": n, "label": s["label"], "id": s["id"], "default_sort": s["sort"], "hidden": s.get("hidden", []), "date_filter": bool(s.get("date")) and not s.get("no_default_range"),
             "columns": [{"id": c, "kind": k} for c, (_e, k) in s["cols"].items()]} for n, s in DATASETS.items()]


class Q:
    def __init__(self, page: int = Query(0, ge=0), size: int = Query(25, ge=1, le=200), sort: str | None = None, filters: str | None = None,
                 q: str | None = Query(None, max_length=100), from_: str | None = Query(None, alias="from"), to: str | None = None):
        import datetime as dt
        d0 = dt.date.fromisoformat(from_) if from_ else DEFAULT_FROM
        d1 = dt.date.fromisoformat(to) if to else DEFAULT_TO
        self.r, self.page, self.size, self.sort, self.filters, self.q = DR(d0, d1), page, size, sort, filters, q


@router.get("/{name}")
def table(name: str, p: Q = Depends()):
    spec = _spec(name)
    w, params = _clause(spec, p.r, p.q, p.filters)
    total = q(f"SELECT count(*) n FROM {spec['from']}{w}", **params)[0]["n"]
    rows = q(f"SELECT {_select(spec)} FROM {spec['from']}{w}{_order(spec, p.sort)} LIMIT :lim OFFSET :off", **params, lim=p.size, off=p.page * p.size)
    return {"rows": rows, "total": total, "page": p.page, "size": p.size, "pages": (total + p.size - 1) // p.size, "id": spec["id"], "label": spec["label"]}


@router.get("/{name}/export")
def export(name: str, fmt: str = Query("csv", pattern="^(csv|xlsx)$"), p: Q = Depends(), limit: int = Query(50000, ge=1, le=100000)):
    spec = _spec(name)
    w, params = _clause(spec, p.r, p.q, p.filters)
    sql = text(f"SELECT {_select(spec)} FROM {spec['from']}{w}{_order(spec, p.sort)} LIMIT :lim")
    names = list(spec["cols"])
    if fmt == "csv":
        def gen():
            # rows are written in chunks: one yield per row costs a thread hop each and made a 50k-row export take over a minute
            with engine().connect().execution_options(stream_results=True) as c:
                buf = io.StringIO()
                wr = csv.writer(buf)
                wr.writerow(names)
                for i, row in enumerate(c.execute(sql, {**params, "lim": limit}), 1):
                    wr.writerow(["" if v is None else v for v in row])
                    if i % 2000 == 0:
                        yield buf.getvalue()
                        buf.seek(0); buf.truncate()
                yield buf.getvalue()
        return StreamingResponse(gen(), media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{name}.csv"'})
    from openpyxl import Workbook
    wb = Workbook(write_only=True)
    ws = wb.create_sheet(name[:31])
    ws.append(names)
    with engine().connect().execution_options(stream_results=True) as c:
        for row in c.execute(sql, {**params, "lim": min(limit, 50000)}):
            ws.append([("" if v is None else (v.replace(tzinfo=None) if hasattr(v, "tzinfo") and v.tzinfo else (float(v) if hasattr(v, "quantize") else v))) for v in row])
    out = io.BytesIO()
    wb.save(out)
    return Response(out.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", headers={"Content-Disposition": f'attachment; filename="{name}.xlsx"'})

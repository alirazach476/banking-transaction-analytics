"""Data-engineering observability from REAL pipeline metadata: audit.* tables, payments.reconciliation_runs, dbt artifacts in dbt/target,
the Airflow REST API when AIRFLOW_BASE_URL is configured, and DAG definitions parsed from airflow/dags. Nothing here is simulated:
when a source is not available the endpoint says so instead of inventing status."""
from __future__ import annotations

import ast
import datetime as dt
import json
import os
from pathlib import Path

from fastapi import APIRouter

from .common import cached, one, q

router = APIRouter(prefix="/observability", tags=["observability"])
ROOT = Path(__file__).resolve().parents[3]


@router.get("/summary")
@cached(ttl=60)
def summary():
    runs = q("SELECT pipeline_name, status, count(*) n FROM audit.pipeline_runs GROUP BY 1,2 ORDER BY 1,2")
    dq = q("SELECT status, count(*) n FROM audit.data_quality_results GROUP BY 1")
    ing = one("SELECT count(*) sources, coalesce(sum(rows_read),0) rows_read, coalesce(sum(rows_loaded),0) rows_loaded, coalesce(sum(rows_rejected),0) rows_rejected FROM audit.source_ingestion")
    rec = q("SELECT status, count(*) n FROM audit.reconciliation_results GROUP BY 1")
    return {"pipeline_runs": runs, "data_quality": dq, "ingestion": ing, "reconciliation": rec}


@router.get("/pipelines")
@cached(ttl=60)
def pipelines():
    stats = q("""SELECT pipeline_name, count(*) runs, count(*) FILTER (WHERE status = 'SUCCESS') success, count(*) FILTER (WHERE status = 'FAILED') failed,
                        count(*) FILTER (WHERE status = 'WARNING') warning, avg(extract(epoch FROM (end_time - start_time))) avg_duration_s,
                        sum(rows_processed) rows_processed, max(start_time) last_run
                 FROM audit.pipeline_runs GROUP BY 1 ORDER BY 1""")
    history = q("""SELECT run_id::text run_id, pipeline_name, status, start_time, end_time, extract(epoch FROM (end_time - start_time)) duration_s, rows_processed, rows_failed
                   FROM audit.pipeline_runs ORDER BY start_time DESC LIMIT 50""")
    return {"stats": stats, "history": history, "note": "audit.pipeline_runs written by the project's own pipelines (not Airflow task instances)."}


@router.get("/ingestion")
@cached(ttl=60)
def ingestion():
    return q("""SELECT source_name, source_system, status, rows_read, rows_loaded, rows_rejected, started_at, completed_at,
                       rows_rejected::float / nullif(rows_read, 0) reject_rate FROM audit.source_ingestion ORDER BY started_at DESC""")


@router.get("/data-quality")
@cached(ttl=60)
def data_quality():
    by_table = q("SELECT table_name, status, count(*) n FROM audit.data_quality_results GROUP BY 1,2 ORDER BY 1,2")
    failing = q("""SELECT check_name, table_name, check_type, status, failed_rows, expected_result, actual_result, checked_at
                   FROM audit.data_quality_results WHERE status <> 'PASS' ORDER BY checked_at DESC""")
    return {"by_table": by_table, "failing": failing}


@router.get("/reconciliation")
@cached(ttl=60)
def reconciliation():
    src = q("SELECT source_name, metric_name, source_value, warehouse_value, difference, status, checked_at FROM audit.reconciliation_results ORDER BY checked_at DESC, source_name")
    pay = q("SELECT * FROM payments.reconciliation_runs ORDER BY recon_run_id DESC LIMIT 1")
    open_q = q("SELECT issue_type, status, count(*) n, coalesce(sum(amount_at_risk),0) amount_at_risk FROM payments.investigation_queue GROUP BY 1,2 ORDER BY 3 DESC")
    return {"source_to_warehouse": src, "payments_latest_run": pay[0] if pay else None, "payments_exception_queue": open_q}


@router.get("/freshness")
@cached(ttl=60)
def freshness():
    now = dt.datetime.now(dt.timezone.utc)
    items = []

    def add(name, ts, kind):
        if ts is None:
            items.append({"name": name, "latest": None, "age_days": None, "kind": kind})
            return
        if isinstance(ts, str):
            ts = dt.datetime.fromisoformat(ts.replace('Z', '+00:00'))
        t = ts if isinstance(ts, dt.datetime) else dt.datetime.combine(ts, dt.time(), tzinfo=dt.timezone.utc)
        t = t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)
        items.append({"name": name, "latest": t, "age_days": (now - t).total_seconds() / 86400, "kind": kind})
    add("Last pipeline run", one("SELECT max(start_time) t FROM audit.pipeline_runs")["t"], "pipeline")
    add("Last source ingestion", one("SELECT max(completed_at) t FROM audit.source_ingestion")["t"], "pipeline")
    add("Last payments reconciliation run", one("SELECT max(created_at) t FROM payments.reconciliation_runs")["t"], "pipeline")
    add("Latest payment in data", one("SELECT max(payment_date) t FROM ui.payments_usd")["t"], "data")
    add("Latest core-banking transaction", one("SELECT max(d) t FROM ui.core_txn_usd")["t"], "data")
    add("Latest FX rate", one("SELECT max(rate_date)::date t FROM raw.fx_rates_synthetic")["t"], "data")
    dbt = _dbt_results()
    add("Last dbt invocation", dbt["generated_at"] if dbt else None, "dbt")
    return {"as_of": now, "items": items, "note": "The transactional data is synthetic and historical (2023-2025), so data ages are large by design; pipeline and dbt timestamps show when processes last ran."}


def _dbt_results():
    f = ROOT / "dbt" / "target" / "run_results.json"
    if not f.exists():
        return None
    r = json.loads(f.read_text(encoding="utf-8"))
    res = r.get("results", [])
    return {"command": (r.get("args") or {}).get("which"), "generated_at": r["metadata"].get("generated_at"), "elapsed_s": r.get("elapsed_time"), "dbt_version": r["metadata"].get("dbt_version"),
            "counts": {s: sum(1 for x in res if x["status"] == s) for s in sorted({x["status"] for x in res})},
            "results": [{"unique_id": x["unique_id"], "status": x["status"], "seconds": x.get("execution_time"), "message": (x.get("message") or "")[:200], "failures": x.get("failures")} for x in res]}


@router.get("/dbt")
@cached(ttl=60)
def dbt():
    last = _dbt_results()
    m = ROOT / "dbt" / "target" / "manifest.json"
    inv = None
    if m.exists():
        man = json.loads(m.read_text(encoding="utf-8"))
        nodes = man.get("nodes", {})
        kinds: dict[str, int] = {}
        for n in nodes.values():
            kinds[n["resource_type"]] = kinds.get(n["resource_type"], 0) + 1
        inv = {"nodes_by_type": kinds, "sources": len(man.get("sources", {})), "generated_at": man["metadata"].get("generated_at")}
    return {"available": last is not None, "last_invocation": last, "inventory": inv,
            "note": "dbt writes run_results.json for the LAST invocation only, so this shows that run's results plus the project inventory from manifest.json; it is not a run history."}


def _dag_files():
    out = []
    for f in sorted((ROOT / "airflow" / "dags").glob("*.py")):
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except SyntaxError:
            continue
        dag_id, schedule, tasks = None, None, []
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                fn = getattr(n.func, "id", getattr(n.func, "attr", ""))
                kw = {k.arg: k.value for k in n.keywords if k.arg}
                if fn == "DAG" and "dag_id" in kw or (fn == "DAG" and n.args):
                    node = kw.get("dag_id") or n.args[0]
                    dag_id = getattr(node, "value", None)
                    sc = kw.get("schedule") or kw.get("schedule_interval")
                    schedule = getattr(sc, "value", None) if sc is not None else None
                if fn.endswith("Operator") and "task_id" in kw:
                    tasks.append(getattr(kw["task_id"], "value", None))
        if dag_id:
            out.append({"dag_id": dag_id, "file": f.name, "schedule": schedule, "tasks": [t for t in tasks if t]})
    return out


@router.get("/airflow")
def airflow():
    base = os.getenv("AIRFLOW_BASE_URL")
    defs = _dag_files()
    if not base:
        return {"connected": False, "reason": "AIRFLOW_BASE_URL is not set, so no live DAG status is available. Showing DAG definitions parsed from airflow/dags (definitions only, no run status).", "definitions": defs}
    import requests
    auth = (os.getenv("AIRFLOW_USER", ""), os.getenv("AIRFLOW_PASSWORD", ""))
    try:
        dags = requests.get(f"{base.rstrip('/')}/api/v1/dags", auth=auth, timeout=8).json().get("dags", [])
        out = []
        for d in dags:
            runs = requests.get(f"{base.rstrip('/')}/api/v1/dags/{d['dag_id']}/dagRuns", params={"order_by": "-execution_date", "limit": 20}, auth=auth, timeout=8).json().get("dag_runs", [])
            out.append({"dag_id": d["dag_id"], "is_paused": d.get("is_paused"), "schedule": (d.get("schedule_interval") or {}).get("value"), "runs": [
                {"run_id": r["dag_run_id"], "state": r["state"], "start": r.get("start_date"), "end": r.get("end_date")} for r in runs]})
        return {"connected": True, "dags": out, "definitions": defs}
    except Exception as exc:
        return {"connected": False, "reason": f"Airflow at {base} could not be reached ({type(exc).__name__}).", "definitions": defs}


@router.get("/errors")
@cached(ttl=60)
def errors():
    log = []
    for r in q("SELECT start_time t, pipeline_name, notes, rows_failed FROM audit.pipeline_runs WHERE status = 'FAILED' ORDER BY start_time DESC LIMIT 20"):
        log.append({"time": r["t"], "source": "pipeline", "level": "ERROR", "message": f"{r['pipeline_name']} failed" + (f": {r['notes']}" if r["notes"] else "")})
    for r in q("SELECT checked_at t, check_name, table_name, status, failed_rows FROM audit.data_quality_results WHERE status <> 'PASS' ORDER BY checked_at DESC LIMIT 20"):
        log.append({"time": r["t"], "source": "data quality", "level": "WARNING" if r["status"] == "WARNING" else "ERROR", "message": f"{r['check_name']} on {r['table_name']}: {r['status']} ({r['failed_rows']} failed rows)"})
    for r in q("SELECT started_at t, source_name, status, rows_rejected FROM audit.source_ingestion WHERE status <> 'SUCCESS' OR rows_rejected > 0 ORDER BY started_at DESC LIMIT 20"):
        log.append({"time": r["t"], "source": "ingestion", "level": "ERROR" if r["status"] != "SUCCESS" else "WARNING", "message": f"{r['source_name']}: {r['status']}, {r['rows_rejected']} rows rejected"})
    d = _dbt_results()
    for x in (d or {}).get("results", []):
        if x["status"] in ("error", "fail"):
            log.append({"time": d["generated_at"], "source": "dbt", "level": "ERROR", "message": f"{x['unique_id']}: {x['message']}"})
        elif x["status"] == "warn":
            log.append({"time": d["generated_at"], "source": "dbt", "level": "WARNING", "message": f"{x['unique_id']}: {x['message']}"})
    log.sort(key=lambda e: str(e["time"]), reverse=True)
    return {"entries": log[:80], "note": "Collected from audit tables and dbt results; the project has no central application-log store."}

"""Orchestration task logic, independent of Airflow so it can be unit-tested and run from a CLI or a DAG.

Every function is idempotent (safe to re-run) and returns a small JSON-serialisable dict for XCom/logging.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text

from src.monitoring.drift import psi
from src.utils.db import get_engine
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)
ROOT = Path(os.environ.get("AIRFLOW_PROJECT_ROOT", Path(__file__).resolve().parents[2]))


class DataQualityError(RuntimeError):
    """Raised by the quality gate; fails the DAG run so bad data does not reach marts consumers."""


def generate_payments(num_payments: int = 100_000, seed: int | None = None) -> dict:
    from src.payments.writer import main as gen
    argv = ["--payments", str(num_payments)] + (["--seed", str(seed)] if seed is not None else [])
    m = gen(argv)
    return {"row_counts": m["row_counts"]}


def load_payments() -> dict:
    from src.payments.load import load_payment_sources
    from config.settings import get_settings
    return load_payment_sources(get_settings().data_source_dir / "payments")


def run_dbt(select: str, test: bool = True) -> dict:
    """Run `dbt build` (or run) for a selector inside the dbt project. Raises on failure."""
    cmd = [sys.executable, "-m", "dbt.cli.main", "build" if test else "run", "--select", select, "--profiles-dir", "."]
    p = subprocess.run(cmd, cwd=ROOT / "dbt", capture_output=True, text=True, env=os.environ)
    tail = "\n".join(p.stdout.strip().splitlines()[-5:])
    if p.returncode != 0:
        raise RuntimeError(f"dbt failed for {select}:\n{p.stdout[-2000:]}\n{p.stderr[-500:]}")
    return {"select": select, "tail": tail}


def run_reconciliation() -> dict:
    from src.payments.load import run_reconciliation_from_raw
    res = run_reconciliation_from_raw()
    s = res.summary
    return {k: (float(v) if isinstance(v, (np.floating, float)) else int(v) if isinstance(v, (np.integer, int)) else str(v))
            for k, v in s.items()}


def ingest_external(only: list[str] | None = None) -> dict:
    from src.external.ingest import run_all
    out = run_all(only=only)
    failed = [r["source"] for r in out if r["status"] not in ("OK", "UNCHANGED", "SUCCESS")]
    return {"sources": len(out), "failed": failed}


def quality_gate(min_approval: float = 0.5, max_null_date_share: float = 0.02, engine=None) -> dict:
    """Fail the run if marts are empty, rates are implausible, or too many payments lack a date."""
    engine = engine or get_engine()
    with engine.connect() as c:
        k = c.execute(text("""SELECT count(*) days, sum(payments) payments, sum(approved) approved, sum(declined) declined
                              FROM analytics.mart_payment_kpis_daily""")).one()
        total = c.execute(text("SELECT count(*) FROM intermediate.int_payment_outcomes")).scalar()
        undated = c.execute(text("SELECT count(*) FROM intermediate.int_payment_outcomes WHERE payment_date IS NULL")).scalar()
        dup = c.execute(text("""SELECT count(*) FROM (SELECT payment_id FROM intermediate.int_payment_outcomes
                                GROUP BY 1 HAVING count(*) > 1) d""")).scalar()
    problems = []
    if not k.days or not k.payments:
        problems.append("mart_payment_kpis_daily is empty")
    else:
        rate = float(k.approved) / max(float(k.approved + k.declined), 1)
        if not (min_approval <= rate <= 1):
            problems.append(f"approval rate {rate:.3f} outside [{min_approval}, 1]")
    if total and undated / total > max_null_date_share:
        problems.append(f"{undated}/{total} payments have no valid authorization date")
    if dup:
        problems.append(f"{dup} duplicate payment_ids in int_payment_outcomes")
    if problems:
        raise DataQualityError("; ".join(problems))
    return {"days": int(k.days), "payments": int(k.payments), "undated": int(undated)}


def drift_check(window_days: int = 30, threshold: float = 0.25, engine=None) -> dict:
    """PSI of payment amount and of the daily approval rate: last `window_days` vs the preceding history.
    Logs a warning (does not fail the run) when PSI > threshold."""
    engine = engine or get_engine()
    amt = pd.read_sql(text("SELECT payment_date, amount FROM intermediate.int_payment_outcomes WHERE payment_date IS NOT NULL AND amount IS NOT NULL"), engine)
    amt["payment_date"] = pd.to_datetime(amt.payment_date)
    cut = amt.payment_date.max() - pd.Timedelta(days=window_days)
    ref, cur = amt[amt.payment_date <= cut].amount, amt[amt.payment_date > cut].amount
    res = {"window_days": window_days, "cut": str(cut.date()), "psi_amount": psi(np.log1p(ref), np.log1p(cur)) if len(ref) and len(cur) else None}
    res["alert"] = bool(res["psi_amount"] is not None and res["psi_amount"] > threshold)
    if res["alert"]:
        logger.warning("DRIFT ALERT: amount PSI %.3f > %.2f", res["psi_amount"], threshold)
    return res

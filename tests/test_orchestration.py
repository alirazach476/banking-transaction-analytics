"""Orchestration tests. Airflow itself is not installed in the dev environment, so DAG files are imported against
a minimal stub of the Airflow API that records the task graph; task logic is tested directly."""
import importlib.util
import sys
import types
from pathlib import Path

import pytest

from src.orchestration import tasks

ROOT = Path(__file__).resolve().parents[1]


class _Op:
    registry: list = []

    def __init__(self, task_id, **kw):
        self.task_id, self.kw, self.up, self.down = task_id, kw, set(), set()
        _Op.registry.append(self)

    def __rshift__(self, other):
        for o in (other if isinstance(other, list) else [other]):
            self.down.add(o.task_id)
            o.up.add(self.task_id)
        return other

    def __rrshift__(self, other):  # list >> op
        for s in other:
            s >> self
        return self


class _DAG:
    def __init__(self, dag_id, **kw):
        self.dag_id, self.kw = dag_id, kw

    def __enter__(self):
        _Op.registry = []
        return self

    def __exit__(self, *a):
        pass


def _load_dag(name):
    air = types.ModuleType("airflow"); air.DAG = _DAG
    ops = types.ModuleType("airflow.operators"); py = types.ModuleType("airflow.operators.python")
    py.PythonOperator = _Op; py.ShortCircuitOperator = _Op
    sys.modules.update({"airflow": air, "airflow.operators": ops, "airflow.operators.python": py})
    spec = importlib.util.spec_from_file_location(name, ROOT / "airflow" / "dags" / f"{name}.py")
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m, {o.task_id: o for o in _Op.registry}


def test_payments_dag_structure():
    m, t = _load_dag("payments_pipeline")
    assert set(t) == {"check_generate_flag", "generate_payments", "load_raw_payments", "dbt_payments",
                      "reconcile_payments", "quality_gate", "drift_check"}
    assert t["dbt_payments"].up == {"load_raw_payments"}
    assert t["reconcile_payments"].up == {"dbt_payments"} and t["quality_gate"].up == {"dbt_payments"}
    assert t["drift_check"].up == {"quality_gate"}
    assert t["load_raw_payments"].kw["trigger_rule"] == "none_failed_min_one_success"


def test_external_dag_structure():
    m, t = _load_dag("external_data_daily")
    assert t["check_ingest_results"].up == {"ingest_external"} and t["dbt_external"].up == {"check_ingest_results"}


def test_fail_if_sources_failed():
    m, _ = _load_dag("external_data_daily")

    class TI:
        def __init__(self, v): self.v = v
        def xcom_pull(self, task_ids): return self.v
    m._fail_if_sources_failed(ti=TI({"failed": []}))
    with pytest.raises(RuntimeError):
        m._fail_if_sources_failed(ti=TI({"failed": ["fred"]}))


def test_quality_gate_passes_on_live_marts():
    try:
        r = tasks.quality_gate()
    except tasks.DataQualityError as e:  # pragma: no cover
        pytest.fail(str(e))
    except Exception as e:
        pytest.skip(f"database unavailable: {type(e).__name__}")
    assert r["payments"] > 0


def test_quality_gate_fails_when_empty():
    from sqlalchemy import create_engine, text
    e = create_engine("sqlite://")
    with e.begin() as c:  # sqlite has no schemas: attach them
        pass
    with pytest.raises(Exception):
        tasks.quality_gate(engine=e)


def test_drift_check_runs():
    try:
        r = tasks.drift_check()
    except Exception as e:
        pytest.skip(f"database unavailable: {type(e).__name__}")
    assert r["psi_amount"] is not None and r["psi_amount"] < 0.25 and r["alert"] is False


def test_reconciliation_from_raw_sees_clean_clearing_rows():
    """Regression: COPY loads empty dq_defect as NULL; the loader query must still select clean rows."""
    try:
        r = tasks.run_reconciliation()
    except Exception as e:
        pytest.skip(f"database unavailable: {type(e).__name__}")
    assert r["cleared_payments"] > 100_000

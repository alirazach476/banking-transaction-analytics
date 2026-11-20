"""
NovaBank payments_pipeline: load payment lifecycle data, build dbt models, reconcile, gate quality, check drift.

  (optional generate) -> load_raw -> dbt_payments -> [reconcile, quality_gate] ; quality_gate -> drift_check

Task logic lives in src/orchestration/tasks.py (unit-tested without Airflow).
Trigger-time parameters: generate (bool, default false), num_payments (int).
Synthetic data only.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator, ShortCircuitOperator

PROJECT_ROOT = os.environ.get("AIRFLOW_PROJECT_ROOT", "/opt/airflow/project")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

default_args = {
    "owner": "novabank-analytics",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}


def _t():
    from src.orchestration import tasks  # imported lazily so DAG parsing stays fast
    return tasks


def _should_generate(**ctx) -> bool:
    return bool(ctx["params"].get("generate", False))


with DAG(
    dag_id="payments_pipeline",
    description="Payments: load, dbt, reconcile, quality gate, drift check",
    default_args=default_args,
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    params={"generate": False, "num_payments": 100000},
    tags=["novabank", "payments", "synthetic"],
) as dag:
    maybe_generate = ShortCircuitOperator(task_id="check_generate_flag", python_callable=_should_generate,
                                          ignore_downstream_trigger_rules=False)
    generate = PythonOperator(task_id="generate_payments",
                              python_callable=lambda **c: _t().generate_payments(int(c["params"]["num_payments"])))
    load_raw = PythonOperator(task_id="load_raw_payments", python_callable=lambda **_: _t().load_payments(),
                              trigger_rule="none_failed_min_one_success")
    dbt_payments = PythonOperator(task_id="dbt_payments", python_callable=lambda **_: _t().run_dbt("models/payments"))
    reconcile = PythonOperator(task_id="reconcile_payments", python_callable=lambda **_: _t().run_reconciliation())
    gate = PythonOperator(task_id="quality_gate", python_callable=lambda **_: _t().quality_gate())
    drift = PythonOperator(task_id="drift_check", python_callable=lambda **_: _t().drift_check())

    maybe_generate >> generate >> load_raw
    # when generation is skipped, still load the existing source files
    load_raw >> dbt_payments >> [reconcile, gate]
    gate >> drift

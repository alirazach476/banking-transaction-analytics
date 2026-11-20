"""
NovaBank payments_pipeline: load payment lifecycle data, build dbt models, reconcile, gate quality, check drift.

  check_generate_flag -> generate_payments -> load_raw_payments -> dbt_payments -> [reconcile_payments, quality_gate]
  quality_gate -> drift_check        (load_raw_payments also runs when generation is skipped)

Tasks run `python -m src.orchestration.cli ...` in the project's own Python environment (AIRFLOW_PYTHON), so they are
independent of Airflow's pinned dependencies. Task logic lives in src/orchestration/tasks.py (unit-tested).
Trigger-time params: generate (bool, default false), num_payments (int). Synthetic data only.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.python import ShortCircuitOperator

PROJECT_ROOT = os.environ.get("AIRFLOW_PROJECT_ROOT", "/opt/airflow/project")
PYTHON = os.environ.get("AIRFLOW_PYTHON", "python")
CLI = f"cd {PROJECT_ROOT} && PYTHONPATH={PROJECT_ROOT} {PYTHON} -m src.orchestration.cli"

default_args = {
    "owner": "novabank-analytics",
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}


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
    generate = BashOperator(task_id="generate_payments", bash_command=CLI + " generate --num-payments {{ params.num_payments }}")
    load_raw = BashOperator(task_id="load_raw_payments", bash_command=CLI + " load",
                            trigger_rule="none_failed_min_one_success")
    dbt_payments = BashOperator(task_id="dbt_payments", bash_command=CLI + " dbt --select models/payments")
    reconcile = BashOperator(task_id="reconcile_payments", bash_command=CLI + " reconcile")
    gate = BashOperator(task_id="quality_gate", bash_command=CLI + " quality-gate")
    drift = BashOperator(task_id="drift_check", bash_command=CLI + " drift")

    maybe_generate >> generate >> load_raw
    load_raw >> dbt_payments >> [reconcile, gate]
    gate >> drift

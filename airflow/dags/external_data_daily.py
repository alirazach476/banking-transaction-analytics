"""
NovaBank external_data_daily: polite ingestion of public data (ECB FX, World Bank, FRED, ECB RSS), then the external dbt models.
Ingestion is change-detected (SHA-256) and idempotent. The CLI exits non-zero when any source failed, which fails the task.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.bash import BashOperator

PROJECT_ROOT = os.environ.get("AIRFLOW_PROJECT_ROOT", "/opt/airflow/project")
PYTHON = os.environ.get("AIRFLOW_PYTHON", "python")
CLI = f"cd {PROJECT_ROOT} && PYTHONPATH={PROJECT_ROOT} {PYTHON} -m src.orchestration.cli"

default_args = {"owner": "novabank-analytics", "retries": 3, "retry_delay": timedelta(minutes=10),
                "execution_timeout": timedelta(hours=1)}

with DAG(
    dag_id="external_data_daily",
    description="External public data ingestion + dbt external marts",
    default_args=default_args,
    schedule="0 6 * * *",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=["novabank", "external"],
) as dag:
    ingest = BashOperator(task_id="ingest_external", bash_command=CLI + " ingest-external")
    dbt_external = BashOperator(task_id="dbt_external", bash_command=CLI + " dbt --select models/external")
    ingest >> dbt_external

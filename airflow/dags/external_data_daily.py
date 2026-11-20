"""
NovaBank external_data_daily: polite ingestion of public data (ECB FX, World Bank, FRED, ECB RSS),
then the external dbt models and a source-freshness check. Ingestion is change-detected (SHA-256) and idempotent.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

PROJECT_ROOT = os.environ.get("AIRFLOW_PROJECT_ROOT", "/opt/airflow/project")
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

default_args = {"owner": "novabank-analytics", "retries": 3, "retry_delay": timedelta(minutes=10),
                "execution_timeout": timedelta(hours=1)}


def _t():
    from src.orchestration import tasks
    return tasks


def _fail_if_sources_failed(**ctx):
    res = ctx["ti"].xcom_pull(task_ids="ingest_external")
    if res and res.get("failed"):
        raise RuntimeError(f"external sources failed: {res['failed']}")


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
    ingest = PythonOperator(task_id="ingest_external", python_callable=lambda **_: _t().ingest_external())
    check = PythonOperator(task_id="check_ingest_results", python_callable=_fail_if_sources_failed)
    dbt_external = PythonOperator(task_id="dbt_external", python_callable=lambda **_: _t().run_dbt("models/external"))
    ingest >> check >> dbt_external

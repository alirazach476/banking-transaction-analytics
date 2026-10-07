"""
NovaBank banking_daily_pipeline — daily ELT orchestration.

Docker:  project root mounted at /opt/airflow/project
Local:   set AIRFLOW_PROJECT_ROOT to repo root; PYTHONPATH=.

Disclaimer: Synthetic banking data for portfolio demonstration only.
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.bash import BashOperator
from airflow.operators.empty import EmptyOperator
from airflow.operators.python import PythonOperator

PROJECT_ROOT = os.environ.get("AIRFLOW_PROJECT_ROOT", "/opt/airflow/project")
PYTHON = os.environ.get("AIRFLOW_PYTHON", "python")
PIPELINE_MODE = os.environ.get("PIPELINE_MODE", "incremental")

default_args = {
    "owner": "novabank-analytics",
    "depends_on_past": False,
    "email_on_failure": False,
    "email_on_retry": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
    "execution_timeout": timedelta(hours=2),
}

DISCLAIMER = (
    "This project uses synthetic banking data generated solely for demonstrating "
    "data engineering, analytics, and transaction-monitoring capabilities. "
    "It does not represent real customer or banking data."
)


def _bootstrap_path() -> Path:
    root = Path(PROJECT_ROOT)
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    return root


def _ingest_subset(source_names: list[str], mode: str | None = None) -> int:
    """Load a subset of SOURCE_MAP entries into raw."""
    from config.settings import get_settings
    from src.ingestion.load_raw import (
        SOURCE_MAP,
        _finish_run,
        _get_watermark,
        _load_table,
        _start_run,
    )
    from src.utils.db import get_engine, run_ddl

    _bootstrap_path()
    settings = get_settings()
    mode = mode or PIPELINE_MODE
    engine = get_engine()
    run_ddl(engine)
    run_id = _start_run(engine, f"ingest_{'_'.join(source_names)}", mode)
    total = 0
    try:
        root = settings.data_source_dir
        for name, rel, table, key, system in SOURCE_MAP:
            if name not in source_names:
                continue
            wm = _get_watermark(engine, name) if mode == "incremental" else None
            total += _load_table(
                engine, run_id, name, root / rel, table, key, system, mode, wm
            )
        _finish_run(engine, run_id, "SUCCESS", total)
    except Exception:
        _finish_run(engine, run_id, "FAILED", total, failed=1)
        raise
    return total


def check_sources_callable(**context) -> None:
    root = _bootstrap_path()
    required = [
        root / "data" / "source" / "core_banking" / "transactions.csv",
        root / "data" / "source" / "customer_system" / "customers.csv",
    ]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError(
            f"Source check failed. Missing: {missing}. Run data generation first."
        )
    context["ti"].xcom_push(key="source_check", value="OK")


def ingest_customer_data_callable(**_) -> int:
    return _ingest_subset(["customers"])


def ingest_account_data_callable(**_) -> int:
    return _ingest_subset(["accounts", "branches"])


def ingest_transaction_data_callable(**_) -> int:
    return _ingest_subset(["transactions", "transfers"])


def ingest_card_data_callable(**_) -> int:
    return _ingest_subset(["merchants", "cards", "card_transactions"])


def ingest_atm_data_callable(**_) -> int:
    return _ingest_subset(["atm_transactions"])


def update_audit_callable(**context) -> None:
    from datetime import timezone

    from sqlalchemy import text

    from src.utils.db import get_engine

    _bootstrap_path()
    run_id = str(uuid.uuid4())
    engine = get_engine()
    now = datetime.now(timezone.utc)
    logical_date = context.get("logical_date") or now

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO audit.pipeline_runs
                    (run_id, pipeline_name, start_time, end_time, status, mode, notes)
                VALUES
                    (:run_id, 'banking_daily_pipeline', :start, :end, 'SUCCESS', :mode, :notes)
                """
            ),
            {
                "run_id": run_id,
                "start": logical_date,
                "end": now,
                "mode": PIPELINE_MODE,
                "notes": f"Airflow DAG completed. {DISCLAIMER}",
            },
        )


bash_prefix = f"cd '{PROJECT_ROOT}' && export PYTHONPATH='{PROJECT_ROOT}' && "

with DAG(
    dag_id="banking_daily_pipeline",
    description="NovaBank daily ingest, transform, reconcile, and anomaly detection",
    default_args=default_args,
    schedule="@daily",
    start_date=datetime(2024, 1, 1),
    catchup=False,
    tags=["novabank", "banking", "elt", "synthetic"],
    doc_md=f"""
# banking_daily_pipeline

{DISCLAIMER}

## Task graph
```
start → check_sources → [parallel ingest tasks] → validate_data → load_raw
  → dbt_staging → dbt_warehouse → dbt_analytics → reconciliation
  → anomaly_detection → data_quality_tests → update_audit → end
```

## Local execution
```bash
export AIRFLOW_PROJECT_ROOT="/path/to/Bank Anaylsis"
export PYTHONPATH="$AIRFLOW_PROJECT_ROOT"
airflow dags test banking_daily_pipeline
```
""",
) as dag:

    start = EmptyOperator(task_id="start")

    check_sources = PythonOperator(
        task_id="check_sources",
        python_callable=check_sources_callable,
    )

    ingest_customer_data = PythonOperator(
        task_id="ingest_customer_data",
        python_callable=ingest_customer_data_callable,
    )

    ingest_account_data = PythonOperator(
        task_id="ingest_account_data",
        python_callable=ingest_account_data_callable,
    )

    ingest_transaction_data = PythonOperator(
        task_id="ingest_transaction_data",
        python_callable=ingest_transaction_data_callable,
    )

    ingest_card_data = PythonOperator(
        task_id="ingest_card_data",
        python_callable=ingest_card_data_callable,
    )

    ingest_atm_data = PythonOperator(
        task_id="ingest_atm_data",
        python_callable=ingest_atm_data_callable,
    )

    validate_data = BashOperator(
        task_id="validate_data",
        bash_command=bash_prefix + f"{PYTHON} -m src.validation.run_validation",
    )

    load_raw = BashOperator(
        task_id="load_raw",
        bash_command=bash_prefix + f"{PYTHON} -m src.ingestion.load_raw {PIPELINE_MODE}",
    )

    dbt_staging = BashOperator(
        task_id="dbt_staging",
        bash_command=(
            bash_prefix
            + "cd dbt && dbt run --profiles-dir . --select staging.* "
            "&& dbt test --profiles-dir . --select staging.*"
        ),
    )

    dbt_warehouse = BashOperator(
        task_id="dbt_warehouse",
        bash_command=(
            bash_prefix
            + "cd dbt && dbt run --profiles-dir . --select warehouse.* "
            "&& dbt test --profiles-dir . --select warehouse.*"
        ),
    )

    dbt_analytics = BashOperator(
        task_id="dbt_analytics",
        bash_command=(
            bash_prefix
            + "cd dbt && dbt run --profiles-dir . --select analytics.* "
            "&& dbt test --profiles-dir . --select analytics.*"
        ),
    )

    reconciliation = BashOperator(
        task_id="reconciliation",
        bash_command=bash_prefix + f"{PYTHON} -m src.validation.reconciliation",
    )

    anomaly_detection = BashOperator(
        task_id="anomaly_detection",
        bash_command=bash_prefix + f"{PYTHON} -m src.anomaly_detection.run_detection {PIPELINE_MODE}",
    )

    data_quality_tests = BashOperator(
        task_id="data_quality_tests",
        bash_command=bash_prefix + f"{PYTHON} -m pytest tests/test_validation.py -v --tb=short -q",
    )

    update_audit = PythonOperator(
        task_id="update_audit",
        python_callable=update_audit_callable,
    )

    end = EmptyOperator(task_id="end")

    # Task graph per brief
    start >> check_sources
    check_sources >> [
        ingest_customer_data,
        ingest_account_data,
        ingest_transaction_data,
        ingest_card_data,
        ingest_atm_data,
    ]
    [
        ingest_customer_data,
        ingest_account_data,
        ingest_transaction_data,
        ingest_card_data,
        ingest_atm_data,
    ] >> validate_data >> load_raw
    load_raw >> dbt_staging >> dbt_warehouse >> dbt_analytics
    dbt_analytics >> reconciliation >> anomaly_detection >> data_quality_tests
    data_quality_tests >> update_audit >> end

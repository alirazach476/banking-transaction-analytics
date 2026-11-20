# Airflow image with the project baked in and a separate virtualenv for task code.
# Tasks (BashOperator -> python -m src.orchestration.cli) run in /opt/airflow/pyenv, so the project's pandas/SQLAlchemy 2/dbt
# versions do not clash with Airflow's own pinned dependencies. Build context: repository root.
FROM apache/airflow:2.8.1-python3.11

USER root
RUN apt-get update && apt-get install -y --no-install-recommends libgomp1 libpq5 && rm -rf /var/lib/apt/lists/*
USER airflow

COPY --chown=airflow:root requirements.txt /tmp/requirements.txt
RUN python -m venv /opt/airflow/pyenv \
 && grep -v -i "embedded-postgres" /tmp/requirements.txt > /tmp/req-airflow.txt \
 && PIP_USER=false /opt/airflow/pyenv/bin/pip install --no-cache-dir -r /tmp/req-airflow.txt

ENV AIRFLOW_PYTHON=/opt/airflow/pyenv/bin/python \
    AIRFLOW_PROJECT_ROOT=/opt/airflow/project \
    PATH="/opt/airflow/pyenv/bin:${PATH}"
# dbt is invoked as `python -m dbt.cli.main`, which resolves inside the venv

COPY --chown=airflow:root . /opt/airflow/project
COPY --chown=airflow:root airflow/dags /opt/airflow/dags

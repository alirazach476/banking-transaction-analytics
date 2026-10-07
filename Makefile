# NovaBank Banking Transaction Analytics Pipeline
# Usage: make <target>
# On Windows without make, use: python -m src.pipeline.run_pipeline --help
# or run the equivalent python/docker commands listed in README.

.PHONY: setup generate-data generate-data-full validate ingest dbt-build \
        anomaly-detection reconcile test pipeline clean docker-up docker-down \
        insights help

PYTHON ?= python
export PYTHONPATH := .

help:
	@echo "NovaBank Pipeline Targets:"
	@echo "  setup               Install deps + copy .env"
	@echo "  docker-up           Start Postgres (+ Airflow)"
	@echo "  generate-data       Generate synthetic source data (demo volumes)"
	@echo "  generate-data-full  Generate full portfolio volumes"
	@echo "  validate            Run data quality checks"
	@echo "  ingest              Load source CSVs into raw schema"
	@echo "  dbt-build           Run dbt build"
	@echo "  anomaly-detection   Run anomaly detection"
	@echo "  reconcile           Run source vs warehouse reconciliation"
	@echo "  insights            Generate business insights from DB"
	@echo "  test                Run pytest"
	@echo "  pipeline            Full end-to-end pipeline"
	@echo "  clean               Remove generated data and caches"

setup:
	@if not exist .env copy .env.example .env
	$(PYTHON) -m pip install -r requirements.txt
	@echo "Setup complete. Edit .env as needed."

docker-up:
	docker compose up -d postgres
	@echo "Waiting for Postgres..."
	@$(PYTHON) -c "import time; time.sleep(5)"
	@echo "Postgres should be ready on localhost:5432"

docker-up-airflow:
	docker compose up -d

docker-down:
	docker compose down

generate-data:
	$(PYTHON) -m src.data_generation.generate_all

generate-data-full:
	$(PYTHON) -c "import os; os.environ['NUM_CUSTOMERS']='100000'; os.environ['NUM_ACCOUNTS']='150000'; os.environ['NUM_TRANSACTIONS']='2000000'; os.environ['NUM_BRANCHES']='500'; os.environ['NUM_MERCHANTS']='20000'; os.environ['NUM_CARDS']='200000'; os.environ['NUM_TRANSFERS']='300000'; os.environ['NUM_ATM_TRANSACTIONS']='400000'; os.environ['NUM_CARD_TRANSACTIONS']='800000'; from src.data_generation.generate_all import main; main()"

validate:
	$(PYTHON) -m src.validation.run_validation

ingest:
	$(PYTHON) -m src.ingestion.load_raw

dbt-deps:
	cd dbt && dbt deps

dbt-build:
	cd dbt && dbt build --profiles-dir .

anomaly-detection:
	$(PYTHON) -m src.anomaly_detection.run_detection

reconcile:
	$(PYTHON) -m src.validation.reconciliation

insights:
	$(PYTHON) -m src.utils.generate_insights

test:
	$(PYTHON) -m pytest tests/ -v --tb=short

pipeline:
	$(PYTHON) -m src.pipeline.run_pipeline

clean:
	@$(PYTHON) -c "import shutil, pathlib; \
paths=['data/source/core_banking','data/source/card_system','data/source/atm_system','data/source/customer_system','data/source/branch_system','data/raw','data/processed','dbt/target','dbt/logs','.pytest_cache']; \
[shutil.rmtree(p, ignore_errors=True) for p in paths]; \
print('Cleaned generated artifacts')"

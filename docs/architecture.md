# NovaBank Architecture

> **Disclaimer:** This project uses synthetic banking data generated solely for demonstrating data engineering, analytics, and transaction-monitoring capabilities. It does not represent real customer or banking data.

## System Context

NovaBank operates multiple legacy-style source systems that export CSV extracts. The analytics platform consolidates these into PostgreSQL, transforms them with dbt into a dimensional warehouse, and serves BI and monitoring use cases.

```mermaid
flowchart LR
    subgraph External["Simulated Source Systems"]
        direction TB
        S1[Core Banking]
        S2[Card System]
        S3[ATM System]
        S4[Customer System]
        S5[Branch System]
    end

    subgraph Platform["NovaBank Analytics Platform"]
        direction TB
        L1[Ingestion Layer]
        L2[Raw Layer]
        L3[Quality Layer]
        L4[dbt ELT]
        L5[Warehouse]
        L6[Analytics Marts]
        L7[Anomaly Detection]
        L8[Power BI]
    end

    S1 & S2 & S3 & S4 & S5 --> L1 --> L2 --> L3 --> L4
    L4 --> L5 --> L6
    L5 --> L7
    L6 & L7 --> L8
```

---

## Layered Pipeline

```mermaid
flowchart TB
    subgraph Layer0["Layer 0 — Generation"]
        PY[src/data_generation/generate_all.py]
        CSV[data/source/**]
    end

    subgraph Layer1["Layer 1 — Ingestion"]
        ING[src/ingestion/load_raw.py]
        RAW[(PostgreSQL: raw)]
    end

    subgraph Layer2["Layer 2 — Data Quality"]
        VAL[src/validation/run_validation.py]
        AUD[(PostgreSQL: audit)]
    end

    subgraph Layer3["Layer 3 — Transformation (dbt)"]
        STG[(staging views)]
        INT[(intermediate tables)]
        WH[(warehouse dims/facts)]
        AN[(analytics marts)]
    end

    subgraph Layer4["Layer 4 — Monitoring & Analytics"]
        AD[src/anomaly_detection/]
        MON[(monitoring)]
        SQL[sql/analytics/]
        PBI[Power BI]
    end

    subgraph Layer5["Layer 5 — Orchestration"]
        CLI[src/pipeline/run_pipeline.py]
        AF[Airflow: banking_daily_pipeline]
    end

    PY --> CSV --> ING --> RAW
    RAW --> VAL --> AUD
    RAW --> STG --> INT --> WH --> AN
    WH --> AD --> MON
    AN --> SQL & PBI
    CLI & AF -.-> PY & ING & VAL & STG & WH & AN & AD
```

---

## PostgreSQL Schema Layout

| Schema | Role |
|--------|------|
| `raw` | As-ingested TEXT columns; preserves source quirks |
| `staging` | dbt views: typed, cleaned, deduplicated |
| `intermediate` | Business logic, enrichments, feature engineering |
| `warehouse` | Star schema dimensions and facts |
| `analytics` | Business-facing marts (denormalized for BI) |
| `audit` | Pipeline runs, DQ results, watermarks, reconciliation |
| `monitoring` | Transaction anomaly results |

DDL: `sql/ddl/01_create_schemas.sql` through `05_create_airflow_db.sql`.

---

## Source System Integration

Each source system uses slightly different column naming and formats:

| System | Example entities | Notable schema differences |
|--------|------------------|----------------------------|
| Core Banking | accounts, transactions, transfers | Standard banking field names |
| Card System | cards, merchants, card_transactions | `card_txn_id`, `timestamp` vs `transaction_timestamp` |
| ATM System | atm_transactions | `atm_txn_id`, `atm_id` |
| Customer System | customers | Demographics focus |
| Branch System | branches | Branch metadata |

Ingestion standardizes via dbt staging models (`stg_*`).

---

## dbt Model Layers

```mermaid
flowchart LR
    RAW2[raw.*] --> STG2[staging.stg_*]
    STG2 --> INT2[intermediate.int_*]
    INT2 --> DIM[warehouse.dim_*]
    INT2 --> FACT[warehouse.fact_*]
    DIM & FACT --> MART[analytics.mart_*]
```

- **Staging:** rename, cast, dedupe, status normalization
- **Intermediate:** customer/account metrics, channel rollups, anomaly features
- **Warehouse:** SCD2 dimensions, incremental facts
- **Analytics:** KPI-ready marts for Power BI

---

## Anomaly Detection Architecture

```mermaid
flowchart LR
    FT[fact_transactions] --> RB[Rule-Based Engine]
    FT --> ZS[Z-Score Statistical]
    FT --> IF[Isolation Forest]
    RB & ZS & IF --> MERGE[Score Merge & Severity]
    MERGE --> TA[(monitoring.transaction_anomalies)]
```

Three independent scorers combine into a unified record with `anomaly_reason` (pipe-delimited) and `severity` (Low → Critical). This is a **Transaction Anomaly Detection Prototype**, not a production fraud engine.

---

## Orchestration Options

### Python CLI (primary for local dev)

`src/pipeline/run_pipeline.py` runs all eight steps sequentially with audit logging.

### Apache Airflow

DAG `banking_daily_pipeline` (`airflow/dags/banking_daily_pipeline.py`):

- Parallel ingestion tasks per entity group
- Sequential dbt layers (staging → warehouse → analytics)
- Reconciliation and anomaly detection after transforms
- Retries with exponential backoff

Docker mounts project at `/opt/airflow/project` for container execution.

---

## Deployment Topology (Local)

```mermaid
flowchart TB
    subgraph Docker["Docker Compose"]
        PG[(postgres:16)]
        AW_W[airflow-webserver :8080]
        AW_S[airflow-scheduler]
    end

    subgraph Host["Developer Machine"]
        PY2[Python pipeline]
        DBT[dbt CLI]
        PBI2[Power BI Desktop]
    end

    PY2 & DBT --> PG
    AW_W & AW_S --> PG
    PBI2 -->|DirectQuery/Import| PG
```

**Embedded Postgres fallback:** When Docker is unavailable, `scripts/start_embedded_postgres.py` provisions Postgres under `.pgdata/` and writes connection settings to `.env`.

---

## Cross-Cutting Concerns

| Concern | Implementation |
|---------|----------------|
| Configuration | `.env` + `config/settings.py` (Pydantic) |
| Idempotency | Unique indexes on raw keys; dbt incremental facts |
| Incremental load | `updated_at` watermark in `audit.pipeline_watermarks` |
| Observability | `audit.pipeline_runs`, `audit.data_quality_results` |
| Testing | pytest in `tests/` |
| Reconciliation | `src/validation/reconciliation.py` + SQL |

See [cloud_architecture.md](cloud_architecture.md) for AWS, Azure, and GCP migration paths.

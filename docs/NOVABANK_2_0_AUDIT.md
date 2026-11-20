# NovaBank 2.0 — Repository Audit (Phase 0)

Audit date: 2026-11-20. Baseline: `pytest tests` = **17 passed**. All data is synthetic.

## 1. Existing functionality
| Area | What exists |
|---|---|
| Generation | `src/data_generation/generate_all.py` — seeded (`RANDOM_SEED`) numpy generator for customers, accounts, branches, merchants, cards, transactions, transfers, ATM and card transactions. Writes CSVs per source system into `data/source/`. Injects anomalies (7 types) and DQ defects (dups, nulls, status case variants, timestamp format, bad account FK). |
| Ingestion | `src/ingestion/load_raw.py` — CSV -> `raw.*` (all TEXT), full (truncate+insert) or incremental (watermark + insert-if-not-exists), audit rows. |
| Validation | `src/validation/` — SQL DQ checks persisted to `audit.data_quality_results`; source-vs-warehouse and balance reconciliation. |
| dbt | 9 staging, 6 intermediate, 8 dims, 4 facts, 9 analytics models (~36) with unique/not_null/relationships tests; `dim_customer` is a hand-rolled SCD2 model. No snapshots, no singular/custom generic tests, no source freshness. |
| Anomalies | Rule-based, per-customer z-score, Isolation Forest; persisted to `monitoring.transaction_anomalies`. Config in `config/anomaly_config.yaml`. |
| Orchestration | One DAG `airflow/dags/banking_daily_pipeline.py` (@daily, retries=2). docker-compose with Postgres 16 + Airflow 2.8 (LocalExecutor). |
| Presentation | **Static HTML/JS** dashboard (`web/`, `dashboards/`) fed by `dashboards/data/bi_dashboard.json`, deployed on Vercel. *It is not React.* Power BI spec/DAX docs only — no `.pbix`. |
| Docs/tests | README, 14 docs, PDF report; 3 test modules (generation, anomaly, validation). |

## 2. Existing architecture
`CSV sources -> raw (TEXT) -> dbt staging(view) -> intermediate(view) -> warehouse(dims/facts) -> analytics marts` plus `audit` and `monitoring` schemas. Python orchestrator `run_pipeline.py` (8 steps) and one Airflow DAG. Local DB via embedded Postgres (`.pgdata`) when Docker is unavailable.

## 3. Feature implementation matrix
Legend: ✅ implemented · 🟡 partial · ❌ missing · ⚙️ needs optimization

| # | Feature | Status | Notes |
|---|---|---|---|
| A1 | Seeded deterministic generator | ✅ | |
| A2 | Customers/accounts/branches/merchants/cards/txns/transfers/ATM/card txns | ✅ | Card/ATM txns not linked to core txns |
| A3 | Auth request/response, clearing, settlement, chargeback, reversal, refund events | ❌ | Only a `Reversed` status exists |
| A4 | Exchange rates, payment-failure events, customer activity history | ❌ | |
| A5 | Multi-country / multi-currency | 🟡 | 4 currencies, one country (US) |
| A6 | Seasonality, recurring payments, weekday patterns | 🟡 ⚙️ | Weekday/night bias via slow Python rejection sampling |
| A7 | Chunked generation (low RAM) | ❌ ⚙️ | Whole DataFrames in RAM; per-row Python loops; will not reach 2M rows practically |
| A8 | Account balance consistency | ❌ | Balances random, not derived from txns |
| A9 | Configurable, documented DQ defects; clean vs dirty distinguishable | 🟡 | 3 rates configurable; invalid currency/FK/timestamp defects hard-coded; clean copies only for 3 tables |
| B | External data / scraping | ❌ | No scrapy/bs4/playwright code, no `external_*` schemas |
| C | Payment lifecycle KPIs, decline reasons, settlement reconciliation | ❌ | Existing recon is count/sum + balance only |
| D1 | Watermark ingestion | 🟡 | "Upsert" is insert-if-new (changed rows never update); late-arriving rows older than watermark are lost |
| D2 | Indexing, partitioning, pooling, COPY bulk load | ❌ ⚙️ | `to_sql(method="multi")`; indexes only on anomalies table |
| D3 | PySpark + Pandas benchmark | ❌ | pyspark not installed; only Java 8 locally |
| D4 | Parquet partitioned storage, retention | ❌ | pyarrow present but unused |
| D5 | Observability | 🟡 | `audit.pipeline_runs`/`source_ingestion` exist; no per-task metrics, retries, freshness |
| E1 | dbt staging/intermediate/warehouse/analytics | ✅ | Folder layout differs (`analytics/` vs `marts/<domain>/`) |
| E2 | Lifecycle facts, dims (country, currency, decline_reason), forecasting mart | ❌ | |
| E3 | True SCD2 snapshots, singular/generic tests, freshness, docs | 🟡 | |
| F1 | Rule/z-score/Isolation Forest anomalies | ✅ | Persistence lacks model name/version/feature values |
| F2 | Statistical testing (chi², t, ANOVA, GLM, CI, effect sizes) | ❌ | |
| F3 | LOF, geographic simulation | 🟡 | Velocity/night/behavior-change rules exist |
| F4 | Predictive models, CV, tuning, SHAP | ❌ | |
| G | Tableau datasets/flows/calc fields | ❌ | Only Power BI markdown specs + HTML BI page |
| H | FastAPI + 10 frontend pages | ❌ | Static 2-page site, no API |
| I | 7 Airflow DAGs | 🟡 | 1 of 7 |
| J | Tests: unit/integration/db/api/scraper/idempotency | 🟡 | 17 tests; no DB, dbt, API, scraper tests |
| K | Benchmarks 100K–2M | ❌ | Only 100K notes in `docs/performance.md` |
| L | Docs set | 🟡 | Older lowercase docs exist — extend rather than duplicate |

## 4. Technical debt
- Per-row Python loops in generator (`generate_transactions`; `inject_data_quality_issues` uses `.at` in loops).
- `burst = 8 if anomaly_type[anom_idx[0]] else 8` is a no-op conditional; burst txn ids (`txn_counter = n`) are safe only because they start after `n`.
- `execute_sql_file` splits on `;` (breaks on functions/DO blocks).
- No connection-pool tuning; `to_sql method="multi"` is slow.
- `requirements.txt` pins `numpy<2`, `dbt<1.9`, while the local env has numpy 2.1 / dbt-core 1.9.1 — dependency drift.
- docker-compose embeds the dev DB password in plaintext (dev-only; should read from env).

## 5. Missing capabilities
Every ❌ row above: lifecycle events, FX/external data, settlement reconciliation, stats/ML, FastAPI, Tableau assets, PySpark/Parquet, scale benchmarks.

## 6. Database design limitations
Raw is all-TEXT (fine for bronze); no partitioning; no FK constraints; facts use delete+insert on `updated_at` (late data with old `updated_at` skipped); no currency/FX handling; no lifecycle entities.

## 7. Pipeline performance limitations
Generation and ingestion are single-threaded, in-memory, row-loop based; default full reload; anomaly detection loads all transactions into pandas. Not validated beyond ~100K rows.

## 8. Dashboard limitations
Static snapshot JSON (no live API); 2 pages; no drill-down/filters; no lifecycle/risk/ops views; no Tableau.

## 9. Testing coverage gaps
No DB-backed tests; dbt not exercised from pytest; no idempotency, late-arrival or empty-dataset tests; no API/scraper/model-evaluation tests.

## 10. Recommended implementation sequence
1. Phase 1 — vectorised, chunked, configurable generator extension (new modules; existing generator kept working).
2. Phase 2 — payment lifecycle generator + reconciliation engine + `payments` DDL + tests.
3. Phase 3 — external data subsystem (API-first: ECB, World Bank, FRED CSV; robots.txt-aware HTML scraper) + `external_*` schemas.
4. Phase 4 — COPY loading, indexes/partitions, Parquet, Pandas-vs-Spark benchmark (Spark only if runnable).
5. Phase 5 — dbt additions (lifecycle facts, dims, snapshots, custom tests, marts).
6. Phase 6 — statistics, ML, SHAP.
7. Phase 7 — Tableau-ready extracts + guide.
8. Phase 8 — FastAPI + extend static dashboard.
9. Phase 9 — Airflow DAGs.
10. Phase 10 — benchmarks, docs, regression.

## Environment findings
Python 3.12; pandas 2.2, numpy 2.1, scikit-learn 1.9, statsmodels, xgboost, shap, fastapi, bs4, pyarrow, dbt-postgres 1.8, embedded Postgres 18 are installed. **Not installed:** scrapy, playwright, pyspark. Docker CLI present (daemon not verified); Java 8 only. The Postgres instance was down at audit time (restartable via `scripts/start_embedded_postgres.py`).

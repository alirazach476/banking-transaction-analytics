# NovaBank premium analytics UI: audit and plan

Phase 1 deliverable. Facts below come from inspecting the repository and the live Postgres database, not from assumptions.

## 1. What exists today
- **Frontend:** `web/react-app` (Vite + React 18 + Recharts), no router, two tabs (synthetic payments with live API; real-data Pakistan analysis with 52 static charts from `public/analysis.json`). Served by FastAPI at `/app/`. Tests: vitest (5), Playwright (8).
- **Backend:** FastAPI `src/api/main.py` (12 routes: health, models, KPI summary/daily, decline reasons, reconciliation, three scoring endpoints), optional `X-API-Key`, in-process rate limit, model warm-up. Read-only SQL via SQLAlchemy.
- **Database (Postgres):** two synthetic data domains plus pipeline metadata.
  - *Payments domain* (493,199 payments, 1.92M lifecycle events, 454,881 settlements; 2023-01 to 2025-12): `intermediate.int_payment_outcomes`, `int_card_payments`, `raw.payment_transactions` (card, customer, merchant id/category, channel, country), `raw.payment_lifecycle_events` (AUTH_REQUEST/RESPONSE, CLEARING, SETTLEMENT, REFUND, REVERSAL, CHARGEBACK), `analytics.mart_payment_kpis_daily`, `mart_decline_reasons`, `payments.investigation_queue` (15,783 reconciliation exceptions).
  - *Core-banking domain* (101,600 transactions, 5,000 customers, 7,500 accounts, 50 branches, 1,000 merchants, 40,000 card transactions; 2023-01-01 to 2025-12-30): star schema `warehouse.*`, marts `analytics.mart_branch_performance`, `mart_customer_activity`, `mart_channel_performance`, `mart_monthly_transactions`, `mart_transaction_failures`, `mart_anomaly_monitoring`.
  - *Anomalies:* `monitoring.transaction_anomalies` (8,645 flagged: rule-based score, Isolation Forest score, severity, reason) and 3,597 injected-anomaly labels in `warehouse.fact_transactions` (a synthetic ground truth that allows a rule-vs-ML comparison).
  - *Pipeline metadata:* `audit.pipeline_runs`, `data_quality_results`, `source_ingestion`, `reconciliation_results`, `payments.reconciliation_runs`; dbt artifacts in `dbt/target` (`run_results.json`, `manifest.json`); Airflow DAG definitions in `airflow/dags` (Airflow itself is not running persistently).
  - *External aggregates* (DuckDB warehouse, not Postgres): SBP, World Bank, BIS, ECB, FRED, Global Findex (already charted in `analysis.json`).

## 2. Data gaps and the decisions made (nothing is invented)
| Requested | What the data has | Decision |
|---|---|---|
| Maps | No latitude/longitude anywhere. Branches are in 25 US cities, customers have region only, merchants have city/region | Branch map uses **city centroids from the public GeoNames gazetteer** (CC BY), clearly labelled "city centroid, not branch address". No map for customers/merchants (region only); region comparisons use bars/treemap. |
| Currency | Transaction amounts are in many currencies (payments: USD, GBP, EUR, CAD, INR, AED, PKR; core: USD, GBP, EUR, CAD) | All **value** KPIs are converted to USD with the dataset's own synthetic FX table (`raw.fx_rates_synthetic`, USD per unit, by date). Rows with a missing or unknown currency are excluded from value (still counted in volume) and the count is shown. |
| Fraud rate | No confirmed-fraud labels | The UI shows **anomaly rate** (flagged / transactions) and **chargeback rate**, never "fraud rate"; anomaly is explicitly not confirmed fraud. |
| Investigation status for anomalies | None stored | New table `monitoring.anomaly_investigations` (status, assignee, note) with an update endpoint; default status NEW. |
| Customer cohorts, RFM, CLV | Derivable from transactions | Computed in SQL; RFM = quintile scores of recency/frequency/monetary; CLV is a **simple documented estimate** (average monthly completed value x assumed margin x expected lifetime), shown with assumptions, not as fact. |
| Airflow status | No persistent Airflow | API integration through the Airflow REST API when `AIRFLOW_BASE_URL` is set; otherwise the page says "not connected" and shows only real pipeline-run history from `audit.pipeline_runs` and the DAG definitions parsed from the repo. No fake DAG runs. |
| dbt status | `run_results.json` covers only the last invocation | Shows the last run's real results plus the model/test inventory from `manifest.json`. |
| Authentication | Optional shared `X-API-Key`; no user accounts | Kept as is. The profile menu shows the real state (API key set / local development), no invented user. |
| Real vs synthetic | Everything transactional is synthetic | Every page carries a data-domain badge: Synthetic (payments), Synthetic (core banking), Real external aggregate. |

## 3. Architecture
- **Backend:** new routers under `src/api/dash/` mounted on the existing app (existing routes untouched): overview, payments, anomalies, customers, merchants, branches, generic server-side tables (whitelisted columns, parameterised SQL, pagination/sort/filters, CSV and XLSX export), observability, search. Short TTL cache for expensive aggregates; heavy aggregation in SQL.
- **Frontend:** React Router (`/app/...`, FastAPI SPA fallback), TanStack Query (dedupes and caches requests), design-system components, ECharts for complex charts (Sankey, treemap, heatmap, scatter, funnel), Recharts for simple ones, MapLibre for the branch map, TanStack Table for all tables. D3 is not needed (ECharts covers every requested chart).
- **Theme:** dark navy default and light theme from CSS variables; Inter font bundled locally; responsive sidebar (collapsible; drawer on mobile).

## 4. Phases
1. Audit and this plan (done).
2. Design system and application shell.
3. Executive overview.
4. Payment intelligence.
5. Fraud and anomaly intelligence.
6. Customer, merchant, branch analytics (and branch map).
7. Global financial intelligence (external aggregates).
8. Transaction explorer and advanced tables.
9. Data engineering and observability.
10. Testing (API values vs SQL, routes, tables, export, themes, responsive), performance, deployment, docs.

Each phase ends with: run the app, test, fix, check responsive behaviour, update `docs/UI_UPGRADE_PROGRESS.md`.

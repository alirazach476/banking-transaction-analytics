# NovaBank 2.0 — Implementation Progress

Status: ✅ complete & validated · 🟡 partial · ⏳ pending. Last updated 2026-11-20.
Test suite: **53 passed** (17 original + 16 payment tests + 4 payment DB tests + 16 external-data tests).

| Phase | Scope | Status | Validation / notes |
|---|---|---|---|
| 0 | Repository audit + plan | ✅ | `docs/NOVABANK_2_0_AUDIT.md`; baseline 17 tests passed before changes |
| 1 | Data architecture & event generation | 🟡 | **Done:** chunked, vectorised, seeded payment generator (random + recurring + fraud-pattern streams, seasonality, FX), 7 labelled configurable defect types with clean/dirty separation. **Pending:** chunked rewrite of the legacy generator (customers/accounts/ATM/transfers at 100K+/2M scale), account-balance consistency, customer-activity history, branch/merchant extensions |
| 2 | Payment lifecycle & reconciliation | 🟡 | **Done:** 7 lifecycle event types, 8 decline reasons, KPI module with documented denominators, settlement reconciliation (6 exception types) validated against injected ground truth (≥99 % recall, 100 % precision), persisted investigation queue (idempotent upsert), COPY loader. **Pending:** processing-cost / currency-exposure metrics (need fee schedules from Phase 3), dbt lifecycle models (Phase 5) |
| 3 | Web scraping / external data | 🟡 | **Done & validated (tests + live run):** polite client (robots.txt, throttle, retry), ECB FX / World Bank / FRED / ECB RSS ingestion, `external_raw`/`external_staging`/`external_analytics` schemas, snapshot log with SHA-256 change detection, idempotent upserts. **Pending:** dbt `external_analytics` models (Phase 5), Airflow DAG (Phase 9), payment-network fee schedules and SBP/Visa/Mastercard pages (no verified machine-readable/permitted source; Scrapy/Playwright deliberately not added), COPY-based upsert for speed |
| 4 | PostgreSQL tuning + PySpark/Parquet | 🟡 | **Done (measured, `docs/PHASE4_BENCHMARKS.md`):** payment COPY load, monthly-partitioned + indexed lifecycle table vs heap, Parquet export, DuckDB-on-Parquet timings. **Pending:** PySpark (not installed, Java 8 only), tuning of transactions/settlements tables, EXPLAIN plans in docs |
| 5 | dbt analytics engineering | ✅ (scope below) | **Done (dbt build: 17 PASS, 0 fail, ~49 s):** payment staging views (dedupe, safe casts, status normalised from event_type), `int_payment_outcomes` (493,199 payments), `mart_payment_kpis_daily`, `mart_decline_reasons`, 10 tests. Cross-check vs `src/payments/kpis.py` on the same data: approved 467,001 (dbt) vs 466,004 (Python), declined 24,226 vs 24,281; differences are expected (dbt repairs dirty status values like APPROVD and drops 987 payments with invalid authorization timestamps from daily marts; Python counts only exact APPROVED). **Also done:** `mart_settlement_daily` (1,106 days; orphan + duplicate settlement counts), `external_analytics.mart_fx_monthly` (10,422 rows), source freshness check on `external_raw.http_snapshots` (PASS), `dbt docs generate`. **Not done:** reconciliation exception models (reconciliation stays in `src/payments/reconciliation.py`), indicator marts, snapshots (SCD2) |
| 6 | Statistics & ML | 🟡 | **Done (`docs/PHASE6_RESULTS.md`, `scripts/phase6_stats_ml.py`):** statsmodels logit recovers all 6 true generator coefficients (every 95% CI covers truth, n=394,398); chi-square + Mann-Whitney tests; XGBoost with time-based split (ROC-AUC 0.635; 0.606 excluding forced expired/blocked declines — modest because the true logit has weak signal); SHAP importances. **Pending:** fraud-pattern / anomaly model, forecasting, customer segmentation, hyper-parameter search, model persistence/serving |
| 7 | Tableau / BI | ⏳ | |
| 8 | FastAPI & frontend | ⏳ | Existing dashboard is static HTML, not React |
| 9 | Airflow | ⏳ | |
| 10 | Testing, benchmarks, docs | ⏳ | |

## Measured so far (real runs, this machine)
| Run | Result |
|---|---|
| Payment generation, 500,000 payment attempts, chunk 100,000, defects on, 6 CSV outputs | **120.3 s**; 493,199 transactions (incl. recurring/burst streams), 1,918,653 events, 454,881 settlements, 9,563 injected settlement exceptions; 285 MB dirty + 247 MB clean on disk |

| External ingestion, live (2026-11-20) | all 8 sources succeeded; immediate re-run: 8/8 UNCHANGED, 0 writes; ECB full history 222,108 rows loaded in ~3 min (uncontrolled timing) |

No 1M / 2M benchmark, ingestion timing, dbt timing or Spark comparison has been run yet; none is claimed.

## Environment notes
* Embedded PostgreSQL restarts on a **new random port** each time `scripts/start_embedded_postgres.py` runs (this session: 60771); `.env` (git-ignored) was updated locally.
* DB-backed tests use a separate `novabank_test` database and skip automatically if no server is reachable.

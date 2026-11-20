# NovaBank 2.0 — Implementation Progress

Status: ✅ complete & validated · 🟡 partial · ⏳ pending. Last updated 2026-11-20.
Test suite: **37 passed** (17 original + 16 payment unit/recon/KPI tests + 4 PostgreSQL-backed tests).

| Phase | Scope | Status | Validation / notes |
|---|---|---|---|
| 0 | Repository audit + plan | ✅ | `docs/NOVABANK_2_0_AUDIT.md`; baseline 17 tests passed before changes |
| 1 | Data architecture & event generation | 🟡 | **Done:** chunked, vectorised, seeded payment generator (random + recurring + fraud-pattern streams, seasonality, FX), 7 labelled configurable defect types with clean/dirty separation. **Pending:** chunked rewrite of the legacy generator (customers/accounts/ATM/transfers at 100K+/2M scale), account-balance consistency, customer-activity history, branch/merchant extensions |
| 2 | Payment lifecycle & reconciliation | 🟡 | **Done:** 7 lifecycle event types, 8 decline reasons, KPI module with documented denominators, settlement reconciliation (6 exception types) validated against injected ground truth (≥99 % recall, 100 % precision), persisted investigation queue (idempotent upsert), COPY loader. **Pending:** processing-cost / currency-exposure metrics (need fee schedules from Phase 3), dbt lifecycle models (Phase 5) |
| 3 | Web scraping / external data | ⏳ | |
| 4 | PostgreSQL tuning + PySpark/Parquet | ⏳ | COPY loader exists for payment tables only; no indexes/partitions/Parquet/Spark yet (pyspark not installed, Java 8 only) |
| 5 | dbt analytics engineering | ⏳ | |
| 6 | Statistics & ML | ⏳ | Decline-model ground-truth coefficients documented in `src/payments/constants.py` for later validation |
| 7 | Tableau / BI | ⏳ | |
| 8 | FastAPI & frontend | ⏳ | Existing dashboard is static HTML, not React |
| 9 | Airflow | ⏳ | |
| 10 | Testing, benchmarks, docs | ⏳ | |

## Measured so far (real runs, this machine)
| Run | Result |
|---|---|
| Payment generation, 500,000 payment attempts, chunk 100,000, defects on, 6 CSV outputs | **120.3 s**; 493,199 transactions (incl. recurring/burst streams), 1,918,653 events, 454,881 settlements, 9,563 injected settlement exceptions; 285 MB dirty + 247 MB clean on disk |

No 1M / 2M benchmark, ingestion timing, dbt timing or Spark comparison has been run yet; none is claimed.

## Environment notes
* Embedded PostgreSQL restarts on a **new random port** each time `scripts/start_embedded_postgres.py` runs (this session: 60771); `.env` (git-ignored) was updated locally.
* DB-backed tests use a separate `novabank_test` database and skip automatically if no server is reachable.

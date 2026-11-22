# Deployment

## Hosted demo (Vercel): https://banking-transaction-analytics.vercel.app

The same React app that runs on localhost, with its analytics API, runs on Vercel as a **read-only snapshot**:

| Piece | Local | Hosted demo |
|---|---|---|
| UI | `web/react-app` served by FastAPI at `/app/` | the same build, served statically at `/app/` (`/` redirects to `/app/overview`) |
| API | FastAPI `src/api` + `src/api/dash` on PostgreSQL | the same `src/api/dash` routers as a Python function (`api/index.py`) |
| Database | PostgreSQL (embedded), dbt marts, `ui` views | one bundled DuckDB file (`data/demo.duckdb`, about 30 MB, opened read-only) |
| Real-data pages | `public/analysis.json` | the same static file |
| Not available | | payment scoring (needs trained XGBoost models) and saving investigation outcomes (read-only); both say so in the UI |

Other URLs on the same site: `/portfolio` (the earlier portfolio page), `/dashboard` (the static BI page), `/docs` (API docs), `/health`.

All transactional data is synthetic. The hosted copy is a snapshot taken from the local database; it does not update by itself.

### How the demo is built and checked
1. `cd web/react-app && npm run build`
2. `PYTHONPATH=. python scripts/build_demo_db.py` copies 19 relations from PostgreSQL into `deploy/vercel/data/demo.duckdb` (timestamps are converted to the database session zone, decimals to floats; analyst notes are cleared).
3. `python scripts/build_vercel_bundle.py` assembles `deploy/vercel/` (static site, function, the few files the API reads at run time). The folder is generated and git-ignored.
4. `cd deploy/vercel && vercel deploy --prod`; if the custom aliases do not move, `vercel alias set <deployment-url> banking-transaction-analytics.vercel.app`.

**Portability.** The routers use the same SQL on both databases; `src/api/dash/common.py` has a small adapter for DuckDB (`:name` binds, row mappings, read-only). Two queries were rewritten to be portable (`width_bucket`, the `months` alias) and the RFM quintiles and score histogram were made deterministic. `scripts/check_demo_parity.py` calls every GET endpoint on both servers: 50 of 51 are identical (the 51st, `/v1/meta`, differs only by the new `demo` flag). Rows that tie in an ORDER BY may come back in a different order.

**Verification.** `tests/test_dash_api.py` passes on PostgreSQL and, with `DEMO_DUCKDB` set, on DuckDB (the independent SQL checks still run against PostgreSQL, so DuckDB is cross-checked); `tests/test_demo_engine.py` tests the adapter; the 24 Playwright tests pass against the local PostgreSQL app, the local DuckDB app, a Vercel preview and the production URL (`E2E_BASE_URL=<url> npx playwright test`).

**Limits.** Cold starts take about a second or two while the function loads DuckDB. A CSV export of the transactions table takes a few seconds; Excel exports of large tables are slower. The snapshot is fixed at the time of building.

## Local
`uvicorn src.api.main:app` then open `/app/`. See the README.

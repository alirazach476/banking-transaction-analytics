# Dashboard (React)

One React app (`web/react-app`, served by the API at `/app/`) holds every dashboard and chart in the project. There is no separate BI tool: the charts that used to exist only as PNG images in the reports are native, interactive charts in the app.

| Tab | Data | How it gets data |
|---|---|---|
| Payments (synthetic) | NovaBank synthetic payments: KPIs, daily approval rate, decline reasons, reconciliation queue, payment scoring form | live FastAPI endpoints (`/kpis/summary`, `/kpis/daily`, `/decline-reasons`, `/reconciliation/queue`, `/score/*`) |
| Pakistan analysis (real data) | SBP, World Bank, BIS, ECB, FRED, Global Findex: 9 sections, 52 charts and tables | one static file, `web/react-app/public/analysis.json`, generated from the analysis results |

## Pakistan analysis tab: sections
Overview (10 KPI tiles), Macro and monetary (policy rate vs inflation, policy-rate history, USD/PKR, repo vs policy rate, GDP growth, reserves, inflation, remittances, balance of payments), Banking system (capital, NPLs, ADR spike, sector NPLs, NPL categories, financial depth), Payments (retail volume by quarter, digital share, channel share and growth, Raast, POS/ATM/QR infrastructure, users, cards, FY2018 channels), International comparison (BIS card use and instruments, WDI peers, policy rates across central banks, ECB rates and inflation, Pakistan vs euro-area banks), Cross-border finance (BIS claims, claims by headquarters country, external debt, debt composition, remittance costs), Financial inclusion (Findex trend, peers, women, ranks, WDI extremes), Fraud models (PR-AUC by dataset, including real card transactions), Data quality (reconciliation scoreboard).

Every chart shows its source and notes. Values are not typed into the front end: they come from the JSON results written by the analysis scripts.

## Rebuild
```
python scripts/allinone/run_all.py          # recompute the analysis parts (reads the warehouse read-only)
python scripts/export_dashboard_data.py     # writes web/react-app/public/analysis.json
cd web/react-app && npm run build           # bundle; the API serves web/react-app/dist at /app/
```

## Tests
- `npm test` (vitest): every chart spec is valid (data present, series keys numeric, unique ids, a source on every chart).
- `npx playwright test` (needs the API with the payments marts): both tabs render, all sections and at least 45 charts appear, no chart reports a data problem, no console errors, no horizontal overflow at phone width, tab switching works.

## Payments metric definitions (match `docs/BUSINESS_METRICS.md`)
```
Approval Rate   = SUM(approved) / (SUM(approved) + SUM(declined))
Completion Rate = SUM(cleared)  / SUM(approved)
Settlement Rate = SUM(cleared settled) / SUM(cleared)
Decline Rate    = SUM(declined) / (SUM(approved) + SUM(declined))
```
Never average the daily rates; recompute from sums. Check values for the whole synthetic period: approval 95.07%, completion 97.03%, settlement 99.57%, 492,212 dated payments (987 payments with invalid authorization timestamps are excluded from the daily marts by design). The reconciliation queue has 15,783 rows, all OPEN after the latest run.

## Extracts for other tools
`data/processed/bi/` (CSV and Parquet; dictionary in `docs/BI_EXTRACTS_DICTIONARY.md`, regenerate with `PYTHONPATH=. python scripts/export_payment_bi_extracts.py`) remain available for spreadsheets or any BI tool; nothing in the project depends on them.

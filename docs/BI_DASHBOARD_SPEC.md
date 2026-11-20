# Payments BI dashboard specification (Tableau / Power BI)

**Status:** the data extracts and this spec are done and verified. A Tableau workbook (`.twb/.twbx`) was **not** built:
Tableau is not available in this environment, so no workbook has been opened or tested. The same views already exist as a working
React app (`web/react-app`, served at `/app/`). Data is synthetic.

## Data source
Files in `data/processed/bi/` (CSV and Parquet; dictionary in `docs/BI_EXTRACTS_DICTIONARY.md`). Regenerate:
`PYTHONPATH=. python scripts/export_payment_bi_extracts.py`. Tableau: connect to the CSVs (Text file) or Parquet (Tableau 2021.1+),
or point a live Postgres connection at schemas `analytics`, `intermediate`, `external_analytics`, `payments`.

Relationships (Tableau logical layer): `payment_kpis_daily.payment_date` = `settlement_daily.settlement_date` (date axis only; do not join row-wise);
`decline_reasons_monthly.month` to a month-truncated payment date. `payment_outcomes` is the drill-down grain (one row per payment_id).

## Sheets
| Sheet | Marks | Source | Notes |
|---|---|---|---|
| KPI tiles | Approval, completion, settlement rate; payments | payment_kpis_daily | use the ratio-of-sums calculations below, never an average of daily rates |
| Approval-rate trend | line, daily + 7-day moving avg | payment_kpis_daily | y-axis 80-100% |
| Funnel | bar: payments -> approved -> cleared -> settled | payment_kpis_daily | |
| Decline reasons | horizontal bar by reason, colour by channel | decline_reasons_monthly | month filter |
| Settlement health | stacked bar: orphans / duplicates by day | settlement_daily | |
| Reconciliation queue | table, sort by priority then amount_at_risk | reconciliation_queue | filter status = OPEN |
| FX context | line per currency pair | fx_monthly | |

## Calculated fields (definitions match `docs/BUSINESS_METRICS.md`)
```
Approval Rate   = SUM([approved]) / (SUM([approved]) + SUM([declined]))
Completion Rate = SUM([cleared])  / SUM([approved])
Settlement Rate = SUM([settled])  / SUM([cleared])
Decline Rate    = SUM([declined]) / (SUM([approved]) + SUM([declined]))
Approval 7d MA  = WINDOW_SUM(SUM([approved]),-6,0) / (WINDOW_SUM(SUM([approved]),-6,0) + WINDOW_SUM(SUM([declined]),-6,0))
```
Check values after connecting (whole period): approval 95.07%, completion 97.03%, settlement 99.57%, 492,212 dated payments
(987 payments with invalid authorization timestamps are excluded from daily marts by design).

## Filters / parameters
Date range, channel (decline reasons), issue type + status (queue), currency pair (FX).

## Acceptance checklist for the Tableau build (to be done by whoever has Tableau)
1. KPI tiles reproduce the check values above.
2. No average-of-averages on rate fields.
3. Reconciliation queue shows 15,783 rows total (all OPEN after the latest run).
4. Dashboard works at 1366x768 and tablet widths; colour-blind-safe palette; dark/light not required.

# BI extracts data dictionary (generated)

Synthetic data. Files in `data/processed/bi/` as CSV (UTF-8) and Parquet. Regenerate with `scripts/export_payment_bi_extracts.py`.

## payment_kpis_daily  (1,096 rows)
Daily payment lifecycle KPIs (dbt mart_payment_kpis_daily). Grain: one row per payment date.

| column | type | nulls | example |
|---|---|---|---|
| payment_date | object | 0 | 2023-01-01 |
| payments | int64 | 0 | 322 |
| approved | int64 | 0 | 303 |
| declined | int64 | 0 | 17 |
| cleared | int64 | 0 | 295 |
| settled | int64 | 0 | 295 |
| reversed | int64 | 0 | 4 |
| refunded | int64 | 0 | 7 |
| charged_back | int64 | 0 | 2 |
| approval_rate | float64 | 0 | 0.946875 |
| completion_rate | float64 | 0 | 0.9735973597359736 |
| settlement_rate | float64 | 0 | 1.0 |
| avg_response_ms | float64 | 0 | 426.7125 |

## decline_reasons_monthly  (1,632 rows)
Declined payments and amount by month, channel and reason (dbt mart_decline_reasons).

| column | type | nulls | example |
|---|---|---|---|
| month | object | 0 | 2023-01-01 |
| channel | object | 74 | E-commerce |
| decline_reason | object | 0 | EXPIRED_CARD |
| declined_payments | int64 | 0 | 3 |
| declined_amount | float64 | 0 | 167.14 |

## settlement_daily  (1,106 rows)
Settlement records per day with orphan and duplicate counts (dbt mart_settlement_daily).

| column | type | nulls | example |
|---|---|---|---|
| settlement_date | object | 0 | 2023-01-02 |
| settlement_records | int64 | 0 | 7 |
| distinct_payments | int64 | 0 | 7 |
| settlement_amount | float64 | 0 | 4623.59 |
| orphan_settlements | int64 | 0 | 0 |
| duplicate_settlement_records | int64 | 0 | 0 |

## fx_monthly  (10,422 rows)
External ECB FX reference rates by month (dbt external_analytics.mart_fx_monthly).

| column | type | nulls | example |
|---|---|---|---|
| base_currency | object | 0 | EUR |
| target_currency | object | 0 | AUD |
| month | object | 0 | 1999-01-01 |
| avg_rate | float64 | 0 | 1.83873 |
| min_rate | float64 | 0 | 1.8064 |
| max_rate | float64 | 0 | 1.91 |
| obs | int64 | 0 | 20 |
| mom_change | float64 | 41 | -0.047462106997764764 |

## reconciliation_queue  (15,783 rows)
Investigation queue of settlement exceptions with status and priority.

| column | type | nulls | example |
|---|---|---|---|
| payment_id | object | 0 | PAY-0000322205 |
| settlement_id | object | 0 |  |
| issue_type | object | 0 | MISSING_SETTLEMENT |
| amount_at_risk | float64 | 0 | 18899.62 |
| currency | object | 0 | USD |
| priority | object | 0 | HIGH |
| status | object | 0 | OPEN |
| first_detected_at | datetime64[ns, UTC] | 0 | 2026-11-20 19:38:55.792239+00:00 |
| last_detected_at | datetime64[ns, UTC] | 0 | 2026-11-20 19:40:42.466715+00:00 |

## reconciliation_runs  (2 rows)
Reconciliation run summaries (counts per exception type, success rate, amount at risk).

| column | type | nulls | example |
|---|---|---|---|
| recon_run_id | int64 | 0 | 2 |
| run_id | object | 0 | 2ba948a5-1d19-4d16-8f7e-39269d46ca74 |
| as_of | datetime64[ns, UTC] | 0 | 2026-01-11 07:38:27+00:00 |
| sla_days | int64 | 0 | 3 |
| cleared_payments | int64 | 0 | 448557 |
| matched | int64 | 0 | 439582 |
| pending | int64 | 0 | 0 |
| missing | int64 | 0 | 1882 |
| duplicate | int64 | 0 | 1398 |
| amount_mismatch | int64 | 0 | 1370 |
| currency_mismatch | int64 | 0 | 680 |
| late | int64 | 0 | 3645 |
| fx_rate_missing | int64 | 0 | 0 |
| unmatched_settlements | int64 | 0 | 6808 |
| settlement_success_rate | float64 | 0 | 0.979991 |
| amount_at_risk | float64 | 0 | 2267573.69 |
| created_at | datetime64[ns, UTC] | 0 | 2026-11-20 19:38:55.792239+00:00 |

## payment_outcomes  (493,199 rows)
Per-payment lifecycle flags (dbt int_payment_outcomes); ~490K rows, use for drill-down.

| column | type | nulls | example |
|---|---|---|---|
| payment_id | object | 0 | PAY-0000011494 |
| merchant_category | object | 1972 | Travel |
| channel | object | 1972 | POS Chip |
| currency | object | 777 | USD |
| is_international | bool | 0 | False |
| amount | float64 | 0 | 187.27 |
| payment_date | object | 987 | 2025-09-21 |
| authorized | bool | 0 | True |
| declined | bool | 0 | False |
| decline_reason | object | 468992 | INSUFFICIENT_FUNDS |
| response_ms | float64 | 986 | 112.0 |
| cleared | bool | 0 | True |
| settled | bool | 0 | True |
| reversed | bool | 0 | False |
| refunded | bool | 0 | False |
| charged_back | bool | 0 | False |

# NovaBank Metrics & KPI Definitions

> **Disclaimer:** This project uses synthetic banking data generated solely for demonstrating data engineering, analytics, and transaction-monitoring capabilities. It does not represent real customer or banking data.

All metrics are computed from `warehouse.fact_transactions` and analytics marts unless noted. Amounts are in account currency (predominantly synthetic USD/EUR/GBP mix from generation config).

---

## Core Transaction KPIs

| KPI | Definition | SQL logic (conceptual) |
|-----|------------|------------------------|
| **Total Transaction Value** | Sum of `amount` for all transactions in scope | `SUM(amount)` |
| **Transaction Count** | Count of transaction events | `COUNT(*)` |
| **Average Transaction Value** | Mean transaction amount | `SUM(amount) / COUNT(*)` |
| **Median Transaction Value** | 50th percentile amount | `PERCENTILE_CONT(0.5)` |
| **Completed Transactions** | Count where `transaction_status = 'Completed'` | Filter + count |
| **Failed Transactions** | Count where status = `Failed` | Filter + count |
| **Reversed Transactions** | Count where `is_reversed = true` or status = `Reversed` | Filter + count |
| **Transaction Success Rate** | Completed / (Completed + Failed + Reversed) | Ratio × 100 |
| **Transaction Failure Rate** | Failed / total attempted | Ratio × 100 |

**Scope filters:** Date range, channel, branch, region, customer type, transaction type — applied via dimension joins or mart slicers.

---

## Customer KPIs

| KPI | Definition |
|-----|------------|
| **Active Customers** | Distinct customers with ≥1 completed transaction in last 90 days |
| **New Customers (monthly)** | Customers whose `registration_date` falls in calendar month |
| **Average Customer Balance** | Mean `current_balance` across active accounts (`dim_account` / staging) |
| **Customer Transaction Count** | Per-customer count from `mart_customer_activity` |
| **Days Since Last Transaction** | `CURRENT_DATE - MAX(transaction_timestamp)::date` |

---

## Account KPIs

| KPI | Definition |
|-----|------------|
| **Active Accounts** | Accounts with status `Active` and activity in period |
| **Total Inflows** | Sum of credits (Deposits, Refunds, Interest) |
| **Total Outflows** | Sum of debits (Withdrawals, Payments, Fees) |
| **Net Flow** | `total_inflows - total_outflows` |
| **Average Account Balance** | From account dimension snapshot |

Source: `mart_account_activity`, `int_account_transaction_metrics`.

---

## Channel KPIs

Per channel (ATM, Branch, Mobile App, Internet Banking, POS, Online):

| KPI | Definition |
|-----|------------|
| Transaction Count | Events via channel |
| Transaction Value | Sum amount |
| Average Transaction | Mean amount |
| Success Rate | Completed / total |
| Failure Rate | Failed / total |
| Anomaly Rate | Anomaly-flagged / total (from `mart_anomaly_monitoring`) |

---

## Branch KPIs

| KPI | Definition |
|-----|------------|
| Branch Transaction Count | Transactions linked to branch |
| Branch Transaction Value | Sum amount |
| Deposit Value | Sum where type = Deposit |
| Withdrawal Value | Sum where type = Withdrawal |
| Customer Count | Distinct customers at branch |
| Failure Rate | Failed / total at branch |
| Average Transaction | Mean amount |

Rankings use `RANK()` or `DENSE_RANK()` on transaction value — see `sql/analytics/top_branches_by_value.sql`.

---

## Payment & Transfer KPIs

| KPI | Definition |
|-----|------------|
| Total Deposits | Sum Deposit transactions |
| Total Withdrawals | Sum Withdrawal transactions |
| Total Transfers | Sum from `fact_transfers` |
| Internal Transfer Value | `transfer_type = 'Internal'` |
| Domestic Transfer Value | `transfer_type = 'Domestic'` |
| International Transfer Value | `transfer_type = 'International'` |

---

## Time-Series KPIs

| KPI | Definition |
|-----|------------|
| **MoM Growth** | `(current_month_value - prior_month_value) / prior_month_value` |
| **YoY Growth** | Same for year-over-year month |
| **7-Day Rolling Average** | `AVG(daily_count) OVER (ORDER BY date ROWS 6 PRECEDING)` |
| **30-Day Rolling Average** | 30-row rolling window on daily aggregates |

Implemented in `mart_daily_transactions`, `mart_monthly_transactions`, and `sql/analytics/daily_transaction_trends.sql`.

---

## Anomaly KPIs

| KPI | Definition |
|-----|------------|
| **Anomaly Count** | Rows in `monitoring.transaction_anomalies` |
| **Anomaly Rate** | Anomalies / total transactions in period |
| **High Severity Count** | `severity IN ('High', 'Critical')` |
| **Anomalous Transaction Value** | Sum of amounts for flagged transactions |

Terminology: results are **potential anomalies** requiring review — not confirmed fraud.

---

## Customer Activity Segmentation

Segments are derived from **actual transaction counts** and recency in `mart_customer_activity`:

| Segment | Rule |
|---------|------|
| **Inactive** | `transaction_count = 0` OR `days_since_last_transaction > 90` |
| **Low Activity** | `transaction_count < 10` (and not inactive) |
| **Medium Activity** | `transaction_count` between 10 and 49 |
| **High Activity** | `transaction_count` between 50 and 199 |
| **Premium Activity** | `transaction_count >= 200` |

Thresholds are documented in the dbt model header (`mart_customer_activity.sql`) and enforced consistently in Power BI via a calculated column or imported segment field.

**Rationale:**

- `< 10` — occasional banking (typical retail)
- `10–49` — regular usage
- `50–199` — high engagement (power users, small business patterns)
- `>= 200` — premium/high-volume (business or premium retail profiles)
- `90-day` inactivity aligns with common retail banking dormancy definitions

---

## Data Quality KPIs (Engineering)

| KPI | Source |
|-----|--------|
| Pipeline Success Rate | `audit.pipeline_runs.status = 'SUCCESS'` |
| Failed DQ Checks | Count where `audit.data_quality_results.status = 'FAIL'` |
| Reconciliation Pass Rate | `audit.reconciliation_results.status = 'PASS'` |
| Data Freshness | `NOW() - MAX(_ingested_at)` on raw tables |
| Rows Processed | `audit.pipeline_runs.rows_processed` |

---

## Power BI Measure Mapping

DAX equivalents documented in [dashboards/powerbi/dax_measures.md](../dashboards/powerbi/dax_measures.md). Prefer measures over calculated columns for all KPIs above.

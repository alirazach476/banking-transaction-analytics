# Power BI Dashboard Specification — Pages 1–7

> **Disclaimer:** This project uses synthetic banking data generated solely for demonstrating data engineering, analytics, and transaction-monitoring capabilities. It does not represent real customer or banking data.

**Report name:** NovaBank Transaction Analytics  
**Theme:** Corporate banking — dark blue header, white cards, red for failures, amber for anomalies

Add synthetic data disclaimer footer on **every page**.

---

## Page 1 — Executive Banking Overview

**Purpose:** C-level snapshot of bank transaction health.

### KPI Cards (row 1)

| KPI | Measure | Format |
|-----|---------|--------|
| Total Transaction Value | `[Total Transaction Value]` | Currency |
| Transaction Count | `[Transaction Count]` | Whole number |
| Average Transaction | `[Average Transaction Value]` | Currency |
| Active Customers | `[Active Customers]` | Whole number |
| Active Accounts | `[Active Accounts]` | Whole number |
| Success Rate | `[Transaction Success Rate]` | Percentage |
| Failure Rate | `[Transaction Failure Rate]` | Percentage |
| Anomaly Count | `[Anomaly Count]` | Whole number |

### Charts

| Visual | Type | Fields |
|--------|------|--------|
| Transaction value trend | Line chart | mart_daily_transactions[transaction_date], [Total Transaction Value] |
| Transaction count trend | Line chart | mart_daily_transactions[transaction_date], [Transaction Count] |
| Value by channel | Stacked bar | mart_channel_performance[channel], [Total Transaction Value] |
| Value by transaction type | Donut | mart_payment_activity or fact-derived type, [Total Transaction Value] |
| Regional activity | Map or bar | mart_customer_activity[region], [Total Transaction Value] |

### Slicers

- Date range (mart_daily_transactions[transaction_date])
- Region (optional)

---

## Page 2 — Transaction Analytics

**Purpose:** Operational transaction deep-dive.

### Visuals

| Visual | Type | Fields |
|--------|------|--------|
| Daily transaction volume | Column chart | transaction_date, transaction_count (mart) |
| Monthly transaction value | Column chart | mart_monthly_transactions[month_start], transaction_value |
| Transaction type distribution | Treemap | transaction_type, [Transaction Count] |
| Average transaction value | KPI + line | [Average Transaction Value] over time |
| Success vs failure | Clustered bar | transaction_status, [Transaction Count] |
| Reversal trend | Line | date, reversed_count |
| Hourly activity | Column | hour_of_day (calculated or imported), [Transaction Count] |

### Slicers

- Date
- Region
- Branch (mart_branch_performance[branch_name])
- Channel
- Transaction Type
- Customer Type (mart_customer_activity[customer_type])

---

## Page 3 — Customer Analytics

**Purpose:** Customer behavior and segmentation.

### Visuals

| Visual | Type | Fields |
|--------|------|--------|
| Active customers | KPI | [Active Customers] |
| Customer transaction volume | Histogram / bar | customer transaction_count buckets |
| Customer transaction value | Scatter | transaction_count vs total_amount |
| Customer segments | Donut | activity_segment, [Active Customers] or count |
| Avg customer transaction | KPI | Avg of avg_completed_amount |
| Top customers by value | Table (Top 10) | customer_id, name, total_amount |
| Activity trend | Line | month, distinct active customers |

**Table columns:** customer_id, first_name, last_name, customer_type, activity_segment, transaction_count, total_amount, days_since_last_transaction

---

## Page 4 — Account Analytics

**Purpose:** Account-level flows and balances.

### Visuals

| Visual | Type | Fields |
|--------|------|--------|
| Account count | KPI | DISTINCTCOUNT(account_id) |
| Account type distribution | Donut | account_type |
| Average balance | KPI | AVERAGE(current_balance) from mart_account_activity |
| Total inflows | KPI | [Total Deposits] or sum total_inflows |
| Total outflows | KPI | [Total Withdrawals] or sum total_outflows |
| Net flow | KPI | SUM(net_flow) |
| Account activity | Bar | account_type, transaction_count |

### Slicers

- Account type
- Account status
- Date (via relationship to daily mart)

---

## Page 5 — Channel & Branch Analytics

**Purpose:** Compare delivery channels and branch performance.

### Visuals

| Visual | Type | Fields |
|--------|------|--------|
| Channel volume | Bar | channel, transaction_count |
| Channel value | Bar | channel, transaction_value |
| Channel failure rate | Bar | channel, failure_rate |
| Branch ranking | Table Top N | branch_name, transaction_value, RANK |
| Branch transaction value | Bar | branch_name (Top 15) |
| Branch success rate | KPI card matrix | branch × success_rate |
| Regional performance | Map | region, transaction_value |

**Branch table columns:** branch_name, city, region, transaction_count, transaction_value, deposit_value, withdrawal_value, failure_rate, customer_count

---

## Page 6 — Anomaly Monitoring

**Purpose:** Transaction Anomaly Detection Prototype — **not production fraud**.

### KPI Cards

| KPI | Measure |
|-----|---------|
| Total Anomalies | `[Anomaly Count]` |
| High Severity | COUNT where severity = High |
| Critical Severity | COUNT where severity = Critical |
| Anomaly Rate | `[Anomaly Rate]` |
| Anomalous Transaction Value | SUM(amount) filtered to anomalies |

### Visuals

| Visual | Type | Fields |
|--------|------|--------|
| Anomalies over time | Line | transaction_timestamp (date), [Anomaly Count] |
| By channel | Bar | channel, [Anomaly Count] |
| By region | Bar | region, [Anomaly Count] |
| By reason | Bar | anomaly_reason (split or primary) |
| High-value anomalies | Scatter | amount vs rule_based_score |
| Customer anomaly frequency | Bar Top 20 | customer_id, [Anomaly Count] |

### Detail Table

| Column |
|--------|
| transaction_id |
| customer_id |
| transaction_timestamp |
| amount |
| anomaly_reason |
| severity |
| rule_based_score |
| ml_anomaly_score |

**Conditional formatting:** Critical = dark red, High = red, Medium = amber, Low = yellow.

**Header note:** "Potential anomalies requiring review — synthetic demo data."

---

## Page 7 — Data Quality & Pipeline

**Purpose:** Demonstrate data engineering maturity.

### KPI Cards

| KPI | Source |
|-----|--------|
| Pipeline Status | Latest audit.pipeline_runs[status] |
| Last Successful Run | MAX(end_time) where status=SUCCESS |
| Rows Processed | SUM(rows_processed) latest run |
| Failed Checks | COUNT audit.data_quality_results WHERE status=FAIL |
| Reconciliation Status | Latest audit.reconciliation_results aggregate |
| Source vs Warehouse Count | source_value vs warehouse_value metric |
| Data Freshness (hours) | DAX: hours since max ingest |

### Visuals

| Visual | Type | Fields |
|--------|------|--------|
| Pipeline run history | Table | run_id, start_time, end_time, status, mode, rows_processed |
| DQ check results | Matrix | check_name, table_name, status, failed_rows |
| Reconciliation detail | Table | source_name, metric_name, difference, status |
| Ingestion timeline | Line | _ingested_at by day (if imported from audit) |

### Color rules

- PASS / SUCCESS = green
- FAIL = red
- WARN = amber
- RUNNING = blue

---

## Global Settings

- **Page size:** 16:9
- **Cross-filtering:** Enable between visuals on same page
- **Drill-through:** Page 6 detail from Page 1 anomaly KPI
- **Bookmarks:** "Last 30 days", "Last 12 months", "YTD"
- **Tooltips:** Page 1 KPIs show sparkline on hover

See [dax_measures.md](dax_measures.md) and [data_model.md](data_model.md) for implementation detail.

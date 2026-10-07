# NovaBank DAX Measures

> **Disclaimer:** This project uses synthetic banking data generated solely for demonstrating data engineering, analytics, and transaction-monitoring capabilities. It does not represent real customer or banking data.

Use a dedicated **`_Metrics`** table (blank table) to host measures. Prefer measures over calculated columns for aggregations.

Assume primary fact source: `mart_daily_transactions`, `mart_customer_activity`, `mart_anomaly_monitoring`, `mart_account_activity`, `mart_channel_performance`.

---

## Core Transaction Measures

### Total Transaction Value

```dax
Total Transaction Value =
SUM ( mart_daily_transactions[transaction_value] )
```

Alternative if using row-level fact:

```dax
Total Transaction Value =
SUM ( mart_anomaly_monitoring[amount] )
```

### Transaction Count

```dax
Transaction Count =
SUM ( mart_daily_transactions[transaction_count] )
```

### Average Transaction Value

```dax
Average Transaction Value =
DIVIDE (
    [Total Transaction Value],
    [Transaction Count],
    0
)
```

### Completed Transactions

```dax
Completed Transactions =
SUM ( mart_daily_transactions[completed_count] )
```

If not in mart, use:

```dax
Completed Transactions =
CALCULATE (
    [Transaction Count],
    mart_transaction_failures[transaction_status] = "Completed"
)
```

### Failed Transactions

```dax
Failed Transactions =
SUM ( mart_daily_transactions[failed_count] )
```

### Reversed Transactions

```dax
Reversed Transactions =
SUM ( mart_daily_transactions[reversed_count] )
```

### Transaction Success Rate

```dax
Transaction Success Rate =
DIVIDE (
    [Completed Transactions],
    [Completed Transactions] + [Failed Transactions] + [Reversed Transactions],
    0
)
```

Format: Percentage, 1 decimal.

### Transaction Failure Rate

```dax
Transaction Failure Rate =
DIVIDE (
    [Failed Transactions],
    [Transaction Count],
    0
)
```

---

## Customer & Account Measures

### Active Customers

Customers with activity in last 90 days:

```dax
Active Customers =
CALCULATE (
    DISTINCTCOUNT ( mart_customer_activity[customer_id] ),
    mart_customer_activity[days_since_last_transaction] <= 90,
    mart_customer_activity[transaction_count] > 0
)
```

### Active Accounts

```dax
Active Accounts =
CALCULATE (
    DISTINCTCOUNT ( mart_account_activity[account_id] ),
    mart_account_activity[transaction_count] > 0
)
```

### Average Account Balance

```dax
Average Account Balance =
AVERAGE ( mart_account_activity[current_balance] )
```

---

## Payment Flow Measures

### Total Deposits

```dax
Total Deposits =
SUM ( mart_payment_activity[deposit_value] )
```

Or from payment mart where transaction_type = "Deposit":

```dax
Total Deposits =
CALCULATE (
    [Total Transaction Value],
    mart_payment_activity[transaction_type] = "Deposit"
)
```

### Total Withdrawals

```dax
Total Withdrawals =
SUM ( mart_payment_activity[withdrawal_value] )
```

### Total Transfers

```dax
Total Transfers =
SUM ( mart_payment_activity[transfer_value] )
```

---

## Anomaly Measures

### Anomaly Count

```dax
Anomaly Count =
COUNTROWS ( mart_anomaly_monitoring )
```

Or distinct transactions:

```dax
Anomaly Count =
DISTINCTCOUNT ( mart_anomaly_monitoring[transaction_id] )
```

### Anomaly Rate

```dax
Anomaly Rate =
DIVIDE (
    [Anomaly Count],
    [Transaction Count],
    0
)
```

### High Severity Anomalies

```dax
High Severity Anomalies =
CALCULATE (
    [Anomaly Count],
    mart_anomaly_monitoring[severity] IN { "High", "Critical" }
)
```

### Anomalous Transaction Value

```dax
Anomalous Transaction Value =
SUMX (
    FILTER ( mart_anomaly_monitoring, NOT ISBLANK ( mart_anomaly_monitoring[transaction_id] ) ),
    mart_anomaly_monitoring[amount]
)
```

---

## Time Intelligence (Optional)

Requires `dim_date` or continuous date column marked as date table.

### MoM Transaction Value Growth

```dax
MoM Transaction Value Growth =
VAR CurrentMonth = [Total Transaction Value]
VAR PriorMonth =
    CALCULATE (
        [Total Transaction Value],
        DATEADD ( mart_daily_transactions[transaction_date], -1, MONTH )
    )
RETURN
DIVIDE ( CurrentMonth - PriorMonth, PriorMonth, BLANK () )
```

### 7-Day Rolling Avg Count

If not precomputed in mart:

```dax
Rolling 7D Avg Count =
AVERAGEX (
    DATESINPERIOD (
        mart_daily_transactions[transaction_date],
        MAX ( mart_daily_transactions[transaction_date] ),
        -7,
        DAY
    ),
    CALCULATE ( [Transaction Count] )
)
```

---

## Data Quality Measures (Page 7)

### Failed DQ Checks

```dax
Failed DQ Checks =
CALCULATE (
    COUNTROWS ( audit_data_quality_results ),
    audit_data_quality_results[status] = "FAIL"
)
```

Rename table if imported as `audit_data_quality_results`.

### Latest Pipeline Status

```dax
Latest Pipeline Status =
VAR LatestRun =
    TOPN ( 1, ALL ( audit_pipeline_runs ), audit_pipeline_runs[start_time], DESC )
RETURN
MAXX ( LatestRun, audit_pipeline_runs[status] )
```

### Data Freshness (Hours)

```dax
Data Freshness Hours =
DATEDIFF (
    MAX ( audit_pipeline_runs[end_time] ),
    NOW (),
    HOUR
)
```

---

## Formatting Recommendations

| Measure | Format |
|---------|--------|
| Currency measures | $ English, 2 decimals |
| Rates | Percentage, 1–2 decimals |
| Counts | Whole number, thousand separator |
| Anomaly Rate | Percentage, 2 decimals |

---

## Best Practices Applied

1. All KPIs as **measures** — not calculated columns
2. `DIVIDE()` prevents divide-by-zero
3. Explicit filter context with `CALCULATE`
4. Separate `_Metrics` table for organization
5. Display folders: "Transactions", "Customers", "Anomalies", "Pipeline"

See [dashboard_spec.md](dashboard_spec.md) for visual placement.

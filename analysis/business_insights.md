# NovaBank Business Insights

> **SYNTHETIC DATA — NovaBank demonstration dataset only. Not real customer or banking records.**

*Generated at: 2026-10-07T11:04:26.745165+00:00*

## Executive Summary

- **Customers:** 5,000
- **Accounts:** 7,500
- **Transactions:** 101,600
- **Total transaction volume:** $81,172,698.21
- **Average transaction amount:** $799.18
- **Transactions requiring review (anomalies):** 8,645

### Anomalies by Severity

- **Low:** 5,041
- **High:** 2,031
- **Medium:** 1,573

## Top Channels by Volume

- **Mobile App:** 31,713 transactions
- **ATM:** 18,233 transactions
- **POS:** 14,799 transactions
- **Internet Banking:** 14,795 transactions
- **Branch:** 12,088 transactions

Mobile App represents **34.6%** of transaction volume among the top channels listed above.

## Customer Activity Segments

Thresholds: Inactive (>90 days since last txn relative to dataset as-of date, or 0 txns); Low (<10); Medium (10–49); High (50–199); Premium (≥200).

- **Medium Activity:** 2,471 customers
- **Inactive:** 1,955 customers
- **High Activity:** 388 customers
- **Low Activity:** 186 customers

## Top Branches by Completed Transaction Value

- **NovaBank Dallas #50** (Southwest): $1,149,418.36 across 1,001 txns (failure rate 5.00%)
- **NovaBank Philadelphia #7** (Northeast): $1,021,448.59 across 1,022 txns (failure rate 5.48%)
- **NovaBank Detroit #47** (Midwest): $1,000,420.33 across 1,049 txns (failure rate 4.96%)
- **NovaBank Minneapolis #20** (Midwest): $955,958.77 across 1,101 txns (failure rate 4.63%)
- **NovaBank Atlanta #22** (Southeast): $894,079.01 across 1,046 txns (failure rate 4.30%)

## Channel Success / Failure Rates

- **Branch:** success 87.55%, failure 5.33% (12,088 txns)
- **Online:** success 87.82%, failure 5.29% (9,940 txns)
- **ATM:** success 87.39%, failure 5.28% (18,233 txns)
- **POS:** success 87.82%, failure 5.15% (14,799 txns)
- **Internet Banking:** success 87.95%, failure 4.97% (14,795 txns)
- **Mobile App:** success 88.36%, failure 4.94% (31,713 txns)
- **Unknown:** success 90.63%, failure 3.13% (32 txns)

## Data Sources Queried

- `analytics.mart_channel_performance`
- `analytics.mart_customer_activity`
- `analytics.mart_daily_transactions`
- `monitoring.transaction_anomalies`
- `warehouse.fact_transactions`

---
*This report is for analytical demonstration. Anomaly flags are labeled 'Potential anomaly' / 'Transaction requiring review' and must not be used as automated fraud decisions.*
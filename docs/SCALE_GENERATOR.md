# Scalable core-banking generator (Phase 1 completion)

`src/data_generation/scale.py` — same schemas and anomaly types as the legacy `generate_all.py`, but vectorised and chunked, with the pieces
Phase 1 was missing. It writes to its own folder (default `data/scale/run`) and never touches `data/source`. Synthetic data only.

```
python -m src.data_generation.scale --customers 100000 --accounts 150000 --transactions 2000000 --out data/scale/run
```

## What it adds
| Item | How |
|---|---|
| Chunked / scalable | time-sliced chunks (250K rows each), no per-row Python loops; output is globally time-ordered; memory bounded by one slice |
| Account-balance consistency | `transactions_ledger.csv` (signed amount + `balance_after`); `accounts.csv` gets `opening_balance` and `current_balance` = opening + signed COMPLETED movements. Opening is the legacy balance, lifted only as far as needed so no running balance goes negative (flagged in `balance_note`) |
| Customer activity history | `customer_activity_monthly.csv` (per customer-month: count, amount, completed, failed, anomalies) and `customer_lifecycle.csv` (first/last transaction, active months, `activity_state` active / dormant (>90 days) / never_active) |
| Branch extensions | `branch_extensions.csv`: lat/long (region centroid + noise), floor area, staff, ATM count, safe-deposit, weekend opening |
| Merchant extensions | `merchant_extensions.csv`: MCC, risk tier, onboarding date, average ticket, synthetic chargeback rate by tier |
| Anomalies | same 7 types as the legacy generator, flagged in `is_injected_anomaly`/`anomaly_type`; rapid/high-frequency anomalies add 8-payment bursts |

## Verified (tests/test_scale_generator.py, 8 tests)
Unique ids; all foreign keys resolve; global time order; row count = requested + burst rows; anomaly share within tolerance of the target;
independent recomputation of closing balances from the ledger matches `current_balance` (tolerance 0.02), zero negative running balances;
activity totals equal the transaction count; extension tables cover every branch/merchant; byte-identical output for the same seed.

## Measured (one run each, this machine)
| Run | Result |
|---|---|
| 2,003,200 transactions (100K customers, 150K accounts, 20K merchants, 200 branches) | transactions 57.3 s, ledger 46.2 s, activity history 139.1 s; whole run ~4.3 min; 449 MB output; 34,011 accounts had opening balance lifted; 0 negative balances |
| Legacy generator, 500,000 transactions only | 36.3 s (≈73 µs/row; 2M would be ≈145 s extrapolated, not measured) vs ≈29 µs/row here, i.e. about 2.5x faster at the transaction step |

The legacy generator also cannot produce 100K+ customers/accounts in reasonable time (per-row Faker/loops); this one built the reference tables in 1.2 s.

## Limits
- Customer names come from a small pool (not Faker); acceptable for synthetic analytics, not for realism of names.
- The dirty/clean data-quality defect injection of the legacy generator is NOT replicated here (this generator emits clean data; use it for volume/consistency work).
- Ledger/activity passes re-read the CSV in chunks; at 2M rows this dominates run time (activity history is the slowest step).
- Not wired into the Airflow DAG or the Postgres loader (output folder is separate by design).

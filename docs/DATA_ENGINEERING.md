# Data Engineering

## Payment-lifecycle generator (`src/payments/`)
All output is **synthetic**; every row has `is_synthetic = true`.

| Module | Role |
|---|---|
| `config.py` | `PaymentGenConfig` (volumes, seed, chunk size, rates), `DefectRates`, `SettlementIssueRates`; `from_env()` reads `NUM_PAYMENTS`, `NUM_CARDS`, … |
| `generator.py` | Vectorised numpy generator. Streams: random card payments, monthly **recurring** subscriptions, **synthetic fraud-pattern bursts** (6–12 high-value foreign e-commerce attempts within 20 min) |
| `defects.py` | Labelled, configurable defects for the **dirty** feed |
| `writer.py` | Chunked CSV writer + CLI; clean and dirty copies written to separate folders |
| `reconciliation.py`, `kpis.py`, `load.py` | Reconciliation engine, KPI math, COPY loader / persistence |

```
python -m src.payments.writer --payments 100000 --chunk-size 100000      # dev default
python -m src.payments.writer --payments 2000000 --chunk-size 200000     # benchmark scale
python -m src.payments.writer --no-defects                               # defect-free dirty feed
```

### Realism and determinism
* Per-chunk RNG `default_rng([seed, stream, chunk_idx])` → identical output for the same `(seed, chunk_size)`.
* Calendar weights: weekday/weekend, Nov/Dec seasonal lift, payday days (1/15/30), +15 % linear trend; hourly curve with night trough.
* Card activity ~ lognormal × customer-profile frequency; amounts ~ lognormal by merchant category × profile multiplier; amounts converted to merchant currency at that day's synthetic FX rate.
* Merchants are 92 % domestic to the card's country, so ≈5 % of payments are international.
* **Decline model** (ground truth, so the statistics/ML modules can be validated against it):
  `logit(p) = -3.4 + 0.6·international + 0.5·card_not_present + 0.45·(log10(usd+1)-1.7) + 0.5·night + 1.5·fraud_pattern`; cards with status Expired/Blocked are forced declines (and rarely transact).
* Lifecycle: auth request → response (latency lognormal; timeouts 8–12 s) → reversal (1.5 %) or clearing (98.5 %) → settlement T+1–2 days → refund (3 % of settled) / chargeback (0.4 % base; ×8 fraud pattern, ×2 card-not-present).
* Linked to the legacy `data/source/card_system/{cards,merchants}.csv` IDs when present (deduplicated, null IDs dropped); otherwise standalone reference data in the same ID format. Use `--no-existing-refs` to force standalone.

### Simplifications (honest limits)
* Account balances are **not** yet derived from payments (the legacy balance reconciliation is unchanged).
* Cards past their nominal expiry date but with status Active are treated as silently reissued; only status `Expired` forces `EXPIRED_CARD`.
* FX in this module is a seeded random walk labelled `SYNTHETIC`; real rates arrive with Module B (Phase 3).
* Branches, ATM, transfer and customer-activity history reuse the legacy generator; a chunked rewrite of that legacy generator is still pending.

## Controlled data-quality defects
Applied **only** to the dirty feeds (`data/source/payments/`); clean copies live in `data/processed/clean_reference/payments/`. Each affected row has a `dq_defect` label (`;`-joined if several). The manifest `payments_manifest.json` records the injected count of each label.

| Label | Effect | Default rate |
|---|---|---|
| `duplicate_record` | row appended a second time | 0.5 % |
| `missing_value` | NULL in `merchant_category`, `channel` (transactions) / `reason_code` (events) | 0.4 % per column |
| `invalid_foreign_key` | `merchant_id` (transactions) / `payment_id` (events) = `INVALID-REF` | 0.2 % |
| `inconsistent_capitalization` | `channel` lower/upper-cased | 1 % |
| `invalid_timestamp` | e.g. `2024-13-45 99:00:00` | 0.2 % |
| `invalid_currency` | e.g. `US$`, `XXX` | 0.2 % |
| `incorrect_status` | `event_status` = `APPROVD`/`UNKNOWN`/… | 0.4 % |

Settlement exceptions (missing, duplicate, amount/currency mismatch, late, orphan) are **business-process exceptions**, not DQ defects; they are generated with a ground-truth file `settlement_injected_truth.csv` (clean folder) used to evaluate reconciliation.

**Known caveat:** reconciling directly from the dirty raw tables drops events labelled defective, which can create artificial unmatched settlements. The intended path is dbt staging (Phase 5) which standardises/quarantines defects before reconciliation; until then use `--no-defects` for reconciliation demos.

## Loading
`src/payments/load.py` bulk-loads with `COPY` into `raw.payment_*` (TEXT bronze, truncate + load → idempotent) and persists reconciliation to `payments.reconciliation_runs` / `payments.investigation_queue` (upsert; analyst status preserved; vanished issues → `RESOLVED`). DDL: `sql/ddl/06_create_payments_tables.sql`.

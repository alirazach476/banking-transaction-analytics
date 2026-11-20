# Business Metrics (payment lifecycle)

All figures derive from **synthetic** data. Unit of analysis is the **payment** (`payment_id`, one authorization attempt), *not* the lifecycle event: a single payment produces 2–7 events, so counting events would inflate every denominator. Implementation: `src/payments/kpis.py` (unit-tested with hand-computed fixtures in `tests/test_payments.py`).

| KPI | Numerator | Denominator | Notes |
|---|---|---|---|
| Authorization approval rate | payments with `AUTH_RESPONSE = APPROVED` | payments with any `AUTH_RESPONSE` (approved + declined) | Payments still awaiting a response are excluded. Duplicate event rows are removed by `event_id`. |
| Decline rate | declined payments | same as above | `approval_rate + decline_rate = 1`. |
| Transaction completion rate | payments with `CLEARING` | approved payments | Reversed and never-cleared auths lower it. |
| Settlement success rate (lifecycle) | payments with `SETTLEMENT` | cleared payments | Presence of a settlement record only. |
| Settlement success rate (reconciliation) | payments `MATCHED` | cleared payments that are **due** (not `PENDING`) | Stricter: right amount, currency, no duplicate, within SLA. |
| Reversal rate | payments with `REVERSAL` | approved payments | Reversal = auth voided before clearing. |
| Refund rate | payments with `REFUND` | settled payments | Refunds occur after settlement. |
| Chargeback rate | payments with `CHARGEBACK` | settled payments | Disputes arrive 10–90 days after settlement, so recent cohorts are right-censored; compare mature cohorts only. |
| Average processing time | mean `response_ms` of `AUTH_RESPONSE` | payments with a response | Includes timeouts (8–12 s), so also report the median. |

## Decline reason categories
`INSUFFICIENT_FUNDS`, `EXPIRED_CARD`, `INVALID_CARD`, `SUSPECTED_FRAUD`, `INCORRECT_SECURITY_INFO`, `ISSUER_UNAVAILABLE`, `PROCESSING_TIMEOUT`, `RESTRICTED_TRANSACTION`. Reason mix is conditioned on channel (security-info errors only on card-not-present) and the synthetic fraud-pattern flag.

## Settlement reconciliation (`src/payments/reconciliation.py`)
* **Population:** payments with a `CLEARING` event (deduplicated on `payment_id`).
* **Expected amount:** `round(clearing_amount × FX(txn currency → USD, clearing date), 2)`; rate taken as-of the clearing date (backward as-of join).
* **Actual:** settlement records keyed by `payment_id`.
* **Primary status priority:** `MISSING_SETTLEMENT` > `DUPLICATE_SETTLEMENT` > `CURRENCY_MISMATCH` > `AMOUNT_MISMATCH` > `LATE_SETTLEMENT` > `FX_RATE_MISSING` > `PENDING` > `MATCHED`. Individual flags are kept in `issue_flags`.
* **Missing vs pending:** no settlement is `MISSING` only if `clearing_ts + SLA days < as_of`; otherwise `PENDING` (default SLA 3 days, amount tolerance 0.01).
* **Unmatched settlements:** settlement rows whose `payment_id` has no clearing record.
* **Amount at risk:** full expected amount for missing/late/currency-mismatch; absolute over/under-payment for duplicate/amount mismatch; 0 when FX is unknown.
* **Investigation queue:** `payments.investigation_queue`, keyed `(payment_id, settlement_id, issue_type)`; re-runs upsert, keep analyst status/notes, and auto-resolve exceptions that disappear.

### Validation
On generated data with injected exceptions, `test_reconciliation_recovers_injected_issues` requires ≥ 99 % recall per issue type and 100 % precision (nothing flagged that was not injected).

## Not yet implemented
Processing-cost estimates, currency exposure and interchange-based revenue (need Phase 3 fee-schedule data); these are tracked in `IMPLEMENTATION_PROGRESS.md`.

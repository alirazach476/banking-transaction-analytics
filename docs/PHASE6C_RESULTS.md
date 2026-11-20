# Phase 6c results (measured; synthetic data)

## Larger hyper-parameter search (40 candidates, full 379,893-row training window, 366 s)
- CV PR-AUC 0.335; test PR-AUC new 0.258 vs previous 0.255; promoted: **True** (rule: promote only if test PR-AUC improves)

## Drift monitoring (PSI vs training window; rule PSI>0.25 = alert)
- Max PSI over all feature-months: 0.036; alerts: 0

| month   |     n |   log_amt |   intl |   cnp |   night |   hour |   card_txn_60m |   card_amt_60m |   amt_vs_card_mean |   foreign_merchant |   amount |   score_fraud |
|:--------|------:|----------:|-------:|------:|--------:|-------:|---------------:|---------------:|-------------------:|-------------------:|---------:|--------------:|
| 2025-06 |  4550 |    0.0018 |      0 |     0 |       0 | 0.0058 |              0 |         0.0019 |             0.0319 |                  0 |   0.0018 |        0.0073 |
| 2025-07 | 13766 |    0.0007 |      0 |     0 |       0 | 0.0023 |              0 |         0.0006 |             0.0274 |                  0 |   0.0007 |        0.005  |
| 2025-08 | 13780 |    0.0015 |      0 |     0 |       0 | 0.003  |              0 |         0.0015 |             0.0304 |                  0 |   0.0015 |        0.0054 |
| 2025-09 | 13446 |    0.0015 |      0 |     0 |       0 | 0.0014 |              0 |         0.0014 |             0.0297 |                  0 |   0.0015 |        0.0075 |
| 2025-10 | 13844 |    0.0009 |      0 |     0 |       0 | 0.0026 |              0 |         0.001  |             0.0362 |                  0 |   0.0009 |        0.0078 |
| 2025-11 | 16473 |    0.001  |      0 |     0 |       0 | 0.0005 |              0 |         0.001  |             0.0343 |                  0 |   0.001  |        0.0069 |
| 2025-12 | 19114 |    0.0004 |      0 |     0 |       0 | 0.0003 |              0 |         0.0005 |             0.0342 |                  0 |   0.0004 |        0.0067 |

## Fairness audit (proxy attributes; the synthetic data has no protected attributes)
Fraud model at threshold 0.114; overall flag rate 0.0727%.

- **card_country**: max flag-rate ratio vs overall 2.49, max FPR gap 0.0002 across 4 groups with n>=1000
- **channel**: max flag-rate ratio vs overall 2.65, max FPR gap 0.0003 across 5 groups with n>=1000
- **merchant_category**: max flag-rate ratio vs overall 2.91, max FPR gap 0.0012 across 11 groups with n>=1000

## Caveats
- Drift windows are one synthetic time series; the generator is stationary apart from seasonality, so few alerts are expected. The PSI machinery is unit-tested (`tests/test_monitoring.py`) on injected shifts.
- Fairness here audits proxy attributes (country, channel, category). It is a template for a real audit, not evidence about real customers; rates for small groups are noisy (groups <1000 rows excluded).
- Promotion rule uses the single test split; no further holdout was kept.
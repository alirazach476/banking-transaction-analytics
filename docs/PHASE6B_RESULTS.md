# Phase 6b results (measured; synthetic data)

## Fraud-pattern detection (time split, 80/20)
- Test rows 94,973; fraud rate 0.2506% (random-guess PR-AUC = that rate)
- XGBoost (RandomizedSearchCV, TimeSeriesSplit(3), 8 candidates): CV PR-AUC 0.232; test PR-AUC 0.255, ROC-AUC 0.946
- Best-F1 operating point: F1 0.306 (precision 0.562, recall 0.210)
- Unsupervised IsolationForest: PR-AUC 0.049, ROC-AUC 0.870

## Decline model, tuned
- CV PR-AUC 0.180; test ROC-AUC 0.637, PR-AUC 0.169 (phase 6 fixed-parameter ROC-AUC was 0.635)

## Daily volume forecast (90-day holdout)
- Holt-Winters (damped trend, weekly seasonality) MAPE 16.89% vs seasonal-naive 19.27%

## Customer segmentation (KMeans, 3,248 customers with >=5 payments)
- Silhouette by k: 3: 0.187, 4: 0.201, 5: 0.200, 6: 0.208, 7: 0.206; chosen k=6

| segment | customers | avg payments | avg amount | decline rate | intl share | CNP share |
|---|---|---|---|---|---|---|
| 0 | 489 | 146.2 | 172.8 | 0.054 | 0.028 | 0.428 |
| 1 | 1050 | 257.1 | 593.1 | 0.049 | 0.042 | 0.300 |
| 2 | 21 | 8.3 | 4692.1 | 0.979 | 0.123 | 0.346 |
| 3 | 112 | 58.3 | 1212.0 | 0.082 | 0.160 | 0.357 |
| 4 | 378 | 19.5 | 135.4 | 0.065 | 0.024 | 0.261 |
| 5 | 1198 | 99.5 | 148.1 | 0.048 | 0.032 | 0.269 |

## Persistence
Models saved to `models/*.joblib` with `models/model_registry.json` (features, metrics, seed, timestamp). Load with `joblib.load`.

## Caveats
- Synthetic data: the fraud pattern is a generated card burst (6-12 foreign e-commerce payments in <20 min); scores here say nothing about real-world fraud. Features are point-in-time (past events only), so the first payments of a burst look normal, which caps recall.
- Segments are descriptive clusters; no ground-truth segment labels exist to validate against.
- Search budget is small (8 candidates, 200k-row subsample); no fairness/drift monitoring; no serving endpoint yet (Phase 8).
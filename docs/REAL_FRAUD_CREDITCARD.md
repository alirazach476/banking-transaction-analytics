# Fraud models on real card transactions (public 'creditcard' dataset)

Real, anonymised European card transactions from two days in September 2013 (ULB Machine Learning Group; Dal Pozzolo, Caelen, Johnson and Bontempi, CIDM 2015): 284,807 transactions, 492 frauds (0.17%). Features V1-V28 are PCA components published by the owners; Time and Amount are raw. Downloaded from OpenML (dataset 1597, licence 'Public'). This is the project's only evidence about real card fraud; the other fraud results come from simulators or synthetic data.

Split by time: train on the first 70% of the span (172,090 rows, 360 frauds), test on the rest (112,717 rows, 132 frauds, rate 0.1170%). The random-guess PR-AUC equals the test fraud rate (0.0012).

| model | PR-AUC (95% bootstrap CI) | ROC-AUC | best F1 | precision | recall | recall at 1% false-positive rate |
|---|---|---|---|---|---|---|
| Logistic regression (balanced) | 0.7487 (0.664-0.831) | 0.9773 | 0.7803 | 0.956 | 0.6591 | 0.8636 |
| IsolationForest (unsupervised) | 0.0236 (0.018-0.031) | 0.9394 | 0.0655 | 0.0351 | 0.5 | 0.2727 |
| XGBoost | 0.7888 (0.719-0.848) | 0.9819 | 0.8205 | 0.9412 | 0.7273 | 0.8485 |

Most important XGBoost features: V14 0.463, V10 0.1, V17 0.071, V4 0.044, V12 0.035, V19 0.018, V21 0.018, V13 0.017 (PCA components, so not interpretable as named variables).

## Limits
- Only 132 frauds in the test period, hence the wide bootstrap intervals; differences between models smaller than the intervals should not be read as real.
- Two days of one European issuer in 2013 and anonymised features: performance here does not transfer to Pakistani card or wallet fraud, and the NovaBank API's fraud model (trained on synthetic data) is unaffected by this result.
- The time split puts all test frauds after the training period, which is the realistic direction, but a two-day window has little concept drift to test.

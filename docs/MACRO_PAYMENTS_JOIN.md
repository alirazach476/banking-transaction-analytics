# Real macro series joined to synthetic payments

Months joined: 25 (2023-03 to 2025-03); 24 month-over-month changes. Output table: `data/processed/bi/macro_payments_monthly.csv` (payments, approval rate, avg amount, policy rate, CPI, USD/PKR, real and USD-converted average amount).

| payment metric (%chg) | macro change | Spearman | permutation p |
|---|---|---|---|
| payments | policy_rate | -0.13 | 0.56 |
| payments | cpi_index | 0.23 | 0.284 |
| payments | usd_pkr | -0.03 | 0.888 |
| approval_rate | policy_rate | -0.03 | 0.915 |
| approval_rate | cpi_index | 0.31 | 0.129 |
| approval_rate | usd_pkr | 0.03 | 0.871 |
| avg_amount | policy_rate | -0.03 | 0.891 |
| avg_amount | cpi_index | 0.11 | 0.608 |
| avg_amount | usd_pkr | -0.11 | 0.612 |

0 of 9 pass p<0.05; 9 tests; ~0.5 would pass 5% by chance alone.

## Reading
- The payments are SYNTHETIC and the generator uses no macro input, so there is no real relationship to find. Correlations near zero are the expected, correct outcome and confirm no macro leakage into the generator.
- Any pair that passes p<0.05 should be treated as chance given the number of tests and only ~24 changes.
- This table is useful for scenario work (e.g. restating synthetic average amounts in real or USD terms), not for estimating how macro conditions affect payments.
- To make macro effects testable, the generator would need an explicit macro-sensitivity model (e.g. volume elasticity to CPI/FX), and then recovery of that elasticity could be validated the same way the logit coefficients were.

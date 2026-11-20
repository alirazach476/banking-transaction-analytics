# Phase 6 results (measured; synthetic data)

Payments used (no injected defects, with an authorization response): **474,866**; overall decline rate **0.0496**.

## 1. Logit recovery of true coefficients (n=394,398, USD, non-expired/blocked cards)

| term | true | estimate | 95% CI | CI covers truth |
|---|---|---|---|---|
| const | -3.4 | -3.385 | [-3.407, -3.362] | yes |
| intl | 0.6 | 0.496 | [0.368, 0.624] | yes |
| cnp | 0.5 | 0.487 | [0.455, 0.518] | yes |
| log10_amount_centered | 0.45 | 0.472 | [0.442, 0.501] | yes |
| night | 0.5 | 0.502 | [0.447, 0.557] | yes |
| fraud | 1.5 | 1.437 | [1.271, 1.602] | yes |

## 2. Tests
- Channel vs decline chi-square: chi2=1283.5, dof=4, p=1.24e-276
- Response time approved vs declined (Mann-Whitney): medians 350 vs 395 ms, p=0
- With hundreds of thousands of rows nearly any difference is 'significant'; read the effect sizes (decline rate by flag in the JSON).

## 3. XGBoost (time split: train on first 80% of time, test on last 20%)
- train/test rows: 379,893 / 94,973; test base decline rate 0.0490
- ROC-AUC 0.635; excluding forced (expired/blocked-card) declines 0.606; PR-AUC 0.167; Brier 0.0430

SHAP top features (mean |SHAP|, log-odds): cnp 0.194, log_amt 0.1891, card_status_Blocked 0.0523, night 0.0457, card_status_Expired 0.0446, intl 0.0443, hour 0.0392, card_status_Active 0.0294, card_status_Inactive 0.0212, channel_E-Commerce 0.0146

## Caveats
- Labels and features come from a synthetic generator with a known logit; high recovery shows the pipeline is sound, not that real-world declines behave this way.
- Expired/Blocked cards are deterministic declines (a leak-like feature); the AUC excluding them is the honest signal.
- No hyper-parameter search or fairness analysis was done.
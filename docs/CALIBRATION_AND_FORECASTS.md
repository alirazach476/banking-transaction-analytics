# Calibration, forecasts and the real-vs-synthetic comparison

Three additions that put the real SBP, BIS and World Bank data to work. Everything below is reproducible; numbers are from the committed result files.

| What | Script | Output | Where it shows |
|---|---|---|---|
| Calibrate the payment generator to real aggregates | `scripts/calibrate_payments.py` | `config/pakistan_calibration.json`, `docs/_parts/calibration_results.json` | Real vs Synthetic page |
| Forecast real series with a backtest | `scripts/forecast_real_series.py` | `docs/_parts/forecasts.json`, `forecast` section of `public/analysis.json` | Global Financial Intelligence, tab "Forecasts (real series)" |
| Compare real, dashboard and calibrated | `src/api/dash/benchmarks.py` (`/v1/benchmarks`) | live JSON | Real vs Synthetic page (`/benchmarks`) |

## 1. Calibrating the generator

The generator (`src/payments/generator.py`) takes an optional `Calibration` (`src/payments/config.py`). With none set, output is byte-identical to the original (a test checks this), so the validated baseline stays reproducible. Set `PAYMENT_CALIBRATION=config/pakistan_calibration.json` to generate calibrated payments.

**Calibrated (each has a real target, SBP Payment Systems Review Q3 FY26):**

| Property | Real target | Original synthetic | Calibrated |
|---|---|---|---|
| Card-not-present share of card payments (e-commerce / (POS + e-commerce)) | 10.3% | 33.8% | 10.4% |
| Annual growth of card payment volume (POS and e-commerce, volume-weighted) | +42.4% | +4.9% | +43.5% |
| Average POS ticket (USD) | $20.10 | $162.57 | $20.17 |
| Average e-commerce ticket (USD) | $17.62 | $165.21 | $17.74 |
| Average wallet ticket (USD) | $13.11 | $161.32 | $13.11 |

(Measured on 150,000 generated payments, seed 42; the dashboard's own data measures 33.8%, +4.3% and $160.58 on the same definitions, so the generated baseline and the dashboard agree.)

**These match largely by construction.** They show the calibration works; they do not show the data is realistic.

**Not calibrated (no real target in the data):** decline and approval rates; fraud and anomaly rates; the wallet channel's share (real wallet volume is mostly person-to-person transfers, not merchant card payments); merchant country, currency and customer-profile mix; merchant-category mix; time-of-day, weekday and seasonal patterns.

**Side effect, measured:** the decline rate in the calibrated companion is 3.0% against 4.7% originally, because the decline model depends on amount and channel. This is a consequence of calibrating other things, not a calibrated value; the real decline rate is unknown.

**Assumptions:** the chip : contactless split inside POS is not published (the generator's 25 : 30 ratio is kept); the real growth rate is applied as a constant compound rate, so it matches the pace of growth, not the calendar years; rupee tickets are converted at one rate (BIS Sep-2026 average, 277.22; the rupee moved about 2.5% over two years).

**Why the dashboard's own transactions are not replaced.** Rebuilding every table on calibrated data would change metrics that were not calibrated (the decline rate above) and invalidate the numbers documented elsewhere, so the calibrated dataset is a companion: it is generated with the same generator and compared on the Real vs Synthetic page. To switch the whole pipeline, run the payment generator with `PAYMENT_CALIBRATION` set and then `dbt build` plus `python scripts/create_ui_objects.py`; expect the dashboard figures to change.

## 2. Forecasts of real series

Five real series, chosen because their length allows (or, for two of them, barely allows) a backtest:

| Series | Frequency, points | Published model | Backtest MASE (naive) | Beats naive? | 80% band hit rate |
|---|---|---|---|---|---|
| SBP retail payment volume | quarterly, 10 | drift | 0.72 (1.66) | yes | 67% |
| Raast instant payments | quarterly, 10 | damped ETS | 0.49 (1.56) | yes | 67% |
| Personal remittances (World Bank) | annual, 25 | damped ETS | 2.37 (2.59) | yes, narrowly | 83% |
| USD/PKR (BIS monthly average) | monthly, 141 | naive | 0.86 (0.86) | no | 88% |
| Foreign banks' claims on Pakistan (BIS) | quarterly, 106 | naive | 1.77 (1.63) | no | 75% |

**Method.** Candidate models on the log scale (naive, drift, damped Holt, ARIMA(1,1,0) with drift for long series, seasonal naive where there is history). A rolling-origin backtest refits at each origin and compares the forecast with what actually happened. Long series choose the model on an earlier validation window and are scored on the last window; the two short quarterly series cannot be split, so choice and score share a window and the result is flagged optimistic. MASE below 1 beats a naive "same as last period" forecast. A model that does not beat naive on the scoring window is not published: the forecast falls back to naive (flat), which is the honest answer for an exchange rate that behaves like a random walk. The 80% band comes from one-step backtest errors widened by the square root of the horizon.

**Limits.** Ten quarters is very little: those two forecasts show direction and rough size, not precision, and SBP revises earlier quarters. Raast grew 6.9x in nine quarters, so a damped trend may understate it. The remittance score is only slightly better than naive. Nothing here models policy changes or shocks; bands do not cover them.

## 3. Real vs synthetic page

`/benchmarks` shows a scorecard of each metric (real, dashboard, calibrated companion, gap, status), grouped bar charts, the real SBP channel table, what was and was not calibrated, and the assumptions. Status is "matches" within 10% of the real value, "off" within 50%, otherwise "far off"; metrics without a real target say "no real target".

## Tests
`tests/test_calibration.py` (baseline reproducible with no calibration; calibrated generation hits the real targets within tolerance while the original does not; amount scaling touches only the named channel; weights respected; the file's targets equal the real-data values), `tests/test_forecasts.py` (models, no look-ahead in the backtest, a trend beats naive, a random walk is not dressed up, band widens, short-series flag, labels roll over, published results are consistent), `tests/test_dash_api.py` (benchmark metrics against independent SQL), and the Playwright tests for the page and the forecasts tab.

# Postgres + dbt scale benchmark (isolated temporary database, dropped afterwards)

One run per size on the dev machine (embedded Postgres, default settings, no tuning), other work running concurrently at times. Indicative only.

| payments requested | generate | COPY load (4 raw tables) | dbt build models/payments | dbt ok | DB size | payments in int_payment_outcomes |
|---|---|---|---|---|---|---|
| 1,000,000 | 112.8 s | 99.2 s | 278.7 s | True | 1275 MB | 986,383 |
| 2,000,000 | 229.1 s | 188.6 s | 532.2 s | True | 2538 MB | 1,972,164 |

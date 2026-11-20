# API load test (localhost, 1 uvicorn worker, rate limit off)

1500 requests per endpoint, concurrency 20; measured 2026-11-21 on the dev machine with the 500K-payment dataset in embedded Postgres. Indicative only: client and server share the machine.

| endpoint | req/s | p50 ms | p95 ms | p99 ms | errors |
|---|---|---|---|---|---|
| GET /health | 351 | 43.5 | 133.4 | 192.3 | 0 |
| GET /kpis/summary | 367 | 41.1 | 132.5 | 198.4 | 0 |
| GET /kpis/daily?limit=180 | 77 | 235.1 | 403.1 | 538.8 | 0 |
| GET /decline-reasons | 278 | 51.6 | 176.9 | 261.8 | 0 |
| GET /reconciliation/queue?limit=50 | 110 | 140.9 | 378.3 | 890.6 | 0 |
| POST /score/decline | 120 | 152.1 | 259.6 | 300.3 | 0 |
| POST /score/fraud | 161 | 111.5 | 208.1 | 357.4 | 0 |
| POST /score/fraud/card | 135 | 141.3 | 199.3 | 283.7 | 0 |

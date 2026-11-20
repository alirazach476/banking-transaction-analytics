"""Simple API load test: starts uvicorn (rate limit off), fires concurrent requests per endpoint, reports latency percentiles
and throughput, writes docs/API_LOAD_TEST.md. Single machine, localhost, one worker: indicative only.

Run: PYTHONPATH=. python scripts/api_load_test.py [--requests 1500] [--concurrency 20]
"""
from __future__ import annotations

import argparse
import asyncio
import os
import statistics
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
PORT = 8791

CASES = {
    "GET /health": ("GET", "/health", None),
    "GET /kpis/summary": ("GET", "/kpis/summary", None),
    "GET /kpis/daily?limit=180": ("GET", "/kpis/daily?limit=180", None),
    "GET /decline-reasons": ("GET", "/decline-reasons", None),
    "GET /reconciliation/queue?limit=50": ("GET", "/reconciliation/queue?limit=50", None),
    "POST /score/decline": ("POST", "/score/decline", {"amount": 120, "hour": 14, "channel": "E-commerce"}),
    "POST /score/fraud": ("POST", "/score/fraud", {"amount": 120, "hour": 14, "card_txn_60m": 2}),
    "POST /score/fraud/card": ("POST", "/score/fraud/card", {"card_id": "CARD-001602", "authorization_ts": "2025-06-01T03:00:00", "amount": 80}),
}


async def run_case(client, name, method, path, body, n, conc):
    sem = asyncio.Semaphore(conc)
    lat, errors = [], 0

    async def one():
        nonlocal errors
        async with sem:
            t0 = time.perf_counter()
            try:
                r = await client.request(method, path, json=body)
                if r.status_code != 200:
                    errors += 1
            except Exception:
                errors += 1
            lat.append((time.perf_counter() - t0) * 1000)

    t0 = time.perf_counter()
    await asyncio.gather(*[one() for _ in range(n)])
    wall = time.perf_counter() - t0
    lat.sort()
    return {"endpoint": name, "n": n, "rps": n / wall, "p50": statistics.median(lat), "p95": lat[int(len(lat) * 0.95) - 1],
            "p99": lat[int(len(lat) * 0.99) - 1], "errors": errors}


async def main_async(n, conc):
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{PORT}", timeout=30) as c:
        for _ in range(60):  # wait for startup
            try:
                if (await c.get("/health")).status_code == 200:
                    break
            except Exception:
                await asyncio.sleep(0.5)
        for name, (m, p, b) in CASES.items():  # warm-up (model loading, DB pool)
            await c.request(m, p, json=b)
        return [await run_case(c, name, m, p, b, n, conc) for name, (m, p, b) in CASES.items()]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--requests", type=int, default=1500)
    ap.add_argument("--concurrency", type=int, default=20)
    a = ap.parse_args()
    env = {**os.environ, "RATE_LIMIT_PER_MIN": "0", "PYTHONPATH": str(ROOT)}
    env.pop("API_KEY", None)
    srv = subprocess.Popen([sys.executable, "-m", "uvicorn", "src.api.main:app", "--port", str(PORT), "--log-level", "warning"],
                           cwd=ROOT, env=env)
    try:
        res = asyncio.run(main_async(a.requests, a.concurrency))
    finally:
        srv.terminate()
        srv.wait(timeout=15)
    lines = ["# API load test (localhost, 1 uvicorn worker, rate limit off)", "",
             f"{a.requests} requests per endpoint, concurrency {a.concurrency}; measured {time.strftime('%Y-%m-%d')} on the dev machine with the "
             "500K-payment dataset in embedded Postgres. Indicative only: client and server share the machine.", "",
             "| endpoint | req/s | p50 ms | p95 ms | p99 ms | errors |", "|---|---|---|---|---|---|"]
    for r in res:
        lines.append(f"| {r['endpoint']} | {r['rps']:.0f} | {r['p50']:.1f} | {r['p95']:.1f} | {r['p99']:.1f} | {r['errors']} |")
    (ROOT / "docs" / "API_LOAD_TEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

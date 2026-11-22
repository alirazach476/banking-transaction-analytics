"""Vercel serverless entry point for the hosted, read-only demo of the NovaBank analytics API.

Same FastAPI routers as the local app (src/api/dash), but reading a bundled DuckDB snapshot (data/demo.duckdb) instead of PostgreSQL.
No model scoring, no write-backs. All data is SYNTHETIC (plus real published aggregates on the Global page, served as a static file).
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DEMO_DUCKDB", str(ROOT / "data" / "demo.duckdb"))

from fastapi import FastAPI  # noqa: E402

from src.api.dash import router  # noqa: E402

app = FastAPI(title="NovaBank analytics API (hosted demo, read-only)", version="2.0")


@app.get("/health")
def health():
    return {"status": "ok", "demo": True, "synthetic_data_only": True}


app.include_router(router)

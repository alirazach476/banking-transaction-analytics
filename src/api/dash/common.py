"""Shared helpers for the analytics-UI routers: auth, SQL access, TTL cache, date ranges, prior-period maths."""
from __future__ import annotations

import datetime as dt
import functools
import os
import threading
import time
from decimal import Decimal

from fastapi import Header, HTTPException, Query
from sqlalchemy import text

from src.utils.db import get_engine

DEFAULT_FROM, DEFAULT_TO = dt.date(2023, 1, 1), dt.date(2025, 12, 31)  # extent of the synthetic data


def require_key(x_api_key: str | None = Header(default=None)):
    expected = os.getenv("API_KEY")
    if expected and x_api_key != expected:
        raise HTTPException(401, "invalid or missing X-API-Key")


@functools.lru_cache
def engine():
    return get_engine()


def _clean(v):
    if isinstance(v, Decimal):
        return float(v)
    return v


def q(sql: str, **params) -> list[dict]:
    try:
        with engine().connect() as c:
            return [{k: _clean(v) for k, v in r._mapping.items()} for r in c.execute(text(sql), params)]
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(503, f"database unavailable or query failed: {type(exc).__name__}") from exc


def write(sql: str, **params) -> None:
    """Execute a data-changing statement in its own committed transaction."""
    try:
        with engine().begin() as c:
            c.execute(text(sql), params)
    except Exception as exc:
        raise HTTPException(503, f"database write failed: {type(exc).__name__}") from exc


def one(sql: str, **params) -> dict:
    rows = q(sql, **params)
    return rows[0] if rows else {}


_CACHE: dict = {}
_LOCK = threading.Lock()


def cached(ttl: int = 120):
    """Cache a function's result in-process for `ttl` seconds (keyed by arguments). Expensive aggregates only."""
    def deco(fn):
        @functools.wraps(fn)
        def wrap(*a, **kw):
            key = (fn.__module__, fn.__name__, a, tuple(sorted(kw.items())))
            now = time.monotonic()
            with _LOCK:
                hit = _CACHE.get(key)
                if hit and now - hit[0] < ttl:
                    return hit[1]
            val = fn(*a, **kw)
            with _LOCK:
                _CACHE[key] = (now, val)
            return val
        return wrap
    return deco


class DR:
    """Date range with its immediately preceding period of equal length (for period-over-period comparison)."""
    def __init__(self, d0: dt.date, d1: dt.date):
        if d0 > d1:
            raise HTTPException(422, "'from' must not be after 'to'")
        self.d0, self.d1 = d0, d1
        self.days = (d1 - d0).days + 1
        self.p1 = d0 - dt.timedelta(days=1)
        self.p0 = self.p1 - dt.timedelta(days=self.days - 1)

    def grain(self) -> str:
        return "day" if self.days <= 120 else "week" if self.days <= 540 else "month"

    def key(self):
        return (self.d0, self.d1)


def date_range(from_: dt.date | None = Query(None, alias="from"), to: dt.date | None = Query(None)) -> DR:
    return DR(from_ or DEFAULT_FROM, to or DEFAULT_TO)


def delta(cur, prior, rate: bool = False):
    """Percentage change for counts/values; percentage-point change for rates (both fractions)."""
    if cur is None or prior is None:
        return None
    if rate:
        return (cur - prior) * 100
    return None if prior == 0 else (cur - prior) / prior * 100


def safe_div(a, b):
    return None if not b else a / b

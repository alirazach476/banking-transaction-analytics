"""Shared pytest fixtures for NovaBank tests."""

from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import pytest

from config.settings import get_settings


@pytest.fixture
def settings():
    return get_settings()


@pytest.fixture
def sample_transactions() -> pd.DataFrame:
    """Minimal transaction set for anomaly unit tests."""
    base = datetime(2024, 6, 1, 12, 0, 0)
    rows = []
    for i in range(10):
        rows.append(
            {
                "transaction_id": f"TXN-TEST-{i:04d}",
                "account_id": "ACC-00000001",
                "customer_id": "CUST-00000001",
                "transaction_timestamp": base + timedelta(hours=i),
                "transaction_type": "Payment",
                "amount": 50.0 + i,
                "currency": "USD",
                "channel": "Mobile App",
                "transaction_status": "Completed",
            }
        )
    # High amount outlier
    rows.append(
        {
            "transaction_id": "TXN-TEST-OUTLIER",
            "account_id": "ACC-00000001",
            "customer_id": "CUST-00000001",
            "transaction_timestamp": base + timedelta(hours=11),
            "transaction_type": "Transfer",
            "amount": 50000.0,
            "currency": "USD",
            "channel": "Internet Banking",
            "transaction_status": "Completed",
        }
    )
    return pd.DataFrame(rows)


@pytest.fixture
def high_amount_config() -> dict:
    return {
        "high_amount_zscore": 2.0,
        "high_amount_multiplier": 5.0,
        "high_frequency_daily_count": 100,
        "rapid_window_minutes": 10,
        "rapid_count": 100,
        "night_hours": [0, 1, 2, 3, 4, 5],
        "night_min_amount": 100000,
        "failure_streak": 10,
        "behavior_change_multiplier": 100.0,
    }


@pytest.fixture(scope="session")
def test_engine():
    """Engine for a dedicated ``novabank_test`` database (skips if no server is reachable)."""
    import psycopg2
    from sqlalchemy import create_engine

    s = get_settings().db
    try:
        admin = psycopg2.connect(host=s.host, port=s.port, dbname="postgres", user=s.user,
                                 password=s.password, connect_timeout=3)
    except Exception as exc:  # pragma: no cover - environment dependent
        pytest.skip(f"PostgreSQL not reachable: {exc}")
    admin.autocommit = True
    cur = admin.cursor()
    cur.execute("SELECT 1 FROM pg_database WHERE datname = 'novabank_test'")
    if not cur.fetchone():
        cur.execute("CREATE DATABASE novabank_test")
    admin.close()
    url = s.sqlalchemy_url.rsplit("/", 1)[0] + "/novabank_test"
    engine = create_engine(url, pool_pre_ping=True)
    from src.utils.db import run_ddl

    run_ddl(engine)
    yield engine
    engine.dispose()

"""Database connection helpers."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Generator

import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from config.settings import get_settings


def get_engine(echo: bool = False) -> Engine:
    settings = get_settings()
    return create_engine(settings.db.sqlalchemy_url, echo=echo, pool_pre_ping=True)


@contextmanager
def get_connection() -> Generator:
    engine = get_engine()
    conn = engine.connect()
    try:
        yield conn
    finally:
        conn.close()


def _strip_sql_comments(sql: str) -> str:
    """Remove full-line -- comments; keep inline SQL intact enough for DDL."""
    lines = []
    for line in sql.splitlines():
        stripped = line.strip()
        if stripped.startswith("--"):
            continue
        lines.append(line)
    return "\n".join(lines)


def execute_sql_file(path: str, engine: Engine | None = None) -> None:
    engine = engine or get_engine()
    raw = open(path, encoding="utf-8").read()
    sql = _strip_sql_comments(raw)
    statements = [s.strip() for s in sql.split(";") if s.strip()]
    with engine.begin() as conn:
        for stmt in statements:
            conn.execute(text(stmt))


def run_ddl(engine: Engine | None = None) -> None:
    """Apply all SQL DDL scripts in order."""
    settings = get_settings()
    ddl_dir = settings.project_root / "sql" / "ddl"
    engine = engine or get_engine()
    for name in [
        "01_create_schemas.sql",
        "02_create_raw_tables.sql",
        "03_create_audit_tables.sql",
        "04_create_monitoring_tables.sql",
    ]:
        path = ddl_dir / name
        if path.exists():
            execute_sql_file(str(path), engine)


def read_sql(query: str, params: dict | None = None) -> pd.DataFrame:
    engine = get_engine()
    return pd.read_sql(text(query), engine, params=params or {})


def table_count(schema: str, table: str) -> int:
    df = read_sql(f"SELECT COUNT(*) AS cnt FROM {schema}.{table}")
    return int(df.iloc[0]["cnt"])

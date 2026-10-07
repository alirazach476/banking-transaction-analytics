"""
Idempotent ingestion of source CSVs into PostgreSQL raw schema.

Uses DELETE + INSERT or ON CONFLICT DO NOTHING so re-runs do not duplicate rows.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from config.settings import get_settings
from src.utils.db import get_engine, run_ddl
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)

# Mapping: logical name -> (source relative path, raw table, business key)
SOURCE_MAP = [
    ("customers", "customer_system/customers.csv", "customers", "customer_id", "customer_system"),
    ("accounts", "core_banking/accounts.csv", "accounts", "account_id", "core_banking"),
    ("branches", "branch_system/branches.csv", "branches", "branch_id", "branch_system"),
    ("merchants", "card_system/merchants.csv", "merchants", "merchant_id", "card_system"),
    ("cards", "card_system/cards.csv", "cards", "card_id", "card_system"),
    ("transactions", "core_banking/transactions.csv", "transactions", "transaction_id", "core_banking"),
    ("transfers", "core_banking/transfers.csv", "transfers", "transfer_id", "core_banking"),
    ("atm_transactions", "atm_system/atm_transactions.csv", "atm_transactions", "atm_txn_id", "atm_system"),
    ("card_transactions", "card_system/card_transactions.csv", "card_transactions", "card_txn_id", "card_system"),
]


def _start_run(engine, pipeline_name: str, mode: str) -> str:
    run_id = str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO audit.pipeline_runs
                    (run_id, pipeline_name, start_time, status, mode)
                VALUES (:run_id, :name, :start, 'RUNNING', :mode)
                """
            ),
            {
                "run_id": run_id,
                "name": pipeline_name,
                "start": datetime.now(timezone.utc),
                "mode": mode,
            },
        )
    return run_id


def _finish_run(engine, run_id: str, status: str, rows: int, failed: int = 0) -> None:
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE audit.pipeline_runs
                SET end_time = :end, status = :status,
                    rows_processed = :rows, rows_failed = :failed
                WHERE run_id = :run_id
                """
            ),
            {
                "end": datetime.now(timezone.utc),
                "status": status,
                "rows": rows,
                "failed": failed,
                "run_id": run_id,
            },
        )


def _load_table(
    engine,
    run_id: str,
    name: str,
    csv_path: Path,
    table: str,
    key: str,
    source_system: str,
    mode: str,
    watermark: datetime | None,
) -> int:
    if not csv_path.exists():
        logger.warning("Missing source file: %s", csv_path)
        return 0

    df = pd.read_csv(csv_path, dtype=str, keep_default_na=False, na_values=[""])
    rows_read = len(df)

    # Incremental: filter by updated_at / timestamp if present
    ts_col = None
    for c in ("updated_at", "transaction_timestamp", "transfer_timestamp", "timestamp"):
        if c in df.columns:
            ts_col = c
            break

    if mode == "incremental" and watermark is not None and ts_col:
        parsed = pd.to_datetime(df[ts_col], errors="coerce")
        df = df[parsed > watermark]
        logger.info(
            "%s incremental: %s/%s rows after watermark %s",
            name,
            len(df),
            rows_read,
            watermark,
        )

    df["_source_file"] = str(csv_path.name)
    df["_source_system"] = source_system
    # Let DB DEFAULT NOW() populate _ingested_at (avoid text→timestamptz mismatch)

    # Deduplicate within batch on business key (keep last)
    if key in df.columns:
        df = df.drop_duplicates(subset=[key], keep="last")

    started = datetime.now(timezone.utc)
    loaded = 0

    with engine.begin() as conn:
        if mode == "full":
            conn.execute(text(f"TRUNCATE TABLE raw.{table}"))

        # Stage via temp table then upsert
        temp = f"_stg_{table}"
        df.to_sql(temp, conn, schema="raw", if_exists="replace", index=False, method="multi", chunksize=2000)

        cols = list(df.columns)
        col_list = ", ".join(f'"{c}"' for c in cols)
        select_list = ", ".join(f't."{c}"' for c in cols)

        if mode == "full":
            sql = (
                f'INSERT INTO raw.{table} ({col_list}) '
                f'SELECT {select_list} FROM raw.{temp} t'
            )
            result = conn.execute(text(sql))
            loaded = result.rowcount if result.rowcount and result.rowcount > 0 else len(df)
        else:
            sql = f"""
                INSERT INTO raw.{table} ({col_list})
                SELECT {select_list}
                FROM raw.{temp} t
                WHERE t."{key}" IS NULL
                   OR NOT EXISTS (
                        SELECT 1 FROM raw.{table} r WHERE r."{key}" = t."{key}"
                   )
            """
            result = conn.execute(text(sql))
            loaded = result.rowcount if result.rowcount is not None else 0

        conn.execute(text(f"DROP TABLE IF EXISTS raw.{temp}"))

        conn.execute(
            text(
                """
                INSERT INTO audit.source_ingestion
                    (run_id, source_name, source_system, source_file, rows_read,
                     rows_loaded, rows_rejected, started_at, completed_at, status)
                VALUES
                    (:run_id, :name, :sys, :file, :read, :loaded, :rej, :start, :end, 'SUCCESS')
                """
            ),
            {
                "run_id": run_id,
                "name": name,
                "sys": source_system,
                "file": str(csv_path),
                "read": rows_read,
                "loaded": loaded,
                "rej": max(rows_read - loaded, 0),
                "start": started,
                "end": datetime.now(timezone.utc),
            },
        )

        # Update watermark
        if ts_col and not df.empty:
            max_ts = pd.to_datetime(df[ts_col], errors="coerce").max()
            if pd.notna(max_ts):
                conn.execute(
                    text(
                        """
                        INSERT INTO audit.pipeline_watermarks
                            (pipeline_name, source_name, last_watermark, updated_at)
                        VALUES ('ingest_raw', :src, :wm, :upd)
                        ON CONFLICT (pipeline_name, source_name)
                        DO UPDATE SET last_watermark = EXCLUDED.last_watermark,
                                      updated_at = EXCLUDED.updated_at
                        """
                    ),
                    {
                        "src": name,
                        "wm": max_ts.to_pydatetime(),
                        "upd": datetime.now(timezone.utc),
                    },
                )

    logger.info("Loaded raw.%s: %s rows (mode=%s)", table, f"{loaded:,}", mode)
    return loaded


def _get_watermark(engine, source_name: str) -> datetime | None:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT last_watermark FROM audit.pipeline_watermarks
                WHERE pipeline_name = 'ingest_raw' AND source_name = :src
                """
            ),
            {"src": source_name},
        ).fetchone()
    return row[0] if row else None


def main(mode: str | None = None) -> str:
    settings = get_settings()
    mode = mode or settings.pipeline_mode
    if mode not in ("full", "incremental"):
        mode = "full"

    engine = get_engine()
    logger.info("Ensuring DDL schemas/tables exist...")
    run_ddl(engine)

    run_id = _start_run(engine, "ingest_raw", mode)
    total = 0
    try:
        root = settings.data_source_dir
        for name, rel, table, key, system in SOURCE_MAP:
            wm = _get_watermark(engine, name) if mode == "incremental" else None
            total += _load_table(
                engine, run_id, name, root / rel, table, key, system, mode, wm
            )
        _finish_run(engine, run_id, "SUCCESS", total)
        logger.info("Ingestion complete. run_id=%s rows=%s", run_id, f"{total:,}")
    except Exception as exc:
        _finish_run(engine, run_id, "FAILED", total, failed=1)
        logger.exception("Ingestion failed: %s", exc)
        raise
    return run_id


if __name__ == "__main__":
    import sys

    m = sys.argv[1] if len(sys.argv) > 1 else None
    main(m)

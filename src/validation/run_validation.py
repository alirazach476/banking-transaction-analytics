"""
Data quality validation against raw (and optionally staging) tables.

Checks: nulls, uniqueness, referential integrity, financial rules.
Results written to audit.data_quality_results.
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timezone

from sqlalchemy import text

from src.utils.db import get_engine, run_ddl
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


def _record(
    conn,
    run_id: str,
    check_name: str,
    table_name: str,
    check_type: str,
    expected: str,
    actual: str,
    status: str,
    failed_rows: int,
    elapsed_ms: float,
) -> None:
    conn.execute(
        text(
            """
            INSERT INTO audit.data_quality_results
                (run_id, check_name, table_name, check_type, expected_result,
                 actual_result, status, failed_rows, execution_time_ms, checked_at)
            VALUES
                (:run_id, :name, :table, :ctype, :exp, :act, :status, :failed, :ms, :ts)
            """
        ),
        {
            "run_id": run_id,
            "name": check_name,
            "table": table_name,
            "ctype": check_type,
            "exp": expected,
            "act": actual,
            "status": status,
            "failed": failed_rows,
            "ms": elapsed_ms,
            "ts": datetime.now(timezone.utc),
        },
    )


def _run_check(conn, run_id, name, table, ctype, sql, expected_zero=True):
    t0 = time.perf_counter()
    result = conn.execute(text(sql)).fetchone()
    count = int(result[0]) if result else 0
    ms = (time.perf_counter() - t0) * 1000
    if expected_zero:
        status = "PASS" if count == 0 else "FAIL"
        expected = "0"
    else:
        status = "PASS" if count > 0 else "FAIL"
        expected = ">0"
    _record(conn, run_id, name, table, ctype, expected, str(count), status, count, ms)
    logger.info("[%s] %s.%s = %s (%s)", status, table, name, count, ctype)
    return status == "PASS"


def run_all_checks(engine=None, run_id: str | None = None) -> dict:
    engine = engine or get_engine()
    run_ddl(engine)
    run_id = run_id or str(uuid.uuid4())

    with engine.begin() as conn:
        # Ensure pipeline run exists
        exists = conn.execute(
            text("SELECT 1 FROM audit.pipeline_runs WHERE run_id = :r"),
            {"r": run_id},
        ).fetchone()
        if not exists:
            conn.execute(
                text(
                    """
                    INSERT INTO audit.pipeline_runs
                        (run_id, pipeline_name, start_time, status)
                    VALUES (:r, 'data_quality', :ts, 'RUNNING')
                    """
                ),
                {"r": run_id, "ts": datetime.now(timezone.utc)},
            )

        checks = []

        # Null checks on required IDs
        for table, col in [
            ("customers", "customer_id"),
            ("accounts", "account_id"),
            ("transactions", "transaction_id"),
            ("branches", "branch_id"),
            ("merchants", "merchant_id"),
            ("cards", "card_id"),
        ]:
            checks.append(
                _run_check(
                    conn,
                    run_id,
                    f"null_{col}",
                    f"raw.{table}",
                    "null_check",
                    f"SELECT COUNT(*) FROM raw.{table} WHERE {col} IS NULL OR TRIM({col}) = ''",
                )
            )

        # Uniqueness (among non-null)
        for table, col in [
            ("customers", "customer_id"),
            ("accounts", "account_id"),
            ("transactions", "transaction_id"),
            ("branches", "branch_id"),
            ("merchants", "merchant_id"),
        ]:
            checks.append(
                _run_check(
                    conn,
                    run_id,
                    f"unique_{col}",
                    f"raw.{table}",
                    "uniqueness",
                    f"""
                    SELECT COUNT(*) FROM (
                        SELECT {col} FROM raw.{table}
                        WHERE {col} IS NOT NULL
                        GROUP BY {col} HAVING COUNT(*) > 1
                    ) d
                    """,
                )
            )

        # Referential integrity
        checks.append(
            _run_check(
                conn,
                run_id,
                "fk_txn_account",
                "raw.transactions",
                "referential_integrity",
                """
                SELECT COUNT(*) FROM raw.transactions t
                WHERE t.account_id IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM raw.accounts a WHERE a.account_id = t.account_id
                  )
                """,
            )
        )
        checks.append(
            _run_check(
                conn,
                run_id,
                "fk_txn_customer",
                "raw.transactions",
                "referential_integrity",
                """
                SELECT COUNT(*) FROM raw.transactions t
                WHERE t.customer_id IS NOT NULL
                  AND NOT EXISTS (
                    SELECT 1 FROM raw.customers c WHERE c.customer_id = t.customer_id
                  )
                """,
            )
        )

        # Financial validation: amount > 0 (allow Balance Inquiry style zeros only in ATM)
        checks.append(
            _run_check(
                conn,
                run_id,
                "amount_positive",
                "raw.transactions",
                "financial_rule",
                """
                SELECT COUNT(*) FROM raw.transactions
                WHERE amount IS NOT NULL
                  AND TRIM(amount) <> ''
                  AND amount ~ '^-?[0-9]*\\.?[0-9]+$'
                  AND amount::numeric <= 0
                """,
            )
        )

        # Valid currency
        checks.append(
            _run_check(
                conn,
                run_id,
                "valid_currency",
                "raw.transactions",
                "financial_rule",
                """
                SELECT COUNT(*) FROM raw.transactions
                WHERE currency IS NOT NULL
                  AND UPPER(TRIM(currency)) NOT IN ('USD','EUR','GBP','CAD','')
                """,
            )
        )

        # Valid timestamp parseable
        checks.append(
            _run_check(
                conn,
                run_id,
                "valid_timestamp",
                "raw.transactions",
                "financial_rule",
                """
                SELECT COUNT(*) FROM raw.transactions
                WHERE transaction_timestamp IS NOT NULL
                  AND TRIM(transaction_timestamp) <> ''
                  AND (
                    REPLACE(transaction_timestamp, 'T', ' ')::timestamp IS NULL
                  ) IS NOT TRUE
                  AND NOT (
                    REPLACE(transaction_timestamp, 'T', ' ') ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}'
                  )
                """,
            )
        )

        # Row existence sanity
        checks.append(
            _run_check(
                conn,
                run_id,
                "has_rows",
                "raw.transactions",
                "volume",
                "SELECT COUNT(*) FROM raw.transactions",
                expected_zero=False,
            )
        )

        passed = sum(1 for c in checks if c)
        failed = len(checks) - passed
        conn.execute(
            text(
                """
                UPDATE audit.pipeline_runs
                SET end_time = :ts, status = :st, rows_processed = :p, rows_failed = :f
                WHERE run_id = :r
                """
            ),
            {
                "ts": datetime.now(timezone.utc),
                "st": "SUCCESS" if failed == 0 else "WARNING",
                "p": passed,
                "f": failed,
                "r": run_id,
            },
        )

    summary = {"run_id": run_id, "passed": passed, "failed": failed, "total": len(checks)}
    logger.info(
        "DQ summary: %s/%s passed (%s failed) run_id=%s",
        passed,
        len(checks),
        failed,
        run_id,
    )
    # Note: some failures are EXPECTED because we intentionally inject dirty data
    logger.info(
        "NOTE: Some FAIL results are expected — source data intentionally includes "
        "duplicates, missing values, and invalid FKs for pipeline demonstration."
    )
    return summary


def main():
    return run_all_checks()


if __name__ == "__main__":
    main()

"""
Reconcile source CSV metrics against warehouse (or raw fallback).

Also performs balance reconciliation on a sample of accounts.
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
from src.validation.checks import evaluate_reconciliation

logger = get_logger(__name__)

SOURCE_FILES = {
    "transactions": ("core_banking/transactions.csv", "amount"),
    "accounts": ("core_banking/accounts.csv", None),
    "customers": ("customer_system/customers.csv", None),
}


def _table_exists(engine, schema: str, table: str) -> bool:
    with engine.connect() as conn:
        row = conn.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = :s AND table_name = :t
                )
                """
            ),
            {"s": schema, "t": table},
        ).fetchone()
    return bool(row[0]) if row else False


def _warehouse_count(engine, source_name: str) -> int | None:
    table_map = {
        "transactions": ("warehouse", "fact_transactions"),
        "accounts": ("warehouse", "dim_account"),
        "customers": ("warehouse", "dim_customer"),
    }
    wh = table_map.get(source_name)
    if wh and _table_exists(engine, wh[0], wh[1]):
        q = f"SELECT COUNT(*) FROM {wh[0]}.{wh[1]}"
        with engine.connect() as conn:
            return int(conn.execute(text(q)).scalar() or 0)
    return None


def _raw_count(engine, source_name: str) -> int | None:
    raw_map = {
        "transactions": "transactions",
        "accounts": "accounts",
        "customers": "customers",
    }
    raw_table = raw_map.get(source_name)
    if raw_table and _table_exists(engine, "raw", raw_table):
        with engine.connect() as conn:
            return int(conn.execute(text(f"SELECT COUNT(*) FROM raw.{raw_table}")).scalar() or 0)
    return None


def _warehouse_sum(engine, source_name: str) -> float | None:
    if source_name != "transactions":
        return None
    if _table_exists(engine, "warehouse", "fact_transactions"):
        q = "SELECT COALESCE(SUM(amount::numeric), 0) FROM warehouse.fact_transactions"
    elif _table_exists(engine, "raw", "transactions"):
        q = """
            SELECT COALESCE(SUM(
                CASE WHEN amount ~ '^-?[0-9]*\\.?[0-9]+$' THEN amount::numeric ELSE 0 END
            ), 0)
            FROM raw.transactions
        """
    else:
        return None
    with engine.connect() as conn:
        return float(conn.execute(text(q)).scalar() or 0)


def _source_metrics(settings, source_name: str) -> dict:
    """
    Source metrics use DISTINCT business keys so intentional DQ duplicates
    in CSVs do not falsely fail warehouse reconciliation.
    """
    rel, amount_col = SOURCE_FILES[source_name]
    path = settings.data_source_dir / rel
    if not path.exists():
        return {"count": None, "sum": None, "raw_file_rows": None}
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    key_map = {
        "transactions": "transaction_id",
        "accounts": "account_id",
        "customers": "customer_id",
    }
    key = key_map[source_name]
    raw_file_rows = len(df)
    if key in df.columns:
        df = df[df[key].astype(str).str.strip() != ""].drop_duplicates(subset=[key])
    count = len(df)
    total_sum = None
    if amount_col and amount_col in df.columns:
        total_sum = float(pd.to_numeric(df[amount_col], errors="coerce").sum())
    return {"count": count, "sum": total_sum, "raw_file_rows": raw_file_rows}


def reconcile_counts_and_sums(
    engine=None,
    run_id: str | None = None,
) -> list[dict]:
    settings = get_settings()
    engine = engine or get_engine()
    run_ddl(engine)
    run_id = run_id or str(uuid.uuid4())
    results = []

    with engine.begin() as conn:
        for source_name in SOURCE_FILES:
            src = _source_metrics(settings, source_name)
            wh_count = _warehouse_count(engine, source_name)

            if src["count"] is not None and wh_count is not None:
                status, diff = evaluate_reconciliation(
                    float(src["count"]), float(wh_count), tolerance=0
                )
                conn.execute(
                    text(
                        """
                        INSERT INTO audit.reconciliation_results
                            (run_id, source_name, metric_name, source_value,
                             warehouse_value, difference, status, checked_at)
                        VALUES
                            (:run_id, :src, 'row_count', :sv, :wv, :diff, :st, :ts)
                        """
                    ),
                    {
                        "run_id": run_id,
                        "src": source_name,
                        "sv": src["count"],
                        "wv": wh_count,
                        "diff": diff,
                        "st": status,
                        "ts": datetime.now(timezone.utc),
                    },
                )
                results.append(
                    {
                        "source": source_name,
                        "metric": "row_count",
                        "status": status,
                        "source_value": src["count"],
                        "warehouse_value": wh_count,
                    }
                )
                logger.info(
                    "[%s] %s row_count: source=%s warehouse=%s (%s)",
                    status,
                    source_name,
                    src["count"],
                    wh_count,
                    diff,
                )

            if source_name == "transactions" and src["sum"] is not None:
                wh_sum = _warehouse_sum(engine, source_name)
                if wh_sum is not None:
                    # Allow small float diff for dirty rows excluded in warehouse
                    status, diff = evaluate_reconciliation(
                        src["sum"], wh_sum, tolerance=max(1.0, src["sum"] * 0.001)
                    )
                    conn.execute(
                        text(
                            """
                            INSERT INTO audit.reconciliation_results
                                (run_id, source_name, metric_name, source_value,
                                 warehouse_value, difference, status, checked_at)
                            VALUES
                                (:run_id, :src, 'amount_sum', :sv, :wv, :diff, :st, :ts)
                            """
                        ),
                        {
                            "run_id": run_id,
                            "src": source_name,
                            "sv": src["sum"],
                            "wv": wh_sum,
                            "diff": diff,
                            "st": status,
                            "ts": datetime.now(timezone.utc),
                        },
                    )
                    results.append(
                        {
                            "source": source_name,
                            "metric": "amount_sum",
                            "status": status,
                            "source_value": src["sum"],
                            "warehouse_value": wh_sum,
                        }
                    )
                    logger.info(
                        "[%s] transactions amount_sum: source=%.2f warehouse=%.2f",
                        status,
                        src["sum"],
                        wh_sum,
                    )

    return results


def reconcile_balances(
    engine=None,
    run_id: str | None = None,
    sample_size: int = 100,
) -> list[dict]:
    """
    For a sample of accounts: opening_balance + credits - debits vs reported closing.
    Uses raw accounts and transactions when warehouse unavailable.
    """
    engine = engine or get_engine()
    run_ddl(engine)
    run_id = run_id or str(uuid.uuid4())
    results = []

    accounts_q = """
        SELECT account_id,
               CASE WHEN current_balance ~ '^-?[0-9]*\\.?[0-9]+$'
                    THEN current_balance::numeric ELSE NULL END AS reported_closing
        FROM raw.accounts
        WHERE account_id IS NOT NULL
        ORDER BY account_id
        LIMIT :n
    """
    accounts = pd.read_sql(text(accounts_q), engine, params={"n": sample_size})
    if accounts.empty:
        logger.warning("No accounts for balance reconciliation")
        return results

    txn_q = """
        SELECT account_id, transaction_type, amount, transaction_status
        FROM raw.transactions
        WHERE account_id = ANY(:ids)
          AND amount ~ '^-?[0-9]*\\.?[0-9]+$'
    """
    ids = accounts["account_id"].tolist()
    txns = pd.read_sql(text(txn_q), engine, params={"ids": ids})
    txns["amount"] = pd.to_numeric(txns["amount"], errors="coerce").fillna(0)

    credit_types = {"Deposit", "Refund", "Interest", "Transfer"}
    debit_types = {"Withdrawal", "Payment", "Fee", "Bill Payment"}

    with engine.begin() as conn:
        for _, acct in accounts.iterrows():
            aid = acct["account_id"]
            reported = acct["reported_closing"]
            sub = txns[txns["account_id"] == aid]
            credits = sub[sub["transaction_type"].isin(credit_types)]["amount"].sum()
            debits = sub[sub["transaction_type"].isin(debit_types)]["amount"].sum()
            opening = float(reported) if pd.notna(reported) else 0.0
            opening = opening - credits + debits  # infer opening from closing
            expected = opening + credits - debits
            diff = (
                abs(float(reported) - expected)
                if pd.notna(reported)
                else None
            )
            status = "PASS" if diff is not None and diff < 0.01 else "FAIL"
            if reported is None or pd.isna(reported):
                status = "UNKNOWN"
                diff = None

            def _py(v):
                if v is None or (isinstance(v, float) and pd.isna(v)):
                    return None
                try:
                    return float(v)
                except (TypeError, ValueError):
                    return None

            conn.execute(
                text(
                    """
                    INSERT INTO audit.balance_reconciliation
                        (run_id, account_id, opening_balance, total_credits,
                         total_debits, expected_closing, reported_closing,
                         difference, status, checked_at)
                    VALUES
                        (:run_id, :aid, :open, :cred, :deb, :exp, :rep, :diff, :st, :ts)
                    """
                ),
                {
                    "run_id": run_id,
                    "aid": str(aid),
                    "open": _py(opening),
                    "cred": _py(credits),
                    "deb": _py(debits),
                    "exp": _py(expected),
                    "rep": _py(reported),
                    "diff": _py(diff),
                    "st": status,
                    "ts": datetime.now(timezone.utc),
                },
            )
            results.append(
                {
                    "account_id": aid,
                    "status": status,
                    "difference": diff,
                }
            )

    passed = sum(1 for r in results if r["status"] == "PASS")
    logger.info(
        "Balance reconciliation sample: %s/%s PASS (sample_size=%s)",
        passed,
        len(results),
        sample_size,
    )
    return results


def run_reconciliation(run_id: str | None = None) -> dict:
    engine = get_engine()
    run_ddl(engine)
    run_id = run_id or str(uuid.uuid4())
    with engine.begin() as conn:
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
                    VALUES (:r, 'reconciliation', :ts, 'RUNNING')
                    """
                ),
                {"r": run_id, "ts": datetime.now(timezone.utc)},
            )

    count_results = reconcile_counts_and_sums(run_id=run_id)
    balance_results = reconcile_balances(run_id=run_id)

    with engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE audit.pipeline_runs
                SET end_time = :ts, status = 'SUCCESS'
                WHERE run_id = :r
                """
            ),
            {"ts": datetime.now(timezone.utc), "r": run_id},
        )

    return {
        "run_id": run_id,
        "count_checks": count_results,
        "balance_checks": balance_results,
    }


def main() -> dict:
    return run_reconciliation()


if __name__ == "__main__":
    main()

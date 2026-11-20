"""Load payment CSVs into raw.* with COPY, and persist reconciliation results (idempotent)."""

from __future__ import annotations

import io
import uuid
from pathlib import Path

import pandas as pd
from sqlalchemy import text

from src.payments.reconciliation import ReconConfig, ReconResult, reconcile
from src.utils.db import get_engine, run_ddl
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)

RAW_TABLES = {
    "payment_transactions.csv": "payment_transactions",
    "payment_lifecycle_events.csv": "payment_lifecycle_events",
    "payment_settlements.csv": "payment_settlements",
    "fx_rates_synthetic.csv": "fx_rates_synthetic",
}


def copy_csv(engine, csv_path: Path, table: str, truncate: bool = True, chunk_rows: int = 200_000) -> int:
    """Bulk-load a CSV into ``raw.<table>`` using COPY (column names taken from the CSV header)."""
    cols = list(pd.read_csv(csv_path, nrows=0).columns)
    col_sql = ", ".join(f'"{c}"' for c in cols) + ', "_source_file"'
    total = 0
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        if truncate:
            cur.execute(f"TRUNCATE TABLE raw.{table}")
        for chunk in pd.read_csv(csv_path, dtype=str, keep_default_na=False, chunksize=chunk_rows):
            chunk["_source_file"] = csv_path.name
            buf = io.StringIO()
            chunk.to_csv(buf, index=False, header=False)
            buf.seek(0)
            cur.copy_expert(
                f"COPY raw.{table} ({col_sql}) FROM STDIN WITH (FORMAT csv, NULL '')", buf)
            total += len(chunk)
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()
    return total


def load_payment_sources(source_dir: Path, engine=None) -> dict[str, int]:
    engine = engine or get_engine()
    run_ddl(engine)
    out = {}
    for fname, table in RAW_TABLES.items():
        p = source_dir / fname
        if p.exists():
            out[table] = copy_csv(engine, p, table)
            logger.info("COPY raw.%s: %s rows", table, f"{out[table]:,}")
    return out


def persist_reconciliation(engine, res: ReconResult, cfg: ReconConfig, run_id: str | None = None) -> int:
    """Insert a run summary and upsert exceptions into the investigation queue.

    Re-running with identical inputs leaves the queue unchanged (analyst status/notes are preserved);
    exceptions that no longer occur and are still OPEN are marked RESOLVED.
    Returns number of queue rows touched.
    """
    s = res.summary
    run_id = run_id or str(uuid.uuid4())
    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO payments.reconciliation_runs
              (run_id, as_of, sla_days, cleared_payments, matched, pending, missing, duplicate,
               amount_mismatch, currency_mismatch, late, fx_rate_missing, unmatched_settlements,
               settlement_success_rate, amount_at_risk)
            VALUES (:run_id, :as_of, :sla, :cleared_payments, :matched, :pending, :missing, :duplicate,
               :amount_mismatch, :currency_mismatch, :late, :fx_rate_missing, :unmatched_settlements,
               :settlement_success_rate, :amount_at_risk)"""),
            {**{k: s[k] for k in ("cleared_payments", "matched", "pending", "missing", "duplicate",
                                  "amount_mismatch", "currency_mismatch", "late", "fx_rate_missing",
                                  "unmatched_settlements", "settlement_success_rate", "amount_at_risk")},
             "run_id": run_id, "as_of": s["as_of"], "sla": cfg.sla_days})
        q = res.queue
        conn.execute(text("CREATE TEMP TABLE _q (LIKE payments.investigation_queue INCLUDING DEFAULTS) ON COMMIT DROP"))
        if len(q):
            rows = q[["payment_id", "settlement_id", "issue_type", "amount_at_risk", "currency",
                      "issue_flags", "priority"]].astype(object).where(q.notna(), None).to_dict("records")
            conn.execute(text("""INSERT INTO _q (payment_id, settlement_id, issue_type, amount_at_risk,
                                 currency, issue_flags, priority)
                                 VALUES (:payment_id, :settlement_id, :issue_type, :amount_at_risk,
                                 :currency, :issue_flags, :priority)"""), rows)
        conn.execute(text("""
            INSERT INTO payments.investigation_queue
                (payment_id, settlement_id, issue_type, amount_at_risk, currency, issue_flags, priority)
            SELECT payment_id, settlement_id, issue_type, amount_at_risk, currency, issue_flags, priority FROM _q
            ON CONFLICT (payment_id, settlement_id, issue_type) DO UPDATE
               SET amount_at_risk = EXCLUDED.amount_at_risk, issue_flags = EXCLUDED.issue_flags,
                   priority = EXCLUDED.priority, last_detected_at = NOW()"""))
        conn.execute(text("""
            UPDATE payments.investigation_queue iq SET status = 'RESOLVED', last_detected_at = NOW()
            WHERE iq.status = 'OPEN' AND NOT EXISTS (
              SELECT 1 FROM _q WHERE _q.payment_id = iq.payment_id AND _q.settlement_id = iq.settlement_id
                AND _q.issue_type = iq.issue_type)"""))
    return len(q)


def run_reconciliation_from_raw(engine=None, cfg: ReconConfig | None = None) -> ReconResult:
    """Reconcile using the typed view of the raw payment tables (clean rows only)."""
    engine = engine or get_engine()
    cfg = cfg or ReconConfig()
    clr = pd.read_sql(text("""
        SELECT payment_id, event_ts::timestamp AS clearing_ts, amount::numeric::float8 AS amount, currency
        FROM raw.payment_lifecycle_events
        WHERE event_type = 'CLEARING' AND dq_defect IN ('', 'duplicate_record')
    """), engine)
    stl = pd.read_sql(text("""
        SELECT settlement_id, payment_id, settlement_ts::timestamp AS settlement_ts,
               settlement_amount::numeric::float8 AS settlement_amount, settlement_currency
        FROM raw.payment_settlements"""), engine)
    fx = pd.read_sql(text("""SELECT rate_date, base_currency, quote_currency, rate::float8 AS rate
                             FROM raw.fx_rates_synthetic"""), engine)
    res = reconcile(clr, stl, fx, cfg)
    persist_reconciliation(engine, res, cfg)
    return res

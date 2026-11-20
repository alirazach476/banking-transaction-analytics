"""DB-backed tests (dedicated novabank_test database): COPY load + idempotent reconciliation."""

from __future__ import annotations

import pandas as pd
import pytest
from sqlalchemy import text

from src.payments.config import DefectRates, PaymentGenConfig, SettlementIssueRates
from src.payments.load import load_payment_sources, persist_reconciliation, run_reconciliation_from_raw
from src.payments.reconciliation import ReconConfig
from src.payments.writer import generate_to_disk


@pytest.fixture(scope="module")
def loaded(test_engine, tmp_path_factory):
    cfg = PaymentGenConfig(num_payments=5000, num_cards=600, num_merchants=100, chunk_size=2500,
                           start_date="2024-01-01", end_date="2024-03-31", defects=DefectRates.none(),
                           issues=SettlementIssueRates(missing=0.01, duplicate=0.01, amount_mismatch=0.01,
                                                       currency_mismatch=0.01, late=0.01, orphan=0.005))
    out, clean = tmp_path_factory.mktemp("dirty"), tmp_path_factory.mktemp("clean")
    manifest = generate_to_disk(cfg, out, clean)
    with test_engine.begin() as c:
        c.execute(text("TRUNCATE payments.investigation_queue, payments.reconciliation_runs"))
    counts = load_payment_sources(out, test_engine)
    return manifest, counts, clean


def test_copy_load_row_counts_match_manifest(loaded, test_engine):
    manifest, counts, _ = loaded
    rc = manifest["row_counts"]
    assert counts["payment_transactions"] == rc["dirty_transactions"]
    assert counts["payment_lifecycle_events"] == rc["dirty_events"]
    assert counts["payment_settlements"] == rc["settlements"]
    with test_engine.connect() as c:
        assert c.execute(text("SELECT count(*) FROM raw.payment_transactions")).scalar() == rc["dirty_transactions"]


def test_copy_load_is_idempotent(loaded, test_engine):
    manifest, _, _ = loaded
    # re-loading (truncate + copy) must not duplicate rows
    with test_engine.connect() as c:
        before = c.execute(text("SELECT count(*) FROM raw.payment_settlements")).scalar()
    from pathlib import Path
    load_payment_sources(Path(manifest["dirty_dir"]), test_engine)
    with test_engine.connect() as c:
        after = c.execute(text("SELECT count(*) FROM raw.payment_settlements")).scalar()
    assert before == after


def test_reconciliation_persisted_and_rerun_idempotent(loaded, test_engine):
    cfg = ReconConfig(as_of=pd.Timestamp("2025-01-01"))
    res = run_reconciliation_from_raw(test_engine, cfg)
    assert len(res.queue) > 0
    with test_engine.connect() as c:
        n1 = c.execute(text("SELECT count(*) FROM payments.investigation_queue WHERE status='OPEN'")).scalar()
    assert n1 == len(res.queue)
    # analyst edits survive a re-run; queue size is unchanged
    with test_engine.begin() as c:
        c.execute(text("""UPDATE payments.investigation_queue SET status='IN_REVIEW', notes='checked'
                          WHERE notes IS NULL"""))
    persist_reconciliation(test_engine, res, cfg)
    with test_engine.connect() as c:
        total = c.execute(text("SELECT count(*) FROM payments.investigation_queue")).scalar()
        in_review = c.execute(text("SELECT count(*) FROM payments.investigation_queue WHERE status='IN_REVIEW'")).scalar()
    assert total == len(res.queue)
    assert in_review == len(res.queue)


def test_resolved_when_issue_disappears(loaded, test_engine):
    from src.payments.reconciliation import ReconResult
    with test_engine.begin() as c:
        c.execute(text("UPDATE payments.investigation_queue SET status='OPEN'"))
    empty = ReconResult(detail=pd.DataFrame(), unmatched_settlements=pd.DataFrame(),
                        summary={"as_of": "2025-01-01", "cleared_payments": 0, "matched": 0, "pending": 0,
                                 "missing": 0, "duplicate": 0, "amount_mismatch": 0, "currency_mismatch": 0,
                                 "late": 0, "fx_rate_missing": 0, "unmatched_settlements": 0,
                                 "settlement_success_rate": None, "amount_at_risk": 0.0},
                        queue=pd.DataFrame(columns=["payment_id", "settlement_id", "issue_type", "amount_at_risk",
                                                    "currency", "issue_flags", "priority"]))
    persist_reconciliation(test_engine, empty, ReconConfig())
    with test_engine.connect() as c:
        open_n = c.execute(text("SELECT count(*) FROM payments.investigation_queue WHERE status='OPEN'")).scalar()
    assert open_n == 0

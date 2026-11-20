"""Tests for the payment-lifecycle generator, defects, reconciliation and KPIs."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from src.payments.config import DefectRates, PaymentGenConfig, SettlementIssueRates
from src.payments.defects import inject_defects
from src.payments.generator import PaymentGenerator
from src.payments.kpis import kpi_summary
from src.payments.reconciliation import ReconConfig, reconcile
from src.payments.writer import dirty_views


def _cfg(**kw) -> PaymentGenConfig:
    base = dict(num_payments=6000, num_cards=800, num_merchants=120, chunk_size=2500,
                start_date="2024-01-01", end_date="2024-06-30")
    base.update(kw)
    return PaymentGenConfig(**base)


def _collect(cfg: PaymentGenConfig):
    gen = PaymentGenerator(cfg)
    chunks = list(gen.iter_chunks())
    cat = lambda attr: pd.concat([getattr(c, attr) for c in chunks], ignore_index=True)
    return gen, cat("transactions"), cat("events"), cat("settlements"), cat("truth")


@pytest.fixture(scope="module")
def data():
    return _collect(_cfg())


def test_generation_is_deterministic():
    a = _collect(_cfg(num_payments=1500, chunk_size=1000))
    b = _collect(_cfg(num_payments=1500, chunk_size=1000))
    pd.testing.assert_frame_equal(a[1], b[1])
    pd.testing.assert_frame_equal(a[2], b[2])


def test_different_seed_changes_output():
    a = _collect(_cfg(num_payments=1500, seed=1))[1]
    b = _collect(_cfg(num_payments=1500, seed=2))[1]
    assert not a["amount"].equals(b["amount"])


def test_ids_unique_and_synthetic_flag(data):
    _, t, e, s, _ = data
    assert t["payment_id"].is_unique and e["event_id"].is_unique and s["settlement_id"].is_unique
    assert t["is_synthetic"].all() and e["is_synthetic"].all()


def test_lifecycle_ordering_and_references(data):
    _, t, e, _, _ = data
    assert set(e["payment_id"]) <= set(t["payment_id"]) | set()
    req = e[e.event_type == "AUTH_REQUEST"].set_index("payment_id")["event_ts"]
    clr = e[e.event_type == "CLEARING"].set_index("payment_id")["event_ts"]
    assert (clr > req.reindex(clr.index)).all()
    # every cleared payment was approved; declined payments never clear
    approved = e[(e.event_type == "AUTH_RESPONSE") & (e.event_status == "APPROVED")]["payment_id"]
    declined = e[(e.event_type == "AUTH_RESPONSE") & (e.event_status == "DECLINED")]["payment_id"]
    assert set(clr.index) <= set(approved)
    assert not set(clr.index) & set(declined)
    # declines carry a reason, approvals do not
    resp = e[e.event_type == "AUTH_RESPONSE"]
    assert (resp.loc[resp.event_status == "DECLINED", "reason_code"] != "").all()
    assert (resp.loc[resp.event_status == "APPROVED", "reason_code"] == "").all()


def test_international_declines_exceed_domestic(data):
    _, t, e, _, _ = data
    r = e[e.event_type == "AUTH_RESPONSE"].merge(t[["payment_id", "is_international"]], on="payment_id")
    rate = r.assign(d=r.event_status == "DECLINED").groupby("is_international")["d"].mean()
    assert rate[True] > rate[False]


def test_clean_frames_have_no_defect_labels_and_dirty_do(data):
    gen, t, e, s, _ = data
    cfg = _cfg(defects=DefectRates(duplicate_record=0.02, missing_value=0.02, invalid_foreign_key=0.02,
                                   inconsistent_capitalization=0.05, invalid_timestamp=0.02,
                                   invalid_currency=0.02, incorrect_status=0.02))
    ch = next(PaymentGenerator(cfg).iter_chunks())
    assert "dq_defect" not in ch.transactions.columns
    dt, de = dirty_views(ch, cfg, np.random.default_rng(1))
    labels = set(dt.loc[dt.dq_defect != "", "dq_defect"].str.split(";").explode())
    assert {"duplicate_record", "invalid_foreign_key", "invalid_timestamp", "invalid_currency"} <= labels
    assert len(dt) > len(ch.transactions)  # duplicates appended
    assert (dt.loc[dt.dq_defect.str.contains("invalid_foreign_key"), "merchant_id"] == "INVALID-REF").all()


def test_zero_defect_rates_leave_data_unchanged():
    cfg = _cfg(num_payments=800, defects=DefectRates.none())
    ch = next(PaymentGenerator(cfg).iter_chunks())
    dt, _ = dirty_views(ch, cfg, np.random.default_rng(1))
    assert (dt["dq_defect"] == "").all() and len(dt) == len(ch.transactions)


def test_inject_defects_empty_frame():
    out = inject_defects(pd.DataFrame({"a": []}), DefectRates(), np.random.default_rng(0))
    assert len(out) == 0 and "dq_defect" in out


# ------------------------------ reconciliation ------------------------------
def _recon_inputs(e: pd.DataFrame, s: pd.DataFrame):
    clr = e[e.event_type == "CLEARING"].rename(columns={"event_ts": "clearing_ts"})
    return clr[["payment_id", "clearing_ts", "amount", "currency"]], s


def test_reconciliation_recovers_injected_issues():
    cfg = _cfg(num_payments=40_000, num_cards=2000, num_merchants=300, chunk_size=20_000,
               issues=SettlementIssueRates(missing=0.01, duplicate=0.01, amount_mismatch=0.01,
                                           currency_mismatch=0.005, late=0.01, orphan=0.005))
    gen, t, e, s, truth = _collect(cfg)
    clr, stl = _recon_inputs(e, s)
    res = reconcile(clr, stl, gen.fx, ReconConfig(as_of=pd.Timestamp("2026-01-01")))
    found = res.queue.set_index("payment_id")["issue_type"]
    mapping = {"MISSING": "MISSING_SETTLEMENT", "DUPLICATE": "DUPLICATE_SETTLEMENT",
               "AMOUNT_MISMATCH": "AMOUNT_MISMATCH", "CURRENCY_MISMATCH": "CURRENCY_MISMATCH",
               "LATE": "LATE_SETTLEMENT", "ORPHAN": "UNMATCHED_SETTLEMENT"}
    for injected, detected in mapping.items():
        ids = set(truth.loc[truth.injected_issue == injected, "payment_id"])
        assert ids, injected
        hits = {p for p in ids if found.get(p) == detected}
        assert len(hits) / len(ids) >= 0.99, (injected, len(hits), len(ids))
    # precision: nothing flagged that was not injected
    flagged = set(res.queue["payment_id"])
    assert flagged <= set(truth["payment_id"])
    assert res.summary["unmatched_settlements"] == (truth.injected_issue == "ORPHAN").sum()


def test_reconciliation_clean_data_all_matched():
    cfg = _cfg(num_payments=3000, issues=SettlementIssueRates.none())
    gen, t, e, s, _ = _collect(cfg)
    clr, stl = _recon_inputs(e, s)
    res = reconcile(clr, stl, gen.fx, ReconConfig(as_of=pd.Timestamp("2026-01-01")))
    assert res.summary["matched"] == res.summary["cleared_payments"] > 0
    assert res.queue.empty and res.summary["settlement_success_rate"] == 1.0


FX = pd.DataFrame({"rate_date": ["2024-01-01", "2024-01-02"] * 2,
                   "base_currency": ["EUR"] * 2 + ["USD"] * 2, "quote_currency": "USD",
                   "rate": [1.10, 1.20, 1.0, 1.0]})


def _row(pid, ts="2024-01-02 10:00:00", amt=100.0, ccy="EUR"):
    return {"payment_id": pid, "clearing_ts": ts, "amount": amt, "currency": ccy}


def _stl(pid, amt, ccy="USD", ts="2024-01-03 10:00:00", sid=None):
    return {"settlement_id": sid or f"S-{pid}", "payment_id": pid, "settlement_ts": ts,
            "settlement_amount": amt, "settlement_currency": ccy}


def test_reconciliation_edge_cases():
    clr = pd.DataFrame([_row("A"), _row("B"), _row("C"), _row("D"), _row("E"), _row("F", ccy="XXX"),
                        _row("G", ts="2024-01-09 00:00:00")])
    stl = pd.DataFrame([
        _stl("A", 120.00),                                        # matched (100 EUR @1.20)
        _stl("B", 120.00, sid="S-B1"), _stl("B", 120.00, sid="S-B2"),  # duplicate
        _stl("C", 118.00),                                        # amount mismatch
        _stl("D", 120.00, ccy="EUR"),                             # currency mismatch
        _stl("E", 120.00, ts="2024-01-12 10:00:00"),              # late
        _stl("Z", 10.0),                                          # unmatched settlement
    ])
    res = reconcile(clr, stl, FX, ReconConfig(as_of=pd.Timestamp("2024-01-10")))
    st = res.detail.set_index("payment_id")["primary_status"].to_dict()
    assert st == {"A": "MATCHED", "B": "DUPLICATE_SETTLEMENT", "C": "AMOUNT_MISMATCH",
                  "D": "CURRENCY_MISMATCH", "E": "LATE_SETTLEMENT",
                  "F": "MISSING_SETTLEMENT",   # no FX rate AND no settlement; missing wins
                  "G": "PENDING"}               # inside SLA window -> not yet missing
    assert res.summary["unmatched_settlements"] == 1
    assert "Z" in set(res.queue["payment_id"])
    assert res.queue["amount_at_risk"].is_monotonic_decreasing


def test_reconciliation_fx_rate_missing_flagged():
    clr = pd.DataFrame([_row("F", ccy="XXX")])
    res = reconcile(clr, pd.DataFrame([_stl("F", 5.0)]), FX, ReconConfig(as_of=pd.Timestamp("2024-02-01")))
    assert res.detail.iloc[0]["primary_status"] == "FX_RATE_MISSING"


def test_reconciliation_empty_inputs():
    empty_c = pd.DataFrame(columns=["payment_id", "clearing_ts", "amount", "currency"])
    empty_s = pd.DataFrame(columns=["settlement_id", "payment_id", "settlement_ts",
                                    "settlement_amount", "settlement_currency"])
    res = reconcile(empty_c, empty_s, FX, ReconConfig(as_of=pd.Timestamp("2024-02-01")))
    assert res.summary["cleared_payments"] == 0 and res.queue.empty
    assert res.summary["settlement_success_rate"] is None


def test_reconciliation_is_idempotent(data):
    gen, _, e, s, _ = data
    clr, stl = _recon_inputs(e, s)
    cfg = ReconConfig(as_of=pd.Timestamp("2026-01-01"))
    a, b = reconcile(clr, stl, gen.fx, cfg), reconcile(clr, stl, gen.fx, cfg)
    assert a.summary == b.summary
    # duplicated clearing input rows do not change results
    c = reconcile(pd.concat([clr, clr]), stl, gen.fx, cfg)
    assert c.summary == a.summary


# ------------------------------------ KPIs ----------------------------------
def _ev(rows):
    df = pd.DataFrame(rows, columns=["payment_id", "event_type", "event_status", "response_ms"])
    df["event_id"] = [f"E{i}" for i in range(len(df))]
    df["event_ts"] = pd.Timestamp("2024-01-01")
    return df


def test_kpi_denominators_are_payment_level_and_dedupe_events():
    ev = _ev([
        ("P1", "AUTH_REQUEST", "REQUESTED", 0), ("P1", "AUTH_RESPONSE", "APPROVED", 100),
        ("P1", "CLEARING", "CLEARED", 0), ("P1", "SETTLEMENT", "SETTLED", 0),
        ("P2", "AUTH_REQUEST", "REQUESTED", 0), ("P2", "AUTH_RESPONSE", "DECLINED", 300),
        ("P3", "AUTH_REQUEST", "REQUESTED", 0), ("P3", "AUTH_RESPONSE", "APPROVED", 200),
        ("P3", "REVERSAL", "REVERSED", 0),
        ("P4", "AUTH_REQUEST", "REQUESTED", 0),  # no response yet: excluded from approval denominator
        ("P1", "REFUND", "REFUNDED", 0), ("P1", "CHARGEBACK", "CHARGEBACK", 0),
    ])
    ev = pd.concat([ev, ev.iloc[[1]]])  # duplicated event row must not double count
    k = kpi_summary(ev)
    assert k["payments"] == 4 and k["payments_with_response"] == 3
    assert k["approval_rate"] == pytest.approx(2 / 3) and k["decline_rate"] == pytest.approx(1 / 3)
    assert k["completion_rate"] == pytest.approx(1 / 2)   # cleared / approved
    assert k["settlement_rate"] == 1.0
    assert k["reversal_rate"] == pytest.approx(1 / 2)
    assert k["refund_rate"] == 1.0 and k["chargeback_rate"] == 1.0
    assert k["avg_processing_ms"] == pytest.approx(200.0)


def test_kpi_empty_events():
    ev = _ev([]).iloc[0:0]
    k = kpi_summary(ev)
    assert k["payments"] == 0 and k["approval_rate"] is None

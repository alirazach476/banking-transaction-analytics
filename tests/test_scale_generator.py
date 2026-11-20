import numpy as np
import pandas as pd
import pytest

from src.data_generation.scale import SIGN, main


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    out = tmp_path_factory.mktemp("scale")
    args = ["--customers", "1500", "--accounts", "2500", "--branches", "15", "--merchants", "200",
            "--transactions", "40000", "--anomaly-rate", "0.01", "--seed", "7", "--out", str(out)]
    m = main(args)
    return out, m


def test_ids_unique_and_foreign_keys(run):
    out, _ = run
    t = pd.read_csv(out / "transactions.csv", dtype=str, keep_default_na=False)
    a = pd.read_csv(out / "accounts.csv", dtype=str)
    c = pd.read_csv(out / "customers.csv", dtype=str)
    mer = pd.read_csv(out / "merchants.csv", dtype=str)
    br = pd.read_csv(out / "branches.csv", dtype=str)
    assert t.transaction_id.is_unique and a.account_id.is_unique and c.customer_id.is_unique
    assert t.account_id.isin(a.account_id).all() and t.customer_id.isin(c.customer_id).all()
    assert a.customer_id.isin(c.customer_id).all() and a.branch_id.isin(br.branch_id).all()
    assert t.loc[t.merchant_id != "", "merchant_id"].isin(mer.merchant_id).all()
    assert t.loc[t.branch_id != "", "branch_id"].isin(br.branch_id).all()


def test_globally_time_ordered(run):
    out, _ = run
    ts = pd.read_csv(out / "transactions.csv", usecols=["transaction_timestamp"]).transaction_timestamp
    assert ts.is_monotonic_increasing


def test_row_count_includes_bursts(run):
    _, m = run
    assert m["rows"] == 40000 + m["burst_rows"] and m["burst_rows"] % 8 == 0


def test_anomaly_rate_close_to_target(run):
    out, _ = run
    t = pd.read_csv(out / "transactions.csv", usecols=["is_injected_anomaly", "reference_type"], dtype=str)
    flagged = ((t.is_injected_anomaly == "true") & (t.reference_type == "standard")).mean()
    assert 0.008 < flagged < 0.012


def test_balances_consistent_with_ledger(run):
    """Independent recomputation: closing = opening + signed completed movements; no negative running balance."""
    out, m = run
    t = pd.read_csv(out / "transactions.csv")
    a = pd.read_csv(out / "accounts.csv").set_index("account_id")
    led = pd.read_csv(out / "transactions_ledger.csv")
    signed = t.transaction_type.map(SIGN) * (t.transaction_status == "Completed") * t.amount
    net = signed.groupby(t.account_id).sum().reindex(a.index).fillna(0)
    assert np.allclose(a.opening_balance + net, a.current_balance, atol=0.02)
    assert (led.balance_after >= -0.01).all()
    assert m["ledger"]["negative_balance_rows"] == 0 and m["ledger"]["max_abs_closing_mismatch"] < 0.01
    last = led.groupby("account_id").balance_after.last()
    assert np.allclose(last.reindex(a.index).dropna(), a.current_balance.reindex(last.index), atol=0.02)
    assert (a.opening_balance >= 0).all()


def test_customer_activity_and_lifecycle(run):
    out, _ = run
    t = pd.read_csv(out / "transactions.csv")
    mo = pd.read_csv(out / "customer_activity_monthly.csv")
    life = pd.read_csv(out / "customer_lifecycle.csv")
    assert mo.txn_count.sum() == len(t)
    assert set(life.activity_state) <= {"active", "dormant", "never_active"}
    assert (life[life.activity_state == "never_active"].first_txn.isna()).all()


def test_extensions_cover_reference_tables(run):
    out, _ = run
    be = pd.read_csv(out / "branch_extensions.csv"); br = pd.read_csv(out / "branches.csv")
    me = pd.read_csv(out / "merchant_extensions.csv"); mer = pd.read_csv(out / "merchants.csv")
    assert set(be.branch_id) == set(br.branch_id) and set(me.merchant_id) == set(mer.merchant_id)
    assert be.latitude.between(20, 55).all() and me.risk_tier.isin(["Low", "Medium", "High"]).all()


def test_reproducible_with_same_seed(tmp_path):
    args = ["--customers", "300", "--accounts", "400", "--branches", "5", "--merchants", "50", "--transactions", "3000", "--seed", "3"]
    main(args + ["--out", str(tmp_path / "a")]); main(args + ["--out", str(tmp_path / "b")])
    for f in ("transactions.csv", "accounts.csv", "transactions_ledger.csv"):
        assert (tmp_path / "a" / f).read_bytes() == (tmp_path / "b" / f).read_bytes()

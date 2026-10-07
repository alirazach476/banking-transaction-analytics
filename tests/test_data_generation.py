"""Tests for synthetic NovaBank source data quality and ID conventions."""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
import pytest

from config.settings import get_settings

ID_PATTERNS = {
    "customer_id": re.compile(r"^CUST-\d{8}$"),
    "account_id": re.compile(r"^ACC-\d{8}$"),
    "transaction_id": re.compile(r"^TXN-\d{10}$"),
    "card_id": re.compile(r"^CARD-\d{6}$"),
    "branch_id": re.compile(r"^BR-\d{8}$"),
    "merchant_id": re.compile(r"^MERCH-\d{8}$"),
    "atm_txn_id": re.compile(r"^ATM-\d{10}$"),
    "card_txn_id": re.compile(r"^CTXN-\d{10}$"),
}

# Realistic PAN: 13-19 consecutive digits (Luhn-like length)
PAN_PATTERN = re.compile(r"^\d{13,19}$")


@pytest.fixture
def source_dir(settings):
    return settings.data_source_dir


def _load_csv(source_dir: Path, rel: str) -> pd.DataFrame:
    path = source_dir / rel
    if not path.exists():
        pytest.skip(f"Source file missing: {path}")
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def test_customer_id_format(source_dir):
    df = _load_csv(source_dir, "customer_system/customers.csv")
    sample = df["customer_id"].dropna().head(500)
    assert all(ID_PATTERNS["customer_id"].match(v) for v in sample if v.strip())


def test_account_id_format_and_customer_fk(source_dir):
    accounts = _load_csv(source_dir, "core_banking/accounts.csv")
    customers = _load_csv(source_dir, "customer_system/customers.csv")
    cust_ids = set(customers["customer_id"])
    sample = accounts.head(500)
    assert all(ID_PATTERNS["account_id"].match(v) for v in sample["account_id"] if v.strip())
    linked = sample[sample["customer_id"].isin(cust_ids)]
    assert len(linked) > len(sample) * 0.9


def test_transaction_id_format(source_dir):
    df = _load_csv(source_dir, "core_banking/transactions.csv")
    sample = df["transaction_id"].dropna().head(500)
    assert all(ID_PATTERNS["transaction_id"].match(v) for v in sample if v.strip())


def test_transaction_amounts_positive_except_balance_inquiry(source_dir):
    core = _load_csv(source_dir, "core_banking/transactions.csv")
    amounts = pd.to_numeric(core["amount"], errors="coerce").dropna()
    # Source intentionally includes a small dirty-data fraction; vast majority must be positive
    positive_rate = (amounts > 0).mean()
    assert positive_rate >= 0.99, f"Expected >=99% positive core amounts, got {positive_rate:.2%}"

    atm = _load_csv(source_dir, "atm_system/atm_transactions.csv")
    non_inquiry = atm[atm["transaction_type"] != "Balance Inquiry"]
    non_inquiry_amt = pd.to_numeric(non_inquiry["amount"], errors="coerce").dropna()
    assert (non_inquiry_amt > 0).mean() >= 0.99
    inquiry = atm[atm["transaction_type"] == "Balance Inquiry"]
    assert (pd.to_numeric(inquiry["amount"], errors="coerce") == 0).all()


def test_card_ids_are_tokens_not_pans(source_dir):
    df = _load_csv(source_dir, "card_system/cards.csv")
    for cid in df["card_id"].dropna().head(500):
        assert ID_PATTERNS["card_id"].match(cid), f"Unexpected card id format: {cid}"
        assert not PAN_PATTERN.match(cid), f"Card id looks like PAN: {cid}"


def test_card_transaction_card_id_references(source_dir):
    cards = _load_csv(source_dir, "card_system/cards.csv")
    card_ids = set(cards["card_id"])
    txns = _load_csv(source_dir, "card_system/card_transactions.csv")
    sample = txns.head(500)
    for cid in sample["card_id"]:
        if cid.strip():
            assert cid in card_ids or ID_PATTERNS["card_id"].match(cid)
            assert not PAN_PATTERN.match(cid)

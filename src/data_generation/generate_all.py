"""
NovaBank synthetic banking data generator.

This project uses synthetic banking data generated solely for demonstrating
data engineering, analytics, and transaction-monitoring capabilities.
It does not represent real customer or banking data.

Card identifiers use safe tokens (CARD-000001), never realistic PANs.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from faker import Faker
from tqdm import tqdm

from config.settings import get_settings
from src.data_generation.constants import (
    ACCOUNT_STATUS_WEIGHTS,
    ACCOUNT_STATUSES,
    ACCOUNT_TYPE_WEIGHTS,
    ACCOUNT_TYPES,
    ANOMALY_TYPES,
    AMOUNT_PARAMS,
    BEHAVIOR_PROFILES,
    BRANCH_STATUS_WEIGHTS,
    BRANCH_STATUSES,
    BRANCH_TYPE_WEIGHTS,
    BRANCH_TYPES,
    CARD_STATUS_WEIGHTS,
    CARD_STATUSES,
    CARD_TYPE_WEIGHTS,
    CARD_TYPES,
    CHANNEL_WEIGHTS,
    CHANNELS,
    COUNTRY,
    CURRENCIES,
    CURRENCY_WEIGHTS,
    CUSTOMER_STATUS_WEIGHTS,
    CUSTOMER_STATUSES,
    CUSTOMER_TYPE_WEIGHTS,
    CUSTOMER_TYPES,
    FICTIONAL_COUNTRIES,
    GENDER_WEIGHTS,
    GENDERS,
    MERCHANT_CATEGORIES,
    MERCHANT_CATEGORY_WEIGHTS,
    REGIONS,
    STATUS_VARIANTS,
    TRANSACTION_STATUS_WEIGHTS,
    TRANSACTION_STATUSES,
    TRANSACTION_TYPE_WEIGHTS,
    TRANSACTION_TYPES,
    TRANSFER_TYPE_WEIGHTS,
    TRANSFER_TYPES,
)
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


def _choice(rng: np.random.Generator, options: list, weights: list, size: int):
    probs = np.array(weights, dtype=float)
    probs = probs / probs.sum()
    idx = rng.choice(len(options), size=size, p=probs)
    return np.array(options)[idx]


def _pad_id(prefix: str, n: int, width: int = 8) -> np.ndarray:
    return np.array([f"{prefix}-{i:0{width}d}" for i in range(1, n + 1)])


def _sample_amounts(
    rng: np.random.Generator, txn_types: np.ndarray, customer_types: np.ndarray
) -> np.ndarray:
    amounts = np.empty(len(txn_types), dtype=float)
    for t in TRANSACTION_TYPES:
        mask = txn_types == t
        if not mask.any():
            continue
        params = AMOUNT_PARAMS[t]
        n = int(mask.sum())
        raw = rng.lognormal(params["mean"], params["sigma"], size=n)
        raw = np.clip(raw, params["min"], params["max"])
        # Apply customer behavior multiplier
        ctypes = customer_types[mask]
        mults = np.array([BEHAVIOR_PROFILES.get(ct, {"amount_mult": 1.0})["amount_mult"] for ct in ctypes])
        amounts[mask] = np.round(raw * mults, 2)
    return amounts


def _random_timestamps(
    rng: np.random.Generator,
    n: int,
    start: datetime,
    end: datetime,
    prefer_business_hours: bool = True,
) -> np.ndarray:
    """Generate timestamps with weekday/daytime bias."""
    span = (end - start).total_seconds()
    # Over-generate then filter for realism
    candidates = []
    target = n
    while len(candidates) < target:
        batch = min(target * 2, max(target - len(candidates), 1) * 3)
        offsets = rng.uniform(0, span, size=batch)
        times = [start + timedelta(seconds=float(o)) for o in offsets]
        for t in times:
            # Weekend: keep ~60% of weekday rate
            if t.weekday() >= 5 and rng.random() > 0.6:
                continue
            hour = t.hour
            if prefer_business_hours:
                # Night (0-5): keep ~15%
                if hour < 6 and rng.random() > 0.15:
                    continue
                # Peak hours 9-18 more likely — already partially filtered
            candidates.append(t)
            if len(candidates) >= target:
                break
    return np.array(sorted(candidates[:n]))


def generate_branches(rng: np.random.Generator, n: int, fake: Faker) -> pd.DataFrame:
    region_names = list(REGIONS.keys())
    regions = rng.choice(region_names, size=n)
    cities = [rng.choice(REGIONS[r]) for r in regions]
    start = datetime(1990, 1, 1)
    opening = [
        start + timedelta(days=int(x))
        for x in rng.integers(0, (datetime(2022, 1, 1) - start).days, size=n)
    ]
    return pd.DataFrame(
        {
            "branch_id": _pad_id("BR", n),
            "branch_name": [f"NovaBank {c} #{i+1}" for i, c in enumerate(cities)],
            "city": cities,
            "region": regions,
            "country": COUNTRY,
            "branch_type": _choice(rng, BRANCH_TYPES, BRANCH_TYPE_WEIGHTS, n),
            "opening_date": [d.strftime("%Y-%m-%d") for d in opening],
            "branch_status": _choice(rng, BRANCH_STATUSES, BRANCH_STATUS_WEIGHTS, n),
        }
    )


def generate_customers(
    rng: np.random.Generator, n: int, fake: Faker, start_date: str, end_date: str
) -> pd.DataFrame:
    region_names = list(REGIONS.keys())
    regions = rng.choice(region_names, size=n)
    cities = [rng.choice(REGIONS[r]) for r in regions]
    ctypes = _choice(rng, CUSTOMER_TYPES, CUSTOMER_TYPE_WEIGHTS, n)
    statuses = _choice(rng, CUSTOMER_STATUSES, CUSTOMER_STATUS_WEIGHTS, n)
    genders = _choice(rng, GENDERS, GENDER_WEIGHTS, n)

    dobs = []
    regs = []
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    # Registration spread across history
    reg_span = (end - start).days
    for i in range(n):
        age = int(rng.integers(18, 80))
        dob = datetime(2024, 1, 1) - timedelta(days=age * 365 + int(rng.integers(0, 365)))
        dobs.append(dob.strftime("%Y-%m-%d"))
        reg = start + timedelta(days=int(rng.integers(0, max(reg_span, 1))))
        regs.append(reg.strftime("%Y-%m-%d"))

    # Names via Faker (batch for speed)
    first_names = [fake.first_name() for _ in range(n)]
    last_names = [fake.last_name() for _ in range(n)]

    return pd.DataFrame(
        {
            "customer_id": _pad_id("CUST", n),
            "first_name": first_names,
            "last_name": last_names,
            "date_of_birth": dobs,
            "gender": genders,
            "customer_type": ctypes,
            "registration_date": regs,
            "customer_status": statuses,
            "city": cities,
            "region": regions,
            "country": COUNTRY,
        }
    )


def generate_accounts(
    rng: np.random.Generator,
    n: int,
    customers: pd.DataFrame,
    branches: pd.DataFrame,
) -> pd.DataFrame:
    cust_ids = customers["customer_id"].values
    # Prefer active customers; allow 1–3 accounts
    cust_sample = rng.choice(cust_ids, size=n, replace=True)
    branch_ids = branches["branch_id"].values
    branch_sample = rng.choice(branch_ids, size=n)

    # Lookup customer type for balance distribution
    ctype_map = dict(zip(customers["customer_id"], customers["customer_type"]))
    ctypes = np.array([ctype_map[c] for c in cust_sample])

    balances = np.empty(n)
    for ct, profile in BEHAVIOR_PROFILES.items():
        mask = ctypes == ct
        if not mask.any():
            continue
        # Log-normal balances scaled by profile
        base = rng.lognormal(mean=8.0, sigma=1.2, size=int(mask.sum()))
        balances[mask] = np.round(np.clip(base * profile["amount_mult"], 0, 5_000_000), 2)

    atypes = _choice(rng, ACCOUNT_TYPES, ACCOUNT_TYPE_WEIGHTS, n)
    statuses = _choice(rng, ACCOUNT_STATUSES, ACCOUNT_STATUS_WEIGHTS, n)
    currencies = _choice(rng, CURRENCIES, CURRENCY_WEIGHTS, n)

    open_days = rng.integers(0, 1500, size=n)
    open_dates = [
        (datetime(2020, 1, 1) + timedelta(days=int(d))).strftime("%Y-%m-%d")
        for d in open_days
    ]
    close_dates = []
    for i, st in enumerate(statuses):
        if st == "Closed":
            od = datetime.strptime(open_dates[i], "%Y-%m-%d")
            close_dates.append((od + timedelta(days=int(rng.integers(30, 800)))).strftime("%Y-%m-%d"))
        else:
            close_dates.append("")

    return pd.DataFrame(
        {
            "account_id": _pad_id("ACC", n),
            "customer_id": cust_sample,
            "account_type": atypes,
            "branch_id": branch_sample,
            "open_date": open_dates,
            "close_date": close_dates,
            "currency": currencies,
            "current_balance": balances,
            "account_status": statuses,
        }
    )


def generate_merchants(rng: np.random.Generator, n: int, fake: Faker) -> pd.DataFrame:
    region_names = list(REGIONS.keys())
    regions = rng.choice(region_names, size=n)
    cities = [rng.choice(REGIONS[r]) for r in regions]
    cats = _choice(rng, MERCHANT_CATEGORIES, MERCHANT_CATEGORY_WEIGHTS, n)
    names = [f"{fake.company()} {c}"[:60] for c in cats]
    statuses = rng.choice(["Active", "Inactive"], size=n, p=[0.9, 0.1])
    return pd.DataFrame(
        {
            "merchant_id": _pad_id("MERCH", n),
            "merchant_name": names,
            "merchant_category": cats,
            "city": cities,
            "region": regions,
            "merchant_status": statuses,
        }
    )


def generate_cards(
    rng: np.random.Generator, n: int, accounts: pd.DataFrame
) -> pd.DataFrame:
    # Sample accounts (with replacement if n > accounts)
    idx = rng.choice(len(accounts), size=n, replace=True)
    acc = accounts.iloc[idx]
    issue = [
        datetime(2019, 1, 1) + timedelta(days=int(d))
        for d in rng.integers(0, 2000, size=n)
    ]
    expiry = [(d + timedelta(days=365 * 4)).strftime("%Y-%m-%d") for d in issue]
    return pd.DataFrame(
        {
            "card_id": _pad_id("CARD", n, width=6),
            "customer_id": acc["customer_id"].values,
            "account_id": acc["account_id"].values,
            "card_type": _choice(rng, CARD_TYPES, CARD_TYPE_WEIGHTS, n),
            "issue_date": [d.strftime("%Y-%m-%d") for d in issue],
            "expiry_date": expiry,
            "card_status": _choice(rng, CARD_STATUSES, CARD_STATUS_WEIGHTS, n),
        }
    )


def generate_transactions(
    rng: np.random.Generator,
    n: int,
    customers: pd.DataFrame,
    accounts: pd.DataFrame,
    branches: pd.DataFrame,
    merchants: pd.DataFrame,
    start_date: str,
    end_date: str,
    anomaly_rate: float,
) -> pd.DataFrame:
    # Weight accounts by customer type frequency multiplier
    ctype_map = dict(zip(customers["customer_id"], customers["customer_type"]))
    freq_weights = np.array(
        [
            BEHAVIOR_PROFILES.get(ctype_map.get(c, "Retail"), {"freq_mult": 1.0})["freq_mult"]
            for c in accounts["customer_id"]
        ]
    )
    freq_weights = freq_weights / freq_weights.sum()
    acc_idx = rng.choice(len(accounts), size=n, p=freq_weights)
    acc = accounts.iloc[acc_idx]

    txn_types = _choice(rng, TRANSACTION_TYPES, TRANSACTION_TYPE_WEIGHTS, n)
    statuses = _choice(rng, TRANSACTION_STATUSES, TRANSACTION_STATUS_WEIGHTS, n)
    channels = _choice(rng, CHANNELS, CHANNEL_WEIGHTS, n)
    currencies = acc["currency"].values
    customer_types = np.array([ctype_map[c] for c in acc["customer_id"].values])
    amounts = _sample_amounts(rng, txn_types, customer_types)

    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    timestamps = _random_timestamps(rng, n, start, end)

    # Merchant / branch assignment by channel
    merchant_ids = np.array([""] * n, dtype=object)
    branch_ids = np.array([""] * n, dtype=object)
    merch_pool = merchants["merchant_id"].values
    branch_pool = branches["branch_id"].values
    for i, ch in enumerate(channels):
        if ch in ("POS", "Online", "Mobile App") and txn_types[i] in (
            "Payment",
            "Refund",
            "Bill Payment",
        ):
            merchant_ids[i] = rng.choice(merch_pool)
        if ch in ("Branch", "ATM"):
            branch_ids[i] = rng.choice(branch_pool)
        elif rng.random() < 0.3:
            branch_ids[i] = acc["branch_id"].values[i]

    # Inject controlled anomalies
    is_anomaly = np.zeros(n, dtype=bool)
    anomaly_type = np.array([""] * n, dtype=object)
    n_anom = int(n * anomaly_rate)
    anom_idx = rng.choice(n, size=n_anom, replace=False)
    cust_region = dict(zip(customers["customer_id"], customers["region"]))

    for i in anom_idx:
        atype = rng.choice(ANOMALY_TYPES)
        is_anomaly[i] = True
        anomaly_type[i] = atype
        if atype == "high_amount":
            amounts[i] = round(float(amounts[i]) * float(rng.uniform(15, 40)), 2)
        elif atype == "night_activity":
            t = timestamps[i]
            timestamps[i] = t.replace(hour=int(rng.integers(1, 5)), minute=int(rng.integers(0, 60)))
            amounts[i] = max(amounts[i], 1500.0)
        elif atype == "unusual_location":
            # Point to a distant branch region
            branch_ids[i] = rng.choice(branch_pool)
            channels[i] = "Branch"
        elif atype == "sudden_behavior_change":
            amounts[i] = round(float(amounts[i]) * float(rng.uniform(12, 25)), 2)
        elif atype == "multiple_failures":
            statuses[i] = "Failed"
        elif atype in ("high_frequency", "rapid_transactions"):
            # Marked for post-processing burst injection
            pass

    # Inject rapid/high-frequency bursts for a subset of anomaly customers
    rapid_customers = [
        acc["customer_id"].values[i]
        for i in anom_idx
        if anomaly_type[i] in ("rapid_transactions", "high_frequency")
    ][: max(1, n_anom // 10)]

    extra_rows = []
    txn_counter = n
    for cust in rapid_customers:
        cust_accs = accounts[accounts["customer_id"] == cust]
        if cust_accs.empty:
            continue
        a = cust_accs.iloc[0]
        base_time = start + timedelta(days=int(rng.integers(30, max((end - start).days - 30, 31))))
        burst = 8 if anomaly_type[anom_idx[0]] else 8
        for j in range(burst):
            txn_counter += 1
            extra_rows.append(
                {
                    "transaction_id": f"TXN-{txn_counter:010d}",
                    "account_id": a["account_id"],
                    "customer_id": cust,
                    "transaction_timestamp": (
                        base_time + timedelta(minutes=j * 2)
                    ).strftime("%Y-%m-%d %H:%M:%S"),
                    "transaction_type": "Payment",
                    "amount": round(float(rng.uniform(50, 400)), 2),
                    "currency": a["currency"],
                    "channel": "Mobile App",
                    "merchant_id": rng.choice(merch_pool),
                    "branch_id": "",
                    "transaction_status": "Completed",
                    "reference_type": "anomaly_burst",
                    "is_injected_anomaly": "true",
                    "anomaly_type": "rapid_transactions",
                    "updated_at": (base_time + timedelta(minutes=j * 2)).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    ),
                }
            )

    df = pd.DataFrame(
        {
            "transaction_id": _pad_id("TXN", n, width=10),
            "account_id": acc["account_id"].values,
            "customer_id": acc["customer_id"].values,
            "transaction_timestamp": [t.strftime("%Y-%m-%d %H:%M:%S") for t in timestamps],
            "transaction_type": txn_types,
            "amount": amounts,
            "currency": currencies,
            "channel": channels,
            "merchant_id": merchant_ids,
            "branch_id": branch_ids,
            "transaction_status": statuses,
            "reference_type": "standard",
            "is_injected_anomaly": np.where(is_anomaly, "true", "false"),
            "anomaly_type": anomaly_type,
            "updated_at": [t.strftime("%Y-%m-%d %H:%M:%S") for t in timestamps],
        }
    )
    if extra_rows:
        df = pd.concat([df, pd.DataFrame(extra_rows)], ignore_index=True)
    return df


def generate_transfers(
    rng: np.random.Generator,
    n: int,
    accounts: pd.DataFrame,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    src_idx = rng.choice(len(accounts), size=n)
    dst_idx = rng.choice(len(accounts), size=n)
    # Avoid same account
    same = src_idx == dst_idx
    dst_idx[same] = (dst_idx[same] + 1) % len(accounts)

    src = accounts.iloc[src_idx]
    dst = accounts.iloc[dst_idx]
    ttypes = _choice(rng, TRANSFER_TYPES, TRANSFER_TYPE_WEIGHTS, n)
    statuses = _choice(rng, TRANSACTION_STATUSES, TRANSACTION_STATUS_WEIGHTS, n)
    amounts = np.round(rng.lognormal(6.0, 1.3, size=n).clip(10, 250000), 2)
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    timestamps = _random_timestamps(rng, n, start, end)
    dest_countries = [
        COUNTRY if t != "International" else rng.choice(FICTIONAL_COUNTRIES) for t in ttypes
    ]
    return pd.DataFrame(
        {
            "transfer_id": _pad_id("XFER", n, width=10),
            "source_account_id": src["account_id"].values,
            "destination_account_id": dst["account_id"].values,
            "customer_id": src["customer_id"].values,
            "transfer_timestamp": [t.strftime("%Y-%m-%d %H:%M:%S") for t in timestamps],
            "amount": amounts,
            "currency": src["currency"].values,
            "transfer_type": ttypes,
            "status": statuses,
            "destination_country": dest_countries,
            "updated_at": [t.strftime("%Y-%m-%d %H:%M:%S") for t in timestamps],
        }
    )


def generate_atm_transactions(
    rng: np.random.Generator,
    n: int,
    cards: pd.DataFrame,
    branches: pd.DataFrame,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    idx = rng.choice(len(cards), size=n)
    c = cards.iloc[idx]
    branch_ids = rng.choice(branches["branch_id"].values, size=n)
    atm_ids = [f"ATM-{b[-4:]}-{i%50:02d}" for i, b in enumerate(branch_ids)]
    amounts = np.round(rng.lognormal(4.2, 0.7, size=n).clip(20, 1000), 2)
    ttypes = rng.choice(["Withdrawal", "Deposit", "Balance Inquiry"], size=n, p=[0.75, 0.15, 0.10])
    # Balance inquiry amount = 0 — mark separately; financial validation allows this type
    amounts = np.where(ttypes == "Balance Inquiry", 0.0, amounts)
    statuses = _choice(rng, TRANSACTION_STATUSES, TRANSACTION_STATUS_WEIGHTS, n)
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    timestamps = _random_timestamps(rng, n, start, end)
    return pd.DataFrame(
        {
            "atm_txn_id": _pad_id("ATM", n, width=10),
            "card_id": c["card_id"].values,
            "atm_id": atm_ids,
            "branch_id": branch_ids,
            "customer_id": c["customer_id"].values,
            "account_id": c["account_id"].values,
            "timestamp": [t.strftime("%Y-%m-%d %H:%M:%S") for t in timestamps],
            "amount": amounts,
            "transaction_type": ttypes,
            "status": statuses,
            "updated_at": [t.strftime("%Y-%m-%d %H:%M:%S") for t in timestamps],
        }
    )


def generate_card_transactions(
    rng: np.random.Generator,
    n: int,
    cards: pd.DataFrame,
    merchants: pd.DataFrame,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    idx = rng.choice(len(cards), size=n)
    c = cards.iloc[idx]
    merch = rng.choice(merchants["merchant_id"].values, size=n)
    amounts = np.round(rng.lognormal(3.7, 0.9, size=n).clip(5, 5000), 2)
    statuses = _choice(rng, TRANSACTION_STATUSES, TRANSACTION_STATUS_WEIGHTS, n)
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    timestamps = _random_timestamps(rng, n, start, end)
    return pd.DataFrame(
        {
            "card_txn_id": _pad_id("CTXN", n, width=10),
            "card_id": c["card_id"].values,
            "merchant_id": merch,
            "customer_id": c["customer_id"].values,
            "account_id": c["account_id"].values,
            "timestamp": [t.strftime("%Y-%m-%d %H:%M:%S") for t in timestamps],
            "amount": amounts,
            "status": statuses,
            "currency": "USD",
            "updated_at": [t.strftime("%Y-%m-%d %H:%M:%S") for t in timestamps],
        }
    )


def inject_data_quality_issues(
    rng: np.random.Generator,
    df: pd.DataFrame,
    status_col: str | None,
    id_col: str,
    duplicate_rate: float,
    missing_rate: float,
    invalid_status_rate: float,
) -> pd.DataFrame:
    """Introduce a small percentage of realistic source-data problems."""
    out = df.copy()
    n = len(out)
    if n == 0:
        return out

    # Inconsistent capitalization / status variants
    if status_col and status_col in out.columns and invalid_status_rate > 0:
        n_bad = int(n * invalid_status_rate)
        idxs = rng.choice(n, size=min(n_bad, n), replace=False)
        for i in idxs:
            val = str(out.at[i, status_col])
            # Normalize key then pick variant
            key = val.strip().title()
            # Map common title-case
            for canon, variants in STATUS_VARIANTS.items():
                if key.lower() == canon.lower() or val in variants:
                    out.at[i, status_col] = rng.choice(variants)
                    break

    # Missing values on non-critical columns (keep most IDs intact)
    nullable_cols = [
        c
        for c in out.columns
        if c not in (id_col,) and c not in ("customer_id", "account_id", "transaction_id")
    ]
    if nullable_cols and missing_rate > 0:
        n_miss = int(n * missing_rate)
        for _ in range(n_miss):
            i = int(rng.integers(0, n))
            col = rng.choice(nullable_cols)
            out.at[i, col] = None

    # Duplicate records
    if duplicate_rate > 0:
        n_dup = max(1, int(n * duplicate_rate))
        dup_idx = rng.choice(n, size=min(n_dup, n), replace=False)
        dups = out.iloc[dup_idx].copy()
        out = pd.concat([out, dups], ignore_index=True)

    # Occasional wrong timestamp format
    ts_cols = [c for c in out.columns if "timestamp" in c.lower() or c == "timestamp"]
    for col in ts_cols:
        n_fmt = max(1, int(n * 0.002))
        idxs = rng.choice(len(out), size=min(n_fmt, len(out)), replace=False)
        for i in idxs:
            val = out.at[i, col]
            if val and isinstance(val, str) and " " in val:
                # ISO-ish alternate format
                out.at[i, col] = val.replace(" ", "T")

    return out


def _write_source(df: pd.DataFrame, system: str, filename: str, root: Path) -> Path:
    out_dir = root / system
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    df.to_csv(path, index=False)
    logger.info("Wrote %s (%s rows)", path, f"{len(df):,}")
    return path


def main() -> None:
    settings = get_settings()
    rng = np.random.default_rng(settings.random_seed)
    fake = Faker()
    Faker.seed(settings.random_seed)

    v = settings.volumes
    logger.info("=" * 60)
    logger.info("NovaBank Synthetic Data Generator")
    logger.info("SYNTHETIC DATA ONLY — not real banking records")
    logger.info("=" * 60)
    logger.info(
        "Volumes: customers=%s accounts=%s txns=%s branches=%s merchants=%s",
        v.num_customers,
        v.num_accounts,
        v.num_transactions,
        v.num_branches,
        v.num_merchants,
    )

    logger.info("Generating branches...")
    branches = generate_branches(rng, v.num_branches, fake)

    logger.info("Generating customers...")
    customers = generate_customers(
        rng, v.num_customers, fake, settings.data_start_date, settings.data_end_date
    )

    logger.info("Generating accounts...")
    accounts = generate_accounts(rng, v.num_accounts, customers, branches)

    logger.info("Generating merchants...")
    merchants = generate_merchants(rng, v.num_merchants, fake)

    logger.info("Generating cards...")
    cards = generate_cards(rng, v.num_cards, accounts)

    logger.info("Generating transactions...")
    transactions = generate_transactions(
        rng,
        v.num_transactions,
        customers,
        accounts,
        branches,
        merchants,
        settings.data_start_date,
        settings.data_end_date,
        settings.anomaly.injection_rate,
    )

    logger.info("Generating transfers...")
    transfers = generate_transfers(
        rng, v.num_transfers, accounts, settings.data_start_date, settings.data_end_date
    )

    logger.info("Generating ATM transactions...")
    atm_txns = generate_atm_transactions(
        rng,
        v.num_atm_transactions,
        cards,
        branches,
        settings.data_start_date,
        settings.data_end_date,
    )

    logger.info("Generating card transactions...")
    card_txns = generate_card_transactions(
        rng,
        v.num_card_transactions,
        cards,
        merchants,
        settings.data_start_date,
        settings.data_end_date,
    )

    # Inject DQ issues per source-system export
    dq = settings.dq
    customers_dirty = inject_data_quality_issues(
        rng, customers, "customer_status", "customer_id",
        dq.duplicate_rate, dq.missing_rate, dq.invalid_status_rate,
    )
    accounts_dirty = inject_data_quality_issues(
        rng, accounts, "account_status", "account_id",
        dq.duplicate_rate, dq.missing_rate, dq.invalid_status_rate,
    )
    transactions_dirty = inject_data_quality_issues(
        rng, transactions, "transaction_status", "transaction_id",
        dq.duplicate_rate, dq.missing_rate, dq.invalid_status_rate,
    )
    transfers_dirty = inject_data_quality_issues(
        rng, transfers, "status", "transfer_id",
        dq.duplicate_rate, dq.missing_rate, dq.invalid_status_rate,
    )
    atm_dirty = inject_data_quality_issues(
        rng, atm_txns, "status", "atm_txn_id",
        dq.duplicate_rate, dq.missing_rate, dq.invalid_status_rate,
    )
    card_dirty = inject_data_quality_issues(
        rng, card_txns, "status", "card_txn_id",
        dq.duplicate_rate, dq.missing_rate, dq.invalid_status_rate,
    )
    cards_dirty = inject_data_quality_issues(
        rng, cards, "card_status", "card_id",
        dq.duplicate_rate, dq.missing_rate, dq.invalid_status_rate,
    )
    merchants_dirty = inject_data_quality_issues(
        rng, merchants, "merchant_status", "merchant_id",
        dq.duplicate_rate, dq.missing_rate, dq.invalid_status_rate,
    )
    branches_dirty = inject_data_quality_issues(
        rng, branches, "branch_status", "branch_id",
        dq.duplicate_rate * 0.5, dq.missing_rate, dq.invalid_status_rate,
    )

    # Intentionally inject a few invalid FKs into transactions
    n_bad_fk = max(1, int(len(transactions_dirty) * 0.001))
    bad_idx = rng.choice(len(transactions_dirty), size=n_bad_fk, replace=False)
    for i in bad_idx:
        transactions_dirty.at[i, "account_id"] = "ACC-INVALID"

    root = settings.data_source_dir

    # Write to source-system folders with intentionally different schemas where noted
    _write_source(customers_dirty, "customer_system", "customers.csv", root)
    _write_source(branches_dirty, "branch_system", "branches.csv", root)
    _write_source(accounts_dirty, "core_banking", "accounts.csv", root)
    _write_source(transactions_dirty, "core_banking", "transactions.csv", root)
    _write_source(transfers_dirty, "core_banking", "transfers.csv", root)
    _write_source(merchants_dirty, "card_system", "merchants.csv", root)
    _write_source(cards_dirty, "card_system", "cards.csv", root)
    _write_source(card_dirty, "card_system", "card_transactions.csv", root)
    _write_source(atm_dirty, "atm_system", "atm_transactions.csv", root)

    # Clean reference copies for reconciliation (no DQ issues)
    clean_dir = settings.data_processed_dir / "clean_reference"
    clean_dir.mkdir(parents=True, exist_ok=True)
    customers.to_csv(clean_dir / "customers.csv", index=False)
    accounts.to_csv(clean_dir / "accounts.csv", index=False)
    transactions.to_csv(clean_dir / "transactions.csv", index=False)

    # Manifest
    counts = {
        "customers": len(customers_dirty),
        "accounts": len(accounts_dirty),
        "branches": len(branches_dirty),
        "merchants": len(merchants_dirty),
        "cards": len(cards_dirty),
        "transactions": len(transactions_dirty),
        "transfers": len(transfers_dirty),
        "atm_transactions": len(atm_dirty),
        "card_transactions": len(card_dirty),
        "injected_anomalies": int((transactions["is_injected_anomaly"] == "true").sum()),
        "generated_at": datetime.now().astimezone().isoformat(),
        "note": "SYNTHETIC DATA ONLY",
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(counts, indent=2), encoding="utf-8")

    # Sample extracts for GitHub
    samples = settings.data_samples_dir
    samples.mkdir(parents=True, exist_ok=True)
    customers.head(100).to_csv(samples / "customers_sample.csv", index=False)
    transactions.head(100).to_csv(samples / "transactions_sample.csv", index=False)
    accounts.head(100).to_csv(samples / "accounts_sample.csv", index=False)

    logger.info("=" * 60)
    logger.info("GENERATION COMPLETE — Row counts (source files, may include DQ dups):")
    for k, val in counts.items():
        if k not in ("generated_at", "note"):
            logger.info("  %-22s %s", k, f"{val:,}" if isinstance(val, int) else val)
    logger.info("Manifest: %s", manifest_path)
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

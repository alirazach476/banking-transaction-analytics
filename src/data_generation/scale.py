"""
Scalable, vectorised, chunked NovaBank core-banking generator (Phase 1 completion).

Same schemas and anomaly semantics as ``generate_all.py`` but:
  * no per-row Python loops: customers/accounts/transactions are generated with numpy/pandas, time-sliced chunks, so
    memory is bounded and the output file is globally time-ordered;
  * account balances are CONSISTENT with the transaction ledger (see ``build_ledger``): every account's
    ``current_balance`` equals ``opening_balance + sum(signed COMPLETED transactions)`` and no running balance is negative;
  * customer activity history (monthly) and lifecycle (first/last transaction, dormancy) are derived from the transactions;
  * branch and merchant extension tables add attributes (geo, capacity, risk tier, MCC, onboarding).

Writes to its own output folder (default data/scale/<run>); it never touches data/source.
Synthetic data only. Run:  python -m src.data_generation.scale --customers 100000 --accounts 150000 --transactions 2000000
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from src.data_generation.constants import (
    ACCOUNT_STATUS_WEIGHTS, ACCOUNT_STATUSES, ACCOUNT_TYPE_WEIGHTS, ACCOUNT_TYPES, AMOUNT_PARAMS, ANOMALY_TYPES,
    BEHAVIOR_PROFILES, BRANCH_STATUS_WEIGHTS, BRANCH_STATUSES, BRANCH_TYPE_WEIGHTS, BRANCH_TYPES, CHANNEL_WEIGHTS,
    CHANNELS, COUNTRY, CURRENCIES, CURRENCY_WEIGHTS, CUSTOMER_STATUS_WEIGHTS, CUSTOMER_STATUSES,
    CUSTOMER_TYPE_WEIGHTS, CUSTOMER_TYPES, GENDER_WEIGHTS, GENDERS, MERCHANT_CATEGORIES, MERCHANT_CATEGORY_WEIGHTS,
    REGIONS, TRANSACTION_STATUS_WEIGHTS, TRANSACTION_STATUSES, TRANSACTION_TYPE_WEIGHTS, TRANSACTION_TYPES,
)

# Balance effect of COMPLETED transactions
SIGN = {"Deposit": 1, "Interest": 1, "Refund": 1, "Withdrawal": -1, "Payment": -1, "Fee": -1, "Bill Payment": -1, "Transfer": -1}
REGION_CENTROID = {"Northeast": (41.0, -74.0), "Southeast": (33.5, -82.0), "Midwest": (41.5, -88.0),
                   "Southwest": (31.5, -98.0), "West": (38.0, -121.0)}
FIRST = ["Alex", "Sam", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Jamie", "Avery", "Quinn", "Cameron", "Drew"]
LAST = ["Smith", "Johnson", "Lee", "Brown", "Garcia", "Miller", "Davis", "Martinez", "Clark", "Lewis", "Walker", "Hall"]


def _ids(prefix: str, start: int, n: int, width: int = 8) -> np.ndarray:
    return np.char.add(f"{prefix}-", np.char.zfill(np.arange(start, start + n).astype(str), width))


def _pick(rng, options, weights, n):
    p = np.asarray(weights, float)
    return np.asarray(options, dtype=object)[rng.choice(len(options), size=n, p=p / p.sum())]


def _dates(rng, start: str, days: int, n: int) -> np.ndarray:
    return (np.datetime64(start) + rng.integers(0, max(days, 1), size=n).astype("timedelta64[D]")).astype("datetime64[D]").astype(str)


# --------------------------------------------------------------------------- reference tables
def build_reference(rng, n_customers, n_accounts, n_branches, n_merchants, start, end):
    days = (np.datetime64(end) - np.datetime64(start)).astype(int)
    reg = rng.choice(list(REGIONS), size=n_customers)
    city_pick = rng.integers(0, 5, size=n_customers)
    lut = {r: np.array(v, dtype=object) for r, v in REGIONS.items()}
    cities = np.empty(n_customers, dtype=object)
    for r, arr in lut.items():
        m = reg == r
        cities[m] = arr[city_pick[m]]
    customers = pd.DataFrame({
        "customer_id": _ids("CUST", 1, n_customers),
        "first_name": rng.choice(FIRST, n_customers), "last_name": rng.choice(LAST, n_customers),
        "date_of_birth": (np.datetime64("2024-01-01") - rng.integers(18 * 365, 80 * 365, n_customers).astype("timedelta64[D]")).astype(str),
        "gender": _pick(rng, GENDERS, GENDER_WEIGHTS, n_customers),
        "customer_type": _pick(rng, CUSTOMER_TYPES, CUSTOMER_TYPE_WEIGHTS, n_customers),
        "registration_date": _dates(rng, start, days, n_customers),
        "customer_status": _pick(rng, CUSTOMER_STATUSES, CUSTOMER_STATUS_WEIGHTS, n_customers),
        "city": cities, "region": reg, "country": COUNTRY})

    breg = rng.choice(list(REGIONS), size=n_branches)
    bcity = np.empty(n_branches, dtype=object)
    for r in REGIONS:
        m = breg == r
        bcity[m] = np.array(REGIONS[r], dtype=object)[rng.integers(0, 5, size=int(m.sum()))]
    branches = pd.DataFrame({
        "branch_id": _ids("BR", 1, n_branches), "branch_name": [f"NovaBank {c} #{i+1}" for i, c in enumerate(bcity)],
        "city": bcity, "region": breg, "country": COUNTRY,
        "branch_type": _pick(rng, BRANCH_TYPES, BRANCH_TYPE_WEIGHTS, n_branches),
        "opening_date": (np.datetime64("1990-01-01") + rng.integers(0, 11688, n_branches).astype("timedelta64[D]")).astype(str),
        "branch_status": _pick(rng, BRANCH_STATUSES, BRANCH_STATUS_WEIGHTS, n_branches)})

    mreg = rng.choice(list(REGIONS), size=n_merchants)
    mcity = np.empty(n_merchants, dtype=object)
    for r in REGIONS:
        m = mreg == r
        mcity[m] = np.array(REGIONS[r], dtype=object)[rng.integers(0, 5, size=int(m.sum()))]
    cats = _pick(rng, MERCHANT_CATEGORIES, MERCHANT_CATEGORY_WEIGHTS, n_merchants)
    merchants = pd.DataFrame({
        "merchant_id": _ids("MERCH", 1, n_merchants), "merchant_name": [f"Merchant {i+1} {c}"[:60] for i, c in enumerate(cats)],
        "merchant_category": cats, "city": mcity, "region": mreg,
        "merchant_status": rng.choice(["Active", "Inactive"], size=n_merchants, p=[0.9, 0.1])})

    ctype = customers["customer_type"].to_numpy()
    owner = rng.integers(0, n_customers, size=n_accounts)
    ctypes = ctype[owner]
    base = rng.lognormal(8.0, 1.2, size=n_accounts)
    mult = np.vectorize(lambda t: BEHAVIOR_PROFILES.get(t, {"amount_mult": 1.0})["amount_mult"])(ctypes) if n_accounts < 10 else \
        pd.Series(ctypes).map({k: v["amount_mult"] for k, v in BEHAVIOR_PROFILES.items()}).fillna(1.0).to_numpy()
    legacy_balance = np.round(np.clip(base * mult, 0, 5_000_000), 2)
    statuses = _pick(rng, ACCOUNT_STATUSES, ACCOUNT_STATUS_WEIGHTS, n_accounts)
    open_dates = _dates(rng, "2020-01-01", 1500, n_accounts)
    close_off = rng.integers(30, 800, size=n_accounts).astype("timedelta64[D]")
    close_dates = np.where(statuses == "Closed", (np.datetime64("2020-01-01") + (np.array(open_dates, dtype="datetime64[D]") - np.datetime64("2020-01-01")) + close_off).astype(str), "")
    accounts = pd.DataFrame({
        "account_id": _ids("ACC", 1, n_accounts), "customer_id": customers["customer_id"].to_numpy()[owner],
        "account_type": _pick(rng, ACCOUNT_TYPES, ACCOUNT_TYPE_WEIGHTS, n_accounts),
        "branch_id": branches["branch_id"].to_numpy()[rng.integers(0, n_branches, size=n_accounts)],
        "open_date": open_dates, "close_date": close_dates,
        "currency": _pick(rng, CURRENCIES, CURRENCY_WEIGHTS, n_accounts), "current_balance": legacy_balance,
        "account_status": statuses})
    return customers, accounts, branches, merchants


def branch_extensions(rng, branches: pd.DataFrame) -> pd.DataFrame:
    n = len(branches)
    lat0 = branches["region"].map(lambda r: REGION_CENTROID[r][0]).to_numpy()
    lon0 = branches["region"].map(lambda r: REGION_CENTROID[r][1]).to_numpy()
    size = np.round(rng.lognormal(8.0, 0.4, n)).astype(int)
    return pd.DataFrame({
        "branch_id": branches["branch_id"], "latitude": np.round(lat0 + rng.normal(0, 1.5, n), 4),
        "longitude": np.round(lon0 + rng.normal(0, 1.8, n), 4), "floor_area_sqft": size,
        "staff_count": np.clip((size / 220 + rng.normal(0, 2, n)).round().astype(int), 3, None),
        "atm_count": rng.integers(0, 5, n), "has_safe_deposit": rng.random(n) < 0.45,
        "weekend_open": rng.random(n) < 0.6, "note": "SYNTHETIC; coordinates are region centroids plus noise"})


def merchant_extensions(rng, merchants: pd.DataFrame, start: str) -> pd.DataFrame:
    n = len(merchants)
    mcc = {"Grocery": 5411, "Restaurant": 5812, "Fuel": 5541, "Retail": 5311, "Travel": 4722, "Healthcare": 8011,
           "Education": 8299, "Entertainment": 7832, "Technology": 5732, "Utilities": 4900, "Other": 5999}
    tier = _pick(rng, ["Low", "Medium", "High"], [0.7, 0.25, 0.05], n)
    cb = np.where(tier == "High", rng.beta(2, 60, n), np.where(tier == "Medium", rng.beta(2, 200, n), rng.beta(1, 500, n)))
    return pd.DataFrame({
        "merchant_id": merchants["merchant_id"], "mcc": merchants["merchant_category"].map(mcc).fillna(5999).astype(int),
        "risk_tier": tier, "onboarded_on": _dates(rng, "2015-01-01", 3650, n), "avg_ticket_usd": np.round(rng.lognormal(3.8, 0.7, n), 2),
        "synthetic_chargeback_rate": np.round(cb, 5), "note": "SYNTHETIC"})


# --------------------------------------------------------------------------- transactions
def _amounts(rng, txn_types, ctypes):
    amt = np.empty(len(txn_types))
    mult = pd.Series(ctypes).map({k: v["amount_mult"] for k, v in BEHAVIOR_PROFILES.items()}).fillna(1.0).to_numpy()
    for t in TRANSACTION_TYPES:
        m = txn_types == t
        if m.any():
            p = AMOUNT_PARAMS[t]
            amt[m] = np.round(np.clip(rng.lognormal(p["mean"], p["sigma"], int(m.sum())), p["min"], p["max"]) * mult[m], 2)
    return amt


def _timestamps(rng, n, t0: np.datetime64, t1: np.datetime64):
    """Uniform in [t0,t1) then thinned: weekends keep 60%, hours 0-5 keep 15% (vectorised rejection sampling)."""
    span = int((t1 - t0) / np.timedelta64(1, "s"))
    out = np.empty(0, dtype="datetime64[s]")
    while len(out) < n:
        k = int((n - len(out)) * 1.8) + 16
        ts = t0.astype("datetime64[s]") + rng.integers(0, span, size=k).astype("timedelta64[s]")
        dow = ((ts.astype("datetime64[D]").astype(int) + 3) % 7)  # 1970-01-01 was Thursday (3), Monday=0
        hour = ((ts - ts.astype("datetime64[D]")) / np.timedelta64(1, "h")).astype(int)
        keep = np.where(dow >= 5, rng.random(k) <= 0.6, True) & np.where(hour < 6, rng.random(k) <= 0.15, True)
        out = np.concatenate([out, ts[keep]])
    return np.sort(out[:n])


def generate_transactions(rng, n, customers, accounts, branches, merchants, start, end, anomaly_rate, out_csv: Path,
                          slices: int | None = None) -> dict:
    """Time-sliced chunks appended to ``out_csv``. Returns counters. Memory ~ one slice."""
    ctype_by_cust = pd.Series(customers["customer_type"].to_numpy(), index=customers["customer_id"].to_numpy())
    acc_ids, acc_cust, acc_ccy = accounts["account_id"].to_numpy(), accounts["customer_id"].to_numpy(), accounts["currency"].to_numpy()
    acc_branch = accounts["branch_id"].to_numpy()
    acc_ctype = ctype_by_cust.reindex(acc_cust).to_numpy()
    fw = pd.Series(acc_ctype).map({k: v["freq_mult"] for k, v in BEHAVIOR_PROFILES.items()}).fillna(1.0).to_numpy()
    fw = fw / fw.sum()
    merch, brs = merchants["merchant_id"].to_numpy(), branches["branch_id"].to_numpy()
    t0, t1 = np.datetime64(start), np.datetime64(end)
    slices = slices or max(1, int(np.ceil(n / 250_000)))
    edges = np.linspace(t0.astype("datetime64[s]").astype(np.int64), t1.astype("datetime64[s]").astype(np.int64), slices + 1).astype(np.int64)
    # rows per slice proportional to slice length (weekday/hour thinning is applied inside the slice)
    per = np.diff(edges); counts = np.floor(per / per.sum() * n).astype(int); counts[-1] += n - counts.sum()
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    if out_csv.exists():
        out_csv.unlink()
    next_id, n_anom_total, n_burst = 1, 0, 0
    for s in range(slices):
        m = int(counts[s])
        if m <= 0:
            continue
        ts = _timestamps(rng, m, np.datetime64(int(edges[s]), "s"), np.datetime64(int(edges[s + 1]), "s"))
        ai = rng.choice(len(acc_ids), size=m, p=fw)
        types = _pick(rng, TRANSACTION_TYPES, TRANSACTION_TYPE_WEIGHTS, m)
        status = _pick(rng, TRANSACTION_STATUSES, TRANSACTION_STATUS_WEIGHTS, m)
        chan = _pick(rng, CHANNELS, CHANNEL_WEIGHTS, m)
        amt = _amounts(rng, types, acc_ctype[ai])
        merchant = np.where(np.isin(chan, ["POS", "Online", "Mobile App"]) & np.isin(types, ["Payment", "Refund", "Bill Payment"]),
                            merch[rng.integers(0, len(merch), m)], "").astype(object)
        branch = np.where(np.isin(chan, ["Branch", "ATM"]), brs[rng.integers(0, len(brs), m)],
                          np.where(rng.random(m) < 0.3, acc_branch[ai], "")).astype(object)
        anomaly = np.zeros(m, dtype=bool); atype = np.full(m, "", dtype=object)
        k = int(m * anomaly_rate)
        idx = rng.choice(m, size=k, replace=False)
        at = rng.choice(ANOMALY_TYPES, size=k)
        anomaly[idx] = True; atype[idx] = at
        ha = idx[at == "high_amount"]; amt[ha] = np.round(amt[ha] * rng.uniform(15, 40, len(ha)), 2)
        sb = idx[at == "sudden_behavior_change"]; amt[sb] = np.round(amt[sb] * rng.uniform(12, 25, len(sb)), 2)
        na = idx[at == "night_activity"]
        sec = rng.integers(1 * 3600, 5 * 3600, len(na)) + rng.integers(0, 3600, len(na)) % 3600
        ts[na] = ts[na].astype("datetime64[D]").astype("datetime64[s]") + np.minimum(sec, 5 * 3600 - 1).astype("timedelta64[s]")
        amt[na] = np.maximum(amt[na], 1500.0)
        ul = idx[at == "unusual_location"]; branch[ul] = brs[rng.integers(0, len(brs), len(ul))]; chan[ul] = "Branch"
        status[idx[at == "multiple_failures"]] = "Failed"
        ids = _ids("TXN", next_id, m, 10); next_id += m
        df = pd.DataFrame({"transaction_id": ids, "account_id": acc_ids[ai], "customer_id": acc_cust[ai],
                           "transaction_timestamp": pd.Series(ts).dt.strftime("%Y-%m-%d %H:%M:%S").to_numpy(),
                           "transaction_type": types, "amount": amt, "currency": acc_ccy[ai], "channel": chan,
                           "merchant_id": merchant, "branch_id": branch, "transaction_status": status,
                           "reference_type": "standard", "is_injected_anomaly": np.where(anomaly, "true", "false"),
                           "anomaly_type": atype})
        # rapid/high-frequency bursts: 8 payments, 2 minutes apart, for a subset of flagged customers
        rapid = idx[np.isin(at, ["rapid_transactions", "high_frequency"])][: max(1, k // 10)]
        if len(rapid):
            b = np.repeat(rapid, 8)
            offs = np.tile(np.arange(8) * 120, len(rapid)).astype("timedelta64[s]")
            bts = np.repeat(ts[rapid], 8) + offs
            nb = len(b)
            burst = pd.DataFrame({"transaction_id": _ids("TXN", next_id, nb, 10), "account_id": acc_ids[ai][b],
                                  "customer_id": acc_cust[ai][b], "transaction_timestamp": pd.Series(bts).dt.strftime("%Y-%m-%d %H:%M:%S").to_numpy(),
                                  "transaction_type": "Payment", "amount": np.round(rng.uniform(50, 400, nb), 2),
                                  "currency": acc_ccy[ai][b], "channel": "Mobile App", "merchant_id": merch[rng.integers(0, len(merch), nb)],
                                  "branch_id": "", "transaction_status": "Completed", "reference_type": "anomaly_burst",
                                  "is_injected_anomaly": "true", "anomaly_type": "rapid_transactions"})
            next_id += nb; n_burst += nb
            df = pd.concat([df, burst], ignore_index=True)
        df["updated_at"] = df["transaction_timestamp"]
        df = df.sort_values("transaction_timestamp", kind="stable")
        df.to_csv(out_csv, mode="a", header=not out_csv.exists(), index=False)
        n_anom_total += k
    return {"rows": next_id - 1, "anomalies": n_anom_total, "burst_rows": n_burst, "slices": slices}


# --------------------------------------------------------------------------- ledger + activity
def build_ledger(txn_csv: Path, accounts: pd.DataFrame, ledger_csv: Path, chunksize: int = 500_000) -> tuple[pd.DataFrame, dict]:
    """Make balances consistent with the ledger.

    Pass 1 accumulates per-account net movement and the minimum running balance (COMPLETED rows only).
    opening_balance = legacy balance lifted just enough that the running balance never goes below 0.
    Pass 2 writes ``transaction_id, account_id, signed_amount, balance_after`` (non-completed rows carry the unchanged balance).
    Returns accounts with ``opening_balance`` and ``current_balance`` (= closing) plus stats.
    """
    pos = pd.Series(np.arange(len(accounts)), index=accounts["account_id"].to_numpy())
    net = np.zeros(len(accounts)); runmin = np.zeros(len(accounts))
    for ch in pd.read_csv(txn_csv, usecols=["transaction_id", "account_id", "transaction_type", "amount", "transaction_status"], chunksize=chunksize):
        sg = ch.transaction_type.map(SIGN).to_numpy() * np.where(ch.transaction_status == "Completed", 1, 0)
        ch["s"] = sg * ch.amount.to_numpy()
        a = pos.reindex(ch.account_id.to_numpy()).to_numpy()
        ch["a"] = a
        ch = ch.sort_values("a", kind="stable")  # preserves time order within account
        cs = ch.groupby("a")["s"].cumsum().to_numpy() + net[ch.a.to_numpy()]
        np.minimum.at(runmin, ch.a.to_numpy(), cs)
        np.add.at(net, ch.a.to_numpy(), ch.s.to_numpy())
    legacy = accounts["current_balance"].to_numpy()
    opening = np.round(np.maximum(legacy, -runmin), 2)
    acc = accounts.copy(); acc["opening_balance"] = opening
    acc["current_balance"] = np.round(opening + net, 2)
    acc["balance_note"] = np.where(opening > legacy, "opening lifted to cover outflows", "")
    running = opening.copy(); neg = 0; first = True
    ledger_csv.parent.mkdir(parents=True, exist_ok=True)
    if ledger_csv.exists():
        ledger_csv.unlink()
    for ch in pd.read_csv(txn_csv, usecols=["transaction_id", "account_id", "transaction_type", "amount", "transaction_status", "transaction_timestamp"], chunksize=chunksize):
        ch["signed_amount"] = ch.transaction_type.map(SIGN).to_numpy() * np.where(ch.transaction_status == "Completed", 1, 0) * ch.amount.to_numpy()
        a = pos.reindex(ch.account_id.to_numpy()).to_numpy()
        order = np.argsort(a, kind="stable")
        sa = a[order]; ss = ch.signed_amount.to_numpy()[order]
        cs = pd.Series(ss).groupby(sa).cumsum().to_numpy() + running[sa]
        bal = np.empty(len(ch)); bal[order] = cs
        np.add.at(running, a, ch.signed_amount.to_numpy())
        ch["balance_after"] = np.round(bal, 2)
        neg += int((ch.balance_after < -0.005).sum())
        ch[["transaction_id", "account_id", "signed_amount", "balance_after"]].to_csv(ledger_csv, mode="a", header=first, index=False)
        first = False
    return acc, {"accounts_lifted": int((opening > legacy).sum()), "negative_balance_rows": neg,
                 "max_abs_closing_mismatch": float(np.abs(running - acc["current_balance"].to_numpy()).max())}


def build_customer_activity(txn_csv: Path, customers: pd.DataFrame, chunksize: int = 500_000, as_of: str | None = None):
    parts = []
    first_last = []
    for ch in pd.read_csv(txn_csv, usecols=["customer_id", "transaction_timestamp", "amount", "transaction_status", "is_injected_anomaly"], chunksize=chunksize):
        ch["month"] = ch.transaction_timestamp.str.slice(0, 7)
        ch["completed"] = (ch.transaction_status == "Completed")
        ch["failed"] = (ch.transaction_status == "Failed")
        ch["anom"] = (ch.is_injected_anomaly == "true")
        g = ch.groupby(["customer_id", "month"]).agg(txn_count=("amount", "size"), total_amount=("amount", "sum"),
                                                     completed=("completed", "sum"), failed=("failed", "sum"), anomalies=("anom", "sum")).reset_index()
        parts.append(g)
        fl = ch.groupby("customer_id").transaction_timestamp.agg(["min", "max"]).reset_index()
        first_last.append(fl)
    monthly = pd.concat(parts).groupby(["customer_id", "month"], as_index=False).sum()
    monthly["total_amount"] = monthly.total_amount.round(2)
    fl = pd.concat(first_last).groupby("customer_id").agg(first_txn=("min", "min"), last_txn=("max", "max")).reset_index()
    months = monthly.groupby("customer_id").month.nunique().rename("active_months").reset_index()
    life = customers[["customer_id", "registration_date", "customer_status"]].merge(fl, how="left").merge(months, how="left")
    asof = pd.Timestamp(as_of or life.last_txn.dropna().max())
    life["days_since_last_txn"] = (asof - pd.to_datetime(life.last_txn)).dt.days
    life["activity_state"] = np.select([life.first_txn.isna(), life.days_since_last_txn > 90], ["never_active", "dormant"], "active")
    life["active_months"] = life.active_months.fillna(0).astype(int)
    return monthly, life


# --------------------------------------------------------------------------- CLI
def main(argv=None) -> dict:
    ap = argparse.ArgumentParser(description="Scalable NovaBank core-banking generator (synthetic)")
    ap.add_argument("--customers", type=int, default=100_000)
    ap.add_argument("--accounts", type=int, default=150_000)
    ap.add_argument("--branches", type=int, default=200)
    ap.add_argument("--merchants", type=int, default=20_000)
    ap.add_argument("--transactions", type=int, default=1_000_000)
    ap.add_argument("--anomaly-rate", type=float, default=0.002)
    ap.add_argument("--start", default="2023-01-01"); ap.add_argument("--end", default="2025-12-31")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--out", type=Path, default=Path("data/scale/run"))
    a = ap.parse_args(argv)
    rng = np.random.default_rng(a.seed)
    out = a.out; out.mkdir(parents=True, exist_ok=True)
    T = {}; t = time.perf_counter()
    cu, ac, br, me = build_reference(rng, a.customers, a.accounts, a.branches, a.merchants, a.start, a.end)
    T["reference_s"] = round(time.perf_counter() - t, 1); t = time.perf_counter()
    info = generate_transactions(rng, a.transactions, cu, ac, br, me, a.start, a.end, a.anomaly_rate, out / "transactions.csv")
    T["transactions_s"] = round(time.perf_counter() - t, 1); t = time.perf_counter()
    ac2, lstats = build_ledger(out / "transactions.csv", ac, out / "transactions_ledger.csv")
    T["ledger_s"] = round(time.perf_counter() - t, 1); t = time.perf_counter()
    monthly, life = build_customer_activity(out / "transactions.csv", cu)
    T["activity_s"] = round(time.perf_counter() - t, 1)
    cu.to_csv(out / "customers.csv", index=False); ac2.to_csv(out / "accounts.csv", index=False)
    br.to_csv(out / "branches.csv", index=False); me.to_csv(out / "merchants.csv", index=False)
    branch_extensions(rng, br).to_csv(out / "branch_extensions.csv", index=False)
    merchant_extensions(rng, me, a.start).to_csv(out / "merchant_extensions.csv", index=False)
    monthly.to_csv(out / "customer_activity_monthly.csv", index=False); life.to_csv(out / "customer_lifecycle.csv", index=False)
    manifest = {"seed": a.seed, "generated_at": datetime.now().astimezone().isoformat(), "customers": len(cu), "accounts": len(ac2),
                "branches": len(br), "merchants": len(me), **info, "ledger": lstats, "timings": T,
                "activity_states": life.activity_state.value_counts().to_dict(), "note": "SYNTHETIC DATA ONLY"}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    print(json.dumps(manifest, indent=2, default=str))
    return manifest


if __name__ == "__main__":
    main()

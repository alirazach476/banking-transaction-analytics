"""
Vectorised, chunked generator for the synthetic payment lifecycle.

Produces, per chunk, three clean frames:
  * ``transactions``  - one row per payment attempt
  * ``events``        - lifecycle events (auth request/response, clearing,
                        settlement, reversal, refund, chargeback)
  * ``settlements``   - settlement records (with injected business exceptions)
plus ``truth`` - ground truth of injected settlement exceptions (test/eval only).

Determinism: each chunk draws from ``default_rng([seed, stream, chunk_idx])`` so a
run is reproducible for a fixed (seed, chunk_size) pair.
ALL DATA IS SYNTHETIC.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import numpy as np
import pandas as pd

from src.payments.config import PaymentGenConfig
from src.payments.constants import (
    CARD_NOT_PRESENT_CHANNELS, CATEGORY_AMOUNT, CATEGORY_WEIGHTS, CHANNELS,
    CHANNEL_WEIGHTS, CHARGEBACK_REASONS, COUNTRIES, DECLINE_LOGIT,
    DECLINE_REASON_WEIGHTS, DECLINE_REASONS, PROFILE_AMOUNT_MULT,
    PROFILE_FREQ_MULT, SETTLEMENT_CURRENCY,
)
from src.payments.fx import generate_fx_rates

TS_FMT = "%Y-%m-%d %H:%M:%S"


@dataclass
class Reference:
    cards: pd.DataFrame
    merchants: pd.DataFrame


@dataclass
class Chunk:
    transactions: pd.DataFrame
    events: pd.DataFrame
    settlements: pd.DataFrame
    truth: pd.DataFrame


# --------------------------------------------------------------------------- #
# Reference data
# --------------------------------------------------------------------------- #
def build_reference(cfg: PaymentGenConfig, existing_dir: Path | None = None) -> Reference:
    """Build card & merchant reference data.

    If ``existing_dir`` (``data/source``) holds the legacy cards/merchants CSVs, their
    IDs are reused (deduplicated, null IDs dropped) so payments join the existing
    warehouse; country/profile attributes are assigned deterministically.
    """
    rng = np.random.default_rng([cfg.seed, 1])
    countries = list(COUNTRIES)
    cw = np.array([COUNTRIES[c][1] for c in countries])
    cw = cw / cw.sum()

    cards = merchants = None
    if existing_dir is not None:
        cp = existing_dir / "card_system" / "cards.csv"
        mp = existing_dir / "card_system" / "merchants.csv"
        if cp.exists() and mp.exists():
            cards = pd.read_csv(cp, dtype=str).dropna(subset=["card_id"]).drop_duplicates("card_id")
            cards["card_status"] = cards["card_status"].fillna("Active").str.strip().str.title()
            cards["customer_id"] = cards["customer_id"].fillna("")
            cards["account_id"] = cards["account_id"].fillna("")
            cards["expiry_date"] = pd.to_datetime(cards["expiry_date"], errors="coerce").fillna(
                pd.Timestamp("2030-01-01")
            )
            m = pd.read_csv(mp, dtype=str).dropna(subset=["merchant_id"]).drop_duplicates("merchant_id")
            m["merchant_category"] = m["merchant_category"].fillna("Other").str.strip().str.title()
            m.loc[~m["merchant_category"].isin(CATEGORY_AMOUNT), "merchant_category"] = "Other"
            merchants = m[["merchant_id", "merchant_category"]].reset_index(drop=True)
            cards = cards[["card_id", "customer_id", "account_id", "card_status", "expiry_date"]].reset_index(drop=True)

    if cards is None:
        n = cfg.num_cards
        issue = pd.Timestamp("2019-01-01") + pd.to_timedelta(rng.integers(0, 2000, n), unit="D")
        cards = pd.DataFrame({
            "card_id": [f"CARD-{i:06d}" for i in range(1, n + 1)],
            "customer_id": [f"CUST-{i:08d}" for i in rng.integers(1, cfg.num_customers + 1, n)],
            "account_id": [f"ACC-{i:08d}" for i in rng.integers(1, cfg.num_accounts + 1, n)],
            "card_status": rng.choice(["Active", "Inactive", "Blocked", "Expired"], n, p=[.82, .08, .05, .05]),
            "expiry_date": issue + pd.to_timedelta(365 * 4, unit="D"),
        })
        # Cards flagged Expired get an expiry date in the past relative to the data window
        exp = cards["card_status"] == "Expired"
        cards.loc[exp, "expiry_date"] = pd.Timestamp(cfg.start_date) + pd.to_timedelta(
            rng.integers(0, 900, int(exp.sum())), unit="D"
        )
    if merchants is None:
        n = cfg.num_merchants
        cats = list(CATEGORY_WEIGHTS)
        cp_ = np.array(list(CATEGORY_WEIGHTS.values()))
        merchants = pd.DataFrame({
            "merchant_id": [f"MERCH-{i:08d}" for i in range(1, n + 1)],
            "merchant_category": rng.choice(cats, n, p=cp_ / cp_.sum()),
        })

    nc, nm = len(cards), len(merchants)
    cards["card_country"] = rng.choice(["US", "GB", "DE", "CA"], nc, p=[.85, .06, .04, .05])
    cards["card_profile"] = rng.choice(list(PROFILE_AMOUNT_MULT), nc, p=[.55, .15, .15, .15])
    cards["card_currency"] = cards["card_country"].map(lambda c: COUNTRIES[c][0])
    status_mult = cards["card_status"].map({"Active": 1.0, "Inactive": 0.3, "Blocked": 0.03, "Expired": 0.03}).fillna(1.0)
    cards["activity_weight"] = (rng.lognormal(0, 0.8, nc) * cards["card_profile"].map(PROFILE_FREQ_MULT).values
                                * status_mult.values)

    merchants["merchant_country"] = rng.choice(countries, nm, p=cw)
    merchants["merchant_currency"] = merchants["merchant_country"].map(lambda c: COUNTRIES[c][0])
    merchants["popularity"] = rng.lognormal(0, 1.0, nm)
    return Reference(cards=cards.reset_index(drop=True), merchants=merchants.reset_index(drop=True))


# --------------------------------------------------------------------------- #
# Temporal sampling
# --------------------------------------------------------------------------- #
def _calendar_weights(start: str, end: str) -> tuple[np.ndarray, np.ndarray]:
    days = pd.date_range(start, end, freq="D")
    dow = np.where(days.dayofweek == 5, 0.88, np.where(days.dayofweek == 6, 0.78, 1.0))
    month = days.month.map({11: 1.25, 12: 1.40, 1: 0.90, 2: 0.92}).fillna(1.0).to_numpy()
    payday = np.where(np.isin(days.day, [1, 15, 30]), 1.15, 1.0)
    trend = 1.0 + 0.15 * (np.arange(len(days)) / max(len(days) - 1, 1))
    w = dow * month * payday * trend
    return days.to_numpy(dtype="datetime64[D]"), w / w.sum()


_HOUR_W = np.array([.4, .25, .2, .2, .3, .6, 1.2, 2.0, 2.8, 3.2, 3.5, 3.8,
                    4.2, 4.0, 3.6, 3.4, 3.6, 4.0, 4.2, 3.8, 3.0, 2.2, 1.4, .8])
_HOUR_P = _HOUR_W / _HOUR_W.sum()


def _timestamps(rng: np.random.Generator, n: int, days: np.ndarray, p: np.ndarray) -> np.ndarray:
    d = days[rng.choice(len(days), size=n, p=p)].astype("datetime64[s]")
    h = rng.choice(24, size=n, p=_HOUR_P)
    s = rng.integers(0, 3600, size=n)
    return d + (h * 3600 + s).astype("timedelta64[s]")


def _choice_matrix(rng: np.random.Generator, weights: np.ndarray) -> np.ndarray:
    """Row-wise categorical sampling from an (n, k) non-negative weight matrix."""
    cum = np.cumsum(weights / weights.sum(axis=1, keepdims=True), axis=1)
    u = rng.random(weights.shape[0])[:, None]
    return np.minimum((cum < u).sum(axis=1), weights.shape[1] - 1)


# --------------------------------------------------------------------------- #
# Generator
# --------------------------------------------------------------------------- #
class PaymentGenerator:
    def __init__(self, cfg: PaymentGenConfig, ref: Reference | None = None, existing_dir: Path | None = None):
        self.cfg = cfg
        self.ref = ref or build_reference(cfg, existing_dir)
        self.days, self.day_p = _calendar_weights(cfg.start_date, cfg.end_date)
        # FX window extends past end_date because clearing/settlement/chargebacks trail auth
        fx_end = (pd.Timestamp(cfg.end_date) + pd.Timedelta(days=200)).strftime("%Y-%m-%d")
        self.fx = generate_fx_rates(cfg.seed, cfg.start_date, fx_end)
        self._fx_lookup = self._build_fx_lookup()
        self._pay_counter = 0
        self._evt_counter = 0
        self._stl_counter = 0

        r = self.ref
        self._card_p = (r.cards["activity_weight"] / r.cards["activity_weight"].sum()).to_numpy()
        self._merch_p = (r.merchants["popularity"] / r.merchants["popularity"].sum()).to_numpy()
        self._fx_start = pd.Timestamp(cfg.start_date).normalize()

    # ------------------------------------------------------------------ FX
    def _build_fx_lookup(self) -> dict[str, np.ndarray]:
        out = {}
        for ccy, g in self.fx.groupby("base_currency"):
            out[ccy] = g.sort_values("rate_date")["rate"].to_numpy()
        return out

    def fx_rate(self, currency: np.ndarray, ts: np.ndarray) -> np.ndarray:
        """USD-per-unit rate for ``currency`` on the date of ``ts`` (vectorised)."""
        day_idx = ((ts.astype("datetime64[D]") - np.datetime64(self._fx_start.date(), "D"))
                   .astype(int)).clip(min=0)
        out = np.ones(len(currency))
        for ccy, arr in self._fx_lookup.items():
            m = currency == ccy
            if m.any():
                out[m] = arr[np.minimum(day_idx[m], len(arr) - 1)]
        return out

    def _pick_merchants(self, rng, card_idx: np.ndarray, domestic_share: float = 0.92,
                        foreign: bool = False) -> np.ndarray:
        """Choose merchants, biased to the card's own country (or foreign-only if ``foreign``)."""
        m = self.ref.merchants
        idx = rng.choice(len(m), size=len(card_idx), p=self._merch_p)
        ccountry = self.ref.cards["card_country"].to_numpy()[card_idx]
        mcountry = m["merchant_country"].to_numpy()
        for country in np.unique(ccountry):
            pool = np.flatnonzero((mcountry != country) if foreign else (mcountry == country))
            if len(pool) == 0:
                continue
            sel = (ccountry == country) & ((rng.random(len(card_idx)) < domestic_share) | foreign)
            if sel.any():
                p = self._merch_p[pool]
                idx[sel] = pool[rng.choice(len(pool), size=int(sel.sum()), p=p / p.sum())]
        return idx

    # --------------------------------------------------------- core builders
    def _next_ids(self, prefix: str, counter_attr: str, n: int, width: int) -> np.ndarray:
        start = getattr(self, counter_attr)
        setattr(self, counter_attr, start + n)
        return np.array([f"{prefix}-{i:0{width}d}" for i in range(start + 1, start + n + 1)])

    def _txn_frame(self, rng, card_idx, merch_idx, auth_ts, channel, recurring_amount=None,
                   fraud_flag=None, amount_boost=None) -> pd.DataFrame:
        cards, merchants = self.ref.cards, self.ref.merchants
        n = len(card_idx)
        c = cards.iloc[card_idx]
        m = merchants.iloc[merch_idx]
        cat = m["merchant_category"].to_numpy()
        mu = np.array([CATEGORY_AMOUNT[x][0] for x in cat])
        sg = np.array([CATEGORY_AMOUNT[x][1] for x in cat])
        mult = c["card_profile"].map(PROFILE_AMOUNT_MULT).to_numpy()
        if recurring_amount is not None:
            amount_usd = recurring_amount
        else:
            amount_usd = np.clip(rng.lognormal(mu, sg) * mult, 1.0, 25_000.0)
        if amount_boost is not None:
            amount_usd = amount_usd * amount_boost
        mccy = m["merchant_currency"].to_numpy()
        # convert USD-equivalent amount to merchant currency at the auth-date rate
        rate = self.fx_rate(mccy, auth_ts)
        amount = np.round(amount_usd / rate, 2)
        amount = np.maximum(amount, 0.01)
        mc = m["merchant_country"].to_numpy()
        cc = c["card_country"].to_numpy()
        international = mc != cc
        fraud = np.zeros(n, dtype=bool) if fraud_flag is None else fraud_flag
        pay_ids = self._next_ids("PAY", "_pay_counter", n, 10)
        return pd.DataFrame({
            "payment_id": pay_ids,
            "card_id": c["card_id"].to_numpy(),
            "customer_id": c["customer_id"].to_numpy(),
            "account_id": c["account_id"].to_numpy(),
            "merchant_id": m["merchant_id"].to_numpy(),
            "merchant_category": cat,
            "merchant_country": mc,
            "card_country": cc,
            "channel": channel,
            "amount": amount,
            "currency": mccy,
            "billing_currency": c["card_currency"].to_numpy(),
            "is_international": international,
            "authorization_ts": auth_ts,
            "card_status": c["card_status"].to_numpy(),
            "card_expiry_date": c["expiry_date"].to_numpy(),
            "synthetic_fraud_pattern": fraud,
            "is_synthetic": True,
        })

    # ----------------------------------------------------------- streams
    def _random_stream(self, rng, n) -> pd.DataFrame:
        card_idx = rng.choice(len(self.ref.cards), size=n, p=self._card_p)
        merch_idx = self._pick_merchants(rng, card_idx)
        ts = _timestamps(rng, n, self.days, self.day_p)
        channel = rng.choice(CHANNELS, size=n, p=np.array(CHANNEL_WEIGHTS) / sum(CHANNEL_WEIGHTS))
        # a small share of high-value foreign card-not-present payments (synthetic fraud-like)
        fv = rng.random(n) < 0.002
        boost = np.where(fv, rng.uniform(6, 15, n), 1.0)
        df = self._txn_frame(rng, card_idx, merch_idx, ts, channel, fraud_flag=fv, amount_boost=boost)
        return df

    def _recurring_stream(self, rng, n_target) -> pd.DataFrame:
        """Monthly subscriptions: fixed (card, merchant, amount, day-of-month)."""
        months = pd.date_range(self.cfg.start_date, self.cfg.end_date, freq="MS")
        n_subs = max(1, n_target // max(len(months), 1))
        card_idx = rng.choice(len(self.ref.cards), size=n_subs, p=self._card_p)
        merch_idx = self._pick_merchants(rng, card_idx)
        base_amt = np.round(rng.lognormal(2.9, 0.6, n_subs), 2).clip(2, 400)
        dom = rng.integers(1, 28, n_subs)
        hour = rng.integers(0, 6, n_subs)
        start_m = rng.integers(0, max(len(months) // 2, 1), n_subs)
        parts = []
        for mi, mstart in enumerate(months):
            active = start_m <= mi
            k = int(active.sum())
            if k == 0:
                continue
            ts = (np.datetime64(mstart.date(), "D") + (dom[active] - 1).astype("timedelta64[D]")).astype("datetime64[s]") \
                 + (hour[active] * 3600).astype("timedelta64[s]")
            parts.append(self._txn_frame(
                rng, card_idx[active], merch_idx[active], ts,
                np.full(k, "Recurring", dtype=object), recurring_amount=base_amt[active]))
        return pd.concat(parts, ignore_index=True) if parts else self._empty_txn()

    def _fraud_burst_stream(self, rng) -> pd.DataFrame:
        """Compromised-card bursts: many high-value foreign e-commerce attempts in minutes."""
        n_cards = int(len(self.ref.cards) * self.cfg.fraud_card_share)
        if n_cards == 0:
            return self._empty_txn()
        cards = rng.choice(len(self.ref.cards), size=n_cards, replace=False)
        parts = []
        for ci in cards:
            k = int(rng.integers(6, 13))
            t0 = _timestamps(rng, 1, self.days, self.day_p)[0]
            ts = t0 + (np.sort(rng.integers(0, 20 * 60, k))).astype("timedelta64[s]")
            midx = self._pick_merchants(rng, np.full(k, ci), foreign=True)
            parts.append(self._txn_frame(
                rng, np.full(k, ci), midx, ts, np.full(k, "E-commerce", dtype=object),
                fraud_flag=np.ones(k, dtype=bool), amount_boost=rng.uniform(3, 10, k)))
        return pd.concat(parts, ignore_index=True)

    @staticmethod
    def _empty_txn() -> pd.DataFrame:
        return pd.DataFrame()

    # --------------------------------------------------------- lifecycle
    def _decline_model(self, rng, t: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Return (declined, reason, response_ms) arrays for the transactions."""
        n = len(t)
        co = DECLINE_LOGIT
        usd = t["amount"].to_numpy() * self.fx_rate(t["currency"].to_numpy(), t["authorization_ts"].to_numpy())
        hour = ((t["authorization_ts"].to_numpy().astype("datetime64[s]") -
                 t["authorization_ts"].to_numpy().astype("datetime64[D]").astype("datetime64[s]"))
                .astype(int) // 3600)
        night = (hour < 5).astype(float)
        cnp = t["channel"].isin(CARD_NOT_PRESENT_CHANNELS).to_numpy().astype(float)
        intl = t["is_international"].to_numpy().astype(float)
        fraud = t["synthetic_fraud_pattern"].to_numpy().astype(float)
        z = (co["intercept"] + co["international"] * intl + co["card_not_present"] * cnp
             + co["log10_amount_centered"] * (np.log10(usd + 1) - 1.7)
             + co["night"] * night + co["fraud_pattern"] * fraud)
        p = 1 / (1 + np.exp(-z))
        declined = rng.random(n) < p

        status = t["card_status"].str.title().to_numpy()
        # only cards whose status is Expired are forced-declined; active cards past their nominal
        # expiry date are treated as silently reissued (documented simplification)
        expired = status == "Expired"
        blocked = status == "Blocked"
        forced = expired | blocked
        declined = declined | forced

        w = np.tile(np.array([DECLINE_REASON_WEIGHTS[r] for r in DECLINE_REASONS]), (n, 1))
        w[:, DECLINE_REASONS.index("INCORRECT_SECURITY_INFO")] *= cnp
        w[:, DECLINE_REASONS.index("SUSPECTED_FRAUD")] *= np.where(fraud > 0, 8.0, 1.0)
        w = w + 1e-9
        reason_idx = _choice_matrix(rng, w)
        reason = np.array(DECLINE_REASONS, dtype=object)[reason_idx]
        reason[expired] = "EXPIRED_CARD"
        reason[blocked & ~expired] = "RESTRICTED_TRANSACTION"
        reason = np.where(declined, reason, "")

        ms = rng.lognormal(np.log(350), 0.45, n)
        ms = np.where(reason == "PROCESSING_TIMEOUT", 8000 + rng.uniform(0, 4000, n), ms)
        ms = np.where(reason == "ISSUER_UNAVAILABLE", ms * 3, ms)
        return declined, reason, np.round(ms).astype(int)

    def _lifecycle(self, rng, t: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        cfg = self.cfg
        n = len(t)
        declined, reason, ms = self._decline_model(rng, t)
        auth_ts = t["authorization_ts"].to_numpy().astype("datetime64[s]")
        pay = t["payment_id"].to_numpy()
        amt = t["amount"].to_numpy()
        ccy = t["currency"].to_numpy()
        approved = ~declined
        fraud = t["synthetic_fraud_pattern"].to_numpy()
        cnp = t["channel"].isin(CARD_NOT_PRESENT_CHANNELS).to_numpy()

        ev: list[pd.DataFrame] = []

        def add(mask, etype, ts, amount, status="", reason_="", ms_=None):
            k = int(mask.sum())
            if k == 0:
                return
            ev.append(pd.DataFrame({
                "payment_id": pay[mask], "event_type": etype, "event_ts": ts[mask] if len(ts) == n else ts,
                "amount": amount[mask] if len(amount) == n else amount, "currency": ccy[mask],
                "event_status": status if isinstance(status, str) else status[mask],
                "reason_code": reason_ if isinstance(reason_, str) else reason_[mask],
                "response_ms": 0 if ms_ is None else ms_[mask], "is_synthetic": True,
            }))

        allm = np.ones(n, dtype=bool)
        add(allm, "AUTH_REQUEST", auth_ts, amt, "REQUESTED")
        resp_ts = auth_ts + ms.astype("timedelta64[ms]").astype("timedelta64[s]")
        add(allm, "AUTH_RESPONSE", resp_ts, amt, np.where(declined, "DECLINED", "APPROVED"), reason, ms)

        # reversal of approved auths before clearing
        reversed_ = approved & (rng.random(n) < cfg.reversal_rate)
        rev_ts = auth_ts + rng.integers(3600, 48 * 3600, n).astype("timedelta64[s]")
        add(reversed_, "REVERSAL", rev_ts, amt, "REVERSED")

        cleared = approved & ~reversed_ & (rng.random(n) < cfg.clearing_rate)
        clr_ts = auth_ts + rng.integers(0, 2 * 86400, n).astype("timedelta64[s]")
        add(cleared, "CLEARING", clr_ts, amt, "CLEARED")

        # ---- settlements (clean expected first, then inject exceptions)
        rate = self.fx_rate(ccy, clr_ts)
        exp_amt = np.round(amt * rate, 2)
        stl_ts = clr_ts + rng.integers(86400, 2 * 86400, n).astype("timedelta64[s]")
        iss = cfg.issues
        u = rng.random(n)
        edges = np.cumsum([iss.missing, iss.duplicate, iss.amount_mismatch, iss.currency_mismatch, iss.late])
        issue = np.full(n, "", dtype=object)
        for name, lo, hi in zip(["MISSING", "DUPLICATE", "AMOUNT_MISMATCH", "CURRENCY_MISMATCH", "LATE"],
                                np.concatenate([[0], edges[:-1]]), edges):
            issue[cleared & (u >= lo) & (u < hi)] = name

        s_amt = exp_amt.copy()
        s_ccy = np.full(n, SETTLEMENT_CURRENCY, dtype=object)
        mm = issue == "AMOUNT_MISMATCH"
        s_amt[mm] = np.round(exp_amt[mm] * rng.choice([0.98, 0.95, 1.03, 0.9], mm.sum()) + rng.choice([-1.5, 2.0], mm.sum()), 2)
        cm = issue == "CURRENCY_MISMATCH"
        s_ccy[cm] = rng.choice(["EUR", "GBP"], cm.sum())
        lt = issue == "LATE"
        stl_ts = np.where(lt, clr_ts + rng.integers(5 * 86400, 10 * 86400, n).astype("timedelta64[s]"), stl_ts)

        has_stl = cleared & (issue != "MISSING")
        stl = pd.DataFrame({
            "payment_id": pay[has_stl], "settlement_ts": stl_ts[has_stl],
            "settlement_amount": s_amt[has_stl], "settlement_currency": s_ccy[has_stl],
        })
        dup = (issue == "DUPLICATE")
        if dup.any():
            d = pd.DataFrame({
                "payment_id": pay[dup], "settlement_ts": stl_ts[dup] + np.timedelta64(3600, "s"),
                "settlement_amount": s_amt[dup], "settlement_currency": s_ccy[dup],
            })
            stl = pd.concat([stl, d], ignore_index=True)
        n_orph = int(cleared.sum() * iss.orphan)
        if n_orph:
            o = pd.DataFrame({
                "payment_id": [f"PAY-ORPHAN-{self._stl_counter + i:08d}" for i in range(n_orph)],
                "settlement_ts": clr_ts[cleared][:n_orph] + np.timedelta64(86400, "s"),
                "settlement_amount": np.round(rng.uniform(5, 500, n_orph), 2),
                "settlement_currency": SETTLEMENT_CURRENCY,
            })
            stl = pd.concat([stl, o], ignore_index=True)
        stl["settlement_id"] = self._next_ids("STL", "_stl_counter", len(stl), 10)
        stl["batch_id"] = "SB-" + pd.to_datetime(stl["settlement_ts"]).dt.strftime("%Y%m%d")
        stl["is_synthetic"] = True
        stl = stl[["settlement_id", "payment_id", "batch_id", "settlement_ts",
                   "settlement_amount", "settlement_currency", "is_synthetic"]]

        # settlement lifecycle events mirror the actual settlement records
        se = pd.DataFrame({
            "payment_id": stl["payment_id"], "event_type": "SETTLEMENT", "event_ts": stl["settlement_ts"],
            "amount": stl["settlement_amount"], "currency": stl["settlement_currency"],
            "event_status": "SETTLED", "reason_code": "", "response_ms": 0, "is_synthetic": True,
        })
        se = se[~se["payment_id"].str.startswith("PAY-ORPHAN")]
        ev.append(se)

        truth = pd.DataFrame({"payment_id": pay[issue != ""], "injected_issue": issue[issue != ""]})
        if n_orph:
            truth = pd.concat([truth, pd.DataFrame({
                "payment_id": o["payment_id"], "injected_issue": "ORPHAN"})], ignore_index=True)

        # ---- refunds and chargebacks on settled payments
        settled = has_stl
        ref_m = settled & (rng.random(n) < cfg.refund_rate)
        ref_ts = stl_ts + rng.integers(1 * 86400, 20 * 86400, n).astype("timedelta64[s]")
        ref_amt = np.round(amt * np.where(rng.random(n) < 0.7, 1.0, rng.uniform(0.2, 0.9, n)), 2)
        add(ref_m, "REFUND", ref_ts, ref_amt, "REFUNDED")
        p_cb = cfg.chargeback_rate * np.where(fraud, 8.0, 1.0) * np.where(cnp, 2.0, 1.0)
        cb_m = settled & (rng.random(n) < p_cb)
        cb_ts = stl_ts + rng.integers(10 * 86400, 90 * 86400, n).astype("timedelta64[s]")
        cb_reason = np.where(fraud | (rng.random(n) < 0.4), "FRAUD",
                             rng.choice(CHARGEBACK_REASONS[1:], n)).astype(object)
        add(cb_m, "CHARGEBACK", cb_ts, amt, "CHARGEBACK", cb_reason)

        events = pd.concat(ev, ignore_index=True)
        events.insert(0, "event_id", self._next_ids("EVT", "_evt_counter", len(events), 11))
        return events, stl, truth, t

    # ------------------------------------------------------------- public
    def iter_chunks(self) -> Iterator[Chunk]:
        cfg = self.cfg
        n_rec = int(cfg.num_payments * cfg.recurring_share)
        n_rand = cfg.num_payments - n_rec
        idx = 0
        # random stream in chunks
        remaining = n_rand
        while remaining > 0:
            k = min(cfg.chunk_size, remaining)
            rng = np.random.default_rng([cfg.seed, 2, idx])
            yield self._finish(rng, self._random_stream(rng, k))
            remaining -= k
            idx += 1
        rng = np.random.default_rng([cfg.seed, 3, 0])
        rec = self._recurring_stream(rng, n_rec)
        if len(rec):
            yield self._finish(rng, rec)
        rng = np.random.default_rng([cfg.seed, 4, 0])
        fb = self._fraud_burst_stream(rng)
        if len(fb):
            yield self._finish(rng, fb)

    def _finish(self, rng, t: pd.DataFrame) -> Chunk:
        events, stl, truth, t = self._lifecycle(rng, t)
        return Chunk(transactions=t, events=events, settlements=stl, truth=truth)

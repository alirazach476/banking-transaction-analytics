"""Real-vs-synthetic benchmarks: REAL Pakistani payment aggregates (SBP) next to the dashboard's synthetic card payments and the
calibrated companion dataset (scripts/calibrate_payments.py). Nothing here is joined across domains; it compares summary metrics only."""
from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter

from .common import cached, q

router = APIRouter(prefix="/benchmarks", tags=["benchmarks"])
ROOT = Path(__file__).resolve().parents[3]


def _load(rel: str):
    p = ROOT / rel
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def dashboard_metrics() -> dict:
    """Same definitions as scripts/calibrate_payments.metrics_from_frame, computed on the dashboard's own data
    (non-recurring, non-injected-fraud payments, 2023-2025)."""
    rows = q("""SELECT channel, EXTRACT(year FROM payment_date)::int AS yr, count(*) AS n, avg(amount_usd) AS mean_usd, avg(coalesce(declined, false)::int) AS decline
                FROM ui.payments_usd WHERE channel NOT IN ('Recurring', 'Unknown') AND NOT coalesce(synthetic_fraud_label, false)
                GROUP BY 1, 2""")
    tot = sum(r["n"] for r in rows)
    by = {}
    for r in rows:
        d = by.setdefault(r["channel"], {"n": 0, "usd_sum": 0.0, "usd_n": 0, "dec": 0.0})
        d["n"] += r["n"]
        d["dec"] += (r["decline"] or 0) * r["n"]
    ch_mean = {r["channel"]: None for r in rows}
    means = q("""SELECT channel, avg(amount_usd) AS m, count(amount_usd) AS k FROM ui.payments_usd
                 WHERE channel NOT IN ('Recurring', 'Unknown') AND NOT coalesce(synthetic_fraud_label, false) GROUP BY 1""")
    for r in means:
        ch_mean[r["channel"]] = (float(r["m"]), int(r["k"]))
    card = ["POS Chip", "POS Contactless", "E-commerce"]
    n_card = sum(by.get(c, {"n": 0})["n"] for c in card)
    pos_k = sum(ch_mean[c][1] for c in card[:2] if ch_mean.get(c))
    pos_mean = sum(ch_mean[c][0] * ch_mean[c][1] for c in card[:2] if ch_mean.get(c)) / pos_k if pos_k else None
    yearly = {}
    for r in rows:
        if r["channel"] in card:
            yearly[r["yr"]] = yearly.get(r["yr"], 0) + r["n"]
    growth = (yearly[2025] / yearly[2024] - 1) if yearly.get(2024) and yearly.get(2025) else None
    return {
        "payments": tot, "decline_rate": sum(d["dec"] for d in by.values()) / tot if tot else None,
        "cnp_share": by.get("E-commerce", {"n": 0})["n"] / n_card if n_card else None, "annual_volume_growth": growth,
        "avg_ticket_usd": {"pos": pos_mean, "e_commerce": ch_mean["E-commerce"][0] if ch_mean.get("E-commerce") else None, "wallet": ch_mean["Mobile Wallet"][0] if ch_mean.get("Mobile Wallet") else None},
    }


def _status(real, val):
    if real is None:
        return "no real target"
    if val is None:
        return "n/a"
    gap = abs(val - real) / abs(real)
    return "matches" if gap <= 0.10 else "off" if gap <= 0.50 else "far off"


@router.get("")
@cached(ttl=300)
def benchmarks():
    cal = _load("config/pakistan_calibration.json")
    res = _load("docs/_parts/calibration_results.json")
    c2 = _load("docs/_parts/part_c2.json")
    dash = dashboard_metrics()
    real = cal["real_targets"] if cal else None
    calib = res["calibrated_generated"] if res else None

    def get(m, key):
        if m is None:
            return None
        if key.startswith("avg_ticket_usd."):
            return m["avg_ticket_usd"].get(key.split(".")[1])
        return m.get(key)

    spec = [("cnp_share", "Card-not-present share of card payments", "ratio", "E-commerce (CNP) / (POS card-present + E-commerce), by transaction count"),
            ("annual_volume_growth", "Annual growth of card payment volume", "ratio", "Real: volume-weighted year-on-year growth of POS and e-commerce, Q3 FY26. Synthetic: 2025 vs 2024"),
            ("avg_ticket_usd.pos", "Average ticket, POS (USD)", "usd", "SBP average ticket in rupees / USD-PKR"),
            ("avg_ticket_usd.e_commerce", "Average ticket, e-commerce (USD)", "usd", "SBP average ticket in rupees / USD-PKR"),
            ("avg_ticket_usd.wallet", "Average ticket, mobile wallet (USD)", "usd", "Synthetic wallet is a tokenised card wallet; real counterpart is SBP wallet apps and e-money wallets (ticket size only)"),
            ("decline_rate", "Card decline rate", "ratio", "No real target: SBP publishes no card decline rate. Shown to expose the side effect of calibration")]
    rows = []
    for key, label, unit, how in spec:
        r_, d_, c_ = get(real, key) if real else None, get(dash, key), get(calib, key)
        rows.append({"key": key, "label": label, "unit": unit, "how": how, "real": r_, "dashboard": d_, "calibrated": c_,
                     "gap_dashboard": (d_ - r_) / abs(r_) if r_ and d_ is not None else None, "gap_calibrated": (c_ - r_) / abs(r_) if r_ and c_ is not None else None,
                     "status_dashboard": _status(r_, d_), "status_calibrated": _status(r_, c_) if calib else "not generated"})
    channels = []
    if c2:
        for name, v in c2["channels_latest"].items():
            channels.append({"channel": name, "volume_m": v["vol_last"], "share_pct": v["share_of_volume_pct"], "yoy_pct": v["vol_yoy_pct"], "avg_ticket_rs": v["avg_ticket_rs"]})
        channels.sort(key=lambda r: -r["volume_m"])
    return {
        "real": {"period": real["period"] if real else None, "usd_pkr": real["usd_pkr"] if real else None, "source": "SBP Payment Systems Review (real, aggregate)"},
        "scorecard": rows, "real_channels": channels,
        "calibrated_available": calib is not None, "calibrated_payments": res["n_payments_requested"] if res else None,
        "parameters": res["parameters"] if res else None,
        "assumptions": cal["assumptions"] if cal else [], "not_calibrated": cal["not_calibrated"] if cal else [],
        "note": ("The dashboard's transactions are the original synthetic dataset (not calibrated). The calibrated column is a companion dataset generated with the same generator "
                 "after calibration; it is not loaded into the database. Calibrated metrics match their real targets largely by construction: that shows the calibration works, "
                 "not that the data is realistic. Metrics without a real target are not calibrated."),
    }

"""Calibrate the synthetic payment generator to REAL Pakistani payment aggregates and measure the effect.

Real inputs (read-only): docs/_parts/part_c2.json (SBP quarterly Payment Systems Reviews, Q3 FY26 channel table) and
docs/_parts/part_b.json (BIS USD/PKR monthly average, used to convert rupee tickets to dollars).

What is calibrated (each has a real target):
  1. card-not-present share of card-based payments  = E-commerce (CNP) / (POS card-present + E-commerce)
  2. annual growth of card-based payment volume      = volume-weighted year-on-year growth of POS (CP) and E-commerce (CNP)
  3. average ticket size per channel in USD          = SBP average ticket (rupees) / USD-PKR
What is NOT calibrated (no real target in the data) is listed in `not_calibrated` of the output.

Outputs:
  config/pakistan_calibration.json   parameters + provenance, read by PaymentGenConfig (env PAYMENT_CALIBRATION)
  docs/_parts/calibration_results.json   measured metrics: real target, baseline generator, calibrated generator

Run: PYTHONPATH=. python scripts/calibrate_payments.py [--n 150000]
All generated data is synthetic.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from src.payments.config import Calibration, PaymentGenConfig
from src.payments.constants import CHANNELS
from src.payments.generator import PaymentGenerator

ROOT = Path(__file__).resolve().parent.parent
POS = ["POS Chip", "POS Contactless"]
CARD_CHANNELS = POS + ["E-commerce"]


def real_targets() -> dict:
    c2 = json.loads((ROOT / "docs/_parts/part_c2.json").read_text(encoding="utf-8"))
    b = json.loads((ROOT / "docs/_parts/part_b.json").read_text(encoding="utf-8"))
    ch = c2["channels_latest"]
    pos, ecom = ch["POS (CP)"], ch["E-Commerce (CNP)"]
    wal = [ch["Branchless/Digital Banking Apps"], ch["E-Money Wallets"]]
    fx = float(b["bis_usdpkr_sep26_avg"])
    cnp_share = ecom["vol_last"] / (pos["vol_last"] + ecom["vol_last"])
    growth = (pos["vol_last"] * pos["vol_yoy_pct"] + ecom["vol_last"] * ecom["vol_yoy_pct"]) / (pos["vol_last"] + ecom["vol_last"]) / 100
    wal_ticket = sum(w["vol_last"] * w["avg_ticket_rs"] for w in wal) / sum(w["vol_last"] for w in wal)
    return {
        "period": "Q3 FY26 (Jan-Mar 2026), SBP Payment Systems Review; yoy vs Q3 FY25",
        "usd_pkr": fx, "usd_pkr_source": "BIS monthly average Sep-2026 (the rupee moved about 2.5% over 2 years, so the choice of month matters little)",
        "cnp_share": cnp_share, "annual_volume_growth": growth,
        "avg_ticket_usd": {"pos": pos["avg_ticket_rs"] / fx, "e_commerce": ecom["avg_ticket_rs"] / fx, "wallet": wal_ticket / fx},
        "avg_ticket_rs": {"pos": pos["avg_ticket_rs"], "e_commerce": ecom["avg_ticket_rs"], "wallet": wal_ticket},
        "volume_million": {"pos": pos["vol_last"], "e_commerce": ecom["vol_last"]},
        "volume_yoy_pct": {"pos": pos["vol_yoy_pct"], "e_commerce": ecom["vol_yoy_pct"]},
    }


def generate_frame(cfg: PaymentGenConfig) -> pd.DataFrame:
    gen = PaymentGenerator(cfg)
    frames = []
    for chunk in gen.iter_chunks():
        t = chunk.transactions[["payment_id", "channel", "amount", "currency", "authorization_ts", "synthetic_fraud_pattern"]].copy()
        t["usd"] = t["amount"].to_numpy() * gen.fx_rate(t["currency"].to_numpy(), t["authorization_ts"].to_numpy())
        resp = chunk.events[chunk.events["event_type"] == "AUTH_RESPONSE"].drop_duplicates("payment_id").set_index("payment_id")["event_status"]
        t["declined"] = t["payment_id"].map(resp).astype(str).str.upper().str.startswith("DECL")
        frames.append(t)
    return pd.concat(frames, ignore_index=True)


def measure(cfg: PaymentGenConfig) -> dict:
    return metrics_from_frame(generate_frame(cfg))


def metrics_from_frame(t: pd.DataFrame) -> dict:
    """Same definition is used by the API for the dashboard's own data: non-recurring, non-injected-fraud payments."""
    t = t[(t["channel"] != "Recurring") & (~t["synthetic_fraud_pattern"].astype(bool))]
    yr = pd.to_datetime(t["authorization_ts"]).dt.year
    card = t[t["channel"].isin(CARD_CHANNELS)]
    n = card["channel"].value_counts()
    cnp = n.get("E-commerce", 0) / max(n.sum(), 1)
    yc = card.groupby(yr[card.index]).size()
    growth = float(yc.get(2025, np.nan) / yc.get(2024, np.nan) - 1)
    mean = t.groupby("channel")["usd"].mean()
    pos = card[card["channel"].isin(POS)]["usd"].mean()
    return {
        "payments": int(len(t)), "decline_rate": float(t["declined"].mean()), "cnp_share": float(cnp), "annual_volume_growth": growth,
        "avg_ticket_usd": {"pos": float(pos), "e_commerce": float(mean.get("E-commerce", np.nan)), "wallet": float(mean.get("Mobile Wallet", np.nan))},
        "channel_mix": {k: float(v) for k, v in (t["channel"].value_counts(normalize=True)).items()},
    }


def build(n: int) -> None:
    tg = real_targets()
    base_cfg = PaymentGenConfig(num_payments=n)
    print(f"baseline generation ({n:,} payments)...")
    base = measure(base_cfg)

    # channel weights: wallet keeps its generator weight (its real counterpart is dominated by person-to-person transfers,
    # not merchant card payments); the remaining weight is split by the REAL POS : e-commerce ratio, chip : contactless as in the generator
    from src.payments.constants import CHANNEL_WEIGHTS
    w0 = dict(zip(CHANNELS, CHANNEL_WEIGHTS))
    card_total = w0["POS Chip"] + w0["POS Contactless"] + w0["E-commerce"]
    pos_total = card_total * (1 - tg["cnp_share"])
    weights = {"POS Chip": pos_total * w0["POS Chip"] / (w0["POS Chip"] + w0["POS Contactless"]),
               "POS Contactless": pos_total * w0["POS Contactless"] / (w0["POS Chip"] + w0["POS Contactless"]),
               "E-commerce": card_total * tg["cnp_share"], "Mobile Wallet": w0["Mobile Wallet"]}
    # amount scale per channel from the baseline's own measured means (per channel, so POS chip and contactless both hit the POS target)
    bt = generate_frame(base_cfg)
    bt = bt[(bt["channel"] != "Recurring") & (~bt["synthetic_fraud_pattern"].astype(bool))]
    mean_by = bt.groupby("channel")["usd"].mean().to_dict()
    target_by = {"POS Chip": tg["avg_ticket_usd"]["pos"], "POS Contactless": tg["avg_ticket_usd"]["pos"],
                 "E-commerce": tg["avg_ticket_usd"]["e_commerce"], "Mobile Wallet": tg["avg_ticket_usd"]["wallet"]}
    scale = {c: float(target_by[c] / mean_by[c]) for c in target_by}

    params = {"channel_weights": weights, "annual_volume_growth": tg["annual_volume_growth"], "amount_scale": scale}
    cal_cfg = PaymentGenConfig(num_payments=n, calibration=Calibration(**params, source="scripts/calibrate_payments.py"))
    print("calibrated generation...")
    cal = measure(cal_cfg)

    out = {
        "description": "Parameters that calibrate the synthetic card-payment generator to real SBP aggregates. Data stays synthetic.",
        "generated_by": "scripts/calibrate_payments.py",
        "real_targets": tg,
        "parameters": params,
        "assumptions": [
            "Card-based payments are mapped to SBP's POS (card present) and E-commerce (CNP) channels; the generator's Mobile Wallet is mapped to SBP wallet channels for ticket size only.",
            "The chip : contactless split inside POS is not published by SBP; the generator's own 25 : 30 ratio is kept.",
            "Real Q3 FY26 growth is applied as a constant compound rate over the generator's 2023-2025 calendar: it matches the pace of growth, not the calendar years.",
            "Rupee tickets are converted at one exchange rate (BIS Sep-2026 average).",
        ],
        "not_calibrated": [
            "Decline / approval rate (SBP reports no card decline rate)",
            "Fraud and anomaly rates (only euro-area card fraud is published, and it is not Pakistani)",
            "Wallet channel share (real wallet volume is mostly person-to-person transfers, not merchant card payments)",
            "Merchant country mix, currency mix and card-holder profiles (no real counterpart in the files)",
            "Merchant-category mix and spending by category (SBP publishes channel totals only)",
            "Time-of-day and day-of-week patterns, seasonality",
        ],
    }
    (ROOT / "config/pakistan_calibration.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    res = {"n_payments_requested": n, "seed": base_cfg.seed, "real": {k: tg[k] for k in ("cnp_share", "annual_volume_growth", "avg_ticket_usd")},
           "baseline_generated": base, "calibrated_generated": cal, "parameters": params}
    (ROOT / "docs/_parts/calibration_results.json").write_text(json.dumps(res, indent=2), encoding="utf-8")
    show = lambda m: f"decline {m['decline_rate']:.4f} cnp {m['cnp_share']:.3f} growth {m['annual_volume_growth']:+.3f} ticket pos {m['avg_ticket_usd']['pos']:.2f} ecom {m['avg_ticket_usd']['e_commerce']:.2f} wallet {m['avg_ticket_usd']['wallet']:.2f}"
    print("real      ", f"cnp {tg['cnp_share']:.3f} growth {tg['annual_volume_growth']:+.3f} ticket pos {tg['avg_ticket_usd']['pos']:.2f} ecom {tg['avg_ticket_usd']['e_commerce']:.2f} wallet {tg['avg_ticket_usd']['wallet']:.2f}")
    print("baseline  ", show(base))
    print("calibrated", show(cal))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150_000)
    build(ap.parse_args().n)

"""Calibration of the synthetic payment generator to real SBP aggregates. No database needed; all generated data is synthetic."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from scripts.calibrate_payments import generate_frame, metrics_from_frame, real_targets
from src.payments.config import Calibration, PaymentGenConfig
from src.payments.generator import PaymentGenerator

ROOT = Path(__file__).resolve().parent.parent
CAL_FILE = ROOT / "config" / "pakistan_calibration.json"
needs_file = pytest.mark.skipif(not CAL_FILE.exists(), reason="run scripts/calibrate_payments.py first")


def small(**kw) -> PaymentGenConfig:
    return PaymentGenConfig(num_payments=kw.pop("n", 6000), num_cards=800, num_merchants=150, num_customers=400, num_accounts=600, chunk_size=4000, **kw)


def digest(cfg) -> str:
    t = pd.concat([c.transactions for c in PaymentGenerator(cfg).iter_chunks()])
    return hashlib.md5(pd.util.hash_pandas_object(t[["payment_id", "amount", "channel", "authorization_ts"]], index=False).values.tobytes()).hexdigest()


def test_no_calibration_is_the_default():
    assert PaymentGenConfig().calibration is None


def test_empty_calibration_reproduces_the_baseline_exactly():
    # a Calibration with every field None must not change a single value (the validated baseline stays reproducible)
    assert digest(small()) == digest(small(calibration=Calibration()))


@needs_file
def test_calibration_file_targets_are_the_real_data_values():
    d = json.loads(CAL_FILE.read_text(encoding="utf-8"))
    tg = real_targets()
    assert d["real_targets"]["cnp_share"] == pytest.approx(tg["cnp_share"])
    assert d["real_targets"]["annual_volume_growth"] == pytest.approx(tg["annual_volume_growth"])
    assert d["real_targets"]["avg_ticket_usd"]["pos"] == pytest.approx(tg["avg_ticket_usd"]["pos"])
    # the real inputs themselves: POS and e-commerce volumes from the SBP table
    assert tg["cnp_share"] == pytest.approx(16.4 / (143.2 + 16.4), rel=1e-3)
    assert d["not_calibrated"] and d["assumptions"]


@needs_file
def test_calibrated_generation_hits_the_real_targets():
    cal = Calibration.from_json(CAL_FILE)
    tg = real_targets()
    m = metrics_from_frame(generate_frame(small(n=60000, calibration=cal)))
    assert m["cnp_share"] == pytest.approx(tg["cnp_share"], abs=0.02)
    assert m["avg_ticket_usd"]["pos"] == pytest.approx(tg["avg_ticket_usd"]["pos"], rel=0.15)
    assert m["avg_ticket_usd"]["e_commerce"] == pytest.approx(tg["avg_ticket_usd"]["e_commerce"], rel=0.25)  # ~10% of rows: noisier
    assert m["annual_volume_growth"] == pytest.approx(tg["annual_volume_growth"], abs=0.12)
    # and the uncalibrated generator is far from them (otherwise the calibration would be meaningless)
    b = metrics_from_frame(generate_frame(small(n=60000)))
    assert b["cnp_share"] > 0.25 and b["avg_ticket_usd"]["pos"] > 100 and b["annual_volume_growth"] < 0.10


def test_amount_scale_changes_only_the_named_channel():
    base = generate_frame(small()).set_index("payment_id")
    scaled = generate_frame(small(calibration=Calibration(amount_scale={"E-commerce": 0.5}))).set_index("payment_id")
    j = base.join(scaled, rsuffix="_s")
    other = j[(j.channel != "E-commerce") & (j.channel != "Recurring")]
    assert np.allclose(other.usd, other.usd_s, rtol=1e-4)
    ec = j[(j.channel == "E-commerce") & (j.usd > 4)]
    assert len(ec) > 50
    assert np.allclose(ec.usd_s / ec.usd, 0.5, rtol=0.02)


def test_calibrated_channel_weights_are_normalised_and_respected():
    cal = Calibration(channel_weights={"POS Chip": 1.0, "POS Contactless": 1.0, "E-commerce": 0.0, "Mobile Wallet": 0.0})
    t = pd.concat([c.transactions for c in PaymentGenerator(small(calibration=cal)).iter_chunks()])
    mix = t[~t.synthetic_fraud_pattern & (t.channel != "Recurring")].channel.value_counts(normalize=True)
    assert set(mix.index) <= {"POS Chip", "POS Contactless"}
    assert mix.get("POS Chip", 0) == pytest.approx(0.5, abs=0.05)

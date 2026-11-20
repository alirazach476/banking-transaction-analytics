"""Chunked CSV writer + CLI for the payment-lifecycle dataset."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from config.settings import get_settings
from src.payments.config import DefectRates, PaymentGenConfig
from src.payments.defects import inject_defects
from src.payments.generator import TS_FMT, Chunk, PaymentGenerator
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)


def _fmt(df: pd.DataFrame, cols: list[str]) -> pd.DataFrame:
    df = df.copy()
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c]).dt.strftime(TS_FMT)
    return df


def _clean_txn(t: pd.DataFrame) -> pd.DataFrame:
    t = _fmt(t, ["authorization_ts"])
    t["card_expiry_date"] = pd.to_datetime(t["card_expiry_date"]).dt.strftime("%Y-%m-%d")
    return t


def dirty_views(chunk: Chunk, cfg: PaymentGenConfig, rng: np.random.Generator):
    """Dirty transactions/events feeds (the clean frames are not modified)."""
    r = cfg.defects
    t = inject_defects(
        chunk.transactions, r, rng, fk_cols=["merchant_id"],
        ts_cols=["authorization_ts"], currency_cols=["currency"],
        nullable_cols=["merchant_category", "channel"], case_cols=["channel"],
    )
    t["card_expiry_date"] = pd.to_datetime(t["card_expiry_date"]).dt.strftime("%Y-%m-%d")
    e = inject_defects(
        chunk.events, r, rng, status_col="event_status", fk_cols=["payment_id"],
        ts_cols=["event_ts"], currency_cols=["currency"], nullable_cols=["reason_code"],
    )
    return t, e


def generate_to_disk(cfg: PaymentGenConfig, out_dir: Path, clean_dir: Path,
                     existing_dir: Path | None = None) -> dict:
    """Generate in chunks and append to CSVs; never holds the full dataset in memory."""
    out_dir.mkdir(parents=True, exist_ok=True)
    clean_dir.mkdir(parents=True, exist_ok=True)
    for p in list(out_dir.glob("*.csv")) + list(clean_dir.glob("*.csv")):
        p.unlink()
    gen = PaymentGenerator(cfg, existing_dir=existing_dir)
    t0 = time.perf_counter()
    counts = {"transactions": 0, "events": 0, "settlements": 0, "injected_settlement_issues": 0,
              "dirty_transactions": 0, "dirty_events": 0}
    defect_counts: dict[str, int] = {}
    first: dict[str, bool] = {}

    def append(df: pd.DataFrame, path: Path) -> None:
        df.to_csv(path, mode="a", header=first.get(str(path), True), index=False)
        first[str(path)] = False

    for i, ch in enumerate(gen.iter_chunks()):
        rng = np.random.default_rng([cfg.seed, 7, i])
        dt, de = dirty_views(ch, cfg, rng)
        t_clean = _clean_txn(ch.transactions)
        e_clean = _fmt(ch.events, ["event_ts"])
        s_clean = _fmt(ch.settlements, ["settlement_ts"])
        append(t_clean, clean_dir / "payment_transactions.csv")
        append(e_clean, clean_dir / "payment_lifecycle_events.csv")
        append(ch.truth, clean_dir / "settlement_injected_truth.csv")
        append(s_clean, out_dir / "payment_settlements.csv")
        append(dt, out_dir / "payment_transactions.csv")
        append(de, out_dir / "payment_lifecycle_events.csv")
        counts["transactions"] += len(t_clean)
        counts["events"] += len(e_clean)
        counts["settlements"] += len(s_clean)
        counts["injected_settlement_issues"] += len(ch.truth)
        counts["dirty_transactions"] += len(dt)
        counts["dirty_events"] += len(de)
        for frame in (dt, de):
            labs = frame.loc[frame["dq_defect"] != "", "dq_defect"].str.split(";").explode().value_counts()
            for lab, c in labs.items():
                defect_counts[lab] = defect_counts.get(lab, 0) + int(c)
        logger.info("chunk %d: %s payments, %s events", i, f"{len(t_clean):,}", f"{len(e_clean):,}")
    gen.fx.to_csv(out_dir / "fx_rates_synthetic.csv", index=False)
    elapsed = time.perf_counter() - t0
    manifest = {
        "note": "SYNTHETIC DATA ONLY - not real payment records",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "elapsed_seconds": round(elapsed, 2),
        "config": cfg.to_dict(),
        "row_counts": counts,
        "injected_dq_defects": defect_counts,
        "clean_dir": str(clean_dir),
        "dirty_dir": str(out_dir),
    }
    (out_dir / "payments_manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> dict:
    ap = argparse.ArgumentParser(description="Generate synthetic payment lifecycle data")
    ap.add_argument("--payments", type=int, default=None)
    ap.add_argument("--chunk-size", type=int, default=None)
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--no-defects", action="store_true")
    ap.add_argument("--no-existing-refs", action="store_true")
    a = ap.parse_args(argv)
    cfg = PaymentGenConfig.from_env()
    if a.payments:
        cfg.num_payments = a.payments
    if a.chunk_size:
        cfg.chunk_size = a.chunk_size
    if a.seed is not None:
        cfg.seed = a.seed
    if a.no_defects:
        cfg.defects = DefectRates.none()
    s = get_settings()
    m = generate_to_disk(cfg, s.data_source_dir / "payments", s.data_processed_dir / "clean_reference" / "payments",
                         None if a.no_existing_refs else s.data_source_dir)
    logger.info(json.dumps(m["row_counts"]))
    return m


if __name__ == "__main__":
    main()

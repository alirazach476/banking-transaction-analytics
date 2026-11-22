"""Configuration for the payment-lifecycle generator."""

from __future__ import annotations

import os
from dataclasses import dataclass, field, asdict


@dataclass
class DefectRates:
    """Controlled data-quality defects injected ONLY into the dirty feed.

    Every affected row carries a label in the ``dq_defect`` column; clean copies
    are written separately. Rates are fractions of rows per table.
    """

    duplicate_record: float = 0.005
    missing_value: float = 0.004
    invalid_foreign_key: float = 0.002
    inconsistent_capitalization: float = 0.01
    invalid_timestamp: float = 0.002
    invalid_currency: float = 0.002
    incorrect_status: float = 0.004

    @classmethod
    def none(cls) -> "DefectRates":
        return cls(**{k: 0.0 for k in cls.__dataclass_fields__})


@dataclass
class SettlementIssueRates:
    """Business-process exceptions injected into settlements (ground truth kept)."""

    missing: float = 0.004
    duplicate: float = 0.003
    amount_mismatch: float = 0.003
    currency_mismatch: float = 0.0015
    late: float = 0.008
    orphan: float = 0.001  # settlements for payment ids that do not exist

    @classmethod
    def none(cls) -> "SettlementIssueRates":
        return cls(**{k: 0.0 for k in cls.__dataclass_fields__})


@dataclass
class Calibration:
    """Optional calibration of the generator to REAL published aggregates (see config/pakistan_calibration.json).

    Every field is optional; ``None`` keeps the generator's original behaviour, so a config without calibration
    reproduces the baseline dataset exactly. The data stays synthetic: only a few aggregate properties are matched.
    """

    channel_weights: dict | None = None      # replaces CHANNEL_WEIGHTS (channel name -> weight)
    annual_volume_growth: float | None = None  # compound growth per year of payment volume (0.42 = +42%/yr), replaces the linear trend
    amount_scale: dict | None = None         # channel -> multiplier on the USD-equivalent amount
    source: str = ""

    @classmethod
    def from_json(cls, path) -> "Calibration":
        import json
        with open(path, encoding="utf-8") as fh:
            d = json.load(fh)
        p = d.get("parameters", d)
        return cls(channel_weights=p.get("channel_weights"), annual_volume_growth=p.get("annual_volume_growth"),
                   amount_scale=p.get("amount_scale"), source=str(path))


@dataclass
class PaymentGenConfig:
    seed: int = 42
    num_payments: int = 100_000          # random-stream payment attempts
    num_cards: int = 10_000
    num_merchants: int = 1_000
    num_customers: int = 5_000
    num_accounts: int = 7_500
    start_date: str = "2023-01-01"
    end_date: str = "2025-12-31"
    chunk_size: int = 200_000
    recurring_share: float = 0.06        # share of payments that are recurring
    fraud_card_share: float = 0.004      # share of cards with a synthetic burst
    refund_rate: float = 0.03
    chargeback_rate: float = 0.004
    reversal_rate: float = 0.015
    clearing_rate: float = 0.985         # approved & not reversed that reach clearing
    settlement_sla_days: int = 3
    defects: DefectRates = field(default_factory=DefectRates)
    issues: SettlementIssueRates = field(default_factory=SettlementIssueRates)
    calibration: Calibration | None = None

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_env(cls) -> "PaymentGenConfig":
        g = os.getenv
        return cls(
            seed=int(g("RANDOM_SEED", "42")),
            num_payments=int(g("NUM_PAYMENTS", "100000")),
            num_cards=int(g("NUM_CARDS", "10000")),
            num_merchants=int(g("NUM_MERCHANTS", "1000")),
            num_customers=int(g("NUM_CUSTOMERS", "5000")),
            num_accounts=int(g("NUM_ACCOUNTS", "7500")),
            start_date=g("DATA_START_DATE", "2023-01-01"),
            end_date=g("DATA_END_DATE", "2025-12-31"),
            chunk_size=int(g("GEN_CHUNK_SIZE", "200000")),
            calibration=Calibration.from_json(g("PAYMENT_CALIBRATION")) if g("PAYMENT_CALIBRATION") else None,
        )

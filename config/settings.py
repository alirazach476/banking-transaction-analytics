"""Central configuration loaded from environment / .env."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


class DatabaseSettings(BaseModel):
    host: str = Field(default_factory=lambda: os.getenv("POSTGRES_HOST", "localhost"))
    port: int = Field(default_factory=lambda: int(os.getenv("POSTGRES_PORT", "5432")))
    db: str = Field(default_factory=lambda: os.getenv("POSTGRES_DB", "novabank"))
    user: str = Field(default_factory=lambda: os.getenv("POSTGRES_USER", "novabank"))
    password: str = Field(
        default_factory=lambda: os.getenv("POSTGRES_PASSWORD", "novabank_dev_password")
    )

    @property
    def sqlalchemy_url(self) -> str:
        return (
            f"postgresql+psycopg2://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.db}"
        )

    @property
    def psycopg2_dsn(self) -> str:
        return (
            f"host={self.host} port={self.port} dbname={self.db} "
            f"user={self.user} password={self.password}"
        )


class VolumeSettings(BaseModel):
    num_customers: int = Field(
        default_factory=lambda: int(os.getenv("NUM_CUSTOMERS", "5000"))
    )
    num_accounts: int = Field(
        default_factory=lambda: int(os.getenv("NUM_ACCOUNTS", "7500"))
    )
    num_transactions: int = Field(
        default_factory=lambda: int(os.getenv("NUM_TRANSACTIONS", "100000"))
    )
    num_branches: int = Field(
        default_factory=lambda: int(os.getenv("NUM_BRANCHES", "50"))
    )
    num_merchants: int = Field(
        default_factory=lambda: int(os.getenv("NUM_MERCHANTS", "1000"))
    )
    num_cards: int = Field(default_factory=lambda: int(os.getenv("NUM_CARDS", "10000")))
    num_transfers: int = Field(
        default_factory=lambda: int(os.getenv("NUM_TRANSFERS", "15000"))
    )
    num_atm_transactions: int = Field(
        default_factory=lambda: int(os.getenv("NUM_ATM_TRANSACTIONS", "20000"))
    )
    num_card_transactions: int = Field(
        default_factory=lambda: int(os.getenv("NUM_CARD_TRANSACTIONS", "40000"))
    )


class DataQualitySettings(BaseModel):
    duplicate_rate: float = Field(
        default_factory=lambda: float(os.getenv("DQ_DUPLICATE_RATE", "0.01"))
    )
    missing_rate: float = Field(
        default_factory=lambda: float(os.getenv("DQ_MISSING_RATE", "0.005"))
    )
    invalid_status_rate: float = Field(
        default_factory=lambda: float(os.getenv("DQ_INVALID_STATUS_RATE", "0.01"))
    )


class AnomalySettings(BaseModel):
    injection_rate: float = Field(
        default_factory=lambda: float(os.getenv("ANOMALY_INJECTION_RATE", "0.02"))
    )
    zscore_threshold: float = Field(
        default_factory=lambda: float(os.getenv("ANOMALY_ZSCORE_THRESHOLD", "3.0"))
    )
    high_amount_multiplier: float = Field(
        default_factory=lambda: float(os.getenv("ANOMALY_HIGH_AMOUNT_MULTIPLIER", "15.0"))
    )
    rapid_window_minutes: int = Field(
        default_factory=lambda: int(os.getenv("ANOMALY_RAPID_WINDOW_MINUTES", "10"))
    )
    rapid_count_threshold: int = Field(
        default_factory=lambda: int(os.getenv("ANOMALY_RAPID_COUNT_THRESHOLD", "5"))
    )
    isolation_forest_contamination: float = Field(
        default_factory=lambda: float(
            os.getenv("ISOLATION_FOREST_CONTAMINATION", "0.02")
        )
    )


class Settings(BaseModel):
    db: DatabaseSettings = Field(default_factory=DatabaseSettings)
    volumes: VolumeSettings = Field(default_factory=VolumeSettings)
    dq: DataQualitySettings = Field(default_factory=DataQualitySettings)
    anomaly: AnomalySettings = Field(default_factory=AnomalySettings)
    random_seed: int = Field(
        default_factory=lambda: int(os.getenv("RANDOM_SEED", "42"))
    )
    data_start_date: str = Field(
        default_factory=lambda: os.getenv("DATA_START_DATE", "2023-01-01")
    )
    data_end_date: str = Field(
        default_factory=lambda: os.getenv("DATA_END_DATE", "2025-12-31")
    )
    pipeline_mode: str = Field(
        default_factory=lambda: os.getenv("PIPELINE_MODE", "full")
    )
    project_root: Path = PROJECT_ROOT
    data_source_dir: Path = PROJECT_ROOT / "data" / "source"
    data_raw_dir: Path = PROJECT_ROOT / "data" / "raw"
    data_processed_dir: Path = PROJECT_ROOT / "data" / "processed"
    data_samples_dir: Path = PROJECT_ROOT / "data" / "samples"


@lru_cache
def get_settings() -> Settings:
    return Settings()

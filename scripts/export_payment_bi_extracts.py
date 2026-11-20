"""Phase 7: export BI-ready extracts (CSV + Parquet) of the payment marts for Tableau / Power BI / Excel,
and write a machine-generated data dictionary (docs/BI_EXTRACTS_DICTIONARY.md) from the actual exported columns.

Run: PYTHONPATH=. python scripts/export_payment_bi_extracts.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
from sqlalchemy import text

from src.utils.db import get_engine

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "bi"

EXTRACTS = {
    "payment_kpis_daily": ("Daily payment lifecycle KPIs (dbt mart_payment_kpis_daily). Grain: one row per payment date.",
                           "SELECT * FROM analytics.mart_payment_kpis_daily ORDER BY payment_date"),
    "decline_reasons_monthly": ("Declined payments and amount by month, channel and reason (dbt mart_decline_reasons).",
                                "SELECT * FROM analytics.mart_decline_reasons ORDER BY month, channel, decline_reason"),
    "settlement_daily": ("Settlement records per day with orphan and duplicate counts (dbt mart_settlement_daily).",
                         "SELECT * FROM analytics.mart_settlement_daily ORDER BY settlement_date"),
    "fx_monthly": ("External ECB FX reference rates by month (dbt external_analytics.mart_fx_monthly).",
                   "SELECT * FROM external_analytics.mart_fx_monthly ORDER BY base_currency, target_currency, month"),
    "reconciliation_queue": ("Investigation queue of settlement exceptions with status and priority.",
                             "SELECT payment_id, settlement_id, issue_type, amount_at_risk, currency, priority, status, first_detected_at, last_detected_at FROM payments.investigation_queue"),
    "reconciliation_runs": ("Reconciliation run summaries (counts per exception type, success rate, amount at risk).",
                            "SELECT * FROM payments.reconciliation_runs ORDER BY created_at"),
    "payment_outcomes": ("Per-payment lifecycle flags (dbt int_payment_outcomes); ~490K rows, use for drill-down.",
                         "SELECT * FROM intermediate.int_payment_outcomes"),
}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    e = get_engine()
    lines = ["# BI extracts data dictionary (generated)", "",
             "Synthetic data. Files in `data/processed/bi/` as CSV (UTF-8) and Parquet. Regenerate with `scripts/export_payment_bi_extracts.py`.", ""]
    for name, (desc, sql) in EXTRACTS.items():
        df = pd.read_sql(text(sql), e)
        for c in df.columns:  # Decimal -> float so Parquet/CSV types are plain
            if df[c].dtype == object and len(df) and df[c].dropna().map(lambda v: v.__class__.__name__ == "Decimal").all():
                df[c] = df[c].astype(float)
        df.to_csv(OUT / f"{name}.csv", index=False)
        df.to_parquet(OUT / f"{name}.parquet", index=False)
        lines += [f"## {name}  ({len(df):,} rows)", desc, "", "| column | type | nulls | example |", "|---|---|---|---|"]
        for c in df.columns:
            ex = df[c].dropna().iloc[0] if df[c].notna().any() else ""
            lines.append(f"| {c} | {df[c].dtype} | {int(df[c].isna().sum())} | {str(ex)[:40]} |")
        lines.append("")
        print(f"{name}: {len(df):,} rows")
    (ROOT / "docs" / "BI_EXTRACTS_DICTIONARY.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()

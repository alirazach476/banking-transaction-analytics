"""Export a Tableau extract (.hyper) containing (a) the synthetic NovaBank payment BI extracts and (b) the real-data tables from the all-in-one analysis.

Output: data/processed/tableau/novabank.hyper (schema "Extract"). Open in Tableau Desktop/Public via Connect > To a File > More... > the .hyper file.
This is an EXTRACT, not a workbook: no Tableau workbook (.twb/.twbx) is built here because Tableau is not available to build or verify one.
Tables prefixed synthetic_ come from the generator (not real); real_ from SBP, World Bank, BIS, ECB; mixed_ combines synthetic payments with real macro series.
Requires: pip install tableauhyperapi pandas pyarrow.   Run: python scripts/export_tableau_hyper.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
from tableauhyperapi import Connection, CreateMode, HyperProcess, Inserter, SqlType, TableDefinition, TableName, Telemetry

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed" / "tableau"
OUT.mkdir(parents=True, exist_ok=True)
PARTS = ROOT / "docs" / "_parts"
BI = ROOT / "data" / "processed" / "bi"
J = lambda n: json.load(open(PARTS / f"{n}.json"))

tables: dict[str, pd.DataFrame] = {}
for name in ("payment_kpis_daily", "decline_reasons_monthly", "settlement_daily", "reconciliation_runs", "reconciliation_queue", "payment_outcomes"):
    f = BI / f"{name}.parquet"
    if f.exists():
        tables[f"synthetic_{name}"] = pd.read_parquet(f)
if (BI / "fx_monthly.parquet").exists():  # built from real ECB/BIS exchange-rate data, not from the generator
    tables["real_ecb_fx_monthly"] = pd.read_parquet(BI / "fx_monthly.parquet")
if (BI / "macro_payments_monthly.csv").exists():
    tables["mixed_synthetic_payments_with_real_macro_monthly"] = pd.read_csv(BI / "macro_payments_monthly.csv")

c2, b, d, fg, a = J("part_c2"), J("part_b"), J("part_d"), J("part_fg"), J("part_a")
rows = []
for ch, v in c2["channels_latest"].items():
    rows.append({"channel": ch, "quarter": c2["window"][1], "volume_m": v["vol_last"], "value_bn": v["val_last_bn"]})
tables["real_sbp_retail_channels_latest"] = pd.DataFrame(rows)
tables["real_sbp_retail_totals_quarterly"] = pd.DataFrame({"quarter": list(c2["retail_volume_m"]), "volume_m": list(c2["retail_volume_m"].values()), "value_bn": list(c2["retail_value_bn"].values()),
                                                           "digital_share_volume_pct": [c2["digital_share_of_volume_pct"][q] for q in c2["retail_volume_m"]],
                                                           "digital_share_value_pct": [c2["digital_share_of_value_pct"][q] for q in c2["retail_volume_m"]]})
tables["real_sbp_raast_quarterly"] = pd.DataFrame([{"quarter": q, "volume_m": v[0], "value_bn": v[1]} for q, v in c2["raast_total"].items()])
tables["real_sbp_infrastructure_quarterly"] = pd.DataFrame([{"series": k, "quarter": q, "value": (v[0] if isinstance(v, list) else v)} for k, dd in c2["infrastructure"].items() for q, v in dd.items()])
tables["real_sbp_cards_quarterly"] = pd.DataFrame([{"card_type": k, "quarter": q, "cards": v} for k, dd in c2["cards"].items() for q, v in dd.items()])
tables["real_sbp_gdp_growth_fy"] = pd.DataFrame({"fiscal_year": list(b["gdp_growth_pct"]), "real_gdp_growth_pct": list(b["gdp_growth_pct"].values())})
tables["real_sbp_reserves_monthly"] = pd.DataFrame({"month": list(b["liquid_reserves_total_usd_m_monthly"]), "total_liquid_reserves_usd_m": list(b["liquid_reserves_total_usd_m_monthly"].values())})
tables["real_sbp_bop_fy25_fy26"] = pd.DataFrame([{"item": k, "fy25_usd_m": v[0], "fy26_usd_m": v[1]} for k, v in b["bop_fy25_fy26"].items()])
fsi = a["all_banks_fsi"]
tables["real_sbp_bank_fsi_all_banks"] = pd.DataFrame([{"indicator": k, "period": p, "value": x} for k, vals in fsi.items() if vals for p, x in zip(a["fsi_period_labels"][-len(vals):], vals)])
tables["real_sbp_sector_npl_sep26"] = pd.DataFrame([{"sector": k, **v} for k, v in a["sector_npl_sep26"].items()])
tables["real_wb_external_debt_composition"] = pd.DataFrame([{"component": k, "usd_bn": v, "share_pct": d["ids_composition_latest_share_pct"][k]} for k, v in d["ids_composition_latest_usd_bn"].items()])
tables["real_wb_remittance_cost_by_year"] = pd.DataFrame({"year": [int(y) for y in d["rpw_cost_pct_by_year_mean"]], "pakistan_mean_cost_pct": list(d["rpw_cost_pct_by_year_mean"].values()),
                                                          "all_corridors_mean_cost_pct": [d["rpw_world_mean_cost_by_year"].get(str(y)) for y in d["rpw_cost_pct_by_year_mean"]]})
tables["real_findex_peers_2024"] = pd.DataFrame([{"iso3": k, **v} for k, v in fg["peers_findex_2024_pct"].items()])
scr = ROOT / "data" / "processed" / "pakistan_wdi_screen.csv"
if scr.exists():
    tables["real_wdi_pakistan_screen"] = pd.read_csv(scr)


def sqltype(s: pd.Series):
    if pd.api.types.is_bool_dtype(s):
        return SqlType.bool(), lambda x: None if pd.isna(x) else bool(x)
    if pd.api.types.is_integer_dtype(s):
        return SqlType.big_int(), lambda x: None if pd.isna(x) else int(x)
    if pd.api.types.is_float_dtype(s):
        return SqlType.double(), lambda x: None if pd.isna(x) else float(x)
    if pd.api.types.is_datetime64_any_dtype(s):
        return SqlType.timestamp(), lambda x: None if pd.isna(x) else x.to_pydatetime()
    return SqlType.text(), lambda x: None if x is None or (isinstance(x, float) and pd.isna(x)) else str(x)


path = OUT / "novabank.hyper"
summary = {}
with HyperProcess(Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hp:
    with Connection(hp.endpoint, str(path), CreateMode.CREATE_AND_REPLACE) as con:
        con.catalog.create_schema("Extract")
        for name, df in tables.items():
            df = df.copy()
            df.columns = [re.sub(r"\W+", "_", str(c)).strip("_") or "col" for c in df.columns]
            for c in df.columns:
                if df[c].dtype == object:
                    try:
                        parsed = pd.to_datetime(df[c], errors="raise", format="%Y-%m-%d")
                        df[c] = parsed
                    except Exception:
                        pass
            cols, conv = [], []
            for c in df.columns:
                t, f = sqltype(df[c])
                cols.append(TableDefinition.Column(c, t))
                conv.append(f)
            td = TableDefinition(TableName("Extract", name), cols)
            con.catalog.create_table(td)
            with Inserter(con, td) as ins:
                for row in df.itertuples(index=False):
                    ins.add_row([f(x) for f, x in zip(conv, row)])
                ins.execute()
            summary[name] = con.execute_scalar_query(f'SELECT COUNT(*) FROM "Extract"."{name}"')
            assert summary[name] == len(df), (name, summary[name], len(df))
print(f"{path} ({path.stat().st_size/1e6:.1f} MB)")
for k, v in summary.items():
    print(f"  {k}: {v:,} rows")
(OUT / "README.md").write_text(
    "# Tableau extract\n\n`novabank.hyper` (schema `Extract`). Open in Tableau: Connect > To a File > More... > select the file.\n\n"
    "- `synthetic_*` tables come from the NovaBank generator and are NOT real data.\n- `real_*` tables come from SBP, World Bank, BIS and ECB files as parsed in docs/ALL_IN_ONE_ANALYSIS.md.\n"
    "- This is a data extract only. No Tableau workbook has been built or opened by this project (Tableau is not available here), so no dashboard is verified in Tableau.\n"
    "- Rebuild: `python scripts/export_tableau_hyper.py`.\n\nRow counts:\n\n" + "\n".join(f"- {k}: {v:,}" for k, v in summary.items()) + "\n", encoding="utf-8")

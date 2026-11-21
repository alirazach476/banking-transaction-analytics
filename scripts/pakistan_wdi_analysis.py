"""Pakistan banking-sector benchmarking from World Development Indicators (real data, warehouse table wdicsv).

Part A: long-run trends for Pakistan (financial depth, access, macro). Part B: latest-year peer comparison against South Asia and
selected emerging markets, with Pakistan's rank. Part C: correlations over time (descriptive). Writes docs/PAKISTAN_WDI_ANALYSIS.md/.json
and charts docs/img/wdi_*.png.   Run: python scripts/pakistan_wdi_analysis.py
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
con = duckdb.connect(str(ROOT / "data" / "warehouse" / "novabank_data.duckdb"), read_only=True)
T = "worldbank.d0037712_dr0095335_csv_file_wdicsv"
IND = {"credit_gdp": "FS.AST.PRVT.GD.ZS", "bank_credit_gdp": "FD.AST.PRVT.GD.ZS", "broad_money_gdp": "FM.LBL.BMNY.GD.ZS",
       "atm_100k": "FB.ATM.TOTL.P5", "branches_100k": "FB.CBK.BRCH.P5", "borrowers_1000": "FB.CBK.BRWR.P3",
       "remit_gdp": "BX.TRF.PWKR.DT.GD.ZS", "inflation": "FP.CPI.TOTL.ZG", "gdp_growth": "NY.GDP.MKTP.KD.ZG",
       "gdp_pc_usd": "NY.GDP.PCAP.CD", "usdpkr": "PA.NUS.FCRF", "reer": "PX.REX.REER", "reserves_months": "FI.RES.TOTL.MO",
       "mobile_100": "IT.CEL.SETS.P2", "internet_pct": "IT.NET.USER.ZS", "ca_gdp": "BN.CAB.XOKA.GD.ZS"}
PEERS = {"PAK": "Pakistan", "IND": "India", "BGD": "Bangladesh", "LKA": "Sri Lanka", "NPL": "Nepal", "EGY": "Egypt", "IDN": "Indonesia",
         "TUR": "Turkiye", "NGA": "Nigeria", "VNM": "Viet Nam", "PHL": "Philippines", "KEN": "Kenya"}
yrs = [f"_{y}" for y in range(1960, 2026)]
sel = ", ".join(yrs)
codes = "','".join(IND.values())
peers = "','".join(PEERS)
raw = con.execute(f"select country_code cc, indicator_code ic, {sel} from {T} where country_code in ('{peers}') and indicator_code in ('{codes}')").df()
long = raw.melt(id_vars=["cc", "ic"], var_name="year", value_name="v")
long["year"] = long.year.str[1:].astype(int)
long["v"] = pd.to_numeric(long.v, errors="coerce")
long = long.dropna(subset=["v"])
inv = {v: k for k, v in IND.items()}
long["ind"] = long.ic.map(inv)
pak = long[long.cc == "PAK"].pivot_table(index="year", columns="ind", values="v")

R: dict = {}
# ---- Part A ----
def at(s, y):
    s = s.dropna()
    return (int(s.index[s.index <= y][-1]), round(float(s[s.index <= y].iloc[-1]), 2)) if (s.index <= y).any() else None
R["pakistan_latest"] = {k: at(pak[k], 2025) for k in pak.columns}
cr = pak.credit_gdp.dropna()
R["private_credit_gdp"] = {"peak": [int(cr.idxmax()), round(float(cr.max()), 1)], "latest": [int(cr.index[-1]), round(float(cr.iloc[-1]), 1)],
                           "year_2008": round(float(cr.get(2008, np.nan)), 1), "year_2000": round(float(cr.get(2000, np.nan)), 1)}
R["inflation_peak_since_2000"] = {"year": int(pak.inflation[pak.index >= 2000].idxmax()), "pct": round(float(pak.inflation[pak.index >= 2000].max()), 1)}
R["atm_growth"] = {"from": at(pak.atm_100k, 2010), "to": at(pak.atm_100k, 2025)}
R["branches"] = {"from": at(pak.branches_100k, 2010), "to": at(pak.branches_100k, 2025)}
R["usdpkr_change_2015_2023_pct"] = round(float((pak.usdpkr[2023] / pak.usdpkr[2015] - 1) * 100), 1)

# ---- Part B: latest value per country/indicator within 2018-2024 ----
rows = []
for ind in ("credit_gdp", "broad_money_gdp", "atm_100k", "branches_100k", "borrowers_1000", "remit_gdp", "mobile_100", "inflation", "gdp_pc_usd"):
    d = long[(long.ind == ind) & long.year.between(2018, 2025)].sort_values("year").groupby("cc").tail(1).set_index("cc")
    if "PAK" not in d.index:
        continue
    rk = d.v.rank(ascending=False)
    rows.append({"indicator": ind, "pakistan": round(float(d.loc["PAK", "v"]), 1), "year": int(d.loc["PAK", "year"]), "peer_median": round(float(d.drop("PAK").v.median()), 1),
                 "n_peers": int(len(d) - 1), "pakistan_rank_high_to_low": int(rk["PAK"]), "best": PEERS[d.v.idxmax()], "best_value": round(float(d.v.max()), 1)})
R["peer_table"] = rows

# ---- Part C: correlations over time (levels trend, so also first differences) ----
s = pak.loc[1990:2024, ["credit_gdp", "inflation", "gdp_growth", "remit_gdp", "broad_money_gdp", "reer"]].dropna()
R["corr_window"] = [int(s.index.min()), int(s.index.max()), int(len(s))]
R["corr_levels"] = s.corr(method="spearman").round(2).to_dict()
d1 = s.diff().dropna()
R["corr_first_diff"] = d1.corr(method="spearman").round(2).to_dict()
R["note"] = "Annual series with n<=35; correlations are descriptive, not causal; levels trend so first differences are also shown."

# ---- charts ----
plt.rcParams.update({"figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False})
fig, ax = plt.subplots(figsize=(8, 4))
for k, l in (("credit_gdp", "Private credit % GDP"), ("broad_money_gdp", "Broad money % GDP"), ("remit_gdp", "Remittances % GDP")):
    ax.plot(pak[k].dropna().index, pak[k].dropna(), lw=2, label=l)
ax.legend(frameon=False); ax.set_title("Pakistan financial depth (WDI)"); fig.tight_layout(); fig.savefig(ROOT / "docs/img/wdi_depth.png"); plt.close(fig)
fig, ax = plt.subplots(figsize=(8, 4))
ax.bar(pak.index[pak.index >= 2000], pak.inflation[pak.index >= 2000].fillna(0), color="#d95f02")
ax.set_ylabel("%"); ax.set_title("Pakistan CPI inflation (WDI)"); fig.tight_layout(); fig.savefig(ROOT / "docs/img/wdi_inflation.png"); plt.close(fig)
pt = pd.DataFrame(rows).set_index("indicator")
fig, axs = plt.subplots(1, 3, figsize=(11, 3.6))
for ax, ind, t in zip(axs, ("credit_gdp", "atm_100k", "remit_gdp"), ("Private credit % GDP", "ATMs per 100k adults", "Remittances % GDP")):
    d = long[(long.ind == ind) & long.year.between(2018, 2025)].sort_values("year").groupby("cc").tail(1).sort_values("v")
    ax.barh([PEERS[c] for c in d.cc], d.v, color=["#1b9e77" if c == "PAK" else "#999" for c in d.cc]); ax.set_title(t, fontsize=10)
fig.tight_layout(); fig.savefig(ROOT / "docs/img/wdi_peers.png"); plt.close(fig)

(ROOT / "docs" / "PAKISTAN_WDI_ANALYSIS.json").write_text(json.dumps(R, indent=2, default=str), encoding="utf-8")
print(json.dumps(R, indent=1, default=str)[:6000])

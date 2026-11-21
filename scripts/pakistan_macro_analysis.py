"""Pakistan macro / financial-inclusion analysis on REAL data in the warehouse (no synthetic data).

Sources: SBP (policy-rate history parsed from the 'sir' PDF table), BIS (USD/PKR monthly, ws_xru), World Bank/IMF (headline CPI monthly,
inward remittances), World Bank Global Findex 2025. Writes docs/PAKISTAN_ANALYSIS.md, .json and charts in docs/img/.
Run: python scripts/pakistan_macro_analysis.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import duckdb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
IMG = ROOT / "docs" / "img"
IMG.mkdir(parents=True, exist_ok=True)
con = duckdb.connect(str(ROOT / "data" / "warehouse" / "novabank_data.duckdb"), read_only=True)
R: dict = {}

# ---------- 1. SBP policy rate (parsed from PDF table cells) ----------
cells = con.execute("select row_no, cell_text from sbp.table_cells where document='sir' and page=1 and col_no=1 and row_no between 7 and 19 order by row_no").df()
rows = []
for t in cells.cell_text:
    m = re.match(r"(\d{1,2}-[A-Za-z]{3}-\d{2})\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", t)
    if m:
        rows.append((pd.to_datetime(m.group(1), format="%d-%b-%y"), *map(float, m.groups()[1:])))
pol = pd.DataFrame(rows, columns=["date", "ceiling", "floor", "policy", "min_saving_dep"])
assert len(pol) == 13, len(pol)
R["policy_rate_changes"] = pol.assign(date=pol.date.dt.strftime("%Y-%m-%d")).to_dict("records")
R["policy_peak"] = {"rate": float(pol.policy.max()), "date": str(pol.loc[pol.policy.idxmax(), "date"].date())}
R["policy_trough"] = {"rate": float(pol.policy.min()), "date": str(pol.loc[pol.policy.idxmin(), "date"].date())}

# ---------- 2. BIS USD/PKR monthly ----------
x = con.execute("""select time_periodtime_period_or_range tp, obs_valueobservation_value v, collectioncollection c
                   from bis.ws_xru where ref_areareference_area like 'PK:%' and freqfrequency like 'M:%'""").df()
R["bis_xru_collections"] = x.c.value_counts().to_dict()
x["v"] = pd.to_numeric(x.v, errors="coerce")
# one series per period: prefer end-of-period if both exist
x["kind"] = np.where(x.c.str.contains("End|E:", case=False, regex=True), "end", "avg")
fx = x.dropna(subset=["v"]).pivot_table(index="tp", columns="kind", values="v", aggfunc="first")
fx.index = pd.PeriodIndex(fx.index, freq="M")
fx = fx.sort_index()
col = "avg" if "avg" in fx else fx.columns[0]
fxm = fx[col].dropna()
R["fx_series_used"] = col
R["fx_range"] = [str(fxm.index.min()), str(fxm.index.max()), int(len(fxm))]
yoy_fx = fxm.pct_change(12) * 100
R["fx_latest"] = {"period": str(fxm.index[-1]), "pkr_per_usd": float(fxm.iloc[-1])}
R["fx_worst_12m_depreciation"] = {"period": str(yoy_fx.idxmax()), "pct": round(float(yoy_fx.max()), 1)}

# ---------- 3. Pakistan CPI (World Bank/IMF headline CPI, monthly index) ----------
cpi = con.execute("select * from worldbank.d0065307_dr0093087_inflation_data_hcpi_m where country='Pakistan'").df()
ser = cpi.filter(regex=r"^c_\d{6}$").iloc[0].astype(float)
ser.index = pd.PeriodIndex([f"{i[2:6]}-{i[6:]}" for i in ser.index], freq="M")
ser = ser.dropna()
infl = ser.pct_change(12) * 100
R["cpi_range"] = [str(ser.index.min()), str(ser.index.max()), int(ser.notna().sum())]
R["inflation_peak"] = {"period": str(infl.idxmax()), "pct": round(float(infl.max()), 1)}
R["inflation_latest"] = {"period": str(infl.dropna().index[-1]), "pct": round(float(infl.dropna().iloc[-1]), 1)}

# ---------- 4. Join: policy rate vs inflation vs PKR ----------
pr = pol.set_index("date").policy
monthly = pd.period_range("2023-01", infl.dropna().index[-1], freq="M")
pm = pd.Series(index=monthly, dtype=float)
for d, v in pr.items():
    pm[pm.index >= d.to_period("M")] = v
j = pd.DataFrame({"policy": pm, "infl_yoy": infl.reindex(monthly), "fx_yoy": yoy_fx.reindex(monthly)}).dropna()
j["real_rate"] = j.policy - j.infl_yoy
R["joined_months"] = int(len(j))
R["real_rate_min"] = {"period": str(j.real_rate.idxmin()), "pct": round(float(j.real_rate.min()), 1)}
R["real_rate_latest"] = {"period": str(j.index[-1]), "pct": round(float(j.real_rate.iloc[-1]), 1)}
R["corr_policy_infl_same"] = round(float(j.policy.corr(j.infl_yoy)), 2)
lag = {k: round(float(j.policy.corr(j.infl_yoy.shift(-k))), 2) for k in (0, 3, 6, 9, 12)}
R["corr_policy_vs_future_inflation_by_lag_months"] = lag  # policy(t) vs inflation(t+k)
R["note_joined"] = "Only monthly overlap of SBP rate table (starts 2023-03) and World Bank CPI; correlations over a short window are descriptive, not causal."

# ---------- 5. Remittances ----------
rem = con.execute("select * from worldbank.d0066877_dr0095407_inward_remittance_flows_2000_2_inward_remit where remittance_inflows_us_million='Pakistan'").df()
rs = rem.filter(regex=r"^c_\d{4}$").iloc[0].astype(float).dropna()
rs.index = [int(i[2:]) for i in rs.index]
R["remittances_usd_m"] = {int(k): round(float(v)) for k, v in rs.items()}
R["remittance_cagr_2017_2024_pct"] = round(((rs[2024] / rs[2017]) ** (1 / 7) - 1) * 100, 1) if 2017 in rs and 2024 in rs else None

# ---------- 6. Findex Pakistan ----------
f = con.execute("""select _year y, _group g, group2 g2, account_t_d acc, fiaccount_t_d fiacc, mobileaccount_t_d mob, dig_acc dig
                   from external_findex.global_findex_2025 where codewb='PAK'""").df()
for c in ("acc", "fiacc", "mob", "dig"):
    f[c] = pd.to_numeric(f[c], errors="coerce")
allp = f[f.g == "all"].set_index("y")[["acc", "fiacc", "mob", "dig"]] * 100
gen = f[f.g == "gender"].pivot_table(index="y", columns="g2", values="acc") * 100
R["findex_all_pct"] = allp.round(1).to_dict("index")
R["findex_gender_account_pct"] = gen.round(1).to_dict("index")
R["findex_gender_gap_2024_pp"] = round(float(gen.loc[2024, "men"] - gen.loc[2024, "women"]), 1) if 2024 in gen.index else None

# ---------- charts ----------
plt.rcParams.update({"figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False})
fig, ax = plt.subplots(figsize=(8, 4))
ax.plot(j.index.to_timestamp(), j.policy, label="SBP policy rate", lw=2)
ax.plot(j.index.to_timestamp(), j.infl_yoy, label="CPI inflation YoY", lw=2)
ax.plot(j.index.to_timestamp(), j.real_rate, label="Real policy rate", lw=2, ls="--")
ax.axhline(0, color="grey", lw=.8); ax.set_ylabel("%"); ax.legend(frameon=False); ax.set_title("Pakistan: policy rate vs inflation (SBP, World Bank/IMF CPI)")
fig.tight_layout(); fig.savefig(IMG / "pk_policy_inflation.png"); plt.close(fig)

fig, ax = plt.subplots(figsize=(8, 4))
s = fxm[fxm.index >= "2015-01"]
ax.plot(s.index.to_timestamp(), s.values, lw=2); ax.set_ylabel("PKR per USD"); ax.set_title("USD/PKR monthly (BIS)")
fig.tight_layout(); fig.savefig(IMG / "pk_usdpkr.png"); plt.close(fig)

fig, ax = plt.subplots(figsize=(8, 4))
ax.bar(rs.index, rs.values / 1000); ax.set_ylabel("USD bn"); ax.set_title("Pakistan inward remittances (World Bank/KNOMAD)")
fig.tight_layout(); fig.savefig(IMG / "pk_remittances.png"); plt.close(fig)

fig, ax = plt.subplots(figsize=(8, 4))
for c, l in (("acc", "Any account"), ("fiacc", "Bank/FI account"), ("mob", "Mobile money"), ("dig", "Digital payments")):
    ax.plot(allp.index, allp[c], marker="o", label=l)
ax.set_ylabel("% of adults"); ax.set_xticks(allp.index); ax.legend(frameon=False); ax.set_title("Pakistan financial inclusion (Global Findex)")
fig.tight_layout(); fig.savefig(IMG / "pk_findex.png"); plt.close(fig)

R["series"] = {
    "policy_inflation_monthly": [{"month": str(i), "policy": float(r.policy), "inflation": round(float(r.infl_yoy), 2), "real_rate": round(float(r.real_rate), 2)} for i, r in j.iterrows()],
    "usdpkr_monthly": [{"month": str(i), "usdpkr": round(float(v), 2)} for i, v in fxm[fxm.index >= "2015-01"].items()],
    "remittances_usd_m": [{"year": int(i), "usd_m": round(float(v))} for i, v in rs.items()],
    "findex_all_pct": [{"year": int(i), **{k: (None if pd.isna(v) else round(float(v), 1)) for k, v in r.items()}} for i, r in allp.iterrows()],
}
(ROOT / "docs" / "PAKISTAN_ANALYSIS.json").write_text(json.dumps(R, indent=2, default=str), encoding="utf-8")
print(json.dumps(R, indent=2, default=str))

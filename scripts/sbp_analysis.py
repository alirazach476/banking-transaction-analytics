"""Analysis of State Bank of Pakistan tables (real data, parsed from SBP PDFs via OCR into sbp.rows_parsed).

A. Policy-rate history 1991- (OVR-Repo-History). B. Scheduled-bank advances/deposits 2002-2025 -> ADR and growth. C. Daily overnight repo
2015-2026 (OCR-parsed, validated against the policy corridor). D. Net NPLs by bank group (Mar-26 vs Jun-26). E. Government vs private-sector
credit. Writes docs/SBP_ANALYSIS.md/.json and docs/img/sbp_*.png.   Run: python scripts/sbp_analysis.py
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
con = duckdb.connect(str(ROOT / "data" / "warehouse" / "novabank_data.duckdb"), read_only=True)
R: dict = {}
MON = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}


def lines(doc):
    return con.execute(f"select page,row_no,raw_line from sbp.rows_parsed where document='{doc}' order by page,row_no").df()


# ---------------- A. policy rate history ----------------
pr = []
for t in lines("OVR-Repo-History").raw_line:
    m = re.match(r"\s*(\d{1,2}-[A-Za-z]{3}-\d{2})\s*\|?\s*([\d.]+)%?\s*\|?\s*([\d.]+)?%?\s*\|?\s*([\d.]+)?%?", t)
    if m:
        d = pd.to_datetime(m.group(1), format="%d-%b-%y", errors="coerce")
        if pd.notna(d):
            pr.append((d, *[float(x) if x else np.nan for x in m.groups()[1:]]))
P = pd.DataFrame(pr, columns=["date", "c1", "c2", "c3"]).sort_values("date").drop_duplicates("date")
# early rows have one rate column (policy); later rows have ceiling/floor/policy -> use last non-null
P["policy"] = P[["c1", "c2", "c3"]].ffill(axis=1).iloc[:, -1] if False else P[["c1", "c2", "c3"]].apply(lambda r: r.dropna().iloc[-1] if r.notna().any() else np.nan, axis=1)
P["policy"] = np.where(P.c3.notna(), P.c3, P.c1)
P = P.dropna(subset=["policy"])
R["policy_changes"] = int(len(P))
R["policy_span"] = [str(P.date.min().date()), str(P.date.max().date())]
R["policy_peak"] = {"rate": float(P.policy.max()), "date": str(P.loc[P.policy.idxmax(), "date"].date())}
R["policy_trough"] = {"rate": float(P.policy.min()), "date": str(P.loc[P.policy.idxmin(), "date"].date())}
R["policy_latest"] = {"rate": float(P.policy.iloc[-1]), "date": str(P.date.iloc[-1].date())}
P["chg"] = P.policy.diff()
R["largest_hike"] = {"pp": float(P.chg.max()), "date": str(P.loc[P.chg.idxmax(), "date"].date())}
R["largest_cut"] = {"pp": float(P.chg.min()), "date": str(P.loc[P.chg.idxmin(), "date"].date())}
R["hikes"], R["cuts"] = int((P.chg > 0).sum()), int((P.chg < 0).sum())
mp = pd.Series(P.policy.values, index=P.date.dt.to_period("M")).groupby(level=0).last()
mp = mp.reindex(pd.period_range(mp.index.min(), "2026-11", freq="M")).ffill()

# ---------------- B. advances / deposits ----------------
def year_table(doc):
    rows = {}
    for t in lines(doc).raw_line:
        m = re.match(r"(20\d{2})\**\s*\|?\s*(.*)", t)
        if m:
            v = [float(x.replace(",", "")) for x in re.findall(r"\d[\d,]*", m.group(2))]
            if len(v) >= 12:
                rows[int(m.group(1))] = v[:12]
    idx = [pd.Period(f"{y}-{k+1:02d}", "M") for y in sorted(rows) for k in range(12)]
    return pd.Series([x for y in sorted(rows) for x in rows[y]], index=idx)


adv, dep = year_table("advances"), year_table("deposits")
A = pd.DataFrame({"advances": adv, "deposits": dep}).dropna()
A = A.reindex(pd.period_range(A.index.min(), A.index.max(), freq="M"))
R["adr_missing_months"] = int(A.advances.isna().sum())
A["adr"] = A.advances / A.deposits * 100
A["adv_yoy"] = A.advances.pct_change(12) * 100
A["dep_yoy"] = A.deposits.pct_change(12) * 100
R["adr_span"] = [str(A.index.min()), str(A.index.max()), int(len(A))]
R["adr_first"] = round(float(A.adr.iloc[0]), 1)
R["adr_peak"] = {"pct": round(float(A.adr.max()), 1), "month": str(A.adr.idxmax())}
R["adr_trough"] = {"pct": round(float(A.adr.min()), 1), "month": str(A.adr.idxmin())}
R["adr_latest"] = {"pct": round(float(A.adr.iloc[-1]), 1), "month": str(A.index[-1])}
R["advances_cagr_pct"] = round(((A.advances.iloc[-1] / A.advances.iloc[0]) ** (12 / (len(A) - 1)) - 1) * 100, 1)
R["deposits_cagr_pct"] = round(((A.deposits.iloc[-1] / A.deposits.iloc[0]) ** (12 / (len(A) - 1)) - 1) * 100, 1)
R["adv_yoy_extremes"] = {"max": [str(A.adv_yoy.idxmax()), round(float(A.adv_yoy.max()), 1)], "min": [str(A.adv_yoy.idxmin()), round(float(A.adv_yoy.min()), 1)]}
J = A.join(mp.rename("policy")).dropna()
R["corr_adr_vs_policy_levels"] = round(float(J.adr.corr(J.policy, method="spearman")), 2)
R["corr_advances_growth_vs_policy_change_12m"] = round(float((J.adv_yoy.dropna()).corr(J.policy.diff(12).reindex(J.adv_yoy.dropna().index), method="spearman")), 2)
R["adr_by_year_end"] = {str(p.year): round(float(A.adr[p]), 1) for p in A.index if p.month == 12}

# ---------------- C. daily overnight repo (OCR) ----------------
rec = []
rx = re.compile(r"(\d{1,2})\s*[-\s]?\s*([A-Za-z0]{3,9})\.?,?\s*[-\s]?\s*(\d{4})\s*\|?\s*(\d{1,2}\.\d{1,2})")
for t in lines("OvernightsRepoRates_Arch2").raw_line:
    for d, mo, y, r in rx.findall(t.replace("0ctober", "October")):
        k = mo[:3].lower()
        if k in MON:
            try:
                rec.append((pd.Timestamp(int(y), MON[k], int(d)), float(r)))
            except ValueError:
                pass
V = pd.DataFrame(rec, columns=["date", "repo"]).drop_duplicates("date").sort_values("date").set_index("date")
R["repo_daily_obs"] = int(len(V))
R["repo_span"] = [str(V.index.min().date()), str(V.index.max().date())]
R["repo_gaps_gt7d"] = int((V.index.to_series().diff().dt.days > 7).sum())
vm = V.repo.resample("MS").mean().dropna()
vm.index = vm.index.to_period("M")
chk = pd.DataFrame({"repo": vm, "policy": mp.reindex(vm.index)}).dropna()
chk["spread"] = chk.repo - chk.policy
R["repo_minus_policy_pp"] = {"mean": round(float(chk.spread.mean()), 2), "median": round(float(chk.spread.median()), 2), "p5": round(float(chk.spread.quantile(.05)), 2),
                             "p95": round(float(chk.spread.quantile(.95)), 2), "months": int(len(chk))}
R["repo_outliers_gt30"] = int((V.repo > 30).sum())
R["repo_within_1pp_of_policy_share"] = round(float((chk.spread.abs() <= 1).mean()), 3)
dv = V.repo.diff().abs()
R["repo_daily_volatility_median_abs_chg_pp"] = round(float(dv.median()), 3)
V["year"] = V.index.year
R["repo_year_mean"] = {int(y): round(float(g.repo.mean()), 2) for y, g in V.groupby("year")}

# ---------------- D. net NPLs ----------------
npl = []
num = r"(\(?-?[\d,.]+\)?)"
def sg(x):
    v = float(x.strip("()").replace(",", ""))
    return -abs(v) if x.startswith("(") else v
for t in lines("NPLs_Jun-2026").raw_line:
    m = re.match(r"\s*([A-Za-z&/ ]+?)\s*\|\s*" + num + r"\s*\|\s*" + num + r"\s*\|\s*" + num + r"\s*\|\s*" + num + r"\s*\|\s*" + num + r"\s*\|\s*" + num, t)
    if m:
        v = [sg(x) for x in m.groups()[1:]]
        npl.append({"group": m.group(1).strip(), "npl_mar26": v[0], "net_npl_mar26": v[1], "net_npl_ratio_mar26": v[2],
                    "npl_jun26": v[3], "net_npl_jun26": v[4], "net_npl_ratio_jun26": v[5]})
N = pd.DataFrame(npl)
R["npl_rows_parsed"] = int(len(N))
R["npl_table"] = N.to_dict("records")

# ---------------- E. government vs private credit ----------------
cl = lines("CreditLoans")
def credit(pattern):
    r = cl[cl.raw_line.str.contains(pattern, regex=True)].raw_line.head(1)
    if r.empty:
        return None
    t = re.sub(r"^.*?(?=\d[\d,]*\s)", "", r.iloc[0]) if False else r.iloc[0]
    vals = [float(x.replace(",", "")) for x in re.findall(r"(?<![\w.])\d[\d,]{3,}(?![\w.])", t.split("|")[0][-80:] + "|" + "|".join(t.split("|")[1:]))]
    return vals[-4:]
CR = {"government": credit(r"^1\. Credit to Government Sector"), "non_government": credit(r"^2\.Credit to Non Government Sector"),
      "private_sector_total": credit(r"III\. Credit to Private Sector"), "private_business": credit(r"^1\. PRIVATE SECTOR \(BUSINESS\)"),
      "personal": credit(r"^3\.PERSONAL"), "total_credit": credit(r"^Total Credit\(1\+2\)")}
R["credit_jun25_oct25_jun26_oct26p_rs_m"] = CR
if CR["government"] and CR["total_credit"]:
    R["government_share_of_total_credit_pct"] = [round(g / t * 100, 1) for g, t in zip(CR["government"], CR["total_credit"])]
if CR["personal"] and CR["private_sector_total"]:
    R["personal_share_of_private_credit_pct"] = [round(g / t * 100, 1) for g, t in zip(CR["personal"], CR["private_sector_total"])]
    R["personal_credit_growth_jun25_to_jun26_pct"] = round((CR["personal"][2] / CR["personal"][0] - 1) * 100, 1)
    R["private_credit_growth_jun25_to_jun26_pct"] = round((CR["private_sector_total"][2] / CR["private_sector_total"][0] - 1) * 100, 1)
    R["government_credit_growth_jun25_to_jun26_pct"] = round((CR["government"][2] / CR["government"][0] - 1) * 100, 1)

# ---------------- charts ----------------
plt.rcParams.update({"figure.dpi": 130, "axes.spines.top": False, "axes.spines.right": False})
fig, ax = plt.subplots(figsize=(8, 3.8))
ax.step(P.date, P.policy, where="post", lw=2); ax.set_ylabel("%"); ax.set_title("SBP policy (target) rate since 1991")
fig.tight_layout(); fig.savefig(ROOT / "docs/img/sbp_policy_history.png"); plt.close(fig)
fig, axs = plt.subplots(2, 1, figsize=(8, 6), sharex=True)
axs[0].plot(A.index.to_timestamp(), A.adr, lw=2, color="#1b9e77"); axs[0].set_ylabel("Advances / deposits (%)"); axs[0].set_title("Scheduled banks: advances-to-deposits ratio")
axs[1].plot(A.index.to_timestamp(), A.adv_yoy, label="Advances YoY %", lw=1.8); axs[1].plot(A.index.to_timestamp(), A.dep_yoy, label="Deposits YoY %", lw=1.8)
axs[1].legend(frameon=False); axs[1].axhline(0, color="grey", lw=.7)
fig.tight_layout(); fig.savefig(ROOT / "docs/img/sbp_adr.png"); plt.close(fig)
fig, ax = plt.subplots(figsize=(8, 3.8))
ax.plot(chk.index.to_timestamp(), chk.repo, label="Overnight repo (monthly mean)", lw=1.8); ax.step(chk.index.to_timestamp(), chk.policy, where="post", label="Policy rate", lw=1.8)
ax.legend(frameon=False); ax.set_ylabel("%"); ax.set_title("Overnight repo vs policy rate")
fig.tight_layout(); fig.savefig(ROOT / "docs/img/sbp_repo_policy.png"); plt.close(fig)

(ROOT / "docs" / "SBP_ANALYSIS.json").write_text(json.dumps(R, indent=2, default=str), encoding="utf-8")
print(json.dumps(R, indent=1, default=str)[:7000])

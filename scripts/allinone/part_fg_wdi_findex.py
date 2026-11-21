"""Part F: screen of every WDI indicator for Pakistan against all other countries. Part G: Global Findex 2024 (Pakistan vs all economies)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *  # noqa

con = connect()
D: dict = {}
q = lambda s: con.execute(s).df()

# ---------------- F: WDI screen ----------------
cc = q("select * from worldbank.d0037712_dr0095335_csv_file_wdicountry")
regcol = next(c for c in cc.columns if c == "region")
countries = set(cc[(cc[regcol].notna()) & (cc[regcol].astype(str).str.strip() != "")].country_code)
D["wdi_countries_excluding_aggregates"] = len(countries)
yrs = [f"_{y}" for y in range(2005, 2026)]
w = q(f"select country_code cc, indicator_code ic, indicator_name nm, {', '.join(yrs)} from worldbank.d0037712_dr0095335_csv_file_wdicsv")
D["wdi_rows"] = int(len(w))
w = w[w.cc.isin(countries | {"PAK"})]
vals = w[yrs].apply(pd.to_numeric, errors="coerce")
w = pd.concat([w[["cc", "ic", "nm"]], vals], axis=1)
pak = w[w.cc == "PAK"].set_index("ic")
D["pakistan_series"] = int(len(pak))
D["pakistan_series_with_data_since_2015"] = int(pak[[f"_{y}" for y in range(2015, 2026)]].notna().any(axis=1).sum())
res = []
others = w[w.cc != "PAK"].groupby("ic")
for ic, r in pak.iterrows():
    s = r[yrs].dropna()
    s = s[[i for i in s.index if int(i[1:]) >= 2015]]
    if s.empty:
        continue
    y = s.index[-1]
    g = others.get_group(ic)[y].dropna() if ic in others.groups else pd.Series(dtype=float)
    if len(g) < 100:
        continue
    pctl = float((g < s[y]).mean() * 100 + 0.5 * (g == s[y]).mean() * 100)
    s10 = r.get(f"_{int(y[1:]) - 10}")
    chg = None
    if s10 is not None and pd.notna(s10) and s10 != 0:
        chg = float((s[y] - s10) / abs(s10) * 100)
    res.append({"ic": ic, "name": r["nm"], "year": int(y[1:]), "value": float(s[y]), "pctl": pctl, "n_countries": int(len(g) + 1), "chg10_pct": chg})
R = pd.DataFrame(res)
D["indicators_ranked_all"] = int(len(R))
rate_like = R.name.str.contains(r"%|per 1,000|per 100|per 1 million|ratio|rate|index|years|days|per capita|per person", case=False, regex=True) & ~R.name.str.contains(
    r"Net bilateral|Net official|\(NFL|IFC|DAC donors|current LCU|constant LCU|current US\$|constant 20\d\d US\$|Number of|Population,|Terms of trade", case=False, regex=True)
R = R[rate_like].copy()
D["indicators_ranked"] = int(len(R))
THEMES = {"finance & payments": r"account|bank|credit|loan|borrow|deposit|financ|interest|atm|payment|remittance|debit|card|mobile money|lending|insurance|financial",
          "economy & trade": r"gdp|export|import|trade|invest|tax|revenue|income|inflation|price|exchange|reserve|debt|current account|manufactur",
          "health": r"mortality|life expect|health|immuni|birth|death|disease|nutrition|stunting|hospital|physician|sanitation|water",
          "education & gender": r"school|education|literacy|enrol|female|women|gender|girls|teacher",
          "energy & environment": r"energy|electric|co2|emission|forest|renewable|fuel|carbon|pm2|agricultur",
          "digital": r"internet|mobile|telephone|broadband|computer|subscri"}
def theme(n):
    for t, p in THEMES.items():
        if re.search(p, n, re.I):
            return t
    return "other"
R["theme"] = R.name.map(theme)
low = R[R.pctl <= 3].sort_values("pctl")
high = R[R.pctl >= 97].sort_values("pctl", ascending=False)
D["n_lowest_3pct"], D["n_highest_3pct"] = int(len(low)), int(len(high))
D["theme_counts_ranked"] = R.theme.value_counts().to_dict()
D["lowest_extremes_by_theme"] = low.theme.value_counts().to_dict()
D["highest_extremes_by_theme"] = high.theme.value_counts().to_dict()
def pick(d, n):
    out = []
    seen = set()
    for r in d.itertuples():
        key = re.sub(r"\(.*?\)", "", r.name)[:40]
        if key in seen:
            continue
        seen.add(key)
        out.append({"indicator": r.name[:140], "year": r.year, "value": round(r.value, 2), "percentile": round(r.pctl, 1), "of": r.n_countries})
        if len(out) >= n:
            break
    return out
fin_low = pick(low[low.theme.isin(["finance & payments", "digital"])], 8)
fin_high = pick(high[high.theme.isin(["finance & payments", "digital"])], 6)
D["finance_digital_lowest"], D["finance_digital_highest"] = fin_low, fin_high
D["all_lowest_sample"] = pick(low, 10)
D["all_highest_sample"] = pick(high, 8)
pp = R[R.name.str.contains(r"\(%|% of|%\)", regex=True) & R.value.between(0, 100)].copy()
pp["prev"] = pp.apply(lambda r: pak.loc[r.ic, f"_{r.year - 10}"] if f"_{r.year - 10}" in pak.columns else np.nan, axis=1)
pp = pp.dropna(subset=["prev"])
pp["chg_pp"] = pp.value - pp.prev
def pick2(d, n):
    out, seen = [], set()
    for r in d.itertuples():
        key = re.sub(r"\(.*?\)", "", r.name)[:35]
        if key in seen:
            continue
        seen.add(key)
        out.append({"indicator": r.name[:140], "from": round(float(r.prev), 1), "to": round(float(r.value), 1), "year": r.year, "change_pp": round(float(r.chg_pp), 1)})
        if len(out) >= n:
            break
    return out
D["pp_indicators_with_10y_history"] = int(len(pp))
D["biggest_10y_increases_pp"] = pick2(pp.sort_values("chg_pp", ascending=False), 8)
D["biggest_10y_decreases_pp"] = pick2(pp.sort_values("chg_pp"), 8)
D["median_percentile_all_indicators"] = round(float(R.pctl.median()), 1)
R.to_csv(ROOT / "data" / "processed" / "pakistan_wdi_screen.csv", index=False)

# ---------------- G: Findex 2024 ----------------
fx = q("""select countrynewwb c, codewb iso, _year y, _group g, group2 g2, try_cast(account_t_d as double) acc, try_cast(fiaccount_t_d as double) fiacc,
          try_cast(mobileaccount_t_d as double) mob, try_cast(borrow_any_t_d as double) borrow, try_cast(dig_acc as double) dig from external_findex.global_findex_2025""")
a24 = fx[(fx.y == 2024) & (fx.g == "all")].set_index("iso")
D["findex_economies_2024"] = int(len(a24))
rk = {}
for col, nm_ in (("acc", "any account"), ("fiacc", "financial-institution account"), ("mob", "mobile-money account"), ("borrow", "borrowed in the past year"), ("dig", "dig_acc (digital; exact definition not in warehouse)")):
    s = a24[col].dropna()
    if "PAK" in s.index:
        rk[nm_] = {"pakistan_pct": round(float(s["PAK"] * 100), 1), "rank_high_to_low": int((s > s["PAK"]).sum() + 1), "of": int(len(s)), "median_pct": round(float(s.median() * 100), 1)}
D["pakistan_findex_rank_2024"] = rk
gend = fx[(fx.y == 2024) & (fx.g == "gender")].pivot_table(index="iso", columns="g2", values="acc")
gend["gap_pp"] = (gend["men"] - gend["women"]) * 100
D["gender_gap_pk_pp"] = round(float(gend.loc["PAK", "gap_pp"]), 1)
D["gender_gap_pk_rank_largest"] = int((gend.gap_pp > gend.loc["PAK", "gap_pp"]).sum() + 1)
D["gender_gap_economies"] = int(gend.gap_pp.notna().sum())
D["gender_gap_median_pp"] = round(float(gend.gap_pp.median()), 1)
D["gender_gap_largest5"] = [(i, round(float(v), 1)) for i, v in gend.gap_pp.sort_values(ascending=False).head(5).items()]
D["women_account_pk_pct"] = round(float(gend.loc["PAK", "women"] * 100), 1)
D["women_account_rank_lowest"] = int((gend.women < gend.loc["PAK", "women"]).sum() + 1)
peer_codes = ["PAK", "IND", "BGD", "LKA", "NPL", "IDN", "EGY", "TUR", "NGA", "KEN", "VNM", "PHL"]
D["peers_findex_2024_pct"] = {k: {"account": round(float(a24.loc[k, "acc"] * 100), 1), "mobile_money": round(float(a24.loc[k, "mob"] * 100), 1) if pd.notna(a24.loc[k, "mob"]) else None,
                                  "women_account": round(float(gend.loc[k, "women"] * 100), 1)} for k in peer_codes if k in a24.index and k in gend.index}
for grp in ("income", "urbanicity", "education", "age_cat"):
    d = fx[(fx.y == 2024) & (fx.iso == "PAK") & (fx.g == grp)][["g2", "acc"]]
    D[f"pakistan_account_by_{grp}_pct"] = {r.g2: round(r.acc * 100, 1) for r in d.itertuples()}
D["findex_mobile_vs_fi_note"] = "mobile-money account share exceeds financial-institution account share in Pakistan 2024" if rk.get("mobile-money account", {}).get("pakistan_pct", 0) > rk.get("financial-institution account", {}).get("pakistan_pct", 1) else "no"

fig, ax = plt.subplots(figsize=(8, 4.2))
pc = pd.DataFrame(D["peers_findex_2024_pct"]).T.sort_values("account")
ax.barh(pc.index, pc.account, color=["#1b9e77" if i == "PAK" else "#999" for i in pc.index]); ax.set_xlabel("% of adults with an account, 2024"); ax.set_title("Account ownership, Global Findex 2024")
fig.tight_layout(); fig.savefig(IMG / "allin_findex_peers.png"); plt.close(fig)


# ---------------- markdown ----------------
def find(rows, key):
    return next((r for r in rows if key.lower() in r["indicator"].lower()), None)
lo = D["all_lowest_sample"] + D["finance_digital_lowest"]
hi = D["all_highest_sample"]
mu_, md_ = D["biggest_10y_increases_pp"], D["biggest_10y_decreases_pp"]
def L(r, extra=""):
    return f"{r['indicator']} {r['value']}{extra} ({r['year']}; percentile {r['percentile']} of {r['of']})" if r else ""
low_items = [find(lo, k) for k in ("Account ownership", "Employers, female", "Current health expenditure", "Trade (% of GDP)", "Employment in services, female", "Antiretroviral")]
high_items = [find(hi, k) for k in ("Diabetes", "neonatal", "not in education, employment", "Public and publicly guaranteed debt service", "Communications, computer")]
def mv(rows, key):
    return find2(rows, key)
def find2(rows, key):
    return next((r for r in rows if key.lower() in r["indicator"].lower()), None)
ups = [find2(mu_, k) for k in ("Internet", "ICT service exports", "Primary completion rate, female", "Tuberculosis", "Lower secondary completion rate, female")]
dns = [find2(md_, k) for k in ("Electricity production from oil", "open defecation", "surgical care")]
rk = D["pakistan_findex_rank_2024"]
pe = D["peers_findex_2024_pct"]
peer_txt = "; ".join(f"{k} {v['account']}% (women {v['women_account']}%)" for k, v in pe.items() if k != "PAK")
md = f"""## F. Where Pakistan stands on {D['pakistan_series']:,} World Development Indicators

I screened every WDI series for Pakistan ({D['pakistan_series_with_data_since_2015']:,} have data since 2015) and ranked the latest value against all {D['wdi_countries_excluding_aggregates']} countries and territories that report it (aggregates excluded; series with fewer than 100 reporting countries skipped). Size-driven series (populations, aid and flow amounts in dollars) were removed, leaving {D['indicators_ranked']} ratio-type indicators (the full table is `data/processed/pakistan_wdi_screen.csv`). Pakistan's median percentile across them is {D['median_percentile_all_indicators']}; {D['n_lowest_3pct']} sit in the lowest 3% of countries and {D['n_highest_3pct']} in the highest 3%. A high or low percentile is a position, not a judgement: for some of these a higher value is worse.

**Lowest 3% of countries:** {'; '.join(L(r) for r in low_items if r)}.
**Highest 3%:** {'; '.join(L(r) for r in high_items if r)}.
**Largest 10-year changes in % indicators (percentage points):** {'; '.join(f"{r['indicator']} {r['from']} to {r['to']}" for r in ups if r)}; falls: {'; '.join(f"{r['indicator']} {r['from']} to {r['to']}" for r in dns if r)}. Debt service on public and publicly guaranteed debt rose from 8.0% to 27.2% of exports over the decade (consistent with the IDS result in Part D). (Series that drop to exactly 0 in one year, such as the WTO 'binding coverage' ones, were excluded from the narrative as probable reporting artefacts.)
For the banking and payments questions the screen agrees with the earlier analyses: female financial access is the lowest of any country that reports it, and trade and health spending are among the lowest shares of GDP.

## G. Financial inclusion in depth (Global Findex 2024, {D['findex_economies_2024']} economies)

Pakistan's rank among {D['findex_economies_2024']} economies for the adult population:
| Measure | Pakistan | Median economy | Pakistan's rank (1 = highest) |
|---|---|---|---|
| Any account | {rk['any account']['pakistan_pct']}% | {rk['any account']['median_pct']}% | {rk['any account']['rank_high_to_low']} of {rk['any account']['of']} |
| Account at a financial institution | {rk['financial-institution account']['pakistan_pct']}% | {rk['financial-institution account']['median_pct']}% | {rk['financial-institution account']['rank_high_to_low']} of {rk['financial-institution account']['of']} |
| Mobile-money account | {rk['mobile-money account']['pakistan_pct']}% | {rk['mobile-money account']['median_pct']}% | {rk['mobile-money account']['rank_high_to_low']} of {rk['mobile-money account']['of']} |
| Borrowed in the past year (any source) | {rk['borrowed in the past year']['pakistan_pct']}% | {rk['borrowed in the past year']['median_pct']}% | {rk['borrowed in the past year']['rank_high_to_low']} of {rk['borrowed in the past year']['of']} |
| dig_acc (digital; exact definition not in the warehouse) | {rk['dig_acc (digital; exact definition not in warehouse)']['pakistan_pct']}% | {rk['dig_acc (digital; exact definition not in warehouse)']['median_pct']}% | {rk['dig_acc (digital; exact definition not in warehouse)']['rank_high_to_low']} of {rk['dig_acc (digital; exact definition not in warehouse)']['of']} |

- **Women:** {D['women_account_pk_pct']}% of Pakistani women have an account, the **lowest of all {D['gender_gap_economies']} economies** (rank {D['women_account_rank_lowest']} lowest). The gender gap is {D['gender_gap_pk_pp']} percentage points, the **{D['gender_gap_pk_rank_largest']}nd largest** (largest: {', '.join(f"{i} {v}" for i, v in D['gender_gap_largest5'][:3])}) against a median gap of {D['gender_gap_median_pp']} points.
- **Who is excluded:** poorest 40% {D['pakistan_account_by_income_pct']['poorest 40%']}% vs richest 60% {D['pakistan_account_by_income_pct']['richest 60%']}%; rural {D['pakistan_account_by_urbanicity_pct']['rural']}% vs urban {D['pakistan_account_by_urbanicity_pct']['urban']}%; primary education or less {D['pakistan_account_by_education_pct']['prim edu or less']}% vs secondary or more {D['pakistan_account_by_education_pct']['secondary edu or more']}%; ages 15-24 {D['pakistan_account_by_age_cat_pct']['ages 15-24']}% vs 25+ {D['pakistan_account_by_age_cat_pct']['age 25+']}%.
- **Mobile money now roughly equals bank accounts:** {rk['mobile-money account']['pakistan_pct']}% hold a mobile-money account against {rk['financial-institution account']['pakistan_pct']}% a financial-institution account (the two groups overlap, so they are not additive), but Pakistan is still below the median among the {rk['mobile-money account']['of']} economies that report mobile money ({rk['mobile-money account']['median_pct']}%).
- **Borrowing is high** ({rk['borrowed in the past year']['pakistan_pct']}%, rank {rk['borrowed in the past year']['rank_high_to_low']} of {rk['borrowed in the past year']['of']}) even though accounts are rare, which is consistent with a large informal borrowing market, but that is a reading only; the Findex fields available do not let me separate formal from informal borrowing.
- **Peers (account ownership 2024):** {peer_txt}.
- ![](img/allin_findex_peers.png)
- *Correction to my earlier Pakistan analysis:* it labelled the Findex field `dig_acc` 'digital payments'. The Findex codebook is not in the warehouse, so that label was an assumption; this part uses the neutral field name.
"""
save("part_fg", md, D)
print(md)

"""Part D: Pakistan's cross-border finance: BIS banking statistics (claims/liabilities with Pakistan as counterparty), World Bank IDS external debt,
World Bank remittance prices (cost of sending money into Pakistan)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *  # noqa

con = connect()
D: dict = {}
q = lambda s: con.execute(s).df()

# ---------- D1 BIS locational banking statistics ----------
LBS = "bis.ws_lbs_d_pub"
base = "l_cp_countrycounterparty_country like 'PK:%' and l_measuremeasure like 'S:%' and l_instrtype_of_instruments like 'A:%' and l_denomcurrency_denomination like 'TO1%' and l_curr_typecurrency_type_of_reporting_country like 'A:%' and obs_valueobservation_value is not null and freqfrequency like 'Q:%'"
ts = q(f"""select left(l_positionbalance_sheet_position,1) pos, left(l_rep_ctyreporting_country,2) rep, left(l_cp_sectorcounterparty_sector,1) sec, time_periodtime_period_or_range tp,
           try_cast(obs_valueobservation_value as double) v from {LBS} where {base}""")
allc = ts[(ts.rep == "5A") & (ts.sec == "A")].pivot_table(index="tp", columns="pos", values="v").sort_index()
D["lbs_span"] = [allc.index.min(), allc.index.max(), int(len(allc))]
D["lbs_claims_latest_usd_m"] = [allc.index[allc.C.notna()][-1], round(float(allc.C.dropna().iloc[-1]))]
D["lbs_liabilities_latest_usd_m"] = [allc.index[allc.L.notna()][-1], round(float(allc.L.dropna().iloc[-1]))]
D["lbs_claims_peak"] = [allc.C.idxmax(), round(float(allc.C.max()))]
D["lbs_claims_trough_since_2010"] = [allc.C[allc.index >= "2010-Q1"].idxmin(), round(float(allc.C[allc.index >= "2010-Q1"].min()))]
cl = allc.C.dropna()
if len(cl) > 4:
    D["lbs_claims_yoy_latest_pct"] = round((cl.iloc[-1] / cl.iloc[-5] - 1) * 100, 1)
    D["lbs_claims_5y_change_pct"] = round((cl.iloc[-1] / cl.iloc[-21] - 1) * 100, 1) if len(cl) > 21 else None
ll = allc.L.dropna()
D["lbs_net_position_latest_usd_m"] = round(float(cl.iloc[-1] - ll.reindex(cl.index).ffill().iloc[-1]))
last = D["lbs_claims_latest_usd_m"][0]
by_c = ts[(ts.pos == "C") & (ts.sec == "A") & (ts.rep != "5A") & (ts.tp == last)].sort_values("v", ascending=False)
D["claims_by_reporting_country_latest"] = {r.rep: round(r.v) for r in by_c.head(10).itertuples()}
sec_ = ts[(ts.pos == "C") & (ts.rep == "5A") & (ts.tp == last)]
D["claims_by_sector_latest"] = {r.sec: round(r.v) for r in sec_.itertuples()}
D["top3_reporting_share_of_claims_pct"] = round(float(by_c.v.head(3).sum() / allc.C.dropna().iloc[-1] * 100), 1)
# CBS: international claims, immediate counterparty basis
cbs = q("""select left(cbs_basiscbs_reporting_basis,1) basis, left(l_positionbalance_sheet_position,1) pos, left(l_cp_sectorcounterparty_sector,1) sec, left(cbs_bank_typecbs_bank_type,2) bt,
           time_periodtime_period_or_range tp, try_cast(obs_valueobservation_value as double) v from bis.ws_cbs_pub
           where l_cp_countrycounterparty_country like 'PK:%' and l_measuremeasure like 'S:%' and left(l_rep_ctyreporting_country,2)='5A' and obs_valueobservation_value is not null""")
c1 = cbs[(cbs.pos == "I") & (cbs.sec == "A") & (cbs.bt == "4R")]
for basis, name in (("F", "immediate_counterparty"), ("U", "guarantor")):
    s = c1[c1.basis == basis].groupby("tp").v.max().sort_index()
    if len(s):
        D[f"cbs_international_claims_{name}_latest"] = [s.index[-1], round(float(s.iloc[-1]))]
        D[f"cbs_international_claims_{name}_peak"] = [s.idxmax(), round(float(s.max()))]
D["cbs_series_note"] = "CBS = consolidated banking statistics, international claims of banks headquartered in reporting countries (domestic positions excluded), 4R bank type."

# ---------- D2 World Bank IDS external debt ----------
IDS = "worldbank.d0038015_dr0093225_bulk_download_file_debtor_coun_n_q"
yrs = list(range(2000, 2034))
cols = ", ".join(f"c_{y}" for y in yrs)
ids = q(f"select counterpart_area_name cp, series_code sc, series_name sn, {cols} from {IDS} where country_code='PAK'")
def series(sc, cp="World"):
    r = ids[(ids.sc == sc) & (ids.cp == cp)]
    if r.empty:
        return pd.Series(dtype=float)
    s = pd.to_numeric(r.iloc[0][[f"c_{y}" for y in yrs]], errors="coerce")
    s.index = yrs
    return s.dropna()
tot = series("DT.DOD.DECT.CD")
ly = int(tot.index[tot.index <= 2025].max())
D["ids_total_external_debt_usd_bn"] = {y: round(float(tot[y] / 1e9), 1) for y in (2000, 2005, 2010, 2015, 2020, 2022, 2023, ly)}
D["ids_latest_actual_year"] = ly
D["ids_external_debt_cagr_2000_latest_pct"] = round(((tot[ly] / tot[2000]) ** (1 / (ly - 2000)) - 1) * 100, 1)
comp = {"PPG multilateral": "DT.DOD.MLAT.CD", "PPG bilateral": "DT.DOD.BLAT.CD", "PPG bonds": "DT.DOD.PBND.CD", "PPG commercial banks": "DT.DOD.PCBK.CD", "PNG (private non-guaranteed)": "DT.DOD.DPNG.CD",
        "short-term debt": "DT.DOD.DSTC.CD", "IMF credit": "DT.DOD.DIMF.CD"}
cv = {k: series(v) for k, v in comp.items()}
D["ids_composition_latest_usd_bn"] = {k: round(float(s[ly] / 1e9), 1) for k, s in cv.items() if ly in s.index}
D["ids_composition_latest_share_pct"] = {k: round(float(s[ly] / tot[ly] * 100), 1) for k, s in cv.items() if ly in s.index}
tds = series("DT.TDS.DECT.CD")
D["ids_debt_service_usd_bn"] = {y: round(float(tds[y] / 1e9), 1) for y in (2015, 2020, 2022, 2023, ly) if y in tds.index}
D["ids_debt_service_projection_2026_2030_usd_bn"] = {y: round(float(tds[y] / 1e9), 1) for y in range(ly + 1, ly + 6) if y in tds.index}
res = con.execute("select _2024 from worldbank.d0037712_dr0095335_csv_file_wdicsv where country_code='PAK' and indicator_code='FI.RES.TOTL.CD'").fetchone()
D["wdi_reserves_2024_usd_bn"] = round(float(res[0]) / 1e9, 1) if res and res[0] is not None else None
wdi_dod = con.execute(f"select _{ly} from worldbank.d0037712_dr0095335_csv_file_wdicsv where country_code='PAK' and indicator_code='DT.DOD.DECT.CD'").fetchone()
D["reconciliation_ids_vs_wdi_total_debt_latest"] = [round(float(tot[ly]) / 1e9, 2), round(float(wdi_dod[0]) / 1e9, 2) if wdi_dod and wdi_dod[0] is not None else None]
gni = con.execute(f"select _{ly}, _2010, _2020 from worldbank.d0037712_dr0095335_csv_file_wdicsv where country_code='PAK' and indicator_code='DT.DOD.DECT.GN.ZS'").fetchone()
D["wdi_external_debt_pct_gni"] = {str(ly): gni[0], "2010": gni[1], "2020": gni[2]} if gni else None
exp = con.execute(f"select _{ly}, _2010, _2020 from worldbank.d0037712_dr0095335_csv_file_wdicsv where country_code='PAK' and indicator_code='DT.TDS.DECT.EX.ZS'").fetchone()
D["wdi_debt_service_pct_exports"] = {str(ly): exp[0], "2010": exp[1], "2020": exp[2]} if exp else None
cr = ids[(ids.sc == "DT.DOD.DECT.CD") & (ids.cp != "World")][["cp", f"c_{ly}"]].copy()
cr[f"c_{ly}"] = pd.to_numeric(cr[f"c_{ly}"], errors="coerce")
cr = cr.dropna().sort_values(f"c_{ly}", ascending=False)
D["ids_top_creditors_latest_usd_bn"] = {r.cp: round(r[1] / 1e9, 2) for r in cr.head(10).itertuples(index=False)}
D["ids_creditor_rows_sum_vs_total_pct"] = round(float(cr[f"c_{ly}"].sum() / tot[ly] * 100), 1)

# ---------- D3 remittance prices into Pakistan ----------
RPW = "worldbank.d0037898_dr0095523_remittance_prices_worldwide_co_dataset_from"
rp = q(f"select period, source_name src, firm_type, payment_instrument pi, access_point ap, try_cast(cc1_total_cost as double) cost, try_cast(cc1_fx_margin as double) fxm from {RPW} where destination_name ilike 'Pakistan'")
rp = rp.dropna(subset=["cost"])
rp["year"] = rp.period.str[:4].astype(int)
D["rpw_quotes"] = int(len(rp))
D["rpw_years"] = [int(rp.year.min()), int(rp.year.max())]
yr = rp.groupby("year").cost.agg(["mean", "median", "count"]).round(2)
D["rpw_cost_pct_by_year_mean"] = {int(y): float(v) for y, v in yr["mean"].items()}
D["rpw_cost_pct_by_year_median"] = {int(y): float(v) for y, v in yr["median"].items()}
ly2 = int(rp.year.max())
last3 = rp[rp.year >= ly2 - 1]
D["rpw_latest_window"] = [ly2 - 1, ly2, int(len(last3))]
D["rpw_cost_by_sender_latest_mean"] = {k: [round(float(g.cost.mean()), 2), int(len(g))] for k, g in last3.groupby("src") if len(g) >= 8}
D["rpw_cost_by_firm_type_latest_mean"] = {k: [round(float(g.cost.mean()), 2), int(len(g))] for k, g in last3.groupby("firm_type") if len(g) >= 8}
D["rpw_cost_by_instrument_latest_mean"] = {k: [round(float(g.cost.mean()), 2), int(len(g))] for k, g in last3.groupby("pi") if len(g) >= 8}
D["rpw_cost_by_access_point_latest_mean"] = {k: [round(float(g.cost.mean()), 2), int(len(g))] for k, g in last3.groupby("ap") if len(g) >= 8}
D["rpw_share_quotes_above_3pct_latest"] = round(float((last3.cost > 3).mean() * 100), 1)
D["rpw_fx_margin_mean_latest"] = round(float(last3.fxm.mean()), 2)
glob = q(f"select substr(period,1,4) y, avg(try_cast(cc1_total_cost as double)) c from {RPW} where try_cast(cc1_total_cost as double) is not null group by 1 order by 1")
D["rpw_world_mean_cost_by_year"] = {r.y: round(r.c, 2) for r in glob.itertuples()}

# ---------- charts ----------
fig, ax = plt.subplots(figsize=(8, 3.8))
c_ = allc.C.dropna(); l_ = allc.L.dropna()
ax.plot(range(len(c_)), c_.values / 1e3, label="Cross-border claims on Pakistan", lw=2); ax.plot([list(c_.index).index(i) for i in l_.index if i in c_.index], [l_[i] / 1e3 for i in l_.index if i in c_.index], label="Liabilities to Pakistan", lw=2)
ax.set_xticks(range(0, len(c_), 16)); ax.set_xticklabels(c_.index[::16], rotation=45); ax.set_ylabel("US$ billion"); ax.legend(frameon=False); ax.set_title("BIS locational banking statistics, Pakistan as counterparty")
fig.tight_layout(); fig.savefig(IMG / "allin_bis_lbs_pk.png"); plt.close(fig)
fig, ax = plt.subplots(figsize=(8, 3.8))
ax.plot(tot.index[tot.index <= ly], tot[tot.index <= ly] / 1e9, lw=2, label="External debt stock"); ax.plot(tds.index[tds.index <= 2033], tds[tds.index <= 2033] / 1e9, lw=2, ls="--", label="Debt service (projected after " + str(ly) + ")")
ax.axvline(ly, color="grey", lw=.7); ax.set_ylabel("US$ billion"); ax.legend(frameon=False); ax.set_title("Pakistan external debt (World Bank IDS)")
fig.tight_layout(); fig.savefig(IMG / "allin_ids_debt.png"); plt.close(fig)
yy = list(yr.index)
fig, ax = plt.subplots(figsize=(8, 3.6))
ax.plot(yy, yr["mean"], marker="o", lw=2, label="Pakistan (mean quoted cost of sending $200, %)"); gw = pd.Series(D["rpw_world_mean_cost_by_year"]); gw.index = gw.index.astype(int)
ax.plot(gw.index[gw.index.isin(yy)], gw[gw.index.isin(yy)], marker="o", lw=2, label="All corridors"); ax.axhline(3, color="grey", ls=":", lw=1); ax.legend(frameon=False); ax.set_title("Remittance cost (World Bank RPW)")
fig.tight_layout(); fig.savefig(IMG / "allin_rpw_pk.png"); plt.close(fig)


D["series"] = {
    "lbs": [{"quarter": i, "claims_usd_bn": None if pd.isna(r.get("C")) else round(float(r["C"]) / 1e3, 2), "liabilities_usd_bn": None if pd.isna(r.get("L")) else round(float(r["L"]) / 1e3, 2)} for i, r in allc.iterrows() if i >= "2000-Q1"],
    "ids_debt": [{"year": int(y), "stock_usd_bn": round(float(tot[y]) / 1e9, 2) if y in tot.index and y <= ly else None, "service_usd_bn": round(float(tds[y]) / 1e9, 2) if y in tds.index else None, "projected": bool(y > ly)} for y in sorted(set(tot.index) | set(tds.index)) if y <= 2033],
    "rpw": [{"year": int(y), "pakistan": rb_, "all_corridors": D["rpw_world_mean_cost_by_year"].get(str(y))} for y, rb_ in D["rpw_cost_pct_by_year_mean"].items()],
}
# ---------- markdown ----------
_cc = q("""select left(l_rep_ctyreporting_country,2) r, try_cast(obs_valueobservation_value as double) v from bis.ws_cbs_pub
           where l_cp_countrycounterparty_country like 'PK:%' and l_measuremeasure like 'S:%' and left(l_positionbalance_sheet_position,1)='I' and left(l_cp_sectorcounterparty_sector,1)='A'
           and time_periodtime_period_or_range='2026-Q2' and left(cbs_basiscbs_reporting_basis,1)='F' and left(cbs_bank_typecbs_bank_type,2)='4R'
           and left(rem_maturityremaining_maturity,1)='A' and left(l_instrtype_of_instruments,1)='A' and left(curr_type_bookcurrency_type_of_booking_location,1)='T' and obs_valueobservation_value is not null""")
_tot = float(_cc[_cc.r == "5A"].v.iloc[0])
_by = _cc[_cc.r != "5A"].sort_values("v", ascending=False)
D["cbs_by_headquarters_country_2026Q2_usd_m"] = {r.r: round(r.v) for r in _by.head(8).itertuples()}
D["cbs_visible_share_pct"] = round(float(_by.v.sum() / _tot * 100), 1)
D["cbs_total_2026Q2_usd_m"] = round(_tot)
vis = float(by_c.v.sum())
D["visible_country_claims_share_pct"] = round(vis / float(allc.C.dropna().iloc[-1]) * 100, 1)
cs_ = D["claims_by_sector_latest"]
dc = D["ids_composition_latest_share_pct"]
dcb = D["ids_composition_latest_usd_bn"]
tc = D["ids_top_creditors_latest_usd_bn"]
tb = D["ids_total_external_debt_usd_bn"]
ds = D["ids_debt_service_usd_bn"]
dp = D["ids_debt_service_projection_2026_2030_usd_bn"]
rb = D["rpw_cost_pct_by_year_mean"]
gw = D["rpw_world_mean_cost_by_year"]
snd = D["rpw_cost_by_sender_latest_mean"]
cheap = sorted(snd.items(), key=lambda kv: kv[1][0])
md = f"""## D. Cross-border finance: banks, external debt, remittance costs

**Foreign banks' exposure to Pakistan (BIS locational banking statistics; Pakistan is a counterparty here, which I missed in an earlier pass).** Cross-border claims of BIS-reporting banks on Pakistan are US$ {D['lbs_claims_latest_usd_m'][1]/1e3:.1f}bn at {D['lbs_claims_latest_usd_m'][0]} against US$ {D['lbs_liabilities_latest_usd_m'][1]/1e3:.1f}bn of liabilities to Pakistan (net claims US$ {D['lbs_net_position_latest_usd_m']/1e3:.1f}bn). Claims peaked at US$ {D['lbs_claims_peak'][1]/1e3:.1f}bn in {D['lbs_claims_peak'][0]}, are {D['lbs_claims_5y_change_pct']}% over five years and {D['lbs_claims_yoy_latest_pct']}% year on year. {cs_['N']/cs_['A']*100:.0f}% of the claims are on non-banks and {cs_['B']/cs_['A']*100:.0f}% on banks. Country detail is mostly confidential in the locational data: the reporters whose figures are visible (largest: France US$ {D['claims_by_reporting_country_latest']['FR']}m, Hong Kong {D['claims_by_reporting_country_latest']['HK']}m, Switzerland {D['claims_by_reporting_country_latest']['CH']}m, United States {D['claims_by_reporting_country_latest']['US']}m) add up to only {D['visible_country_claims_share_pct']}% of the total, so no ranking is read from that table. The consolidated statistics are more open: of US$ {D['cbs_total_2026Q2_usd_m']:,}m of international claims at 2026-Q2, banks headquartered in {', '.join(f"{ {'CH': 'Switzerland', 'GB': 'the United Kingdom', 'FR': 'France', 'ES': 'Spain', 'SE': 'Sweden', 'JP': 'Japan'}.get(k, k)} US$ {v}m" for k, v in list(D['cbs_by_headquarters_country_2026Q2_usd_m'].items())[:6])} account for {D['cbs_visible_share_pct']}% (the United States is not shown and is presumably confidential). BIS consolidated statistics (a different, narrower basis: international claims of domestic banks on an immediate-counterparty basis) show US$ {D['cbs_international_claims_immediate_counterparty_latest'][1]/1e3:.1f}bn at {D['cbs_international_claims_immediate_counterparty_latest'][0]} against a peak of US$ {D['cbs_international_claims_immediate_counterparty_peak'][1]/1e3:.1f}bn ({D['cbs_international_claims_immediate_counterparty_peak'][0]}); the two BIS bases are not comparable in level.
- ![](img/allin_bis_lbs_pk.png)

**External debt (World Bank International Debt Statistics, to {D['ids_latest_actual_year']}).** Total external debt rose from US$ {tb[2000]}bn (2000) to {tb[2010]}bn (2010), {tb[2020]}bn (2020) and **{tb[2025]}bn (2025)**, {D['ids_external_debt_cagr_2000_latest_pct']}% a year. The IDS total equals WDI's external-debt figure exactly ({D['reconciliation_ids_vs_wdi_total_debt_latest'][0]} vs {D['reconciliation_ids_vs_wdi_total_debt_latest'][1]}) and the creditor-by-creditor rows add up to {D['ids_creditor_rows_sum_vs_total_pct']}% of the total. Composition: multilateral {dc['PPG multilateral']}% (US$ {dcb['PPG multilateral']}bn), bilateral {dc['PPG bilateral']}% ({dcb['PPG bilateral']}bn), private non-guaranteed {dc['PNG (private non-guaranteed)']}% ({dcb['PNG (private non-guaranteed)']}bn), IMF credit {dc['IMF credit']}% ({dcb['IMF credit']}bn), short-term {dc['short-term debt']}% ({dcb['short-term debt']}bn), bonds {dc['PPG bonds']}% ({dcb['PPG bonds']}bn), commercial banks {dc['PPG commercial banks']}%. Largest identified creditors: {'; '.join(f"{k} {v}bn" for k, v in list(tc.items())[:8])} (US$; 'Other Multiple Lenders' and 'Multiple Lenders' are pooled categories in the source). External debt is {D['wdi_external_debt_pct_gni'][str(D['ids_latest_actual_year'])]:.1f}% of GNI (2020: {D['wdi_external_debt_pct_gni']['2020']:.1f}%) and debt service takes {D['wdi_debt_service_pct_exports'][str(D['ids_latest_actual_year'])]:.1f}% of exports (2010: {D['wdi_debt_service_pct_exports']['2010']:.1f}%; 2020: {D['wdi_debt_service_pct_exports']['2020']:.1f}%).
- Debt service paid: US$ {ds[2015]}bn (2015), {ds[2020]}bn (2020), {ds[2022]}bn (2022), {ds[2025]}bn (2025). IDS **scheduled** service on existing debt is US$ {dp[2026]}bn in 2026, then {dp[2027]}bn, {dp[2028]}bn, {dp[2029]}bn and {dp[2030]}bn; the 2026 figure exceeds the whole stock of reserves at end-2024 (US$ {D['wdi_reserves_2024_usd_bn']}bn, WDI) and SBP's liquid reserves of US$ 26.4bn at Oct 2026 are only just above it. Scheduled service is what falls due on existing debt; it takes no account of new borrowing or rollovers, so it measures refinancing need and not the cash that must leave the country.
- ![](img/allin_ids_debt.png)

**Remittance costs into Pakistan (World Bank Remittance Prices Worldwide, {D['rpw_quotes']:,} provider quotes, {D['rpw_years'][0]}-{D['rpw_years'][1]}).** The mean quoted cost of sending US$ 200 to Pakistan fell from {rb[2016]}% (2016) to {rb[2025]}% (2025), against {gw['2016']}% to {gw['2025']}% averaged over all corridors in the database; {D['rpw_share_quotes_above_3pct_latest']}% of 2024-25 quotes are still above the 3% target. By sending country in 2024-25 the cheapest are {', '.join(f"{k} {v[0]}%" for k, v in cheap[:4])}; the most expensive are {', '.join(f"{k} {v[0]}%" for k, v in cheap[-4:])}. Banks charge {D['rpw_cost_by_firm_type_latest_mean']['Bank'][0]}% on average against {D['rpw_cost_by_firm_type_latest_mean']['Money Transfer Operator'][0]}% for money-transfer operators; by access point, a bank branch costs {D['rpw_cost_by_access_point_latest_mean']['Bank branch'][0]}% against {D['rpw_cost_by_access_point_latest_mean']['Internet'][0]}% online. The mean FX margin is {D['rpw_fx_margin_mean_latest']}%. These are surveyed quotes, not volume-weighted actual transactions. With remittances of US$ 41.6bn in FY2026 (SBP) the cost gap between channels is material; the cheapest corridors are Gulf senders and the cheapest access points are digital, which matters for a bank's digital remittance proposition (an observation from the data, not a tested recommendation).
- ![](img/allin_rpw_pk.png)
"""
save("part_d", md, D)
print(md)

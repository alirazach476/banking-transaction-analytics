"""Part E: global context: ECB (policy, inflation, euro-area banks vs Pakistan), BIS peers (policy rates, credit gaps, debt service), FRED (US)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *  # noqa

con = connect()
D: dict = {}
q = lambda s: con.execute(s).df()

# ---------- E1 ECB policy rates, inflation, FX, loans ----------
dfr = q("select time_period tp, obs_value v from ecb.fm where freq='D' and title = 'Deposit facility - date of changes (raw data) - Level' order by time_period")
dfr["v"] = pd.to_numeric(dfr.v, errors="coerce")
dfr["tp"] = pd.to_datetime(dfr.tp)
ch = dfr[dfr.v.diff().fillna(0) != 0]
D["ecb_deposit_rate_latest"] = [str(dfr.tp.iloc[-1].date()), float(dfr.v.iloc[-1])]
D["ecb_deposit_rate_peak"] = [str(dfr.loc[dfr.v.idxmax(), "tp"].date()), float(dfr.v.max())]
D["ecb_deposit_rate_trough"] = [str(dfr.loc[dfr.v.idxmin(), "tp"].date()), float(dfr.v.min())]
D["ecb_rate_changes_since_2022"] = [[str(r.tp.date()), float(r.v)] for r in ch[ch.tp >= "2022-01-01"].itertuples()]
hi = q("select time_period tp, obs_value v from ecb.hicp where _key='HICP.M.U2.N.000000.4D0.ANR' order by time_period")
hi["v"] = pd.to_numeric(hi.v, errors="coerce")
D["hicp_ea_latest"] = [hi.tp.iloc[-1], float(hi.v.iloc[-1])]
D["hicp_ea_peak_since_2020"] = [hi[hi.tp >= "2020-01"].sort_values("v").tp.iloc[-1], float(hi[hi.tp >= "2020-01"].v.max())]
D["hicp_ea_12m_ago"] = float(hi[hi.tp == str(int(hi.tp.iloc[-1][:4]) - 1) + hi.tp.iloc[-1][4:]].v.iloc[0])
D["hicp_ea_last6"] = {r.tp: float(r.v) for r in hi.tail(6).itertuples()}
mir = q("select title, time_period tp, obs_value v from ecb.mir where _key='MIR.M.U2.B.A2I.AM.R.A.2240.EUR.N' order by time_period")
D["mir_series_title"] = mir.title.iloc[0] if len(mir) else None
D["mir_latest"] = [mir.tp.iloc[-1], float(mir.v.iloc[-1])] if len(mir) else None
D["mir_2022_01"] = float(mir[mir.tp == "2022-01"].v.iloc[0]) if len(mir[mir.tp == "2022-01"]) else None
fxu = q("select time_period tp, obs_value v from ecb.exr where _key='EXR.M.USD.EUR.SP00.A' order by time_period")
fxi = q("select time_period tp, obs_value v from ecb.exr where _key='EXR.M.INR.EUR.SP00.A' order by time_period")
D["eurusd_latest"] = [fxu.tp.iloc[-1], round(float(fxu.v.iloc[-1]), 3)]
D["eurusd_low_since_2020"] = [fxu[fxu.tp >= "2020-01"].sort_values("v").tp.iloc[0], round(float(fxu[fxu.tp >= "2020-01"].v.min()), 3)]
D["eurinr_latest"] = [fxi.tp.iloc[-1], round(float(fxi.v.iloc[-1]), 2)]
loans = q("select time_period tp, obs_value v from ecb.bsi where _key='BSI.M.U2.Y.U.A20T.A.I.U2.2240.Z01.A' order by time_period")
D["ea_loans_to_private_nonmfi_growth_latest_pct"] = [loans.tp.iloc[-1], round(float(loans.v.iloc[-1]), 2)]

# ---------- E2 euro-area banks (SSM significant institutions) vs Pakistan ----------
def ssm(title_start):
    d = q(f"select time_period tp, obs_value v from ecb.sup where ref_area='B01' and rtrim(title) = '{title_start}, Significant institutions' and counterpart_sector='_Z' order by time_period")
    d["v"] = pd.to_numeric(d.v, errors="coerce")
    d = d.dropna().groupby("tp").v.first()
    return d
S = {"total capital ratio %": ssm("Total capital ratio"), "NPL ratio % (excl. cash balances)": ssm("Non-performing loans ratio (excl. cash balances)"), "ROE %": ssm("Return on equity (RoE)"),
     "ROA %": ssm("Return on assets (RoA)"), "LCR %": ssm("Liquidity coverage ratio")}
D["ssm_latest"] = {k: [s.index[-1], round(float(s.iloc[-1]), 2)] for k, s in S.items() if len(s)}
D["ssm_two_years_earlier"] = {k: [s.index[-9], round(float(s.iloc[-9]), 2)] for k, s in S.items() if len(s) > 9}
pk = json.load(open(PARTS / "part_a.json"))["all_banks_fsi"]
D["pakistan_all_banks_sep26"] = {"CAR %": pk["CAR"][-1], "NPL ratio %": pk["NPL ratio"][-1], "ROE after tax %": pk["ROE after tax"][-1], "ROA after tax %": pk["ROA after tax"][-1], "cost/income %": pk["Cost/income"][-1]}

# ---------- E3 BIS peers ----------
pol = q("""select left(ref_areareference_area,2) c, time_periodtime_period_or_range tp, try_cast(obs_valueobservation_value as double) v from bis.ws_cbpol
           where freqfrequency like 'M:%' and obs_valueobservation_value is not null""")
last = pol.groupby("c").tp.max()
latest_tp = last.value_counts().idxmax()
pl = pol[pol.tp == latest_tp].set_index("c").v
D["bis_policy_rate_month"] = latest_tp
D["bis_policy_n_central_banks"] = int(len(pl))
D["policy_rate_median_bis"] = round(float(pl.median()), 2)
D["policy_rate_top_bottom"] = {"highest": [(k, round(float(v), 2)) for k, v in pl.sort_values(ascending=False).head(5).items()], "lowest": [(k, round(float(v), 2)) for k, v in pl.sort_values().head(5).items()]}
sbp_now = 12.0
D["pakistan_policy_rate_oct2026"] = sbp_now
D["pakistan_rank_among_bis_plus_pk_high_to_low"] = int((pl > sbp_now).sum() + 1)
D["pakistan_rank_of"] = int(len(pl) + 1)
# real policy rate at 2025-12 using WDI 2025 inflation
iso = con.execute("select country_code iso3, \"2_alpha_code\" a2 from worldbank.d0037712_dr0095335_csv_file_wdicountry").df() if False else None
cc = q("select * from worldbank.d0037712_dr0095335_csv_file_wdicountry")
col2 = next(c for c in cc.columns if "2_alpha" in c or "2alpha" in c)
m = dict(zip(cc[col2], cc.country_code))
inf = q("select country_code, _2025 v from worldbank.d0037712_dr0095335_csv_file_wdicsv where indicator_code='FP.CPI.TOTL.ZG'").set_index("country_code").v
p25 = pol[pol.tp == "2025-12"].set_index("c").v
real = {c: float(p25[c] - float(inf[m[c]])) for c in p25.index if c in m and m[c] in inf.index and pd.notna(inf[m[c]])}
pk_real = 10.5 - float(inf["PAK"])
D["real_policy_rate_dec2025_pakistan"] = round(pk_real, 2)
D["real_policy_rate_dec2025_peer_median"] = round(float(np.median(list(real.values()))), 2)
D["real_policy_rate_rank_pakistan"] = int(sum(v > pk_real for v in real.values()) + 1)
D["real_policy_rate_n"] = len(real) + 1
D["real_rate_note"] = "policy rate at Dec-2025 minus WDI 2025 annual-average CPI inflation; mixes a point-in-time rate with an average inflation"
# credit gap and DSR: peers
cg = q("""select left(borrowers_ctyborrowers_country,2) c, time_periodtime_period_or_range tp, try_cast(obs_valueobservation_value as double) v from bis.ws_credit_gap
          where left(tc_borrowersborrowing_sector,1)='P' and left(cg_dtypecredit_gap_data_type,1)='C' and obs_valueobservation_value is not null""")
cgl = cg.sort_values("tp").groupby("c").tail(1).set_index("c")
D["credit_gap_latest_period_mode"] = cgl.tp.value_counts().idxmax()
D["credit_gap_peers"] = {k: round(float(cgl.loc[k, "v"]), 1) for k in ("IN", "ID", "TR", "CN", "BR", "ZA", "SA", "MX") if k in cgl.index}
D["credit_gap_countries_above_10pp"] = [k for k, v in cgl.v.items() if v > 10]
dsr = q("""select left(borrowers_ctyborrowers_country,2) c, time_periodtime_period_or_range tp, try_cast(obs_valueobservation_value as double) v from bis.ws_dsr
           where left(dsr_borrowersborrowers,1)='P' and obs_valueobservation_value is not null""")
dl = dsr.sort_values("tp").groupby("c").tail(1).set_index("c")
D["dsr_latest_peers"] = {k: round(float(dl.loc[k, "v"]), 1) for k in ("IN", "ID", "TR", "CN", "BR", "ZA", "SA", "MX") if k in dl.index}
D["dsr_highest_5"] = [(k, round(float(v), 1)) for k, v in dl.v.sort_values(ascending=False).head(5).items()]

# ---------- E4 FRED ----------
f = q("select observation_date d, cpiaucsl_pc1 v from external_fred.fred_cpiaucsl_pc1 order by 1")
f["v"] = pd.to_numeric(f.v, errors="coerce")
f = f.dropna(subset=["v"]).reset_index(drop=True)
D["us_cpi_yoy_latest"] = [str(f.d.iloc[-1])[:10], round(float(f.v.iloc[-1]), 2)]
_p = f[f.d >= "2020-01-01"]
D["us_cpi_yoy_peak_since_2020"] = [str(_p.loc[_p.v.idxmax(), "d"])[:10], round(float(_p.v.max()), 2)]
fr = q("select observation_date d, dfedtaru u, dfedtarl l, iorb, dff from external_fred.fred_daily_7day order by 1")
D["fed_target_upper_latest"] = [str(fr.d.iloc[-1])[:10], fr.u.dropna().iloc[-1]]
D["fed_funds_effective_latest"] = fr.dff.dropna().iloc[-1]
D["fred_rates_window"] = [str(fr.d.min())[:10], str(fr.d.max())[:10]]
mu = q("select region_name r, observation_date d, unemployment_rate_pct v from external_fred.metro_unemployment_rate_msa_long")
mu["v"] = pd.to_numeric(mu.v, errors="coerce")
ml = mu.dropna().sort_values("d").groupby("r").tail(1)
D["metro_unemployment_latest_date"] = str(ml.d.max())[:10]
D["metro_unemployment_n_metros"] = int(len(ml))
D["metro_unemployment_median_latest"] = round(float(ml.v.median()), 1)
D["metro_unemployment_highest3"] = [(r.r, round(r.v, 1)) for r in ml.sort_values("v", ascending=False).head(3).itertuples()]
D["metro_unemployment_lowest3"] = [(r.r, round(r.v, 1)) for r in ml.sort_values("v").head(3).itertuples()]


# ---------- markdown ----------
sl, s2 = D["ssm_latest"], D["ssm_two_years_earlier"]
pk = D["pakistan_all_banks_sep26"]
ch = D["ecb_rate_changes_since_2022"]
cut_trough = min(ch[10:], key=lambda x: x[1])
tb_ = D["policy_rate_top_bottom"]
cgp, dsp = D["credit_gap_peers"], D["dsr_latest_peers"]
nm = {"TR": "Turkiye", "RU": "Russia", "BR": "Brazil", "CO": "Colombia", "IS": "Iceland", "CH": "Switzerland", "TH": "Thailand", "JP": "Japan", "SE": "Sweden", "DK": "Denmark",
      "IN": "India", "ID": "Indonesia", "CN": "China", "ZA": "South Africa", "SA": "Saudi Arabia", "MX": "Mexico", "HK": "Hong Kong", "NO": "Norway", "NL": "Netherlands"}
md = f"""## E. Global context: euro area, other central banks, United States

**Euro area (ECB data to Nov 2026).** The ECB deposit rate is {D['ecb_deposit_rate_latest'][1]}% (20 Nov 2026): it peaked at {D['ecb_deposit_rate_peak'][1]}% in Sep 2023, was cut to {cut_trough[1]}% by Jun 2025, and has been raised twice since (2.25% in Jun 2026, 2.5% in Sep 2026). Euro-area HICP inflation is {D['hicp_ea_latest'][1]}% in {D['hicp_ea_latest'][0]}, up from {D['hicp_ea_12m_ago']}% a year earlier and from 2.8% in Jun 2026 (peak since 2020: {D['hicp_ea_peak_since_2020'][1]}% in {D['hicp_ea_peak_since_2020'][0]}). Corporate borrowing costs are {D['mir_latest'][1]}% (Sep 2026) against {D['mir_2022_01']}% in Jan 2022, and bank loans to the euro-area private non-MFI sector grow {D['ea_loans_to_private_nonmfi_growth_latest_pct'][1]}% a year. EUR/USD is {D['eurusd_latest'][1]} (Oct 2026; low of {D['eurusd_low_since_2020'][1]} in {D['eurusd_low_since_2020'][0]}); EUR/INR {D['eurinr_latest'][1]}. The ECB data has no Pakistani rupee series.

**Pakistani banks against euro-area significant banks (ECB supervisory statistics, {sl['total capital ratio %'][0]}, vs Pakistan Sep-2026).**
| Indicator | Euro-area significant banks | Pakistan, all banks |
|---|---|---|
| Capital ratio | {sl['total capital ratio %'][1]}% (total capital; {s2['total capital ratio %'][1]}% two years earlier) | {pk['CAR %']}% (CAR) |
| NPL ratio | {sl['NPL ratio % (excl. cash balances)'][1]}% | {pk['NPL ratio %']}% |
| Return on equity | {sl['ROE %'][1]}% | {pk['ROE after tax %']}% (after tax) |
| Return on assets | {sl['ROA %'][1]}% | {pk['ROA after tax %']}% (after tax) |
| Liquidity | LCR {sl['LCR %'][1]}% | liquid assets about 103% of deposits (a different measure) |
Pakistan's banks carry a bad-loan ratio about 2.6 times the euro-area level and earn a return on equity about 1.7 times higher, with comparable capital. Definitions differ (the euro-area figures are supervisory, significant institutions only; Pakistan's NPL and ROE definitions are SBP's), so this is a rough comparison.

**Policy rates across central banks (BIS, {D['bis_policy_rate_month']}, {D['bis_policy_n_central_banks']} central banks).** The median policy rate is {D['policy_rate_median_bis']}%; the highest are {', '.join(f"{nm.get(k, k)} {v}%" for k, v in tb_['highest'])}. Pakistan's 12.0% (SBP, Oct 2026) would rank {D['pakistan_rank_among_bis_plus_pk_high_to_low']} of {D['pakistan_rank_of']}. In real terms (Dec-2025 policy rate less 2025 average CPI inflation from the World Bank) Pakistan's rate is {D['real_policy_rate_dec2025_pakistan']}%, third highest of {D['real_policy_rate_n']} countries, against a median of {D['real_policy_rate_dec2025_peer_median']}%. (This mixes a point-in-time rate with an annual-average inflation rate.) The United States' policy rate is 4.0% (Fed target upper bound, 19 Nov 2026; effective funds rate {D['fed_funds_effective_latest']}%) against 2.5% in the euro area, so Pakistan's policy rate sits 8 points above the Fed's with the rupee stable near 277 (an observation, not a test of any link).

**Credit conditions elsewhere (BIS).** BIS has no credit-to-GDP gap or debt-service-ratio series for Pakistan. Peers' private-sector credit-to-GDP gaps ({D['credit_gap_latest_period_mode']}, percentage points): {', '.join(f"{nm.get(k, k)} {v}" for k, v in cgp.items())}; none is above +10 (the usual warning level). Private-sector debt-service ratios: {', '.join(f"{nm.get(k, k)} {v}%" for k, v in dsp.items())}; highest in the database: {', '.join(f"{nm.get(k, k)} {v}%" for k, v in D['dsr_highest_5'])}.

**United States (FRED).** CPI inflation is {D['us_cpi_yoy_latest'][1]}% a year ({D['us_cpi_yoy_latest'][0][:7]}); peak since 2020 {D['us_cpi_yoy_peak_since_2020'][1]}% ({D['us_cpi_yoy_peak_since_2020'][0][:7]}). Metropolitan unemployment ({D['metro_unemployment_n_metros']} metros, {D['metro_unemployment_latest_date'][:7]}): median {D['metro_unemployment_median_latest']}%, highest {', '.join(f"{k} {v}%" for k, v in D['metro_unemployment_highest3'])}, lowest {', '.join(f"{k} {v}%" for k, v in D['metro_unemployment_lowest3'])}. The FRED rates files in the warehouse cover only {D['fred_rates_window'][0]} to {D['fred_rates_window'][1]}. This is background context; it is not linked to Pakistan or to the synthetic payments data.
"""
save("part_e", md, D)
print(md)

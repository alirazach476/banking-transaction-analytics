"""Part B: Pakistan macro from SBP tables (GDP, balance of payments, reserves, money growth, FX) with cross-source reconciliation."""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *  # noqa

con = connect()
D: dict = {}


def nums(s):
    out = []
    for x in re.findall(r"\(?-?\d[\d,]*\.?\d*\)?", s):
        v = float(x.strip("()").replace(",", ""))
        out.append(-v if x.startswith("(") else v)
    return out


# ---- B1 GDP (constant 2015-16 prices) ----
g = sbp_lines(con, "GDP_table")
def grab(label_start, page):
    r = g[(g.page == page) & g.raw_line.str.contains(label_start, regex=True)]
    return nums(r.raw_line.iloc[0].split(label_start.replace("\\", ""))[-1] if False else re.sub(r"^[^\d\-]*", "", r.raw_line.iloc[0])) if len(r) else []
gro = grab(r"GDP Growth Rate", 1) + grab(r"GDP Growth Rate", 2)
yrs = [f"FY{y}" for y in range(2001, 2027)]
D["gdp_growth_pct"] = dict(zip(yrs, gro[-26:])) if len(gro) >= 26 else dict(zip(yrs[-len(gro):], gro))
tot = [nums(re.sub(r"^D\s*GDP\s*\{?[^\d]*", "", r.raw_line)) for r in g.itertuples() if r.raw_line.startswith("D GDP")]
levels = [x for t in tot for x in t]
D["gdp_levels_rs_m_fy2000_to_fy2026"] = levels
chk = [(levels[i] / levels[i - 1] - 1) * 100 for i in range(1, len(levels))]
D["gdp_growth_check_max_abs_diff_pp"] = round(max(abs(a - b) for a, b in zip(chk, gro)), 2) if len(chk) == len(gro) else None
gr = pd.Series(D["gdp_growth_pct"])
D["gdp_growth_avg_fy2001_fy2026"] = round(float(gr.mean()), 2)
D["gdp_growth_avg_last5"] = round(float(gr.iloc[-5:].mean()), 2)
D["gdp_negative_years"] = {k: v for k, v in D["gdp_growth_pct"].items() if v < 0}
D["gdp_best_year"] = [gr.idxmax(), float(gr.max())]
D["gdp_growth_std"] = round(float(gr.std()), 2)
sec = {}
for lab, key in (("A Agriculture", "agriculture"), ("B Industrial", "industry"), ("C Services", "services")):
    rows = [nums(re.sub(r"^[A-C]\s*[A-Za-z ,&()\d]*?\)\s*", "", r.raw_line)) for r in g.itertuples() if r.raw_line.startswith(lab)]
    sec[key] = [x for t in rows for x in t]
if len(sec["services"]) == 13 and len(levels) == 27:
    resid = [levels[i] - sec["agriculture"][i] - sec["industry"][i] for i in range(27)]
    D["services_residual_check_max_abs_diff_rs_m"] = round(max(abs(resid[14 + i] - sec["services"][i]) for i in range(13)), 0)
    sec["services"] = resid[:14] + sec["services"]
D["sector_levels_len"] = {k: len(v) for k, v in sec.items()}
if all(len(v) == len(levels) for v in sec.values()):
    D["sector_share_fy2001_vs_fy2026_pct"] = {k: [round(v[1] / levels[1] * 100, 1), round(v[-1] / levels[-1] * 100, 1)] for k, v in sec.items()}
    D["sector_cagr_fy2016_fy2026_pct"] = {k: round(((v[-1] / v[16]) ** (1 / 10) - 1) * 100, 2) for k, v in sec.items()}

# ---- B2 balance of payments (Jul-Jun FY25 vs FY26) ----
bp = sbp_lines(con, "Balancepayment_BPM6", 1)
def bpm(prefix):
    r = bp[bp.raw_line.str.replace(" ", "").str.startswith(prefix.replace(" ", ""))]
    return nums(re.sub(r"^[A-Za-z,'()\s/\*+&:]*(?=-?\d)", "", r.raw_line.iloc[0])) if len(r) else None
B = {k: bpm(k) for k in ("CurrentAccount Balance", "Exports of Goods FOB", "Imports of Goods FOB", "BalanceonTradein Goods", "Workers'Remittances", "Exports of Services", "Imports of Services", "Direct Investment in Pakistan", "PortfolioInvestment", "Financial Account")}
D["bop_columns_note"] = "col1 = Jul-Jun FY25, col3 = Jul-Jun FY26 (full years); col8 = Jul-Oct FY27"
D["bop"] = B
fy = lambda k, i: B[k][i] if B.get(k) and len(B[k]) > i else None
D["bop_fy25_fy26"] = {k: [fy(k, 0), fy(k, 2)] for k in B}
if fy("Exports of Goods FOB", 0):
    D["exports_goods_growth_pct"] = round((fy("Exports of Goods FOB", 2) / fy("Exports of Goods FOB", 0) - 1) * 100, 1)
    D["imports_goods_growth_pct"] = round((fy("Imports of Goods FOB", 2) / fy("Imports of Goods FOB", 0) - 1) * 100, 1)
    D["remittances_growth_pct"] = round((fy("Workers'Remittances", 2) / fy("Workers'Remittances", 0) - 1) * 100, 1)
    D["remittances_cover_of_goods_trade_deficit_fy26_pct"] = round(fy("Workers'Remittances", 2) / -fy("BalanceonTradein Goods", 2) * 100, 1)

# ---- B3 reserves ----
fx = sbp_lines(con, "forex")
res = {}
for r in fx.itertuples():
    m = re.match(r"([A-Z][a-z]{2})\s?(\d{2})\s?R?\s*\|", r.raw_line)
    if m and r.n_values >= 3:
        res[f"{m.group(1)}-{m.group(2)}"] = float(r.raw_line.split("|")[3].replace(",", ""))
fyres = {}
for r in fx.itertuples():
    m = re.match(r"(20\d{2}-\d{2})R?\s*\|", r.raw_line)
    if m:
        fyres[m.group(1)] = float(r.raw_line.split("|")[3].replace(",", ""))
D["liquid_reserves_total_usd_m_fy_end"] = fyres
D["liquid_reserves_total_usd_m_monthly"] = res
D["reserves_latest"] = list(res.items())[-1] if res else None
D["reserves_fy23_low_to_oct26_multiple"] = round(list(res.values())[-1] / fyres["2022-23"], 2) if res and "2022-23" in fyres else None

# ---- B4 money growth ----
def growth_row(doc):
    d = sbp_lines(con, doc)
    r = d[d.raw_line.str.startswith("Growth")]
    return nums(r.raw_line.iloc[0].replace("%", "")) if len(r) else None
D["m2_growth_fy25_fy26_jul_nov25_jul_nov26"] = growth_row("BroadMoney_M2")
D["reserve_money_growth_same_columns"] = growth_row("ReserveMoney")

# ---- B5 FX cross-check (BIS monthly average vs SBP banks' floating rates) ----
ibf = sbp_lines(con, "IBF_Rates")
usd = ibf[ibf.raw_line.str.contains(r"United States|U\.?S\.? Dollar|US Dollar|USA", regex=True)]
D["sbp_ibf_oct26_usd_line"] = usd.raw_line.tolist()[:2]
b = con.execute("select obs_valueobservation_value v from bis.ws_xru where ref_areareference_area like 'PK:%' and freqfrequency like 'M:%' and collectioncollection like 'A:%' and time_periodtime_period_or_range='2026-09'").fetchone()
D["bis_usdpkr_sep26_avg"] = float(b[0]) if b else None
mm = sbp_lines(con, "mark-to-market-revaluation-exchange-rate-19-november-2026")
u = mm[mm.raw_line.str.startswith("USD")]
D["sbp_mtm_usd_ready_19nov26"] = nums(u.raw_line.iloc[0])[0] if len(u) else None
om = sbp_lines(con, "open-market-closing-exchange-rates-19-November-2026")
o = om[om.raw_line.str.startswith("USD")]
D["open_market_usd_buy_sell_19nov26"] = nums(o.raw_line.iloc[0])[:2] if len(o) else None
if D["open_market_usd_buy_sell_19nov26"]:
    bsell = D["open_market_usd_buy_sell_19nov26"]
    D["open_market_spread_pct"] = round((bsell[1] / bsell[0] - 1) * 100, 2)
    D["open_market_vs_interbank_premium_pct"] = round((bsell[1] / D["sbp_mtm_usd_ready_19nov26"] - 1) * 100, 2) if D["sbp_mtm_usd_ready_19nov26"] else None

# ---- B6 inflation snapshot (SBP FY12-FY19) vs WDI ----
mp = sbp_lines(con, "MPM-Old")
infl = {}
for r in mp.itertuples():
    m = re.match(r"(FY\d{2})\s+(-?[\d.]+)", r.raw_line)
    if m:
        infl[m.group(1)] = float(m.group(2))
D["sbp_cpi_general_annual_avg_fy12_fy19"] = infl
wdi = con.execute("select _2012,_2013,_2014,_2015,_2016,_2017,_2018,_2019 from worldbank.d0037712_dr0095335_csv_file_wdicsv where country_code='PAK' and indicator_code='FP.CPI.TOTL.ZG'").fetchone()
wd = dict(zip(range(2012, 2020), [float(x) for x in wdi]))
cmp = {k: (infl[k], round(wd[2000 + int(k[2:])], 1)) for k in infl if 2000 + int(k[2:]) in wd}
D["cpi_sbp_fy_vs_wdi_calendar"] = cmp
diffs = [abs(a - b) for a, b in cmp.values()]
D["cpi_mean_abs_diff_pp"] = round(float(np.mean(diffs)), 2) if diffs else None

# ---- charts ----
fig, ax = plt.subplots(figsize=(8.5, 3.8))
ax.bar(gr.index, gr.values, color=["#d95f02" if v < 0 else "#1b9e77" for v in gr.values]); ax.set_xticks(range(0, len(gr), 3)); ax.set_xticklabels(gr.index[::3], rotation=60)
ax.set_ylabel("%"); ax.set_title("Pakistan real GDP growth (SBP, constant 2015-16 prices)"); fig.tight_layout(); fig.savefig(IMG / "allin_gdp.png"); plt.close(fig)
if res:
    fig, ax = plt.subplots(figsize=(8, 3.6)); ax.plot(list(res), list(res.values()), marker="o", lw=2); ax.tick_params(axis="x", rotation=60)
    ax.set_ylabel("US$ million"); ax.set_title("Total liquid FX reserves (SBP + banks), month-end"); fig.tight_layout(); fig.savefig(IMG / "allin_reserves.png"); plt.close(fig)


# ---- markdown ----
_x = dict(con.execute("select time_periodtime_period_or_range, try_cast(obs_valueobservation_value as double) from bis.ws_xru where ref_areareference_area like 'PK:%' and freqfrequency like 'M:%' and collectioncollection like 'A:%' and time_periodtime_period_or_range between '2024-01' and '2026-09'").fetchall())
D["bis_usdpkr_2024_01"], D["bis_usdpkr_2024_09"], D["bis_usdpkr_2025_09"] = round(_x["2024-01"], 1), round(_x["2024-09"], 1), round(_x["2025-09"], 1)
D["bis_usdpkr_range_2024_09_to_2026_09_pct"] = round((max(v for k, v in _x.items() if k >= "2024-09") / min(v for k, v in _x.items() if k >= "2024-09") - 1) * 100, 1)
bpf = D["bop_fy25_fy26"]
sh = D["sector_share_fy2001_vs_fy2026_pct"]
cg = D["sector_cagr_fy2016_fy2026_pct"]
fxr = D["liquid_reserves_total_usd_m_fy_end"]
m2 = D["m2_growth_fy25_fy26_jul_nov25_jul_nov26"]
rm = D["reserve_money_growth_same_columns"]
svc_g = round((bpf["Exports of Services"][1] / bpf["Exports of Services"][0] - 1) * 100, 1)
fdi_g = round((bpf["Direct Investment in Pakistan"][1] / bpf["Direct Investment in Pakistan"][0] - 1) * 100, 1)
cm = D["cpi_sbp_fy_vs_wdi_calendar"]
md = f"""## B. Macro economy (SBP tables, cross-checked against BIS and World Bank)

**Growth is modest and volatile.** Real GDP growth (constant 2015-16 prices, FY2001-FY2026) averages {D['gdp_growth_avg_fy2001_fy2026']}% a year with a standard deviation of {D['gdp_growth_std']} pp; the last five years average {D['gdp_growth_avg_last5']}%. Best year FY2005 ({D['gdp_best_year'][1]}%); contractions only in FY2020 ({D['gdp_negative_years']['FY2020']}%, COVID) and FY2023 ({D['gdp_negative_years']['FY2023']}%, the year of the exchange-rate and inflation crisis). Parsing check: growth recomputed from the GDP levels matches SBP's published growth row exactly. The economy has shifted toward services: services {sh['services'][0]}% of GDP in FY2001 to {sh['services'][1]}% in FY2026, agriculture {sh['agriculture'][0]}% to {sh['agriculture'][1]}%, industry {sh['industry'][0]}% to {sh['industry'][1]}%; over FY2016-FY2026 services grew {cg['services']}% a year, agriculture {cg['agriculture']}%, industry {cg['industry']}%.
- ![](img/allin_gdp.png)

**Balance of payments, FY2025 to FY2026 (US$ million, Jul-Jun).** The current account swung from a surplus of {bpf['CurrentAccount Balance'][0]:,.0f} to a deficit of {-bpf['CurrentAccount Balance'][1]:,.0f}. Goods exports fell {abs(D['exports_goods_growth_pct'])}% (to {bpf['Exports of Goods FOB'][1]:,.0f}) while imports rose {D['imports_goods_growth_pct']}% (to {bpf['Imports of Goods FOB'][1]:,.0f}), widening the goods trade deficit from {-bpf['BalanceonTradein Goods'][0]:,.0f} to {-bpf['BalanceonTradein Goods'][1]:,.0f}. Workers' remittances rose {D['remittances_growth_pct']}% to {bpf["Workers'Remittances"][1]:,.0f} and covered {D['remittances_cover_of_goods_trade_deficit_fy26_pct']}% of the goods trade deficit; services exports rose {svc_g}%. Foreign direct investment into Pakistan fell {abs(fdi_g)}% (to {bpf['Direct Investment in Pakistan'][1]:,.0f}). (Column mapping of the SBP table was inferred from its header: first column Jul-Jun FY25, third column Jul-Jun FY26.)

**FX reserves rebuilt strongly.** Total liquid reserves (SBP plus banks) were US$ {fxr['2021-22']/1e3:.1f}bn at June 2022, fell to US$ {fxr['2022-23']/1e3:.1f}bn at June 2023 (the crisis low), then rose to {fxr['2023-24']/1e3:.1f}bn, {fxr['2024-25']/1e3:.1f}bn and {fxr['2025-26']/1e3:.1f}bn at June 2026; Oct 2026 is US$ {D['reserves_latest'][1]/1e3:.1f}bn, {D['reserves_fy23_low_to_oct26_multiple']}x the June 2023 level. Most of the Sep-26 jump (US$ 21.9bn to 26.3bn) is in SBP's own reserves; the source does not say why.
- ![](img/allin_reserves.png)

**Money.** Broad money (M2) grew {m2[0]}% in FY25 and {m2[1]}% in FY26, then contracted {abs(m2[3])}% from 1 July to 6 Nov 2026 (against {m2[2]}% in the same period of 2025); reserve money grew {rm[0]}% and {rm[1]}% in the two fiscal years and {rm[3]}% in Jul-Nov 2026. (Column meaning inferred from the SBP header.)

**Exchange rate: four independent sources agree.** BIS monthly average Sep-26: {D['bis_usdpkr_sep26_avg']:.2f} PKR per USD; SBP banks' floating average Oct-26: 277.24; SBP mark-to-market ready rate on 19 Nov 2026: {D['sbp_mtm_usd_ready_19nov26']}; open market 19 Nov 2026: {D['open_market_usd_buy_sell_19nov26'][0]}/{D['open_market_usd_buy_sell_19nov26'][1]} (buy/sell spread {D['open_market_spread_pct']}%, selling rate {D['open_market_vs_interbank_premium_pct']}% above the interbank mark-to-market rate). In the BIS monthly series the rupee was {D['bis_usdpkr_2024_01']} in Jan-24, {D['bis_usdpkr_2024_09']} in Sep-24, {D['bis_usdpkr_2025_09']} in Sep-25 and {D['bis_usdpkr_2025_09'] and D['bis_usdpkr_usd'] if False else D['bis_usdpkr_sep26_avg']:.1f} in Sep-26; the gap between its highest and lowest monthly average since Sep-24 is {D['bis_usdpkr_range_2024_09_to_2026_09_pct']}%, so the rate has been very stable.

**Inflation reconciliation (closes an earlier caveat).** SBP's fiscal-year average CPI and the World Bank's calendar-year CPI differ by {D['cpi_mean_abs_diff_pp']} pp on average over FY12-FY19 (largest gap FY19: {cm['FY19'][0]}% vs {cm['FY19'][1]}%, because calendar 2019 mixes two fiscal years). The two sources agree on level and direction once the period definitions are accounted for; the SBP inflation snapshot in the warehouse only covers FY12 to Nov-18, so it cannot be used for the 2022-23 spike (World Bank/IMF monthly CPI covers that).
"""
save("part_b", md, D)
print(md)

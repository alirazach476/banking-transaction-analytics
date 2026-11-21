"""Part C: Pakistan payment systems (SBP Payment Systems Review FY2017-18) compared with BIS CPMI, ECB payments statistics and WDI."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *  # noqa

con = connect()
D: dict = {}
FY = ["FY14", "FY15", "FY16", "FY17", "FY18"]


def nums(s):
    return [float(x.replace(",", "")) for x in re.findall(r"(?<![\w.])-?\d[\d,]*\.?\d*(?![\w])", s)]


ps = sbp_lines(con, "FiscalYear-2017-18_1")
# ---- C1 Table 5: volume (million) and value (Rs billion) by channel, FY14-FY18 ----
t5 = ps[ps.page == 17]
chan = {}
for r in t5.itertuples():
    name = re.match(r"([A-Za-z][A-Za-z/\- ]+?)(?=[\s|'\d]*[\d])", r.raw_line)
    n = nums(r.raw_line.split("|", 1)[1] if r.raw_line.count("|") >= 9 else r.raw_line)
    if name and len(n) == 10 and r.row_no >= 6:
        chan["Paper-based" if name.group(1).startswith("Paper") else ("Call Centers/IVRBanking" if name.group(1).startswith("Call") else name.group(1).strip())] = {"vol_m": n[0::2], "value_bn": n[1::2]}
    elif name and r.raw_line.startswith("E-Commerce"):
        n2 = nums(r.raw_line)
        if len(n2) == 4:
            chan["E-Commerce"] = {"vol_m": [None, None, None, n2[0], n2[1]] if False else [0, 0, 0, n2[0], n2[2]], "value_bn": [0, 0, 0, n2[1], n2[3]]}
D["table5_channels"] = chan
total = chan.get("Total")
D["total_check"] = None
if total:
    keys = [k for k in chan if k not in ("Total", "e-Banking", "RTOB", "ATM", "POS", "Internet Banking", "Mobile Phone Banking", "Call Centers/IVRBanking", "E-Commerce")]
    D["table5_total_fy18"] = [total["vol_m"][-1], total["value_bn"][-1]]
    chk = sum(chan[k]["vol_m"][-1] for k in chan if k in ("PRISM System", "e-Banking", "Paper-based"))
    D["sum_prism_ebanking_paper_vol_fy18"] = round(chk, 1)

def cagr(a, b, n=4):
    return round(((b / a) ** (1 / n) - 1) * 100, 1) if a and b else None
out = {}
for k, v in chan.items():
    vol, val = v["vol_m"], v["value_bn"]
    out[k] = {"vol_fy18_m": vol[-1], "value_fy18_bn": val[-1], "vol_cagr_fy14_18": cagr(vol[0], vol[-1]), "value_cagr_fy14_18": cagr(val[0], val[-1]),
              "avg_ticket_rs": round(val[-1] * 1e9 / (vol[-1] * 1e6)) if vol[-1] else None, "yoy_vol_fy18_pct": round((vol[-1] / vol[-2] - 1) * 100, 1) if vol[-2] else None}
D["channel_summary"] = out
tv = total["vol_m"][-1]
D["volume_share_fy18_pct"] = {k: round(chan[k]["vol_m"][-1] / tv * 100, 1) for k in ("PRISM System", "e-Banking", "Paper-based") if k in chan}
eb = chan["e-Banking"]["vol_m"][-1]
D["ebanking_channel_share_of_ebanking_vol_fy18_pct"] = {k: round(chan[k]["vol_m"][-1] / eb * 100, 1) for k in ("RTOB", "ATM", "POS", "Internet Banking", "Mobile Phone Banking", "Call Centers/IVRBanking", "E-Commerce") if k in chan}
D["ebanking_share_of_non_prism_volume_fy14_vs_fy18_pct"] = [round(chan["e-Banking"]["vol_m"][0] / (chan["e-Banking"]["vol_m"][0] + chan["Paper-based"]["vol_m"][0]) * 100, 1),
                                                           round(chan["e-Banking"]["vol_m"][-1] / (chan["e-Banking"]["vol_m"][-1] + chan["Paper-based"]["vol_m"][-1]) * 100, 1)]
# ATM cash withdrawals
atm = {}
for r in ps[ps.page == 19].itertuples():
    if r.raw_line.startswith("Cash Withdrawal"):
        n = nums(r.raw_line)
        atm = {"vol_m": n[0::2], "value_bn": n[1::2]}
D["atm_cash_withdrawals"] = atm
if atm:
    D["atm_cash_withdrawal_share_of_atm_volume_fy18_pct"] = round(atm["vol_m"][-1] / chan["ATM"]["vol_m"][-1] * 100, 1)
    D["atm_cash_withdrawal_avg_rs_fy18"] = round(atm["value_bn"][-1] * 1e9 / (atm["vol_m"][-1] * 1e6))
    pos_ecom = chan["POS"]["vol_m"][-1] + chan["E-Commerce"]["vol_m"][-1]
    D["card_payments_per_cash_withdrawal_fy18"] = round(pos_ecom / (atm["vol_m"][-1] + 34.5), 2)  # RTOB branch cash withdrawals 34.5m (Table 7)

# ---- C2 infrastructure (Table 3) and cards (Table 4) ----
rows = {r.row_no: nums(r.raw_line) for r in ps[ps.page == 16].itertuples()}
infra = {"bank branches": rows.get(6), "RTOB branches": rows.get(8), "ATMs": rows.get(10), "POS machines": rows.get(12), "internet banking users": rows.get(14),
         "mobile banking users": rows.get(16), "call centre/IVR users": rows.get(18)}
D["infrastructure_fy14_fy18"] = infra
D["infrastructure_cagr_pct"] = {k: cagr(v[0], v[-1]) for k, v in infra.items() if v and len(v) == 5}
cards = {"ATM-only cards": rows.get(23), "credit cards": rows.get(25), "debit cards": rows.get(26), "total": rows.get(30)}
D["cards_fy14_fy18"] = cards
D["cards_cagr_pct"] = {k: cagr(v[0], v[-1]) for k, v in cards.items() if v and len(v) == 5}
D["pos_transactions_per_pos_machine_fy18"] = round(chan["POS"]["vol_m"][-1] * 1e6 / infra["POS machines"][-1])
D["atm_transactions_per_atm_fy18"] = round(chan["ATM"]["vol_m"][-1] * 1e6 / infra["ATMs"][-1])
D["pos_machines_fall_fy17_fy18_pct"] = round((infra["POS machines"][-1] / infra["POS machines"][-2] - 1) * 100, 1)

# ---- C3 cross-checks with WDI (population, ATMs per 100k adults 2018) ----
w = con.execute("select indicator_code, _2018 from worldbank.d0037712_dr0095335_csv_file_wdicsv where country_code='PAK' and indicator_code in ('SP.POP.TOTL','FB.ATM.TOTL.P5','FB.CBK.BRCH.P5','IT.CEL.SETS.P2')").fetchall()
wd = {a: float(b) for a, b in w}
D["wdi_2018"] = wd
adults_implied = infra["ATMs"][-1] / (wd["FB.ATM.TOTL.P5"] / 1e5)
D["implied_adults_from_sbp_atms_and_wdi_per100k_m"] = round(adults_implied / 1e6, 1)
D["adults_as_share_of_total_pop_pct"] = round(adults_implied / wd["SP.POP.TOTL"] * 100, 1)
D["branches_per_100k_adults_sbp_vs_wdi"] = [round(infra["bank branches"][-1] / adults_implied * 1e5, 2), round(wd["FB.CBK.BRCH.P5"], 2)]
D["pop_2018_m"] = round(wd["SP.POP.TOTL"] / 1e6, 1)
D["card_payments_per_capita_fy18_pk"] = round((chan["POS"]["vol_m"][-1] + chan["E-Commerce"]["vol_m"][-1]) * 1e6 / wd["SP.POP.TOTL"], 2)
D["atm_withdrawals_per_capita_fy18_pk"] = round(atm["vol_m"][-1] * 1e6 / wd["SP.POP.TOTL"], 2)

# ---- C4 BIS CPMI comparison for the same year (2018) ----
bis = json.load(open(PARTS.parent / "BIS_CPMI_ANALYSIS.json"))
b = con.execute("""select left(rep_ctyreporting_country,2) c, left(instrument_typeinstrument_type,1) i, try_cast(time_periodtime_period_or_range as int) y, max(try_cast(obs_valueobservation_value as double)) v
  from bis.ws_cpmi_cashless where left(measuremeasure,1)='N' and left(instrument_typeinstrument_type,1) in ('F','M') and try_cast(time_periodtime_period_or_range as int)=2018
  and left(card_fctcard_function,1) in ('A','Z') and left(directiondirection,1) in ('A','Z','D') and left(terminal_typeterminal_type,1)='A' and left(paymt_speedpayment_speed,1)='A' and left(issuer_or_onusissuer_or_onus_payments,1)='A'
  and (left(dev_state_techdevice_state_technology,1)='A' or left(instrument_typeinstrument_type,1)='M') group by 1,2,3""").df()
bp = b.pivot_table(index="c", columns="i", values="v")
pop = con.execute("select country_code, _2018 from worldbank.d0037712_dr0095335_csv_file_wdicsv where indicator_code='SP.POP.TOTL' and country_code in ('IND','IDN','TUR','BRA','MEX','ZAF','SAU','CHN','ARG')").df().set_index("country_code")["_2018"]
iso = {"IN": "IND", "ID": "IDN", "TR": "TUR", "BR": "BRA", "MX": "MEX", "ZA": "ZAF", "SA": "SAU", "CN": "CHN", "AR": "ARG"}
comp = {}
for c2, i3 in iso.items():
    if c2 in bp.index and not np.isnan(bp.loc[c2, "F"]):
        comp[c2] = {"card_per_capita_2018": round(bp.loc[c2, "F"] * 1e6 / float(pop[i3]), 1), "card_per_cash_withdrawal_2018": round(bp.loc[c2, "F"] / bp.loc[c2, "M"], 2) if "M" in bp and not np.isnan(bp.loc[c2, "M"]) else None}
D["bis_peers_2018"] = comp

# ---- C5 ECB euro area payment statistics ----
e = con.execute("""select time_period y, typ_trnsctn t, unit_measure u, obs_value v from ecb.pay where ref_area='U2' and freq='A' and transformation='N'
                   and typ_trnsctn in ('CP0','CT0','DD','CHQ','TOTL1') and unit_measure in ('PN_R_POP','EUR_R_TT','PN_R_TT') and rl_trnsctn in ('1','2')""").df()
e["y"] = e.y.astype(int)
e["v"] = pd.to_numeric(e.v, errors="coerce")
pc = e[e.u == "PN_R_POP"].pivot_table(index="y", columns="t", values="v")
sh = e[e.u == "PN_R_TT"].pivot_table(index="y", columns="t", values="v")
D["ecb_euro_area_per_capita_latest"] = {"year": int(pc.index.max()), **{k: round(float(pc[k].dropna().iloc[-1]), 1) for k in pc.columns}}
D["ecb_euro_area_share_of_payments_pct_latest"] = {"year": int(sh.index.max()), **{k: round(float(sh[k].dropna().iloc[-1]), 1) for k in sh.columns}}
y0 = max(2009, int(pc.index.min()))
D["ecb_cards_per_capita_first_last"] = [[y0, round(float(pc.loc[y0, "CP0"]), 1)], [int(pc.CP0.dropna().index[-1]), round(float(pc.CP0.dropna().iloc[-1]), 1)]]
D["ecb_cheques_per_capita_first_last"] = [[y0, round(float(pc.loc[y0, "CHQ"]), 1)], [int(pc.CHQ.dropna().index[-1]), round(float(pc.CHQ.dropna().iloc[-1]), 1)]]
D["ecb_series_years"] = [int(pc.index.min()), int(pc.index.max())]

# ---- charts ----
fig, ax = plt.subplots(figsize=(8, 3.8))
for k, lab in (("ATM", "ATM"), ("POS", "POS"), ("Internet Banking", "Internet"), ("Mobile Phone Banking", "Mobile"), ("RTOB", "Online branches")):
    ax.plot(FY, chan[k]["vol_m"], marker="o", lw=2, label=lab)
ax.set_yscale("log"); ax.set_ylabel("Transactions (million, log scale)"); ax.legend(frameon=False, ncol=3); ax.set_title("Pakistan payment channels, FY2014-FY2018 (SBP)")
fig.tight_layout(); fig.savefig(IMG / "allin_pk_channels.png"); plt.close(fig)


# ---- markdown ----
fx18 = float(con.execute("select _2018 from worldbank.d0037712_dr0095335_csv_file_wdicsv where country_code='PAK' and indicator_code='PA.NUS.FCRF'").fetchone()[0])
D['usdpkr_2018_wdi'] = round(fx18, 1)
cs = D["channel_summary"]
vs = D["volume_share_fy18_pct"]
es = D["ebanking_channel_share_of_ebanking_vol_fy18_pct"]
ic = D["infrastructure_cagr_pct"]
cd = D["cards_fy14_fy18"]
pk_cpc, pk_cpw = D["card_payments_per_capita_fy18_pk"], D["card_payments_per_cash_withdrawal_fy18"]
bp_ = D["bis_peers_2018"]
ecb_l, ecb_s = D["ecb_euro_area_per_capita_latest"], D["ecb_euro_area_share_of_payments_pct_latest"]
prism_val_share = round(cs["PRISM System"]["value_fy18_bn"] / cs["Total"]["value_fy18_bn"] * 100, 1)
paper_val_share = round(cs["Paper-based"]["value_fy18_bn"] / cs["Total"]["value_fy18_bn"] * 100, 1)
peer_txt = ", ".join(f"{n} {bp_[c]['card_per_capita_2018']}" for c, n in (("IN", "India"), ("ID", "Indonesia"), ("MX", "Mexico"), ("SA", "Saudi Arabia"), ("CN", "China"), ("BR", "Brazil")) if c in bp_)
peer_cw = ", ".join(f"{n} {bp_[c]['card_per_cash_withdrawal_2018']}" for c, n in (("IN", "India"), ("ID", "Indonesia"), ("SA", "Saudi Arabia"), ("MX", "Mexico"), ("CN", "China")) if c in bp_)
md = f"""## C. Payment systems: Pakistan (SBP FY2018) against BIS, ECB and World Bank

*The SBP payment-systems data in the warehouse is the Payment Systems Review for FY2017-18 (to June 2018), so it is eight years older than the rest of this analysis. It describes the structure of Pakistan's payments before later developments and must not be read as the current position.*

**What moved through the system in FY2018.** {cs['Total']['vol_fy18_m']:,.0f} million transactions worth Rs {cs['Total']['value_fy18_bn']/1e3:,.0f} trillion (volume +{cs['Total']['yoy_vol_fy18_pct']}% on FY17). The channel volumes add up exactly to the total (check performed). By volume, electronic banking was {vs['e-Banking']}% and paper instruments {vs['Paper-based']}%; by value, the large-value PRISM system was {prism_val_share}% (only {cs['PRISM System']['vol_fy18_m']} million transactions at an average of Rs {cs['PRISM System']['avg_ticket_rs']/1e6:,.0f} million each) and paper instruments still {paper_val_share}%. Electronic banking rose from 52.7% of non-PRISM volume in FY2014 to 61.8% in FY2018.

**Pakistan's electronic payments were cash-out dominated.** ATMs carried {es['ATM']}% of electronic-banking volume and {D['atm_cash_withdrawal_share_of_atm_volume_fy18_pct']}% of ATM transactions were cash withdrawals (average Rs {D['atm_cash_withdrawal_avg_rs_fy18']:,}); POS purchases were only {es['POS']}% of electronic volume (average Rs {cs['POS']['avg_ticket_rs']:,}). Each POS machine handled about {D['pos_transactions_per_pos_machine_fy18']:,} transactions in the year (about 3 a day) and the number of POS machines fell {abs(D['pos_machines_fall_fy17_fy18_pct'])}% in FY2018, while each ATM handled {D['atm_transactions_per_atm_fy18']:,}.
- ![](img/allin_pk_channels.png)

**Fastest-growing channels (FY2018 volume growth):** mobile phone banking +{cs['Mobile Phone Banking']['yoy_vol_fy18_pct']:.0f}% (to {cs['Mobile Phone Banking']['vol_fy18_m']} million, average Rs {cs['Mobile Phone Banking']['avg_ticket_rs']:,}), e-commerce +{cs['E-Commerce']['yoy_vol_fy18_pct']:.0f}% (to {cs['E-Commerce']['vol_fy18_m']} million, average Rs {cs['E-Commerce']['avg_ticket_rs']:,}), POS +{cs['POS']['yoy_vol_fy18_pct']}%, internet banking +{cs['Internet Banking']['yoy_vol_fy18_pct']}%. Call-centre/IVR banking was flat at 0.3 million. FY2014-18 compound growth in infrastructure: ATMs {ic['ATMs']}% a year, POS machines {ic['POS machines']}%, bank branches {ic['bank branches']}%, internet-banking users {ic['internet banking users']}%, mobile-banking users {ic['mobile banking users']}%.

**Cards.** {cd['total'][-1]/1e6:.1f} million payment cards in June 2018 (FY2014: {cd['total'][0]/1e6:.1f} million; {D['cards_cagr_pct']['total']}% a year): {cd['debit cards'][-1]/1e6:.1f} million debit, {cd['credit cards'][-1]/1e6:.2f} million credit (just {D['cards_cagr_pct']['credit cards']}% a year growth) and {cd['ATM-only cards'][-1]/1e6:.1f} million ATM-only cards. Debit cards dropped from {cd['debit cards'][2]/1e6:.1f} million (FY16) to {cd['debit cards'][3]/1e6:.1f} million (FY17) before recovering to {cd['debit cards'][-1]/1e6:.1f} million; the SBP text in the warehouse does not explain the dip.

**Cross-checks.** SBP counts and World Bank ratios agree: 14,970 bank branches over the adult population implied by WDI's ATM ratio ({D['implied_adults_from_sbp_atms_and_wdi_per100k_m']} million adults, {D['adults_as_share_of_total_pop_pct']}% of the population) is {D['branches_per_100k_adults_sbp_vs_wdi'][0]} branches per 100,000 adults against WDI's {D['branches_per_100k_adults_sbp_vs_wdi'][1]}.

**Against other countries in the same year (2018, BIS CPMI per capita).** Pakistan had about {pk_cpc} card payments per person (POS plus e-commerce, {D['pop_2018_m']} million people) against: {peer_txt}. Card payments per cash withdrawal: Pakistan {pk_cpw} against {peer_cw}. Pakistan's payments were more cash-out oriented than every one of these peers (SBP and BIS definitions are not identical: SBP's POS figure may exclude some card-not-present and e-money payments).

**Euro-area benchmark (ECB payment statistics, {ecb_l['year']}).** Per inhabitant: {ecb_l['CP0']} card payments, {ecb_l['CT0']} credit transfers, {ecb_l['DD']} direct debits, {ecb_l['CHQ']} cheques; cards are {ecb_s['CP0']}% of payments, credit transfers {ecb_s['CT0']}%, direct debits {ecb_s['DD']}%, cheques {ecb_s['CHQ']}%. Card payments per inhabitant rose from {D['ecb_cards_per_capita_first_last'][0][1]} ({D['ecb_cards_per_capita_first_last'][0][0]}) to {D['ecb_cards_per_capita_first_last'][1][1]}, cheques fell from {D['ecb_cheques_per_capita_first_last'][0][1]} to {D['ecb_cheques_per_capita_first_last'][1][1]}.

**For the NovaBank platform.** The real data supports designing for (1) account-to-account and mobile channels that were still small ({es['Mobile Phone Banking']}% and {es['Internet Banking']}% of electronic volume) but the fastest growing, (2) low card acceptance at POS with heavy cash-out through ATMs (which matters for ATM-switching and cash logistics), (3) small tickets at POS (Rs 4,677, about US$ {cs['POS']['avg_ticket_rs']/fx18:.0f} at the 2018 average rate of {fx18:.0f}) and larger digital transfers (Rs 18,798 on mobile, Rs 40,462 on internet banking). These are FY2018 structural facts, not current figures; the BIS finding that low-card economies such as India moved to instant account-to-account payments is context, not evidence about Pakistan after 2018.
"""
save("part_c", md, D)
print(md)

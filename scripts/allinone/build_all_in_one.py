"""Merge parts A-H into docs/ALL_IN_ONE_ANALYSIS.md with an executive summary computed from the part results.
Run after the parts:  python scripts/allinone/run_all.py   (or run each part_*.py, then this file)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *  # noqa

J = lambda n: json.load(open(PARTS / f"{n}.json"))
A, B, C, Dd, E, FG, H = J("part_a"), J("part_b"), J("part_c"), J("part_d"), J("part_e"), J("part_fg"), J("part_h")
C2 = J("part_c2")
RF = json.load(open(ROOT / "docs" / "REAL_FRAUD_CREDITCARD.json"))
W = json.load(open(ROOT / "docs" / "PAKISTAN_WDI_ANALYSIS.json"))
S = json.load(open(ROOT / "docs" / "SBP_ANALYSIS.json"))
M = json.load(open(ROOT / "docs" / "PAKISTAN_ANALYSIS.json"))
a = A["all_banks_fsi"]
aq = A["asset_quality_sep25_to_sep26"]
rk = FG["pakistan_findex_rank_2024"]
bp = B["bop_fy25_fy26"]
cs = C["channel_summary"]
pt = {r["indicator"]: r for r in W["peer_table"]}
npass = sum(1 for r in H["scoreboard"] if r[2].startswith("pass"))

summary = f"""## Executive summary

**Macro and monetary position (Part B, E).** SBP's policy rate is 12.0% (Oct 2026); in real terms (Dec-2025 rate less 2025 inflation) it is {E['real_policy_rate_dec2025_pakistan']}%, third highest of {E['real_policy_rate_n']} countries. The rupee has been stable near 277 per dollar and total liquid reserves reached US$ {B['reserves_latest'][1]/1e3:.1f}bn in Oct 2026, {B['reserves_fy23_low_to_oct26_multiple']}x the June 2023 low. Growth is modest ({B['gdp_growth_avg_last5']}% average over the last five years). The current account moved from a US$ {bp['CurrentAccount Balance'][0]/1e3:.1f}bn surplus in FY25 to a US$ {-bp['CurrentAccount Balance'][1]:,.0f}m deficit in FY26 as imports rose {B['imports_goods_growth_pct']}% and exports fell {abs(B['exports_goods_growth_pct'])}%; remittances of US$ {bp["Workers'Remittances"][1]/1e3:.1f}bn (+{B['remittances_growth_pct']}%) covered {B['remittances_cover_of_goods_trade_deficit_fy26_pct']}% of the goods trade deficit.

**Banks (Part A).** Capital is solid (CAR {a['CAR'][-1]}%) and the gross NPL ratio is {A['gross_npl_ratio_sep26_pct']}% (down from {a['NPL ratio'][0]}% two years earlier), but {A['loss_category_share_of_npls_sep26_pct']}% of NPLs are in the 'loss' category and the 'doubtful' bucket rose {A['doubtful_npl_jump_jun26_sep26_pct']}% in the latest quarter. Return on equity is {a['ROE after tax'][-1]}% but falling and the cost/income ratio rose from {a['Cost/income'][0]}% to {a['Cost/income'][-1]}%. Banks lend little: advances are {a['Advances/deposits'][-1]}% of deposits and about {S['government_share_of_total_credit_pct'][2]}% of credit goes to government (Jun-26). Compared with euro-area significant banks, Pakistan's NPL ratio is about 2.6 times higher and its ROE about 1.7 times higher (Part E).

**Credit depth and inclusion (WDI doc, Part F, G).** Private credit is {pt['credit_gdp']['pakistan']}% of GDP, the lowest of 12 peers (median {pt['credit_gdp']['peer_median']}%). Only {rk['any account']['pakistan_pct']}% of adults have an account (rank {rk['any account']['rank_high_to_low']} of {rk['any account']['of']}); **{FG['women_account_pk_pct']}% of women do, the lowest of all {FG['gender_gap_economies']} economies**, and the gender gap ({FG['gender_gap_pk_pp']} points) is the second largest. Mobile-money accounts ({rk['mobile-money account']['pakistan_pct']}%) now roughly equal bank accounts ({rk['financial-institution account']['pakistan_pct']}%).

**Payments (Part C2, C).** Retail payments through formal channels were {C2['retail_volume_m'][C2['quarters_used'][-1]]:,.0f} million in Q3 FY26 (+{C2['retail_volume_yoy_pct']}% on a year earlier), {C2['digital_share_of_volume_pct'][C2['quarters_used'][-1]]}% digital by volume but only {C2['digital_share_of_value_pct'][C2['quarters_used'][-1]]}% by value (bank branches still carry about 59% of value). Branchless-banking wallet apps are {C2['channels_latest']['Branchless/Digital Banking Apps']['share_of_volume_pct']}% of volume and mobile banking apps {C2['channels_latest']['Mobile Banking Apps']['share_of_volume_pct']}%, while ATM volume has stalled (+{C2['channels_latest']['ATM/CDM']['vol_yoy_pct']:.0f}%) and card-present POS grew {C2['channels_latest']['POS (CP)']['vol_yoy_pct']:.0f}%. Raast instant payments reached {C2['raast_total'][C2['quarters_used'][-1]][0]:,.0f} million (Rs {C2['raast_total'][C2['quarters_used'][-1]][1]/1e3:.1f} trillion) in the quarter, {C2['raast_vol_growth_pct_first_last']/100 + 1:.1f}x two years earlier. Card payments per person are {C2['card_payments_per_capita_last4q']} a year (0.29 in FY2018) and card payments per cash withdrawal {C2['card_payments_per_cash_withdrawal_now']} (0.14 in FY2018, against {C['bis_peers_2018']['ID']['card_per_cash_withdrawal_2018']} for Indonesia and {C['bis_peers_2018']['IN']['card_per_cash_withdrawal_2018']} for India in 2018). BIS data across 23 countries show card payments and account transfers growing every year while cheques fell, and India's card use flat while account-to-account transfers rose more than tenfold.

**External finance (Part D).** External debt is US$ {Dd['ids_total_external_debt_usd_bn']['2025']}bn ({Dd['wdi_external_debt_pct_gni']['2025']:.0f}% of GNI), with debt service taking {Dd['wdi_debt_service_pct_exports']['2025']:.0f}% of exports and **scheduled service of US$ {Dd['ids_debt_service_projection_2026_2030_usd_bn']['2026']}bn in 2026** (about the size of reserves). Foreign banks' cross-border claims on Pakistan are US$ {Dd['lbs_claims_latest_usd_m'][1]/1e3:.1f}bn. Sending money to Pakistan costs {Dd['rpw_cost_pct_by_year_mean']['2025']}% on average (against {Dd['rpw_world_mean_cost_by_year']['2025']}% worldwide) but banks charge {Dd['rpw_cost_by_firm_type_latest_mean']['Bank'][0]}% against {Dd['rpw_cost_by_firm_type_latest_mean']['Money Transfer Operator'][0]}% for money-transfer operators.

**What the earlier synthetic-data work can and cannot say.** The NovaBank payments data is synthetic and has no macro inputs, so it shows no relationship to any real series (as it should). The fraud result on the PaySim simulator (PR-AUC 1.0) reflects a rule built into the simulator, not real fraud detection. The only real-transaction fraud result is on public European card data: XGBoost PR-AUC {RF['results'][2]['pr_auc']} (95% interval {RF['results'][2]['pr_auc_95ci'][0]}-{RF['results'][2]['pr_auc_95ci'][1]}), anonymised 2013 data that does not transfer to Pakistan. Nothing here validates the synthetic generator against real Pakistani payment behaviour; Part C gives real benchmarks that a future generator calibration could use.

**Reliability.** {npass} of {len(H['scoreboard'])} cross-source checks pass (Part H): exchange rates from four sources agree, GDP growth recomputes exactly, SBP identities hold, and the World Bank and IDS debt totals match. The SBP tables are OCR extractions and have not been checked cell by cell against the PDFs.
"""

order = ["part_a", "part_b", "part_c", "part_c2", "part_d", "part_e", "part_fg", "part_h"]
body = "\n".join((PARTS / f"{p}.md").read_text(encoding="utf-8") for p in order)
head = """# All-in-one analysis of the NovaBank data warehouse (real data)

One document covering every real dataset in the warehouse that bears on Pakistan banking and payments: State Bank of Pakistan (SBP), BIS, World Bank (WDI, IDS, Remittance Prices, Global Findex), ECB, FRED and the PaySim simulator reference. Generated by `scripts/allinone/` (parts A to H, merged by `build_all_in_one.py`; data in `docs/_parts/*.json`). It extends and, where noted, corrects the earlier single-topic reports (`PAKISTAN_ANALYSIS.md`, `PAKISTAN_WDI_ANALYSIS.md`, `SBP_ANALYSIS.md`, `BIS_CPMI_ANALYSIS.md`, `PAYSIM_FRAUD_RESULTS.md`, `MACRO_PAYMENTS_JOIN.md`).

**Contents:** A Banking-system health, B Macro economy, C Payment systems (FY2018), C2 Current payments (SBP quarterly, to Mar 2026), D Cross-border finance, E Global context, F WDI screen, G Financial inclusion, H Data quality and reconciliation.

Dates: the warehouse files run to November 2026; "latest" means the latest value in the files, which differs by source.

"""
(ROOT / "docs" / "ALL_IN_ONE_ANALYSIS.md").write_text(head + summary + "\n" + body, encoding="utf-8")
print((ROOT / "docs" / "ALL_IN_ONE_ANALYSIS.md").stat().st_size, "bytes")
print(summary)

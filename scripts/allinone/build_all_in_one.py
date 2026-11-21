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

**Payments (Part C).** In FY2018 (the only SBP payments data in the warehouse) {cs['ATM']['vol_fy18_m']:.0f} million ATM transactions were {C['atm_cash_withdrawal_share_of_atm_volume_fy18_pct']}% cash withdrawals, while card purchases at POS were only {C['ebanking_channel_share_of_ebanking_vol_fy18_pct']['POS']}% of electronic volume: {C['card_payments_per_cash_withdrawal_fy18']} card payments per cash withdrawal against {C['bis_peers_2018']['ID']['card_per_cash_withdrawal_2018']} (Indonesia), {C['bis_peers_2018']['IN']['card_per_cash_withdrawal_2018']} (India) and {C['bis_peers_2018']['MX']['card_per_cash_withdrawal_2018']} (Mexico) in 2018. Mobile banking grew {cs['Mobile Phone Banking']['yoy_vol_fy18_pct']:.0f}% in FY2018 from a small base. Across 23 countries card payments and account transfers grew every year while cheques fell, and India's card use stayed flat as account-to-account transfers rose more than tenfold (BIS).

**External finance (Part D).** External debt is US$ {Dd['ids_total_external_debt_usd_bn']['2025']}bn ({Dd['wdi_external_debt_pct_gni']['2025']:.0f}% of GNI), with debt service taking {Dd['wdi_debt_service_pct_exports']['2025']:.0f}% of exports and **scheduled service of US$ {Dd['ids_debt_service_projection_2026_2030_usd_bn']['2026']}bn in 2026** (about the size of reserves). Foreign banks' cross-border claims on Pakistan are US$ {Dd['lbs_claims_latest_usd_m'][1]/1e3:.1f}bn. Sending money to Pakistan costs {Dd['rpw_cost_pct_by_year_mean']['2025']}% on average (against {Dd['rpw_world_mean_cost_by_year']['2025']}% worldwide) but banks charge {Dd['rpw_cost_by_firm_type_latest_mean']['Bank'][0]}% against {Dd['rpw_cost_by_firm_type_latest_mean']['Money Transfer Operator'][0]}% for money-transfer operators.

**What the earlier synthetic-data work can and cannot say.** The NovaBank payments data is synthetic and has no macro inputs, so it shows no relationship to any real series (as it should). The fraud result on the PaySim simulator (PR-AUC 1.0) reflects a rule built into the simulator, not real fraud detection. Nothing here validates the synthetic generator against real Pakistani payment behaviour; Part C gives real benchmarks that a future generator calibration could use.

**Reliability.** {npass} of {len(H['scoreboard'])} cross-source checks pass (Part H): exchange rates from four sources agree, GDP growth recomputes exactly, SBP identities hold, and the World Bank and IDS debt totals match. The SBP tables are OCR extractions and have not been checked cell by cell against the PDFs.
"""

order = ["part_a", "part_b", "part_c", "part_d", "part_e", "part_fg", "part_h"]
body = "\n".join((PARTS / f"{p}.md").read_text(encoding="utf-8") for p in order)
head = """# All-in-one analysis of the NovaBank data warehouse (real data)

One document covering every real dataset in the warehouse that bears on Pakistan banking and payments: State Bank of Pakistan (SBP), BIS, World Bank (WDI, IDS, Remittance Prices, Global Findex), ECB, FRED and the PaySim simulator reference. Generated by `scripts/allinone/` (parts A to H, merged by `build_all_in_one.py`; data in `docs/_parts/*.json`). It extends and, where noted, corrects the earlier single-topic reports (`PAKISTAN_ANALYSIS.md`, `PAKISTAN_WDI_ANALYSIS.md`, `SBP_ANALYSIS.md`, `BIS_CPMI_ANALYSIS.md`, `PAYSIM_FRAUD_RESULTS.md`, `MACRO_PAYMENTS_JOIN.md`).

**Contents:** A Banking-system health, B Macro economy, C Payment systems, D Cross-border finance, E Global context, F WDI screen, G Financial inclusion, H Data quality and reconciliation.

Dates: the warehouse files run to November 2026; "latest" means the latest value in the files, which differs by source.

"""
(ROOT / "docs" / "ALL_IN_ONE_ANALYSIS.md").write_text(head + summary + "\n" + body, encoding="utf-8")
print((ROOT / "docs" / "ALL_IN_ONE_ANALYSIS.md").stat().st_size, "bytes")
print(summary)

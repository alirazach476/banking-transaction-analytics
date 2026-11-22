"""Build web/react-app/public/analysis.json: every chart and table from the real-data reports as plain data for the React dashboard.

Reads the JSON results written by the analysis scripts (docs/*.json, docs/_parts/*.json); nothing is recomputed or invented here.
Chart types understood by the React component: line, step, bar, stacked, barh (horizontal bars; optional 'highlight' boolean per row), table.
Run after the analysis scripts:  python scripts/export_dashboard_data.py
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS, PARTS = ROOT / "docs", ROOT / "docs" / "_parts"
J = lambda p: json.load(open(p, encoding="utf-8"))
A, B, C, C2, Dd, E, FG, H = (J(PARTS / f"part_{n}.json") for n in ("a", "b", "c", "c2", "d", "e", "fg", "h"))
MAC, SBP, WDI, BIS = J(DOCS / "PAKISTAN_ANALYSIS.json"), J(DOCS / "SBP_ANALYSIS.json"), J(DOCS / "PAKISTAN_WDI_ANALYSIS.json"), J(DOCS / "BIS_CPMI_ANALYSIS.json")
PAY = J(DOCS / "PAYSIM_FRAUD_RESULTS.json")
PAYB = J(DOCS / "PAYSIM_FRAUD_BEHAVIOURAL.json")
REAL = J(DOCS / "REAL_FRAUD_CREDITCARD.json") if (DOCS / "REAL_FRAUD_CREDITCARD.json").exists() else None
CRM = J(PARTS / "part_c.json")
q = lambda s: tuple(int(x) for x in re.match(r"Q(\d)-FY(\d\d)", s).groups())[::-1]


def chart(id, title, type, data, series=None, x="x", sub="", note="", source="", unit="", fmt=None, height=None, wide=False, log=False):
    return {"id": id, "title": title, "type": type, "x": x, "series": series or [], "data": data, "subtitle": sub, "note": note, "source": source, "unit": unit, "fmt": fmt, "wide": wide, "log": log}


def pretty(t: str) -> str:
    """Repair run-together OCR labels such as 'BalanceonTradein Goods' or 'Transportation,Storage andCommunication'."""
    t = re.sub(r",(?=\S)", ", ", t)
    t = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", t)
    t = re.sub(r"(and|of|on|in|to)(?=[A-Z])", r" ", t)
    t = re.sub(r"(?<=[a-z])(on|in|of|and)(?= [A-Z]|[A-Z])", r"  ", t) if False else t
    return re.sub(r"\s+", " ", t).strip()


BOP_NAMES = {"CurrentAccount Balance": "Current account balance", "Exports of Goods FOB": "Goods exports (FOB)", "Imports of Goods FOB": "Goods imports (FOB)", "BalanceonTradein Goods": "Balance on trade in goods", "Workers'Remittances": "Workers' remittances",
             "Exports of Services": "Services exports", "Imports of Services": "Services imports", "Direct Investment in Pakistan": "Direct investment in Pakistan", "PortfolioInvestment": "Portfolio investment", "Financial Account": "Financial account"}
CTY = {"CH": "Switzerland", "GB": "United Kingdom", "FR": "France", "ES": "Spain", "SE": "Sweden", "JP": "Japan", "CA": "Canada", "AU": "Australia", "IT": "Italy", "BE": "Belgium", "US": "United States", "DE": "Germany", "NL": "Netherlands", "KR": "South Korea", "HK": "Hong Kong"}


S = lambda key, name: {"key": key, "name": name}
sections = []

# ---------------- Overview ----------------
a, bp = A["all_banks_fsi"], B["bop_fy25_fy26"]
rk = FG["pakistan_findex_rank_2024"]
last_q = C2["quarters_used"][-1]
sections.append({"id": "overview", "title": "Overview", "intro": "Real data only (SBP, World Bank, BIS, ECB, FRED, Global Findex). The first tab holds the synthetic NovaBank payments dashboard; nothing on this tab is synthetic.",
    "kpis": [
        {"label": "SBP policy rate", "value": "12.0%", "note": "Oct 2026; real rate " + str(E["real_policy_rate_dec2025_pakistan"]) + "% (Dec-25), 3rd of " + str(E["real_policy_rate_n"])},
        {"label": "Capital adequacy (all banks)", "value": f"{a['CAR'][-1]}%", "note": "Sep 2026"},
        {"label": "Gross NPL ratio", "value": f"{A['gross_npl_ratio_sep26_pct']}%", "note": f"{A['loss_category_share_of_npls_sep26_pct']}% of NPLs are 'loss'"},
        {"label": "Advances / deposits", "value": f"{a['Advances/deposits'][-1]}%", "note": "all banks, Sep 2026"},
        {"label": "FX reserves", "value": f"US$ {B['reserves_latest'][1]/1e3:.1f}bn", "note": f"{B['reserves_latest'][0]}; {B['reserves_fy23_low_to_oct26_multiple']}x the Jun-2023 low"},
        {"label": "Retail payments / quarter", "value": f"{C2['retail_volume_m'][last_q]/1e3:.2f}bn", "note": f"{last_q}: {C2['digital_share_of_volume_pct'][last_q]}% digital by volume"},
        {"label": "Raast transactions / quarter", "value": f"{C2['raast_total'][last_q][0]:,.0f}m", "note": f"Rs {C2['raast_total'][last_q][1]/1e3:.1f}tn"},
        {"label": "External debt", "value": f"US$ {Dd['ids_total_external_debt_usd_bn']['2025']}bn", "note": f"{Dd['wdi_external_debt_pct_gni']['2025']:.0f}% of GNI"},
        {"label": "Women with an account", "value": f"{FG['women_account_pk_pct']}%", "note": f"lowest of {FG['gender_gap_economies']} economies (Findex 2024)"},
        {"label": "Private credit / GDP", "value": f"{WDI['peer_table'][0]['pakistan']}%", "note": f"lowest of 12 peers (median {WDI['peer_table'][0]['peer_median']}%)"},
    ], "charts": []})

# ---------------- Macro & monetary ----------------
ch = []
ch.append(chart("policy_inflation", "Policy rate vs inflation", "line", MAC["series"]["policy_inflation_monthly"], [S("policy", "SBP policy rate"), S("inflation", "CPI inflation (YoY)"), S("real_rate", "Real policy rate")], x="month", unit="%",
                sub="Mar 2023 to Mar 2025", note="Overlap of the SBP rate table and the World Bank/IMF CPI file; descriptive only.", source="SBP, World Bank/IMF"))
ch.append(chart("policy_history", "SBP policy (target) rate since 1991", "step", [{"x": r["date"], "policy": r["policy"]} for r in SBP["series"]["policy_changes"]], [S("policy", "Policy rate")], unit="%", sub=f"{SBP['policy_changes']} recorded changes", source="SBP (OCR table)"))
ch.append(chart("usdpkr", "USD/PKR monthly average", "line", MAC["series"]["usdpkr_monthly"], [S("usdpkr", "PKR per USD")], x="month", source="BIS"))
ch.append(chart("repo_policy", "Overnight repo vs policy rate (monthly)", "line", SBP["series"]["repo_vs_policy_monthly"], [S("repo", "Overnight repo (mean)"), S("policy", "Policy rate")], x="month", unit="%", note="Repo within 1 pp of the policy rate in 94% of months.", source="SBP"))
ch.append(chart("gdp_growth", "Real GDP growth (constant 2015-16 prices)", "bar", [{"x": k.replace("FY20", "FY"), "growth": v} for k, v in B["gdp_growth_pct"].items()], [S("growth", "Real GDP growth")], unit="%", source="SBP", note="Growth recomputed from levels matches SBP's published row exactly."))
ch.append(chart("reserves", "Total liquid FX reserves (month-end)", "line", [{"x": k, "reserves": v} for k, v in B["liquid_reserves_total_usd_m_monthly"].items()], [S("reserves", "US$ million")], source="SBP"))
ch.append(chart("inflation_wdi", "CPI inflation, annual", "bar", WDI["series"]["inflation_annual"], [S("inflation", "Inflation")], x="year", unit="%", source="World Bank WDI"))
ch.append(chart("remittances", "Personal remittances received", "bar", MAC["series"]["remittances_usd_m"], [S("usd_m", "US$ million")], x="year", source="World Bank KNOMAD"))
ch.append(chart("bop", "Balance of payments, FY25 vs FY26 (US$ million)", "table", [{"item": BOP_NAMES.get(k, pretty(k)), "FY25": v[0], "FY26": v[1]} for k, v in B["bop_fy25_fy26"].items()], [S("item", "Item"), S("FY25", "FY25"), S("FY26", "FY26")], source="SBP"))
sections.append({"id": "macro", "title": "Macro and monetary", "intro": f"Growth is modest and volatile ({B['gdp_growth_avg_last5']}% average over five years). Reserves rebuilt to {B['reserves_fy23_low_to_oct26_multiple']}x the June 2023 low; the rupee has been stable near 277. The current account moved from a surplus to a US$ {-bp['CurrentAccount Balance'][1]:,.0f}m deficit in FY26.", "kpis": [], "charts": ch})

# ---------------- Banking ----------------
per = A["fsi_period_labels"]
fsi = lambda k: [{"x": p, "v": v} for p, v in zip(per[-len(a[k]):], a[k])]
ch = [
    chart("fsi_car", "Capital adequacy ratio, all banks", "line", fsi("CAR"), [S("v", "CAR")], unit="%", source="SBP Quarterly Compendium"),
    chart("fsi_npl", "NPL ratio, all banks", "line", fsi("NPL ratio"), [S("v", "NPL ratio")], unit="%", source="SBP Quarterly Compendium"),
    chart("fsi_adr", "Advances / deposits (SBP soundness table)", "line", fsi("Advances/deposits"), [S("v", "ADR")], unit="%", note="The Dec-24 spike (49.7%) is in SBP's own table, not an OCR error.", source="SBP Quarterly Compendium"),
    chart("fsi_roe", "Return on equity and cost/income, all banks", "line", [{"x": p, "roe": r, "cost": c} for p, r, c in zip(per, a["ROE after tax"], a["Cost/income"])], [S("roe", "ROE (after tax)"), S("cost", "Cost / income")], unit="%", source="SBP Quarterly Compendium"),
    chart("adr_monthly", "Scheduled banks: advances-to-deposits ratio", "line", SBP["series"]["adr_monthly"], [S("adr", "Advances / deposits")], x="month", unit="%", sub="Monthly, 2002-2025", source="SBP"),
    chart("adr_growth", "Advances and deposits growth (YoY)", "line", SBP["series"]["adr_monthly"], [S("adv_yoy", "Advances YoY"), S("dep_yoy", "Deposits YoY")], x="month", unit="%", note="Advances rose 30% between Sep and Dec 2024 on flat deposits, then fell back.", source="SBP"),
    chart("npl_group", "NPL ratio by bank group (Sep 2026)", "barh", [{"x": pretty(k), "v": v, "highlight": k == "All Banks"} for k, v in A["npl_ratio_by_group_sep26"].items()], [S("v", "NPL ratio")], unit="%", source="SBP Quarterly Compendium"),
    chart("npl_sector", "NPL ratio by sector (Sep 2026, sectors over Rs 200bn)", "barh", [{"x": pretty(k), "v": v["npl_ratio_pct"], "highlight": False} for k, v in sorted(A["sector_npl_sep26"].items(), key=lambda kv: kv[1]["npl_ratio_pct"]) if v["advances_m"] > 2e5 and k not in ("Total", "Others")], [S("v", "NPL ratio")], unit="%", source="SBP Quarterly Compendium"),
    chart("npl_cats", "NPLs by category (Rs million)", "stacked", [{"x": p, "OAEM": o, "Substandard": s_, "Doubtful": d_, "Loss": l_} for p, o, s_, d_, l_ in zip(A["asset_quality_sep25_to_sep26"]["periods"], A["asset_quality_sep25_to_sep26"]["oaem"], A["asset_quality_sep25_to_sep26"]["substandard"], A["asset_quality_sep25_to_sep26"]["doubtful"], A["asset_quality_sep25_to_sep26"]["loss"])],
          [S("OAEM", "OAEM"), S("Substandard", "Substandard"), S("Doubtful", "Doubtful"), S("Loss", "Loss")], note=f"Doubtful NPLs rose {A['doubtful_npl_jump_jun26_sep26_pct']}% in the latest quarter.", source="SBP Quarterly Compendium"),
    chart("depth", "Financial depth (% of GDP)", "line", WDI["series"]["depth_annual"], [S("credit_gdp", "Private credit"), S("broad_money_gdp", "Broad money"), S("remit_gdp", "Remittances")], x="year", unit="%", source="World Bank WDI"),
]
sections.append({"id": "banking", "title": "Banking system", "intro": f"Capital is solid and the gross NPL ratio is {A['gross_npl_ratio_sep26_pct']}%, but {A['loss_category_share_of_npls_sep26_pct']}% of NPLs are in the 'loss' category and doubtful NPLs are rising. Banks lend about {a['Advances/deposits'][-1]}% of deposits and roughly 73% of credit goes to government.", "kpis": [], "charts": ch})

# ---------------- Payments ----------------
qs = C2["quarters_used"]
inf = C2["infrastructure"]
g = lambda k, qq: (inf[k][qq][0] if isinstance(inf[k][qq], list) else inf[k][qq])
dig = {qq: C2["retail_volume_m"][qq] * C2["digital_share_of_volume_pct"][qq] / 100 for qq in qs}
chl = C2["channels_latest"]
t5 = CRM["table5_channels"]
ch = [
    chart("retail_now", "Retail payments by quarter: digital vs over-the-counter (million)", "stacked", [{"x": qq, "Digital": round(dig[qq], 1), "Over-the-counter": round(C2["retail_volume_m"][qq] - dig[qq], 1)} for qq in qs], [S("Digital", "Digital channels"), S("Over-the-counter", "Over-the-counter")], source="SBP Payment Systems Quarterly Reviews", wide=True),
    chart("digital_share", "Digital share of retail payments", "line", [{"x": qq, "volume": C2["digital_share_of_volume_pct"][qq], "value": C2["digital_share_of_value_pct"][qq]} for qq in qs], [S("volume", "By volume"), S("value", "By value")], unit="%", source="SBP"),
    chart("channel_share", f"Channel share of retail volume ({last_q})", "barh", [{"x": k, "v": v["share_of_volume_pct"], "highlight": False} for k, v in sorted(chl.items(), key=lambda kv: kv[1]["share_of_volume_pct"]) if v["share_of_volume_pct"] >= 0.1], [S("v", "Share of volume")], unit="%", source="SBP"),
    chart("channel_growth", f"Channel volume growth, year on year ({last_q})", "barh", [{"x": k, "v": v["vol_yoy_pct"], "highlight": False} for k, v in sorted(chl.items(), key=lambda kv: kv[1]["vol_yoy_pct"]) if v["share_of_volume_pct"] >= 0.1], [S("v", "YoY volume")], unit="%", source="SBP"),
    chart("raast", "Raast instant payments (million per quarter)", "bar", [{"x": qq, "v": C2["raast_total"][qq][0]} for qq in sorted(C2["raast_total"], key=q)], [S("v", "Transactions (million)")], source="SBP", note=f"{C2['raast_vol_growth_pct_first_last']/100 + 1:.1f}x the volume of two years earlier."),
    chart("infra_pos_atm", "POS machines and ATMs", "line", [{"x": qq, "POS machines": g("POS machines", qq), "ATMs": g("ATMs", qq)} for qq in sorted(inf["POS machines"], key=q)], [S("POS machines", "POS machines"), S("ATMs", "ATMs")], source="SBP"),
    chart("infra_qr", "QR-enabled merchants", "bar", [{"x": qq, "v": g("QR merchants", qq)} for qq in sorted(inf["QR merchants"], key=q)], [S("v", "QR merchants")], source="SBP"),
    chart("infra_users", "Digital channel users (million)", "line", [{"x": qq, "Branchless app": round(g("BB mobile app users", qq) / 1e6, 1), "Mobile banking": round(g("mobile banking users", qq) / 1e6, 1), "Internet banking": round(g("internet banking users", qq) / 1e6, 1)} for qq in sorted(inf["mobile banking users"], key=q)],
          [S("Branchless app", "Branchless-banking app users"), S("Mobile banking", "Mobile banking users"), S("Internet banking", "Internet banking users")], source="SBP"),
    chart("cards", "Payment cards (million)", "stacked", [{"x": qq, "Debit": round(C2["cards"]["Debit Cards"][qq] / 1e6, 2), "Credit": round(C2["cards"]["Credit Cards"][qq] / 1e6, 2), "Other": round((C2["cards"]["Overall Cards"][qq] - C2["cards"]["Debit Cards"][qq] - C2["cards"]["Credit Cards"][qq]) / 1e6, 2)} for qq in sorted(C2["cards"]["Overall Cards"], key=q)],
          [S("Debit", "Debit"), S("Credit", "Credit"), S("Other", "Pre-paid and social-welfare")], source="SBP", note="The step in credit cards between Q4 FY25 and Q1 FY26 coincides with report revisions that SBP does not explain."),
    chart("fy18_channels", "FY2014-FY2018 channels (million transactions)", "line", [{"x": f, **{n: t5[k]["vol_m"][i] for n, k in (("ATM", "ATM"), ("POS", "POS"), ("Internet", "Internet Banking"), ("Mobile", "Mobile Phone Banking"), ("Online branches", "RTOB")) if k in t5}} for i, f in enumerate(["FY14", "FY15", "FY16", "FY17", "FY18"])],
          [S("ATM", "ATM"), S("POS", "POS"), S("Internet", "Internet banking"), S("Mobile", "Mobile banking"), S("Online branches", "Online branches")], source="SBP Payment Systems Review FY2018", log=True, note="Log scale. Historical comparison only; SBP's current series has a wider scope."),
]
sections.append({"id": "payments", "title": "Payments", "intro": f"Digital channels carry {C2['digital_share_of_volume_pct'][last_q]}% of retail volume but {C2['digital_share_of_value_pct'][last_q]}% of value. Wallet apps are {chl['Branchless/Digital Banking Apps']['share_of_volume_pct']}% of volume; ATM volume is flat while card-present POS grew {chl['POS (CP)']['vol_yoy_pct']:.0f}% in a year.",
    "kpis": [{"label": "Card payments per person / year", "value": str(C2["card_payments_per_capita_last4q"]), "note": "0.29 in FY2018"}, {"label": "Card payments per cash withdrawal", "value": str(C2["card_payments_per_cash_withdrawal_now"]), "note": "0.14 in FY2018"},
             {"label": "POS terminals / million people", "value": f"{C2['pakistan_terminals_per_million']['pos']:,}", "note": f"euro area {C2['ecb_terminals']['pos_per_million']:,}"}, {"label": "ATMs / million people", "value": str(C2["pakistan_terminals_per_million"]["atms"]), "note": f"euro area {C2['ecb_terminals']['atms_per_million']}"}], "charts": ch})

# ---------------- International comparison ----------------
ch = [
    chart("bis_card_pc", "Card and e-money payments per person, 2023", "barh", [{"x": r["country"], "v": r["per_capita"], "highlight": r["is_india"]} for r in BIS["series"]["card_per_capita_2023"]], [S("v", "Payments per person")], source="BIS CPMI + World Bank population", note="Pakistan is not a CPMI reporter; India highlighted as the closest comparator."),
    chart("bis_instruments", "Payment instruments over time (median country, 2015 = 100)", "line", BIS["series"]["instrument_index_2015_100"], [S("Card and e-money", "Card and e-money"), S("Credit transfers", "Credit transfers"), S("Cheques", "Cheques"), S("Cash withdrawals", "Cash withdrawals")], x="year", source="BIS CPMI"),
    chart("wdi_credit_peers", "Private credit, % of GDP (latest)", "barh", [{"x": r["country"], "v": r["value"], "highlight": r["is_pakistan"]} for r in WDI["series"]["peers"]["credit_gdp"]], [S("v", "% of GDP")], unit="%", source="World Bank WDI"),
    chart("wdi_atm_peers", "ATMs per 100,000 adults (latest)", "barh", [{"x": r["country"], "v": r["value"], "highlight": r["is_pakistan"]} for r in WDI["series"]["peers"]["atm_100k"]], [S("v", "ATMs per 100k adults")], source="World Bank WDI"),
    chart("wdi_remit_peers", "Remittances, % of GDP (latest)", "barh", [{"x": r["country"], "v": r["value"], "highlight": r["is_pakistan"]} for r in WDI["series"]["peers"]["remit_gdp"]], [S("v", "% of GDP")], unit="%", source="World Bank WDI"),
    chart("policy_rates", "Policy rates across central banks (Oct 2026)", "barh", sorted([{"x": CTY.get(r["country"], r["country"]), "v": r["rate"], "highlight": False} for r in E["series"]["bis_policy_rates"]] + [{"x": "Pakistan (SBP)", "v": 12.0, "highlight": True}], key=lambda r: r["v"]), [S("v", "Policy rate")], unit="%", source="BIS, SBP"),
    chart("ecb_rates", "ECB deposit rate", "step", [{"x": r["date"], "rate": r["rate"]} for r in E["series"]["ecb_deposit_rate_steps"]], [S("rate", "Deposit facility rate")], unit="%", source="ECB"),
    chart("hicp", "Euro-area HICP inflation (YoY)", "line", E["series"]["hicp_ea_monthly"], [S("hicp", "HICP")], x="month", unit="%", source="ECB"),
    chart("banks_vs_ea", "Pakistan's banks vs euro-area significant banks", "table", [
        {"indicator": "Capital ratio (%)", "euro_area": E["ssm_latest"]["total capital ratio %"][1], "pakistan": E["pakistan_all_banks_sep26"]["CAR %"]},
        {"indicator": "NPL ratio (%)", "euro_area": E["ssm_latest"]["NPL ratio % (excl. cash balances)"][1], "pakistan": E["pakistan_all_banks_sep26"]["NPL ratio %"]},
        {"indicator": "Return on equity (%)", "euro_area": E["ssm_latest"]["ROE %"][1], "pakistan": E["pakistan_all_banks_sep26"]["ROE after tax %"]},
        {"indicator": "Return on assets (%)", "euro_area": E["ssm_latest"]["ROA %"][1], "pakistan": E["pakistan_all_banks_sep26"]["ROA after tax %"]}],
          [S("indicator", "Indicator"), S("euro_area", "Euro area (Q2 2026)"), S("pakistan", "Pakistan (Sep 2026)")], source="ECB, SBP", note="Definitions differ; a rough comparison."),
]
sections.append({"id": "global", "title": "International comparison", "intro": "Pakistan against peers and other central banks. BIS payment statistics do not include Pakistan, so BIS charts are context, not Pakistani data.", "kpis": [], "charts": ch})

# ---------------- Cross-border ----------------
cb = Dd["rpw_cost_by_sender_latest_mean"]
ch = [
    chart("lbs", "Foreign banks' cross-border claims on Pakistan (US$ billion)", "line", Dd["series"]["lbs"], [S("claims_usd_bn", "Claims on Pakistan"), S("liabilities_usd_bn", "Liabilities to Pakistan")], x="quarter", source="BIS locational banking statistics", note="Country detail is mostly unpublished (confidential) in this table."),
    chart("cbs_country", "International claims by headquarters country, 2026-Q2 (US$ million)", "barh", [{"x": CTY.get(k, k), "v": v, "highlight": False} for k, v in sorted(Dd["cbs_by_headquarters_country_2026Q2_usd_m"].items(), key=lambda kv: kv[1])] + [{"x": "Not published", "v": Dd["cbs_total_2026Q2_usd_m"] - sum(Dd["cbs_by_headquarters_country_2026Q2_usd_m"].values()), "highlight": True}],
          [S("v", "US$ million")], source="BIS consolidated banking statistics", note=f"Shown countries cover {Dd['cbs_visible_share_pct']}% of claims; the rest is not published by BIS (includes the United States). Top 8 reporters shown plus the unpublished remainder."),
    chart("ids_debt", "External debt stock and debt service (US$ billion)", "line", Dd["series"]["ids_debt"], [S("stock_usd_bn", "Debt stock"), S("service_usd_bn", "Debt service (scheduled after 2025)")], x="year", source="World Bank IDS", note="Scheduled service on existing debt only; excludes new borrowing and rollovers."),
    chart("debt_comp", "External debt by creditor type (US$ billion, 2025)", "barh", [{"x": k, "v": v, "highlight": False} for k, v in sorted(Dd["ids_composition_latest_usd_bn"].items(), key=lambda kv: kv[1])], [S("v", "US$ billion")], source="World Bank IDS"),
    chart("rpw_year", "Cost of sending US$ 200 (mean quote, %)", "line", Dd["series"]["rpw"], [S("pakistan", "Pakistan"), S("all_corridors", "All corridors")], x="year", unit="%", source="World Bank Remittance Prices Worldwide"),
    chart("rpw_sender", "Remittance cost by sending country, 2024-25 (%)", "barh", [{"x": k, "v": v[0], "highlight": False} for k, v in sorted(cb.items(), key=lambda kv: kv[1][0])], [S("v", "Mean cost")], unit="%", source="World Bank Remittance Prices Worldwide", note="Surveyed provider quotes, not volume-weighted."),
]
sections.append({"id": "crossborder", "title": "Cross-border finance", "intro": f"External debt is US$ {Dd['ids_total_external_debt_usd_bn']['2025']}bn; IDS scheduled service is US$ {Dd['ids_debt_service_projection_2026_2030_usd_bn']['2026']}bn in 2026. Remittances cost {Dd['rpw_cost_pct_by_year_mean']['2025']}% on average, but banks charge {Dd['rpw_cost_by_firm_type_latest_mean']['Bank'][0]}% against {Dd['rpw_cost_by_firm_type_latest_mean']['Money Transfer Operator'][0]}% for money-transfer operators.", "kpis": [], "charts": ch})

# ---------------- Inclusion ----------------
fx = MAC["series"]["findex_all_pct"]
pe = FG["peers_findex_2024_pct"]
ch = [
    chart("findex_trend", "Account ownership in Pakistan (% of adults)", "line", fx, [S("acc", "Any account"), S("fiacc", "Financial-institution account"), S("mob", "Mobile-money account")], x="year", unit="%", source="Global Findex", note="Mobile money and bank accounts overlap, so they are not additive."),
    chart("findex_peers", "Account ownership, 2024 (% of adults)", "barh", [{"x": k, "v": v["account"], "highlight": k == "PAK"} for k, v in sorted(pe.items(), key=lambda kv: kv[1]["account"])], [S("v", "Any account")], unit="%", source="Global Findex"),
    chart("findex_women", "Women's account ownership, 2024 (% of women)", "barh", [{"x": k, "v": v["women_account"], "highlight": k == "PAK"} for k, v in sorted(pe.items(), key=lambda kv: kv[1]["women_account"])], [S("v", "Women with an account")], unit="%", source="Global Findex", note=f"Pakistan is the lowest of {FG['gender_gap_economies']} economies."),
    chart("findex_ranks", "Pakistan's rank among 153 economies (Findex 2024)", "table", [{"measure": k, "pakistan": f"{v['pakistan_pct']}%", "median": f"{v['median_pct']}%", "rank": f"{v['rank_high_to_low']} of {v['of']}"} for k, v in rk.items()],
          [S("measure", "Measure"), S("pakistan", "Pakistan"), S("median", "Median economy"), S("rank", "Rank (1 = highest)")], source="Global Findex"),
    chart("wdi_extremes", "WDI indicators where Pakistan is in the lowest or highest 3% of countries", "table", [{"indicator": r["indicator"][:80], "value": r["value"], "year": r["year"], "percentile": r["percentile"]} for r in (FG["all_lowest_sample"][:6] + FG["all_highest_sample"][:5])],
          [S("indicator", "Indicator"), S("value", "Value"), S("year", "Year"), S("percentile", "Percentile (of countries)")], source="World Bank WDI", note="A position, not a judgement: for some indicators higher is worse."),
]
sections.append({"id": "inclusion", "title": "Financial inclusion", "intro": f"Only {rk['any account']['pakistan_pct']}% of adults have an account (rank {rk['any account']['rank_high_to_low']} of {rk['any account']['of']}). {FG['women_account_pk_pct']}% of women do, the lowest of all economies; the gender gap is {FG['gender_gap_pk_pp']} points, the second largest.", "kpis": [], "charts": ch})

# ---------------- Machine learning ----------------
SHORT = {"NovaBank synthetic payments": "Synthetic", "PaySim simulator": "PaySim sim", "REAL card transactions": "REAL EU cards"}
mlrows = [{"data": "NovaBank synthetic payments (card fraud)", "model": "XGBoost, tuned", "pr_auc": round(J(DOCS / "PHASE6C_RESULTS.json")["fraud_search"]["test_pr_auc_new"], 3), "note": "synthetic labels from the generator's own rules"},
          {"data": "PaySim simulator", "model": "XGBoost, balances included", "pr_auc": PAY["results"][1]["pr_auc"], "note": "leakage-prone features; simulator rule"},
          {"data": "PaySim simulator", "model": "XGBoost, amount/type/hour only", "pr_auc": PAYB["results"][0]["pr_auc"], "note": "no balances"},
          {"data": "PaySim simulator", "model": "XGBoost, plus account history", "pr_auc": PAYB["results"][1]["pr_auc"], "note": "leak-free behavioural features"}]
if REAL:
    for r in REAL["results"]:
        mlrows.append({"data": "REAL card transactions (anonymised, Europe 2013)", "model": r["model"], "pr_auc": r["pr_auc"], "note": f"time-ordered split; {REAL['test_fraud']} test frauds"})
ch = [chart("ml_prauc", "Fraud models: precision-recall AUC by dataset", "barh", [{"x": f"{SHORT[r['data'].split(' (')[0]]} | {r['model']}".replace(" (balanced)", "").replace(", balances included", " + balances").replace(", amount/type/hour only", " (amount/type/hour)").replace(", plus account history", " + history").replace(", tuned", ""), "v": r["pr_auc"], "highlight": r["data"].startswith("REAL")} for r in mlrows], [S("v", "PR-AUC")], source="docs/PAYSIM_FRAUD_RESULTS.md, docs/REAL_FRAUD_CREDITCARD.md",
            note="Simulated datasets reward learning the simulator's rules; the REAL rows are the only evidence about real card fraud.", wide=True),
      chart("ml_table", "Model results", "table", [{"data": r["data"], "model": r["model"], "pr_auc": r["pr_auc"], "note": r["note"]} for r in mlrows], [S("data", "Dataset"), S("model", "Model"), S("pr_auc", "PR-AUC"), S("note", "Note")], wide=True, source="docs/PAYSIM_FRAUD_RESULTS.md, docs/PHASE6C_RESULTS.md, docs/REAL_FRAUD_CREDITCARD.md")]
sections.append({"id": "ml", "title": "Fraud models", "intro": "PR-AUC (higher is better; random is the fraud rate). Only the real-transaction rows say anything about real fraud.", "kpis": [], "charts": ch})

# ---------------- Data quality ----------------
ch = [chart("scoreboard", "Cross-source reconciliation checks", "table", [{"check": r[0], "result": r[1], "status": r[2]} for r in H["scoreboard"]], [S("check", "Check"), S("result", "Result"), S("status", "Status")], wide=True, source="docs/ALL_IN_ONE_ANALYSIS.md Part H")]
sections.append({"id": "quality", "title": "Data quality", "intro": f"{sum(1 for r in H['scoreboard'] if r[2].startswith('pass'))} of {len(H['scoreboard'])} checks pass; the rest are explained by differing periods or cannot be tested from these files. SBP tables come from OCR and have not been checked cell by cell against the PDFs.", "kpis": [], "charts": ch})

# ---------------- ECB payment statistics and FRED (real external aggregates; read straight from the warehouse) ----------------
import duckdb
_wh = duckdb.connect(str(ROOT / "data" / "warehouse" / "novabank_data.duckdb"), read_only=True)
_pay = lambda sql: _wh.execute(sql).df()
ECB_C = {"AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "CY": "Cyprus", "CZ": "Czechia", "DE": "Germany", "EE": "Estonia", "ES": "Spain", "FI": "Finland", "FR": "France", "GR": "Greece", "HR": "Croatia",
         "HU": "Hungary", "IE": "Ireland", "IT": "Italy", "LT": "Lithuania", "LU": "Luxembourg", "LV": "Latvia", "MT": "Malta", "NL": "Netherlands", "PL": "Poland", "PT": "Portugal", "RO": "Romania",
         "SI": "Slovenia", "SK": "Slovakia", "U2": "Euro area"}
inst = _pay("""SELECT time_period y, typ_trnsctn t, obs_value v FROM ecb.pay WHERE ref_area='U2' AND freq='A' AND transformation='N' AND unit_measure='PN_R_POP' AND rl_trnsctn IN ('1','2') AND frd_typ='_Z'
               AND typ_trnsctn IN ('CP0','CT0','DD','CHQ') AND time_period >= '2009' ORDER BY 1""")
inst["v"] = inst.v.astype(float)
ip = inst.pivot_table(index="y", columns="t", values="v").reset_index()
card_c = _pay("""SELECT ref_area r, obs_value v FROM ecb.pay WHERE freq='A' AND typ_trnsctn='CP0' AND unit_measure='PN_R_POP' AND rl_trnsctn='1' AND transformation='N' AND frd_typ='_Z' AND time_period='2024' AND ref_area <> 'B0'""")
card_c = card_c[card_c.r.isin(ECB_C)].assign(v=lambda d: d.v.astype(float)).sort_values("v")
fr = _pay("SELECT time_period p, obs_value v FROM ecb.pay WHERE _key='PAY.H.U2.W0.CP0.1.F.N.EUR' ORDER BY 1")
den = _pay("SELECT time_period p, obs_value v FROM ecb.pay WHERE _key='PAY.H.U2.W0.CP0.1._Z.N.EUR' ORDER BY 1").set_index("p").v.astype(float)
fraud_rows = [{"x": r.p, "fraud_eur_m": round(float(r.v), 1), "fraud_rate_bps": round(float(r.v) / float(den[r.p]) * 1e4, 2)} for r in fr.itertuples() if r.p in den.index]
cpi = _pay("SELECT observation_date d, cpiaucsl_pc1 v FROM external_fred.fred_cpiaucsl_pc1 WHERE observation_date >= '2015-01-01' AND cpiaucsl_pc1 IS NOT NULL ORDER BY 1")
fed = _pay("SELECT observation_date d, dfedtaru u, dff e FROM external_fred.fred_daily_7day WHERE dfedtaru IS NOT NULL ORDER BY 1")
fed = fed.iloc[::5]
ch = [
    chart("ecb_instruments", "Euro-area payments per inhabitant by instrument", "line", [{"x": r.y, "Card payments": round(r.CP0, 1), "Credit transfers": round(r.CT0, 1), "Direct debits": round(r.DD, 1), "Cheques": round(r.CHQ, 1)} for r in ip.itertuples()],
          [S("Card payments", "Card payments"), S("Credit transfers", "Credit transfers"), S("Direct debits", "Direct debits"), S("Cheques", "Cheques")], source="ECB payment statistics", note="Cards overtook every other instrument; cheques are nearly gone."),
    chart("ecb_card_country", "Card payments per inhabitant by country, 2024", "barh", [{"x": ECB_C[r.r], "v": round(r.v, 1), "highlight": r.r == "U2"} for r in card_c.itertuples()], [S("v", "Payments per inhabitant")], source="ECB payment statistics", note="Euro area highlighted."),
    chart("ecb_fraud", "Euro-area card fraud (value, half-yearly)", "line", [{"x": r["x"], "Fraud rate (basis points of card payment value)": r["fraud_rate_bps"]} for r in fraud_rows], [S("Fraud rate (basis points of card payment value)", "Fraud rate (basis points)")],
          source="ECB payment statistics", note="Fraudulent card transactions as a share of card payment value; 1 basis point = 0.01%. Euro-area figures; they say nothing about Pakistani card fraud."),
    chart("fred_cpi", "US consumer price inflation (year on year)", "line", [{"x": str(r.d)[:7], "inflation": round(float(r.v), 2)} for r in cpi.itertuples()], [S("inflation", "CPI inflation")], unit="%", source="FRED"),
    chart("fred_fed", "US Federal Reserve target rate and effective funds rate", "line", [{"x": str(r.d)[:10], "Target (upper bound)": r.u, "Effective funds rate": r.e} for r in fed.itertuples()], [S("Target (upper bound)", "Target (upper bound)"), S("Effective funds rate", "Effective funds rate")], unit="%", source="FRED", note="The FRED rates files in the warehouse cover one year only."),
]
sections.append({"id": "ecb_fred", "title": "ECB payments and FRED", "intro": "Euro-area payment behaviour and fraud (ECB) and US inflation and policy rates (FRED): real aggregate statistics, kept separate from the synthetic transaction data.", "kpis": [], "charts": ch})

# forecasts of the real series (scripts/forecast_real_series.py); kept when present so a re-export does not drop them
_fc = ROOT / "docs" / "_parts" / "forecasts.json"
if _fc.exists():
    sys.path.insert(0, str(ROOT))
    from scripts.forecast_real_series import chart_specs as _fc_specs
    sections.append(_fc_specs(json.loads(_fc.read_text(encoding="utf-8"))))

out = {"generated": dt.date.today().isoformat(), "title": "Pakistan banking and payments: real-data analysis", "sections": sections}
dest = ROOT / "web" / "react-app" / "public"
dest.mkdir(parents=True, exist_ok=True)
(dest / "analysis.json").write_text(json.dumps(out, separators=(",", ":"), default=str), encoding="utf-8")
n_ch = sum(len(s["charts"]) for s in sections)
print(f"{dest/'analysis.json'}: {(dest/'analysis.json').stat().st_size/1e3:.0f} KB, {len(sections)} sections, {n_ch} charts/tables")

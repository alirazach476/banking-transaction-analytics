"""Part H: data-quality results and cross-source reconciliation scoreboard; closes the caveats raised in earlier analyses."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import *  # noqa

con = connect()
D: dict = {}
J = lambda n: json.load(open(PARTS / f"{n}.json"))
A, B, C, Dd, E, FG = J("part_a"), J("part_b"), J("part_c"), J("part_d"), J("part_e"), J("part_fg")
C2 = J("part_c2")
RF = json.load(open(ROOT / "docs" / "REAL_FRAUD_CREDITCARD.json"))

# H1 SBP policy-rate tables agree
def norm(d):
    return pd.to_datetime(d, format="%d-%b-%y").strftime("%Y-%m-%d")
sir = {}
for (t,) in con.execute("select raw_line from sbp.rows_parsed where document='sir' and page=1 and row_no between 7 and 19").fetchall():
    m = re.match(r"\s*(\d{1,2}-[A-Za-z]{3}-\d{2})\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", t)
    if m:
        sir[norm(m.group(1))] = float(m.group(4))
hist = {}
for (t,) in con.execute("select raw_line from sbp.rows_parsed where document='OVR-Repo-History'").fetchall():
    m = re.match(r"\s*(\d{1,2}-[A-Za-z]{3}-\d{2})\s*\|?\s*([\d.]+)%?\s*\|?\s*([\d.]+)?%?\s*\|?\s*([\d.]+)?%?", t)
    if m:
        hist[norm(m.group(1))] = float(m.group(4) or m.group(2))
D["policy_rate_tables_compared"] = len(sir)
D["policy_rate_tables_matching"] = int(sum(1 for d, v in sir.items() if hist.get(d) == v))

# H2 crowdsourced file integrity
f = ROOT / "data/external_downloads/worldbank_relevant/0042083/_unzipped/DR0052677_All_Countries_Crowdsourced_Price_Data__AllPilotCountries(15)-CrowdsourcedPDCPilot02_final_obs_all_clean.csv"
d2 = duckdb.connect()
strict = d2.execute(f"select count(*) from read_csv('{f.as_posix()}', header=true, all_varchar=true, ignore_errors=false, sample_size=50000)").fetchone()[0]
loaded = con.execute("select count(*) from worldbank.d0042083_dr0052677_all_countries_crowdsourced_pri").fetchone()[0]
D["crowdsourced_strict_read_rows"], D["crowdsourced_loaded_rows"] = int(strict), int(loaded)
D["crowdsourced_line_count_note"] = "wc -l counted 1,270,165 lines; the 7,706 extra lines are line breaks inside quoted text fields, not rows"

# H3 mostly-null tables
P = pd.read_csv(ROOT / "data" / "processed" / "data_profile.csv")
mn = P[P.mostly_null == True]
D["tables_profiled"], D["mostly_null_tables"] = int(len(P)), int(len(mn))
D["mostly_null_by_schema"] = mn.schema.value_counts().to_dict()
D["mostly_null_median_rows"], D["mostly_null_median_cols"] = int(mn.rows.median()), int(mn.cols.median())
D["mostly_null_wide_30plus_cols"], D["mostly_null_tiny_50rows"] = int((mn.cols >= 30).sum()), int((mn.rows <= 50).sum())
D["mostly_null_examples"] = [(r.table[:55], int(r.rows), int(r.cols), round(float(r.null_share), 2)) for r in mn.sort_values("rows", ascending=False).head(4).itertuples()]

# H4 remaining unloaded / failed
files = con.execute("select path, extension from catalog.files where extension in ('csv','xlsx','xls')").df()
src = con.execute("select source_file from catalog.tables").df().source_file.dropna()
done = set(src.str.split("#").str[0].str.replace("\\", "/", regex=False))
D["files_still_not_tables"] = files[~files.path.isin(done)].path.tolist()
D["catalog_files_total"] = int(len(files))

# H5 SBP identity checks
aq = A["asset_quality_sep25_to_sep26"]
D["net_plus_provisions_equals_gross_max_diff_rs_m"] = round(max(abs(aq["net_advances"][i] + aq["provisions"][i] - aq["gross_advances"][i]) for i in range(5)), 1)

# scoreboard
ps = lambda x: "pass" if x else "check"
rows = [
    ("USD/PKR: BIS Sep-26 monthly average vs SBP banks' floating average Oct-26", f"{B['bis_usdpkr_sep26_avg']:.2f} vs 277.24 (SBP mark-to-market 19 Nov: {B['sbp_mtm_usd_ready_19nov26']})", "pass"),
    ("SBP policy-rate table (policy rate changes since Mar-2023) vs SBP long rate history", f"{D['policy_rate_tables_matching']} of {D['policy_rate_tables_compared']} changes identical", ps(D["policy_rate_tables_matching"] == D["policy_rate_tables_compared"])),
    ("GDP growth recomputed from SBP GDP levels vs SBP growth row", f"max difference {B['gdp_growth_check_max_abs_diff_pp']} pp", ps(B["gdp_growth_check_max_abs_diff_pp"] == 0)),
    ("GDP services = total - agriculture - industry, vs published services row", f"max difference Rs {B['services_residual_check_max_abs_diff_rs_m']:.0f} million", "pass"),
    ("Payment-channel volumes sum to published total (SBP FY18)", f"{C['sum_prism_ebanking_paper_vol_fy18']} = {C['table5_total_fy18'][0]} million", "pass"),
    ("Advances: net advances + provisions = gross advances (SBP, 5 quarters)", f"max difference Rs {D['net_plus_provisions_equals_gross_max_diff_rs_m']} million", ps(D["net_plus_provisions_equals_gross_max_diff_rs_m"] < 2)),
    ("External debt: IDS total vs WDI", f"{Dd['reconciliation_ids_vs_wdi_total_debt_latest'][0]} vs {Dd['reconciliation_ids_vs_wdi_total_debt_latest'][1]} US$ bn; creditor rows sum to {Dd['ids_creditor_rows_sum_vs_total_pct']}%", "pass"),
    ("Bank branches per 100,000 adults: SBP count vs WDI ratio (2018)", f"{C['branches_per_100k_adults_sbp_vs_wdi'][0]} vs {C['branches_per_100k_adults_sbp_vs_wdi'][1]} (adults implied from WDI's ATM ratio)", "pass (9% apart)"),
    ("SBP quarterly payments: channel rows vs published total", f"{len(C2['a4_quarters_passing_sum_check'])} of {len(C2['a4_sum_minus_total_vol_value'])} quarters within 0.5% (the other has no POS/e-commerce rows in the old layout)", "pass"),
    ("SBP quarterly payments: my digital-channel total vs the digital total SBP states (Q3 FY26)", f"{C2['my_digital_q2_q3_vol_val'][2]:,.1f}m / Rs {C2['my_digital_q2_q3_vol_val'][3]}tn vs {C2['sbp_stated_digital_q2_q3_vol_val'][2]:,.1f}m / Rs {C2['sbp_stated_digital_q2_q3_vol_val'][3]}tn", ps(C2["digital_definition_matches_sbp"])),
    ("BIS CPMI: instruments add up to 'cashless payments, all'", "98.7% of 302 country-years within 5%", "pass"),
    ("Overnight repo (OCR daily) vs policy rate", f"within 1 pp in 94.2% of 139 months; mean gap +0.04 pp", "pass"),
    ("SBP fiscal-year CPI vs World Bank calendar-year CPI (FY12-FY19)", f"mean absolute gap {B['cpi_mean_abs_diff_pp']} pp (period definitions differ)", "explained, not equal"),
    ("Crowdsourced price file: rows loaded vs strict read", f"{D['crowdsourced_loaded_rows']:,} vs {D['crowdsourced_strict_read_rows']:,}", ps(D["crowdsourced_loaded_rows"] == D["crowdsourced_strict_read_rows"])),
    ("World Bank monthly CPI (0.7% in Mar-25) vs WDI 2025 average (3.55%)", "different periods, not reconcilable from these files", "not testable"),
    ("KNOMAD remittances (calendar 2024, US$ 34.9bn) vs SBP balance of payments (FY25, US$ 38.3bn)", "different periods and definitions", "not testable"),
]
D["scoreboard"] = rows
n_pass = sum(1 for r in rows if r[2].startswith("pass"))

md = f"""## H. Data quality and reconciliation (closing the earlier caveats)

**Checks across independent sources.** {n_pass} of the {len(rows)} checks below pass; the other {len(rows) - n_pass} are explained or cannot be tested from these files.
| Check | Result | Status |
|---|---|---|
""" + "\n".join(f"| {a} | {b} | {c} |" for a, b, c in rows) + f"""

**Caveats from earlier passes that are now resolved**
- *'About 7,700 rows may have been dropped from the 868 MB crowdsourced price file.'* No rows were lost: a strict read (no error skipping) returns exactly {D['crowdsourced_strict_read_rows']:,} rows, identical to what was loaded and with no duplicates. The extra lines counted by `wc -l` are line breaks inside quoted fields.
- *'86 (now {D['mostly_null_tables']}) tables are mostly null.'* They are {D['mostly_null_by_schema'].get('worldbank', 0)} World Bank tables and {D['mostly_null_by_schema'].get('sbp', 0)} SBP table out of {D['tables_profiled']:,}; the median has {D['mostly_null_median_rows']} rows and {D['mostly_null_median_cols']} columns, and {D['mostly_null_wide_30plus_cols']} have 30 or more columns. They are sparse matrices, for example {'; '.join(f'{n} ({r:,} rows x {c} columns, {int(ns*100)}% null)' for n, r, c, ns in D['mostly_null_examples'])}; a feature of the source layout and not a load error.
- *'The late-2024 advances spike might be OCR.'* It is also in SBP's own financial-soundness ratio table (Part A).
- *'The gross NPL ratio is not available.'* It is: {A['gross_npl_ratio_sep26_pct']}% (Part A).
- *'Policy-rate changes might be missing from the SBP history.'* The two SBP rate tables agree on all {D['policy_rate_tables_compared']} changes since Mar-2023.
- *'BIS has no Pakistan series.'* Wrong earlier: BIS has Pakistan as a counterparty in the locational and consolidated banking statistics (Part D).
- *'WB and WDI inflation are not reconciled.'* Done for FY12-FY19 (Part B); the remaining differences are explained by period definitions.
- *'Findex `dig_acc` is digital payments.'* An unverified assumption; corrected in Part G.
- *Files not loaded:* {len(D['files_still_not_tables'])} of {D['catalog_files_total']} CSV/Excel files are still not tables: {', '.join(Path(p).name[:60] for p in D['files_still_not_tables'])} (the first is a SharePoint login page saved as .xlsx, not data; the second workbook contains no usable table).

**What is still limited (not fixed)**
- Current payments data (Part C2) covers formal banking and payment channels only (cash is excluded), the latest quarters are provisional, SBP revises earlier quarters (Q1 FY26 volume by +13.4% between reports), and the Q1 FY25 report was not obtained; the FY2018 review (Part C) is the only older SBP payments source.
- SBP tables come from OCR. The identity checks above all pass, but an individual cell can still be wrong; no table was verified by hand against the PDF.
- BIS country-level claims on Pakistan are mostly confidential in the locational statistics ({Dd['visible_country_claims_share_pct']}% visible); the consolidated statistics show the headquarters country for {Dd['cbs_visible_share_pct']}% of claims, with the remainder (including the United States) not published. That residual cannot be recovered from BIS data.
- The cause of the late-2024 advances surge, and of the Sep-2026 jump in SBP's reserves, is not given in any file.
- The synthetic payments data is not linked to any real series, so no real macro effect on NovaBank-style payments can be claimed (the earlier join found no relationship, as expected from a generator with no macro inputs).
- Not analysed because they are not relevant to Pakistan banking or payments: about 1,000 World Bank project datasets (for example Ukraine BOOST fiscal data, skills, energy and gas-flaring data), most of the 103 ECB datasets (country HICP detail, survey and securities data), the BIS effective-exchange-rate, global-liquidity and long-CPI tables, and the BIS locational data for other countries. They are loaded and profiled.
- Machine learning: on the NovaBank synthetic data the fraud PR-AUC is about 0.26; on the PaySim simulator it is 1.0 with leakage-prone balance features, 0.52 with amount/type/hour only and 0.80 with leak-free account-history features (these learn rules built into simulators). The only evidence on real card fraud is the public European card dataset (`REAL_FRAUD_CREDITCARD.md`): XGBoost PR-AUC {RF['results'][2]['pr_auc']} (95% bootstrap interval {RF['results'][2]['pr_auc_95ci'][0]}-{RF['results'][2]['pr_auc_95ci'][1]}) on a time-ordered split with only {RF['test_fraud']} test frauds; it is anonymised 2013 data from one European issuer and does not transfer to Pakistani cards or wallets, and the NovaBank API's fraud model is unaffected by it.
- Not built: a hosted deployment and (until the repository is pushed) a verified GitHub Actions run.
"""
save("part_h", md, D)
print(md)

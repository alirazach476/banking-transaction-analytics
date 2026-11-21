## H. Data quality and reconciliation (closing the earlier caveats)

**Checks across independent sources.** 13 of the 16 checks below pass; the other 3 are explained or cannot be tested from these files.
| Check | Result | Status |
|---|---|---|
| USD/PKR: BIS Sep-26 monthly average vs SBP banks' floating average Oct-26 | 277.22 vs 277.24 (SBP mark-to-market 19 Nov: 276.5205) | pass |
| SBP policy-rate table (policy rate changes since Mar-2023) vs SBP long rate history | 13 of 13 changes identical | pass |
| GDP growth recomputed from SBP GDP levels vs SBP growth row | max difference 0.0 pp | pass |
| GDP services = total - agriculture - industry, vs published services row | max difference Rs 1 million | pass |
| Payment-channel volumes sum to published total (SBP FY18) | 1224.4 = 1224.4 million | pass |
| Advances: net advances + provisions = gross advances (SBP, 5 quarters) | max difference Rs 0.0 million | pass |
| External debt: IDS total vs WDI | 135.11 vs 135.11 US$ bn; creditor rows sum to 100.0% | pass |
| Bank branches per 100,000 adults: SBP count vs WDI ratio (2018) | 10.95 vs 10.08 (adults implied from WDI's ATM ratio) | pass (9% apart) |
| SBP quarterly payments: channel rows vs published total | 10 of 11 quarters within 0.5% (the other has no POS/e-commerce rows in the old layout) | pass |
| SBP quarterly payments: my digital-channel total vs the digital total SBP states (Q3 FY26) | 3,414.6m / Rs 68.3tn vs 3,414.5m / Rs 68.3tn | pass |
| BIS CPMI: instruments add up to 'cashless payments, all' | 98.7% of 302 country-years within 5% | pass |
| Overnight repo (OCR daily) vs policy rate | within 1 pp in 94.2% of 139 months; mean gap +0.04 pp | pass |
| SBP fiscal-year CPI vs World Bank calendar-year CPI (FY12-FY19) | mean absolute gap 1.31 pp (period definitions differ) | explained, not equal |
| Crowdsourced price file: rows loaded vs strict read | 1,262,459 vs 1,262,459 | pass |
| World Bank monthly CPI (0.7% in Mar-25) vs WDI 2025 average (3.55%) | different periods, not reconcilable from these files | not testable |
| KNOMAD remittances (calendar 2024, US$ 34.9bn) vs SBP balance of payments (FY25, US$ 38.3bn) | different periods and definitions | not testable |

**Caveats from earlier passes that are now resolved**
- *'About 7,700 rows may have been dropped from the 868 MB crowdsourced price file.'* No rows were lost: a strict read (no error skipping) returns exactly 1,262,459 rows, identical to what was loaded and with no duplicates. The extra lines counted by `wc -l` are line breaks inside quoted fields.
- *'86 (now 95) tables are mostly null.'* They are 94 World Bank tables and 1 SBP table out of 1,354; the median has 98 rows and 82 columns, and 61 have 30 or more columns. They are sparse matrices, for example d0037712_dr0095336_excel_file_wdiexcel_data (398,468 rows x 70 columns, 63% null); d0037712_dr0095335_csv_file_wdicsv (398,468 rows x 70 columns, 64% null); d0037740_dr0045613_bulk_download_file_csv_sddscsv (234,000 rows x 116 columns, 90% null); d0037740_dr0045612_bulk_download_file_excel_sddse_data (234,000 rows x 116 columns, 90% null); a feature of the source layout and not a load error.
- *'The late-2024 advances spike might be OCR.'* It is also in SBP's own financial-soundness ratio table (Part A).
- *'The gross NPL ratio is not available.'* It is: 5.57% (Part A).
- *'Policy-rate changes might be missing from the SBP history.'* The two SBP rate tables agree on all 13 changes since Mar-2023.
- *'BIS has no Pakistan series.'* Wrong earlier: BIS has Pakistan as a counterparty in the locational and consolidated banking statistics (Part D).
- *'WB and WDI inflation are not reconciled.'* Done for FY12-FY19 (Part B); the remaining differences are explained by period definitions.
- *'Findex `dig_acc` is digital payments.'* An unverified assumption; corrected in Part G.
- *Files not loaded:* 2 of 552 CSV/Excel files are still not tables: 0037857_DR0045869_Raw_Data_on_Trade_Flows_and_Policies_for_C, DR0090858_Hydraulic_defenses_protection_level.xlsx (the first is a SharePoint login page saved as .xlsx, not data; the second workbook contains no usable table).

**What is still limited (not fixed)**
- Current payments data (Part C2) covers formal banking and payment channels only (cash is excluded), the latest quarters are provisional, SBP revises earlier quarters (Q1 FY26 volume by +13.4% between reports), and the Q1 FY25 report was not obtained; the FY2018 review (Part C) is the only older SBP payments source.
- SBP tables come from OCR. The identity checks above all pass, but an individual cell can still be wrong; no table was verified by hand against the PDF.
- BIS country-level claims on Pakistan are mostly confidential in the locational statistics (8.2% visible); the consolidated statistics show the headquarters country for 76.9% of claims, with the remainder (including the United States) not published. That residual cannot be recovered from BIS data.
- The cause of the late-2024 advances surge, and of the Sep-2026 jump in SBP's reserves, is not given in any file.
- The synthetic payments data is not linked to any real series, so no real macro effect on NovaBank-style payments can be claimed (the earlier join found no relationship, as expected from a generator with no macro inputs).
- Not analysed because they are not relevant to Pakistan banking or payments: about 1,000 World Bank project datasets (for example Ukraine BOOST fiscal data, skills, energy and gas-flaring data), most of the 103 ECB datasets (country HICP detail, survey and securities data), the BIS effective-exchange-rate, global-liquidity and long-CPI tables, and the BIS locational data for other countries. They are loaded and profiled.
- Machine learning: on the NovaBank synthetic data the fraud PR-AUC is about 0.26; on the PaySim simulator it is 1.0 with leakage-prone balance features, 0.52 with amount/type/hour only and 0.80 with leak-free account-history features (these learn rules built into simulators). The only evidence on real card fraud is the public European card dataset (`REAL_FRAUD_CREDITCARD.md`): XGBoost PR-AUC 0.7888 (95% bootstrap interval 0.719-0.848) on a time-ordered split with only 132 test frauds; it is anonymised 2013 data from one European issuer and does not transfer to Pakistani cards or wallets, and the NovaBank API's fraud model is unaffected by it.
- Not built: a hosted deployment (no target or credentials). GitHub Actions has run and passed on the public repository (all four jobs: unit tests, tests with Postgres and dbt, frontend, API image with health check).

## H. Data quality and reconciliation (closing the earlier caveats)

**Checks across independent sources.** 11 of the 14 checks below pass; the other 3 are explained or cannot be tested from these files.
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
| BIS CPMI: instruments add up to 'cashless payments, all' | 98.7% of 302 country-years within 5% | pass |
| Overnight repo (OCR daily) vs policy rate | within 1 pp in 94.2% of 139 months; mean gap +0.04 pp | pass |
| SBP fiscal-year CPI vs World Bank calendar-year CPI (FY12-FY19) | mean absolute gap 1.31 pp (period definitions differ) | explained, not equal |
| Crowdsourced price file: rows loaded vs strict read | 1,262,459 vs 1,262,459 | pass |
| World Bank monthly CPI (0.7% in Mar-25) vs WDI 2025 average (3.55%) | different periods, not reconcilable from these files | not testable |
| KNOMAD remittances (calendar 2024, US$ 34.9bn) vs SBP balance of payments (FY25, US$ 38.3bn) | different periods and definitions | not testable |

**Caveats from earlier passes that are now resolved**
- *'About 7,700 rows may have been dropped from the 868 MB crowdsourced price file.'* No rows were lost: a strict read (no error skipping) returns exactly 1,262,459 rows, identical to what was loaded and with no duplicates. The extra lines counted by `wc -l` are line breaks inside quoted fields.
- *'86 (now 95) tables are mostly null.'* They are 94 World Bank tables and 1 SBP table out of 1,354; the median has 98 rows and 82 columns, and 61 have 30 or more columns. They are sparse matrices, for example d0037712_dr0095336_excel_file_wdiexcel_data (398,468 rows x 70 columns, 64% null); d0037712_dr0095335_csv_file_wdicsv (398,468 rows x 70 columns, 64% null); d0037740_dr0045613_bulk_download_file_csv_sddscsv (234,000 rows x 116 columns, 90% null); d0037740_dr0045612_bulk_download_file_excel_sddse_data (234,000 rows x 116 columns, 90% null); a feature of the source layout and not a load error.
- *'The late-2024 advances spike might be OCR.'* It is also in SBP's own financial-soundness ratio table (Part A).
- *'The gross NPL ratio is not available.'* It is: 5.57% (Part A).
- *'Policy-rate changes might be missing from the SBP history.'* The two SBP rate tables agree on all 13 changes since Mar-2023.
- *'BIS has no Pakistan series.'* Wrong earlier: BIS has Pakistan as a counterparty in the locational and consolidated banking statistics (Part D).
- *'WB and WDI inflation are not reconciled.'* Done for FY12-FY19 (Part B); the remaining differences are explained by period definitions.
- *'Findex `dig_acc` is digital payments.'* An unverified assumption; corrected in Part G.
- *Files not loaded:* 2 of 552 CSV/Excel files are still not tables: 0037857_DR0045869_Raw_Data_on_Trade_Flows_and_Policies_for_C, DR0090858_Hydraulic_defenses_protection_level.xlsx (the first is a SharePoint login page saved as .xlsx, not data; the second workbook contains no usable table).

**What is still limited (not fixed)**
- The only SBP payment-systems data in the warehouse is FY2017-18, so current Pakistani payment volumes, instant-payment growth and card counts cannot be analysed.
- SBP tables come from OCR. The identity checks above all pass, but an individual cell can still be wrong; no table was verified by hand against the PDF.
- BIS country-level claims on Pakistan are mostly confidential; the Part D country list covers 8.2% of claims.
- The cause of the late-2024 advances surge, and of the Sep-2026 jump in SBP's reserves, is not given in any file.
- The synthetic payments data is not linked to any real series, so no real macro effect on NovaBank-style payments can be claimed (the earlier join found no relationship, as expected from a generator with no macro inputs).
- Not analysed because they are not relevant to Pakistan banking or payments: about 1,000 World Bank project datasets (for example Ukraine BOOST fiscal data, skills, energy and gas-flaring data), most of the 103 ECB datasets (country HICP detail, survey and securities data), the BIS effective-exchange-rate, global-liquidity and long-CPI tables, and the BIS locational data for other countries. They are loaded and profiled.
- The machine-learning results from earlier (fraud PR-AUC about 0.26 on synthetic data, 1.0 on the PaySim simulator with leakage-prone balance features) remain modest or non-transferable.
- Not built: a Tableau workbook, a hosted deployment, and a verified GitHub Actions run.

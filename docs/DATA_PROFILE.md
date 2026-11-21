# Data profile: every loaded file and table

Warehouse tables profiled: **1,354** (from 1,349 source files); csv/xlsx/xls files catalogued: **552**. Null share is sampled (5,000 rows) for tables over 20,000 rows. Full per-table detail: `data/processed/data_profile.csv`.

## Overview by schema

| schema | tables | total rows | empty | mostly null (>60%) | mention Pakistan |
|---|---|---|---|---|---|
| bis | 19 | 53,694,948 | 0 | 0 | 1 |
| catalog | 4 | 21,623 | 0 | 0 | 3 |
| ecb | 103 | 82,394,734 | 0 | 0 | 0 |
| external_findex | 1 | 8,577 | 0 | 0 | 1 |
| external_fred | 4 | 147,131 | 0 | 0 | 0 |
| external_paysim | 1 | 6,362,620 | 0 | 0 | 0 |
| misc | 5 | 894 | 0 | 0 | 1 |
| sbp | 3 | 34,675 | 0 | 1 | 2 |
| synthetic_clean | 6 | 2,535,515 | 0 | 0 | 0 |
| synthetic_curated | 3 | 2,495,032 | 0 | 0 | 0 |
| synthetic_raw | 13 | 3,090,016 | 0 | 0 | 0 |
| worldbank | 1,192 | 24,556,313 | 1 | 94 | 379 |

## Topic coverage (tables tagged, by name/column keywords; a table can have several tags)

| topic | tables | rows |
|---|---|---|
| inflation_prices | 99 | 16,883,992 |
| fx_rates | 116 | 109,215,451 |
| interest_rates | 132 | 66,284,602 |
| credit_debt | 117 | 4,731,597 |
| payments | 71 | 17,305,778 |
| money_banking | 1,201 | 75,567,384 |
| gdp_growth | 44 | 224,873 |
| trade_bop | 56 | 57,421,847 |
| inclusion | 52 | 17,092,338 |
| labour | 28 | 262,136 |
| fiscal | 102 | 10,105,942 |
| pakistan | 40 | 14,720 |

## Pakistan-relevant tables that are non-empty and not mostly null: 360

| table | rows | date range | tags |
|---|---|---|---|
| bis.ws_xru | 1,495,022 | 1791 to 2026-Q3 | fx_rates |
| worldbank.d0037947_dr0094302_csv_file | 1,048,404 | 2006.0 to 2024.0 | money_banking |
| worldbank.d0037712_dr0095335_csv_file_wdifootnote | 850,060 | YR1960 to yr2006     | money_banking |
| worldbank.d0037712_dr0095336_excel_file_wdiexcel_footnote | 850,060 | YR1960 to yr2006 | money_banking |
| worldbank.d0038015_dr0092202_bulk_download_file_debtor_coun_e_k | 816,219 | -0.1187 to 99960.1 | credit_debt,money_banking |
| worldbank.d0038015_dr0092203_bulk_download_file_debtor_coun_l_m | 795,219 | -0.105295624 to 999969000.0 | credit_debt,money_banking |
| worldbank.d0038015_dr0092201_bulk_download_file_debtor_coun_a_d | 724,923 | -0.1324 to 9998510.4 | credit_debt,money_banking |
| worldbank.d0038015_dr0092204_bulk_download_file_debtor_coun_r_u | 713,658 | -0.2495 to NULL | credit_debt,money_banking |
| worldbank.d0042066_dr0094835_sdmx_csv_file | 469,984 | 1995.0 to 2020.0 | money_banking |
| worldbank.d0038015_dr0093225_bulk_download_file_debtor_coun_n_q | 228,174 | -0.2756 to 999189.9 | credit_debt,money_banking |
| worldbank.d0037898_dr0095523_remittance_prices_worldwide_co_dataset_fr | 204,469 | 2016_2Q to 2025_3Q | inflation_prices,fx_rates,interest_rates,credit_debt,payments,money_banking |
| worldbank.d0038015_dr0092205_bulk_download_file_debtor_coun_v_z | 201,850 | -0.308 to 9924643.2 | credit_debt,money_banking |
| worldbank.d0037769_dr0045662_data_c_2_harmonized_ind | 154,711 | 1.0 to 9.0 | credit_debt,money_banking,gdp_growth |
| worldbank.d0042083_dr0052667_kenya_crowdsourced_price_data | 89,078 | nan to nan | inflation_prices,fx_rates,money_banking |
| worldbank.d0064204_dr0090935_global_database_of_country_lea_clo_indica | 63,334 | 2000.0 to 2019.0 | money_banking |
| worldbank.d0040437_dr0050407_ave_estimates_at_gtap_sector | 53,241 | nan to nan | money_banking,trade_bop |
| worldbank.d0040437_dr0050404_ave_of_ntm | 53,241 | nan to nan | money_banking,trade_bop |
| worldbank.d0037898_dr0095523_remittance_prices_worldwide_co_dataset_up | 49,491 | 2011_1Q to 2016_1Q | inflation_prices,fx_rates,interest_rates,credit_debt,payments,money_banking |
| worldbank.d0038272_dr0095374_world_bank_official_boundaries | 41,020 | 1984-06-23 0 to 2024-10-22 0 | money_banking |
| worldbank.d0040667_dr0050703_data_bown_reynolds_tftd_july_2_wto_value | 36,820 | nan to nan | money_banking |
| worldbank.d0040667_dr0050703_data_bown_reynolds_tftd_july_2_wto_unit_p | 36,820 | nan to nan | inflation_prices,money_banking |
| worldbank.d0040667_dr0050703_data_bown_reynolds_tftd_july_2_wto_value_ | 36,820 | nan to nan | money_banking |
| worldbank.d0040667_dr0050703_data_bown_reynolds_tftd_july_2_wto_volume | 36,820 | nan to nan | money_banking |
| sbp.table_cells | 27,682 | nan to nan |  |
| worldbank.d0042040_dr0052551_worldwide_exclusion_indicators_in | 27,192 | 1789.0 to 2020.0 | money_banking |
| worldbank.d0040205_dr0050046_excel_file_data | 13,512 | -0.008215051 to 9967400 | money_banking |
| catalog.wb_resources | 11,376 | nan to nan |  |
| worldbank.d0037743_dr0087112_c_2021_global_gas_flaring_volu_c_2021_glo | 10,395 | nan to nan | money_banking |
| worldbank.d0037743_dr0084248_c_2020_global_gas_flaring_volu_flare_upst | 10,076 | nan to nan | money_banking |
| worldbank.d0037743_dr0045623_c_2017_global_gas_flaring_volu_flares_ups | 10,009 | nan to nan | money_banking |
| worldbank.d0037743_dr0045622_c_2018_global_gas_flaring_volu_flares_ups | 9,767 | nan to nan | money_banking |
| worldbank.d0038947_dr0094223_learning_poverty_database_2024_wdi_indica | 9,329 | 2001.0 to 2023.0 | money_banking |
| worldbank.d0038490_dr0047063_global_wage_bill_and_labor_vol_main_data | 9,165 | nan to nan | money_banking,labour |
| external_findex.global_findex_2025 | 8,577 | 2011 to 2024 | credit_debt,payments,inclusion |
| worldbank.d0038015_dr0096040_bulk_download_file_excel_long_data | 8,576 | 1970.0 to 2033.0 | fx_rates,money_banking |
| worldbank.d0038015_dr0096042_bulk_download_file_csv_long_fo_6e6424 | 8,576 | 1970.0 to 2033.0 | fx_rates,money_banking |
| worldbank.d0037712_dr0095347_historical_classification_by_i_list | 8,502 | 1988.0 to 2026.0 | credit_debt,money_banking |
| worldbank.d0061295_dr0086321_international_capital_flows_by_data | 8,500 | 1996.0 to 2020.0 | money_banking |
| worldbank.d0039060_dr0048469_dataset_sheet1 | 8,295 | 1960.0 to 2002.0 | money_banking,gdp_growth,labour |
| worldbank.d0038947_dr0090187_learning_poverty_database_2022_wdi_indica | 8,249 | 2001.0 to 2019.0 | money_banking |

## Problems to fix or know about

- Empty tables: **1**. Mostly-null (>60%): **95**. Profiling errors: **0**.
- csv/xlsx/xls files that never became a table: **2** (listed below, first 40).
- Duplicate-content file groups: **9** (31 files).
- Latest load status FAILED: **0** items (listed below).

| unloaded file | ext |
|---|---|
| /0037857_DR0045869_Raw_Data_on_Trade_Flows_and_Policies_for_COVID-19_Medical_Supplies.xlsx | xlsx |
| downloads/worldbank_collections/0064152/DR0090858_Hydraulic_defenses_protection_level.xlsx | xlsx |

## What this does and does not tell you
- It is an inventory and quality screen, not an analysis of the content of each table.
- Topic tags come from names and column headers, so they can be wrong; Pakistan detection checks the first 8 text columns only (sampled).
- Next step is analysis of the Pakistan/payments/rates subsets flagged above.

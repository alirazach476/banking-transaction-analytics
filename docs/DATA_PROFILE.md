# Data profile: every loaded file and table

Warehouse tables profiled: **1,249** (from 1,245 source files); csv/xlsx/xls files catalogued: **552**. Null share is sampled (5,000 rows) for tables over 20,000 rows. Full per-table detail: `data/processed/data_profile.csv`.

## Overview by schema

| schema | tables | total rows | empty | mostly null (>60%) | mention Pakistan |
|---|---|---|---|---|---|
| bis | 19 | 53,694,948 | 0 | 0 | 1 |
| catalog | 4 | 21,623 | 0 | 0 | 3 |
| ecb | 103 | 82,394,734 | 0 | 0 | 0 |
| external_findex | 1 | 8,577 | 0 | 0 | 1 |
| external_fred | 4 | 147,131 | 0 | 0 | 0 |
| external_paysim | 1 | 6,362,620 | 0 | 0 | 0 |
| sbp | 2 | 27,722 | 0 | 0 | 1 |
| synthetic_clean | 6 | 2,535,515 | 0 | 0 | 0 |
| synthetic_curated | 3 | 2,495,032 | 0 | 0 | 0 |
| synthetic_raw | 13 | 3,090,016 | 0 | 0 | 0 |
| worldbank | 1,093 | 20,006,424 | 1 | 86 | 332 |

## Topic coverage (tables tagged, by name/column keywords; a table can have several tags)

| topic | tables | rows |
|---|---|---|
| inflation_prices | 88 | 15,583,586 |
| fx_rates | 107 | 107,943,456 |
| interest_rates | 121 | 66,282,989 |
| credit_debt | 102 | 4,729,775 |
| payments | 64 | 17,304,829 |
| money_banking | 1,102 | 71,017,495 |
| gdp_growth | 36 | 224,067 |
| trade_bop | 40 | 57,420,069 |
| inclusion | 39 | 17,090,748 |
| labour | 26 | 261,733 |
| fiscal | 94 | 10,105,042 |
| pakistan | 37 | 14,093 |

## Pakistan-relevant tables that are non-empty and not mostly null: 318

| table | rows | date range | tags |
|---|---|---|---|
| bis.ws_xru | 1,495,022 | 1791 to 2026-Q3 | fx_rates |
| worldbank.d0037947_dr0094302_csv_file | 1,048,404 | 2006.0 to 2024.0 | money_banking |
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
| sbp.table_cells | 27,682 | nan to nan |  |
| worldbank.d0042040_dr0052551_worldwide_exclusion_indicators_in | 27,192 | 1789.0 to 2020.0 | money_banking |
| worldbank.d0040205_dr0050046_excel_file_data | 13,512 | -0.008215051 to 9967400 | money_banking |
| catalog.wb_resources | 11,376 | nan to nan |  |
| worldbank.d0037743_dr0087112_c_2021_global_gas_flaring_volu_c_2021_glo | 10,395 | nan to nan | money_banking |
| worldbank.d0037743_dr0084248_c_2020_global_gas_flaring_volu_flare_upst | 10,076 | nan to nan | money_banking |
| worldbank.d0037743_dr0045623_c_2017_global_gas_flaring_volu_flares_ups | 10,009 | nan to nan | money_banking |
| worldbank.d0037743_dr0045622_c_2018_global_gas_flaring_volu_flares_ups | 9,767 | nan to nan | money_banking |
| worldbank.d0038490_dr0047063_global_wage_bill_and_labor_vol_main_data | 9,165 | nan to nan | money_banking,labour |
| external_findex.global_findex_2025 | 8,577 | 2011 to 2024 | credit_debt,payments,inclusion |
| worldbank.d0038015_dr0096040_bulk_download_file_excel_long_data | 8,576 | 1970.0 to 2033.0 | fx_rates,money_banking |
| worldbank.d0037712_dr0095347_historical_classification_by_i_list | 8,502 | 1988.0 to 2026.0 | credit_debt,money_banking |
| worldbank.d0061295_dr0086321_international_capital_flows_by_data | 8,500 | 1996.0 to 2020.0 | money_banking |
| worldbank.d0039060_dr0048469_dataset_sheet1 | 8,295 | 1960.0 to 2002.0 | money_banking,gdp_growth,labour |
| worldbank.d0037743_dr0045621_c_2019_global_gas_flaring_volu_all_flares | 8,079 | nan to nan | money_banking |
| catalog.wb_datasets | 7,781 | nan to nan |  |
| worldbank.d0038045_dr0046261_excel_employment_growth_from_i_growth_fro | 7,335 | nan to nan | interest_rates,money_banking,gdp_growth,labour |
| worldbank.d0037743_dr0045621_c_2019_global_gas_flaring_volu_flare_upst | 7,209 | nan to nan | money_banking |
| worldbank.d0038647_dr0047778_mix_market_social_performance_sheet1 | 5,155 | 1999.0 to 2018.0 | inflation_prices,interest_rates,credit_debt,payments,money_banking,gdp_growth,trade_bop,inclusion,labour,fiscal |
| worldbank.d0037996_dr0046108_spi_data_csv | 4,557 | 2004.0 to 2024.0 | inflation_prices,fx_rates,credit_debt,money_banking |
| worldbank.d0037996_dr0095674_spi_index_data_csv | 4,557 | 2004.0 to 2024.0 | inflation_prices,fx_rates,money_banking |
| worldbank.d0037999_dr0046127_covid_19_financial_sector_resp_raw_data | 4,029 | 2020-02-01 0 to 2021-11-30 0 | interest_rates,money_banking |
| worldbank.d0042066_dr0084043_cwon_2024_country_tool_151_cou_country | 3,926 | 1995.0 to 2020.0 | money_banking |

## Problems to fix or know about

- Empty tables: **1**. Mostly-null (>60%): **86**. Profiling errors: **0**.
- csv/xlsx/xls files that never became a table: **60** (listed below, first 40).
- Duplicate-content file groups: **9** (31 files).
- Latest load status FAILED: **17** items (listed below).

| item | message |
|---|---|
| 0039818_DR0049514_Finance_for_All_Database.xlsx | File is not a zip file |
| 0060802_DR0085351_UHC_Data_-_Financial_Protection_-_Country_Level_Data | File is not a zip file |
| 0038947_DR0054368_Learning_Poverty_Database_2021_07-July_.xlsx | File is not a zip file |
| 0040521_DR0050542_NFI_2017.xlsx | File is not a zip file |
| 0042054_DR0052583_Data.xlsx | File is not a zip file |
| 0038632_DR0047732_2003_database.xlsx | File is not a zip file |
| 0039364_DR0048892_Managing_Decline_Database.xlsx | File is not a zip file |
| 0038947_DR0090187_Learning_Poverty_Database_2022_06-June_.xlsx | File is not a zip file |
| 0038632_DR0047733_2001_Database.xlsx | File is not a zip file |
| 0037857_DR0045869_Raw_Data_on_Trade_Flows_and_Policies_for_COVID-19_Me | No tables found |
| 0038947_DR0094223_Learning_Poverty_Database_2024_04-April_.xlsx | File is not a zip file |
| 0060802_DR0085352_UHC_Data_-_Financial_Protection_-_Global_Regional_an | File contains no valid workbook part |
| 0041070_DR0051218_Spread_of_Conflict_Data.xlsx | File is not a zip file |
| 0038632_DR0047731_2007_Database.xlsx | File is not a zip file |
| 0040658_DR0050682_Dataset.xlsx | File is not a zip file |
| 0038947_DR0048277_Learning_Poverty_Database_2019_10-October_.xlsx | File is not a zip file |
| 0042050_DR0052577_Data.xlsx | File contains no valid workbook part |

| unloaded file | ext |
|---|---|
| data/external_downloads/csv_excel_sources_index.csv | csv |
| data/external_downloads/csv_sources_index.csv | csv |
| data/samples/accounts_sample.csv | csv |
| data/samples/customers_sample.csv | csv |
| data/samples/transactions_sample.csv | csv |
| /0037857_DR0045869_Raw_Data_on_Trade_Flows_and_Policies_for_COVID-19_Medical_Supplies.xlsx | xlsx |
| data/external_downloads/worldbank/UKRAINE/0038632_DR0047731_2007_Database.xlsx | xlsx |
| data/external_downloads/worldbank/UKRAINE/0038632_DR0047732_2003_database.xlsx | xlsx |
| data/external_downloads/worldbank/UKRAINE/0038632_DR0047733_2001_Database.xlsx | xlsx |
| nloads/worldbank/UKRAINE/0038947_DR0048277_Learning_Poverty_Database_2019_10-October_.xlsx | xlsx |
| downloads/worldbank/UKRAINE/0038947_DR0054368_Learning_Poverty_Database_2021_07-July_.xlsx | xlsx |
| downloads/worldbank/UKRAINE/0038947_DR0090187_Learning_Poverty_Database_2022_06-June_.xlsx | xlsx |
| ownloads/worldbank/UKRAINE/0038947_DR0094223_Learning_Poverty_Database_2024_04-April_.xlsx | xlsx |
| data/external_downloads/worldbank/UKRAINE/0039364_DR0048892_Managing_Decline_Database.xlsx | xlsx |
| data/external_downloads/worldbank/UKRAINE/0039818_DR0049514_Finance_for_All_Database.xlsx | xlsx |
| data/external_downloads/worldbank/UKRAINE/0040521_DR0050542_NFI_2017.xlsx | xlsx |
| data/external_downloads/worldbank/UKRAINE/0040658_DR0050682_Dataset.xlsx | xlsx |
| data/external_downloads/worldbank/UKRAINE/0041070_DR0051218_Spread_of_Conflict_Data.xlsx | xlsx |
| data/external_downloads/worldbank/UKRAINE/0042050_DR0052577_Data.xlsx | xlsx |
| data/external_downloads/worldbank/UKRAINE/0042054_DR0052583_Data.xlsx | xlsx |
| ldbank/UKRAINE/0060802_DR0085351_UHC_Data_-_Financial_Protection_-_Country_Level_Data.xlsx | xlsx |
| _UHC_Data_-_Financial_Protection_-_Global_Regional_and_Country_Income_Group_Estimates.xlsx | xlsx |
| downloads/worldbank_collections/0064152/DR0090858_Hydraulic_defenses_protection_level.xlsx | xlsx |
| l_downloads/worldbank_relevant/0037712/_unzipped/DR0095335_CSV_file__WDIcountry-series.csv | csv |
| external_downloads/worldbank_relevant/0037712/_unzipped/DR0095335_CSV_file__WDICountry.csv | csv |
| ata/external_downloads/worldbank_relevant/0037712/_unzipped/DR0095335_CSV_file__WDICSV.csv | csv |
| xternal_downloads/worldbank_relevant/0037712/_unzipped/DR0095335_CSV_file__WDIfootnote.csv | csv |
| rnal_downloads/worldbank_relevant/0037712/_unzipped/DR0095335_CSV_file__WDIseries-time.csv | csv |
| /external_downloads/worldbank_relevant/0037712/_unzipped/DR0095335_CSV_file__WDISeries.csv | csv |
| xternal_downloads/worldbank_relevant/0037712/_unzipped/DR0095336_Excel_file__WDIEXCEL.xlsx | xlsx |
| s/worldbank_relevant/0037740/_unzipped/DR0045612_Bulk_Download_File_Excel___SDDSEXCEL.xlsx | xlsx |
| ds/worldbank_relevant/0037740/_unzipped/DR0045613_Bulk_Download_File_CSV___SDDSCountry.csv | csv |
| nloads/worldbank_relevant/0037740/_unzipped/DR0045613_Bulk_Download_File_CSV___SDDSCSV.csv | csv |
| s/worldbank_relevant/0037741/_unzipped/DR0045616_Bulk_Download_File_Excel___GDDSEXCEL.xlsx | xlsx |
| ds/worldbank_relevant/0037741/_unzipped/DR0045617_Bulk_Download_File_CSV___GDDSCountry.csv | csv |
| nloads/worldbank_relevant/0037741/_unzipped/DR0045617_Bulk_Download_File_CSV___GDDSCSV.csv | csv |
| 5/_unzipped/DR0096042_Bulk_Download_File_CSV_-_long_format___Country-Series - Metadata.csv | csv |
| 0038015/_unzipped/DR0096042_Bulk_Download_File_CSV_-_long_format___IDS_CountryMetaData.csv | csv |
| levant/0038015/_unzipped/DR0096042_Bulk_Download_File_CSV_-_long_format___IDS_CSV_long.csv | csv |
| 038015/_unzipped/DR0096042_Bulk_Download_File_CSV_-_long_format___IDS_FootNoteMetaData.csv | csv |

## What this does and does not tell you
- It is an inventory and quality screen, not an analysis of the content of each table.
- Topic tags come from names and column headers, so they can be wrong; Pakistan detection checks the first 8 text columns only (sampled).
- Next step is analysis of the Pakistan/payments/rates subsets flagged above.

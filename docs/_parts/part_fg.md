## F. Where Pakistan stands on 1,498 World Development Indicators

I screened every WDI series for Pakistan (1,350 have data since 2015) and ranked the latest value against all 217 countries and territories that report it (aggregates excluded; series with fewer than 100 reporting countries skipped). Size-driven series (populations, aid and flow amounts in dollars) were removed, leaving 519 ratio-type indicators (the full table is `data/processed/pakistan_wdi_screen.csv`). Pakistan's median percentile across them is 43.4; 12 sit in the lowest 3% of countries and 9 in the highest 3%. A high or low percentile is a position, not a judgement: for some of these a higher value is worse.

**Lowest 3% of countries:** Account ownership at a financial institution or with a mobile-money-service provider, female (% of population ages 15+) 11.91 (2024; percentile 0.0 of 139); Employers, female (% of female employment) (modeled ILO estimate) 0.1 (2025; percentile 0.0 of 182); Current health expenditure (% of GDP) 2.52 (2023; percentile 2.6 of 192); Trade (% of GDP) 27.19 (2025; percentile 2.2 of 138); Employment in services, female (% of female employment) (modeled ILO estimate) 18.82 (2025; percentile 2.8 of 182); Antiretroviral therapy coverage (% of people living with HIV) 16.0 (2024; percentile 0.8 of 126).
**Highest 3%:** Diabetes prevalence (% of population ages 20 to 79) 31.4 (2024; percentile 100.0 of 209); Mortality rate, neonatal (per 1,000 live births) 36.1 (2024; percentile 99.0 of 196); Share of youth not in education, employment or training, female (% of female youth population) (modeled ILO estimate) 56.6 (2025; percentile 98.9 of 182); Public and publicly guaranteed debt service (% of exports of goods, services and primary income) 27.15 (2024; percentile 98.0 of 101); Communications, computer, etc. (% of service exports, BoP) 73.89 (2025; percentile 98.5 of 135).
**Largest 10-year changes in % indicators (percentage points):** Individuals using the Internet (% of population) 10.0 to 57.3; ICT service exports (% of service exports, BoP) 13.4 to 46.1; Primary completion rate, female (% of relevant age group) 51.2 to 72.9; Tuberculosis case detection rate (%, all forms) 53.0 to 74.0; Lower secondary completion rate, female (% of relevant age group) 34.7 to 54.5; falls: Electricity production from oil sources (% of total) 36.8 to 8.2; People practicing open defecation, rural (% of rural population) 26.9 to 13.0; Risk of catastrophic expenditure for surgical care (% of people at risk) 60.5 to 33.7. Debt service on public and publicly guaranteed debt rose from 8.0% to 27.2% of exports over the decade (consistent with the IDS result in Part D). (Series that drop to exactly 0 in one year, such as the WTO 'binding coverage' ones, were excluded from the narrative as probable reporting artefacts.)
For the banking and payments questions the screen agrees with the earlier analyses: female financial access is the lowest of any country that reports it, and trade and health spending are among the lowest shares of GDP.

## G. Financial inclusion in depth (Global Findex 2024, 153 economies)

Pakistan's rank among 153 economies for the adult population:
| Measure | Pakistan | Median economy | Pakistan's rank (1 = highest) |
|---|---|---|---|
| Any account | 27.3% | 73.1% | 148 of 153 |
| Account at a financial institution | 18.3% | 70.5% | 143 of 153 |
| Mobile-money account | 18.4% | 28.8% | 59 of 93 |
| Borrowed in the past year (any source) | 69.5% | 58.1% | 26 of 108 |
| dig_acc (digital; exact definition not in the warehouse) | 19.8% | 47.7% | 94 of 108 |

- **Women:** 11.9% of Pakistani women have an account, the **lowest of all 153 economies** (rank 1 lowest). The gender gap is 30.4 percentage points, the **2nd largest** (largest: DZA 33.8, PAK 30.4, ARE 29.6) against a median gap of 4.7 points.
- **Who is excluded:** poorest 40% 13.6% vs richest 60% 36.4%; rural 21.1% vs urban 32.9%; primary education or less 18.9% vs secondary or more 46.7%; ages 15-24 24.3% vs 25+ 28.5%.
- **Mobile money now roughly equals bank accounts:** 18.4% hold a mobile-money account against 18.3% a financial-institution account (the two groups overlap, so they are not additive), but Pakistan is still below the median among the 93 economies that report mobile money (28.8%).
- **Borrowing is high** (69.5%, rank 26 of 108) even though accounts are rare, which is consistent with a large informal borrowing market, but that is a reading only; the Findex fields available do not let me separate formal from informal borrowing.
- **Peers (account ownership 2024):** IND 89.0% (women 89.2%); BGD 43.3% (women 33.3%); LKA 81.7% (women 80.2%); NPL 60.0% (women 59.8%); IDN 56.3% (women 58.0%); EGY 43.1% (women 40.2%); TUR 81.6% (women 71.7%); NGA 63.3% (women 52.2%); KEN 90.1% (women 86.5%); VNM 70.6% (women 69.9%); PHL 50.2% (women 57.1%).
- ![](img/allin_findex_peers.png)
- *Correction to my earlier Pakistan analysis:* it labelled the Findex field `dig_acc` 'digital payments'. The Findex codebook is not in the warehouse, so that label was an assumption; this part uses the neutral field name.

# NovaBank Data Warehouse (DuckDB)

File: `data/warehouse/novabank_data.duckdb` (~4.3 GB, git-ignored). Built from everything under `data/` (646 files, 54.4 GB scanned).

Rebuild: `python -I scripts/build_data_warehouse.py [--stage catalog synthetic sbp meta external bis worldbank ecb] [--force] [--only SUBSTR]`
Loading is idempotent: tables already loaded are skipped unless `--force`.

## Schemas (tables / rows, from `catalog.tables`)

| Schema | Tables | Rows | Source |
|---|---|---|---|
| synthetic_raw / clean / curated | 13 / 6 / 3 | 3.1M / 2.5M / 2.5M | NovaBank synthetic generator output (curated has a rejects table) |
| ecb | 103 | 82.4M | ECB SDMX CSVs (`data/external_downloads/ecb`) |
| bis | 18 | 15.8M | BIS bulk flat CSVs |
| worldbank | 1,091 | 20.0M | World Bank Excel/CSV (featured, collections, relevant incl. unzipped members); one table per sheet |
| sbp | 2 | 27.7K | SBP PDFs OCR'd to text, loaded as long-form cells + document list |
| external_fred | 4 | 147K | `fredgraph/`: CPI YoY, daily rates, metro unemployment (melted to long) |
| external_paysim | 1 | 6.4M | PaySim log (public synthetic) |
| external_findex | 1 | 8.6K | Global Findex 2025 |
| catalog | 8 | | lineage: `files`, `tables`, `load_log`, `download_manifest`, `wb_datasets`, `wb_resources`, `zip_members`, view `duplicate_files` |

## Cleaning rules
- Column names snake_cased; duplicates de-suffixed.
- Columns typed only when >=98% of values parse; otherwise kept as text.
- Exact duplicate rows removed for tables under 5M rows; counts in `catalog.tables.duplicates_removed`.
- SDMX (ECB/BIS): `obs_value` DOUBLE, `period_start` DATE parsed from `time_period` (annual, monthly, daily, quarterly, semester).
- Excel: file signature sniffed (some `.xlsx` are really legacy OLE `.xls` or HTML); header row detected; empty rows/columns dropped.
- FRED: `.` and blanks = NULL. Metro unemployment melted wide -> long, empty months dropped.
- Every table is registered in `catalog.tables` (source file, rows in/out, notes); every step logged in `catalog.load_log`.

## Querying
```python
import duckdb
c = duckdb.connect("data/warehouse/novabank_data.duckdb", read_only=True)
c.sql("select * from catalog.tables order by rows_out desc limit 20").show()
c.sql("select * from external_fred.metro_unemployment_rate_msa_long where region_name like 'Dallas%' order by observation_date desc limit 12").show()
```

## Known limitations
- `catalog.load_log` is append-only; use each item's latest row. Older FAILED rows were fixed by later runs.
- `worldbank/..DR0045869..xlsx` (COVID trade flows) is a saved SharePoint error page, not data; not loadable. Re-download needed.
- Some World Bank downloads were blocked (HTTP 403/500) and are absent; see `download_manifest`.
- BIS `WS_LBS_D_PUB` (locational banking) is not present in `data/external_downloads/bis`; download was incomplete.
- 14 less-relevant large ECB datasets (SEC, SHSS, IVF, IDCS, STP, RAS, RA6, GFS, QSA, MNA, STS, WTS, E09, E11) were deliberately not downloaded.
- 8 climate/biomass zips were not extracted (irrelevant to banking).
- SBP figures are OCR; verify critical numbers against the source PDF (low-confidence cells marked `?`).
- FRED CPI file contains dates through 2026-10 as supplied; trailing blanks are NULL.
- Only 1 file per SDMX dataset is loaded as a single table; no cross-dataset joins/keys are defined yet.

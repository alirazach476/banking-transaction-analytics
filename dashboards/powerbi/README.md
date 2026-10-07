# Power BI — NovaBank Dashboards

> **Disclaimer:** This project uses synthetic banking data generated solely for demonstrating data engineering, analytics, and transaction-monitoring capabilities. It does not represent real customer or banking data.

## Live dashboard (already built from PostgreSQL)

1. **Cursor Canvas** — open beside chat: project `canvases/novabank-bi-dashboard.canvas.tsx`
2. **Browser HTML** — open [`../novabank_bi_dashboard.html`](../novabank_bi_dashboard.html)

```powershell
python scripts/export_bi_dashboard_data.py
python scripts/build_bi_artifacts.py
```

This folder also has specs to rebuild the same pages in Power BI Desktop. A `.pbix` file is **not** auto-generated (Power BI Desktop cannot be automated reliably here).

---

## Prerequisites

- Power BI Desktop (latest)
- PostgreSQL ODBC driver or native PostgreSQL connector
- NovaBank pipeline executed (`make pipeline`)
- PostgreSQL accessible on `localhost:5432` (or embedded Postgres port from `.env`)

---

## Connect to PostgreSQL

### Option A: Native PostgreSQL connector

1. **Get Data** → **PostgreSQL database**
2. Server: `localhost:5432` (check `.env` for `POSTGRES_PORT`)
3. Database: `novabank`
4. Data connectivity mode:
   - **Import** — recommended for demo volumes
   - **DirectQuery** — for larger datasets with indexed marts
5. Advanced options → SQL statement optional (prefer selecting schemas)
6. Credentials: Database → User `novabank` / Password from `.env`

### Option B: ODBC

1. Install PostgreSQL ODBC driver
2. **Get Data** → **ODBC** → configure DSN to `novabank`

### SSL

Local Docker/embedded Postgres typically does not use SSL. Disable SSL in connector options if connection fails.

---

## Tables to Import

Primary schema: **`analytics`**

| Table | Use |
|-------|-----|
| mart_daily_transactions | Executive trends, Page 1–2 |
| mart_monthly_transactions | Monthly growth |
| mart_customer_activity | Customer analytics, Page 3 |
| mart_account_activity | Account analytics, Page 4 |
| mart_channel_performance | Channel KPIs, Page 5 |
| mart_branch_performance | Branch rankings, Page 5 |
| mart_payment_activity | Payment mix |
| mart_anomaly_monitoring | Anomaly dashboard, Page 6 |
| mart_transaction_failures | Failure analysis |

Supporting dimensions (optional DirectQuery to `warehouse`):

- dim_date, dim_customer (is_current=true), dim_branch, dim_channel

Audit tables for Page 7:

- `audit.pipeline_runs`
- `audit.data_quality_results`
- `audit.reconciliation_results`

---

## Build Order

1. Import tables listed above
2. Configure relationships per [data_model.md](data_model.md)
3. Create DAX measures from [dax_measures.md](dax_measures.md)
4. Build pages per [dashboard_spec.md](dashboard_spec.md)
5. Apply consistent theme (NovaBank blue #003366, accent #00A3E0)
6. Add disclaimer text box to every page:

   > This project uses synthetic banking data generated solely for demonstrating data engineering, analytics, and transaction-monitoring capabilities. It does not represent real customer or banking data.

---

## Refresh

After pipeline re-run:

- **Import mode:** Home → Refresh
- **Scheduled refresh:** Power BI Service gateway to on-premises/cloud Postgres

---

## Performance Tips

- Import marts only; avoid raw schema
- Hide unused columns
- Use measures for all KPIs
- Sort month names by `month` column not alphabetically

---

## Files in This Folder

| File | Content |
|------|---------|
| dashboard_spec.md | Pages 1–7 visual specifications |
| dax_measures.md | Documented DAX measures |
| data_model.md | Star schema relationships in Power BI |

---

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Connection refused | Start Postgres: `docker compose up -d postgres` or embedded script |
| Wrong port | Read `POSTGRES_PORT` from `.env` after embedded start |
| Empty tables | Run `make pipeline` |
| Relationship errors | Use fact tables from marts (pre-joined) where possible |

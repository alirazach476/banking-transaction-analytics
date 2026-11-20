"""Join REAL Pakistan macro series (SBP policy rate, World Bank CPI, BIS USD/PKR) with monthly SYNTHETIC NovaBank payment KPIs.

The payment generator has no macro inputs, so this is a realism / leakage check, not a causal study: if the synthetic payments were
macro-sensitive we would see it; if not, the correlations should be indistinguishable from zero. Uses month-over-month CHANGES
(levels trend and give spurious correlations) and Spearman + a permutation p-value. Writes docs/MACRO_PAYMENTS_JOIN.md/.json
and the joined table analytics_ext.macro_payments_monthly in the DuckDB warehouse is NOT modified (read-only); CSV goes to data/processed/bi/.
Run (needs .env + Postgres): set -a; . ./.env; set +a; python scripts/join_macro_payments.py
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]
wh = duckdb.connect(str(ROOT / "data" / "warehouse" / "novabank_data.duckdb"), read_only=True)

# --- real macro (same parsing as pakistan_macro_analysis.py) ---
cells = wh.execute("select cell_text from sbp.table_cells where document='sir' and page=1 and col_no=1 and row_no between 7 and 19 order by row_no").df()
pol = pd.DataFrame([(pd.to_datetime(m.group(1), format="%d-%b-%y"), float(m.group(4))) for t in cells.cell_text
                    if (m := re.match(r"(\d{1,2}-[A-Za-z]{3}-\d{2})\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)", t))], columns=["d", "policy"])
x = wh.execute("select time_periodtime_period_or_range tp, obs_valueobservation_value v from bis.ws_xru where ref_areareference_area like 'PK:%' and freqfrequency like 'M:%' and collectioncollection like 'A:%'").df()
fx = pd.Series(pd.to_numeric(x.v).values, index=pd.PeriodIndex(x.tp, freq="M")).sort_index()
cpi = wh.execute("select * from worldbank.d0065307_dr0093087_inflation_data_hcpi_m where country='Pakistan'").df().filter(regex=r"^c_\d{6}$").iloc[0].astype(float)
cpi.index = pd.PeriodIndex([f"{i[2:6]}-{i[6:]}" for i in cpi.index], freq="M")
cpi = cpi.dropna()

# --- synthetic payments, monthly ---
e = create_engine(f"postgresql+psycopg2://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}@{os.environ.get('POSTGRES_HOST','localhost')}:{os.environ['POSTGRES_PORT']}/{os.environ['POSTGRES_DB']}")
pay = pd.read_sql(text("""select date_trunc('month', payment_date)::date m, sum(payments) payments, sum(approved) approved, sum(declined) declined,
                          round(avg(approval_rate)::numeric, 4) approval_rate from analytics.mart_payment_kpis_daily group by 1 order by 1"""), e)
amt = pd.read_sql(text("select date_trunc('month', payment_date)::date m, avg(amount) avg_amount from intermediate.int_payment_outcomes where payment_date is not null and amount is not null group by 1"), e)
pay = pay.merge(amt, on="m")
pay.index = pd.PeriodIndex(pd.to_datetime(pay.m), freq="M")
pay = pay.drop(columns="m").astype(float)

pm = pd.Series(index=pay.index, dtype=float)
for _, r in pol.sort_values("d").iterrows():
    pm[pm.index >= r.d.to_period("M")] = r.policy
J = pay.join(pd.DataFrame({"policy_rate": pm, "cpi_index": cpi.reindex(pay.index), "usd_pkr": fx.reindex(pay.index)}))
J["cpi_yoy_pct"] = (cpi.pct_change(12) * 100).reindex(J.index)
J["avg_amount_real"] = J.avg_amount / (J.cpi_index / J.cpi_index.dropna().iloc[0])   # amount in first-month prices
J["avg_amount_usd"] = J.avg_amount / J.usd_pkr
J = J.dropna(subset=["policy_rate", "cpi_index", "usd_pkr"])
(ROOT / "data" / "processed" / "bi").mkdir(parents=True, exist_ok=True)
J.reset_index(names="month").astype({"month": str}).to_csv(ROOT / "data" / "processed" / "bi" / "macro_payments_monthly.csv", index=False)

D = J[["payments", "approval_rate", "avg_amount", "policy_rate", "cpi_index", "usd_pkr"]].pct_change().dropna()
D["policy_rate"] = J.policy_rate.diff().loc[D.index]            # change in percentage points
rng = np.random.default_rng(7)
out = []
for a in ("payments", "approval_rate", "avg_amount"):
    for b in ("policy_rate", "cpi_index", "usd_pkr"):
        rho = spearmanr(D[a], D[b]).statistic
        perm = np.array([spearmanr(D[a], rng.permutation(D[b].values)).statistic for _ in range(2000)])
        out.append({"payment_metric": a, "macro_change": b, "spearman": round(float(rho), 2), "perm_p": round(float((np.abs(perm) >= abs(rho)).mean()), 3)})
R = {"months_joined": int(len(J)), "span": [str(J.index.min()), str(J.index.max())], "n_changes": int(len(D)), "correlations": out}
R["significant_at_5pct"] = [o for o in out if o["perm_p"] < 0.05]
R["multiple_testing_note"] = f"{len(out)} tests; ~{len(out)*0.05:.1f} would pass 5% by chance alone"
(ROOT / "docs" / "MACRO_PAYMENTS_JOIN.json").write_text(json.dumps(R, indent=2), encoding="utf-8")
L = ["# Real macro series joined to synthetic payments", "",
     f"Months joined: {R['months_joined']} ({R['span'][0]} to {R['span'][1]}); {R['n_changes']} month-over-month changes. Output table: `data/processed/bi/macro_payments_monthly.csv` "
     "(payments, approval rate, avg amount, policy rate, CPI, USD/PKR, real and USD-converted average amount).", "",
     "| payment metric (%chg) | macro change | Spearman | permutation p |", "|---|---|---|---|"]
L += [f"| {o['payment_metric']} | {o['macro_change']} | {o['spearman']} | {o['perm_p']} |" for o in out]
L += ["", f"{len(R['significant_at_5pct'])} of {len(out)} pass p<0.05; {R['multiple_testing_note']}.", "",
      "## Reading",
      "- The payments are SYNTHETIC and the generator uses no macro input, so there is no real relationship to find. Correlations near zero are the expected, correct outcome and confirm no macro leakage into the generator.",
      "- Any pair that passes p<0.05 should be treated as chance given the number of tests and only ~%d changes." % R["n_changes"],
      "- This table is useful for scenario work (e.g. restating synthetic average amounts in real or USD terms), not for estimating how macro conditions affect payments.",
      "- To make macro effects testable, the generator would need an explicit macro-sensitivity model (e.g. volume elasticity to CPI/FX), and then recovery of that elasticity could be validated the same way the logit coefficients were."]
(ROOT / "docs" / "MACRO_PAYMENTS_JOIN.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L))

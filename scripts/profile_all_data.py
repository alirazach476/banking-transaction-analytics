"""Automatic profile of every file/table under data/ as loaded in the DuckDB warehouse (read-only).

For each loaded table: rows, columns, null share (sampled), numeric-column share, detected date range, Pakistan mention, topic tags
(from table/column names), and quality flags. Also reports files that never became a table and the latest load failures.
Writes docs/DATA_PROFILE.md and data/processed/data_profile.csv.   Run: python scripts/profile_all_data.py
"""
from __future__ import annotations

import re
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
con = duckdb.connect(str(ROOT / "data" / "warehouse" / "novabank_data.duckdb"), read_only=True)
tabs = con.execute("select * from catalog.tables").df()
TOPICS = {"inflation_prices": r"cpi|inflation|price|deflat", "fx_rates": r"fx|exchange|xru|eer|currency|usd|forex", "interest_rates": r"rate|kibor|repo|libor|yield|policy|cbpol",
          "credit_debt": r"credit|loan|debt|advance|npl|lend|borrow|dsr", "payments": r"payment|cashless|card|atm|cpmi|remit|transfer|mobile", "money_banking": r"money|m2|m3|deposit|bank|monetary|reserve",
          "gdp_growth": r"gdp|growth|output|production", "trade_bop": r"trade|export|import|balance|bop|bpm", "inclusion": r"findex|inclusion|account", "labour": r"unemploy|labou?r|employ|wage",
          "fiscal": r"fiscal|budget|revenue|tax|expenditure|boost", "pakistan": r"pakistan|\bpak\b|\bpk\b"}
DATE = re.compile(r"date|time_period|period|year|month|^c_\d{4}|^yr|^_year", re.I)


def tags(txt: str) -> str:
    return ",".join(k for k, p in TOPICS.items() if re.search(p, txt, re.I))


rows = []
for t in tabs.itertuples():
    fq = f'"{t.schema_name}"."{t.table_name}"'
    r = {"schema": t.schema_name, "table": t.table_name, "source_file": t.source_file, "rows": int(t.rows_out or 0), "cols": int(t.n_columns or 0)}
    try:
        cols = con.execute(f"select column_name, data_type from information_schema.columns where table_schema='{t.schema_name}' and table_name='{t.table_name}'").fetchall()
        names = [c for c, _ in cols]
        num = [c for c, d in cols if re.search(r"INT|DOUBLE|DECIMAL|FLOAT|HUGEINT", d)]
        r["numeric_col_share"] = round(len(num) / max(len(cols), 1), 2)
        r["tags"] = tags(f"{t.table_name} {t.source_file} {' '.join(names)}")
        if r["rows"]:
            samp = f"(select * from {fq} using sample 5000 rows)" if r["rows"] > 20000 else fq
            sel = ", ".join(f'avg(case when "{c}" is null then 1.0 else 0 end)' for c in names[:60])
            nulls = con.execute(f"select {sel} from {samp}").fetchone()
            r["null_share"] = round(float(sum(nulls) / len(nulls)), 3)
            dcols = [c for c in names if DATE.search(c)][:1]
            if dcols:
                c0 = dcols[0]
                mn, mx = con.execute(f'select min(try_cast("{c0}" as varchar)), max(try_cast("{c0}" as varchar)) from {fq}').fetchone()
                r["date_col"], r["date_min"], r["date_max"] = c0, str(mn)[:12], str(mx)[:12]
            pk = False
            for c in [c for c, d in cols if d == "VARCHAR"][:8]:
                if con.execute(f"select 1 from {samp} where \"{c}\" ilike '%pakistan%' or \"{c}\" ilike 'PK:%' or \"{c}\" = 'PAK' limit 1").fetchone():
                    pk = True
                    break
            r["mentions_pakistan"] = pk
    except Exception as e:  # keep profiling the rest
        r["error"] = str(e)[:120]
    rows.append(r)
P = pd.DataFrame(rows)
P["is_empty"] = P.rows == 0
P["mostly_null"] = P.null_share.fillna(0) > 0.6
(ROOT / "data" / "processed").mkdir(parents=True, exist_ok=True)
P.to_csv(ROOT / "data" / "processed" / "data_profile.csv", index=False)

files = con.execute("select path, extension, size_bytes from catalog.files").df()
tabular = files[files.extension.isin(["csv", "xlsx", "xls"])]
loaded = set(tabs.source_file.dropna().str.split("#").str[0].str.replace("\\", "/", regex=False))
unloaded = tabular[~tabular.path.isin(loaded)]
fails = con.execute("""select item, status, message from (select *, row_number() over (partition by stage, item order by logged_at desc) rn from catalog.load_log)
                       where rn=1 and status='FAILED'""").df()
dups = con.execute("select count(*), sum(copies) from catalog.duplicate_files").fetchone()

L = ["# Data profile: every loaded file and table", "",
     f"Warehouse tables profiled: **{len(P):,}** (from {tabs.source_file.nunique():,} source files); csv/xlsx/xls files catalogued: **{len(tabular):,}**. Null share is sampled (5,000 rows) for tables over 20,000 rows. Full per-table detail: `data/processed/data_profile.csv`.", "",
     "## Overview by schema", "", "| schema | tables | total rows | empty | mostly null (>60%) | mention Pakistan |", "|---|---|---|---|---|---|"]
for s, g in P.groupby("schema"):
    L.append(f"| {s} | {len(g):,} | {int(g.rows.sum()):,} | {int(g.is_empty.sum())} | {int(g.mostly_null.sum())} | {int(g.mentions_pakistan.fillna(False).sum())} |")
L += ["", "## Topic coverage (tables tagged, by name/column keywords; a table can have several tags)", "", "| topic | tables | rows |", "|---|---|---|"]
for k in TOPICS:
    m = P.tags.fillna("").str.contains(k)
    L.append(f"| {k} | {int(m.sum()):,} | {int(P.loc[m, 'rows'].sum()):,} |")
good = P[(~P.is_empty) & (~P.mostly_null) & P.mentions_pakistan.fillna(False)]
L += ["", f"## Pakistan-relevant tables that are non-empty and not mostly null: {len(good)}", "", "| table | rows | date range | tags |", "|---|---|---|---|"]
for r in good.sort_values("rows", ascending=False).head(40).itertuples():
    L.append(f"| {r.schema}.{r.table[:60]} | {r.rows:,} | {r.date_min or ''} to {r.date_max or ''} | {r.tags} |")
L += ["", "## Problems to fix or know about", "",
      f"- Empty tables: **{int(P.is_empty.sum())}**. Mostly-null (>60%): **{int(P.mostly_null.sum())}**. Profiling errors: **{int(P.get('error', pd.Series(dtype=str)).notna().sum())}**.",
      f"- csv/xlsx/xls files that never became a table: **{len(unloaded)}** (listed below, first 40).",
      f"- Duplicate-content file groups: **{dups[0]}** ({dups[1]} files).",
      f"- Latest load status FAILED: **{len(fails)}** items (listed below)."]
if len(fails):
    L += ["", "| item | message |", "|---|---|"] + [f"| {r.item[:70]} | {str(r.message)[:90]} |" for r in fails.head(50).itertuples()]
L += ["", "| unloaded file | ext |", "|---|---|"] + [f"| {r.path[-90:]} | {r.extension} |" for r in unloaded.head(40).itertuples()]
L += ["", "## What this does and does not tell you", "- It is an inventory and quality screen, not an analysis of the content of each table.",
      "- Topic tags come from names and column headers, so they can be wrong; Pakistan detection checks the first 8 text columns only (sampled).",
      "- Next step is analysis of the Pakistan/payments/rates subsets flagged above."]
(ROOT / "docs" / "DATA_PROFILE.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L[:60]))

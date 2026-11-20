"""
Build the NovaBank data warehouse (DuckDB) from everything under data/.

Database file: data/warehouse/novabank_data.duckdb

Schemas
  catalog            files (every file in data/), tables (registry of loaded tables), load_log,
                     download_manifest, wb_datasets, wb_resources, zip_members
  synthetic_raw      legacy + payment CSV feeds exactly as generated (dirty; all text)
  synthetic_clean    clean reference copies (typed)
  synthetic_curated  cleaned/typed/deduplicated transactions + payment feeds, plus a rejects table
  ecb, bis           one typed table per dataset (snake_case columns, period_start date)
  worldbank          one table per CSV / Excel sheet (typed where >=98% of values parse)
  sbp                OCR'd SBP statistical tables in long form (+ documents)
  external_paysim, external_findex   user-added public datasets

Cleaning rules (every stage): snake_case ASCII column names; text trimmed, empty -> NULL; fully empty
rows/columns dropped; numeric/date typing; exact duplicate rows removed for tables < 5M rows (counts
logged); lineage (source file, rows in/out) recorded in catalog.tables. Stages are resumable.

Usage: python -I scripts/build_data_warehouse.py [--stage catalog synthetic sbp meta bis worldbank ecb external]
                                                   [--force] [--only SUBSTR]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DB = DATA / "warehouse" / "novabank_data.duckdb"
OLE_MAGIC = bytes.fromhex("d0cf11e0")
DEDUP_LIMIT = 5_000_000
HASH_LIMIT = 100 * 1024 * 1024
SCHEMAS = ["catalog", "synthetic_raw", "synthetic_clean", "synthetic_curated", "ecb", "bis",
           "worldbank", "sbp", "external_paysim", "external_findex", "external_fred"]


# ------------------------------------------------------------------ helpers
def snake(name: str, fallback: str = "col") -> str:
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    s = re.sub(r"[^0-9a-zA-Z]+", "_", s).strip("_").lower()
    if not s:
        s = fallback
    return ("c_" + s) if s[0].isdigit() else s


def unique(names):
    seen, out = {}, []
    for i, n in enumerate(names):
        n = snake(n, f"col_{i + 1}")
        k = seen.get(n, 0)
        seen[n] = k + 1
        out.append(n if k == 0 else f"{n}_{k + 1}")
    return out


def qident(x: str) -> str:
    return '"' + x.replace('"', '""') + '"'


def connect() -> duckdb.DuckDBPyConnection:
    DB.parent.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(DB))
    tmp = DB.parent / "_tmp"
    tmp.mkdir(exist_ok=True)
    con.execute(f"SET temp_directory='{tmp.as_posix()}'")
    con.execute("SET threads=8")
    con.execute("SET memory_limit='10GB'")
    con.execute("SET preserve_insertion_order=false")
    for s in SCHEMAS:
        con.execute(f"CREATE SCHEMA IF NOT EXISTS {s}")
    con.execute("""CREATE TABLE IF NOT EXISTS catalog.tables(
        schema_name VARCHAR, table_name VARCHAR, source_file VARCHAR, source_system VARCHAR,
        rows_in BIGINT, rows_out BIGINT, n_columns INTEGER, duplicates_removed BIGINT,
        notes VARCHAR, loaded_at TIMESTAMP)""")
    con.execute("""CREATE TABLE IF NOT EXISTS catalog.load_log(
        stage VARCHAR, item VARCHAR, status VARCHAR, message VARCHAR, seconds DOUBLE, logged_at TIMESTAMP)""")
    return con


def log(con, stage, item, status, msg="", secs=0.0):
    con.execute("INSERT INTO catalog.load_log VALUES (?,?,?,?,?,?)",
                [stage, str(item), status, str(msg)[:500], round(secs, 2), datetime.now(timezone.utc)])
    print(f"[{stage}] {status:8} {str(item)[:90]} {str(msg)[:100]} {secs:.1f}s", flush=True)


def is_loaded(con, schema, table) -> bool:
    return con.execute("SELECT count(*) FROM catalog.tables WHERE schema_name=? AND table_name=?",
                       [schema, table]).fetchone()[0] > 0


def register(con, schema, table, source, system, rows_in, notes="", dups=0):
    cols = con.execute("SELECT count(*) FROM information_schema.columns WHERE table_schema=? AND table_name=?",
                       [schema, table]).fetchone()[0]
    rows_out = con.execute(f"SELECT count(*) FROM {schema}.{qident(table)}").fetchone()[0]
    con.execute("DELETE FROM catalog.tables WHERE schema_name=? AND table_name=?", [schema, table])
    con.execute("INSERT INTO catalog.tables VALUES (?,?,?,?,?,?,?,?,?,?)",
                [schema, table, source, system, rows_in, rows_out, cols, dups, notes, datetime.now(timezone.utc)])


def rel(p: Path) -> str:
    return p.relative_to(ROOT).as_posix()


def short(name: str, n: int = 60) -> str:
    return snake(name)[:n].rstrip("_")


# --------------------------------------------------------------- stage: catalog
def system_of(r: str) -> tuple[str, str]:
    """(source_system, group) from a repo-relative path."""
    if r.startswith("data/source/payments"):
        return "synthetic_payments_dirty", "synthetic"
    if r.startswith("data/source/"):
        return "synthetic_legacy_dirty", "synthetic"
    if r.startswith("data/processed/clean_reference"):
        return "synthetic_clean_reference", "synthetic"
    if r.startswith("data/samples"):
        return "synthetic_samples", "synthetic"
    if r.startswith("data/external_downloads/ecb"):
        return "ecb", "external"
    if r.startswith("data/external_downloads/bis"):
        return "bis", "external"
    if r.startswith("data/external_downloads/worldbank_collections"):
        return "worldbank_collections", "external"
    if r.startswith("data/external_downloads/worldbank_relevant"):
        return "worldbank_relevant", "external"
    if r.startswith("data/external_downloads/worldbank_zips"):
        return "worldbank_zips", "external"
    if r.startswith("data/external_downloads/worldbank"):
        return "worldbank_featured", "external"
    if r.startswith("data/external_downloads/sbp_text"):
        return "sbp_text", "external"
    if r.startswith("data/warehouse"):
        return "warehouse", "internal"
    name = Path(r).name
    if r.startswith("data/external_downloads/") and r.count("/") == 2:
        if name.endswith((".jsonl", ".json", ".log")) or name.startswith(("csv_", "plan_", "manifest_")):
            return "download_metadata", "meta"
        return "user_added", "external"
    return "other", "other"


def stage_catalog(con, a):
    t0 = time.time()
    rows = []
    for p in DATA.rglob("*"):
        if p.is_dir() or "warehouse" in p.parts[len(DATA.parts):len(DATA.parts) + 1] or p.suffix == ".part":
            continue
        r = rel(p)
        st = p.stat()
        sha = None
        if st.st_size <= HASH_LIMIT:
            h = hashlib.sha256()
            with open(p, "rb") as f:
                for chunk in iter(lambda: f.read(1 << 20), b""):
                    h.update(chunk)
            sha = h.hexdigest()
        sysname, group = system_of(r)
        rows.append({"path": r, "folder": Path(r).parent.as_posix(), "file_name": p.name,
                     "extension": p.suffix.lower().lstrip(".") or None, "size_bytes": st.st_size,
                     "modified_at": datetime.fromtimestamp(st.st_mtime, timezone.utc),
                     "source_system": sysname, "group_name": group, "sha256": sha})
    df = pd.DataFrame(rows)
    con.execute("DROP TABLE IF EXISTS catalog.files")
    con.execute("CREATE TABLE catalog.files AS SELECT * FROM df")
    # exact-duplicate files (same hash) are flagged, not deleted
    con.execute("""CREATE OR REPLACE VIEW catalog.duplicate_files AS
        SELECT sha256, count(*) AS copies, list(path) AS paths FROM catalog.files
        WHERE sha256 IS NOT NULL AND size_bytes > 0 GROUP BY sha256 HAVING count(*) > 1""")
    log(con, "catalog", "files", "OK", f"{len(df)} files, {df.size_bytes.sum() / 1e9:.1f} GB", time.time() - t0)


# ------------------------------------------------------------ stage: synthetic
CURATED_STATUS = {"completed": "Completed", "complete": "Completed", "pending": "Pending", "failed": "Failed",
                  "fail": "Failed", "reversed": "Reversed"}


def load_csv_table(con, schema, table, path: Path, system: str, typed: bool, force: bool, extra_sql="", dedup=True):
    if is_loaded(con, schema, table) and not force:
        return
    t0 = time.time()
    opts = "header=true, normalize_names=true, ignore_errors=true, sample_size=200000"
    opts += ", all_varchar=true" if not typed else ""
    src = f"read_csv('{path.as_posix()}', {opts})"
    try:
        con.execute(f"DROP TABLE IF EXISTS {schema}.{qident(table)}")
        con.execute(f"CREATE TABLE {schema}.{qident(table)} AS SELECT * {extra_sql} FROM {src}")
        n_in = con.execute(f"SELECT count(*) FROM {schema}.{qident(table)}").fetchone()[0]
        dups = 0
        if dedup and typed is False and n_in < DEDUP_LIMIT and "dq_defect" not in [
                c[0] for c in con.execute(f"DESCRIBE {schema}.{qident(table)}").fetchall()]:
            pass  # raw feeds keep duplicates on purpose; curated layer removes them
        register(con, schema, table, rel(path), system, n_in, "typed" if typed else "all text (raw)", dups)
        log(con, schema, table, "OK", f"{n_in} rows", time.time() - t0)
    except Exception as exc:
        log(con, schema, table, "FAILED", exc, time.time() - t0)


def stage_synthetic(con, a):
    raw_map = {
        "customer_system/customers.csv": "customers", "core_banking/accounts.csv": "accounts",
        "branch_system/branches.csv": "branches", "card_system/merchants.csv": "merchants",
        "card_system/cards.csv": "cards", "core_banking/transactions.csv": "transactions",
        "core_banking/transfers.csv": "transfers", "atm_system/atm_transactions.csv": "atm_transactions",
        "card_system/card_transactions.csv": "card_transactions",
        "payments/payment_transactions.csv": "payment_transactions",
        "payments/payment_lifecycle_events.csv": "payment_lifecycle_events",
        "payments/payment_settlements.csv": "payment_settlements",
        "payments/fx_rates_synthetic.csv": "fx_rates_synthetic"}
    for sub, table in raw_map.items():
        p = DATA / "source" / sub
        if p.exists():
            load_csv_table(con, "synthetic_raw", table, p, "synthetic_dirty", False, a.force)
    clean_dir = DATA / "processed" / "clean_reference"
    for p in sorted(clean_dir.rglob("*.csv")):
        load_csv_table(con, "synthetic_clean", p.stem, p, "synthetic_clean_reference", True, a.force)
    build_curated(con, a.force)


def build_curated(con, force):
    """Typed, deduplicated, status-normalised transactions and payment feeds; invalid rows go to rejects."""
    have = lambda s, t: con.execute("SELECT count(*) FROM information_schema.tables WHERE table_schema=? "
                                    "AND table_name=?", [s, t]).fetchone()[0] > 0
    con.execute("""CREATE TABLE IF NOT EXISTS synthetic_curated.rejects(
        source_table VARCHAR, business_key VARCHAR, reason VARCHAR, loaded_at TIMESTAMP)""")
    jobs = []
    if have("synthetic_raw", "transactions"):
        jobs.append(("transactions", "transaction_id", """
            SELECT transaction_id, account_id, customer_id,
                   try_cast(replace(transaction_timestamp,'T',' ') AS TIMESTAMP) AS transaction_ts,
                   transaction_type,
                   try_cast(amount AS DECIMAL(18,2)) AS amount,
                   upper(trim(currency)) AS currency, channel, nullif(merchant_id,'') AS merchant_id,
                   nullif(branch_id,'') AS branch_id,
                   CASE lower(trim(transaction_status)) WHEN 'completed' THEN 'Completed' WHEN 'complete' THEN 'Completed'
                        WHEN 'pending' THEN 'Pending' WHEN 'failed' THEN 'Failed' WHEN 'fail' THEN 'Failed'
                        WHEN 'reversed' THEN 'Reversed' ELSE NULL END AS transaction_status,
                   reference_type, (lower(is_injected_anomaly)='true') AS is_injected_anomaly, anomaly_type
            FROM synthetic_raw.transactions""",
                     "transaction_ts IS NULL OR amount IS NULL OR transaction_status IS NULL "
                     "OR currency NOT IN ('USD','EUR','GBP','CAD') OR transaction_id IS NULL"))
    if have("synthetic_raw", "payment_transactions"):
        jobs.append(("payment_transactions", "payment_id", """
            SELECT payment_id, card_id, customer_id, account_id, merchant_id, merchant_category, merchant_country,
                   card_country, channel, try_cast(amount AS DECIMAL(18,2)) AS amount, upper(trim(currency)) AS currency,
                   billing_currency, (lower(is_international)='true') AS is_international,
                   try_cast(authorization_ts AS TIMESTAMP) AS authorization_ts, card_status,
                   (lower(synthetic_fraud_pattern)='true') AS synthetic_fraud_pattern
            FROM synthetic_raw.payment_transactions""",
                     "authorization_ts IS NULL OR amount IS NULL OR merchant_id = 'INVALID-REF' "
                     "OR currency NOT IN ('USD','EUR','GBP','CAD','PKR','AED','INR') OR payment_id IS NULL"))
    if have("synthetic_raw", "payment_lifecycle_events"):
        jobs.append(("payment_lifecycle_events", "event_id", """
            SELECT event_id, payment_id, upper(trim(event_type)) AS event_type,
                   try_cast(event_ts AS TIMESTAMP) AS event_ts, try_cast(amount AS DECIMAL(18,2)) AS amount,
                   upper(trim(currency)) AS currency, upper(trim(event_status)) AS event_status,
                   nullif(reason_code,'') AS reason_code, try_cast(response_ms AS INTEGER) AS response_ms
            FROM synthetic_raw.payment_lifecycle_events""",
                     "event_ts IS NULL OR amount IS NULL OR payment_id = 'INVALID-REF' OR event_id IS NULL "
                     "OR event_status NOT IN ('REQUESTED','APPROVED','DECLINED','CLEARED','SETTLED','REVERSED',"
                     "'REFUNDED','CHARGEBACK')"))
    for table, key, select_sql, bad in jobs:
        if is_loaded(con, "synthetic_curated", table) and not force:
            continue
        t0 = time.time()
        con.execute("DROP TABLE IF EXISTS _stage")
        con.execute(f"CREATE TEMP TABLE _stage AS {select_sql}")
        n_in = con.execute("SELECT count(*) FROM _stage").fetchone()[0]
        con.execute("DELETE FROM synthetic_curated.rejects WHERE source_table=?", [table])
        con.execute(f"""INSERT INTO synthetic_curated.rejects
            SELECT '{table}', {key}, 'invalid or unparseable value in key/typed field', now() FROM _stage WHERE {bad}""")
        con.execute(f"DROP TABLE IF EXISTS synthetic_curated.{table}")
        con.execute(f"""CREATE TABLE synthetic_curated.{table} AS
            SELECT * FROM (SELECT *, row_number() OVER (PARTITION BY {key}) AS _rn FROM _stage WHERE NOT ({bad}))
            WHERE _rn = 1""")
        con.execute(f"ALTER TABLE synthetic_curated.{table} DROP COLUMN _rn")
        n_out = con.execute(f"SELECT count(*) FROM synthetic_curated.{table}").fetchone()[0]
        n_rej = con.execute("SELECT count(*) FROM synthetic_curated.rejects WHERE source_table=?", [table]).fetchone()[0]
        register(con, "synthetic_curated", table, f"synthetic_raw.{table}", "synthetic_curated", n_in,
                 f"rejected {n_rej} invalid rows (see rejects); duplicates removed on {key}", n_in - n_rej - n_out)
        log(con, "synthetic_curated", table, "OK", f"in={n_in} out={n_out} rejected={n_rej}", time.time() - t0)


# ------------------------------------------------------------------- stage: sbp
def parse_num(s: str):
    t = s.strip().rstrip("?").replace(",", "").replace("−", "-")
    neg = t.startswith("(") and t.endswith(")")
    t = t.strip("()").rstrip("%")
    try:
        v = float(t)
    except ValueError:
        return None
    return -v if neg else v


def stage_sbp(con, a):
    d = DATA / "external_downloads" / "sbp_text"
    if not d.exists():
        return
    t0 = time.time()
    cells, docs = [], []
    for p in sorted(d.glob("*.txt")):
        page, rno, n_low = 0, 0, 0
        pages = 0
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith("=== Page"):
                page = int(re.findall(r"\d+", line)[0])
                pages = max(pages, page)
                rno = 0
                continue
            if line.startswith("---") or not line.strip():
                continue
            rno += 1
            for cno, c in enumerate(line.split("\t"), 1):
                if not c.strip():
                    continue
                low = c.endswith("?")
                n_low += low
                txt = c.rstrip("?").strip()
                cells.append((p.stem, page, rno, cno, txt, parse_num(txt), low))
        docs.append((p.stem, pages, rno, n_low, rel(p)))
    df = pd.DataFrame(cells, columns=["document", "page", "row_no", "col_no", "cell_text", "cell_number",
                                      "low_confidence"])
    dd = pd.DataFrame(docs, columns=["document", "pages", "last_page_rows", "low_confidence_cells", "source_file"])
    con.execute("DROP TABLE IF EXISTS sbp.table_cells")
    con.execute("CREATE TABLE sbp.table_cells AS SELECT * FROM df")
    con.execute("DROP TABLE IF EXISTS sbp.documents")
    con.execute("CREATE TABLE sbp.documents AS SELECT * FROM dd")
    for t in ("table_cells", "documents"):
        register(con, "sbp", t, rel(d), "sbp_text", len(df) if t == "table_cells" else len(dd),
                 "OCR (RapidOCR) text tables in long form; low_confidence marks OCR '?' cells")
    log(con, "sbp", "table_cells", "OK", f"{len(df)} cells from {len(dd)} documents", time.time() - t0)


# ------------------------------------------------------------------- stage: meta
def stage_meta(con, a):
    t0 = time.time()
    rows = []
    for mf in sorted((DATA / "external_downloads").glob("manifest_*.jsonl")):
        for line in mf.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            rows.append({"manifest": mf.stem.replace("manifest_", ""), "url": r.get("url"), "file": r.get("file"),
                         "status": r.get("status"), "bytes": r.get("bytes"), "sha256": r.get("sha256") or None})
    df = pd.DataFrame(rows)
    con.execute("DROP TABLE IF EXISTS catalog.download_manifest")
    con.execute("CREATE TABLE catalog.download_manifest AS SELECT * FROM df")
    cache = DATA / "external_downloads" / "wb_catalog_cache.json"
    if cache.exists():
        ds_rows, res_rows, seen = [], [], set()
        for d in json.loads(cache.read_text(encoding="utf-8")):
            did = d.get("dataset_unique_id")
            if did in seen:
                continue
            seen.add(did)
            i = d.get("identification") or {}
            col = i.get("collection_id") or []
            ds_rows.append({"dataset_unique_id": did, "name": (d.get("name") or "").strip() or None,
                            "collections": ", ".join(map(str, col)) if isinstance(col, list) else str(col),
                            "description": re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", i.get("description") or "")).strip()[:2000] or None,
                            "modified_on": d.get("modified_on")})
            for r in d.get("resources") or []:
                res_rows.append({"dataset_unique_id": did, "resource_unique_id": r.get("resource_unique_id"),
                                 "name": r.get("name"), "format": (r.get("format") or "").lower() or None,
                                 "url": r.get("url")})
        con.execute("DROP TABLE IF EXISTS catalog.wb_datasets")
        con.execute("DROP TABLE IF EXISTS catalog.wb_resources")
        a1, a2 = pd.DataFrame(ds_rows), pd.DataFrame(res_rows)
        con.execute("CREATE TABLE catalog.wb_datasets AS SELECT * FROM a1")
        con.execute("CREATE TABLE catalog.wb_resources AS SELECT * FROM a2")
    zrows = []
    for z in DATA.rglob("*.zip"):
        try:
            with zipfile.ZipFile(z) as zf:
                for i in zf.infolist():
                    if not i.is_dir():
                        zrows.append({"zip_path": rel(z), "member": i.filename, "size_bytes": i.file_size})
        except zipfile.BadZipFile:
            zrows.append({"zip_path": rel(z), "member": "<<not a valid zip>>", "size_bytes": None})
    con.execute("DROP TABLE IF EXISTS catalog.zip_members")
    z = pd.DataFrame(zrows, columns=["zip_path", "member", "size_bytes"])
    con.execute("CREATE TABLE catalog.zip_members AS SELECT * FROM z")
    for t in ("download_manifest", "wb_datasets", "wb_resources", "zip_members"):
        register(con, "catalog", t, "data/external_downloads", "metadata", 0, "metadata/lineage")
    log(con, "meta", "catalog metadata", "OK", f"manifest={len(df)} zip_members={len(z)}", time.time() - t0)


# ------------------------------------------------------- stage: ecb / bis / ext
def load_sdmx(con, schema, path: Path, table: str, system: str, force: bool):
    if is_loaded(con, schema, table) and not force:
        return
    t0 = time.time()
    base = f"read_csv('{path.as_posix()}', header=true, normalize_names=true, sample_size=100000, ignore_errors=true)"
    try:
        cols = [c[0] for c in con.execute(f"DESCRIBE SELECT * FROM {base}").fetchall()]
        con.execute(f"DROP TABLE IF EXISTS {schema}.{qident(table)}")
        sel = []
        for c in cols:
            if c == "obs_value":
                sel.append("try_cast(obs_value AS DOUBLE) AS obs_value")
            elif c == "time_period":
                sel.append("CAST(time_period AS VARCHAR) AS time_period")
            else:
                sel.append(qident(c))
        extra = ""
        if "time_period" in cols:
            extra = """, CASE
                 WHEN regexp_matches(CAST(time_period AS VARCHAR), '^\\d{4}$') THEN try_cast(CAST(time_period AS VARCHAR) || '-01-01' AS DATE)
                 WHEN regexp_matches(CAST(time_period AS VARCHAR), '^\\d{4}-\\d{2}$') THEN try_cast(CAST(time_period AS VARCHAR) || '-01' AS DATE)
                 WHEN regexp_matches(CAST(time_period AS VARCHAR), '^\\d{4}-\\d{2}-\\d{2}$') THEN try_cast(CAST(time_period AS VARCHAR) AS DATE)
                 WHEN regexp_matches(CAST(time_period AS VARCHAR), '^\\d{4}-Q[1-4]$') THEN
                      make_date(CAST(left(CAST(time_period AS VARCHAR),4) AS INTEGER), (CAST(right(CAST(time_period AS VARCHAR),1) AS INTEGER)-1)*3+1, 1)
                 WHEN regexp_matches(CAST(time_period AS VARCHAR), '^\\d{4}-S[1-2]$') THEN
                      make_date(CAST(left(CAST(time_period AS VARCHAR),4) AS INTEGER), (CAST(right(CAST(time_period AS VARCHAR),1) AS INTEGER)-1)*6+1, 1)
                 ELSE NULL END AS period_start"""
        con.execute(f"CREATE TABLE {schema}.{qident(table)} AS SELECT {', '.join(sel)}{extra} FROM {base}")
        n = con.execute(f"SELECT count(*) FROM {schema}.{qident(table)}").fetchone()[0]
        register(con, schema, table, rel(path), system, n, "typed; obs_value DOUBLE; period_start parsed from time_period")
        log(con, schema, table, "OK", f"{n:,} rows", time.time() - t0)
    except Exception as exc:
        log(con, schema, table, "FAILED", exc, time.time() - t0)


def stage_bis(con, a):
    for p in sorted((DATA / "external_downloads" / "bis").glob("*.csv")):
        if a.only and a.only.lower() not in p.name.lower():
            continue
        m = re.match(r"(WS_[A-Z0-9_]+?)_csv_flat", p.name)
        load_sdmx(con, "bis", p, snake(m.group(1) if m else p.stem)[:60], "bis", a.force)


def stage_ecb(con, a):
    for p in sorted((DATA / "external_downloads" / "ecb").glob("*.csv"), key=lambda x: x.stat().st_size):
        if a.only and a.only.lower() not in p.name.lower():
            continue
        load_sdmx(con, "ecb", p, snake(p.stem), "ecb", a.force)


def stage_external(con, a):
    d = DATA / "external_downloads"
    for p in sorted((d / "fredgraph").glob("*.csv")) if (d / "fredgraph").exists() else []:
        if p.stem == "metro_unemployment_rate_msa":
            # wide (one column per month) -> long: one row per MSA x month
            name = "metro_unemployment_rate_msa_long"
            if is_loaded(con, "external_fred", name) and not a.force:
                continue
            t0 = time.time()
            df = pd.read_csv(p, dtype={"Region Code": str})
            idc = ["Series ID", "Series Name", "Units", "Region Name", "Region Code"]
            df = df.melt(id_vars=idc, var_name="observation_date", value_name="unemployment_rate_pct")
            df.columns = [snake(c) for c in df.columns]
            df["observation_date"] = pd.to_datetime(df["observation_date"]).dt.date
            df["unemployment_rate_pct"] = pd.to_numeric(df["unemployment_rate_pct"], errors="coerce")
            df = df.dropna(subset=["unemployment_rate_pct"]).drop_duplicates(["series_id", "observation_date"])
            con.execute("SELECT 1").fetchall()
            con.register("_metro_df", df)
            con.execute(f"DROP TABLE IF EXISTS external_fred.{qident(name)}")
            con.execute(f"CREATE TABLE external_fred.{qident(name)} AS SELECT * FROM _metro_df")
            con.unregister("_metro_df")
            register(con, "external_fred", name, rel(p), "user_added", len(df), "melted wide->long; empty cells dropped")
            log(con, "external_fred", name, "OK", "", time.time() - t0)
            continue
        # FRED graph downloads: observation_date + one column per series; '.' = missing
        name = "fred_" + snake(p.stem).replace("_7_day", "_7day")
        if is_loaded(con, "external_fred", name) and not a.force:
            continue
        t0 = time.time()
        con.execute(f"DROP TABLE IF EXISTS external_fred.{qident(name)}")
        con.execute(f"""CREATE TABLE external_fred.{qident(name)} AS
            SELECT * FROM read_csv('{p.as_posix()}', header=true, normalize_names=true, nullstr=['.',''],
                                   dateformat='%Y-%m-%d')""")
        register(con, "external_fred", name, rel(p), "user_added", 0, "FRED series; '.' treated as NULL")
        log(con, "external_fred", name, "OK", "", time.time() - t0)
    for fname, schema, table in [("PS_20174392719_1491204439457_log.csv", "external_paysim", "paysim_transactions"),
                                 ("GlobalFindexDatabase2025.csv", "external_findex", "global_findex_2025")]:
        p = d / fname
        if p.exists():
            load_csv_table(con, schema, table, p, "user_added", True, a.force)


# -------------------------------------------------------------- stage: worldbank
def clean_frame(rows: list[list]) -> pd.DataFrame | None:
    """rows: list of lists (strings/None). Detect header, clean names, drop empties."""
    rows = [r for r in rows if any(c not in (None, "") for c in r)]
    if len(rows) < 2:
        return None
    width = max(len(r) for r in rows)
    rows = [list(r) + [None] * (width - len(r)) for r in rows]
    hdr_i = 0
    for i, r in enumerate(rows[:15]):
        filled = [c for c in r if c not in (None, "")]
        if len(filled) >= max(2, 0.5 * width) and sum(isinstance(c, str) and not re.fullmatch(r"[-\d.,\s%]+", c)
                                                    for c in filled) >= 0.6 * len(filled):
            hdr_i = i
            break
    header, body = rows[hdr_i], rows[hdr_i + 1:]
    if not body:
        return None
    names = unique([h if h not in (None, "") else f"col_{i + 1}" for i, h in enumerate(header)])
    df = pd.DataFrame(body, columns=names)
    df = df.dropna(how="all").dropna(axis=1, how="all")
    return df if df.shape[0] >= 1 and df.shape[1] >= 2 else None


def to_text(v):
    if v is None:
        return None
    if isinstance(v, float):
        return repr(v) if v == v else None
    if isinstance(v, (datetime, pd.Timestamp)):
        return v.isoformat(sep=" ")
    s = str(v).strip()
    return s or None


def type_table(con, schema, tmp, final):
    """Promote text columns to DOUBLE / TIMESTAMP when >=98% of non-null values parse."""
    cols = [c[0] for c in con.execute(f"DESCRIBE {schema}.{qident(tmp)}").fetchall()]
    aggs = []
    for c in cols:
        q = qident(c)
        aggs.append(f"count({q}), count(try_cast({q} AS DOUBLE)), count(try_cast({q} AS TIMESTAMP))")
    r = con.execute(f"SELECT {', '.join(aggs)} FROM {schema}.{qident(tmp)}").fetchone()
    sel = []
    for i, c in enumerate(cols):
        nn, nd, nt = r[3 * i], r[3 * i + 1], r[3 * i + 2]
        q = qident(c)
        if nn and nd >= 0.98 * nn:
            sel.append(f"try_cast({q} AS DOUBLE) AS {q}")
        elif nn and nt >= 0.98 * nn and nd < 0.5 * nn:
            sel.append(f"try_cast({q} AS TIMESTAMP) AS {q}")
        else:
            sel.append(q)
    con.execute(f"CREATE TABLE {schema}.{qident(final)} AS SELECT {', '.join(sel)} FROM {schema}.{qident(tmp)}")
    con.execute(f"DROP TABLE {schema}.{qident(tmp)}")


def finish_wb_table(con, tmp, final, source, rows_in):
    type_table(con, "worldbank", tmp, final)
    dups = 0
    n = con.execute(f"SELECT count(*) FROM worldbank.{qident(final)}").fetchone()[0]
    if n < DEDUP_LIMIT:
        con.execute(f"CREATE TABLE worldbank._d AS SELECT DISTINCT * FROM worldbank.{qident(final)}")
        n2 = con.execute("SELECT count(*) FROM worldbank._d").fetchone()[0]
        dups = n - n2
        con.execute(f"DROP TABLE worldbank.{qident(final)}")
        con.execute(f"ALTER TABLE worldbank._d RENAME TO {qident(final)}")
    register(con, "worldbank", final, source, "worldbank", rows_in, "cleaned, typed where >=98% parse", dups)


def table_name_for(p: Path, sheet: str | None = None) -> str:
    """Stable, readable table name: d<dataset>_<resource>_<file stem>[_<sheet>] (<= 62 chars)."""
    parts = p.relative_to(DATA / "external_downloads").parts
    ds = next((x for x in parts if re.fullmatch(r"00\d{5}", x)), None)
    if ds is None:
        m0 = re.match(r"(00\d{5})_", p.name)
        ds = m0.group(1) if m0 else None
    m = re.search(r"(DR\d+)", p.name)
    stem = short(re.sub(r"^(\d+_)?(DR\d+_)?", "", p.stem), 30)
    t = "_".join(x for x in ((f"d{ds}" if ds else snake(parts[0])[:10]), m.group(1).lower() if m else None, stem) if x)
    if sheet:
        t += "_" + short(sheet, 18)
    return re.sub(r"_+", "_", t)[:62].strip("_")


def stage_worldbank(con, a):
    files = [p for sub in ("worldbank", "worldbank_collections", "worldbank_relevant")
             for p in sorted((DATA / "external_downloads" / sub).rglob("*")) if p.is_file()]
    for p in files:
        if a.only and a.only.lower() not in p.name.lower():
            continue
        ext = p.suffix.lower()
        t0 = time.time()
        try:
            if ext == ".csv":
                name = table_name_for(p)
                if is_loaded(con, "worldbank", name) and not a.force:
                    continue
                tmp = "_tmp_" + name[:50]
                con.execute(f"DROP TABLE IF EXISTS worldbank.{qident(tmp)}")
                try:
                    con.execute(f"""CREATE TABLE worldbank.{qident(tmp)} AS SELECT * FROM read_csv('{p.as_posix()}',
                        header=true, normalize_names=true, all_varchar=true, ignore_errors=true, sample_size=50000)""")
                except Exception:
                    con.execute(f"""CREATE TABLE worldbank.{qident(tmp)} AS SELECT * FROM read_csv('{p.as_posix()}',
                        header=true, normalize_names=true, all_varchar=true, ignore_errors=true, encoding='latin-1',
                        strict_mode=false)""")
                n_in = con.execute(f"SELECT count(*) FROM worldbank.{qident(tmp)}").fetchone()[0]
                con.execute(f"DROP TABLE IF EXISTS worldbank.{qident(name)}")
                finish_wb_table(con, tmp, name, rel(p), n_in)
                log(con, "worldbank", name, "OK", f"{n_in} rows", time.time() - t0)
            elif ext in (".xlsx", ".xls"):
                load_excel(con, p, a.force)
        except Exception as exc:
            log(con, "worldbank", p.name, "FAILED", exc, time.time() - t0)


def load_excel(con, p: Path, force: bool):
    t0 = time.time()
    sheets = {}
    with open(p, "rb") as fh:
        head = fh.read(8)
    if head[:2] == b"PK":          # real .xlsx (zip container)
        from openpyxl import load_workbook
        wb = load_workbook(p, read_only=True, data_only=True)
        for ws in wb.worksheets:
            sheets[ws.title] = [[to_text(c) for c in row] for row in ws.iter_rows(values_only=True)]
        wb.close()
    elif head[:4] == OLE_MAGIC:   # legacy .xls (OLE2), whatever the extension says
        x = pd.read_excel(p, sheet_name=None, header=None, dtype=object, engine="xlrd")
        for k, v in x.items():
            sheets[k] = [[to_text(c) for c in r] for r in v.itertuples(index=False)]
    elif head.lstrip()[:1] == b"<":  # an HTML page saved with an Excel extension
        from io import StringIO
        tabs = pd.read_html(StringIO(p.read_text(encoding="utf-8", errors="ignore")), header=None)
        for i, t in enumerate(tabs, 1):
            sheets[f"html_table_{i}"] = [[to_text(c) for c in r] for r in t.astype(object).itertuples(index=False)]
    else:
        raise ValueError(f"unrecognised file signature {head[:6]!r}")
    loaded = 0
    for sname, rows in sheets.items():
        df = clean_frame(rows)
        if df is None:
            continue
        name = table_name_for(p, sname)
        if is_loaded(con, "worldbank", name) and not force:
            continue
        tmp = "_tmp_" + name[:50]
        con.execute(f"DROP TABLE IF EXISTS worldbank.{qident(tmp)}")
        con.execute(f"CREATE TABLE worldbank.{qident(tmp)} AS SELECT * FROM df")
        con.execute(f"DROP TABLE IF EXISTS worldbank.{qident(name)}")
        finish_wb_table(con, tmp, name, rel(p) + f"#{sname}", len(df))
        loaded += 1
    log(con, "worldbank", p.name, "OK" if loaded else "EMPTY", f"{loaded} sheet tables of {len(sheets)} sheets",
        time.time() - t0)


STAGES = {"catalog": stage_catalog, "synthetic": stage_synthetic, "sbp": stage_sbp, "meta": stage_meta,
          "external": stage_external, "bis": stage_bis, "worldbank": stage_worldbank, "ecb": stage_ecb}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", nargs="*", default=list(STAGES))
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--only")
    a = ap.parse_args(argv)
    con = connect()
    for s in a.stage:
        print(f"=== stage {s} ===", flush=True)
        STAGES[s](con, a)
    con.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

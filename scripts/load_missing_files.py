"""Load the CSV/Excel files that never became warehouse tables, and parse the SBP OCR text into a queryable row table.

1. Missing files = catalog.files (csv/xlsx/xls) whose path is not a source_file of any table and whose content hash is not already
   loaded. Excel files are read by their real signature (many '.xlsx' are legacy .xls) through build_data_warehouse.load_excel.
   Table names are made unique (hash suffix on collision) so a name clash can never silently skip a file again.
2. sbp.rows_parsed: one row per OCR text line with label, numeric values v1..v24 and the raw line (heuristic split, see docs).
Run (nothing else may hold the DuckDB file): python scripts/load_missing_files.py [--sbp-only] [--skip-big]
"""
from __future__ import annotations

import argparse
import importlib.util
import re
import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("bdw", ROOT / "scripts" / "build_data_warehouse.py")
bdw = importlib.util.module_from_spec(spec)
sys.modules["bdw"] = bdw
spec.loader.exec_module(bdw)

NUM = re.compile(r"^\(?-?\d[\d,]*(\.\d+)?\)?%?[A-Za-z]?$")
ORD = re.compile(r"^\d+(\.\d+)*\.$")          # list numbering such as '1.1.'


def missing_files(con) -> pd.DataFrame:
    f = con.execute("select path, extension, size_bytes, sha256 from catalog.files where extension in ('csv','xlsx','xls')").df()
    src = con.execute("select source_file from catalog.tables").df().source_file.dropna()
    loaded = set(src.str.split("#").str[0].str.replace("\\", "/", regex=False))
    f["loaded"] = f.path.isin(loaded)
    u = f[~f.loaded & ~f.sha256.isin(set(f[f.loaded].sha256))].sort_values(["size_bytes"])
    return u[~u.sha256.duplicated()]


def unique_name(con, schema: str, base: str, sha: str) -> str:
    return base if not bdw.is_loaded(con, schema, base) else (base[:54] + "_" + sha[:6])


def load_csv(con, p: Path, name: str, sha: str, schema: str):
    t0 = time.time()
    tmp = "_tmp_" + name[:50]
    con.execute(f"DROP TABLE IF EXISTS {schema}.{bdw.qident(tmp)}")
    try:
        con.execute(f"""CREATE TABLE {schema}.{bdw.qident(tmp)} AS SELECT * FROM read_csv('{p.as_posix()}', header=true,
                        normalize_names=true, all_varchar=true, ignore_errors=true, sample_size=50000)""")
    except Exception:
        con.execute(f"""CREATE TABLE {schema}.{bdw.qident(tmp)} AS SELECT * FROM read_csv('{p.as_posix()}', header=true,
                        normalize_names=true, all_varchar=true, ignore_errors=true, encoding='latin-1', strict_mode=false)""")
    n = con.execute(f"SELECT count(*) FROM {schema}.{bdw.qident(tmp)}").fetchone()[0]
    if schema == "worldbank":
        bdw.finish_wb_table(con, tmp, name, bdw.rel(p), n)
    else:
        con.execute(f"DROP TABLE IF EXISTS {schema}.{bdw.qident(name)}")
        con.execute(f"ALTER TABLE {schema}.{bdw.qident(tmp)} RENAME TO {bdw.qident(name)}")
        bdw.register(con, schema, name, bdw.rel(p), "loaded_missing", n, "all text (raw)")
    bdw.log(con, schema, name, "OK", f"{n} rows", time.time() - t0)
    return n


def parse_line(line: str):
    toks = line.replace("\t", " ").split()
    label, vals, i = [], [], 0
    while i < len(toks) and (not NUM.match(toks[i]) or ORD.match(toks[i])):
        label.append(toks[i]); i += 1
    for t in toks[i:]:
        if NUM.match(t):
            s = t.strip("()%").replace(",", "").rstrip("PRpr")
            neg = t.startswith("(")
            try:
                v = float(s)
                vals.append(-v if neg else v)
            except ValueError:
                pass
    return " ".join(label), vals


def build_sbp_rows(con):
    t0 = time.time()
    rows = []
    for p in sorted((bdw.DATA / "external_downloads" / "sbp_text").glob("*.txt")):
        page, rno = 0, 0
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith("=== Page"):
                page, rno = int(re.findall(r"\d+", line)[0]), 0
                continue
            if line.startswith("---") or not line.strip():
                continue
            rno += 1
            label, vals = parse_line(line)
            rec = {"document": p.stem, "page": page, "row_no": rno, "label": label, "n_values": len(vals)}
            for k in range(24):
                rec[f"v{k+1}"] = vals[k] if k < len(vals) else None
            rec["raw_line"] = line.replace("\t", " | ").rstrip("?").strip()
            rows.append(rec)
    df = pd.DataFrame(rows)
    con.execute("DROP TABLE IF EXISTS sbp.rows_parsed")
    con.execute("CREATE TABLE sbp.rows_parsed AS SELECT * FROM df")
    bdw.register(con, "sbp", "rows_parsed", bdw.rel(bdw.DATA / "external_downloads" / "sbp_text"), "sbp_text", len(df),
                 "OCR text lines split into label + numeric values v1..v24 (heuristic); raw_line keeps the original")
    bdw.log(con, "sbp", "rows_parsed", "OK", f"{len(df)} lines, {int((df.n_values > 0).sum())} with numbers", time.time() - t0)
    print(f"sbp.rows_parsed: {len(df)} lines, {int((df.n_values > 0).sum())} with numbers", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sbp-only", action="store_true")
    ap.add_argument("--skip-big", action="store_true", help="skip files over 100 MB")
    a = ap.parse_args()
    con = bdw.connect()
    con.execute("CREATE SCHEMA IF NOT EXISTS misc")
    if not a.sbp_only:
        todo = missing_files(con)
        print(f"{len(todo)} unique missing files, {todo.size_bytes.sum()/1e6:.0f} MB", flush=True)
        ok = fail = 0
        # make load_excel use collision-safe names
        orig = bdw.table_name_for
        for r in todo.itertuples():
            p = ROOT / r.path
            schema = "worldbank" if "external_downloads/world" in r.path else "misc"
            if a.skip_big and r.size_bytes > 100e6:
                continue
            t0 = time.time()
            try:
                if r.extension == "csv":
                    name = unique_name(con, schema, orig(p) if schema == "worldbank" else bdw.snake(p.stem)[:55], r.sha256)
                    n = load_csv(con, p, name, r.sha256, schema)
                else:
                    bdw.table_name_for = lambda pp, sheet=None, _o=orig, _s=r.sha256[:6]: (_o(pp, sheet) if not bdw.is_loaded(con, "worldbank", _o(pp, sheet)) else _o(pp, sheet)[:54] + "_" + _s)
                    bdw.load_excel(con, p, False)
                    bdw.table_name_for = orig
                    n = "excel"
                ok += 1
                print(f"OK   {r.path[-70:]} ({n}) {time.time()-t0:.0f}s", flush=True)
            except Exception as exc:
                bdw.table_name_for = orig
                fail += 1
                bdw.log(con, schema, p.name, "FAILED", exc, time.time() - t0)
                print(f"FAIL {r.path[-70:]}: {str(exc)[:100]}", flush=True)
        print(f"files ok={ok} failed={fail}", flush=True)
    build_sbp_rows(con)
    con.close()


if __name__ == "__main__":
    main()

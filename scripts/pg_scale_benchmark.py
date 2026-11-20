"""Postgres + dbt scale benchmark in an isolated, temporary database (your main database is never touched).

For each size: create DB -> generate payments (scratch dir) -> COPY into raw.* -> `dbt build --select models/payments` -> drop DB.
Appends a row set to docs/PG_SCALE_BENCHMARK.md.   Run: PYTHONPATH=. python scripts/pg_scale_benchmark.py 1000000 2000000
Requires the embedded/local Postgres from .env to be running. One run per size, single machine, indicative only.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from sqlalchemy import create_engine, text

ROOT = Path(__file__).resolve().parents[1]


def admin_engine():
    from src.utils.db import get_engine
    return get_engine().execution_options(isolation_level="AUTOCOMMIT")


def run_one(n: int) -> dict:
    db = f"bench_{n}"
    scratch = Path(tempfile.mkdtemp(prefix=f"pgbench_{n}_"))
    out: dict = {"payments": n}
    with admin_engine().connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE)'))
        c.execute(text(f'CREATE DATABASE "{db}"'))
    env = {**os.environ, "POSTGRES_DB": db, "PYTHONPATH": str(ROOT)}
    try:
        code = f"""
import json, time
from pathlib import Path
from config.settings import get_settings
from src.payments.config import PaymentGenConfig
from src.payments.writer import generate_to_disk
from src.payments.load import load_payment_sources
cfg = PaymentGenConfig.from_env(); cfg.num_payments = {n}
src = Path(r'{scratch.as_posix()}')
t = time.perf_counter(); m = generate_to_disk(cfg, src / 'payments', src / 'clean', get_settings().data_source_dir); gen = time.perf_counter() - t
t = time.perf_counter(); rows = load_payment_sources(src / 'payments'); load = time.perf_counter() - t
print(json.dumps({{"generate_s": round(gen, 1), "copy_load_s": round(load, 1), "rows": rows}}))
"""
        p = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, text=True)
        if p.returncode:
            raise RuntimeError(p.stderr[-1500:])
        out.update(json.loads(p.stdout.strip().splitlines()[-1]))
        t = time.perf_counter()
        d = subprocess.run([sys.executable, "-m", "dbt.cli.main", "build", "--select", "models/payments", "--profiles-dir", "."],
                           cwd=ROOT / "dbt", env=env, capture_output=True, text=True)
        out["dbt_build_s"] = round(time.perf_counter() - t, 1)
        out["dbt_ok"] = d.returncode == 0
        out["dbt_tail"] = d.stdout.strip().splitlines()[-1][-80:] if d.stdout else ""
        e = create_engine(f"postgresql+psycopg2://{os.environ['POSTGRES_USER']}:{os.environ['POSTGRES_PASSWORD']}@{os.environ.get('POSTGRES_HOST','localhost')}:{os.environ['POSTGRES_PORT']}/{db}")
        with e.connect() as c:
            out["db_size_mb"] = round(c.execute(text("select pg_database_size(current_database())/1e6")).scalar())
            out["outcome_rows"] = c.execute(text("select count(*) from intermediate.int_payment_outcomes")).scalar()
        e.dispose()
    finally:
        with admin_engine().connect() as c:
            c.execute(text(f'DROP DATABASE IF EXISTS "{db}" WITH (FORCE)'))
        shutil.rmtree(scratch, ignore_errors=True)
    return out


def main():
    sizes = [int(a) for a in sys.argv[1:]] or [1_000_000]
    rows = []
    for n in sizes:
        r = run_one(n)
        print(json.dumps(r))
        rows.append(r)
    path = ROOT / "docs" / "PG_SCALE_BENCHMARK.md"
    lines = ["# Postgres + dbt scale benchmark (isolated temporary database, dropped afterwards)", "",
             "One run per size on the dev machine (embedded Postgres, default settings, no tuning), other work running concurrently at times. Indicative only.", "",
             "| payments requested | generate | COPY load (4 raw tables) | dbt build models/payments | dbt ok | DB size | payments in int_payment_outcomes |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['payments']:,} | {r['generate_s']} s | {r['copy_load_s']} s | {r['dbt_build_s']} s | {r['dbt_ok']} | {r['db_size_mb']} MB | {r['outcome_rows']:,} |")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()

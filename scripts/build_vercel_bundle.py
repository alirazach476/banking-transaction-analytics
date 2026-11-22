"""Assemble the deployable Vercel project in deploy/vercel/: the built React app (static), the analytics API as a Python
function over a bundled read-only DuckDB snapshot, and the small files the API reads at run time.

Steps (run from the repository root):
  1. cd web/react-app && npm run build                      # the UI
  2. PYTHONPATH=. python scripts/build_demo_db.py           # snapshot of the synthetic data (needs local PostgreSQL)
  3. python scripts/build_vercel_bundle.py                  # this script: assemble deploy/vercel/
  4. cd deploy/vercel && vercel --prod                      # deploy (project link is copied from web/.vercel if present)

deploy/vercel/ is generated and git-ignored (the data file is about 30 MB). All data is synthetic.
"""
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "deploy" / "vercel"


def copy(src: Path, dst: Path) -> None:
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def main() -> None:
    dist = ROOT / "web" / "react-app" / "dist"
    data = OUT / "data" / "demo.duckdb"
    if not dist.exists():
        raise SystemExit("web/react-app/dist is missing: run `npm run build` in web/react-app first")
    if not data.exists():
        raise SystemExit("deploy/vercel/data/demo.duckdb is missing: run `PYTHONPATH=. python scripts/build_demo_db.py` first")
    keep = OUT / "data"
    for child in OUT.iterdir():
        if child == keep or child.name == ".vercel":
            continue
        shutil.rmtree(child) if child.is_dir() else child.unlink()

    # function + config
    copy(ROOT / "deploy" / "api_index.py", OUT / "api" / "index.py")
    for name in ("requirements.txt", "vercel.json", ".python-version"):
        copy(ROOT / "deploy" / name, OUT / name)
    # API code (only the modules the function imports)
    copy(ROOT / "src" / "__init__.py", OUT / "src" / "__init__.py")
    for f in (ROOT / "src" / "api" / "dash").glob("*.py"):
        copy(f, OUT / "src" / "api" / "dash" / f.name)
    # files the API reads at run time
    for rel in ("config/pakistan_calibration.json", "docs/_parts/calibration_results.json", "docs/_parts/part_c2.json",
                "dbt/target/run_results.json", "dbt/target/manifest.json"):
        if (ROOT / rel).exists():
            copy(ROOT / rel, OUT / rel)
    for f in (ROOT / "airflow" / "dags").glob("*.py"):
        copy(f, OUT / "airflow" / "dags" / f.name)
    # static site: the React app at /app, the earlier portfolio pages alongside
    shutil.copytree(dist, OUT / "public" / "app")
    for page in ("dashboard.html", "payments_dashboard.html"):
        copy(ROOT / "web" / page, OUT / "public" / page)
    copy(ROOT / "web" / "index.html", OUT / "public" / "portfolio.html")
    link = ROOT / "web" / ".vercel" / "project.json"  # keep the existing Vercel project (and its domain)
    if link.exists():
        copy(link, OUT / ".vercel" / "project.json")
    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file() and ".vercel" not in p.parts) / 1e6
    print(f"{OUT}: {size:.0f} MB in {sum(1 for p in OUT.rglob('*') if p.is_file())} files")


if __name__ == "__main__":
    main()

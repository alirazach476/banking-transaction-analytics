"""Create/refresh the objects behind the analytics UI: ui.payments_usd, ui.core_txn_usd (USD-converted materialized views),
monitoring.anomaly_investigations, and ui.city_centroids (city centroids from the public GeoNames gazetteer, CC BY 4.0, via the
geonamescache package; used only to place branches on a map at CITY level; they are not branch addresses).
Run: python scripts/create_ui_objects.py   (needs the payment marts and the warehouse schema in Postgres; safe to re-run)"""
from __future__ import annotations

from pathlib import Path

from sqlalchemy import text

from src.utils.db import get_engine

ROOT = Path(__file__).resolve().parents[1]


def run(engine=None) -> dict:
    engine = engine or get_engine()
    lines = (ROOT / "sql" / "ui_views.sql").read_text(encoding="utf-8").splitlines()
    sql = chr(10).join(l for l in lines if not l.strip().startswith("--"))
    with engine.begin() as c:
        for stmt in [s.strip() for s in sql.split(";\n") if s.strip() and not s.strip().startswith("--")]:
            c.execute(text(stmt))
    out = {}
    try:
        import geonamescache
        gc = geonamescache.GeonamesCache()
        cities = gc.get_cities()
        with engine.connect() as c:
            wanted = {r[0] for r in c.execute(text("SELECT DISTINCT city FROM warehouse.dim_branch WHERE country = 'United States' AND city IS NOT NULL"))}
        alias = {"New York City": "New York"}  # GeoNames name -> branch city name
        best: dict[str, dict] = {}
        for cty in cities.values():
            nm = alias.get(cty["name"], cty["name"])
            if cty["countrycode"] == "US" and nm in wanted and (nm not in best or cty["population"] > best[nm]["population"]):
                best[nm] = cty
        with engine.begin() as c:
            c.execute(text("DELETE FROM ui.city_centroids"))
            for name, cty in best.items():
                c.execute(text("INSERT INTO ui.city_centroids VALUES (:c, 'United States', :la, :lo, :p, 'GeoNames (CC BY 4.0), largest US city of that name')"),
                          {"c": name, "la": cty["latitude"], "lo": cty["longitude"], "p": cty["population"]})
        out["city_centroids"] = len(best)
        out["unmatched_cities"] = sorted(wanted - set(best))
    except ImportError:
        out["city_centroids"] = "geonamescache not installed (map disabled)"
    with engine.connect() as c:
        out["payments_usd"] = tuple(c.execute(text("SELECT count(*), count(amount_usd) FROM ui.payments_usd")).one())
        out["core_txn_usd"] = tuple(c.execute(text("SELECT count(*), count(amount_usd) FROM ui.core_txn_usd")).one())
    return out


if __name__ == "__main__":
    print(run())

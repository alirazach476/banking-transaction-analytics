"""
Polite, resumable bulk downloader for three public data sources.

  ecb  - every dataset listed at https://data.ecb.europa.eu/data/datasets, as CSV via the official
         SDMX API (https://data-api.ecb.europa.eu/service/data/<DATASET>?format=csvdata)
  sbp  - every PDF linked from https://www.sbp.org.pk/economic-data
  wb   - Excel files (xls/xlsx) attached to datasets of the World Bank Data Catalog's featured
         collections, discovered through the official Data Catalog API (ddh-openapi.worldbank.org)

Safeguards: identifiable User-Agent, per-host throttle, retries, resume (existing files skipped),
.part files renamed only on success, per-file and total size caps, JSONL manifest with SHA-256.
Downloaded files are untrusted data: they are stored, hashed and never executed or opened here.

Usage:
  python scripts/download_public_data.py plan  ecb sbp wb        # list what would be fetched
  python scripts/download_public_data.py fetch ecb --max-file-mb 500 --max-total-gb 10
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import urllib.robotparser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "external_downloads"
UA = "NovaBankPortfolioBot/1.0 (educational data-engineering project)"
S = requests.Session()
S.headers["User-Agent"] = UA
_last: dict[str, float] = {}
INTERVAL = {"data.ecb.europa.eu": 1.0, "data-api.ecb.europa.eu": 1.5, "www.sbp.org.pk": 2.5,
            "ddh-openapi.worldbank.org": 1.0, "datacatalogfiles.worldbank.org": 1.0,
            "thedocs.worldbank.org": 1.0}


def throttle(url: str) -> None:
    host = urlparse(url).netloc
    wait = _last.get(host, 0) + INTERVAL.get(host, 1.0) - time.monotonic()
    if wait > 0:
        time.sleep(wait)
    _last[host] = time.monotonic()


def get(url: str, **kw) -> requests.Response:
    for attempt in range(4):
        throttle(url)
        try:
            r = S.get(url, timeout=60, **kw)
            if r.status_code in (429, 500, 502, 503, 504) and attempt < 3:
                time.sleep(float(r.headers.get("Retry-After", 2 ** (attempt + 1))))
                continue
            return r
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError("unreachable")


def robots_ok(url: str, cache: dict = {}) -> bool | None:
    """True/False from robots.txt; None if robots.txt could not be read (reported, not assumed)."""
    p = urlparse(url)
    base = f"{p.scheme}://{p.netloc}"
    if base not in cache:
        try:
            r = get(base + "/robots.txt")
            if r.status_code == 200:
                rp = urllib.robotparser.RobotFileParser()
                rp.parse(r.text.splitlines())
                cache[base] = rp
            elif r.status_code == 404:
                cache[base] = True
            else:
                cache[base] = None
        except requests.RequestException:
            cache[base] = None
    v = cache[base]
    return v if isinstance(v, (bool, type(None))) else v.can_fetch(UA, url)


def download(url: str, dest: Path, max_file_bytes: int) -> dict:
    """Stream to dest (resume = skip if present). Returns a manifest record."""
    rec = {"url": url, "file": str(dest.relative_to(OUT)), "status": "", "bytes": 0, "sha256": ""}
    if dest.exists() and dest.stat().st_size > 0:
        rec.update(status="SKIPPED_EXISTS", bytes=dest.stat().st_size)
        return rec
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    try:
        with get(url, stream=True) as r:
            if r.status_code != 200:
                rec["status"] = f"HTTP_{r.status_code}"
                return rec
            h, n = hashlib.sha256(), 0
            with open(part, "wb") as f:
                for chunk in r.iter_content(1 << 20):
                    n += len(chunk)
                    if n > max_file_bytes:
                        rec["status"] = "TOO_LARGE"
                        break
                    h.update(chunk)
                    f.write(chunk)
            if rec["status"] == "TOO_LARGE":
                part.unlink(missing_ok=True)
                rec["bytes"] = n
                return rec
        part.replace(dest)
        rec.update(status="OK", bytes=n, sha256=h.hexdigest())
    except Exception as exc:  # network failure: leave no partial file behind
        part.unlink(missing_ok=True)
        rec["status"] = f"ERROR: {type(exc).__name__}"
    return rec


# ------------------------------------------------------------------ discovery
def plan_ecb() -> list[tuple[str, Path]]:
    page = "https://data.ecb.europa.eu/data/datasets"
    html = get(page).text
    codes = sorted(set(re.findall(r'href="/data/datasets/([A-Za-z0-9_]+)"', html)))
    return [(f"https://data-api.ecb.europa.eu/service/data/{c}?format=csvdata", OUT / "ecb" / f"{c}.csv")
            for c in codes]


def plan_sbp() -> list[tuple[str, Path]]:
    page = "https://www.sbp.org.pk/economic-data"
    html = get(page).text
    seen, items = set(), []
    for href in re.findall(r'href="([^"]+)"', html):
        u = urljoin(page, href.strip())
        if u.lower().split("?")[0].endswith(".pdf") and u not in seen:
            seen.add(u)
            items.append((u, OUT / "sbp" / unquote(Path(urlparse(u).path).name)))
    return items


WB = "https://ddh-openapi.worldbank.org"
# Featured carousel on https://datacatalog.worldbank.org: WDR, Ukraine, SPI, WDI (mapped by name/collection;
# the carousel targets are rendered client-side and could not be read from static HTML).
def _colls(d: dict) -> set[str]:
    """collection_id is a LIST of collection codes/titles in the Data Catalog API."""
    v = (d.get("identification") or {}).get("collection_id") or []
    return {str(x).strip().lower() for x in (v if isinstance(v, list) else [v])}


WB_FEATURED = {
    "WDI": lambda d: (d.get("name") or "").strip().lower() == "world development indicators",
    "SPI": lambda d: "statistical performance indicators" in (d.get("name") or "").lower()
    and "arab world" not in (d.get("name") or "").lower(),
    "UKRAINE": lambda d: bool(_colls(d) & {"ukraine", "ukraine datasets"}),
    "WDR": lambda d: bool(_colls(d) & {"wdr", "wdr2022", "world development report", "world development report 2021",
                                       "world development report 2022"}),
    # second carousel page (screenshots supplied by the user)
    "COVID19": lambda d: bool(_colls(d) & {"covid_19", "coronavirus (covid-19) related datasets"}),
    "BOUNDARIES": lambda d: "official boundaries" in (d.get("name") or "").lower(),
    "LIBRARY": lambda d: bool(_colls(d) & {"library", "library databases", "library database"}),
    "WSF": lambda d: bool(_colls(d) & {"world_settlement", "world settlement footprint"}),
    "ESA": lambda d: bool(_colls(d) & {"wbg_esa"}),
}
EXCEL = {"xls", "xlsx", "excel", "ms excel", "microsoft excel"}


def wb_all_datasets() -> list[dict]:
    cache = OUT / "wb_catalog_cache.json"
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    out, skip = [], 0
    while True:
        r = get(WB + "/search", params={"qname": "dataset", "top": 100, "skip": skip})
        r.raise_for_status()
        j = r.json()
        out.extend(j["data"])
        skip += 100
        if skip >= j["count"] or not j["data"]:
            cache.write_text(json.dumps(out), encoding="utf-8")
            return out


def wb_resource_detail(rid: str) -> dict:
    """Per-resource metadata (cached). The bulk search listing often omits url/format that the
    website shows; the detail endpoint carries distribution.website_url."""
    cache = OUT / "wb_resource_details.json"
    store = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    if rid not in store:
        r = get(f"{WB}/resources/{rid}")
        store[rid] = r.json() if r.status_code == 200 else {}
        cache.write_text(json.dumps(store), encoding="utf-8")
    return store[rid]


def _is_excel_url(u: str) -> bool:
    return u.lower().split("?")[0].endswith((".xls", ".xlsx"))


def _failed_files() -> set[str]:
    """Destination paths whose latest manifest record is a failure (Excel unavailable -> CSV fallback)."""
    mf = OUT / "manifest_wb.jsonl"
    last: dict[str, str] = {}
    if mf.exists():
        for line in mf.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            last[r["file"]] = r["status"]
    return {f for f, st in last.items() if st not in ("OK", "SKIPPED_EXISTS")}


def _classify(res: dict) -> tuple[str, str | None]:
    """Return (kind, direct_url) with kind in {'excel','csv',''} using listing, then detail endpoint."""
    rid = res["resource_unique_id"]
    fmt = (res.get("format") or "").strip().lower()
    name = res.get("name") or ""
    url = res.get("url") or ""
    if fmt in EXCEL or _is_excel_url(url) or name.lower().endswith((".xls", ".xlsx")):
        return "excel", url or (wb_resource_detail(rid).get("distribution") or {}).get("website_url")
    if fmt == "csv" or url.lower().split("?")[0].endswith(".csv"):
        return "csv", url or (wb_resource_detail(rid).get("distribution") or {}).get("website_url")
    if not url and (fmt == "" or "excel" in name.lower() or "xls" in name.lower() or "csv" in name.lower()):
        w = (wb_resource_detail(rid).get("distribution") or {}).get("website_url") or ""
        if _is_excel_url(w):
            return "excel", w
        if w.lower().split("?")[0].endswith(".csv"):
            return "csv", w
    return "", None


def plan_wb() -> list[tuple[str, Path]]:
    """Per featured dataset: Excel resources; if the dataset has none (or all its Excel downloads
    failed), its CSV resources instead."""
    items, seen = [], set()
    failed = _failed_files()
    for d in wb_all_datasets():
        tag = next((t for t, f in WB_FEATURED.items() if f(d)), None)
        if not tag:
            continue
        excel, csv_ = [], []
        for res in d.get("resources") or []:
            if res["resource_unique_id"] in seen:
                continue
            kind, direct = _classify(res)
            if kind == "excel":
                excel.append((res, direct))
            elif kind == "csv" and direct:
                csv_.append((res, direct))

        def dest(res, kind, src):
            rid, name = res["resource_unique_id"], res.get("name") or ""
            safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:90] or rid
            ext = ".csv" if kind == "csv" else (".xlsx" if ".xlsx" in (src or "").lower() or
                                               (res.get("format") or "").lower() in ("excel", "ms excel") else ".xls")
            if not safe.lower().endswith(ext):
                safe += ext
            sub = "csv" if kind == "csv" else ""
            return OUT / "worldbank" / tag / sub / f'{d["dataset_unique_id"]}_{rid}_{safe}'

        excel_paths = [dest(r, "excel", u or "") for r, u in excel]
        excel_ok = [p for p in excel_paths if str(p.relative_to(OUT)) not in failed]
        for (res, direct), path in zip(excel, excel_paths):
            items.append((direct or f"{WB}/resources/{res['resource_unique_id']}/download", path))
            seen.add(res["resource_unique_id"])
        if not excel_ok:  # no Excel at all, or every Excel download failed -> CSV instead
            for res, direct in csv_:
                items.append((direct, dest(res, "csv", direct)))
                seen.add(res["resource_unique_id"])
    return items


# Datasets matched by the catalog search filter the user supplied (collection_code any of these 8);
# the API lists collection codes AND titles in collection_id, so both are matched (1,020 datasets).
WBCAT_NAMES = {"coronavirus (covid-19) related datasets", "covid_19", "data 360", "data360", "energy data info",
               "energy_data", "equitable growth, finance and institutions", "equitable_growth",
               "infrastructure finance datasets", "infrastructure_finance_datasets", "rdl", "risk data library",
               "ukraine", "ukraine datasets", "wb_energy", "world bank energy datasets"}


def plan_wbcat() -> list[tuple[str, Path]]:
    """Every Excel and CSV resource of every dataset in the filtered collections."""
    have = {p.name.split("_")[1] for p in (OUT / "worldbank").rglob("*") if p.is_file() and p.name.startswith("00")}
    items, seen_ds, seen = [], set(), set()
    for d in wb_all_datasets():
        if not (_colls(d) & WBCAT_NAMES) or d["dataset_unique_id"] in seen_ds:
            continue
        seen_ds.add(d["dataset_unique_id"])
        for res in d.get("resources") or []:
            rid = res["resource_unique_id"]
            if rid in seen or rid in have:
                continue
            kind, direct = _classify(res)
            if not kind or not direct:
                continue
            seen.add(rid)
            safe = re.sub(r"[^A-Za-z0-9._-]+", "_", res.get("name") or "")[:80] or rid
            ext = ".csv" if kind == "csv" else (".xlsx" if ".xlsx" in direct.lower() else ".xls")
            if not safe.lower().endswith(ext):
                safe += ext
            items.append((direct, OUT / "worldbank_collections" / d["dataset_unique_id"] / f"{rid}_{safe}"))
    return items


def plan_wbzip() -> list[tuple[str, Path]]:
    """Zip resources of featured/filtered datasets that have NO Excel or CSV resource at all."""
    items, seen_ds = [], set()
    for d in wb_all_datasets():
        in_scope = (_colls(d) & WBCAT_NAMES) or any(f(d) for f in WB_FEATURED.values())
        if not in_scope or d["dataset_unique_id"] in seen_ds:
            continue
        seen_ds.add(d["dataset_unique_id"])
        res_list = d.get("resources") or []
        if any(_classify(r)[0] for r in res_list):  # has Excel/CSV -> not a zip-only dataset
            continue
        for res in res_list:
            fmt = (res.get("format") or "").strip().lower()
            url = res.get("url") or ""
            if fmt != "zip" and not url.lower().split("?")[0].endswith(".zip"):
                continue
            rid = res["resource_unique_id"]
            if not url:
                url = (wb_resource_detail(rid).get("distribution") or {}).get("website_url") or ""
            if not url.lower().split("?")[0].endswith(".zip"):
                continue
            safe = re.sub(r"[^A-Za-z0-9._-]+", "_", res.get("name") or "")[:80] or rid
            if not safe.lower().endswith(".zip"):
                safe += ".zip"
            items.append((url, OUT / "worldbank_zips" / d["dataset_unique_id"] / f"{rid}_{safe}"))
    return items


def plan_wbrel() -> list[tuple[str, Path]]:
    """Excel, CSV and zip resources of the datasets judged relevant to NovaBank (finance, banking,
    payments, credit, inflation, debt, fiscal, trade). ids come from data/external_downloads/relevant_datasets.json."""
    ids = set(json.loads((OUT / "relevant_datasets.json").read_text(encoding="utf-8")))
    have = {p.name.split("_")[1] for p in OUT.rglob("*") if p.is_file() and "_" in p.name and p.name.startswith("00")}
    have |= {p.name.split("_")[0] for p in OUT.rglob("*") if p.is_file() and p.name.startswith("DR")}
    items, seen = [], set()
    for d in wb_all_datasets():
        if d["dataset_unique_id"] not in ids:
            continue
        for res in d.get("resources") or []:
            rid = res["resource_unique_id"]
            if rid in seen or rid in have:
                continue
            kind, direct = _classify(res)
            fmt = (res.get("format") or "").strip().lower()
            url = res.get("url") or ""
            if not kind and (fmt == "zip" or url.lower().split("?")[0].endswith(".zip")):
                kind, direct = "zip", url or (wb_resource_detail(rid).get("distribution") or {}).get("website_url")
            if not kind or not direct:
                continue
            seen.add(rid)
            ext = {"csv": ".csv", "zip": ".zip"}.get(kind) or (".xlsx" if ".xlsx" in direct.lower() else ".xls")
            safe = re.sub(r"[^A-Za-z0-9._-]+", "_", res.get("name") or "")[:80] or rid
            if not safe.lower().endswith(ext):
                safe += ext
            items.append((direct, OUT / "worldbank_relevant" / d["dataset_unique_id"] / f"{rid}_{safe}"))
    return items


PLANNERS = {"ecb": plan_ecb, "sbp": plan_sbp, "wb": plan_wb, "wbcat": plan_wbcat, "wbzip": plan_wbzip, "wbrel": plan_wbrel}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["plan", "fetch"])
    ap.add_argument("sources", nargs="+", choices=list(PLANNERS))
    ap.add_argument("--max-file-mb", type=int, default=500)
    ap.add_argument("--max-total-gb", type=float, default=10.0)
    ap.add_argument("--limit", type=int, default=0, help="only first N items per source (testing)")
    a = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    total = 0
    for src in a.sources:
        items = PLANNERS[src]()
        if a.limit:
            items = items[: a.limit]
        print(f"[{src}] {len(items)} files planned")
        if a.mode == "plan":
            for u, p in items[:5]:
                print("   ", u, "->", p.relative_to(OUT))
            (OUT / f"plan_{src}.json").write_text(json.dumps([[u, str(p.relative_to(OUT))] for u, p in items], indent=1))
            continue
        ro = robots_ok(items[0][0]) if items else True
        print(f"[{src}] robots.txt check: {ro!r} (None = robots.txt unreadable)")
        if ro is False:
            print(f"[{src}] disallowed by robots.txt - skipping")
            continue
        man = (OUT / f"manifest_{src}.jsonl").open("a", encoding="utf-8")
        for i, (u, p) in enumerate(items, 1):
            if total >= a.max_total_gb * 1e9:
                print("total size cap reached - stopping")
                break
            rec = download(u, p, a.max_file_mb * 1_000_000)
            total += rec["bytes"] if rec["status"] == "OK" else 0
            man.write(json.dumps(rec) + "\n")
            man.flush()
            print(f"  {i}/{len(items)} {rec['status']:<16} {rec['bytes']/1e6:9.2f} MB  {p.name}")
        man.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

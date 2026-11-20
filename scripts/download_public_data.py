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
            "ddh-openapi.worldbank.org": 1.0, "datacatalogfiles.worldbank.org": 1.0}


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


def plan_wb() -> list[tuple[str, Path]]:
    items, seen = [], set()
    for d in wb_all_datasets():
        tag = next((t for t, f in WB_FEATURED.items() if f(d)), None)
        if not tag:
            continue
        for res in d.get("resources") or []:
            fmt = (res.get("format") or "").strip().lower()
            name = (res.get("name") or "")
            if fmt in EXCEL or name.lower().endswith((".xls", ".xlsx")):
                rid = res["resource_unique_id"]
                if rid in seen:
                    continue
                seen.add(rid)
                safe = re.sub(r"[^A-Za-z0-9._-]+", "_", name)[:90] or rid
                if not safe.lower().endswith((".xls", ".xlsx")):
                    safe += ".xlsx" if "xlsx" in fmt or fmt in ("excel", "ms excel") else ".xls"
                items.append((f"{WB}/resources/{rid}/download",
                              OUT / "worldbank" / tag / f'{d["dataset_unique_id"]}_{rid}_{safe}'))
    return items


PLANNERS = {"ecb": plan_ecb, "sbp": plan_sbp, "wb": plan_wb}


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

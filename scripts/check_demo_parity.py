"""Compare every parameter-free and sample-parameter GET endpoint of the analytics API between two running servers:
the normal PostgreSQL-backed one and the DuckDB-backed demo (env DEMO_DUCKDB). Differences mean the demo would show different numbers.

Run: python scripts/check_demo_parity.py [--pg http://127.0.0.1:8792] [--demo http://127.0.0.1:8793]
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.error
import urllib.request

# fields that legitimately differ between runs (clock-dependent)
VOLATILE = {"as_of", "age_days", "generated_at", "now"}
SAMPLES = {"{customer_id}": "CUST-00004035", "{merchant_id}": "MERCH-00000505", "{branch_id}": "BR-00000011", "{anomaly_id}": "446", "{name}": "transactions"}
SKIP = ("/export", "/investigation")


def get(base: str, path: str):
    try:
        with urllib.request.urlopen(base + path, timeout=120) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8")[:200]


ORDER_ONLY: list = []


def _round(v):
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(f"{float(v):.5g}")
    if isinstance(v, dict):
        return {k: _round(x) for k, x in v.items() if k not in VOLATILE}
    if isinstance(v, list):
        return [_round(x) for x in v]
    if isinstance(v, str) and len(v) > 19 and v[10] == "T":
        return v[:19]
    return v


def same(a, b, path="$"):
    """Return list of differing paths; floats compared with a tolerance, volatile keys ignored."""
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k in VOLATILE:
                continue
            if k not in a or k not in b:
                out.append(f"{path}.{k}: missing on one side")
            else:
                out += same(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append(f"{path}: length {len(a)} vs {len(b)}")
        elementwise = []
        for i, (x, y) in enumerate(zip(a, b)):
            elementwise += same(x, y, f"{path}[{i}]")
        if elementwise and len(a) == len(b) and all(isinstance(e, dict) for e in a + b):
            # same rows in a different order (ties in ORDER BY)? Sort both by their text fields, then compare with tolerance
            key = lambda e: json.dumps({k: v for k, v in e.items() if isinstance(v, str) and k not in VOLATILE}, sort_keys=True)
            sa, sb = sorted(a, key=key), sorted(b, key=key)
            if not any(same(x, y) for x, y in zip(sa, sb)):
                ORDER_ONLY.append(path)
                elementwise = []
        out += elementwise
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool):
        if not math.isclose(a, b, rel_tol=1e-6, abs_tol=1e-6):
            out.append(f"{path}: {a} vs {b}")
    elif isinstance(a, str) and isinstance(b, str):
        # timestamps: Postgres serialises with an offset, the demo stores wall-clock time
        if a[:19] != b[:19]:
            out.append(f"{path}: {a[:60]!r} vs {b[:60]!r}")
    elif a != b:
        out.append(f"{path}: {a!r} vs {b!r}")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pg", default="http://127.0.0.1:8792")
    ap.add_argument("--demo", default="http://127.0.0.1:8793")
    a = ap.parse_args()
    _, spec = get(a.pg, "/openapi.json")
    bad = total = 0
    for path, ops in sorted(spec["paths"].items()):
        if "get" not in ops or not path.startswith("/v1/") or any(s in path for s in SKIP):
            continue
        url = path
        for k, v in SAMPLES.items():
            url = url.replace(k, v)
        if "{" in url:
            continue
        q = "?from=2025-01-01&to=2025-12-31" if "tables" not in url else "?from=2025-01-01&to=2025-12-31&size=25"
        s1, j1 = get(a.pg, url + q)
        s2, j2 = get(a.demo, url + q)
        total += 1
        diffs = [] if (s1 == s2 and s1 == 200) is False and s1 != s2 else same(j1, j2)
        if s1 != s2:
            diffs = [f"status {s1} vs {s2}: {str(j2)[:120]}"]
        if diffs:
            bad += 1
            print(f"DIFF {url}  ({len(diffs)}): {diffs[:3]}")
        else:
            print(f"ok   {url}")
    print(f"\n{total - bad}/{total} endpoints identical")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

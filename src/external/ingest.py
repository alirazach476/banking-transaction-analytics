"""Orchestrates external-source ingestion: fetch -> change detection -> parse -> idempotent upsert."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Callable

import yaml

from config.settings import PROJECT_ROOT
from src.external import parsers, store
from src.external.client import FetchResult, PoliteClient, RobotsDisallowed
from src.utils.db import get_engine, run_ddl
from src.utils.logging_utils import get_logger

logger = get_logger(__name__)
CONFIG_PATH = PROJECT_ROOT / "config" / "external_sources.yaml"


def load_config(path: Path = CONFIG_PATH) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _fetch_and_store(engine, client: PoliteClient, name: str, url: str, params: dict | None,
                     parse: Callable[[str], list[dict]], save: Callable[[list[dict], int], int],
                     force: bool = False) -> dict:
    """Fetch one URL. Skips parsing/loading when the content hash is unchanged (incremental)."""
    full_url = url
    try:
        res: FetchResult = client.get(url, params=params)
    except RobotsDisallowed:
        store.log_snapshot(engine, name, None, url, "BLOCKED_ROBOTS", parsers.PARSER_VERSION, None,
                           error="disallowed by robots.txt")
        logger.warning("%s blocked by robots.txt - skipped", url)
        return {"source": name, "status": "BLOCKED_ROBOTS", "parsed": 0, "new": 0}
    if params:  # keep the query string in the logged URL so each parameterised call has its own history
        from urllib.parse import urlencode
        full_url = f"{url}?{urlencode(params)}"
    if not res.ok:
        store.log_snapshot(engine, name, res, full_url, "FAILED", parsers.PARSER_VERSION, None, error=res.error)
        logger.error("%s failed: %s", full_url, res.error)
        return {"source": name, "status": "FAILED", "parsed": 0, "new": 0, "error": res.error}
    prev = store.last_hash(engine, full_url)
    changed = prev != res.content_hash
    if not changed and not force:
        store.log_snapshot(engine, name, res, full_url, "UNCHANGED", parsers.PARSER_VERSION, False)
        return {"source": name, "status": "UNCHANGED", "parsed": 0, "new": 0}
    try:
        rows = parse(res.text)
    except Exception as exc:  # parser breakage must not abort other sources
        store.log_snapshot(engine, name, res, full_url, "FAILED", parsers.PARSER_VERSION, changed,
                           error=f"parse error: {exc}")
        logger.exception("parse failed for %s", full_url)
        return {"source": name, "status": "FAILED", "parsed": 0, "new": 0, "error": str(exc)}
    snap = store.log_snapshot(engine, name, res, full_url, "SUCCESS", parsers.PARSER_VERSION, changed, len(rows), 0)
    new = save(rows, snap)
    from sqlalchemy import text
    with engine.begin() as c:
        c.execute(text("UPDATE external_raw.http_snapshots SET records_new = :n WHERE snapshot_id = :s"),
                  {"n": new, "s": snap})
    return {"source": name, "status": "SUCCESS", "parsed": len(rows), "new": new}


def run_all(engine=None, client: PoliteClient | None = None, config: dict | None = None,
            only: list[str] | None = None, force: bool = False) -> list[dict]:
    engine = engine or get_engine()
    run_ddl(engine)
    cfg = config or load_config()
    client = client or PoliteClient(min_interval=cfg.get("min_interval_seconds", 1.0),
                                    max_retries=cfg.get("max_retries", 3))
    out: list[dict] = []
    for s in cfg["sources"]:
        if only and s["name"] not in only:
            continue
        label, kind = s["source_label"], s["kind"]
        if kind == "ecb_fx":
            out.append(_fetch_and_store(engine, client, s["name"], s["url"], None, parsers.parse_ecb_fx,
                                        lambda rows, sid, l=label: store.upsert_fx(engine, rows, l, sid), force))
        elif kind == "worldbank":
            for ind in s["indicators"]:
                url = s["base_url"].format(countries=";".join(s["countries"]), indicator=ind["id"])
                params = {"format": "json", "per_page": 1000, "date": s["date_range"]}
                out.append(_fetch_and_store(
                    engine, client, f'{s["name"]}:{ind["id"]}', url, params,
                    lambda t, u=ind["unit"]: parsers.parse_worldbank(t, u)[0],
                    lambda rows, sid, l=label: store.upsert_indicators(engine, rows, l, sid), force))
        elif kind == "fred":
            for ser in s["series"]:
                out.append(_fetch_and_store(
                    engine, client, f'{s["name"]}:{ser["id"]}', s["url"], {"id": ser["id"], "cosd": s["since"]},
                    lambda t, sid_=ser["id"], u=ser["unit"], since=s["since"]: parsers.parse_fred_csv(t, sid_, u, since=since),
                    lambda rows, sid, l=label: store.upsert_indicators(engine, rows, l, sid), force))
        elif kind == "rss":
            out.append(_fetch_and_store(
                engine, client, s["name"], s["url"], None,
                lambda t, l=label, c=s.get("category", "news"): parsers.parse_rss(t, l, c),
                lambda rows, sid: store.upsert_announcements(engine, rows, sid), force))
        else:
            logger.warning("unknown source kind %s", kind)
    for r in out:
        logger.info("%-40s %-14s parsed=%-6s new=%s", r["source"], r["status"], r["parsed"], r["new"])
    return out


def main(argv: list[str] | None = None) -> list[dict]:
    ap = argparse.ArgumentParser(description="Ingest public external financial data")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--force", action="store_true", help="re-parse even if content hash is unchanged")
    a = ap.parse_args(argv)
    return run_all(only=a.only, force=a.force)


if __name__ == "__main__":
    main()

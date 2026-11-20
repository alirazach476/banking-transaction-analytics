"""Persistence for external data: snapshot log, change detection, idempotent upserts."""

from __future__ import annotations

import hashlib

from sqlalchemy import text

from src.external.client import FetchResult


def last_hash(engine, url: str) -> str | None:
    with engine.connect() as c:
        return c.execute(text("""
            SELECT content_hash FROM external_raw.http_snapshots
            WHERE source_url = :u AND extraction_status IN ('SUCCESS', 'UNCHANGED')
            ORDER BY extracted_at DESC, snapshot_id DESC LIMIT 1"""), {"u": url}).scalar()


def log_snapshot(engine, source: str, res: FetchResult | None, url: str, status: str, parser_version: str,
                 changed: bool | None, parsed: int = 0, new: int = 0, error: str | None = None) -> int:
    from urllib.parse import urlparse
    with engine.begin() as c:
        return c.execute(text("""
            INSERT INTO external_raw.http_snapshots
              (source_name, source_url, source_domain, http_status, extraction_status, parser_version,
               content_hash, changed, records_parsed, records_new, attempts, error_message)
            VALUES (:s, :u, :d, :h, :st, :pv, :ch, :cg, :p, :n, :a, :e) RETURNING snapshot_id"""),
            {"s": source, "u": url, "d": urlparse(url).netloc, "h": res.http_status if res else None,
             "st": status, "pv": parser_version, "ch": res.content_hash if res else None, "cg": changed,
             "p": parsed, "n": new, "a": res.attempts if res else 0, "e": error}).scalar()


def upsert_fx(engine, rows: list[dict], source: str, snapshot_id: int) -> int:
    for r in rows:
        r.update(source=source, snapshot_id=snapshot_id)
    return _bulk(engine, "external_raw.exchange_rates",
                 ["base_currency", "target_currency", "effective_date", "rate", "source", "snapshot_id"],
                 ["base_currency", "target_currency", "effective_date", "source"], ["rate", "snapshot_id"], rows)


def upsert_indicators(engine, rows: list[dict], source: str, snapshot_id: int) -> int:
    for r in rows:
        r.update(source=source, snapshot_id=snapshot_id)
    return _bulk(engine, "external_raw.economic_indicators",
                 ["indicator_id", "indicator_name", "country", "observation_date", "value", "unit",
                  "source", "publication_date", "snapshot_id"],
                 ["indicator_id", "country", "observation_date", "source"],
                 ["value", "indicator_name", "unit", "publication_date", "snapshot_id"], rows)


def upsert_announcements(engine, rows: list[dict], snapshot_id: int) -> int:
    for r in rows:
        r["url_hash"] = hashlib.sha256(r["url"].encode()).hexdigest()
        r["snapshot_id"] = snapshot_id
    return _bulk(engine, "external_raw.industry_announcements",
                 ["url_hash", "source", "category", "title", "url", "published_at", "summary", "snapshot_id"],
                 ["url_hash"], ["title", "summary", "snapshot_id"], rows)


def _bulk(engine, table: str, cols: list[str], key: list[str], update: list[str], rows: list[dict]) -> int:
    """Idempotent upsert; returns number of rows that were newly inserted (not updated)."""
    if not rows:
        return 0
    col_sql, val_sql = ", ".join(cols), ", ".join(f":{c}" for c in cols)
    set_sql = ", ".join(f"{c} = EXCLUDED.{c}" for c in update)
    with engine.begin() as c:
        n0 = c.execute(text(f"SELECT count(*) FROM {table}")).scalar()
        # de-duplicate within the batch on the business key (last wins)
        dedup = {tuple(r[k] for k in key): r for r in rows}
        batch = [{c_: r.get(c_) for c_ in cols} for r in dedup.values()]
        for i in range(0, len(batch), 5000):
            c.execute(text(f"INSERT INTO {table} ({col_sql}) VALUES ({val_sql}) "
                           f"ON CONFLICT ({', '.join(key)}) DO UPDATE SET {set_sql}"), batch[i:i + 5000])
        n1 = c.execute(text(f"SELECT count(*) FROM {table}")).scalar()
    return n1 - n0

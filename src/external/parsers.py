"""Pure parsers for external sources (no network). PARSER_VERSION is stored with every snapshot."""

from __future__ import annotations

import csv
import io
import json
import re
from datetime import datetime
from email.utils import parsedate_to_datetime

from bs4 import BeautifulSoup

PARSER_VERSION = "1.0.0"


def parse_ecb_fx(xml: str) -> list[dict]:
    """ECB euro foreign-exchange reference rates (daily / 90-day XML). base = EUR."""
    soup = BeautifulSoup(xml, "xml")
    rows = []
    for day in soup.find_all("Cube", attrs={"time": True}):
        for c in day.find_all("Cube", attrs={"currency": True}):
            try:
                rate = float(c["rate"])
            except (KeyError, ValueError):
                continue
            if rate <= 0:
                continue
            rows.append({"base_currency": "EUR", "target_currency": c["currency"].upper(),
                         "rate": rate, "effective_date": day["time"]})
    return rows


def parse_worldbank(payload: str, unit_hint: str = "") -> tuple[list[dict], dict]:
    """World Bank API v2 JSON -> (observations, paging meta). Null values are skipped."""
    data = json.loads(payload)
    if not isinstance(data, list) or len(data) < 2 or data[1] is None:
        return [], (data[0] if data and isinstance(data[0], dict) else {})
    meta, items = data[0], data[1]
    rows = []
    for it in items:
        if it.get("value") is None:
            continue
        rows.append({
            "indicator_id": it["indicator"]["id"], "indicator_name": it["indicator"]["value"],
            "country": it.get("countryiso3code") or it["country"]["id"],
            "observation_date": f'{it["date"]}-01-01' if re.fullmatch(r"\d{4}", str(it["date"])) else str(it["date"]),
            "value": float(it["value"]), "unit": it.get("unit") or unit_hint,
            "publication_date": meta.get("lastupdated"),
        })
    return rows, meta


def parse_fred_csv(text: str, series_id: str, unit: str = "", country: str = "USA",
                   since: str | None = None) -> list[dict]:
    """FRED graph CSV (observation_date,SERIES). '.'/empty values are skipped."""
    rows = []
    for rec in csv.DictReader(io.StringIO(text)):
        d = rec.get("observation_date") or rec.get("DATE")
        v = rec.get(series_id)
        if not d or v in (None, "", "."):
            continue
        if since and d < since:
            continue
        try:
            rows.append({"indicator_id": series_id, "indicator_name": series_id, "country": country,
                         "observation_date": d, "value": float(v), "unit": unit, "publication_date": None})
        except ValueError:
            continue
    return rows


def parse_rss(xml: str, source: str, category: str = "central_bank_news") -> list[dict]:
    """Generic RSS 2.0 -> announcements (official feeds only)."""
    soup = BeautifulSoup(xml, "xml")
    rows = []
    for it in soup.find_all("item"):
        title = (it.find("title").get_text(strip=True) if it.find("title") else "")
        link = (it.find("link").get_text(strip=True) if it.find("link") else "")
        if not title or not link:
            continue
        pub = None
        if it.find("pubDate"):
            try:
                pub = parsedate_to_datetime(it.find("pubDate").get_text(strip=True)).isoformat()
            except (TypeError, ValueError):
                pub = None
        rows.append({"source": source, "category": category, "title": title, "url": link,
                     "published_at": pub,
                     "summary": (BeautifulSoup(it.find("description").get_text(), "lxml")
                                 .get_text(" ", strip=True)[:500] if it.find("description") else "")})
    return rows


def parse_announcement_html(html: str, base_url: str, source: str, item_selector: str,
                            title_selector: str = "a", date_selector: str | None = None,
                            category: str = "payment_industry") -> list[dict]:
    """Config-driven HTML list scraper (BeautifulSoup). Used only for pages whose robots.txt/terms allow it."""
    from urllib.parse import urljoin
    soup = BeautifulSoup(html, "lxml")
    rows = []
    for el in soup.select(item_selector):
        a = el.select_one(title_selector)
        if not a or not a.get("href"):
            continue
        d = el.select_one(date_selector) if date_selector else None
        published = None
        if d:
            txt = d.get("datetime") or d.get_text(strip=True)
            for fmt in ("%Y-%m-%d", "%B %d, %Y", "%d %B %Y", "%b %d, %Y"):
                try:
                    published = datetime.strptime(txt[:len(txt)], fmt).date().isoformat()
                    break
                except ValueError:
                    continue
            if published is None and re.match(r"\d{4}-\d{2}-\d{2}", txt or ""):
                published = txt[:10]
        rows.append({"source": source, "category": category, "title": a.get_text(" ", strip=True),
                     "url": urljoin(base_url, a["href"]), "published_at": published, "summary": ""})
    return rows

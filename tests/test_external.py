"""External-data tests: parsers, polite client (fake session), idempotent/incremental ingestion."""

from __future__ import annotations

from pathlib import Path

import pytest
import requests
from sqlalchemy import text

from src.external import parsers
from src.external.client import PoliteClient, RobotsDisallowed
from src.external.ingest import run_all

FX = Path(__file__).parent / "fixtures"


def read(name: str) -> str:
    return (FX / name).read_text(encoding="utf-8")


# ----------------------------- parsers -----------------------------
def test_ecb_parser_skips_bad_rates():
    rows = parsers.parse_ecb_fx(read("ecb_fx.xml"))
    assert {(r["target_currency"], r["effective_date"]) for r in rows} == {
        ("USD", "2024-01-03"), ("GBP", "2024-01-03"), ("USD", "2024-01-02")}
    assert all(r["base_currency"] == "EUR" and r["rate"] > 0 for r in rows)


def test_worldbank_parser_skips_nulls_and_maps_dates():
    rows, meta = parsers.parse_worldbank(read("worldbank.json"), "% annual")
    assert len(rows) == 2 and meta["lastupdated"] == "2026-11-11"
    assert rows[0]["country"] == "PAK" and rows[0]["observation_date"] == "2025-01-01"
    assert rows[0]["unit"] == "% annual"


def test_worldbank_parser_error_payload_and_empty():
    assert parsers.parse_worldbank('[{"message":[{"id":"120"}]}]')[0] == []
    assert parsers.parse_worldbank('[{"page":1},null]')[0] == []


def test_fred_parser_handles_missing_and_since():
    rows = parsers.parse_fred_csv(read("fred.csv"), "DFF", "%", since="2018-01-01")
    assert [r["observation_date"] for r in rows] == ["2024-01-01", "2024-01-03"]


def test_rss_parser():
    rows = parsers.parse_rss(read("press.xml"), "ECB_PRESS")
    assert len(rows) == 2 and rows[0]["published_at"].startswith("2024-03-05")
    assert rows[1]["published_at"] is None and "<" not in rows[0]["summary"]


def test_html_parser_config_driven():
    rows = parsers.parse_announcement_html(read("news.html"), "https://site.org/news", "S", "li.n", "a", "time")
    assert len(rows) == 2
    assert rows[0]["url"] == "https://site.org/p/1" and rows[0]["published_at"] == "2024-02-01"
    assert rows[1]["published_at"] == "2024-03-03"


# ----------------------------- client -----------------------------
class _Resp:
    def __init__(self, status=200, text_="", headers=None):
        self.status_code, self.text, self.headers = status, text_, headers or {}


class FakeSession:
    def __init__(self, routes):
        self.routes, self.calls, self.headers = routes, [], {}

    def get(self, url, params=None, timeout=None):
        self.calls.append(url)
        r = self.routes.get(url)
        if callable(r):
            r = r()
        if isinstance(r, Exception):
            raise r
        return r or _Resp(404)


def _client(sess, **kw):
    return PoliteClient(min_interval=0, session=sess, sleep=kw.pop("sleep", lambda s: None), **kw)


def test_client_retries_then_succeeds_and_hashes():
    seq = iter([_Resp(503), _Resp(429, headers={"Retry-After": "2"}), _Resp(200, "hello")])
    sess = FakeSession({"https://a.org/robots.txt": _Resp(404), "https://a.org/x": lambda: next(seq)})
    sleeps: list[float] = []
    r = _client(sess, sleep=sleeps.append).get("https://a.org/x")
    assert r.ok and r.attempts == 3 and r.text == "hello" and 2.0 in sleeps
    assert len(r.content_hash) == 64


def test_client_gives_up_after_max_retries():
    sess = FakeSession({"https://a.org/robots.txt": _Resp(404), "https://a.org/x": _Resp(500)})
    r = _client(sess, max_retries=2).get("https://a.org/x")
    assert not r.ok and r.attempts == 3 and r.error == "HTTP 500"


def test_client_network_error_is_reported():
    sess = FakeSession({"https://a.org/robots.txt": _Resp(404),
                        "https://a.org/x": requests.ConnectionError("boom")})
    r = _client(sess, max_retries=1).get("https://a.org/x")
    assert not r.ok and r.http_status is None and "ConnectionError" in r.error


def test_client_respects_robots_and_never_fetches_disallowed():
    sess = FakeSession({"https://a.org/robots.txt": _Resp(200, "User-agent: *\nDisallow: /private\n"),
                        "https://a.org/private/x": _Resp(200, "secret")})
    with pytest.raises(RobotsDisallowed):
        _client(sess).get("https://a.org/private/x")
    assert "https://a.org/private/x" not in sess.calls


def test_client_throttles_per_domain():
    sess = FakeSession({"https://a.org/robots.txt": _Resp(404), "https://a.org/1": _Resp(200, "a"),
                        "https://a.org/2": _Resp(200, "b")})
    sleeps: list[float] = []
    c = PoliteClient(min_interval=5, session=sess, sleep=sleeps.append)
    c.get("https://a.org/1")
    c.get("https://a.org/2")
    assert any(s > 0 for s in sleeps)


# ------------------------- ingestion (DB-backed) -------------------------
CFG = {"min_interval_seconds": 0, "sources": [
    {"name": "ecb_fx_90d", "kind": "ecb_fx", "url": "https://e.org/fx.xml", "source_label": "ECB"},
    {"name": "wb", "kind": "worldbank", "base_url": "https://w.org/{countries}/{indicator}",
     "countries": ["PK", "US"], "date_range": "2024:2025",
     "indicators": [{"id": "FP.CPI.TOTL.ZG", "unit": "%"}], "source_label": "WORLD_BANK"},
    {"name": "press", "kind": "rss", "url": "https://e.org/press.xml", "source_label": "ECB_PRESS"},
]}
WB_URL = "https://w.org/PK;US/FP.CPI.TOTL.ZG"


def _session(fx=None):
    return FakeSession({
        "https://e.org/robots.txt": _Resp(404), "https://w.org/robots.txt": _Resp(404),
        "https://e.org/fx.xml": _Resp(200, fx or read("ecb_fx.xml")),
        WB_URL: _Resp(200, read("worldbank.json")),
        "https://e.org/press.xml": _Resp(200, read("press.xml")),
    })


@pytest.fixture
def clean_db(test_engine):
    with test_engine.begin() as c:
        c.execute(text("TRUNCATE external_raw.exchange_rates, external_raw.economic_indicators, "
                       "external_raw.industry_announcements, external_raw.http_snapshots CASCADE"))
    return test_engine


def _count(e, t):
    with e.connect() as c:
        return c.execute(text(f"SELECT count(*) FROM {t}")).scalar()


def test_ingestion_loads_and_is_incremental_and_idempotent(clean_db):
    r1 = run_all(clean_db, _client(_session()), CFG)
    assert {x["status"] for x in r1} == {"SUCCESS"}
    assert _count(clean_db, "external_raw.exchange_rates") == 3
    assert _count(clean_db, "external_raw.economic_indicators") == 2
    assert _count(clean_db, "external_raw.industry_announcements") == 2
    r2 = run_all(clean_db, _client(_session()), CFG)  # identical content -> nothing re-parsed
    assert {x["status"] for x in r2} == {"UNCHANGED"}
    assert _count(clean_db, "external_raw.exchange_rates") == 3
    r3 = run_all(clean_db, _client(_session()), CFG, force=True)  # forced re-parse adds 0 rows
    assert all(x["new"] == 0 for x in r3) and _count(clean_db, "external_raw.exchange_rates") == 3
    assert _count(clean_db, "external_raw.http_snapshots") == 9  # full snapshot history retained


def test_changed_content_detected_and_new_rows_loaded(clean_db):
    run_all(clean_db, _client(_session()), CFG, only=["ecb_fx_90d"])
    changed = read("ecb_fx.xml").replace(
        "</Cube></Cube></gesmes", '<Cube time="2024-01-04"><Cube currency="USD" rate="1.09"/></Cube></Cube></gesmes')
    r = run_all(clean_db, _client(_session(changed)), CFG, only=["ecb_fx_90d"])
    assert r[0]["status"] == "SUCCESS" and r[0]["new"] == 1
    with clean_db.connect() as c:
        assert c.execute(text("SELECT count(*) FROM external_raw.http_snapshots WHERE changed")).scalar() == 2


def test_failed_source_logged_and_does_not_stop_others(clean_db):
    s = _session()
    s.routes["https://e.org/fx.xml"] = _Resp(500)
    r = {x["source"]: x["status"] for x in run_all(clean_db, _client(s, max_retries=0), CFG)}
    assert r["ecb_fx_90d"] == "FAILED" and r["press"] == "SUCCESS"
    assert _count(clean_db, "external_raw.exchange_rates") == 0


def test_robots_blocked_source_is_logged(clean_db):
    s = _session()
    s.routes["https://e.org/robots.txt"] = _Resp(200, "User-agent: *\nDisallow: /fx.xml\n")
    r = {x["source"]: x["status"] for x in run_all(clean_db, _client(s), CFG)}
    assert r["ecb_fx_90d"] == "BLOCKED_ROBOTS" and r["press"] == "SUCCESS"


def test_malformed_payload_marks_failed(clean_db):
    s = _session()
    s.routes[WB_URL] = _Resp(200, "<html>not json</html>")
    r = {x["source"]: x["status"] for x in run_all(clean_db, _client(s), CFG)}
    assert r["wb:FP.CPI.TOTL.ZG"] == "FAILED"

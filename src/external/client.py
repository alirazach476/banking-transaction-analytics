"""Polite HTTP client: robots.txt, per-domain throttling, retry with backoff, content hashing."""

from __future__ import annotations

import hashlib
import time
import urllib.robotparser
from dataclasses import dataclass
from urllib.parse import urlparse

import requests

from src.utils.logging_utils import get_logger

logger = get_logger(__name__)

USER_AGENT = "NovaBankPortfolioBot/1.0 (educational data-engineering project)"
RETRY_STATUS = {429, 500, 502, 503, 504}


class RobotsDisallowed(Exception):
    """Raised when robots.txt forbids fetching the URL (we never bypass it)."""


@dataclass
class FetchResult:
    url: str
    domain: str
    http_status: int | None
    text: str
    content_hash: str
    fetched_at: float
    attempts: int
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.http_status == 200 and self.error is None


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class PoliteClient:
    def __init__(self, min_interval: float = 1.0, max_retries: int = 3, backoff: float = 1.5,
                 timeout: float = 30.0, respect_robots: bool = True, session=None, sleep=time.sleep):
        self.min_interval, self.max_retries, self.backoff = min_interval, max_retries, backoff
        self.timeout, self.respect_robots = timeout, respect_robots
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._sleep = sleep
        self._last: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}

    def _allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        p = urlparse(url)
        base = f"{p.scheme}://{p.netloc}"
        if base not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                r = self.session.get(f"{base}/robots.txt", timeout=self.timeout)
                if r.status_code == 200:
                    rp.parse(r.text.splitlines())
                    self._robots[base] = rp
                else:  # no robots.txt (or error) -> nothing is disallowed
                    self._robots[base] = None
            except requests.RequestException:
                self._robots[base] = None
        rp = self._robots[base]
        return True if rp is None else rp.can_fetch(USER_AGENT, url)

    def _throttle(self, domain: str) -> None:
        wait = self._last.get(domain, 0) + self.min_interval - time.monotonic()
        if wait > 0:
            self._sleep(wait)
        self._last[domain] = time.monotonic()

    def get(self, url: str, params: dict | None = None) -> FetchResult:
        domain = urlparse(url).netloc
        if not self._allowed(url):
            raise RobotsDisallowed(url)
        attempts, status, text, err = 0, None, "", None
        while attempts <= self.max_retries:
            attempts += 1
            self._throttle(domain)
            try:
                r = self.session.get(url, params=params, timeout=self.timeout)
                status, text, err = r.status_code, r.text, None
                if status in RETRY_STATUS and attempts <= self.max_retries:
                    ra = r.headers.get("Retry-After")
                    delay = float(ra) if ra and ra.isdigit() else self.backoff ** attempts
                    logger.warning("%s -> HTTP %s, retry %d in %.1fs", url, status, attempts, delay)
                    self._sleep(delay)
                    continue
                break
            except requests.RequestException as exc:
                err = f"{type(exc).__name__}: {exc}"
                if attempts <= self.max_retries:
                    self._sleep(self.backoff ** attempts)
                    continue
                break
        return FetchResult(url=url, domain=domain, http_status=status, text=text,
                           content_hash=content_hash(text), fetched_at=time.time(), attempts=attempts,
                           error=err if status is None else (None if status == 200 else f"HTTP {status}"))

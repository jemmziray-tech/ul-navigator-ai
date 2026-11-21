"""Polite fetcher + same-site link discovery.

* robots.txt obeyed per host (including Crawl-delay); unreachable robots (5xx/network) =>
  the host is treated as disallowed, which is the conservative choice.
* Per-host rate limiting, retries with exponential backoff (429/5xx/timeouts), Retry-After.
* Conditional GET (ETag / Last-Modified) + on-disk raw cache for incremental runs.
* Optional Playwright rendering for JavaScript-heavy pages.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse, parse_qs, urlencode
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup

log = logging.getLogger("ul_ingest.crawler")


@dataclass
class FetchResult:
    url: str
    final_url: str = ""
    status: int = 0
    content: bytes = b""
    content_type: str = ""
    etag: str | None = None
    last_modified: str | None = None
    not_modified: bool = False
    from_cache: bool = False
    error: str | None = None
    raw_path: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and (200 <= self.status < 300 or self.not_modified
                                       or self.from_cache)

    @property
    def kind(self) -> str:
        ct = self.content_type.lower()
        if "pdf" in ct or self.content[:5] == b"%PDF-":
            return "pdf"
        if "html" in ct or "xml" in ct:
            return "html"
        if "csv" in ct:
            return "csv"
        if "rtf" in ct:
            return "rtf"
        return "txt" if ct.startswith("text/") else "other"


class RobotsCache:
    def __init__(self, client: httpx.Client, user_agent: str):
        self.client = client
        self.ua = user_agent
        self._parsers: dict[str, RobotFileParser | None] = {}

    def _get(self, url: str) -> RobotFileParser | None:
        p = urlparse(url)
        host = f"{p.scheme}://{p.netloc}"
        if host not in self._parsers:
            rp = RobotFileParser()
            try:
                r = self.client.get(f"{host}/robots.txt", timeout=15)
                if r.status_code >= 500:
                    rp = None  # conservative: treat as disallow-all
                elif r.status_code >= 400:
                    rp.parse([])  # no robots file => allowed
                else:
                    rp.parse(r.text.splitlines())
            except httpx.HTTPError as exc:
                log.warning("robots.txt unreachable; host disallowed",
                            extra={"extra_fields": {"host": host, "error": str(exc)}})
                rp = None
            self._parsers[host] = rp
        return self._parsers[host]

    def allowed(self, url: str) -> bool:
        rp = self._get(url)
        return False if rp is None else rp.can_fetch(self.ua, url)

    def crawl_delay(self, url: str) -> float | None:
        rp = self._get(url)
        if rp is None:
            return None
        d = rp.crawl_delay(self.ua)
        return float(d) if d else None


class PoliteFetcher:
    def __init__(self, user_agent: str, cache_dir: Path, delay_s: float = 1.5,
                 timeout_s: float = 30.0, max_retries: int = 3, max_bytes: int = 60_000_000,
                 offline: bool = False, transport: httpx.BaseTransport | None = None,
                 cache_ttl_s: float = 0.0, max_delay_s: float = 30.0):
        self.ua = user_agent
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.delay_s = delay_s
        self.max_retries = max_retries
        self.max_bytes = max_bytes
        self.offline = offline
        self.cache_ttl_s = cache_ttl_s
        self.max_delay_s = max_delay_s
        self._host_delay: dict[str, float] = {}  # adaptive per-host politeness delay
        self.client = httpx.Client(
            headers={"User-Agent": user_agent, "Accept-Language": "en-IE,en;q=0.9"},
            timeout=timeout_s, follow_redirects=True, transport=transport)
        self.robots = RobotsCache(self.client, user_agent)
        self._last_hit: dict[str, float] = {}

    # ------------------------------------------------------------- cache
    def _cache_paths(self, url: str) -> tuple[Path, Path]:
        key = hashlib.sha1(url.encode()).hexdigest()
        return self.cache_dir / f"{key}.bin", self.cache_dir / f"{key}.json"

    def _load_cache(self, url: str) -> FetchResult | None:
        body, meta = self._cache_paths(url)
        if not (body.exists() and meta.exists()):
            return None
        m = json.loads(meta.read_text())
        self._cache_age = time.time() - m.get("fetched_at", 0)
        return FetchResult(url=url, final_url=m.get("final_url", url), status=m.get("status", 200),
                           content=body.read_bytes(), content_type=m.get("content_type", ""),
                           etag=m.get("etag"), last_modified=m.get("last_modified"),
                           from_cache=True, raw_path=str(body))

    def _save_cache(self, r: FetchResult) -> None:
        body, meta = self._cache_paths(r.url)
        body.write_bytes(r.content)
        meta.write_text(json.dumps({"final_url": r.final_url, "status": r.status,
                                    "content_type": r.content_type, "etag": r.etag,
                                    "last_modified": r.last_modified,
                                    "fetched_at": time.time()}))
        r.raw_path = str(body)

    # ------------------------------------------------------------- fetch
    def _throttle(self, url: str) -> None:
        host = urlparse(url).netloc
        delay = max(self.delay_s, self._host_delay.get(host, 0), self.robots.crawl_delay(url) or 0)
        wait = self._last_hit.get(host, 0) + delay - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        self._last_hit[host] = time.monotonic()

    def fetch(self, url: str, conditional: bool = True) -> FetchResult:
        self._cache_age = float("inf")
        cached = self._load_cache(url)
        if self.offline:
            return cached or FetchResult(url=url, error="offline: not in cache")
        if cached and self._cache_age < self.cache_ttl_s:
            return cached  # fetched recently: don't hit the server again
        if not self.robots.allowed(url):
            return FetchResult(url=url, error="disallowed by robots.txt")
        headers = {}
        if conditional and cached:
            if cached.etag:
                headers["If-None-Match"] = cached.etag
            if cached.last_modified:
                headers["If-Modified-Since"] = cached.last_modified
        last_err = "unknown error"
        for attempt in range(self.max_retries):
            self._throttle(url)
            try:
                with self.client.stream("GET", url, headers=headers) as resp:
                    if resp.status_code == 304 and cached:
                        cached.not_modified = True
                        return cached
                    if resp.status_code in (429, 500, 502, 503, 504):
                        retry_after = resp.headers.get("Retry-After", "")
                        wait = float(retry_after) if retry_after.isdigit() else 15 * (attempt + 1)
                        last_err = f"HTTP {resp.status_code}"
                        if resp.status_code == 429:  # server asked us to slow down: stay slower
                            host = urlparse(url).netloc
                            cur = self._host_delay.get(host, self.delay_s)
                            self._host_delay[host] = min(self.max_delay_s, max(cur * 2, 5.0))
                            log.warning("rate limited; slowing down", extra={"extra_fields": {
                                "host": host, "delay_s": self._host_delay[host], "wait_s": wait}})
                        time.sleep(min(max(wait, 5), 180))
                        continue
                    if resp.status_code >= 400:
                        return FetchResult(url=url, status=resp.status_code,
                                           error=f"HTTP {resp.status_code}")
                    buf = bytearray()
                    for part in resp.iter_bytes():
                        buf.extend(part)
                        if len(buf) > self.max_bytes:
                            return FetchResult(url=url, status=resp.status_code,
                                               error=f"exceeds size limit ({self.max_bytes} bytes)")
                    final_url = str(resp.url)
                    if not self.robots.allowed(final_url):
                        return FetchResult(url=url, error="redirect target disallowed by robots.txt")
                    r = FetchResult(url=url, final_url=final_url, status=resp.status_code,
                                    content=bytes(buf),
                                    content_type=resp.headers.get("content-type", ""),
                                    etag=resp.headers.get("etag"),
                                    last_modified=resp.headers.get("last-modified"))
                    self._save_cache(r)
                    return r
            except httpx.HTTPError as exc:
                last_err = f"{type(exc).__name__}: {exc}"
                time.sleep(2 ** (attempt + 1))
        return FetchResult(url=url, error=f"failed after {self.max_retries} attempts: {last_err}")

    def render_with_playwright(self, url: str) -> str | None:
        """Render JS-heavy pages. Requires `pip install playwright && playwright install chromium`."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return None
        if not self.robots.allowed(url):
            return None
        self._throttle(url)
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(user_agent=self.ua)
            page.goto(url, wait_until="networkidle", timeout=45000)
            html = page.content()
            browser.close()
        return html

    def close(self) -> None:
        self.client.close()


@dataclass
class CrawlScope:
    allowed_hosts: list[str]
    allowed_prefixes: list[str]
    exclude: list[re.Pattern] = field(default_factory=list)

    @classmethod
    def from_config(cls, cfg: dict) -> "CrawlScope":
        return cls(cfg.get("allowed_hosts", []), cfg.get("allowed_path_prefixes", []),
                   [re.compile(p, re.IGNORECASE) for p in cfg.get("exclude_patterns", [])])

    def normalize(self, base: str, href: str) -> str | None:
        if not href or href.startswith(("#", "javascript:")):
            return None
        url, _ = urldefrag(urljoin(base, href.strip()))
        p = urlparse(url)
        if p.scheme not in ("http", "https"):
            return None
        if p.hostname in {"www.bookofmodules.ul.ie", "bookofmodules.ul.ie"} and p.path.lower() == "/default.aspx":
            value = parse_qs(p.query).get("ModuleCodeParameter", [""])[0].upper()
            if re.fullmatch(r"\|[A-Z]{2,3}\d{4}\|", value):
                return p._replace(query=urlencode({"ModuleCodeParameter": value}), fragment="").geturl()
        if p.query and not p.path.endswith("/download"):
            url = url.split("?", 1)[0]
        return url.rstrip("/") if p.path not in ("", "/") else url

    def allows(self, url: str) -> bool:
        p = urlparse(url)
        if p.netloc not in self.allowed_hosts:
            return False
        if any(rx.search(url) for rx in self.exclude):
            return False
        return any(p.path.startswith(pref) for pref in self.allowed_prefixes)


def extract_links(html: bytes | str, base_url: str, scope: CrawlScope) -> list[str]:
    soup = BeautifulSoup(html, "lxml")
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        url = scope.normalize(base_url, a["href"])
        if url and url not in seen and scope.allows(url):
            seen.add(url)
            out.append(url)
    return out

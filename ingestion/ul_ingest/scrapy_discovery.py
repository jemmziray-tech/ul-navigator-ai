"""Optional large-scale URL discovery with Scrapy.

The built-in crawler is enough for a few hundred pages. For thousands of pages, Scrapy's
scheduler, AutoThrottle and robots.txt middleware are a better fit. This spider only
*discovers* permitted URLs and writes them to a file; ingestion then goes through the same
extraction / dedupe / indexing pipeline:

    pip install scrapy
    python -m ul_ingest.scrapy_discovery --out data/discovered_urls.txt --max-pages 2000
    python -m ul_ingest crawl --urls-file data/discovered_urls.txt --max-pages 2000
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .crawler import CrawlScope
from .pipeline import load_sources


def run(out: Path, max_pages: int, user_agent: str) -> None:
    import scrapy
    from scrapy.crawler import CrawlerProcess

    cfg = load_sources()
    scope = CrawlScope.from_config(cfg)
    found: set[str] = set()

    class ULDiscoverySpider(scrapy.Spider):
        name = "ul_discovery"
        start_urls = [s["url"] for s in cfg["seeds"] if s.get("discover", True)]
        custom_settings = {
            "ROBOTSTXT_OBEY": True, "USER_AGENT": user_agent, "AUTOTHROTTLE_ENABLED": True,
            "AUTOTHROTTLE_START_DELAY": 1.5, "DOWNLOAD_DELAY": 1.5,
            "CONCURRENT_REQUESTS_PER_DOMAIN": 2, "CLOSESPIDER_PAGECOUNT": max_pages,
            "DEPTH_LIMIT": 4, "HTTPCACHE_ENABLED": True, "LOG_LEVEL": "INFO",
        }

        def parse(self, response):
            found.add(response.url)
            if b"html" not in response.headers.get("Content-Type", b""):
                return
            for href in response.css("a::attr(href)").getall():
                url = scope.normalize(response.url, href)
                if url and scope.allows(url) and url not in found:
                    found.add(url)
                    if not url.endswith("/download"):
                        yield response.follow(url, self.parse)

    proc = CrawlerProcess()
    proc.crawl(ULDiscoverySpider)
    proc.start()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(sorted(found)))
    print(f"wrote {len(found)} URLs to {out}")


if __name__ == "__main__":
    from app.config import get_settings

    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=Path("data/discovered_urls.txt"))
    ap.add_argument("--max-pages", type=int, default=1000)
    a = ap.parse_args()
    run(a.out, a.max_pages, get_settings().crawl_user_agent)

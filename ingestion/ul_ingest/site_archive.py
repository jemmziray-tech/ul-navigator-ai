"""Resumable public UL sitemap/link archive and bounded live publisher.

Run with the repository's Python and PYTHONPATH=backend;ingestion.
No Gemini calls are made. Queue, extracted text, provenance and failures survive restarts.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import re
import shutil
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urldefrag, urljoin, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from .crawler import PoliteFetcher, FetchResult
from .extractors import extract

HOSTS = {"www.ul.ie", "ul.ie"}
BLOCK = re.compile(r"^/(?:user|admin|core|profiles|search|comment|filter|node/add|media/oembed)(?:/|$)", re.I)
ASSET = re.compile(r"\.(?:jpe?g|png|gif|svg|webp|ico|css|js|map|woff2?|ttf|mp[34]|mov|avi|zip|gz|exe|ics|docx?|xlsx?|pptx?)$", re.I)
PRIORITIES = ["/fees", "/accommodation", "/academic-registry", "/student-affairs",
              "/global", "/study", "/gps", "/library", "/cecd", "/policy-hub",
              "/disability", "/medical", "/counselling", "/student-life", "/ctl"]


def now():
    return datetime.now(timezone.utc).isoformat()


def canonical(base, href):
    """No authentication, query traps, external hosts or executable/media downloads."""
    if not href or href.startswith(("#", "mailto:", "tel:", "javascript:")):
        return None
    u = urlsplit(urldefrag(urljoin(base, href.strip()))[0])
    path = unquote(u.path)
    if u.scheme not in {"http", "https"} or u.hostname not in HOSTS:
        return None
    inline_download = u.query == "inline" and (path.endswith("/download") or path.lower().endswith(".pdf"))
    if u.username or u.password or u.port not in (None, 80, 443) or (u.query and not inline_download):
        return None  # UL robots.txt excludes query parameters; don't erase them into different pages
    if BLOCK.search(path) or ASSET.search(path) or re.search(r"/(?:edit|delete|login|logout)(?:/|$)", path, re.I):
        return None
    if path.lower().endswith((".php", ".yml", ".yaml", ".sql")):
        return None
    return urlunsplit(("https", "www.ul.ie", u.path.rstrip("/") or "/", "inline" if inline_download else "", ""))


def priority(url):
    p = urlsplit(url).path.lower()
    depth = len([part for part in p.split('/') if part])
    years = [int(y) for y in re.findall(r'(?<!\d)(20\d{2})(?!\d)', p)]
    age = max(0, datetime.now(timezone.utc).year - max(years)) * 10 if years else 0
    for i, prefix in enumerate(PRIORITIES):
        if p == prefix or p.startswith(prefix + "/") or p.startswith(prefix + "-"):
            return i + depth * 3 + age
    if p.startswith("/media/") or p.endswith(".pdf"):
        return 30
    if "/courses/" in p or "/course/" in p:
        return 80
    if "/news/" in p or "/events/" in p:
        return 250
    return 150


def category(url):
    p = url.lower()
    for key, cat in [("fees", "fees"), ("accommodation", "accommodation"),
                     ("scholarship", "scholarships"), ("global", "international"),
                     ("academic-registry", "regulations"), ("policy-hub", "regulations"),
                     ("postgraduate", "postgraduate"), ("/gps", "postgraduate"),
                     ("undergraduate", "undergraduate"), ("/library", "library"),
                     ("/cecd", "careers"), ("student", "student_support")]:
        if key in p:
            return cat
    return "general"


def connect(root):
    root.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(root / "queue.sqlite3", timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA journal_mode=WAL")
    db.execute("""CREATE TABLE IF NOT EXISTS pages (
      url TEXT PRIMARY KEY, state TEXT NOT NULL DEFAULT 'pending', priority INTEGER,
      attempts INTEGER NOT NULL DEFAULT 0, http_status INTEGER, title TEXT, category TEXT,
      words INTEGER, content_hash TEXT, payload TEXT, fetched_at TEXT, error TEXT,
      publish_state TEXT NOT NULL DEFAULT 'pending', publish_error TEXT,
      publish_attempts INTEGER NOT NULL DEFAULT 0, published_at TEXT)""")
    columns = {row[1] for row in db.execute("PRAGMA table_info(pages)")}
    if "link_scope_version" not in columns:
        try:
            db.execute("ALTER TABLE pages ADD COLUMN link_scope_version INTEGER NOT NULL DEFAULT 0")
        except sqlite3.OperationalError:
            if "link_scope_version" not in {row[1] for row in db.execute("PRAGMA table_info(pages)")}:
                raise
    db.execute("CREATE INDEX IF NOT EXISTS queue_order ON pages(state,priority,url)")
    db.commit()
    return db


def enqueue(db, urls):
    values = {(u, priority(u)) for href in urls if (u := canonical("https://www.ul.ie/", href))}
    db.executemany("INSERT OR IGNORE INTO pages(url,priority) VALUES (?,?)", values)
    db.commit()


def atomic_json(path, value):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


@contextmanager
def worker_lock(root, mode):
    """OS-held lock releases after crashes; a second launch cannot duplicate workers."""
    root.mkdir(parents=True, exist_ok=True)
    handle = (root / (mode + '.lock')).open('a+b')
    try:
        if handle.tell() == 0:
            handle.write(b'0'); handle.flush()
        handle.seek(0)
        if os.name == 'nt':
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield
    finally:
        handle.close()


def report(db, root, mode, state="running", **extra):
    field = "state" if mode == "crawl" else "publish_state"
    result = {"updated_at": now(), "worker_state": state, "process_id": os.getpid(),
              "queued_urls": db.execute("SELECT count(*) FROM pages").fetchone()[0],
              "collected_documents": db.execute("SELECT count(*) FROM pages WHERE payload IS NOT NULL").fetchone()[0],
              "counts": dict(db.execute(f"SELECT {field},count(*) FROM pages GROUP BY {field}")),
              **extra}
    atomic_json(root / f"{mode}-status.json", result)
    return result


def safe_fetch(fetcher, url):
    # Disable httpx automatic redirects so every hop is scoped and robots-checked FIRST.
    fetcher.client.follow_redirects = False
    for _ in range(6):
        res = fetcher.fetch(url)
        if res.status not in (301, 302, 303, 307, 308):
            return res
        for cachefile in fetcher._cache_paths(url):
            cachefile.unlink(missing_ok=True)
        # PoliteFetcher stores response headers only selectively; use a redirect-aware
        # response hook to retain Location without issuing a second request.
        target = canonical(url, getattr(fetcher, "redirect_location", ""))
        if not target:
            return FetchResult(url=url, error="redirect outside public crawl scope")
        url = target
    return FetchResult(url=url, error="redirect loop")


def crawl(args):
    root = Path(args.archive).resolve()
    db = connect(root)
    if args.inventory:
        enqueue(db, json.loads(Path(args.inventory).read_text(encoding="utf-8")))
    enqueue(db, ["https://www.ul.ie/"])
    # Backfill public PDF links omitted by the first strict no-query rule.
    # Existing extracted payloads remain available to the publisher during refresh.
    db.execute("UPDATE pages SET state='pending' WHERE state='ready' AND link_scope_version=0")
    # A previous process may have exited between claim and commit.
    db.execute("UPDATE pages SET state='pending' WHERE state='fetching'")
    if args.retry_failed:
        db.execute("UPDATE pages SET state='pending',error=NULL WHERE state='failed' AND attempts<3")
    db.commit()
    (root / "documents").mkdir(exist_ok=True)
    fetcher = PoliteFetcher(
        "ULNavigatorAI/1.1 (+https://ul-navigator-ai.vercel.app; public academic reference archive)",
        root / "raw", delay_s=max(3, args.delay), max_retries=2, timeout_s=25,
        max_bytes=15_000_000, cache_ttl_s=3600)

    def capture_location(response):
        fetcher.redirect_location = response.headers.get("location", "")
    fetcher.client.event_hooks["response"].append(capture_location)
    processed = 0
    robots_checked = time.monotonic()
    try:
        while args.limit == 0 or processed < args.limit:
            if time.monotonic() - robots_checked > 3600:
                fetcher.robots._parsers.clear()
                robots_checked = time.monotonic()
            if (root / "STOP").exists():
                report(db, root, "crawl", "paused_by_stop_file")
                return
            if shutil.disk_usage(root).free < 5 * 1024**3:
                report(db, root, "crawl", "paused_low_disk")
                return
            row = db.execute("SELECT * FROM pages WHERE state='pending' ORDER BY priority,url LIMIT 1").fetchone()
            if row is None:
                report(db, root, "crawl", "complete")
                return
            url = row["url"]
            db.execute("UPDATE pages SET state='fetching',attempts=attempts+1 WHERE url=?", (url,))
            db.commit()
            try:
                res = safe_fetch(fetcher, url)
                if not res.ok:
                    raise ValueError(res.error or f"HTTP {res.status}")
                if res.kind == "html":
                    soup = BeautifulSoup(res.content, "lxml")
                    enqueue(db, [v for a in soup.find_all("a", href=True)
                                 if (v := canonical(res.final_url or url, a["href"]))])
                if res.kind not in {"html", "pdf", "csv", "txt", "rtf"}:
                    db.execute("UPDATE pages SET state='skipped',error='unsupported content type' WHERE url=?", (url,))
                else:
                    ex = extract(res.kind, res.content, url)
                    words = len(ex.markdown.split())
                    if words < 5:
                        raise ValueError("no useful extractable text; may require OCR or JavaScript")
                    payload = {"url": url, "final_url": res.final_url, "title": ex.title,
                               "markdown": ex.markdown, "kind": res.kind, "page_count": ex.page_count,
                               "category": category(url), "collected_at": now(),
                               "http_status": res.status, "etag": res.etag,
                               "last_modified": res.last_modified,
                               "links": ([v for a in soup.find_all("a", href=True)
                                          if (v := canonical(res.final_url or url, a["href"]))]
                                         if res.kind == "html" else []),
                               "raw_sha256": hashlib.sha256(res.content).hexdigest()}
                    digest = hashlib.sha256(ex.markdown.encode()).hexdigest()
                    path = root / "documents" / (hashlib.sha1(url.encode()).hexdigest() + ".json.gz")
                    with gzip.open(path, "wt", encoding="utf-8") as f:
                        json.dump(payload, f, ensure_ascii=False)
                    db.execute("""UPDATE pages SET state='ready',link_scope_version=1,http_status=?,title=?,category=?,
                               words=?,content_hash=?,payload=?,fetched_at=?,error=NULL WHERE url=?""",
                               (res.status, ex.title, payload["category"], words, digest, str(path), now(), url))
                # Extracted text + content hash are retained. Avoid filling the disk with raw HTML.
                for cached_url in {url, res.final_url} - {"", None}:
                    for cachefile in fetcher._cache_paths(cached_url):
                        cachefile.unlink(missing_ok=True)
            except Exception as exc:
                db.execute("UPDATE pages SET state='failed',error=?,fetched_at=? WHERE url=?",
                           (f"{type(exc).__name__}: {str(exc)[:400]}", now(), url))
            db.commit()
            processed += 1
            report(db, root, "crawl", last_url=url)
            if processed % 25 == 0:
                print(json.dumps(report(db, root, "crawl")), flush=True)
        report(db, root, "crawl", "batch_complete")
    finally:
        fetcher.close()
        db.close()


def publish(args):
    """Use the existing protected API: production chats and uploaded sources stay intact.

    One request at a time; no provider generation calls; a hard chunk/document ceiling
    bounds this initial rollout's compute and RAM. The complete crawl continues locally.
    """
    import httpx
    from .chunking import chunk_markdown

    root = Path(args.archive).resolve()
    db = connect(root)
    base = args.backend.rstrip("/")
    if args.retry_failed:
        db.execute("UPDATE pages SET publish_state='pending' WHERE publish_state='failed' AND publish_attempts<3")
        db.commit()
    if base != os.environ.get("UL_PUBLISH_API", "http://localhost:8000").rstrip("/"):
        raise ValueError("publisher target must match UL_PUBLISH_API (defaults to localhost)")
    # Credential is read at runtime, never placed in logs, process arguments or reports.
    credentials = Path(args.credentials).read_text(encoding="utf-8")
    password_match = re.search(r"ULNav-[A-Za-z0-9_-]+", credentials)
    if not password_match:
        raise ValueError("admin password not found in maintainer credentials file")
    with httpx.Client(timeout=240, follow_redirects=False) as client:
        # Scaling from zero can briefly return platform 500/503 responses.
        # Poll readiness before using the tightly rate-limited login endpoint.
        for attempt in range(8):
            report(db, root, "publish", "waiting_for_backend", attempt=attempt + 1)
            if (root / "STOP").exists():
                report(db, root, "publish", "paused_by_stop_file")
                return
            try:
                ready = client.get(base + "/health/ready", timeout=45)
                if ready.status_code == 200:
                    break
                if ready.status_code in (401, 403):
                    ready.raise_for_status()
            except httpx.RequestError:
                pass
            time.sleep(15)
        else:
            report(db, root, "publish", "paused_backend_unavailable")
            return
        token = None
        def login():
            nonlocal token
            r = client.post(base + "/api/admin/login", json={"username": "admin", "password": password_match[0]})
            r.raise_for_status()
            token = r.json()["access_token"]
        login()
        known = set()
        page = 1
        while True:
            r = client.get(base + "/api/sources", params={"page": page, "size": 100})
            r.raise_for_status()
            result = r.json()
            known.update(item["url"] for item in result["items"])
            if page * 100 >= result["total"]:
                break
            page += 1
        stats = client.get(base + "/api/stats"); stats.raise_for_status()
        start_chunks = stats.json()["chunks"]
        published, chunks, consecutive_failures = 0, start_chunks, 0
        while published < args.max_documents:
            if (root / "STOP").exists():
                report(db, root, "publish", "paused_by_stop_file", chunks=chunks)
                return
            row = db.execute("""SELECT * FROM pages WHERE payload IS NOT NULL AND publish_state='pending'
                                AND publish_attempts<3 ORDER BY priority,url LIMIT 1""").fetchone()
            if row is None:
                pending = db.execute("SELECT count(*) FROM pages WHERE state IN ('pending','fetching')").fetchone()[0]
                if not args.watch or pending == 0:
                    report(db, root, "publish", "batch_complete", chunks=chunks)
                    return
                report(db, root, "publish", "waiting_for_crawl", chunks=chunks)
                time.sleep(10)
                continue
            url = row["url"]
            if url in known:
                db.execute("UPDATE pages SET publish_state='already_live' WHERE url=?", (url,)); db.commit()
                continue
            with gzip.open(row["payload"], "rt", encoding="utf-8") as f:
                payload = json.load(f)
            estimate = len(chunk_markdown(payload["markdown"], 260, 50, 40))
            if len(payload["markdown"].split()) < 25 or estimate == 0:
                db.execute("UPDATE pages SET publish_state='deferred_short_page' WHERE url=?", (url,)); db.commit()
                continue
            if chunks + estimate > args.max_chunks:
                report(db, root, "publish", "paused_at_capacity", chunks=chunks, ceiling=args.max_chunks)
                return
            if len(payload["markdown"].encode()) > 4_000_000 or estimate > 200:
                db.execute("UPDATE pages SET publish_state='deferred_large_document' WHERE url=?", (url,)); db.commit()
                continue
            try:
                db.execute("UPDATE pages SET publish_attempts=publish_attempts+1 WHERE url=?", (url,)); db.commit()
                def upload():
                    return client.post(base + "/api/admin/upload", headers={"Authorization": "Bearer " + token},
                        data={"title": payload["title"], "category": payload["category"], "source_url": url},
                        files={"file": (hashlib.sha1(url.encode()).hexdigest() + ".md",
                                         payload["markdown"].encode(), "text/markdown")})
                r = upload()
                if r.status_code == 401:
                    login(); r = upload()
                if r.status_code in (429, 503):
                    time.sleep(45)
                    continue
                r.raise_for_status()
                result = r.json()
                if result.get("status") not in {"new", "updated", "unchanged", "duplicate"}:
                    raise ValueError("API did not confirm indexing")
                chunks += result.get("chunks_added", 0) - result.get("chunks_removed", 0)
                known.add(url)
                db.execute("UPDATE pages SET publish_state=?,published_at=?,publish_error=NULL WHERE url=?",
                           ("published_" + result["status"], now(), url))
                published += 1
                consecutive_failures = 0
            except Exception as exc:
                # Response bodies/tokens are deliberately omitted from logs.
                db.execute("UPDATE pages SET publish_state='failed',publish_error=? WHERE url=?",
                           ((f"HTTP {exc.response.status_code}" if isinstance(exc, httpx.HTTPStatusError)
                             else type(exc).__name__), url))
                consecutive_failures += 1
            db.commit()
            if consecutive_failures >= 3:
                report(db, root, "publish", "paused_after_api_failures", chunks=chunks)
                return
            report(db, root, "publish", chunks=chunks, added_this_run=published, last_url=url)
            time.sleep(8)
        report(db, root, "publish", "paused_at_document_limit", chunks=chunks, added_this_run=published)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["crawl", "publish", "status"])
    parser.add_argument("--archive", default="data/site_archive")
    parser.add_argument("--inventory")
    parser.add_argument("--limit", type=int, default=0, help="0 = drain the full persistent queue")
    parser.add_argument("--delay", type=float, default=3)
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--backend", default=os.environ.get("UL_PUBLISH_API", "http://localhost:8000"))
    parser.add_argument("--credentials", default="data/ADMIN_PASSWORD.txt")
    parser.add_argument("--max-documents", type=int, default=1000)
    parser.add_argument("--max-chunks", type=int, default=24000)
    parser.add_argument("--watch", action="store_true")
    args = parser.parse_args()
    if args.limit < 0 or args.max_documents < 1 or not 1 <= args.max_chunks <= 30000:
        parser.error("invalid limits; initial live ceiling may not exceed 30,000 chunks")
    if args.mode in {"crawl", "publish"}:
        with worker_lock(Path(args.archive).resolve(), args.mode):
            if args.mode == "crawl":
                crawl(args)
            else:
                publish(args)
    else:
        db = connect(Path(args.archive))
        print(json.dumps({"counts": dict(db.execute('SELECT state,count(*) FROM pages GROUP BY state')),
                          "publish_counts": dict(db.execute('SELECT publish_state,count(*) FROM pages GROUP BY publish_state'))}, indent=2))
        db.close()


if __name__ == "__main__":
    main()

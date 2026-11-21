"""Ingestion orchestration: crawl -> extract -> clean -> dedupe -> chunk -> embed -> index.

Incremental by design: documents are keyed by URL, change-detected with a SHA-256 content
hash, and only new/changed documents are re-chunked and re-embedded. FAISS vectors are
removed/added by chunk id, so the index is never rebuilt from scratch unless asked.
"""
from __future__ import annotations

import json
import logging
import re
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import yaml
from sqlalchemy import delete, select

from app.config import get_settings
from app.db import Chunk, Document, IngestionJob, init_db, session_scope, utcnow
from app.rag.knowledge_index import KnowledgeIndex, get_index
from app.rag.text import content_hash, doc_id_for, dominant_academic_year, normalize_ws

from .chunking import chunk_markdown
from .crawler import CrawlScope, FetchResult, PoliteFetcher, extract_links
from .extractors import extract, find_boilerplate_lines, remove_boilerplate

log = logging.getLogger("ul_ingest")
SOURCES_FILE = Path(__file__).with_name("sources.yaml")
BOILERPLATE_FILE_NAME = "boilerplate_lines.json"


@dataclass
class DocInput:
    url: str
    kind: str
    title: str
    markdown: str
    category: str
    academic_year: str | None = None
    page_count: int | None = None
    is_manual: bool = False
    etag: str | None = None
    last_modified: str | None = None
    raw_path: str | None = None
    byte_size: int = 0
    preserve_sections: bool = False


@dataclass
class JobReport:
    kind: str
    started: float = field(default_factory=time.time)
    counts: dict = field(default_factory=lambda: {
        "discovered": 0, "fetched": 0, "new": 0, "updated": 0, "unchanged": 0,
        "duplicate": 0, "failed": 0, "skipped": 0, "chunks_added": 0, "chunks_removed": 0})
    failures: list = field(default_factory=list)

    def fail(self, url: str, stage: str, error: str) -> None:
        self.counts["failed"] += 1
        self.failures.append({"url": url, "stage": stage, "error": error[:500],
                              "at": datetime.now(timezone.utc).isoformat()})
        log.warning("ingestion failure", extra={"extra_fields": {"url": url, "stage": stage,
                                                                  "error": error[:300]}})


def load_sources(path: Path = SOURCES_FILE) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def categorize(url: str, rules: list, default: str) -> str:
    low = url.lower()
    for kw, cat in rules:
        if kw in low:
            return cat
    return default


# --------------------------------------------------------------------- indexing
def upsert_document(index: KnowledgeIndex, d: DocInput, report: JobReport) -> str:
    s = get_settings()
    md = normalize_ws(d.markdown)
    if len(md.split()) < 25:
        report.counts["skipped"] += 1
        report.failures.append({"url": d.url, "stage": "extract",
                                "error": "too little text extracted (<25 words)"})
        return "skipped"
    h = content_hash(md)
    did = doc_id_for(d.url)
    year = d.academic_year or dominant_academic_year(d.url, d.title, md[:4000])
    with session_scope() as db:
        doc = db.get(Document, did)
        if doc and doc.content_hash == h and doc.status == "indexed":
            doc.collected_at = utcnow()
            report.counts["unchanged"] += 1
            return "unchanged"
        dup = db.scalar(select(Document).where(Document.content_hash == h, Document.id != did,
                                               Document.status == "indexed"))
        old_ids = [c for (c,) in db.execute(select(Chunk.id).where(Chunk.document_id == did))]
        if old_ids:
            index.remove_vectors(old_ids)
            db.execute(delete(Chunk).where(Chunk.document_id == did))
            report.counts["chunks_removed"] += len(old_ids)
        status = "updated" if doc else "new"
        if doc is None:
            doc = Document(id=did, url=d.url)
            db.add(doc)
        doc.title = (d.title or d.url)[:500]
        doc.category = d.category
        doc.academic_year = year
        doc.content_type = d.kind
        doc.content_hash = h
        doc.is_manual = d.is_manual
        doc.etag, doc.last_modified = d.etag, d.last_modified
        doc.raw_path = d.raw_path
        doc.byte_size = d.byte_size
        doc.page_count = d.page_count
        doc.preview = re.sub(r"\s+", " ", re.sub(r"[#|*>\-]+", " ", md))[:600]
        doc.collected_at = utcnow()
        doc.error = None
        if dup is not None:
            doc.status, doc.duplicate_of, doc.chunk_count = "duplicate", dup.id, 0
            report.counts["duplicate"] += 1
            return "duplicate"
        doc.status, doc.duplicate_of = "indexed", None
        drafts = chunk_markdown(md, s.chunk_size_words, s.chunk_overlap_words, s.chunk_min_words, d.preserve_sections)
        def _section(sec: str) -> str:  # drop the document title from the heading path
            t = doc.title.strip().lower()
            parts = [x for x in sec.split(" > ") if x.strip().lower() != t]
            return " > ".join(parts)[:480]

        rows = [Chunk(document_id=did, chunk_index=i, text=c.text, section=_section(c.section),
                      page=c.page, category=d.category, academic_year=year,
                      content_hash=content_hash(c.text), word_count=c.word_count)
                for i, c in enumerate(drafts)]
        db.add_all(rows)
        db.flush()
        embed_texts = [f"{doc.title}\n{r.section}\n{r.text}" for r in rows]
        index.add_vectors([r.id for r in rows], embed_texts, db=db)
        doc.chunk_count = len(rows)
        report.counts["chunks_added"] += len(rows)
        report.counts[status] += 1
        return status


def mark_failed(url: str, category: str, error: str) -> None:
    did = doc_id_for(url)
    with session_scope() as db:
        doc = db.get(Document, did)
        if doc is None:  # record so the admin dashboard shows the failure
            db.add(Document(id=did, url=url, title=url, category=category, status="failed",
                            error=error[:1000]))
        else:
            doc.error = error[:1000]  # keep previously indexed content


def _start_job(kind: str) -> str:
    with session_scope() as db:
        job = IngestionJob(kind=kind)
        db.add(job)
        db.flush()
        return job.id


def _finish_job(job_id: str, report: JobReport) -> Path:
    s = get_settings()
    c = report.counts
    ok = c["new"] + c["updated"] + c["unchanged"] + c["duplicate"]
    status = "failed" if ok == 0 and c["failed"] else ("partial" if report.failures else "success")
    path = s.reports_dir / f"ingest_{report.kind}_{datetime.now():%Y%m%d_%H%M%S}.json"
    payload = {"job_id": job_id, "kind": report.kind, "status": status,
               "duration_s": round(time.time() - report.started, 1), "counts": c,
               "failures": report.failures}
    path.write_text(json.dumps(payload, indent=2))
    with session_scope() as db:
        job = db.get(IngestionJob, job_id)
        job.status, job.finished_at = status, utcnow()
        job.stats = {**c, "duration_s": payload["duration_s"]}
        job.failures = report.failures[:500]
        job.report_path = str(path)
    log.info("ingestion job finished", extra={"extra_fields": payload | {"failures": len(report.failures)}})
    return path


def _boilerplate_path() -> Path:
    return get_settings().index_dir / BOILERPLATE_FILE_NAME


def _load_boilerplate() -> set[str]:
    p = _boilerplate_path()
    return set(json.loads(p.read_text())) if p.exists() else set()


# ------------------------------------------------------------------------ crawl
def crawl(max_pages: int | None = None, max_depth: int | None = None, offline: bool = False,
          seeds_only: bool = False, extra_urls: list[str] | None = None,
          fetcher: PoliteFetcher | None = None, sources: dict | None = None) -> dict:
    s = get_settings()
    init_db()
    cfg = sources or load_sources()
    scope = CrawlScope.from_config(cfg)
    rules = cfg.get("category_rules", [])
    max_pages = max_pages or s.crawl_max_pages
    max_depth = 0 if seeds_only else (s.crawl_max_depth if max_depth is None else max_depth)
    own_fetcher = fetcher is None
    fetcher = fetcher or PoliteFetcher(
        s.crawl_user_agent, s.raw_dir, s.crawl_delay_s, s.crawl_timeout_s, s.crawl_max_retries,
        s.crawl_max_pdf_mb * 1_000_000, offline=offline,
        cache_ttl_s=s.crawl_cache_ttl_hours * 3600)
    index = get_index()
    report = JobReport("crawl")
    job_id = _start_job("crawl")

    queue: deque[tuple[str, int, dict]] = deque()
    seen: set[str] = set()
    for seed in cfg.get("seeds", []):
        queue.append((seed["url"], 0, seed))
        seen.add(seed["url"])
    for u in extra_urls or []:
        queue.append((u, 0, {"url": u, "category": categorize(u, rules, "general")}))
        seen.add(u)
    report.counts["discovered"] = len(seen)

    collected: list[tuple[DocInput, bool]] = []  # (doc, is_html)
    fetched = 0
    deferred: list[tuple[str, int, dict]] = []
    try:
        while (queue or deferred) and fetched < max_pages:
            if not queue:  # second chance for pages that were rate-limited
                queue.extend(deferred)
                deferred = []
                for item in queue:
                    item[2]["_retried"] = True
            url, depth, seed = queue.popleft()
            res: FetchResult = fetcher.fetch(url)
            fetched += 1
            if not res.ok and "429" in (res.error or "") and not seed.get("_retried"):
                deferred.append((url, depth, dict(seed)))
                fetched -= 1
                continue
            if not res.ok:
                report.fail(url, "fetch", res.error or f"HTTP {res.status}")
                mark_failed(url, seed.get("category", "general"), res.error or "fetch failed")
                continue
            report.counts["fetched"] += 1
            kind = res.kind
            if kind not in ("html", "pdf", "csv", "txt", "rtf"):
                report.counts["skipped"] += 1
                continue
            category = seed.get("category") if seed.get("url") == url else categorize(
                url, rules, seed.get("category", "general"))
            try:
                content = res.content
                if kind == "html" and s.crawl_use_playwright:
                    probe = extract("html", content, url)
                    if len(probe.markdown.split()) < 80:
                        rendered = fetcher.render_with_playwright(url)
                        if rendered:
                            content = rendered.encode()
                ex = extract(kind, content, url, seed.get("title", "") if seed.get("url") == url else "")
            except Exception as exc:  # noqa: BLE001
                report.fail(url, "extract", f"{type(exc).__name__}: {exc}")
                mark_failed(url, category or "general", f"extract: {exc}")
                continue
            title = (seed.get("title") if seed.get("url") == url else None) or ex.title or url
            collected.append((DocInput(
                url=url, kind=kind, title=title, markdown=ex.markdown, category=category or "general",
                academic_year=seed.get("year") if seed.get("url") == url else None,
                page_count=ex.page_count, etag=res.etag, last_modified=res.last_modified,
                raw_path=res.raw_path, byte_size=len(res.content)), kind == "html"))
            discover = seed.get("discover", True) if seed.get("url") == url else True
            if kind == "html" and discover and depth < max_depth:
                for link in extract_links(content, res.final_url or url, scope):
                    if link not in seen:
                        seen.add(link)
                        queue.append((link, depth + 1, {"category": category,
                                                        "seed": seed.get("url")}))
                report.counts["discovered"] = len(seen)
    finally:
        if own_fetcher:
            fetcher.close()

    # site-wide boilerplate (menus, footers repeated across pages)
    html_docs = [d.markdown for d, is_html in collected if is_html]
    boiler = _load_boilerplate() | find_boilerplate_lines(html_docs)
    if boiler:
        _boilerplate_path().write_text(json.dumps(sorted(boiler)))
    for d, is_html in collected:
        if is_html:
            d.markdown = remove_boilerplate(d.markdown, boiler)
        try:
            upsert_document(index, d, report)
        except Exception as exc:  # noqa: BLE001
            report.fail(d.url, "index", f"{type(exc).__name__}: {exc}")
    index.persist()
    index.reload()
    report.counts["not_fetched_due_to_limit"] = len(queue)
    path = _finish_job(job_id, report)
    return {"job_id": job_id, "report": str(path), **report.counts,
            "failures": report.failures}


# ------------------------------------------------------------------- uploads
KIND_BY_EXT = {".pdf": "pdf", ".csv": "csv", ".rtf": "rtf", ".txt": "txt", ".md": "md",
               ".html": "html", ".htm": "html"}


def ingest_bytes(data: bytes, filename: str, *, category: str = "general", title: str = "",
                 source_url: str | None = None, academic_year: str | None = None,
                 index: KnowledgeIndex | None = None, preserve_sections: bool = False) -> dict:
    """Ingest an authorised, manually supplied document (admin upload / CLI)."""
    init_db()
    ext = Path(filename).suffix.lower()
    kind = KIND_BY_EXT.get(ext)
    if kind is None:
        raise ValueError(f"unsupported file type: {ext}")
    index = index or get_index()
    report = JobReport("upload")
    job_id = _start_job("upload")
    url = source_url or f"upload://{Path(filename).name}"
    status = "failed"
    try:
        ex = extract(kind, data, url, title)
        status = upsert_document(index, DocInput(
            url=url, kind="txt" if kind == "md" else kind, title=title or ex.title or Path(filename).stem,
            markdown=ex.markdown, category=category, academic_year=academic_year,
            page_count=ex.page_count, is_manual=True, byte_size=len(data), preserve_sections=preserve_sections), report)
        index.persist()
        index.reload()
    except Exception as exc:  # noqa: BLE001
        report.fail(url, "upload", f"{type(exc).__name__}: {exc}")
    _finish_job(job_id, report)
    return {"job_id": job_id, "url": url, "status": status, **report.counts,
            "failures": report.failures}


# --------------------------------------------------------------- maintenance
def delete_document(doc_id_or_url: str, index: KnowledgeIndex | None = None) -> bool:
    index = index or get_index()
    with session_scope() as db:
        doc = db.get(Document, doc_id_or_url) or db.scalar(
            select(Document).where(Document.url == doc_id_or_url))
        if doc is None:
            return False
        ids = [c for (c,) in db.execute(select(Chunk.id).where(Chunk.document_id == doc.id))]
        index.remove_vectors(ids)
        db.delete(doc)
    index.persist()
    index.reload()
    return True


def reconcile(index: KnowledgeIndex | None = None) -> dict:
    """Make FAISS and the database agree: drop orphan vectors, embed missing chunks."""
    index = index or get_index()
    job_id = _start_job("reconcile")
    report = JobReport("reconcile")
    with session_scope() as db:
        rows = db.execute(select(Chunk.id, Chunk.text, Chunk.section, Document.title)
                          .join(Document).where(Document.status == "indexed")).all()
        stale = [c for (c,) in db.execute(select(Chunk.id).join(Document)
                                          .where(Document.status != "indexed"))]
    from app.rag.embedding_cache import import_seed_embeddings
    import_seed_embeddings(index.embedder.name, index.embedder.dim)
    db_ids = {r[0] for r in rows}
    faiss_ids = index.store.ids()
    orphans = list((faiss_ids - db_ids) | (set(stale) & faiss_ids))
    missing = [r for r in rows if r[0] not in faiss_ids]
    # The replicated content-addressed cache survives scale-to-zero and also
    # prevents an old seed vector from being reused after a chunk ID is recycled.
    index.store.reset()
    index.add_vectors([r[0] for r in rows], [f"{r[3]}\n{r[2]}\n{r[1]}" for r in rows])
    index.persist()
    index.reload()
    report.counts["chunks_removed"] = len(orphans)
    report.counts["chunks_added"] = len(missing)
    _finish_job(job_id, report)
    return {"orphan_vectors_removed": len(orphans), "missing_vectors_added": len(missing),
            "vectors": index.store.size, "chunks": len(db_ids)}


def reindex_all(index: KnowledgeIndex | None = None) -> dict:
    """Re-embed every chunk (e.g. after changing EMBEDDING_MODEL)."""
    index = index or get_index()
    job_id = _start_job("reindex")
    report = JobReport("reindex")
    index.store.reset()
    with session_scope() as db:
        rows = db.execute(select(Chunk.id, Chunk.text, Chunk.section, Document.title)
                          .join(Document).where(Document.status == "indexed")).all()
    index.add_vectors([r[0] for r in rows], [f"{r[3]}\n{r[2]}\n{r[1]}" for r in rows], use_cache=False)
    index.persist()
    index.reload()
    report.counts["chunks_added"] = len(rows)
    _finish_job(job_id, report)
    return {"vectors": index.store.size}


def find_duplicates() -> list[dict]:
    with session_scope() as db:
        docs = db.scalars(select(Document).where(Document.status == "duplicate")).all()
        return [{"id": d.id, "url": d.url, "title": d.title, "duplicate_of": d.duplicate_of}
                for d in docs]

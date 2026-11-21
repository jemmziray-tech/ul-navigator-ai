"""Protected administration endpoints."""
from __future__ import annotations

import logging
import threading
from collections import deque
from datetime import datetime, timedelta, timezone

from fastapi import (APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Request,
                     UploadFile)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import (Chunk, Conversation, Document, Feedback, IngestionJob, Message, QueryLog,
                  get_db)
from ..security import (authenticate, create_token, limiter, require_admin, safe_filename,
                        validate_upload)
from .schemas import CrawlRequest, LoginRequest

router = APIRouter(prefix="/api/admin", tags=["admin"])
log = logging.getLogger(__name__)
_job_lock = threading.Lock()


@router.post("/curricula/import")
def import_curriculum_snapshot(_: str = Depends(require_admin)):
    from ul_ingest.curriculum_index import install_snapshot
    with _job_lock:
        try: return install_snapshot()
        except ValueError as exc: raise HTTPException(409, str(exc)) from None


@router.post("/login")
@limiter.limit(lambda: get_settings().rate_limit_login)
def login(request: Request, body: LoginRequest):
    if not authenticate(body.username, body.password):
        log.warning("failed admin login", extra={"extra_fields": {"username": body.username[:40]}})
        raise HTTPException(401, "Invalid credentials")
    token, exp = create_token(body.username)
    return {"access_token": token, "token_type": "bearer", "expires_at": exp}


@router.get("/overview")
def overview(_: str = Depends(require_admin), db: Session = Depends(get_db)):
    by_status = dict(db.execute(select(Document.status, func.count()).group_by(Document.status)).all())
    coverage = [{"category": c, "documents": n, "chunks": int(ch or 0)} for c, n, ch in db.execute(
        select(Document.category, func.count(), func.sum(Document.chunk_count))
        .where(Document.status == "indexed").group_by(Document.category)).all()]
    jobs = dict(db.execute(select(IngestionJob.status, func.count())
                           .group_by(IngestionJob.status)).all())
    last_sync = db.scalar(select(func.max(IngestionJob.finished_at)))
    since = datetime.now(timezone.utc) - timedelta(days=30)
    q = select(QueryLog).where(QueryLog.created_at >= since)
    logs = db.scalars(q).all()
    n = len(logs)
    lat = sorted(l.total_ms for l in logs)
    ret = sorted(l.retrieval_ms for l in logs)

    def pct(xs, p):
        return round(xs[min(len(xs) - 1, int(len(xs) * p))], 1) if xs else None

    fb = dict(db.execute(select(Feedback.rating, func.count()).group_by(Feedback.rating)).all())
    modes: dict[str, int] = {}
    for l in logs:
        modes[l.mode] = modes.get(l.mode, 0) + 1
    return {
        "documents": {"by_status": by_status,
                      "indexed": by_status.get("indexed", 0),
                      "chunks": db.scalar(select(func.count()).select_from(Chunk)) or 0},
        "coverage": sorted(coverage, key=lambda x: -x["documents"]),
        "jobs": jobs, "last_sync": last_sync,
        "queries_30d": {"total": n, "answered": sum(1 for l in logs if l.answered),
                        "unanswered": sum(1 for l in logs if not l.answered),
                        "modes": modes,
                        "latency_ms": {"p50": pct(lat, .5), "p95": pct(lat, .95)},
                        "retrieval_ms": {"p50": pct(ret, .5), "p95": pct(ret, .95)},
                        "avg_citations": round(sum(l.n_citations for l in logs) / n, 2) if n else None},
        "feedback": {"up": fb.get(1, 0), "down": fb.get(-1, 0)},
        "conversations": db.scalar(select(func.count()).select_from(Conversation)) or 0,
        "busy": _job_lock.locked(),
    }


@router.get("/jobs")
def jobs(_: str = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(IngestionJob).order_by(IngestionJob.started_at.desc()).limit(50)).all()
    return [{"id": j.id, "kind": j.kind, "status": j.status, "started_at": j.started_at,
             "finished_at": j.finished_at, "stats": j.stats, "failure_count": len(j.failures or [])}
            for j in rows]


@router.get("/jobs/{job_id}")
def job_detail(job_id: str, _: str = Depends(require_admin), db: Session = Depends(get_db)):
    j = db.get(IngestionJob, job_id)
    if j is None:
        raise HTTPException(404, "Job not found")
    return {"id": j.id, "kind": j.kind, "status": j.status, "started_at": j.started_at,
            "finished_at": j.finished_at, "stats": j.stats, "failures": j.failures}


@router.get("/documents")
def documents(status: str | None = None, q: str | None = None, page: int = 1,
              _: str = Depends(require_admin), db: Session = Depends(get_db)):
    stmt = select(Document)
    if status:
        stmt = stmt.where(Document.status == status)
    if q:
        stmt = stmt.where(Document.title.ilike(f"%{q}%") | Document.url.ilike(f"%{q}%"))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Document.updated_at.desc()).offset((max(page, 1) - 1) * 50)
                      .limit(50)).all()
    return {"total": total, "items": [
        {"id": d.id, "title": d.title, "url": d.url, "category": d.category,
         "status": d.status, "academic_year": d.academic_year, "content_type": d.content_type,
         "chunk_count": d.chunk_count, "collected_at": d.collected_at, "error": d.error,
         "duplicate_of": d.duplicate_of, "is_manual": d.is_manual,
         "content_hash": d.content_hash[:12]} for d in rows]}


@router.delete("/documents/{doc_id}")
def delete_doc(doc_id: str, _: str = Depends(require_admin)):
    from ul_ingest.pipeline import delete_document
    with _job_lock:
        if not delete_document(doc_id):
            raise HTTPException(404, "Document not found")
    return {"ok": True}


@router.get("/duplicates")
def duplicates(_: str = Depends(require_admin)):
    from ul_ingest.pipeline import find_duplicates
    return find_duplicates()


@router.get("/unanswered")
def unanswered(_: str = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.scalars(select(QueryLog).where(QueryLog.answered.is_(False))
                      .order_by(QueryLog.created_at.desc()).limit(100)).all()
    return [{"question": r.question, "category": r.category, "created_at": r.created_at,
             "top_score": r.top_score, "flags": r.flags} for r in rows]


@router.get("/feedback")
def feedback_list(_: str = Depends(require_admin), db: Session = Depends(get_db)):
    rows = db.execute(select(Feedback, Message).join(Message, Message.id == Feedback.message_id)
                      .order_by(Feedback.created_at.desc()).limit(100)).all()
    return [{"rating": f.rating, "comment": f.comment, "created_at": f.created_at,
             "answer_excerpt": m.content[:300], "category": (m.meta or {}).get("category")}
            for f, m in rows]


@router.get("/logs")
def ingestion_logs(lines: int = 200, _: str = Depends(require_admin)):
    path = get_settings().logs_dir / "ingestion.log"
    if not path.exists():
        return {"lines": []}
    with path.open(encoding="utf-8", errors="replace") as fh:
        tail = deque(fh, maxlen=max(10, min(lines, 2000)))
    return {"lines": [ln.rstrip() for ln in tail]}


def _run_locked(fn, *args, **kwargs):
    if not _job_lock.acquire(blocking=False):
        return
    try:
        fn(*args, **kwargs)
    except Exception:  # noqa: BLE001
        log.exception("background ingestion job failed")
    finally:
        _job_lock.release()


@router.post("/crawl", status_code=202)
def start_crawl(body: CrawlRequest, background: BackgroundTasks, _: str = Depends(require_admin)):
    from ul_ingest.pipeline import crawl
    if _job_lock.locked():
        raise HTTPException(409, "Another ingestion job is running")
    background.add_task(_run_locked, crawl, body.max_pages, body.max_depth, False,
                        body.seeds_only, body.urls)
    return {"started": True}


@router.post("/reconcile")
def reconcile(_: str = Depends(require_admin)):
    from ul_ingest.pipeline import reconcile as rec
    with _job_lock:
        return rec()


@router.post("/reindex", status_code=202)
def reindex(background: BackgroundTasks, _: str = Depends(require_admin)):
    from ul_ingest.pipeline import reindex_all
    if _job_lock.locked():
        raise HTTPException(409, "Another ingestion job is running")
    background.add_task(_run_locked, reindex_all)
    return {"started": True}


@router.post("/upload")
async def upload(file: UploadFile = File(...), category: str = Form("general"),
                 title: str = Form(""), academic_year: str | None = Form(None),
                 source_url: str | None = Form(None), preserve_sections: bool = Form(False), _: str = Depends(require_admin)):
    from ul_ingest.pipeline import ingest_bytes
    s = get_settings()
    data = await file.read(s.max_upload_mb * 1024 * 1024 + 1)
    name = safe_filename(file.filename or "upload")
    try:
        validate_upload(name, data)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    if source_url and not source_url.startswith(("https://", "http://")):
        raise HTTPException(400, "source_url must be an http(s) URL")
    (s.uploads_dir / name).write_bytes(data)
    with _job_lock:
        out = ingest_bytes(data, name, category=category[:50], title=title[:300],
                           source_url=source_url, academic_year=academic_year, preserve_sections=preserve_sections)
    if out["status"] == "failed":
        raise HTTPException(422, {"message": "Ingestion failed", "failures": out["failures"]})
    return out

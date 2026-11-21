"""Public read-only endpoints: health, stats, knowledge explorer and student tools."""
from __future__ import annotations

import re
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, or_, select, text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..db import Chunk, Document, IngestionJob, get_db
from ..rag.classifier import OFFICIAL_CONTACTS
from ..rag.knowledge_index import get_index
from ..rag.llm import get_llm
from ..rag.text import MODULE_CODE_RE, tokenize
from ..tools import qca
from ..tools.modules import describes_module

router = APIRouter(tags=["public"])


@router.get("/health")
def health():
    return {"status": "ok", "time": datetime.now(timezone.utc).isoformat()}


@router.get("/health/ready")
def ready(db: Session = Depends(get_db)):
    checks: dict = {}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # pragma: no cover
        checks["database"] = f"error: {type(exc).__name__}"
    try:
        checks["index"] = get_index().stats
    except Exception as exc:  # pragma: no cover
        checks["index"] = f"error: {type(exc).__name__}: {exc}"
    s = get_settings()
    checks["llm"] = {"configured": s.gemini_enabled, "model": s.gemini_model,
                     "available": get_llm() is not None}
    ok = checks["database"] == "ok" and isinstance(checks["index"], dict)
    if not ok:
        raise HTTPException(503, checks)
    return {"status": "ready", **checks}


@router.get("/api/stats")
def stats(db: Session = Depends(get_db)):
    docs = db.scalar(select(func.count()).select_from(Document)
                     .where(Document.status == "indexed")) or 0
    chunks = db.scalar(select(func.count()).select_from(Chunk)
                       .join(Document).where(Document.status == "indexed")) or 0
    pdfs = db.scalar(select(func.count()).select_from(Document).where(
        Document.status == "indexed", Document.content_type == "pdf")) or 0
    pages = db.scalar(select(func.coalesce(func.sum(Document.page_count), 0)).where(
        Document.status == "indexed", Document.content_type == "pdf")) or 0
    cats = db.execute(select(Document.category, func.count()).where(Document.status == "indexed")
                      .group_by(Document.category)).all()
    last = db.scalar(select(func.max(IngestionJob.finished_at)).where(
        IngestionJob.status.in_(["success", "partial"])))
    s = get_settings()
    return {"documents": docs, "chunks": chunks, "pdf_documents": pdfs, "pdf_pages": int(pages),
            "categories": {c: n for c, n in cats}, "last_synced": last,
            "generation": "gemini" if s.gemini_enabled else "extractive",
            "embedding_model": s.embedding_model if s.embedding_backend != "hash" else "hash (test)",
            "current_academic_year": s.current_academic_year()}


@router.get("/api/sources")
def list_sources(q: str | None = Query(default=None, max_length=200),
                 category: str | None = Query(default=None, max_length=50),
                 year: str | None = Query(default=None, max_length=10),
                 content_type: str | None = Query(default=None, max_length=10),
                 page: int = Query(default=1, ge=1), size: int = Query(default=20, ge=1, le=100),
                 db: Session = Depends(get_db)):
    stmt = select(Document).where(Document.status == "indexed")
    if category:
        stmt = stmt.where(Document.category == category)
    if year:
        stmt = stmt.where(Document.academic_year == year)
    if content_type:
        stmt = stmt.where(Document.content_type == content_type)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(or_(Document.title.ilike(like), Document.url.ilike(like),
                              Document.preview.ilike(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.scalars(stmt.order_by(Document.category, Document.title)
                      .offset((page - 1) * size).limit(size)).all()
    years = [y for (y,) in db.execute(select(Document.academic_year).distinct()
                                      .where(Document.academic_year.is_not(None)))]
    return {"total": total, "page": page, "size": size, "years": sorted(years, reverse=True),
            "items": [_doc_summary(d) for d in rows]}


def _doc_summary(d: Document) -> dict:
    return {"id": d.id, "title": d.title, "url": d.url, "category": d.category,
            "academic_year": d.academic_year, "content_type": d.content_type,
            "chunk_count": d.chunk_count, "page_count": d.page_count,
            "collected_at": d.collected_at, "preview": d.preview[:280], "is_manual": d.is_manual}


@router.get("/api/sources/{doc_id}")
def get_source(doc_id: str, db: Session = Depends(get_db)):
    d = db.get(Document, doc_id)
    if d is None or d.status != "indexed":
        raise HTTPException(404, "Source not found")
    chunks = db.scalars(select(Chunk).where(Chunk.document_id == doc_id)
                        .order_by(Chunk.chunk_index).limit(60)).all()
    return {**_doc_summary(d),
            "sections": [{"chunk_id": c.id, "section": c.section, "page": c.page,
                          "text": c.text} for c in chunks]}


@router.get("/api/chunks/{chunk_id}")
def get_chunk(chunk_id: int, db: Session = Depends(get_db)):
    c = db.get(Chunk, chunk_id)
    if c is None or c.document.status != "indexed":
        raise HTTPException(404, "Passage not found")
    d = c.document
    return {"chunk_id": c.id, "text": c.text, "section": c.section, "page": c.page,
            "document": _doc_summary(d)}


# ------------------------------------------------------------------ tools
@router.get("/api/curricula")
def curricula(course_id: str | None = Query(None, max_length=80)):
    from ..rag.curricula import catalogue
    courses = catalogue()
    if course_id:
        course = next((c for c in courses if c["id"] == course_id or c.get("code") == course_id.upper()), None)
        if course is None: raise HTTPException(404, "Programme not in the curriculum snapshot")
        return course
    return {"section_preserving_ingestion": 1, "courses": len(courses),
            "structured_courses": sum(bool(c["sections"]) for c in courses),
            "semester_sections": sum(len(c["sections"]) for c in courses)}


@router.get("/api/modules/{code}")
def module_descriptor(code: str, db: Session = Depends(get_db)):
    code = code.upper().strip()
    if not re.fullmatch(r"[A-Z]{2,4}\d{4}[A-Z]?", code): raise HTTPException(422, "Invalid module code")
    rows = db.execute(select(Chunk, Document).join(Document).where(
        Document.status == "indexed", Document.url.like("https://bookofmodules.ul.ie/%"),
        Document.title.like(code + " —%")
    ).order_by(Document.collected_at.desc(), Chunk.chunk_index)).all()
    if not rows: raise HTTPException(404, "This official module descriptor has not yet been indexed")
    doc = rows[0][1]
    chunks = [c for c, d in rows if d.id == doc.id]
    return {"code": code, "title": doc.title, "url": doc.url, "collectedAt": doc.collected_at,
            "text": "\n\n".join(("### " + c.section.split(" > ")[-1] + "\n\n" if c.section else "") + c.text for c in chunks)[:90000],
            "note": "Year Last Offered describes this module's published offering, not a programme's curriculum year."}


@router.get("/api/tools/qca/rules")
def qca_rules():
    return qca.rules()


@router.post("/api/tools/qca")
def qca_calc(body: qca.QCARequest):
    return qca.calculate(body)


def _passages(db: Session, categories: list[str], q: str | None, limit: int) -> list[dict]:
    stmt = (select(Chunk, Document).join(Document)
            .where(Document.status == "indexed", Chunk.category.in_(categories)))
    if q:
        for tok in tokenize(q)[:6]:
            stmt = stmt.where(or_(Chunk.text.ilike(f"%{tok}%"), Chunk.section.ilike(f"%{tok}%"),
                                  Document.title.ilike(f"%{tok}%")))
    rows = db.execute(stmt.order_by(Document.title, Chunk.chunk_index).limit(limit)).all()
    return [{"chunk_id": c.id, "document_id": d.id, "title": d.title, "url": d.url,
             "section": c.section, "page": c.page, "text": c.text,
             "academic_year": c.academic_year, "collected_at": d.collected_at,
             "category": c.category} for c, d in rows]


@router.get("/api/tools/calendar")
def calendar(q: str | None = Query(default=None, max_length=100),
             year: str | None = Query(default=None, max_length=10),
             db: Session = Depends(get_db)):
    items = _passages(db, ["calendar"], q, 80)
    if year:
        items = [i for i in items if i["academic_year"] in (year, None)]
    return {"items": items, "contact": OFFICIAL_CONTACTS["calendar"]}


@router.get("/api/tools/explore")
def explore(category: str = Query(pattern="^(scholarships|accommodation|fees|international)$"),
            q: str | None = Query(default=None, max_length=100), db: Session = Depends(get_db)):
    return {"items": _passages(db, [category], q, 60), "contact": OFFICIAL_CONTACTS[category]}


@router.get("/api/tools/modules")
def module_search(q: str = Query(min_length=2, max_length=100), db: Session = Depends(get_db)):
    """Search indexed module information (booklets, Book of Modules exports) by code or name."""
    qn = q.strip()
    code_m = MODULE_CODE_RE.search(qn.upper())
    stmt = select(Chunk, Document).join(Document).where(Document.status == "indexed")
    if code_m:
        code = f"{code_m.group(1)}{code_m.group(2)}"
        spaced = f"{code_m.group(1)} {code_m.group(2)}"
        stmt = stmt.where(or_(Chunk.text.ilike(f"%{code}%"), Chunk.text.ilike(f"%{spaced}%"),
                              Chunk.section.ilike(f"%{code}%"), Document.title.ilike(f"%{code}%")))
        stmt = stmt.order_by(case((Document.title.ilike(f"{code}%"), 0), else_=1), Chunk.id)
    else:
        stmt = stmt.where(Chunk.category == "modules")
        for tok in tokenize(qn)[:5]:
            stmt = stmt.where(or_(Chunk.text.ilike(f"%{tok}%"), Chunk.section.ilike(f"%{tok}%")))
    rows = db.execute(stmt.limit(40)).all()
    results = []
    references = []
    seen_documents = set()
    for c, d in rows:
        codes = sorted({f"{m.group(1)}{m.group(2)}" for m in MODULE_CODE_RE.finditer(c.text)})
        line = ""
        if code_m:
            for ln in c.text.splitlines():
                if re.search(rf"{code_m.group(1)}\s?{code_m.group(2)}", ln, re.I):
                    line = ln.strip()[:300]
                    break
        item = {"chunk_id": c.id, "title": d.title, "url": d.url, "section": c.section,
                        "page": c.page, "academic_year": c.academic_year,
                        "matched_line": line, "module_codes": codes[:20],
                        "excerpt": c.text[:500]}
        if code_m:
            if not describes_module(c, d, code):
                references.append({**item, "match_type": "reference"})
                continue
            if d.id in seen_documents:
                continue
            seen_documents.add(d.id)
            item["matched_line"] = d.title if re.match(rf"{re.escape(code)}\b", d.title, re.I) else line
        results.append({**item, "match_type": "module"})
    return {"query": qn, "results": results, "references": references,
            "contact": OFFICIAL_CONTACTS["modules"]}


CHECKLIST = [
    {"id": "visa", "stage": "Before you arrive", "title": "Check visa and immigration requirements",
     "detail": "Requirements depend on your nationality. Read UL Global's visa and immigration page.",
     "url": "https://www.ul.ie/global/incoming-students/before-you-arrive/visa-and-immigration",
     "ask": "What visa and immigration steps do international students need before coming to UL?"},
    {"id": "faq", "stage": "Before you arrive", "title": "Read the incoming students FAQs",
     "detail": "Common questions about arriving, documents and first weeks.",
     "url": "https://www.ul.ie/global/incoming-students/need-know-information/incoming-students-faqs",
     "ask": "What do incoming international students need to know before arriving at UL?"},
    {"id": "fees", "stage": "Before you arrive", "title": "Understand your fees and payment deadlines",
     "detail": "Check your fee category and how/when to pay.", "url": "https://www.ul.ie/fees",
     "ask": "How and when do I pay my tuition fees at UL?"},
    {"id": "budget", "stage": "Before you arrive", "title": "Plan your budget",
     "detail": "Use UL's official budget planner to estimate living costs.",
     "url": "https://www.ul.ie/media/budget-planner-2026-27-0/download",
     "ask": "What living costs does the UL budget planner estimate?"},
    {"id": "scholarships", "stage": "Before you arrive", "title": "Look for scholarships",
     "detail": "See which scholarships you may be eligible for.",
     "url": "https://www.ul.ie/study/undergraduate/scholarships",
     "ask": "What scholarships are available for UL students?"},
    {"id": "accommodation", "stage": "Before you arrive", "title": "Arrange accommodation",
     "detail": "Apply for on-campus accommodation or research off-campus options.",
     "url": "https://www.ul.ie/accommodation", "ask": "How do I apply for accommodation at UL?"},
    {"id": "orientation", "stage": "When you arrive", "title": "Attend orientation",
     "detail": "Find your orientation schedule and what to bring.",
     "url": "https://www.ul.ie/academic-registry/orientation",
     "ask": "What happens during UL orientation?"},
    {"id": "registration", "stage": "When you arrive", "title": "Complete registration",
     "detail": "Register with the Academic Registry and get your student ID.",
     "url": "https://www.ul.ie/academic-registry", "ask": "How do I complete registration at UL?"},
    {"id": "calendar", "stage": "When you arrive", "title": "Check the academic calendar",
     "detail": "Know your semester start, exam and holiday dates.",
     "url": "https://www.ul.ie/academic-registry/academic-calendars-past-future/academic-calendar-2026/27",
     "ask": "What are the key dates in the 2026/27 academic calendar?"},
    {"id": "map", "stage": "When you arrive", "title": "Learn your way around campus",
     "detail": "Use the campus maps and room-number guide.",
     "url": "https://www.ul.ie/buildings/campus-maps", "ask": "How do UL room numbers work?"},
    {"id": "library", "stage": "Settling in", "title": "Get set up with the library",
     "detail": "Borrowing, study spaces and online resources.", "url": "https://www.ul.ie/library",
     "ask": "What services does the UL library offer?"},
    {"id": "supports", "stage": "Settling in", "title": "Know where to get support",
     "detail": "Counselling, health, disability and academic supports.",
     "url": "https://www.ul.ie/academic-registry/newstudents/student-supports-resources",
     "ask": "What student supports are available at UL?"},
    {"id": "careers", "stage": "Settling in", "title": "Meet the careers service (CECD)",
     "detail": "Co-op placements, CV help and career guidance.", "url": "https://www.ul.ie/cecd",
     "ask": "How does CECD help students with co-op and careers?"},
]


@router.get("/api/tools/checklist")
def checklist():
    return {"items": CHECKLIST,
            "note": "Steps link to official UL pages. Requirements vary by nationality and "
                    "programme; always follow the official guidance."}

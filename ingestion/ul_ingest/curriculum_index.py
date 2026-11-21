"""Install the reviewed public curriculum seed with cached vectors, preserving user data."""
from pathlib import Path
import json

from .curricula import curriculum_markdown
from .extractors import extract_text
from .pipeline import DocInput, JobReport, upsert_document
from .chunking import chunk_markdown
from app.config import get_settings
from app.db import Chunk, Document, session_scope
from app.rag.embedding_cache import embedding_key, cached_vectors
from app.rag.knowledge_index import get_index
from app.rag.text import normalize_ws, content_hash, doc_id_for
from sqlalchemy import select, func


def snapshot_documents(directory=None):
    directory = Path(directory or Path(__file__).resolve().parents[2] / "backend/app/data")
    courses = json.loads((directory / "curricula.json").read_text(encoding="utf-8"))["courses"]
    modules_file = directory / "module-descriptors.json"
    modules = json.loads(modules_file.read_text(encoding="utf-8")) if modules_file.exists() else []
    docs = []
    for c in courses:
        if c["sections"]:
            docs.append(DocInput(url=c["url"], title="Curriculum | " + (c.get("code") or "") + " | " + c["title"],
                                 markdown=curriculum_markdown(c), kind="txt", category="modules", preserve_sections=True))
    for m in modules:
        docs.append(DocInput(url=m["url"], title=m["code"] + " — " + m.get("title", "Official Book of Modules descriptor"),
                             markdown=m["markdown"], kind="txt", category="modules"))
    for d in docs: d.markdown = normalize_ws(extract_text(d.markdown.encode()).markdown)
    return docs


def embedding_inputs(doc):
    s = get_settings()
    for c in chunk_markdown(doc.markdown, s.chunk_size_words, s.chunk_overlap_words, s.chunk_min_words, doc.preserve_sections):
        section = " > ".join(x for x in c.section.split(" > ") if x.strip().lower() != doc.title.strip().lower())[:480]
        yield f"{doc.title}\n{section}\n{c.text}"


def install_snapshot(index=None, directory=None, require_cache=True):
    index = index or get_index()
    docs = snapshot_documents(directory)
    with session_scope() as db:
        known = {d.id: d.content_hash for d in db.scalars(select(Document).where(Document.status == "indexed"))}
        docs = [d for d in docs if known.get(doc_id_for(d.url)) != content_hash(d.markdown)]
        existing = db.scalar(select(func.count()).select_from(Chunk)) or 0
        keys = [embedding_key(index.embedder.name, t) for d in docs for t in embedding_inputs(d)]
        if existing + len(keys) > 24000: raise ValueError("Existing 24,000-passage capacity ceiling would be exceeded")
        if require_cache:
            for start in range(0, len(keys), 256):
                batch = keys[start:start + 256]
                if len(cached_vectors(db, batch, index.embedder.name, index.embedder.dim)) != len(set(batch)):
                    raise ValueError("Curriculum seed vectors are incomplete; import paused before changing sources")
    report = JobReport("curriculum")
    try:
        for doc in docs: upsert_document(index, doc, report)
    finally:
        index.persist(); index.reload()
    return {"documents": len(docs), "counts": report.counts, "index": index.stats}

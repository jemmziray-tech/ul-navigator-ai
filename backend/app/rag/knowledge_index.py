"""In-memory view of the knowledge base: FAISS vectors + BM25 + chunk metadata cache.

The SQL database is the source of truth for chunk text/metadata; FAISS holds vectors
keyed by chunk id. `reload()` rebuilds the BM25 index and metadata cache from the DB.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from functools import lru_cache

import numpy as np
from rank_bm25 import BM25Okapi
from sqlalchemy import select

from ..config import get_settings
from ..db import Chunk, Document, session_scope
from .embeddings import get_embedder
from .text import tokenize
from .vector_store import FaissStore

log = logging.getLogger(__name__)


@dataclass(slots=True)
class ChunkRecord:
    id: int
    document_id: str
    text: str
    section: str
    page: int | None
    category: str
    academic_year: str | None
    title: str
    url: str
    content_type: str
    collected_at: str


class KnowledgeIndex:
    def __init__(self):
        s = get_settings()
        self.embedder = get_embedder()
        self.store = FaissStore(s.index_dir, self.embedder.dim, self.embedder.name)
        self._lock = threading.RLock()
        self.records: dict[int, ChunkRecord] = {}
        self._bm25: BM25Okapi | None = None
        self._bm25_ids: list[int] = []
        self.reload()

    # ------------------------------------------------------------------ load
    def reload(self) -> None:
        with session_scope() as db:
            rows = db.execute(
                select(Chunk, Document.title, Document.url, Document.content_type,
                       Document.collected_at)
                .join(Document, Chunk.document_id == Document.id)
                .where(Document.status == "indexed")
            ).all()
        records: dict[int, ChunkRecord] = {}
        corpus: list[list[str]] = []
        ids: list[int] = []
        for ch, title, url, ctype, collected in rows:
            rec = ChunkRecord(ch.id, ch.document_id, ch.text, ch.section, ch.page, ch.category,
                              ch.academic_year, title, url, ctype,
                              collected.isoformat() if collected else "")
            records[ch.id] = rec
            toks = tokenize(f"{title} {ch.section} {ch.text}")
            corpus.append(toks or ["_empty_"])
            ids.append(ch.id)
        with self._lock:
            self.records = records
            self._bm25_ids = ids
            self._bm25 = BM25Okapi(corpus) if corpus else None
        log.info("knowledge index reloaded", extra={"extra_fields": {
            "chunks": len(records), "vectors": self.store.size}})

    # --------------------------------------------------------------- search
    def semantic_search(self, query: str, k: int) -> list[tuple[int, float]]:
        vec = self.embedder.encode([query], is_query=True)[0]
        return [(i, s) for i, s in self.store.search(vec, k) if i in self.records]

    def keyword_search(self, query: str, k: int) -> list[tuple[int, float]]:
        with self._lock:
            if self._bm25 is None:
                return []
            toks = tokenize(query)
            if not toks:
                return []
            scores = self._bm25.get_scores(toks)
            ids = self._bm25_ids
        if len(scores) == 0:
            return []
        top = np.argsort(-scores)[:k]
        return [(ids[i], float(scores[i])) for i in top if scores[i] > 0]

    # ----------------------------------------------------------------- write
    def add_vectors(self, ids: list[int], texts: list[str], db=None, use_cache: bool = True) -> None:
        from .embedding_cache import cached_vectors, embedding_key, save_vectors
        if db is None:
            with session_scope() as session:
                self.add_vectors(ids, texts, db=session, use_cache=use_cache)
            return
        bs = min(256, max(1, get_settings().embedding_batch_size) * 4)
        for start in range(0, len(ids), bs):
            batch_ids, batch_texts = ids[start:start + bs], texts[start:start + bs]
            keys = [embedding_key(self.embedder.name, text) for text in batch_texts]
            known = cached_vectors(db, keys, self.embedder.name, self.embedder.dim) if use_cache else {}
            missing = dict((key, text) for key, text in zip(keys, batch_texts) if key not in known)
            if missing:
                encoded = self.embedder.encode(list(missing.values()))
                fresh = dict(zip(missing, encoded))
                save_vectors(db, fresh, self.embedder.name, self.embedder.dim)
                known.update(fresh)
            self.store.add(batch_ids, np.stack([known[key] for key in keys]))

    def remove_vectors(self, ids: list[int]) -> int:
        return self.store.remove(ids)

    def persist(self) -> None:
        self.store.save()

    @property
    def stats(self) -> dict:
        return {"chunks": len(self.records), "vectors": self.store.size,
                "embedding_model": self.embedder.name, "device": self.embedder.device}


_index_lock = threading.Lock()


@lru_cache
def get_index() -> KnowledgeIndex:
    with _index_lock:
        return KnowledgeIndex()

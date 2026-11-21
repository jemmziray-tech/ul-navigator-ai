"""Hybrid retrieval: FAISS semantic + BM25 keyword -> Reciprocal Rank Fusion ->
metadata filtering/boosting -> de-duplication -> cross-encoder rerank -> relevance gate."""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..config import get_settings
from .knowledge_index import ChunkRecord, KnowledgeIndex
from .catalogue import directory_records
from .curricula import curriculum_records
from .reranker import get_reranker
from .text import content_hash, lexical_overlap
from .source_policy import source_role, policy_weight


@dataclass
class Hit:
    record: ChunkRecord
    rrf: float = 0.0
    semantic: float | None = None
    bm25: float | None = None
    semantic_rank: int | None = None
    bm25_rank: int | None = None
    rerank: float | None = None
    overlap: float = 0.0
    score: float = 0.0
    relevant: bool = False
    year_mismatch: bool = False
    directory_match: bool = False
    curriculum_match: bool = False
    module_match: bool = False
    source_role: str = "guidance"
    source_weight: float = 1.0
    policy_allowed: bool = True

    def to_debug(self) -> dict:
        return {"chunk_id": self.record.id, "title": self.record.title, "url": self.record.url,
                "section": self.record.section, "page": self.record.page,
                "rrf": round(self.rrf, 5), "semantic": _r(self.semantic), "bm25": _r(self.bm25),
                "rerank": _r(self.rerank), "score": round(self.score, 4),
                "relevant": self.relevant, "directory_match": self.directory_match,
                "curriculum_match": self.curriculum_match, "source_role": self.source_role, "source_weight": self.source_weight}


def _r(x):
    return None if x is None else round(x, 4)


@dataclass
class RetrievalResult:
    hits: list[Hit]
    candidates: int
    reranked: bool
    elapsed_ms: float
    filters: dict = field(default_factory=dict)

    @property
    def relevant_hits(self) -> list[Hit]:
        return [h for h in self.hits if h.relevant]

    @property
    def top_score(self) -> float | None:
        return self.hits[0].score if self.hits else None


def reciprocal_rank_fusion(rankings: list[list[int]], k: int = 60,
                           weights: list[float] | None = None) -> dict[int, float]:
    weights = weights or [1.0] * len(rankings)
    fused: dict[int, float] = {}
    for w, ranking in zip(weights, rankings):
        for rank, doc_id in enumerate(ranking):
            fused[doc_id] = fused.get(doc_id, 0.0) + w / (k + rank + 1)
    return fused


def retrieve(index: KnowledgeIndex, query: str, *, top_k: int | None = None,
             categories: list[str] | None = None, academic_year: str | None = None,
             year_is_explicit: bool = False, boost_categories: list[str] | None = None,
             module_codes: list[str] | None = None) -> RetrievalResult:
    s = get_settings()
    t0 = time.perf_counter()
    top_k = top_k or s.retrieval_top_k
    cand_k = s.retrieval_candidate_k

    sem = index.semantic_search(query, cand_k)
    kw = index.keyword_search(query, cand_k)
    if module_codes:  # exact module code lookups get an extra keyword pass
        kw_codes = index.keyword_search(" ".join(module_codes), cand_k)
        kw = kw + [x for x in kw_codes if x[0] not in {i for i, _ in kw}]

    fused = reciprocal_rank_fusion([[i for i, _ in sem], [i for i, _ in kw]], k=s.rrf_k)
    directories = {rec.id for rec in directory_records(index, query)}
    curriculum = {rec.id for rec in curriculum_records(index, query)}
    descriptors = {r.id for r in index.records.values() if module_codes
                   and r.url.startswith(("https://bookofmodules.ul.ie/", "https://www.bookofmodules.ul.ie/"))
                   and any(r.title.upper().startswith(c.upper() + " —") for c in module_codes)}
    for cid in descriptors:
        fused.setdefault(cid, 0.0)
    for cid in curriculum:
        fused.setdefault(cid, 0.0)
    for cid in directories:
        fused.setdefault(cid, 0.0)
    sem_map = {i: (sc, r) for r, (i, sc) in enumerate(sem)}
    kw_map = {i: (sc, r) for r, (i, sc) in enumerate(kw)}

    hits: list[Hit] = []
    for cid, rrf in fused.items():
        rec = index.records.get(cid)
        if rec is None:
            continue
        if categories and rec.category not in categories:
            continue  # hard metadata filter (explicit UI filter)
        h = Hit(record=rec, rrf=rrf, directory_match=cid in directories, curriculum_match=cid in curriculum, module_match=cid in descriptors)
        if cid in sem_map:
            h.semantic, h.semantic_rank = sem_map[cid]
        if cid in kw_map:
            h.bm25, h.bm25_rank = kw_map[cid]
        # soft metadata boosts
        if boost_categories and rec.category in boost_categories[:2]:
            h.rrf *= 1.15
        if academic_year and rec.academic_year:
            if rec.academic_year == academic_year:
                h.rrf *= 1.25 if year_is_explicit else 1.1
            else:
                h.year_mismatch = True
                h.rrf *= 0.75 if year_is_explicit else 0.9
        if module_codes and any(c.lower() in rec.text.lower().replace(" ", "")
                                for c in module_codes):
            h.rrf *= 1.4
        h.source_role = source_role(rec.url, rec.title)
        older = bool(academic_year and rec.academic_year and rec.academic_year < academic_year)
        h.source_weight, h.policy_allowed = policy_weight(
            query, h.source_role, h.year_mismatch and (year_is_explicit or older), year_is_explicit)
        h.rrf *= h.source_weight
        h.overlap = lexical_overlap(query, f"{rec.title} {rec.section} {rec.text}")
        hits.append(h)

    hits.sort(key=lambda h: (not h.curriculum_match, not h.module_match, not h.directory_match, -h.rrf))

    # de-duplicate near-identical passages and cap chunks per document
    seen_hashes: set[str] = set()
    per_doc: dict[str, int] = {}
    deduped: list[Hit] = []
    for h in hits:
        hsh = content_hash(h.record.text[:600])
        if hsh in seen_hashes:
            continue
        if per_doc.get(h.record.document_id, 0) >= s.max_chunks_per_document:
            continue
        seen_hashes.add(hsh)
        per_doc[h.record.document_id] = per_doc.get(h.record.document_id, 0) + 1
        deduped.append(h)

    pool = deduped[: s.reranker_top_n]
    reranker = get_reranker()
    reranked = False
    if reranker is not None and pool:
        probs = reranker.score(query, [f"{h.record.title}. {h.record.section}\n{h.record.text}"
                                       for h in pool])
        for h, p in zip(pool, probs):
            h.rerank = p
            h.score = p * h.source_weight
            h.relevant = p >= s.min_rerank_probability and h.policy_allowed
        pool.sort(key=lambda h: -h.score)
        reranked = True
    else:
        max_rrf = max((h.rrf for h in pool), default=1.0) or 1.0
        sem_thr = (s.hash_min_semantic_score if s.embedding_backend == "hash"
                   else s.min_semantic_score)
        for h in pool:
            h.score = h.rrf / max_rrf
            h.relevant = ((h.semantic or 0) >= sem_thr and h.overlap > 0) or (
                h.overlap >= s.min_lexical_overlap and (h.bm25 or 0) > 0)
            h.relevant = h.relevant and h.policy_allowed

    for h in pool:
        if (h.directory_match or h.curriculum_match or h.module_match) and h.policy_allowed and not (year_is_explicit and h.year_mismatch):
            h.relevant = True
    pool.sort(key=lambda h: (not h.relevant, not (h.curriculum_match and h.relevant), not (h.module_match and h.relevant), not (h.directory_match and h.relevant), -h.score))

    return RetrievalResult(
        hits=pool[:top_k], candidates=len(fused), reranked=reranked,
        elapsed_ms=(time.perf_counter() - t0) * 1000,
        filters={"categories": categories, "academic_year": academic_year,
                 "year_is_explicit": year_is_explicit})

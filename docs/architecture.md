# Architecture

## Components

| Layer | Location | Key modules |
|---|---|---|
| Ingestion | `ingestion/ul_ingest/` | `crawler.py` (polite fetcher, robots, scope), `extractors.py` (HTML/PDF/CSV/RTF → Markdown, boilerplate), `chunking.py` (adaptive heading-aware chunks), `pipeline.py` (incremental upsert, dedupe, jobs, reconcile), `scrapy_discovery.py` |
| Storage | `backend/app/db.py`, `data/` | SQLAlchemy models: `documents`, `chunks`, `ingestion_jobs`, `conversations`, `messages`, `feedback`, `query_logs`; FAISS `IndexIDMap2(IndexFlatIP)` keyed by chunk id |
| Retrieval | `backend/app/rag/` | `embeddings.py` (bge-small, CUDA/fp16 or CPU), `knowledge_index.py` (FAISS + BM25 + metadata cache), `retriever.py` (RRF, filters, dedupe, rerank, thresholds), `reranker.py` |
| Generation | `backend/app/rag/` | `classifier.py`, `prompts.py`, `llm.py` (Gemini with retries/fallback), `citations.py`, `pipeline.py` |
| API | `backend/app/api/` | `chat.py` (SSE + sync, conversations, feedback), `public.py` (health, stats, explorer, tools), `admin.py` |
| Web | `frontend/src/` | App Router pages: `/`, `/chat`, `/explorer`, `/tools`, `/admin` |

## Request flow (`POST /api/chat`)

1. **Validate** (length, client id, filters) and load or create the conversation.
2. **Classify:** category scores, module codes, academic year (explicit, "next/last year" or current), high-stakes flags, prompt-injection detection and stripping, smalltalk.
3. **Reformulate:** follow-ups are rewritten with Gemini (or a heuristic) using recent turns. Synonyms are expanded (QCA, IRP, CECD…).
4. **Hybrid retrieval:** top-40 FAISS and top-40 BM25 candidates, fused with Reciprocal Rank Fusion (k = 60).
5. **Metadata:** hard category filter (UI) plus soft boosts for the classified category, matching academic year and exact module codes. Mismatched years are penalised and flagged.
6. **Dedupe:** near-identical passages are dropped, with at most 3 chunks per document.
7. **Rerank:** cross-encoder probability over the top 30. Passages under `MIN_RERANK_PROBABILITY` are not used. Without the reranker, a cosine plus lexical-overlap gate applies.
8. **No relevant passages:** an "insufficient evidence" answer with the right official contact, and the question is logged as unanswered.
9. **Generate:** the context is fenced `<source id="S#">` blocks with instruction-like text neutralised. The system prompt requires source-only answers and `[S#]` citations. Tokens are streamed.
10. **Validate:** citation markers are checked against the retrieved set and renumbered; figures not found in the cited text are flagged; year-mismatch and high-stakes notices are added.
11. **Persist** the message and anonymous telemetry, and emit a `done` event with the validated answer, citations and follow-ups.

## Incremental indexing

`documents.id = sha1(url)`. On each crawl, `304 Not Modified` or an unchanged SHA-256 hash of the normalised Markdown leaves the document alone. A changed document has its old chunk vectors removed from FAISS by id and its new chunks embedded and added. Identical content at another URL is stored as `duplicate` and not indexed. `reconcile` repairs any drift between FAISS and the database.

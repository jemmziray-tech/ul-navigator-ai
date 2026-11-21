# Public UL website collection

Started 20 November 2026 from https://www.ul.ie/ and its sitemap inventory (17,929 URLs). Discovered public links, including PDFs, are added to the persistent queue. This is an ongoing crawl, not a claim of complete coverage.

## Scope and provenance

- Only public `www.ul.ie` / `ul.ie` pages and supported text documents. No authenticated services, parameterized search/authentication URLs, executable downloads, images, video, Office attachments or other hosts.
- Respects robots.txt; the official PDF download flag `?inline` is allowed because it carries no search/authentication parameters. Minimum three seconds between requests, with slower retries on rate limits. Each redirect is scoped before following it. Robots rules refresh hourly.
- Student-facing sections are prioritized before wider faculty, research, news and event pages. Historical pages remain dated sources rather than being relabelled as current.
- Compressed extracted text preserves original URL, final URL, title, collection time, HTTP status, raw content hash, ETag, Last-Modified, public links and PDF page markers where extraction provides them.
- Failed, unsupported, oversized, empty/scanned and thin pages are tracked. Scanned PDFs requiring OCR are not claimed as searchable text.

## Running and checking

From the project folder, run `UL_RESOURCE_CRAWL.ps1` to resume both workers. `UL_RESOURCE_PROGRESS.ps1` displays current counters. `UL_RESOURCE_PAUSE.ps1` pauses after the current request. Keep the computer awake and connected; no change to its power settings is made. Start the resume script again after a reboot. OS-held locks prevent duplicate worker processes. Limited, interactive Windows tasks named ULNavigator-Public-crawl and ULNavigator-Public-publish run independently of the launching terminal; no passwords or elevated task privileges are stored.

Queue: `data/site_archive/queue.sqlite3` (SQLite WAL). Extracted documents: `data/site_archive/documents/*.json.gz`. Progress: `crawl-status.json` / `publish-status.json`. Logs contain no passwords or tokens. Failures are available in the queue's `error` / `publish_error` columns. A crawl `complete` state means the queue has been attempted; check failure counts before reporting coverage.

The sitemap inventory is saved in `work/ul-sitemap-urls.json`. The collector follows public links beyond it. It does not dynamically execute JavaScript forms or crawl other UL services such as Brightspace, staff portals or the separate Book of Modules host.

## Live publication and limits

The separate publisher imports through the existing authenticated production upload endpoint, keyed by original URL. It leaves saved conversations, feedback, manual uploads and existing sources intact. Already indexed URLs are skipped rather than replaced. Tokens remain in memory and credentials are read from the local maintainer file, never passed as process arguments.

The initial rollout stops after 1,000 additional documents per run or 24,000 total live chunks, whichever comes first. This is a deliberate RAM/compute bound for the current single-instance 2 GiB Cloud Run service and €10 monthly budget. The full local collection continues independently. Very large documents (>200 chunks), pages too short for meaningful chunks, and API failures are reported separately. The publisher pauses after three consecutive API failures. No Gemini generation calls are used by collection/import.

**The full archive will not automatically become searchable once the live ceiling is reached.** Review coverage, retrieval quality, memory use and billing before expanding that ceiling. Full-site collection may take a day or longer at the polite request rate, and inaccessible content will remain excluded.

No new cloud resources or billing limits are introduced. Imports still consume the existing Cloud Run/storage allowance. The existing Google service caps remain in place; they are not instantaneous guarantees against all overages.

## Verification

Boundary tests cover public scope, excluded private/query/external URLs, persistent queue deduplication and failure reporting. Ingestion tests cover short main-content extraction and retaining public contact email addresses. The live source explorer and a fee-receipt chat query are used to verify the first imported sources.

## Restart fix (20 November 2026)

The first large import exposed a Cloud Run startup limit: rebuilding embeddings for 1,726 added passages exceeded the four-minute startup window. Embeddings now have a content-addressed database cache keyed by the model and exact input text, independent of chunk IDs. The cache is replicated with the source database. Startup rebuilds FAISS from cached vectors; only genuinely missing vectors need computation. A locally prepared public-source-only seed cache bootstraps the existing live database without replacing its chats or records. Corrupt, incompatible or wrong-model cache entries are ignored and recomputed. An explicit reindex still forces new computation.

The full suite passes 104 tests for the cache rollout, plus a subsequent PDF-link boundary regression check. Windows test invocations preload FAISS before pytest capture to avoid a native DLL initialization issue; this changes test startup only, not application behavior. Offline Linux validation additionally checks actual ingestion and restoration without embedding calls.

The initial strict query exclusion omitted UL's public `download?inline` document links. The corrected local worker preserves this single flag, while continuing to reject parameterized queries. A versioned backfill refreshes earlier pages to discover those documents. Existing extracted payloads stay available for publication during the backfill; `collected_documents` counts all saved payloads, while `ready` counts the current pass.

Live cache rollout: revision `ul-navigator-api-00002-hfw`, image digest `sha256:d4761bfa95da0420761d3a2fe7d257a6dada509ca79a6ced4826545e49b0c569`. Thirty-source offline Linux import/restore test completed in 10.1 seconds with zero encoding calls. Production startup passed its TCP check and resumed ingestion with 8,397 searchable vectors; a fee-receipt chat answer cited newly indexed official fee and visa pages.

# Security & reliability

| Concern | Implementation |
|---|---|
| Secrets | Loaded from env (`pydantic-settings`, `SecretStr`); never logged (log formatter masks secret-like keys); `.env.example` has placeholders only; `.env`, `data/` git-ignored |
| Admin auth | bcrypt (`ADMIN_PASSWORD_HASH`), HS256 JWT with expiry (`JWT_SECRET` ≥ 32 chars). Admin endpoints return 503 until configured. Login limited to 5/min; failed logins logged |
| Rate limiting | Shared configurable generated-answer limit (example: 3/min), separate outer chat limit of 20/min, configurable login/default limits; configure trusted proxy headers only behind a trusted proxy |
| Input validation | Pydantic schemas: question length ≤ 2000, client-id pattern, academic-year format, category allow-lists; 422 responses never echo internals |
| Uploads | Extension allow-list, size cap, PDF magic bytes, reject PDFs containing `/JavaScript`/`/Launch`, RTF signature, UTF-8 + no NUL bytes for text, CSV header parse, sanitised filenames |
| CORS & headers | Explicit origin allow-list; `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy` on API and web; `Permissions-Policy` on web |
| Prompt injection | Regex detection and stripping of injection phrases in questions; pure-injection prompts are refused; instruction-like text in sources is neutralised; system prompt treats sources and conversation as data; server-side citation validation |
| Hallucination guards | Relevance gate before generation; insufficient-evidence answers; invalid citation removal; unverified-figure flags; year-mismatch and high-stakes notices |
| Privacy | Anonymous random browser ID; no accounts or IP storage; conversation storage can be disabled; daily retention purge (`RETENTION_DAYS`) |
| Reliability | Gemini timeouts, retries with exponential backoff (pre-first-token), fallback model, extractive fallback on failure; `/health` and `/health/ready`; structured JSON logs with request IDs; optional Sentry |

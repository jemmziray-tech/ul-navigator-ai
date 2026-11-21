"""Central configuration for UL Navigator AI.

All settings come from environment variables (or a local `.env` file).
Secrets are typed as SecretStr so they are never printed in logs or reprs.
"""
from __future__ import annotations

from datetime import date
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(str(REPO_ROOT / ".env"), ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- General -----------------------------------------------------------
    app_name: str = "UL Navigator AI"
    app_env: Literal["development", "test", "production"] = "development"
    log_level: str = "INFO"
    log_json: bool = True
    data_dir: Path = REPO_ROOT / "data"
    database_url: str = ""  # default: sqlite file inside data_dir
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    sentry_dsn: SecretStr | None = None

    # ---- Gemini ------------------------------------------------------------
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.8-flash"
    gemini_fallback_model: str = "gemini-3.1-flash-lite"
    gemini_temperature: float = 0.2
    gemini_max_output_tokens: int = 1400
    gemini_timeout_s: int = 45
    gemini_max_retries: int = 3
    use_llm_query_rewrite: bool = True

    # ---- Embeddings / reranking -------------------------------------------
    embedding_backend: Literal["sentence-transformers", "hash"] = "sentence-transformers"
    embedding_model: str = "BAAI/bge-small-en-v1.5"
    embedding_device: Literal["auto", "cuda", "cpu"] = "auto"
    embedding_batch_size: int = 64
    embedding_query_instruction: str = "Represent this sentence for searching relevant passages: "
    reranker_enabled: bool = True
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    reranker_top_n: int = 30
    model_cache_dir: Path | None = None

    # ---- Chunking ----------------------------------------------------------
    chunk_size_words: int = 260
    chunk_overlap_words: int = 50
    chunk_min_words: int = 40

    # ---- Retrieval ---------------------------------------------------------
    retrieval_candidate_k: int = 40
    retrieval_top_k: int = 6
    rrf_k: int = 60
    max_chunks_per_document: int = 3
    min_semantic_score: float = 0.50  # cosine, used when reranker disabled
    min_rerank_probability: float = 0.12
    hash_min_semantic_score: float = 0.10
    min_lexical_overlap: float = 0.5
    history_turns: int = 6

    # ---- Crawling ----------------------------------------------------------
    crawl_user_agent: str = (
        "ULNavigatorAI/1.0 (independent student project; respectful crawler; "
        "+https://github.com/)"
    )
    crawl_delay_s: float = 3.0
    crawl_cache_ttl_hours: float = 12.0
    crawl_max_pages: int = 150
    crawl_max_depth: int = 2
    crawl_timeout_s: float = 30.0
    crawl_max_retries: int = 3
    crawl_max_pdf_mb: int = 60
    crawl_use_playwright: bool = False

    # ---- Security ----------------------------------------------------------
    admin_username: str = "admin"
    admin_password_hash: SecretStr | None = None  # bcrypt hash
    jwt_secret: SecretStr | None = None
    jwt_expiry_minutes: int = 480
    rate_limit_chat: str = "20/minute"
    rate_limit_default: str = "120/minute"
    rate_limit_login: str = "5/minute"
    max_upload_mb: int = 25
    max_question_chars: int = 2000
    trust_proxy_headers: bool = False

    # ---- Privacy -----------------------------------------------------------
    retention_days: int = 90
    store_conversations: bool = True

    # ---- Calendar ----------------------------------------------------------
    academic_year_start_month: int = Field(default=8, ge=1, le=12)

    @field_validator("data_dir", mode="before")
    @classmethod
    def _resolve_data_dir(cls, v):
        p = Path(v)
        return p if p.is_absolute() else (REPO_ROOT / p)

    # ---- Derived paths -----------------------------------------------------
    @property
    def sqlalchemy_url(self) -> str:
        if self.database_url:
            url = self.database_url
            if url.startswith("postgres://"):  # Render style
                url = url.replace("postgres://", "postgresql+psycopg://", 1)
            elif url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+psycopg://", 1)
            return url
        return f"sqlite:///{(self.data_dir / 'ul_navigator.db').as_posix()}"

    @property
    def index_dir(self) -> Path:
        return self.data_dir / "index"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def logs_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def reports_dir(self) -> Path:
        return self.data_dir / "reports"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def gemini_enabled(self) -> bool:
        key = self.gemini_api_key.get_secret_value().strip() if self.gemini_api_key else ""
        return bool(key) and not key.startswith("your-")  # ignore the .env.example placeholder

    def current_academic_year(self, today: date | None = None) -> str:
        today = today or date.today()
        start = today.year if today.month >= self.academic_year_start_month else today.year - 1
        return f"{start}/{str(start + 1)[-2:]}"

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.index_dir, self.raw_dir, self.uploads_dir,
                  self.logs_dir, self.reports_dir):
            d.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    s = Settings()
    s.ensure_dirs()
    return s

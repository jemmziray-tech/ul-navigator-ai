"""Shared fixtures.

IMPORTANT: the fixture corpus describes a FICTIONAL institution ("Northbridge Test
University"). It exists only to exercise the pipeline deterministically and offline. It is
never mixed with, or presented as, University of Limerick data.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "ingestion"), str(ROOT / "tests" / "fixtures")]

from synthetic_corpus import *  # noqa: F401,F403
from synthetic_corpus import CORPUS, MODULES_CSV, make_handbook_pdf


@pytest.fixture(scope="session", autouse=True)
def _env(tmp_path_factory):
    data = tmp_path_factory.mktemp("data")
    os.environ.update({
        "APP_ENV": "test", "DATA_DIR": str(data), "EMBEDDING_BACKEND": "hash",
        "GEMINI_API_KEY": "", "RERANKER_ENABLED": "false", "LOG_JSON": "false",
        "ADMIN_USERNAME": "admin", "JWT_SECRET": "x" * 48, "RATE_LIMIT_CHAT": "1000/minute",
        "RATE_LIMIT_DEFAULT": "5000/minute", "DATABASE_URL": "",
        "CORS_ORIGINS": "http://localhost:3000",
    })
    from app.security import hash_password
    os.environ["ADMIN_PASSWORD_HASH"] = hash_password("correct-horse-battery")
    yield data


def _clear_caches():
    from app.config import get_settings
    from app.db import get_engine, get_sessionmaker
    from app.rag.embeddings import get_embedder
    from app.rag.knowledge_index import get_index
    from app.rag.llm import get_llm
    from app.rag.reranker import get_reranker
    for f in (get_settings, get_engine, get_sessionmaker, get_embedder, get_index, get_llm,
              get_reranker):
        f.cache_clear()


@pytest.fixture()
def fresh_env(tmp_path, monkeypatch):
    """Isolated data dir + empty DB/index for a single test."""
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    _clear_caches()
    from app.db import init_db
    init_db()
    yield tmp_path
    _clear_caches()


@pytest.fixture()
def loaded_index(fresh_env):
    """Ingest the synthetic corpus and return the knowledge index."""
    from ul_ingest.extractors import extract, find_boilerplate_lines, remove_boilerplate
    from ul_ingest.pipeline import DocInput, JobReport, ingest_bytes, upsert_document

    from app.rag.knowledge_index import get_index

    index = get_index()
    report = JobReport("test")
    extracted = {url: extract(kind, body.encode(), url) for url, (kind, _, body) in CORPUS.items()}
    boiler = find_boilerplate_lines([e.markdown for e in extracted.values()], min_docs=3)
    for url, (kind, cat, _) in CORPUS.items():
        ex = extracted[url]
        upsert_document(index, DocInput(url=url, kind=kind, title=ex.title,
                                        markdown=remove_boilerplate(ex.markdown, boiler),
                                        category=cat), report)
    pdf = fresh_env / "handbook.pdf"
    make_handbook_pdf(pdf)
    ingest_bytes(pdf.read_bytes(), "handbook.pdf", category="regulations",
                 source_url="https://test.northbridge.example/handbook.pdf", index=index)
    ingest_bytes(MODULES_CSV.encode(), "modules.csv", category="modules",
                 source_url="https://test.northbridge.example/modules.csv", index=index)
    index.persist()
    index.reload()
    assert report.counts["failed"] == 0, report.failures
    return index

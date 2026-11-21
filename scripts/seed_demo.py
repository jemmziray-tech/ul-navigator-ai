"""Seed an OFFLINE DEMO knowledge base from the synthetic test corpus.

This lets you click through the UI without internet access. The content describes a
fictional institution ("Northbridge Test University") and must never be presented as UL
information. Use a separate data directory so it can't mix with the real index:

    DATA_DIR=data_demo EMBEDDING_BACKEND=hash python scripts/seed_demo.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "backend"), str(ROOT / "ingestion"), str(ROOT / "tests" / "fixtures")]

if "demo" not in os.environ.get("DATA_DIR", ""):
    sys.exit("Refusing to run: set DATA_DIR to a demo directory (e.g. DATA_DIR=data_demo).")

from app.db import init_db  # noqa: E402
from app.rag.knowledge_index import get_index  # noqa: E402
from synthetic_corpus import CORPUS, MODULES_CSV, make_handbook_pdf  # noqa: E402
from ul_ingest.extractors import extract, find_boilerplate_lines, remove_boilerplate  # noqa: E402
from ul_ingest.pipeline import DocInput, JobReport, ingest_bytes, upsert_document  # noqa: E402

init_db()
index = get_index()
report = JobReport("demo")
ex = {u: extract(k, b.encode(), u) for u, (k, _, b) in CORPUS.items()}
bp = find_boilerplate_lines([e.markdown for e in ex.values()], min_docs=3)
for url, (kind, cat, _) in CORPUS.items():
    upsert_document(index, DocInput(url, kind, ex[url].title,
                                    remove_boilerplate(ex[url].markdown, bp), cat), report)
pdf = Path(os.environ["DATA_DIR"]) / "demo_handbook.pdf"
pdf.parent.mkdir(parents=True, exist_ok=True)
make_handbook_pdf(pdf)
ingest_bytes(pdf.read_bytes(), "handbook.pdf", category="regulations",
             source_url="https://test.northbridge.example/handbook.pdf", index=index)
ingest_bytes(MODULES_CSV.encode(), "modules.csv", category="modules",
             source_url="https://test.northbridge.example/modules.csv", index=index)
index.persist()
index.reload()
print({"demo_documents": 7, **index.stats})

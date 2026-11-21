"""Command line interface for the UL Navigator AI ingestion pipeline.

    python -m ul_ingest crawl                 # crawl seeds + discovery, incremental
    python -m ul_ingest crawl --seeds-only    # just the seed URLs
    python -m ul_ingest ingest-file path.pdf --category modules --year 2026/27
    python -m ul_ingest ingest-dir ./my_exports --category modules
    python -m ul_ingest reconcile             # repair FAISS <-> DB drift
    python -m ul_ingest reindex               # re-embed everything (model change)
    python -m ul_ingest delete <doc-id|url>
    python -m ul_ingest stats
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.config import get_settings
from app.db import Chunk, Document, IngestionJob, count, init_db, session_scope
from app.logging_conf import setup_logging

from . import pipeline


def main(argv: list[str] | None = None) -> int:
    s = get_settings()
    setup_logging(s.log_level, s.log_json, s.logs_dir / "ingestion.log")
    init_db()
    ap = argparse.ArgumentParser(prog="ul_ingest")
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("crawl")
    c.add_argument("--max-pages", type=int)
    c.add_argument("--max-depth", type=int)
    c.add_argument("--seeds-only", action="store_true")
    c.add_argument("--offline", action="store_true", help="use cached raw files only")
    c.add_argument("--urls-file", type=Path, help="extra URLs (one per line), e.g. from Scrapy")
    f = sub.add_parser("ingest-file")
    f.add_argument("path", type=Path)
    f.add_argument("--category", default="general")
    f.add_argument("--title", default="")
    f.add_argument("--year")
    f.add_argument("--source-url")
    d = sub.add_parser("ingest-dir")
    d.add_argument("path", type=Path)
    d.add_argument("--category", default="general")
    d.add_argument("--year")
    sub.add_parser("reconcile")
    sub.add_parser("reindex")
    sub.add_parser("duplicates")
    x = sub.add_parser("delete")
    x.add_argument("target")
    sub.add_parser("stats")
    a = ap.parse_args(argv)

    if a.cmd == "crawl":
        extra = None
        if a.urls_file:
            extra = [u.strip() for u in a.urls_file.read_text().splitlines() if u.strip()]
        out = pipeline.crawl(a.max_pages, a.max_depth, a.offline, a.seeds_only, extra)
        summary = {k: v for k, v in out.items() if k != "failures"}
        print(json.dumps(summary, indent=2))
        if out["failures"]:
            print(f"\n{len(out['failures'])} failure(s). Full report: {out['report']}")
            for fl in out["failures"][:15]:
                print(f"  - [{fl['stage']}] {fl['url']}: {fl['error']}")
    elif a.cmd == "ingest-file":
        out = pipeline.ingest_bytes(a.path.read_bytes(), a.path.name, category=a.category,
                                    title=a.title, source_url=a.source_url, academic_year=a.year)
        print(json.dumps(out, indent=2))
    elif a.cmd == "ingest-dir":
        for p in sorted(a.path.iterdir()):
            if p.suffix.lower() in pipeline.KIND_BY_EXT:
                out = pipeline.ingest_bytes(p.read_bytes(), p.name, category=a.category,
                                            academic_year=a.year)
                print(f"{p.name}: {out['status']}")
    elif a.cmd == "reconcile":
        print(json.dumps(pipeline.reconcile(), indent=2))
    elif a.cmd == "reindex":
        print(json.dumps(pipeline.reindex_all(), indent=2))
    elif a.cmd == "duplicates":
        print(json.dumps(pipeline.find_duplicates(), indent=2))
    elif a.cmd == "delete":
        print("deleted" if pipeline.delete_document(a.target) else "not found")
    elif a.cmd == "stats":
        with session_scope() as db:
            print(json.dumps({"documents": count(db, Document), "chunks": count(db, Chunk),
                              "jobs": count(db, IngestionJob)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())

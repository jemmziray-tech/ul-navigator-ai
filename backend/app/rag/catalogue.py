"""Recognise broad course browsing requests and select official directory sources."""
from urllib.parse import urlparse

from .text import tokenize

DIRECTORIES = {
    "/study/undergraduate/alphabetical-list-of-courses": "undergraduate",
    "/study/postgraduate/taught-programmes/alphabetical-list": "postgraduate",
    "/study/postgraduate/professional-flexible/alphabetical-list": "professional",
    "/research/doctoral-college/postgraduate-research-programmes": "research",
}


def directory_scope(query: str) -> set[str]:
    words = set(tokenize(query))
    if not words & {"course", "courses", "programme", "programmes", "program", "programs", "degrees"}:
        return set()
    # Subject names and application/fee questions must retain normal retrieval.
    generic = set("course courses programme programmes program programs degree degrees offer offers "
                  "offered available list all browse catalogue catalog directory study studies "
                  "undergraduate postgraduate taught professional flexible research doctoral "
                  "masters master bachelor bachelors full part time options show find "
                  "currently university college".split())
    if words - generic:
        return set()
    if words & {"undergraduate", "bachelor", "bachelors"}:
        return {"undergraduate"}
    if words & {"research", "doctoral"}:
        return {"research"}
    if words & {"professional", "flexible", "part"}:
        return {"professional"}
    if words & {"postgraduate", "masters", "master", "taught"}:
        return {"postgraduate", "professional", "research"}
    return set(DIRECTORIES.values())


def directory_records(index, query: str):
    scope = directory_scope(query)
    found = {}
    for record in index.records.values() if scope else []:
        parsed = urlparse(record.url)
        path = parsed.path.rstrip("/")
        if parsed.hostname not in {"www.ul.ie", "ul.ie"} or DIRECTORIES.get(path) not in scope:
            continue
        # One representative passage per directory; link to the full original list.
        if path not in found or record.id < found[path].id:
            found[path] = record
    return list(found.values())

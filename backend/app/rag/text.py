"""Shared text utilities: tokenisation, normalisation, hashing, academic-year parsing."""
from __future__ import annotations

import hashlib
import re
import unicodedata

STOPWORDS = frozenset("""
a an and are as at be been but by can could do does for from had has have how i if in
into is it its me my of on or our so than that the their them then there these they this
to was we were what when where which who why will with would you your about am any also
ul university limerick please tell know need get much many
""".split())

_TOKEN_RE = re.compile(r"[a-z0-9]+(?:[/.'-][a-z0-9]+)*")
MODULE_CODE_RE = re.compile(r"\b([A-Z]{2,3})\s?(\d{4})\b")
YEAR_RE = re.compile(r"\b(20\d{2})\s*[/\-–]\s*(20\d{2}|\d{2})\b")


def normalize_ws(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).replace(" ", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def tokenize(text: str, keep_stopwords: bool = False) -> list[str]:
    toks = _TOKEN_RE.findall(text.lower())
    if keep_stopwords:
        return toks
    return [t for t in toks if t not in STOPWORDS and len(t) > 1]


def content_hash(text: str) -> str:
    norm = re.sub(r"\s+", " ", text.lower()).strip()
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def doc_id_for(url: str) -> str:
    return hashlib.sha1(url.strip().encode("utf-8")).hexdigest()


def normalize_year(match: re.Match) -> str | None:
    start = int(match.group(1))
    end = match.group(2)
    end_i = int(end) if len(end) == 4 else int(str(start)[:2] + end)
    if end_i != start + 1:
        return None
    return f"{start}/{str(end_i)[-2:]}"


def find_academic_years(text: str) -> list[str]:
    years = []
    for m in YEAR_RE.finditer(text):
        y = normalize_year(m)
        if y:
            years.append(y)
    return years


def dominant_academic_year(*texts: str) -> str | None:
    counts: dict[str, int] = {}
    for t in texts:
        for y in find_academic_years(t or ""):
            counts[y] = counts.get(y, 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda kv: (kv[1], kv[0]))[0]


def lexical_overlap(query: str, text: str) -> float:
    q = set(tokenize(query))
    if not q:
        return 0.0
    t = set(tokenize(text))
    return len(q & t) / len(q)

"""Citation building and validation.

Guarantees: every citation marker in the final answer refers to a source that was actually
retrieved for this request; markers pointing anywhere else are removed and reported.
Also flags figures (money, dates, percentages, QCA values) that cannot be found in the
cited source text - a cheap hallucination guard."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

_MARKER_GROUP_RE = re.compile(r"\[(S\d+(?:\s*,\s*S?\d+)*)\]")
_MARKER_RE = re.compile(r"\[S(\d+)\]")
_FIGURE_RE = re.compile(
    r"(€\s?\d[\d,]*(?:\.\d+)?|\d[\d,]*(?:\.\d+)?\s?(?:%|percent|euro|EUR)|"
    r"\b\d{1,2}(?:st|nd|rd|th)?\s+(?:January|February|March|April|May|June|July|August|"
    r"September|October|November|December)\b|\b\d\.\d{1,2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b)",
    re.IGNORECASE)


def make_citation(idx: int, hit, excerpt_chars: int = 320) -> dict:
    r = hit.record
    text = re.sub(r"\s+", " ", r.text).strip()
    excerpt = text[:excerpt_chars] + ("…" if len(text) > excerpt_chars else "")
    return {
        "id": f"S{idx}", "chunk_id": r.id, "document_id": r.document_id, "title": r.title,
        "url": r.url, "section": r.section or None, "page": r.page, "excerpt": excerpt,
        "academic_year": r.academic_year, "category": r.category,
        "retrieved_at": r.collected_at, "content_type": r.content_type,
        "score": round(hit.score, 4),
    }


@dataclass
class ValidationResult:
    content: str
    citations: list[dict]
    invalid_markers: list[str] = field(default_factory=list)
    unverified_figures: list[str] = field(default_factory=list)
    has_citations: bool = False


def _expand_groups(text: str) -> str:
    def repl(m: re.Match) -> str:
        ids = [p.strip().lstrip("S") for p in m.group(1).split(",")]
        return "".join(f"[S{i}]" for i in ids if i.isdigit())
    return _MARKER_GROUP_RE.sub(repl, text)


def _norm_fig(s: str) -> str:
    return re.sub(r"[\s,€]", "", s.lower()).replace("percent", "%").replace("euro", "")


def validate(answer: str, sources: list[dict]) -> ValidationResult:
    text = _expand_groups(answer)
    valid = {s["id"]: s for s in sources}
    invalid: list[str] = []
    order: list[str] = []

    def check(m: re.Match) -> str:
        sid = f"S{m.group(1)}"
        if sid not in valid:
            invalid.append(sid)
            return ""
        if sid not in order:
            order.append(sid)
        return m.group(0)

    text = _MARKER_RE.sub(check, text)
    # renumber used sources sequentially: S3,S1 -> S1,S2
    remap = {old: f"S{i}" for i, old in enumerate(order, start=1)}
    text = _MARKER_RE.sub(lambda m: f"[{remap[f'S{m.group(1)}']}]", text)
    text = re.sub(r"(\[S\d+\])(?:\1)+", r"\1", text)  # collapse duplicates
    text = re.sub(r"[ \t]+([.,;:])", r"\1", text)
    citations = []
    for old in order:
        c = dict(valid[old])
        c["id"] = remap[old]
        citations.append(c)

    cited_text = " ".join(valid[o].get("_full_text", valid[o]["excerpt"]) for o in order)
    norm_cited = _norm_fig(cited_text)
    unverified = []
    for fig in {m.group(0).strip() for m in _FIGURE_RE.finditer(text)}:
        if _norm_fig(fig) and _norm_fig(fig) not in norm_cited:
            unverified.append(fig)
    for c in citations:
        c.pop("_full_text", None)
    return ValidationResult(text.strip(), citations, invalid, sorted(unverified),
                            bool(citations))

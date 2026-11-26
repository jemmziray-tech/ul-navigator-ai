"""End-to-end RAG pipeline.

question -> classification -> reformulation -> hybrid retrieval -> metadata filtering ->
rerank -> context construction -> Gemini generation (streamed) -> citation validation ->
final answer.  Emits events so the API can stream them as Server-Sent Events.
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from typing import Iterator

from ..config import get_settings
from . import prompts
from .clarification import clarify
from .citations import make_citation, validate
from .exam_schedule import exam_timing, module_exam_guidance
from .classifier import (OFFICIAL_CONTACTS, SWAHILI_SMALLTALK_RE, QueryAnalysis, analyse, expand_query,
                         heuristic_rewrite)
from .knowledge_index import KnowledgeIndex, get_index
from .llm import LLMUnavailable, get_llm
from .retriever import Hit, retrieve
from .text import tokenize

log = logging.getLogger(__name__)

SMALLTALK_ANSWER = (
    "Hi! I'm **UL Navigator AI**, an independent assistant for University of "
    "Limerick information. I answer from official UL web pages and documents and show you the "
    "source for every fact.\n\nYou can ask me about **QCA and grading, registration, "
    "accommodation, fees, scholarships, international student requirements, academic calendars, "
    "modules, the library and student supports**.")

SWAHILI_SMALLTALK_ANSWER = (
    "Habari! Karibu **UL Navigator AI**. Ninaweza kukusaidia kupata taarifa kuhusu "
    "University of Limerick, kama ada, malazi, masomo na kalenda ya chuo. "
    "Una swali gani?\n\n"
    "Hii ni huduma huru ya taarifa, si huduma rasmi ya chuo.")

INJECTION_ANSWER = (
    "I can't follow instructions that try to change how I work or reveal internal settings. "
    "I'm happy to help with questions about the University of Limerick, for example fees, "
    "accommodation, QCA rules or academic calendars.")

FOLLOWUP_TEMPLATES = {
    "qca_grading": ["How is QCA calculated?", "What QCA do I need for a first class honours?",
                    "What happens if I fail a module?"],
    "accommodation": ["How do I apply for on-campus accommodation?",
                      "How are accommodation fees paid?", "What supports exist for off-campus housing?"],
    "international": ["What should I do before I arrive at UL?",
                      "How do I register with immigration after arriving?",
                      "Do international students need medical insurance?"],
    "fees": ["When are fees due?", "Can fees be paid in instalments?",
             "What is the student contribution charge?"],
    "scholarships": ["What undergraduate scholarships are available?",
                     "How do I apply for a scholarship?", "Are there sports scholarships?"],
    "calendar": ["When does the autumn semester start?", "When are the end-of-semester exams?",
                 "When is reading week?"],
    "modules": ["How many credits is a typical module?", "Where can I find module descriptors?",
                "How do I choose electives?"],
    "library": ["What are the library opening hours?", "How do I book a study room?",
                "How many books can I borrow?"],
    "student_support": ["How do I access counselling at UL?", "What disability supports exist?",
                        "Where can I get academic writing help?"],
    "careers": ["What is Cooperative Education at UL?", "How does CECD help with CVs?",
                "When does co-op placement happen?"],
    "registration": ["How do I register as a new student?", "What happens at orientation?",
                     "How do I get my student ID card?"],
    "campus": ["Where can I find a campus map?", "How do UL room numbers work?",
               "Where is the library on campus?"],
    "undergraduate": ["What undergraduate courses does UL offer?",
                      "What are the entry requirements?", "How do I apply through the CAO?"],
}


@dataclass
class PipelineResult:
    answer: str
    citations: list[dict]
    sources: list[dict]
    analysis: QueryAnalysis
    retrieval_query: str
    mode: str
    answered: bool
    follow_ups: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    retrieval_ms: float = 0.0
    total_ms: float = 0.0
    top_score: float | None = None
    debug: list[dict] = field(default_factory=list)
    clarification: dict | None = None


def _contact_line(category: str) -> str:
    name, url = OFFICIAL_CONTACTS.get(category, OFFICIAL_CONTACTS["general"])
    return f"[{name}]({url})"


def insufficient_answer(a: QueryAnalysis) -> str:
    return ("I couldn't find reliable information about this in the official UL sources I have "
            "indexed, so I won't guess.\n\n"
            f"For an authoritative answer, please check with {_contact_line(a.category)}. "
            "You could also try rephrasing your question with more detail (for example the "
            "programme, module code or academic year).")


def verification_note(a: QueryAnalysis) -> str:
    return (f"\n\n> **Please verify:** this is a high-stakes topic. Always confirm the current "
            f"rules with {_contact_line(a.category)} before acting on it.")


def _follow_ups(a: QueryAnalysis, hits: list[Hit], question: str) -> list[str]:
    out: list[str] = []
    qlow = question.lower().strip(" ?")
    for t in FOLLOWUP_TEMPLATES.get(a.category, []):
        if t.lower().strip(" ?") != qlow:
            out.append(t)
    seen = {o.lower() for o in out}
    for h in hits:
        sec = (h.record.section or "").split(">")[-1].strip()
        if 3 <= len(sec) <= 70 and not re.search(r"\d{3,}", sec):
            q = f"Tell me more about {sec[0].lower() + sec[1:]}"
            if q.lower() not in seen:
                out.append(q)
                seen.add(q.lower())
    return out[:3]


def _best_sentences(text: str, query: str, max_words: int = 70) -> str:
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)  # re-join wrapped lines
    sents = re.split(r"(?<=[.!?])\s+|\n{2,}", text)
    q = set(tokenize(query))
    scored = sorted(enumerate(sents), key=lambda p: -len(q & set(tokenize(p[1]))))
    keep = sorted(i for i, _ in scored[:3])
    out = " ".join(sents[i].strip() for i in keep if sents[i].strip())
    words = out.split()
    return " ".join(words[:max_words]) + ("…" if len(words) > max_words else "")


def extractive_answer(hits: list[Hit], query: str, unavailable: bool = False, verification_failed: bool = False) -> str:
    notice = ("_Generative answers are temporarily unavailable, so here are the most relevant "
              "passages from official UL sources:_" if unavailable else
              "_Generative answers are switched off (no Gemini API key configured), so here are "
              "the most relevant passages from official UL sources:_")
    if verification_failed:
        notice = "_I couldn't verify the generated details, so here are relevant passages from official UL sources:_"
    lines = [notice, ""]
    for i, h in enumerate(hits[:3], start=1):
        label = h.record.title + (f" — {h.record.section}" if h.record.section else "")
        lines.append(f"**{label}** [S{i}]")
        lines.append(f"> {_best_sentences(h.record.text, query)}")
        lines.append("")
    return "\n".join(lines).strip()


def _rewrite(question: str, history: list[dict], a: QueryAnalysis) -> str:
    base = a.sanitized_query or question
    if not a.is_follow_up:
        return base
    s = get_settings()
    llm = get_llm()
    if llm is not None and s.use_llm_query_rewrite:
        try:
            out = llm.complete(prompts.build_rewrite_prompt(
                base, prompts.build_history(history, s.history_turns)), prompts.REWRITE_SYSTEM,
                max_tokens=80)
            out = out.strip().strip('"').splitlines()[0] if out else ""
            if 3 <= len(out.split()) <= 40:
                return out
        except LLMUnavailable as exc:
            log.warning("query rewrite failed", extra={"extra_fields": {"error": str(exc)}})
    return heuristic_rewrite(base, history)


def run_stream(question: str, history: list[dict] | None = None,
               categories: list[str] | None = None, academic_year: str | None = None,
               index: KnowledgeIndex | None = None) -> Iterator[dict]:
    """Yields events: status, sources, token, done. The final `done` event carries the
    validated answer, which supersedes any streamed tokens."""
    t0 = time.perf_counter()
    s = get_settings()
    history = history or []
    question = question.strip()[: s.max_question_chars]
    a = analyse(question, has_history=bool(history))
    if academic_year:
        a.academic_year, a.year_is_explicit = academic_year, True

    def done(answer: str, citations: list[dict], sources: list[dict], mode: str,
             answered: bool, retrieval_query: str = "", follow_ups: list[str] | None = None,
             flags: list[str] | None = None, retrieval_ms: float = 0.0,
             top_score: float | None = None, debug: list | None = None, clarification: dict | None = None) -> dict:
        res = PipelineResult(answer, citations, sources, a, retrieval_query, mode, answered,
                             follow_ups or [], sorted(set(a.flags + (flags or []))),
                             retrieval_ms, (time.perf_counter() - t0) * 1000, top_score,
                             debug or [], clarification)
        return {"type": "done", "result": res}

    yield {"type": "status", "stage": "classifying", "category": a.category,
           "high_stakes": a.high_stakes, "academic_year": a.academic_year}

    if a.intent == "empty":
        yield done("Please type a question.", [], [], "system", False)
        return
    if a.intent == "smalltalk":
        yield done(SWAHILI_SMALLTALK_ANSWER if SWAHILI_SMALLTALK_RE.fullmatch(question)
                   else SMALLTALK_ANSWER, [], [], "system", True,
                   follow_ups=["How is QCA calculated?", "How do I apply for accommodation?",
                               "What scholarships are available?"])
        return
    if a.intent == "injection":
        yield done(INJECTION_ANSWER, [], [], "refusal", True)
        return
    if a.intent == "social":
        yield done("I can help you explore student societies, campus events and ways to meet people, "
                   "but I can't find a partner for you. What interests would you like to share with others?",
                   [], [], "system", True, follow_ups=["What student societies are available?",
                                                      "Where can I find student events?"])
        return

    clarified = clarify(question, history, academic_year)
    if clarified.state:
        a = analyse(clarified.question)
        yield done(clarified.answer, [], [], "clarification", False,
                   follow_ups=clarified.choices, flags=["clarification_required"],
                   clarification=clarified.state)
        return
    if clarified.question != question:
        question = clarified.question
        a = analyse(question)
        a.is_follow_up = False
        if academic_year:
            a.academic_year, a.year_is_explicit = academic_year, True

    yield {"type": "status", "stage": "retrieving"}
    retrieval_query = _rewrite(question, history, a)
    schedule = analyse(retrieval_query)
    if exam_timing(retrieval_query) and schedule.module_codes:
        requested_session = re.search(r"\b(autumn|spring|summer|repeat|winter)\b", retrieval_query, re.I)
        exam_year = schedule.academic_year if schedule.year_is_explicit else a.academic_year if a.year_is_explicit else None
        exam_answer, confirmed = module_exam_guidance(schedule.module_codes, exam_year,
                                                      requested_session[1] if requested_session else None)
        yield done(exam_answer, [], [], "system", confirmed, retrieval_query,
                   ["Where can I check the general examination period?", "How do I report an exam timetable clash?"],
                   ["module_exam_timetable_found" if confirmed else "module_exam_timetable_required"])
        return
    index = index or get_index()
    rr = retrieve(index, expand_query(retrieval_query), categories=categories,
                  academic_year=a.academic_year, year_is_explicit=a.year_is_explicit,
                  boost_categories=a.categories, module_codes=a.module_codes)
    relevant = rr.relevant_hits
    flags = [] if rr.reranked else ["no_reranker"]
    debug = [h.to_debug() for h in rr.hits]

    sources = []
    for i, h in enumerate(relevant, start=1):
        c = make_citation(i, h)
        c["_full_text"] = h.record.text
        sources.append(c)
    public_sources = [{k: v for k, v in c.items() if k != "_full_text"} for c in sources]
    yield {"type": "sources", "sources": public_sources}

    if not relevant:
        yield done(insufficient_answer(a), [], [], "insufficient", False, retrieval_query,
                   _follow_ups(a, [], question), flags + ["no_relevant_sources"],
                   rr.elapsed_ms, rr.top_score, debug)
        return

    if a.year_is_explicit and all(h.year_mismatch for h in relevant):
        flags.append("year_mismatch")

    llm = get_llm()
    mode = "generative"
    raw = ""
    if llm is None:
        mode = "extractive"
        raw = extractive_answer(relevant, retrieval_query)
        yield {"type": "token", "text": raw}
    else:
        yield {"type": "status", "stage": "generating"}
        prompt = prompts.build_answer_prompt(
            a.sanitized_query or question, prompts.build_context(relevant),
            prompts.build_history(history, s.history_turns), a.academic_year,
            a.year_is_explicit, a.high_stakes)
        try:
            for delta in llm.stream(prompt, prompts.SYSTEM_PROMPT):
                raw += delta
        except LLMUnavailable as exc:
            log.error("generation failed, falling back to extractive",
                      extra={"extra_fields": {"error": str(exc)}})
            flags.append("llm_error")
            mode = "extractive"
            raw = extractive_answer(relevant, retrieval_query, unavailable=True)
            yield {"type": "reset"}
            yield {"type": "token", "text": raw}

    v = validate(raw, sources)
    if mode == "generative" and v.unverified_figures:
        # A warning does not make an unsupported date or amount safe to display.
        flags.append("unverified_generation_replaced")
        if v.invalid_markers:
            flags.append("invalid_citations_removed")
        mode = "extractive"
        raw = extractive_answer(relevant, retrieval_query, verification_failed=True)
        v = validate(raw, sources)
        yield {"type": "reset"}
        yield {"type": "token", "text": raw}
    if mode == "generative" and not v.has_citations:
        # An uncited or cut-off generated answer is not a usable final answer.
        # Replace it with source excerpts instead of displaying unsupported claims.
        flags.append("uncited_generation_replaced")
        mode = "extractive"
        raw = extractive_answer(relevant, retrieval_query, unavailable=True)
        v = validate(raw, sources)
        yield {"type": "reset"}
        yield {"type": "token", "text": raw}
    answer = v.content
    if v.invalid_markers:
        flags.append("invalid_citations_removed")
    if mode == "generative" and not v.has_citations:
        flags.append("uncited_answer")
        answer += ("\n\n> I couldn't link this answer to a specific source passage, so please "
                   f"treat it with caution and verify with {_contact_line(a.category)}.")
    if v.unverified_figures:
        flags.append("unverified_figures")
        answer += ("\n\n> Some figures (" + ", ".join(v.unverified_figures[:5]) +
                   ") could not be matched exactly to the cited text. Please check the source.")
    if "year_mismatch" in flags:
        years = sorted({h.record.academic_year for h in relevant if h.record.academic_year})
        answer += (f"\n\n> Note: I found information for {', '.join(years)}, not "
                   f"{a.academic_year}. Details may have changed.")
    if a.high_stakes:
        answer += verification_note(a)
    if any(h.curriculum_match for h in relevant):
        from .curricula import resolve_course
        course = resolve_course(retrieval_query)
        if course:
            answer += f"\n\n[Browse the published semester map](/curricula?course={course['id']})"

    if mode == "generative":
        # The client paces verified text progressively; do not expose unvalidated model deltas.
        yield {"type": "token", "text": answer}
    yield done(answer, v.citations, public_sources, mode, True, retrieval_query,
               _follow_ups(a, relevant, question), flags, rr.elapsed_ms, rr.top_score, debug)


def run(question: str, history: list[dict] | None = None, **kwargs) -> PipelineResult:
    result = None
    for ev in run_stream(question, history, **kwargs):
        if ev["type"] == "done":
            result = ev["result"]
    assert result is not None
    return result

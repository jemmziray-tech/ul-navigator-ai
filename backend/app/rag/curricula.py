"""Resolve programme context and prefer exact published semester passages."""
import json
import re
from functools import lru_cache
from pathlib import Path


@lru_cache
def catalogue():
    path = Path(__file__).resolve().parents[1] / "data/curricula.json"
    return json.loads(path.read_text(encoding="utf-8")).get("courses", []) if path.exists() else []


def study_year(q):
    for word, number in [("first", 1), ("second", 2), ("third", 3), ("fourth", 4), ("fifth", 5)]:
        if re.search(r"\b" + word + r"\s+year\b", q, re.I): return number
    direct = re.search(r"\byear\s*:?\s*([1-8])\b", q, re.I)
    reverse = re.search(r"\b([1-8])(?:st|nd|rd|th)?\s+year\b", q, re.I)
    return int(direct.group(1)) if direct else int(reverse.group(1)) if reverse else None


def semester(q):
    direct = re.search(r"\bsemester\s*:?\s*(20|1[0-9]|[1-9])\b", q, re.I)
    reverse = re.search(r"\b(20|1[0-9]|[1-9])(?:st|nd|rd|th)\s+semester\b", q, re.I)
    if direct: return int(direct.group(1))
    if reverse: return int(reverse.group(1))
    for word, number in [("first", 1), ("second", 2), ("third", 3)]:
        if re.search(r"\b" + word + r"\s+semester\b", q, re.I): return number
    return None


def resolve_course(question, history=()):
    courses = catalogue()
    for c in courses:
        if c.get("code") and re.search(r"\b" + re.escape(c["code"]) + r"\b", question, re.I): return c
    tokens = set(re.findall(r"[a-z]+", question.lower()))
    generic = set("the at in of and or a an course programme program degree bachelor master science arts bsc msc ba ma ul university limerick modules semester year first second third what which how many for content".split())
    ranked = []
    for c in courses:
        terms = set(re.findall(r"[a-z]+", c["title"].lower())) - generic
        if terms and terms <= tokens:
            if "bsc" in tokens and "msc" not in tokens and "bsc" not in c["title"].lower(): continue
            if "msc" in tokens and "bsc" not in tokens and "bsc" in c["title"].lower(): continue
            ranked.append((len(terms), c))
    if ranked:
        ranked.sort(key=lambda x: -x[0])
        if len(ranked) == 1 or ranked[0][0] > ranked[1][0]: return ranked[0][1]
        return None
    # Short context-dependent semester questions can inherit one recently identified programme.
    # An explicitly named new subject must not silently inherit the previous programme.
    if re.search(r"engineering|nursing|business|psychology|artificial|machine learning|computer science", question, re.I): return None
    for turn in reversed(list(history)[-8:]):
        if turn.get("clarification"): continue
        text = turn.get("content", "")
        found = [c for c in courses if c.get("code") and re.search(r"\b" + re.escape(c["code"]) + r"\b", text, re.I)]
        if len(found) == 1: return found[0]
        if len(found) > 1: return None
    return None


def select_sections(course, query):
    sections = course.get("sections", [])
    year = study_year(query)
    if year:
        explicit = [s for s in sections if re.search(r"\byear\s*" + str(year) + r"\b", s["yearLabel"], re.I)]
        # Combined year labels retain their source wording; semester numbers disambiguate later years.
        for s in sections:
            m = re.search(r"\byear\s*(\d+)\s*(?:and|&|to|–|-)\s*(\d+)", s["yearLabel"], re.I)
            if m and int(m.group(1)) <= year <= int(m.group(2)) and s not in explicit:
                explicit.append(s)
        sections = explicit or [s for s in sections if not re.search(r"\byear\s*\d", s["yearLabel"], re.I)]
        # Only derive a combined-year split when the programme itself establishes
        # cumulative two-semester numbering in at least two separate earlier years.
        single = [(s.get("year"), s.get("semesterNumber")) for s in course.get("sections", []) if s.get("year") and s.get("semesterNumber")]
        established = len({y for y, _ in single}) >= 2 and all(2 * y - 1 <= n <= 2 * y for y, n in single)
        if established:
            sections = [s for s in sections if not re.search(r"\byear\s*\d+\s*(?:and|&|to|–|-)\s*\d+", s["yearLabel"], re.I)
                        or not s.get("semesterNumber") or (s["semesterNumber"] + 1) // 2 == year]
    bsc, msc = bool(re.search(r"\bbsc\b", query, re.I)), bool(re.search(r"\bmsc\b", query, re.I))
    chosen = re.search(r"\b(bsc|msc)\s+pathway\b", query, re.I)
    if chosen: bsc, msc = chosen.group(1).lower() == "bsc", chosen.group(1).lower() == "msc"
    if bsc != msc:
        other = "msc" if bsc else "bsc"
        sections = [s for s in sections if other not in s["yearLabel"].lower()]
    season = next((x for x in ["autumn", "spring", "summer", "winter"] if re.search(r"\b" + x + r"\b", query, re.I)), None)
    number = semester(query)
    if season: sections = [s for s in sections if season in s["semester"].lower()]
    elif number:
        exact = [s for s in sections if s.get("semesterNumber") == number]
        if exact: sections = exact
        elif year:
            # "First semester of Year 2" means the first listed semester in that year,
            # even when the source numbers it Semester 3. Preserve source labels.
            labels = list(dict.fromkeys(s["semester"] for s in sections))
            sections = [s for s in sections if number <= len(labels) and s["semester"] == labels[number - 1]]
        else: sections = []
    return sections


def curriculum_records(index, query):
    if not re.search(r"modules?|subjects?|curriculum|course structure|what.*study", query, re.I): return []
    if re.search(r"\b[A-Z]{2,4}\d{4}\b", query) and re.search(r"syllabus|learning outcomes?|prerequisites?|assessment|credits|module content", query, re.I) and not re.search(r"semester", query, re.I): return []
    course = resolve_course(query)
    if not course: return []
    targets = select_sections(course, query)
    markers = [f"| {s['yearLabel']} | {s['semester']}".lower() for s in targets]
    return [r for r in index.records.values()
            if r.url.split("#")[0] == course["url"].split("#")[0]
            and any(m in r.section.lower() for m in markers)]

"""Fast rule-based query understanding: category, intent, risk level, academic year,
prompt-injection detection and query expansion. Deterministic and cheap, so it runs on
every request before retrieval."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..config import get_settings
from .text import MODULE_CODE_RE, find_academic_years
from .exam_schedule import exam_timing

CATEGORIES: dict[str, list[str]] = {
    "qca_grading": ["qca", "grade", "grading", "gpa", "quality credit", "qpv", "honours",
                    "first class", "2.1", "2.2", "classification", "pass mark", "repeat",
                    "fail", "i-grade", "ng grade", "appeal", "exam result", "results"],
    "regulations": ["regulation", "regulations", "handbook", "policy", "policies", "appeal",
                    "plagiarism", "academic integrity", "progression", "exclusion", "repeat",
                    "academic council", "examination board"],
    "registration": ["register", "registration", "enrol", "enrolment", "enrollment", "orientation",
                     "student id", "id card", "deferral", "defer", "withdraw", "leave of absence",
                     "transfer", "timetable"],
    "accommodation": ["accommodation", "housing", "residence", "room", "rent", "village",
                      "licence agreement", "landlord", "plassey", "dorm", "on-campus", "off-campus",
                      "deposit"],
    "international": ["visa", "immigration", "irp", "gnib", "stamp 2", "international student",
                      "non-eu", "erasmus", "exchange", "incoming", "study abroad", "passport",
                      "medical insurance", "garda"],
    "fees": ["fee", "fees", "tuition", "payment", "pay", "instalment", "student contribution",
             "refund", "cost", "budget", "€", "euro", "free fees", "susi", "grant"],
    "scholarships": ["scholarship", "bursary", "award", "funding", "sports scholarship",
                     "merit", "financial aid", "hardship fund"],
    "calendar": ["calendar", "semester", "term", "week", "start date", "deadline", "exam period",
                 "exams start", "reading week", "holiday", "teaching week", "when does",
                 "when is", "dates"],
    "modules": ["module", "modules", "book of modules", "credits", "ects", "elective",
                "prerequisite", "syllabus", "course content", "lecturer"],
    "library": ["library", "glucksman", "borrow", "loan", "books", "study space", "printing",
                "database", "journal", "opening hours"],
    "student_support": ["support", "counselling", "counseling", "disability", "health",
                        "wellbeing", "mental", "chaplaincy", "student life", "access", "medical",
                        "learning support", "maths learning", "writing centre"],
    "careers": ["career", "cecd", "coop", "co-op", "placement", "internship", "cv", "job",
                "employability", "graduate"],
    "campus": ["map", "building", "room number", "where is", "campus", "parking", "bus",
               "location", "directions"],
    "undergraduate": ["course", "courses", "programme", "program", "cao", "entry requirement",
                      "points", "prospectus", "apply", "admission", "undergraduate", "degree"],
}

HIGH_STAKES = {
    "international": ["visa", "immigration", "irp", "stamp", "gnib", "permission to remain"],
    "accommodation": ["contract", "licence agreement", "deposit", "eviction", "cancel", "refund"],
    "qca_grading": ["appeal", "regulation", "repeat", "progression", "academic integrity",
                    "plagiarism", "exclusion", "deferral"],
    "fees": ["refund", "non-payment", "penalty"],
    "regulations": ["appeal", "repeat", "progression", "plagiarism", "academic integrity",
                    "exclusion", "deferral", "regulation"],
}

OFFICIAL_CONTACTS: dict[str, tuple[str, str]] = {
    "qca_grading": ("Academic Registry", "https://www.ul.ie/academic-registry"),
    "regulations": ("UL Policy Hub / Academic Registry", "https://www.ul.ie/policy-hub/policies"),
    "registration": ("Academic Registry", "https://www.ul.ie/academic-registry"),
    "calendar": ("Academic Registry - Academic Calendars",
                 "https://www.ul.ie/academic-registry"),
    "accommodation": ("UL Accommodation Office", "https://www.ul.ie/accommodation"),
    "international": ("UL Global - Incoming Students",
                      "https://www.ul.ie/global/incoming-students/need-know-information/incoming-students-faqs"),
    "fees": ("UL Fees Office", "https://www.ul.ie/fees"),
    "scholarships": ("UL Scholarships", "https://www.ul.ie/study/undergraduate/scholarships"),
    "modules": ("UL Book of Modules", "https://www.bookofmodules.ul.ie/"),
    "library": ("Glucksman Library", "https://www.ul.ie/library"),
    "student_support": ("Student Supports & Resources",
                        "https://www.ul.ie/academic-registry/newstudents/student-supports-resources"),
    "careers": ("Cooperative Education & Careers Division (CECD)", "https://www.ul.ie/cecd"),
    "campus": ("UL Campus Maps", "https://www.ul.ie/buildings/campus-maps"),
    "undergraduate": ("UL Undergraduate Study", "https://www.ul.ie/study/undergraduate"),
    "general": ("University of Limerick", "https://www.ul.ie"),
}

INJECTION_PATTERNS = [
    r"ignore (all |any |the )?(previous|prior|above|earlier) (instructions|prompts?|rules)",
    r"disregard (all |any |the )?(previous|prior|above|system)",
    r"(reveal|show|print|repeat|output) (me )?(your|the) (system |hidden |initial )?(prompt|instructions)",
    r"you are now\b", r"\bdeveloper mode\b", r"\bjailbreak", r"\bdan mode\b",
    r"pretend (to be|you are)", r"act as (an? )?(unfiltered|unrestricted|different)",
    r"new instructions?:", r"system prompt", r"</?system>", r"override (your|the) (rules|safety)",
    r"(your|the server'?s?|the) (gemini )?(api[_ ]?key|secret key|\.env file)",
    r"\b(fabricate|hallucinate|invent) (a |an |some )?(answer|citation|source|policy|fee|deadline)",
]
_INJ_RE = re.compile("|".join(INJECTION_PATTERNS), re.IGNORECASE)

SMALLTALK_RE = re.compile(
    r"^\s*(hi|hello|hey|hiya|good (morning|afternoon|evening)|thanks?( you)?|thank you|cheers|"
    r"who are you|what can you do|help)\W*$", re.IGNORECASE)

# Whole-message matches keep greetings from swallowing substantive questions.
SWAHILI_SMALLTALK_RE = re.compile(
    r"\s*(habari(?: (?:yako|yenu|za (?:asubuhi|mchana|jioni)))?|"
    r"hujambo|hamjambo|jambo|mambo|shikamoo|salama|asante(?: sana)?)\s*[.!?]*\s*",
    re.IGNORECASE,
)

SYNONYMS = {
    "ai": "artificial intelligence",
    "ml": "machine learning",
    "qca": "QCA quality credit average grade point",
    "accom": "accommodation",
    "irp": "IRP Irish Residence Permit immigration registration",
    "gnib": "IRP immigration registration",
    "cecd": "CECD careers cooperative education",
    "coop": "cooperative education placement",
    "co-op": "cooperative education placement",
    "sem": "semester",
    "fees": "fees tuition",
    "ects": "ECTS credits",
}

FOLLOW_UP_RE = re.compile(
    r"^(and|what about|how about|also|so|then|but|ok|okay)\b|\b(it|that|this|they|those|them|"
    r"there|its|their)\b", re.IGNORECASE)


@dataclass
class QueryAnalysis:
    query: str
    category: str = "general"
    categories: list[str] = field(default_factory=list)
    intent: str = "question"  # question|smalltalk|injection|empty
    high_stakes: bool = False
    academic_year: str | None = None
    year_is_explicit: bool = False
    module_codes: list[str] = field(default_factory=list)
    injection_detected: bool = False
    sanitized_query: str = ""
    is_follow_up: bool = False
    flags: list[str] = field(default_factory=list)


def _strip_injection(text: str) -> str:
    cleaned = _INJ_RE.sub(" ", text)
    return re.sub(r"\s+", " ", cleaned).strip()


def analyse(query: str, has_history: bool = False) -> QueryAnalysis:
    q = (query or "").strip()
    a = QueryAnalysis(query=q)
    if not q:
        a.intent = "empty"
        return a
    low = q.lower()

    if _INJ_RE.search(q):
        a.injection_detected = True
        a.flags.append("prompt_injection")
    a.sanitized_query = _strip_injection(q) if a.injection_detected else q

    if SMALLTALK_RE.fullmatch(q) or SWAHILI_SMALLTALK_RE.fullmatch(q):
        a.intent = "smalltalk"
        return a

    if re.search(r"(?:find|get|want|need)(?: me)? (?:a |an )?(?:wife|husband|girlfriend|boyfriend)|date me|marry me", low):
        a.intent = "social"
        return a

    scores: dict[str, int] = {}
    for cat, kws in CATEGORIES.items():
        n = sum(1 for kw in kws if re.search(rf"(?<![a-z0-9]){re.escape(kw)}(?![a-z0-9])", low))
        if n:
            scores[cat] = n
    if scores:
        ranked = sorted(scores.items(), key=lambda kv: -kv[1])
        a.category = ranked[0][0]
        a.categories = [c for c, _ in ranked]
    # Immigration registration is handled by UL Global, not student enrolment.
    if re.search(r"\bimmigration\b|\birp\b|\bgnib\b|\bvisa\b|stamp 2|permission to remain", low):
        a.category = "international"
        a.categories = ["international"] + [c for c in a.categories if c != "international"]
        a.high_stakes = True
        a.flags.append("high_stakes:international")
    a.module_codes = [f"{m.group(1)}{m.group(2)}" for m in MODULE_CODE_RE.finditer(q.upper())]
    if a.module_codes and "modules" not in a.categories:
        a.categories.insert(0, "modules")
        a.category = "modules"
    if exam_timing(q):
        a.category = "calendar"
        a.categories = ["calendar"] + [c for c in a.categories if c != "calendar"]

    for cat in a.categories[:2]:
        if any(kw in low for kw in HIGH_STAKES.get(cat, [])):
            a.high_stakes = True
            a.flags.append(f"high_stakes:{cat}")

    years = find_academic_years(q)
    if years:
        a.academic_year, a.year_is_explicit = years[0], True
    else:
        settings = get_settings()
        cur = settings.current_academic_year()
        if re.search(r"\bnext (academic )?year\b", low):
            start = int(cur[:4]) + 1
            a.academic_year, a.year_is_explicit = f"{start}/{str(start + 1)[-2:]}", True
        elif re.search(r"\b(last|previous) (academic )?year\b", low):
            start = int(cur[:4]) - 1
            a.academic_year, a.year_is_explicit = f"{start}/{str(start + 1)[-2:]}", True
        else:
            a.academic_year = cur

    # Short complete questions can introduce a new topic. Only rewrite a short
    # fragment or a question that actually refers to earlier context.
    complete_question = bool(re.match(
        r"^(what|which|where|when|why|how|who|can|could|does|do|is|are|should|"
        r"nataka|ninataka|naomba)\b", q, re.IGNORECASE))
    a.is_follow_up = has_history and (
        bool(FOLLOW_UP_RE.search(q)) or (len(q.split()) <= 7 and not complete_question))

    if a.injection_detected and len(a.sanitized_query.split()) < 3:
        a.intent = "injection"
    return a


def expand_query(q: str) -> str:
    extra = []
    for tok in re.findall(r"[a-zA-Z\-]+", q.lower()):
        if tok in SYNONYMS:
            extra.append(SYNONYMS[tok])
    return q if not extra else f"{q} ({' '.join(extra)})"


def heuristic_rewrite(question: str, history: list[dict]) -> str:
    """Make a follow-up self-contained by prepending the previous user question."""
    prev = [m["content"] for m in history if m.get("role") == "user"]
    if not prev:
        return question
    return f"{prev[-1]} — follow-up: {question}"

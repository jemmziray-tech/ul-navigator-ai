"""Small, persisted clarification flow; no model calls or inferred fee status."""
from __future__ import annotations

import re
from dataclasses import dataclass

from .text import find_academic_years
from .curricula import resolve_course, select_sections, study_year, semester


@dataclass
class Clarification:
    question: str
    answer: str = ""
    choices: list[str] | None = None
    state: dict | None = None


def _topic(q: str) -> str | None:
    if re.search(r"\b(fees?|tuition)\b", q, re.I) and re.search(
            r"how much|cost|amount|price|what (?:are|is).*fees?|tuition fees", q, re.I):
        if not re.search(r"pay|payment|refund|instalment|receipt|due|free fees|fee status|repeat|examination|exam fee|accommodation|housing|rent|parking|library|visa|immigration|appeal", q, re.I):
            return "fees"
    if re.search(r"entry requirements?|admission requirements?|what grades.*need|can i apply", q, re.I):
        return "entry"
    if re.search(r"modules?|subjects?|curriculum|course structure|what.*study", q, re.I) and re.search(r"semester|year|programme|course|LM\d{3}|study|curriculum", q, re.I):
        return "curriculum"
    return None


def _fields(q: str) -> dict[str, str]:
    fields = {}
    codes = re.findall(r"\bLM\d{3}\b", q, re.I)
    if codes:
        fields["programme"] = codes[0].upper()
    else:
        name = re.search(r"\b(?:for|in)\s+((?:(?:the|a|an)\s+)?(?:MSc|MA|BSc|BA|Bachelor|Master|PhD)\b[^?;\n]*)", q, re.I)
        if name:
            fields["programme"] = name.group(1).strip()[:200]
    years = find_academic_years(q)
    if years:
        fields["academic_year"] = years[0]
    if re.search(r"^(?:non[- ]?eu)[.! ]*$|non[- ]?eu (?:fees?|category|rate)|(?:fee category|assessed as)[: ]+non[- ]?eu", q, re.I):
        fields["fee_category"] = "Non-EU (user-stated; not an eligibility assessment)"
    elif re.search(r"^eu[.! ]*$|(?<!non-)(?<!non )\beu (?:fees?|category|rate)|(?:fee category|assessed as)[: ]+eu", q, re.I):
        fields["fee_category"] = "EU (user-stated; not an eligibility assessment)"
    for pattern, route in [(r"leaving cert", "Leaving Certificate"), (r"\bqqi|fetac", "QQI/FET"),
                           (r"\bmature\b", "Mature applicant"), (r"\btransfer\b", "Transfer applicant"),
                           (r"\bgraduate\b", "Graduate applicant"),
                           (r"international qualification|overseas qualification", "International qualification")]:
        if re.search(pattern, q, re.I):
            fields["route"] = route
            break
    return fields


def clarify(question: str, history: list[dict], academic_year: str | None = None) -> Clarification:
    previous = history[-1].get("clarification") if history and history[-1].get("role") == "assistant" else None
    pending = previous if isinstance(previous, dict) and previous.get("version") == 1 else None
    # A new complete question starts its own flow. Short replies resume the saved question.
    is_new = bool(re.match(r"^(?:what|how|where|when|why|can|does|do|tell|show)\b", question, re.I))
    general = bool(re.search(r"answer generally|general overview|in general|generally", question, re.I))
    if general:
        original = pending["original_question"] if pending else question
        return Clarification(original + " Give a general overview; do not quote a programme-specific fee or infer an applicant's eligibility.")
    if pending and not is_new:
        topic = pending["topic"]
        original = pending["original_question"]
        fields = {**pending.get("known_fields", {}), **_fields(question)}
        missing = pending.get("missing_field")
        if missing == "programme" and not fields.get("programme"):
            if len(question.split()) >= 2 and not re.search(r"not sure|don't know|thank|\b20\d\d\b", question, re.I):
                fields["programme"] = question[:200].strip(" .?")
        if missing == "fee_category" and re.search(r"not sure|don't know|unsure", question, re.I):
            return Clarification(original + " Fee category is unknown. Explain how to establish EU/non-EU fee status using UL guidance, rather than quoting a personalised tuition price.")
        if missing == "qualification" and len(question.split()) >= 2:
            fields["qualification"] = question[:200]
    else:
        topic = _topic(question)
        if not topic:
            return Clarification(question)
        original, fields = question, _fields(question)
    if academic_year:
        fields["academic_year"] = academic_year
    if topic == "curriculum":
        if study_year(question): fields["study_year"] = str(study_year(question))
        if semester(question): fields["semester"] = str(semester(question))
        for pathway in ["BSc", "MSc"]:
            if re.search(r"\b" + pathway + r"\b", question, re.I) and not re.search(r"\b" + ("MSc" if pathway == "BSc" else "BSc") + r"\b", question, re.I): fields["pathway"] = pathway
        course = resolve_course(original + " " + fields.get("programme", ""), history)
        if course:
            fields["programme"] = course.get("code") or course["title"]
        effective = original + " " + fields.get("programme", "")
        if fields.get("study_year"): effective += " Year " + fields["study_year"]
        if fields.get("semester"): effective += " Semester " + fields["semester"]
        if fields.get("pathway"): effective += " " + fields["pathway"] + " pathway"
        required = ["programme"]
        selected = select_sections(course, effective) if course else []
        if len({s["yearLabel"] for s in selected}) > 1 and not study_year(effective) and semester(effective): required.append("study_year")
        labels = " ".join(s["yearLabel"] for s in selected).lower()
        if "bsc" in labels and "msc" in labels and not fields.get("pathway"): required.append("pathway")
    else:
        required = ["programme", "fee_category", "academic_year"] if topic == "fees" else ["programme", "route"]
    if topic == "entry" and fields.get("route") == "International qualification":
        required.append("qualification")
    missing = next((f for f in required if not fields.get(f)), None)
    if not missing:
        context = "; ".join(f"{k.replace('_', ' ')}: {v}" for k, v in fields.items())
        return Clarification(original + "\nApplicant details supplied by the user: " + context)
    questions = {
        "study_year": "Which year of study do you mean? The programme lists modules across several years.",
        "pathway": "Do you mean the BSc or MSc pathway? UL publishes different modules for those routes.",
        "programme": "Which UL programme do you mean? Please give its full name or CAO code (for example LM174). You can also ask for a general overview.",
        "fee_category": "Which fee category should I look up: EU or Non-EU? Use your assessed fee category if you know it; nationality alone does not determine fee status.",
        "academic_year": "Which academic year are you asking about? Please use a year such as 2026/27, so I can check the right fee information.",
        "route": "Which application route applies to you? Entry requirements can differ by route.",
        "qualification": "Which qualification are you applying with, and which country or education system awarded it? This helps me find the relevant entry guidance.",
    }
    choices = {"study_year": ["Year 1", "Year 2", "Year 3", "Year 4", "Year 5"], "pathway": ["BSc pathway", "MSc pathway"], "programme": ["Answer generally"],
               "fee_category": ["EU", "Non-EU", "I'm not sure about my fee status"],
               "academic_year": ["2026/27", "2027/28", "Answer generally"],
               "route": ["Leaving Certificate", "QQI/FET", "Mature applicant", "International qualification", "Answer generally"]}
    return Clarification(original, questions[missing], choices.get(missing, ["Answer generally"]),
                         {"version": 1, "topic": topic, "original_question": original,
                          "known_fields": fields, "missing_field": missing})

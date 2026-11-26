"""Keep module exam scheduling distinct from teaching-semester descriptors."""
import re
from ..tools.exams import lookup_exam

MODULE_EXAM_TIMETABLE = "https://www.timetable.ul.ie/UA/ExamModuleTimetable.aspx"


def exam_timing(query: str) -> bool:
    return bool(re.search(r"\bexam(?:s|ination|inations)?\b", query, re.I)
                and re.search(r"\bwhen\b|\bdates?\b|\btimes?\b|\bschedul\w*\b|\btimetable\b|exam period", query, re.I)
                and not re.search(r"\bfees?\b|\bresults?\b|\bgrades?\b|\bmarks?\b", query, re.I))


def module_exam_guidance(codes: list[str], academic_year=None, session=None) -> tuple[str, bool]:
    def plain(text):
        return re.sub(r"([\\`*{}\[\]<>()!_])", r"\\\1", str(text))
    parts = []
    confirmed = False
    for code in list(dict.fromkeys(codes))[:3]:
        result = lookup_exam(code, academic_year, session)
        if result["status"] == "found":
            confirmed = True
            parts.append(f"**{code} — {result['session']} {result['academic_year']}**")
            for row in result["rows"]:
                parts.append(f"- **{row['date_iso']} at {row['time']}** ({plain(row['day'])}) · Building: {plain(row['building'])}; location: {plain(row['location'])}.")
                if row["information"]:
                    parts.append(f"  Published information: {plain(row['information'])}")
            parts.append(f"Checked: {result['checked_at'][:16].replace('T', ' ')} UTC. {result['note']}")
        else:
            parts.append(f"**{code}: no current appointment confirmed.** {result['note']}")
            if result.get("session"):
                parts.append(f"The source currently publishes {result['session']} {result['academic_year']}.")
        parts.append(f"[Open exam lookup](/exams?module={code})")
    if parts:
        return ("\n\n".join(parts) + f"\n\n[Verify on the official UL Module Exam Timetable]({MODULE_EXAM_TIMETABLE}). Published module venues do not establish your personal seating or accommodations.", confirmed)
    return (f"I can't confirm the exact exam date, time or venue for **{', '.join(dict.fromkeys(codes))}** "
            "from verified module timetable data in this service.\n\n"
            f"Open the [official UL Module Exam Timetable]({MODULE_EXAM_TIMETABLE}) and look up "
            "your module for the relevant exam session. Check the latest timetable before attending.\n\n"
            "A module's teaching semester or the general university exam period does not establish its individual exam appointment.", False)

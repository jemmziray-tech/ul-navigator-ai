"""Keep module exam scheduling distinct from teaching-semester descriptors."""
import re

MODULE_EXAM_TIMETABLE = "https://www.timetable.ul.ie/UA/ExamModuleTimetable.aspx"


def exam_timing(query: str) -> bool:
    return bool(re.search(r"\bexam(?:s|ination|inations)?\b", query, re.I)
                and re.search(r"\bwhen\b|\bdates?\b|\btimes?\b|\bschedul\w*\b|\btimetable\b|exam period", query, re.I)
                and not re.search(r"\bfees?\b|\bresults?\b|\bgrades?\b|\bmarks?\b", query, re.I))


def module_exam_guidance(codes: list[str]) -> str:
    return (f"I can't confirm the exact exam date, time or venue for **{', '.join(dict.fromkeys(codes))}** "
            "from verified module timetable data in this service.\n\n"
            f"Open the [official UL Module Exam Timetable]({MODULE_EXAM_TIMETABLE}) and look up "
            "your module for the relevant exam session. Check the latest timetable before attending.\n\n"
            "A module's teaching semester or the general university exam period does not establish its individual exam appointment.")

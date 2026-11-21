"""Source-role ranking survives cross-encoder reranking; dates never imply validity."""
import re
from urllib.parse import urlsplit


def source_role(url: str, title: str) -> str:
    path = urlsplit(url).path.lower()
    if re.search(r"/(?:news|events?)(?:/|$)", path):
        return "editorial"
    if re.search(r"/(?:people|staff|profiles?|alumni)(?:/|$)", path) or re.search(
            r"graduate spotlight|meet our|biography|50 years of co-op", title, re.I):
        return "profile"
    return "guidance"


def policy_weight(query: str, role: str, year_mismatch: bool, explicit: bool) -> tuple[float, bool]:
    editorial_query = bool(re.search(
        r"\bnews\b|\bevents?\b|open day|who is|biography|\bprofessor\b|\bdr\.|\balumni\b|spotlight", query, re.I))
    rules_query = bool(re.search(
        r"\bfees?\b|tuition|\bqca\b|honours|deadline|entry requirements?|admission requirements?|\bvisa\b|progression|\bpolicy\b|regulations?", query, re.I))
    allowed = not (rules_query and role != "guidance" and not editorial_query)
    weight = 1.0 if role == "guidance" or editorial_query else 0.65
    if year_mismatch:
        weight *= 0.65 if explicit else 0.8
    return weight, allowed

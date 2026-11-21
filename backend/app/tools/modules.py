"""Distinguish module descriptions from incidental prerequisite references."""
import re
from urllib.parse import parse_qs, urlparse


def describes_module(chunk, document, code):
    parsed = urlparse(document.url)
    if parsed.hostname in {"www.bookofmodules.ul.ie", "bookofmodules.ul.ie"}:
        value = parse_qs(parsed.query).get("ModuleCodeParameter", [""])[0]
        if value.upper() == f"|{code}|":
            return True
    pattern = re.escape(code[:-4]) + r"\s?" + code[-4:] + r"(?![A-Z0-9])"
    if re.match(pattern, document.title.strip(), re.I):
        return True
    section = chunk.section or ""
    if not re.search(r"prerequisites?|prior modules?", section, re.I):
        if re.match(pattern, section.split(">")[ -1].strip(), re.I):
            return True
    # Explicit Markdown module headings in uploaded exports/booklets.
    return bool(re.search(r"^\s*#{1,6}\s+" + pattern, chunk.text, re.I | re.M))

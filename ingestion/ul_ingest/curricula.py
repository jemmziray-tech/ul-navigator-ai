"""Extract published curriculum sections without flattening year/pathway/semester tabs."""
from __future__ import annotations

import hashlib
import re
from urllib.parse import parse_qs, quote, urljoin, urlsplit

from bs4 import BeautifulSoup

CODE = re.compile(r"\b[A-Z]{2,4}\d{4}[A-Z]?\b")
SEMESTER = re.compile(r"\b(?:semester\s*\d+|(?:autumn|spring|summer|winter)\s*(?:semester|term)|(?:first|second|third)\s+semester)\b", re.I)


def clean(text):
    return re.sub(r"\s+", " ", text or "").strip()


def module_url(code):
    return "https://bookofmodules.ul.ie/Default.aspx?ModuleCodeParameter=" + quote("|" + code + "|", safe="")


def tab_label(soup, panel):
    node = soup.find(id=panel.get("aria-labelledby", ""))
    return clean(node.get_text(" ", strip=True)) if node else ""


def content_link(html, base):
    soup = BeautifulSoup(html, "lxml")
    for a in soup.select("a[href]"):
        if clean(a.get_text(" ", strip=True)).lower() in {"course content", "programme content", "program content"}:
            u = urljoin(base, a["href"])
            if urlsplit(u).hostname in {"www.ul.ie", "ul.ie"} and not urlsplit(u).query:
                return u.split("#")[0]
    return None


def parse_curriculum(html, course, url, checked):
    soup = BeautifulSoup(html, "lxml")
    main = soup.find("main") or soup
    panels = main.select("section.tabs__panel")
    leaves = [p for p in panels if not p.select_one("section.tabs__panel")]
    sections = []
    containers = leaves or [main]
    for panel in containers:
        labels = [tab_label(soup, p) for p in reversed([a for a in panel.parents if a in panels])]
        if panel in panels:
            labels.append(tab_label(soup, panel))
        labels = [x for x in labels if x]
        context = " > ".join(x for x in labels if not SEMESTER.search(x)) or "Programme structure"
        semester = next((x for x in reversed(labels) if SEMESTER.search(x)), None)
        group = "Listed modules"
        current = None

        def start(label):
            nonlocal current
            key = hashlib.sha1((context + "|" + label + "|" + str(len(sections))).encode()).hexdigest()[:12]
            ym = re.search(r"\byear\s*(\d+)(?!\s*(?:and|&|to|–|-)\s*\d)", context, re.I)
            sm = re.search(r"\bsemester\s*(\d+)\b", label, re.I)
            current = {"id": key, "yearLabel": context, "year": int(ym.group(1)) if ym else None,
                       "semester": label, "semesterNumber": int(sm.group(1)) if sm else None,
                       "modules": [], "notes": [], "sourceUrl": url + ("#" + panel["id"] if panel.get("id") else "")}
            sections.append(current)

        if semester:
            start(semester)
        for node in panel.find_all(["h2", "h3", "h4", "table", "li", "p"]):
            if node.find_parent("table") or (node.name != "li" and node.find_parent("li")):
                continue
            text = clean(node.get_text(" ", strip=True))
            if node.name.startswith("h"):
                if SEMESTER.search(text):
                    semester = text
                    start(text)
                    group = "Listed modules"
                elif re.search(r"core|compulsory|mandatory|elective|optional|choose|select", text, re.I):
                    group = text
                elif re.search(r"\byear\s*\d", text, re.I):
                    context = text
                    current = None
                continue
            candidates = []
            if node.name == "table":
                headers = [clean(x.get_text(" ", strip=True)) for x in node.select("tr:first-child th, tr:first-child td")]
                # Side-by-side semester columns require separate groups, never a combined list.
                semester_columns = [(i, h) for i, h in enumerate(headers) if SEMESTER.search(h)]
                if semester_columns:
                    for i, label in semester_columns:
                        start(label)
                        for row in node.find_all("tr")[1:]:
                            cells = row.find_all(["td", "th"], recursive=False)
                            if i < len(cells):
                                for part in cells[i].find_all(["p", "li"]) or [cells[i]]:
                                    t = clean(part.get_text(" ", strip=True)); codes = CODE.findall(t)
                                    if len(codes) == 1:
                                        current["modules"].append({"code": codes[0], "title": clean(t.replace(codes[0], "").strip(" -:()")), "description": "", "group": group, "url": module_url(codes[0])})
                    current = None
                    continue
                code_idx = next((i for i, h in enumerate(headers) if re.search(r"(?:module )?code", h, re.I)), None)
                title_idx = next((i for i, h in enumerate(headers) if re.search(r"title|module name", h, re.I)), None)
                for row in node.find_all("tr"):
                    cells = row.find_all(["td", "th"], recursive=False)
                    if not cells:
                        continue
                    row_text = clean(row.get_text(" ", strip=True)); codes = CODE.findall(row_text)
                    if len(codes) != 1:
                        if current and re.search(r"elective|optional|choose|select|compulsory|core", row_text, re.I):
                            group = row_text; current["notes"].append(row_text)
                        continue
                    code = codes[0]
                    if code_idx is not None and (code_idx >= len(cells) or not CODE.fullmatch(clean(cells[code_idx].get_text(" ", strip=True)))):
                        continue  # a code mentioned in prerequisites is not a module row
                    title = clean(cells[title_idx].get_text(" ", strip=True)) if title_idx is not None and title_idx < len(cells) else clean(row_text.replace(code, "").strip(" -:()"))
                    candidates.append((code, title, ""))
            elif node.name == "li":
                codes = CODE.findall(text)
                if len(codes) == 1:
                    a = next((a for a in node.select("a[href]") if "ModuleCodeParameter" in a["href"]), None)
                    heading = clean(a.get_text(" ", strip=True)) if a else text
                    if a or text.startswith(codes[0]) or re.match(r"^.{3,100}\(" + codes[0] + r"\)", text):
                        title = clean(heading.replace(codes[0], "").strip(" -:()"))
                        candidates.append((codes[0], title, clean(text[len(heading):]) if a else ""))
            elif node.name == "p" and current and text and not CODE.search(text):
                if len(text) < 1000 and not re.search(r"books and journal|for more information|book of modules", text, re.I):
                    current["notes"].append(text)
                    if re.search(r"choose|select|elective|optional", text, re.I): group = text
            if candidates:
                if current is None:
                    start(semester or "Semester not stated")
                for code, title, description in candidates:
                    if not any(m["code"] == code for m in current["modules"]):
                        current["modules"].append({"code": code, "title": title, "description": description, "group": group, "url": module_url(code)})
    sections = [s for s in sections if s["modules"] or any(re.search(r"co.?op|placement|dissertation|research|study abroad", n, re.I) for n in s["notes"])]
    return {"id": course["id"], "title": course["title"], "code": course.get("code"),
            "url": url, "checkedAt": checked, "academicYear": None, "sections": sections,
            "status": "structured" if sections else "no_structured_modules_found"}


def curriculum_markdown(course):
    name = f"{course.get('code') or ''} {course['title']}".strip()
    out = [f"# {name} — published curriculum", "", f"Official curriculum source: {course['url']}",
           f"Collected: {course['checkedAt']}. Academic-year applicability is not confirmed in this extract; do not assume it applies to every entry cohort."]
    for section in course["sections"]:
        out += ["", f"## {name} | {section['yearLabel']} | {section['semester']}", "",
                f"Programme: {name}. Published context: {section['yearLabel']}; {section['semester']}.",
                f"Captured coded module listings in this section: {len(section['modules'])}. This is not a confirmed compulsory workload where electives or choices apply; other uncoded or choice descriptions may also appear in the source."]
        for m in section["modules"]:
            out.append(f"- {m['code']} — {m['title']}. Group: {m['group']}. {m['description']}")
        out += section["notes"]
    return "\n".join(out)


def parse_module(html, code, checked):
    soup = BeautifulSoup(html, "lxml")
    # Text labels on the official ASP.NET page are stable even when generated IDs change.
    lines = [clean(s) for s in soup.get_text("\n", strip=True).splitlines() if clean(s)]
    text = "\n".join(lines)
    if not re.search(r"Module Code\s*-\s*Title:\s*" + re.escape(code) + r"\b", text, re.I):
        return None
    start = text.index("Module Code")
    stop = text.find("Module Leader:", start)
    body = text[start:stop if stop >= 0 else len(text)].strip()
    # Public staff contact emails are unnecessary for module content.
    body = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "", body)
    title = re.search(r"Module Code\s*-\s*Title:\s*" + re.escape(code) + r"\s*[-–—]\s*(.*?)\s*Year Last Offered:", text, re.S | re.I)
    formatted = []
    for line in body.splitlines():
        if line.endswith(":") or line in {"Credits", "Cognitive (Knowledge, Understanding, Application, Analysis, Evaluation, Synthesis)", "Affective (Attitudes and Values)", "Psychomotor (Physical Skills)"}:
            formatted += ["", "## " + line.rstrip(":"), "", "**" + line.rstrip(":") + ":**"]
        else: formatted.append(line)
    return {"code": code, "title": clean(title.group(1)) if title else "Official Book of Modules descriptor", "url": module_url(code), "checkedAt": checked,
            "markdown": f"# {code} — official Book of Modules description\n\nCollected: {checked}. Year Last Offered is a module-offering field, not confirmation of a programme's curriculum year.\n\n" + "\n".join(formatted)}

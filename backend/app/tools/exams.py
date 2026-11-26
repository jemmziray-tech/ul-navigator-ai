"""Bounded public ASP.NET timetable lookup; never accesses student accounts."""
from collections import OrderedDict
from copy import deepcopy
from datetime import datetime, timezone
import re
import threading
import time

import httpx
from bs4 import BeautifulSoup

SOURCE = "https://www.timetable.ul.ie/UA/ExamModuleTimetable.aspx"
CODE = re.compile(r"[A-Z]{2,4}\d{4}[A-Z]?")


def page(html):
    if len(html) > 2_000_000:
        raise ValueError("Timetable page exceeds limit")
    soup = BeautifulSoup(html, "html.parser")
    text = " ".join(soup.stripped_strings)
    match = re.search(r"The\s+(Autumn|Spring|Summer|Repeat|Winter)\s+(20\d{2}/\d{2})\s+Exam\s+Timetable", text, re.I)
    if not match:
        raise ValueError("Published exam session not identified")
    return soup, match[1].title(), match[2]


def parse_rows(html, code, session, year):
    soup, shown_session, shown_year = page(html)
    if (shown_session, shown_year) != (session, year):
        raise ValueError("Exam session changed during lookup")
    selected = soup.select_one("select[name] option[selected]")
    if selected is None or selected.get("value", "").upper() != code:
        raise ValueError("Timetable did not confirm selected module")
    table = soup.find("table", id="MainContent_ExamTimetableGridView")
    if table is None:
        raise ValueError("Timetable result table missing")
    headers = [th.get_text(" ", strip=True).lower() for th in table.find_all("th")]
    expected = ["module", "name", "date", "time", "day", "building", "location", "information"]
    if headers != expected:
        raise ValueError("Timetable format changed")
    rows = []
    for tr in table.find_all("tr"):
        cells = tr.find_all("td", recursive=False)
        if not cells:
            continue
        if len(cells) != len(headers):
            raise ValueError("Unexpected timetable row")
        values = [c.get_text(" ", strip=True).replace("\xa0", " ").replace("\ufffd", "").strip() for c in cells]
        record = dict(zip(headers, values))
        if record["module"].upper() != code:
            raise ValueError("Returned module does not match request")
        date = datetime.strptime(record["date"], "%d-%b-%y")
        if date.strftime("%A").lower() != record["day"].lower() or not re.fullmatch(r"\d{2}:\d{2}", record["time"]):
            raise ValueError("Unrecognised date or time")
        datetime.strptime(record["time"], "%H:%M")
        start = int(year[:4])
        if date.year not in {start, start + 1}:
            raise ValueError("Exam date does not match published academic year")
        record["date_iso"] = date.date().isoformat()
        rows.append(record)
    if not rows:
        raise ValueError("No confirmed exam rows returned")
    return rows


class ExamTimetable:
    def __init__(self, transport=None, clock=time.monotonic, delay=3):
        self.transport, self.clock, self.delay = transport, clock, delay
        self.cache = OrderedDict()
        self.lock = threading.Lock()
        self.last_request = -float("inf")

    def _request(self, client, method, **kwargs):
        wait = self.delay - (self.clock() - self.last_request)
        if wait > 0:
            time.sleep(wait)
        self.last_request = self.clock()
        response = client.request(method, SOURCE, **kwargs)
        response.raise_for_status()
        return response.text

    def lookup(self, code, academic_year=None, session=None):
        code = code.strip().upper()
        if not CODE.fullmatch(code):
            raise ValueError("Enter a module code such as CS4141")
        key = (code, academic_year, session.lower() if session else None)
        with self.lock:
            previous = self.cache.get(key)
            if previous and self.clock() < previous[0]:
                self.cache.move_to_end(key)
                return deepcopy(previous[1])
            result = {"module":code, "source_url":SOURCE, "checked_at":None, "session":None, "academic_year":None, "rows":[], "status":"unavailable"}
            try:
                with httpx.Client(timeout=12, follow_redirects=False, transport=self.transport,
                                  headers={"User-Agent":"ULNavigatorAI/1.4 (public module exam lookup)"}) as client:
                    html = self._request(client, "GET")
                    soup, shown_session, year = page(html)
                    result.update(session=shown_session, academic_year=year)
                    if (academic_year and academic_year != year) or (session and session.lower() != shown_session.lower()):
                        result.update(status="session_mismatch", note="The source currently publishes a different exam session. No appointment is confirmed for your requested session.")
                    else:
                        select = soup.find("select", id="HeaderContent_ExamModuleDropdown")
                        if select is None or not select.get("name"):
                            raise ValueError("Module selector unavailable")
                        choices = {o.get("value", "").upper() for o in select.find_all("option")}
                        if code not in choices:
                            result.update(status="not_listed", note="This code is not listed in the currently published module selector. This does not prove that you have no exam.")
                        else:
                            data = {i["name"]:i.get("value", "") for i in soup.select('input[type="hidden"][name]')}
                            if "__VIEWSTATE" not in data or "__EVENTVALIDATION" not in data:
                                raise ValueError("Timetable form could not be verified")
                            data.update({select["name"]:code, "__EVENTTARGET":select["name"], "__EVENTARGUMENT":""})
                            html = self._request(client, "POST", data=data)
                            result.update(status="found", rows=parse_rows(html, code, shown_session, year), note="Times and venues are shown as published by UL. Check your personal timetable and any individual arrangements before attending.")
                    result["checked_at"] = datetime.now(timezone.utc).isoformat()
            except (httpx.HTTPError, ValueError, KeyError):
                if previous and previous[1]["status"] in {"found", "stale"} and self.clock() - previous[2] < 86400:
                    result = deepcopy(previous[1])
                    result.update(status="stale", note="UL could not be rechecked. These are older saved details, not a current confirmation. Open the official timetable before acting.")
                else:
                    result.update(status="unavailable", rows=[], note="The official timetable could not be verified. Open UL's timetable directly; no exam appointment is confirmed here.")
            ttl = 600 if result["status"] == "found" else 60 if result["status"] in {"stale", "unavailable"} else 300
            saved_at = previous[2] if result["status"] == "stale" else self.clock()
            self.cache[key] = (self.clock() + ttl, deepcopy(result), saved_at)
            self.cache.move_to_end(key)
            while len(self.cache) > 256:
                self.cache.popitem(last=False)
            return result


_timetable = ExamTimetable()
lookup_exam = _timetable.lookup

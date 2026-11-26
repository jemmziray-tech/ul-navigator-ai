from datetime import datetime
import httpx
import pytest
from app.tools.exams import ExamTimetable, parse_rows


def html(code="CS4141", selected=False, row=True):
    day = datetime(2030, 12, 9).strftime("%A")
    return f'''<p>The Autumn 2030/31 Exam Timetable is now available.</p>
    <input type="hidden" name="__VIEWSTATE" value="fixture-state">
    <input type="hidden" name="__EVENTVALIDATION" value="fixture-validation">
    <select id="HeaderContent_ExamModuleDropdown" name="module-choice"><option value="{code}" {'selected' if selected else ''}>{code}</option></select>
    <table id="MainContent_ExamTimetableGridView"><tr>{''.join('<th>'+x+'</th>' for x in ['Module','Name','Date','Time','Day','Building','Location','Information'])}</tr>
    {f'<tr><td>{code}</td><td>TEST PROGRAMMING</td><td>09-Dec-30</td><td>16:00</td><td>{day}</td><td>MAIN5</td><td>TEST10</td><td>Check personal arrangements</td></tr>' if row else ''}</table>'''


def client(now=None, fail=None, returned="CS4141"):
    calls = []
    def handle(request):
        calls.append(request)
        assert str(request.url) == "https://www.timetable.ul.ie/UA/ExamModuleTimetable.aspx"
        if fail and fail[0]: return httpx.Response(503)
        if request.method == "POST":
            assert b'module-choice=CS4141' in request.content
            return httpx.Response(200, text=html(returned, True))
        return httpx.Response(200, text=html())
    return ExamTimetable(httpx.MockTransport(handle), clock=lambda: now[0] if now else 0, delay=0), calls


def test_verified_lookup_posts_module_and_preserves_all_source_fields():
    lookup, calls = client()
    r = lookup.lookup("cs4141")
    assert r["status"] == "found" and r["academic_year"] == "2030/31"
    assert r["rows"][0]["date_iso"] == "2030-12-09" and r["rows"][0]["time"] == "16:00"
    assert r["rows"][0]["building"] == "MAIN5" and r["rows"][0]["location"] == "TEST10"
    r["rows"].clear()
    assert lookup.lookup("CS4141")["rows"] and len(calls) == 2


def test_stale_result_is_labelled_and_discarded_after_one_day():
    now, fail = [0], [False]
    lookup, _ = client(now, fail)
    first = lookup.lookup("CS4141"); now[0] = 601; fail[0] = True
    stale = lookup.lookup("CS4141")
    assert stale["status"] == "stale" and stale["checked_at"] == first["checked_at"]
    now[0] = 90000
    assert lookup.lookup("CS4141")["status"] == "unavailable"
    assert not lookup.lookup("CS4141")["rows"]


def test_different_session_does_not_return_another_sessions_dates():
    lookup, calls = client()
    r = lookup.lookup("CS4141", "2029/30")
    assert r["status"] == "session_mismatch" and not r["rows"] and len(calls) == 1
    assert lookup.lookup("CS4141", session="spring")["status"] == "session_mismatch"


def test_missing_code_is_not_a_claim_of_no_exam():
    lookup, calls = client()
    r = lookup.lookup("XX9999")
    assert r["status"] == "not_listed" and "does not prove" in r["note"] and len(calls) == 1
    with pytest.raises(ValueError): lookup.lookup("https://example.com")


def test_mismatched_module_or_unconfirmed_selection_is_rejected():
    lookup, _ = client(returned="CS4221")
    assert lookup.lookup("CS4141")["status"] == "unavailable"
    with pytest.raises(ValueError): parse_rows(html(selected=False), "CS4141", "Autumn", "2030/31")
    with pytest.raises(ValueError): parse_rows(html(selected=True).replace("16:00", "25:00"), "CS4141", "Autumn", "2030/31")
    with pytest.raises(ValueError): parse_rows(html(selected=True, row=False), "CS4141", "Autumn", "2030/31")


def test_chat_uses_verified_rows_and_respects_explicit_year(fresh_env, monkeypatch):
    from app.rag import exam_schedule, pipeline
    lookup, _ = client()
    monkeypatch.setattr(exam_schedule, "lookup_exam", lookup.lookup)
    r = pipeline.run("When is the exam for CS4141 in 2030/31?")
    assert "2030-12-09" in r.answer and "16:00" in r.answer and "TEST10" in r.answer
    r = pipeline.run("When is the exam for CS4141 in 2029/30?")
    assert "2030-12-09" not in r.answer and "different exam session" in r.answer
    r = pipeline.run("When is the exam for CS4141?", academic_year="2029/30")
    assert "2030-12-09" not in r.answer and not r.answered

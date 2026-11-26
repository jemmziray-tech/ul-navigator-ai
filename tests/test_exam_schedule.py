import pytest


@pytest.mark.parametrize("query", ["when is the exam for CS4141?", "CS4141 exam date", "What time is my CS4141 examination?", "When are autumn exams?"])
def test_exam_dates_are_calendar_questions(fresh_env, query):
    from app.rag.classifier import analyse
    assert analyse(query).category == "calendar"


@pytest.mark.parametrize("query", ["What does CS4141 cover?", "Does CS4141 have an exam assessment?", "What is the repeat exam fee?", "When are exam results released?"])
def test_non_schedule_queries_are_not_hijacked(query):
    from app.rag.exam_schedule import exam_timing
    assert not exam_timing(query)


def test_module_exam_dates_never_infer_from_descriptor_or_history(fresh_env, monkeypatch):
    from app.rag import pipeline
    monkeypatch.setattr(pipeline, "get_llm", lambda: (_ for _ in ()).throw(AssertionError("Must not generate an exam appointment")))
    monkeypatch.setattr(pipeline, "get_index", lambda: (_ for _ in ()).throw(AssertionError("Must not use teaching descriptors")))
    result = pipeline.run("when is the exam for CS4141?", history=[{"role":"assistant", "content":"Autumn exams are 05 December to 19 December 2026."}])
    assert "ExamModuleTimetable.aspx" in result.answer and "CS4141" in result.answer
    assert "05 December" not in result.answer and "19 December" not in result.answer
    assert result.mode == "system" and not result.answered and not result.citations


def test_unverified_dates_are_removed_before_any_token_is_sent(loaded_index, monkeypatch):
    from app.rag import pipeline
    class InventedDate:
        def stream(self, *args, **kwargs):
            yield "Borrow books until 05 December 2099 [S1]."
    monkeypatch.setattr(pipeline, "get_llm", lambda: InventedDate())
    events = list(pipeline.run_stream("How many books can undergraduates borrow?"))
    result = events[-1]["result"]
    assert result.mode == "extractive" and result.citations
    assert "unverified_generation_replaced" in result.flags
    assert all("05 December" not in e.get("text", "") for e in events)


def test_date_validation_includes_year_and_iso_dates():
    from app.rag.citations import validate
    sources = [{"id":"S1", "excerpt":"Exam 05 December 2026. Updated 2026-11-26."}]
    assert validate("Exam 05 December 2027 [S1].", sources).unverified_figures == ["05 December 2027"]
    assert validate("Exam 2026-12-05 [S1].", sources).unverified_figures == ["2026-12-05"]


def test_deterministic_timetable_guidance_does_not_use_generation_allowance(fresh_env):
    from types import SimpleNamespace
    from app.api.chat import _budget_cost
    request = SimpleNamespace(state=SimpleNamespace())
    _budget_cost(request, SimpleNamespace(question="When is the exam for CS4141?"))
    assert request.state.generation_cost == 0

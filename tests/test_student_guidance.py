from pathlib import Path
import json
from types import SimpleNamespace

import pytest


def history(state):
    return [{"role": "assistant", "content": "A clarification", "clarification": state}]


def test_fee_flow_keeps_original_and_does_not_infer_status():
    from app.rag.clarification import clarify
    a = clarify("How much are tuition fees?", [])
    assert a.state["missing_field"] == "programme"
    b = clarify("LM174", history(a.state))
    assert b.state["missing_field"] == "fee_category"
    c = clarify("I am an EU citizen", history(b.state))
    assert c.state["missing_field"] == "fee_category"
    d = clarify("Non-EU", history(c.state))
    assert d.state["missing_field"] == "academic_year"
    e = clarify("2026/27", history(d.state))
    assert e.state is None
    assert all(v in e.question for v in ["tuition fees", "LM174", "Non-EU", "2026/27"])


def test_clarification_exit_and_new_topic():
    from app.rag.clarification import clarify
    a = clarify("What are the entry requirements?", [])
    assert a.state
    assert clarify("How is QCA calculated?", history(a.state)).state is None
    assert "general overview" in clarify("Answer generally", history(a.state)).question
    assert clarify("How do I pay my tuition fees?", []).state is None
    b = clarify("How much are Non-EU fees for LM174?", [])
    assert b.state["missing_field"] == "academic_year"
    assert "unknown" in clarify("I'm not sure about my fee status", history(
        clarify("LM174", history(clarify("How much are tuition fees?", []).state)).state)).question


def test_applicant_route_and_qualification():
    from app.rag.clarification import clarify
    a = clarify("What are entry requirements for LM174?", [])
    assert a.state["missing_field"] == "route"
    b = clarify("International qualification", history(a.state))
    assert b.state["missing_field"] == "qualification"
    c = clarify("A-levels from Tanzania", history(b.state))
    assert not c.state and "A-levels from Tanzania" in c.question


def test_qca_rules_consistent_and_boundaries_not_rounded_up():
    from app.tools.qca import classify, QCARequest, calculate, rules
    assert classify(3.3) == "First class honours"
    assert "2.1" in classify(3.2999)
    assert "2.2" in classify(2.8999)
    assert "D2" not in {g["grade"] for g in rules()["grades"]}
    front = Path(__file__).resolve().parents[1] / "frontend/src/data/qca-rules.json"
    assert json.loads(front.read_text(encoding="utf-8")) == rules()
    req = QCARequest(modules=[{"credits": 1, "grade": "A2"}, {"credits": 3.1, "grade": "B1"}])
    r = calculate(req)
    assert r["qca"] == 3.3 and "2.1" in r["classification"]


def test_immigration_contact_and_social_scope(fresh_env):
    from app.rag.classifier import analyse
    from app.rag.pipeline import run
    a = analyse("How do I register with immigration after arriving?")
    assert a.category == "international" and a.high_stakes
    r = run("I wanna be married at UL can i get a wife?")
    assert r.mode == "system" and "partner" in r.answer
    assert "authoritative" not in r.answer
    assert analyse("What wedding venues does UL offer?").intent == "question"


def test_source_policy_keeps_news_for_news_but_not_rules():
    from app.rag.source_policy import source_role, policy_weight
    role = source_role("https://www.ul.ie/news/student-story", "A student's experience")
    assert role == "editorial"
    assert not policy_weight("What are tuition fees?", role, False, False)[1]
    assert policy_weight("Latest news about tuition fees", role, False, False)[1]
    assert policy_weight("QCA", "guidance", True, False)[0] < policy_weight("QCA", "guidance", False, False)[0]


def test_gemini_max_tokens_is_not_a_successful_stream():
    from app.rag.llm import GeminiLLM, LLMUnavailable
    llm = GeminiLLM.__new__(GeminiLLM)
    llm.model = "test"
    llm.settings = SimpleNamespace(gemini_fallback_model=None, gemini_max_retries=1)
    llm._config = lambda *args: None
    chunks = [SimpleNamespace(text="Partial **answer", candidates=[]),
              SimpleNamespace(text=None, candidates=[SimpleNamespace(finish_reason=SimpleNamespace(name="MAX_TOKENS"))])]
    llm.client = SimpleNamespace(models=SimpleNamespace(generate_content_stream=lambda **kwargs: iter(chunks)))
    with pytest.raises(LLMUnavailable):
        list(llm.stream("question", "system"))


def test_gemini_thinking_does_not_swallow_small_answer_budget():
    from app.rag.llm import GeminiLLM
    from google.genai import types
    llm = GeminiLLM.__new__(GeminiLLM)
    llm.model = "gemini-3.8-flash"
    llm._types = types
    llm.settings = SimpleNamespace(gemini_temperature=.2, gemini_max_output_tokens=1000)
    config = llm._config("system", None, None)
    assert config.max_output_tokens == 1000
    assert config.thinking_config.thinking_level.value == "LOW"
    assert llm._config("system", None, None, "gemini-3.1-flash-lite").thinking_config.thinking_level.value == "MINIMAL"


@pytest.mark.parametrize("interrupted", [False, True])
def test_partial_or_uncited_generation_is_replaced_with_cited_excerpts(loaded_index, monkeypatch, interrupted):
    from app.rag import pipeline
    from app.rag.llm import LLMUnavailable
    class Partial:
        def stream(self, *args):
            yield "An unsupported **unfinished answer ("
            if interrupted:
                raise LLMUnavailable("MAX_TOKENS")
    monkeypatch.setattr(pipeline, "get_llm", lambda: Partial())
    events = list(pipeline.run_stream("How many books can undergraduates borrow?"))
    result = events[-1]["result"]
    assert result.mode == "extractive" and result.citations
    assert "unsupported" not in result.answer
    assert any(e["type"] == "reset" for e in events)


def test_source_policy_survives_reranker(fresh_env, monkeypatch):
    from app.rag import retriever
    from app.rag.knowledge_index import ChunkRecord
    records = {
        1: ChunkRecord(1, "news", "Tuition fees in a student news story", "", None, "fees", "2026/27", "Student story", "https://www.ul.ie/news/story", "html", ""),
        2: ChunkRecord(2, "current", "Tuition fees in official student guidance", "", None, "fees", "2026/27", "Fees guidance", "https://www.ul.ie/fees", "html", ""),
        3: ChunkRecord(3, "old", "Tuition fees from an earlier academic year", "", None, "fees", "2025/26", "Earlier fees", "https://www.ul.ie/fees/archive", "html", ""),
    }
    index = SimpleNamespace(records=records, semantic_search=lambda *a: [(1, .9), (3, .85), (2, .8)], keyword_search=lambda *a: [(1, 5), (3, 4), (2, 3)])
    monkeypatch.setattr(retriever, "directory_records", lambda *a: [])
    monkeypatch.setattr(retriever, "get_reranker", lambda: SimpleNamespace(score=lambda q, texts: [.9] * len(texts)))
    result = retriever.retrieve(index, "tuition fees", academic_year="2026/27")
    assert result.hits[0].record.id == 2
    assert all(h.record.id != 1 for h in result.relevant_hits)

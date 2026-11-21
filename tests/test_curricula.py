"""Synthetic structure fixtures: not statements about actual UL programmes."""
from types import SimpleNamespace
import json
import pytest

HTML = '''<main><a id="year">Year 1</a><section class="tabs__panel" aria-labelledby="year" id="y1">
<h2>Semester 1</h2><table><tr><th>Module code</th><th>Module title</th></tr><tr><td>NB4001</td><td>Foundations</td></tr><tr><td>NB4002</td><td>Programming</td></tr></table>
<h2>Semester 2</h2><p>Cooperative education placement</p></section>
<a id="bsc">Year 4 (BSc Pathway)</a><section class="tabs__panel" aria-labelledby="bsc" id="bsc4"><h2>Semester 7</h2><table><tr><th>Module code</th><th>Module title</th></tr><tr><td>NB4007</td><td>Project</td></tr></table></section>
<a id="msc">Year 4 (MSc Pathway)</a><section class="tabs__panel" aria-labelledby="msc" id="msc4"><h2>Semester 7</h2><h3>Electives: choose one</h3><ul><li><a href="https://bookofmodules.ul.ie/Default.aspx?ModuleCodeParameter=|NB6001|">Research (NB6001)</a>Research methods content.</li><li><a href="https://bookofmodules.ul.ie/Default.aspx?ModuleCodeParameter=|NB6002|">Design (NB6002)</a>Design methods content.</li></ul></section></main>'''


def course():
    from ul_ingest.curricula import parse_curriculum
    return parse_curriculum(HTML, {"id": "fixture", "title": "Synthetic Computing - BSc or MSc", "code": "LM999"}, "https://fixture.example/course-content", "2026-11-21T12:00:00Z")


def test_course_tabs_keep_year_semester_pathway_and_placement():
    c = course()
    assert len(c["sections"]) == 4
    assert [m["code"] for m in c["sections"][0]["modules"]] == ["NB4001", "NB4002"]
    assert c["sections"][1]["modules"] == [] and "placement" in c["sections"][1]["notes"][0]
    assert "BSc" in c["sections"][2]["yearLabel"] and "MSc" in c["sections"][3]["yearLabel"]
    assert c["sections"][3]["modules"][0]["group"] == "Electives: choose one"
    assert c["academicYear"] is None
    assert c["sections"][0]["sourceUrl"].endswith("#y1")


def test_side_by_side_semester_columns_are_not_combined():
    from ul_ingest.curricula import parse_curriculum
    html = '<main><h2>Year 1</h2><table><tr><th>Semester 1</th><th>Semester 2</th></tr><tr><td>NB4001 Foundations</td><td>NB4002 Programming</td></tr></table></main>'
    result = parse_curriculum(html, {"id":"x","title":"Fixture"}, "https://fixture.example/c", "today")
    assert [[m["code"] for m in s["modules"]] for s in result["sections"]] == [["NB4001"], ["NB4002"]]


def test_descriptor_requires_identity_not_a_prerequisite_mention():
    from ul_ingest.curricula import parse_module
    html = '<p>Module Code - Title:</p><p>NB4001 - FOUNDATIONS</p><p>Year Last Offered:</p><p>2026/7</p><p>Credits</p><p>6</p><p>Prerequisite Modules:</p><p>NB4002</p><p>Syllabus:</p><p>Algorithms and data.</p><p>Module Leader:</p><p>staff@fixture.example</p>'
    assert parse_module(html, "NB4002", "today") is None
    result = parse_module(html, "NB4001", "today")
    assert result["title"] == "FOUNDATIONS"
    assert "## Syllabus" in result["markdown"] and "staff@" not in result["markdown"]
    assert "**Credits:**\n6" in result["markdown"]


def test_small_semesters_do_not_merge_when_preservation_is_requested():
    from ul_ingest.chunking import chunk_markdown
    md = "# Programme\n## Year 1 Semester 1\nNB4001 Foundations module.\n## Year 1 Semester 2\nNB4002 Programming module."
    chunks = chunk_markdown(md, min_words=40, preserve_sections=True)
    assert len(chunks) == 2
    assert "NB4002" not in chunks[0].text and "Semester 1" in chunks[0].section


def test_curriculum_context_resolves_history_but_not_an_example_in_a_clarification(monkeypatch):
    from app.rag import curricula
    from app.rag.clarification import clarify
    monkeypatch.setattr(curricula, "catalogue", lambda: [course()])
    q = "How many modules are there in first semester of 1st year?"
    r = clarify(q, [{"role":"user","content":"I study LM999"}])
    assert r.state is None and "LM999" in r.question
    assert len(curricula.select_sections(course(), r.question)) == 1
    r = clarify(q, [])
    assert r.state["missing_field"] == "programme"
    hist = [{"role":"assistant","content":"For example LM999", "clarification":r.state}]
    assert curricula.resolve_course("Year 1", hist) is None
    assert "LM999" in clarify("LM999", hist).question


def test_pathway_ambiguity_requires_a_choice(monkeypatch):
    from app.rag import curricula
    from app.rag.clarification import clarify
    monkeypatch.setattr(curricula, "catalogue", lambda: [course()])
    a = clarify("Which modules in Year 4 Semester 7 for LM999?", [])
    assert a.state["missing_field"] == "pathway"
    b = clarify("MSc pathway", [{"role":"assistant", "clarification":a.state, "content":a.answer}])
    selected = curricula.select_sections(course(), b.question)
    assert len(selected) == 1 and "MSc" in selected[0]["yearLabel"]


def test_exact_semester_passage_is_injected_and_preserved(loaded_index, monkeypatch):
    from app.rag import curricula
    from app.rag.retriever import retrieve
    from ul_ingest.curricula import curriculum_markdown
    from ul_ingest.pipeline import DocInput, JobReport, upsert_document
    c = course(); monkeypatch.setattr(curricula, "catalogue", lambda: [c])
    upsert_document(loaded_index, DocInput(url=c["url"], title="Curriculum | LM999", markdown=curriculum_markdown(c), kind="txt", category="modules", preserve_sections=True), JobReport("test"))
    loaded_index.reload()
    result = retrieve(loaded_index, "Which modules for LM999 year 1 semester 1?")
    assert result.hits[0].curriculum_match
    assert "NB4001" in result.hits[0].record.text and "NB4007" not in result.hits[0].record.text


def test_cached_snapshot_installs_without_replacing_conversations(fresh_env, tmp_path):
    from app.db import Conversation, session_scope
    from app.rag.knowledge_index import get_index
    from ul_ingest.curriculum_index import install_snapshot
    with session_scope() as db: db.add(Conversation(id="keep-test-chat", client_id="fixture-client", title="Keep this"))
    (tmp_path / "curricula.json").write_text(json.dumps({"courses":[course()]}), encoding="utf-8")
    idx = get_index()
    with pytest.raises(ValueError, match="vectors are incomplete"):
        install_snapshot(idx, tmp_path)
    first = install_snapshot(idx, tmp_path, require_cache=False)
    assert first["documents"] == 1
    assert install_snapshot(idx, tmp_path)["documents"] == 0
    with session_scope() as db: assert db.get(Conversation, "keep-test-chat").title == "Keep this"


def test_explicit_semester_numbers_take_precedence_over_adjacent_year_numbers():
    from app.rag.curricula import semester, study_year
    assert semester("Year 4 Semester 7") == 7
    assert semester("Semester 11") == 11
    assert semester("11th semester of year 6") == 11
    assert study_year("Semester 1 Year 2") == 2

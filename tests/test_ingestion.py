"""Extraction, chunking, crawling and incremental indexing."""
from __future__ import annotations

import httpx
from sqlalchemy import func, select

from synthetic_corpus import ACCOM_HTML, CAL_HTML, CORPUS, FEES_HTML, MODULES_CSV, make_handbook_pdf


def test_html_extraction_removes_chrome_and_keeps_structure():
    from ul_ingest.extractors import extract_html
    ex = extract_html(FEES_HTML, "u")
    assert ex.title == "Tuition Fees 2030/31"
    assert "We use cookies" not in ex.markdown
    assert "Home" not in ex.markdown.split("\n")[0]
    assert "## Non-EU undergraduate fees" in ex.markdown
    assert "| Science and Engineering | €19,750 |" in ex.markdown  # table preserved


def test_boilerplate_detection():
    from ul_ingest.extractors import extract_html, find_boilerplate_lines, remove_boilerplate
    docs = [extract_html(b, "u").markdown for _, _, b in CORPUS.values()]
    docs = [d + "\nShared promo line on every page" for d in docs]
    bp = find_boilerplate_lines(docs, min_docs=3)
    assert "Shared promo line on every page" in bp
    assert "Shared promo line" not in remove_boilerplate(docs[0], bp)


def test_pdf_extraction_pages_and_headings(tmp_path):
    from ul_ingest.extractors import extract_pdf
    p = tmp_path / "h.pdf"
    make_handbook_pdf(p)
    ex = extract_pdf(p.read_bytes())
    assert ex.page_count == 2
    assert "<!-- page: 2 -->" in ex.markdown
    assert "Repeat Examinations" in ex.markdown
    assert "240 euro" in ex.markdown


def test_csv_extraction_book_of_modules_export():
    from ul_ingest.extractors import extract_csv
    ex = extract_csv(MODULES_CSV.encode(), "Modules")
    assert "## NB4012 Introduction to Machine Learning" in ex.markdown
    assert "**Credits:** 6" in ex.markdown


def test_chunking_sections_overlap_and_tables():
    from ul_ingest.chunking import chunk_markdown
    from ul_ingest.extractors import extract_html
    md = extract_html(CAL_HTML, "u").markdown
    chunks = chunk_markdown(md, size=60, overlap=10, min_words=5)
    assert any("Autumn semester" in c.section for c in chunks)
    table_chunks = [c for c in chunks if "|" in c.text]
    assert table_chunks and all(c.text.splitlines()[0].startswith("|") for c in table_chunks)
    long = "# T\n\n" + " ".join(f"word{i}." for i in range(700))
    parts = chunk_markdown(long, size=200, overlap=30, min_words=20)
    assert len(parts) >= 3
    assert all(p.word_count <= 240 for p in parts)
    # overlap: the start of chunk 2 repeats the end of chunk 1
    assert parts[0].text.split()[-1] in parts[1].text.split()[:40]


def test_chunk_page_numbers(tmp_path):
    from ul_ingest.chunking import chunk_markdown
    from ul_ingest.extractors import extract_pdf
    p = tmp_path / "h.pdf"
    make_handbook_pdf(p)
    chunks = chunk_markdown(extract_pdf(p.read_bytes()).markdown, size=40, overlap=0, min_words=5)
    pages = {c.page for c in chunks}
    assert pages == {1, 2}
    assert any("Repeat" in c.section and c.page == 2 for c in chunks)


def _mock_transport(routes: dict, calls: list):
    def handler(request: httpx.Request):
        calls.append((request.method, str(request.url), dict(request.headers)))
        fn = routes.get(str(request.url))
        if fn is None:
            return httpx.Response(404)
        return fn(request)
    return httpx.MockTransport(handler)


def test_fetcher_obeys_robots_and_retries(tmp_path, monkeypatch):
    from ul_ingest import crawler
    monkeypatch.setattr(crawler.time, "sleep", lambda s: None)
    state = {"n": 0}

    def flaky(_):
        state["n"] += 1
        return httpx.Response(503) if state["n"] < 2 else httpx.Response(
            200, html=FEES_HTML, headers={"ETag": '"v1"'})

    def cond(req):
        if req.headers.get("if-none-match") == '"v1"':
            return httpx.Response(304)
        return httpx.Response(200, html=FEES_HTML, headers={"ETag": '"v1"'})

    calls: list = []
    routes = {
        "https://site.example/robots.txt": lambda _: httpx.Response(
            200, text="User-agent: *\nDisallow: /private\n"),
        "https://site.example/fees": flaky,
        "https://site.example/cond": cond,
    }
    f = crawler.PoliteFetcher("TestBot/1.0", tmp_path, delay_s=0,
                              transport=_mock_transport(routes, calls))
    blocked = f.fetch("https://site.example/private/x")
    assert not blocked.ok and "robots" in blocked.error
    assert not any("/private" in c[1] for c in calls)
    ok = f.fetch("https://site.example/fees")
    assert ok.ok and state["n"] == 2  # retried after 503
    first = f.fetch("https://site.example/cond")
    second = f.fetch("https://site.example/cond")
    assert first.ok and second.not_modified and second.content == first.content


def test_robots_unreachable_disallows(tmp_path):
    from ul_ingest import crawler
    calls: list = []
    routes = {"https://down.example/robots.txt": lambda _: httpx.Response(503)}
    f = crawler.PoliteFetcher("TestBot", tmp_path, delay_s=0,
                              transport=_mock_transport(routes, calls))
    assert f.fetch("https://down.example/page").error == "disallowed by robots.txt"


def test_crawl_scope_filters_links():
    from ul_ingest.crawler import CrawlScope, extract_links
    scope = CrawlScope.from_config({
        "allowed_hosts": ["www.ul.ie"], "allowed_path_prefixes": ["/fees", "/media/"],
        "exclude_patterns": ["/login", r"\.jpg$"]})
    html = """<a href="/fees/payment">a</a><a href="/news/x">b</a><a href="/login">c</a>
    <a href="https://evil.example/fees">d</a><a href="/media/doc/download">e</a>
    <a href="/fees/x.jpg">f</a><a href="/fees/payment#top">dup</a>"""
    links = extract_links(html, "https://www.ul.ie/fees", scope)
    assert links == ["https://www.ul.ie/fees/payment", "https://www.ul.ie/media/doc/download"]


def test_crawl_end_to_end_with_mock_site(fresh_env, monkeypatch):
    from ul_ingest import crawler, pipeline

    from app.config import get_settings
    from app.db import Document, IngestionJob, session_scope
    monkeypatch.setattr(crawler.time, "sleep", lambda s: None)
    calls: list = []
    hub = """<html><body><main><h1>Student hub</h1><p>Welcome to the student information hub
    with links to fees and accommodation information for all students of the university.
    Use the links below to find official guidance, deadlines and contacts for each service.</p>
    <a href="/fees">Fees</a><a href="/accommodation">Accom</a><a href="/missing">Gone</a>
    </main></body></html>"""
    routes = {
        "https://site.example/robots.txt": lambda _: httpx.Response(200, text="User-agent: *\n"),
        "https://site.example/hub": lambda _: httpx.Response(200, html=hub),
        "https://site.example/fees": lambda _: httpx.Response(200, html=FEES_HTML),
        "https://site.example/accommodation": lambda _: httpx.Response(200, html=ACCOM_HTML),
    }
    s = get_settings()
    fetcher = crawler.PoliteFetcher("TestBot", s.raw_dir, delay_s=0,
                                    transport=_mock_transport(routes, calls))
    sources = {"allowed_hosts": ["site.example"], "allowed_path_prefixes": ["/"],
               "exclude_patterns": [], "category_rules": [["accommodation", "accommodation"],
                                                         ["fees", "fees"]],
               "seeds": [{"url": "https://site.example/hub", "category": "general"}]}
    out = pipeline.crawl(max_pages=10, max_depth=1, fetcher=fetcher, sources=sources)
    assert out["new"] == 3 and out["failed"] == 1  # /missing -> 404 is reported, not hidden
    assert any(f["url"].endswith("/missing") for f in out["failures"])
    with session_scope() as db:
        cats = {d.url: d.category for d in db.scalars(select(Document)).all()}
        assert cats["https://site.example/accommodation"] == "accommodation"
        assert db.scalar(select(func.count()).select_from(IngestionJob)) == 1
    again = pipeline.crawl(max_pages=10, max_depth=1, fetcher=fetcher, sources=sources)
    assert again["unchanged"] == 3 and again["new"] == 0


def test_incremental_update_duplicate_delete_reconcile(loaded_index):
    from ul_ingest.pipeline import (DocInput, JobReport, delete_document, find_duplicates,
                                    reconcile, upsert_document)

    from app.db import Chunk, Document, session_scope
    idx = loaded_index
    url = "https://test.northbridge.example/library"
    report = JobReport("t")
    md = "# Library Services\n\n## Opening hours\n\nThe library now opens 24 hours a day during exam periods for all registered students of the university. Study rooms can be booked online and quiet zones are available on every floor of the building."
    assert upsert_document(idx, DocInput(url, "html", "Library Services", md, "library"), report) == "updated"
    assert upsert_document(idx, DocInput(url, "html", "Library Services", md, "library"), report) == "unchanged"
    with session_scope() as db:
        doc = db.scalar(select(Document).where(Document.url == url))
        new_ids = {c.id for c in doc.chunks}
    assert new_ids <= idx.store.ids()
    # duplicate content at another URL is detected and not indexed twice
    dup = DocInput(url + "-copy", "html", "Library copy", md, "library")
    assert upsert_document(idx, dup, report) == "duplicate"
    assert any(d["url"].endswith("-copy") for d in find_duplicates())
    # delete + reconcile keep FAISS and DB consistent
    idx.persist()
    assert delete_document(url, idx)
    assert not (new_ids & idx.store.ids())
    idx.store.add([999999], idx.embedder.encode(["orphan"]))  # simulate drift
    res = reconcile(idx)
    assert res["orphan_vectors_removed"] >= 1
    with session_scope() as db:
        n_chunks = db.scalar(select(func.count()).select_from(Chunk).join(Document)
                             .where(Document.status == "indexed"))
    assert idx.store.size == n_chunks


def test_fetcher_slows_down_after_429(tmp_path, monkeypatch):
    from ul_ingest import crawler
    sleeps: list = []
    monkeypatch.setattr(crawler.time, "sleep", lambda s: sleeps.append(s))
    state = {"n": 0}

    def limited(_):
        state["n"] += 1
        return httpx.Response(429, headers={"Retry-After": "7"}) if state["n"] == 1 else \
            httpx.Response(200, html=FEES_HTML)

    calls: list = []
    routes = {"https://rl.example/robots.txt": lambda _: httpx.Response(200, text=""),
              "https://rl.example/p": limited, "https://rl.example/q": lambda _: httpx.Response(200, html=FEES_HTML)}
    f = crawler.PoliteFetcher("TestBot", tmp_path, delay_s=1.0,
                              transport=_mock_transport(routes, calls), cache_ttl_s=3600)
    assert f.fetch("https://rl.example/p").ok
    assert 7 in sleeps and f._host_delay["rl.example"] >= 5.0  # honoured Retry-After, slowed down
    n = len(calls)
    assert f.fetch("https://rl.example/p").from_cache and len(calls) == n  # fresh cache: no request


def test_expanded_sources_are_official_unique_and_categorized():
    from urllib.parse import urlparse
    from ul_ingest.pipeline import load_sources, categorize
    cfg = load_sources()
    urls = [s["url"] for s in cfg["seeds"]]
    assert len(urls) == len(set(urls))
    assert all(url == url.strip() for url in urls)
    assert all(urlparse(u).hostname in cfg["allowed_hosts"] for u in urls)
    assert any("alphabetical-list-of-courses" in u for u in urls)
    rules = cfg["category_rules"]
    for path, category in [
        ("/student-affairs/counselling-service", "student_support"),
        ("/student-affairs/disability-services", "student_support"),
        ("/ctl/mlc", "student_support"),
        ("/ctl/writing-centre", "student_support"),
        ("/sportsscholarships", "scholarships"),
    ]:
        assert categorize("https://www.ul.ie" + path, rules, "general") == category



def test_book_of_modules_details_inside_form_are_preserved():
    from ul_ingest.extractors import extract_html
    html = """<html><body><form><input value='search'>
    <div id='ctl00_MasterContentPlaceHolder_ModuleFull_ListViewUpdatePanel'>
    <div class='ModuleLayoutStyle'><h1>Module Code - Title:</h1>NB6005 - TEST RESEARCH PROJECT</div>
    <p>Credits 9</p><p>Learning Outcomes: Develop research and analysis skills.</p>
    <div class='DataPagerStyle'>Page navigation controls</div></div></form></body></html>"""
    result = extract_html(html, "https://www.bookofmodules.ul.ie/Default.aspx?ModuleCodeParameter=%7CNB6005%7C")
    assert result.title == "NB6005 - TEST RESEARCH PROJECT"
    assert "Credits 9" in result.markdown
    assert "Develop research" in result.markdown
    assert "Page navigation controls" not in result.markdown
    # Generic forms on unrelated sites remain excluded.
    assert "Develop research" not in extract_html(html, "https://example.com").markdown


def test_book_of_modules_url_parameter_is_not_stripped():
    from ul_ingest.crawler import CrawlScope
    scope = CrawlScope(["www.bookofmodules.ul.ie"], ["/Default.aspx"])
    base = "https://www.bookofmodules.ul.ie/"
    url = scope.normalize(base, "Default.aspx?ModuleCodeParameter=%7CNB6005%7C&tracking=1")
    assert url.endswith("?ModuleCodeParameter=%7CNB6005%7C")
    assert scope.allows(url)
    assert scope.normalize("https://example.com", "/Default.aspx?ModuleCodeParameter=%7CNB6005%7C").endswith("/Default.aspx")

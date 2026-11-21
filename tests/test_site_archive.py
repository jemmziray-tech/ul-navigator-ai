"""Public crawl boundaries and durable progress, using fictional page text."""
import json

import pytest

from ul_ingest.site_archive import canonical, connect, enqueue, priority, report


@pytest.mark.parametrize('href', [
    'https://example.com/private', 'https://www.ul.ie/user/login',
    '/study?field_course=123', '/news?q=one', '/assets/film.mp4',
    'https://www.ul.ie:1234/study', '/node/123/edit', 'mailto:person@example.com',
    '/%75ser/password',
])
def test_scope_excludes_private_external_queries_and_assets(href):
    assert canonical('https://www.ul.ie/', href) is None


def test_canonical_public_pages_and_pdfs():
    assert canonical('https://www.ul.ie/study/', '../fees#payment') == 'https://www.ul.ie/fees'
    assert canonical('https://www.ul.ie/', '/media/fictional-guide.pdf') == 'https://www.ul.ie/media/fictional-guide.pdf'
    assert priority('https://www.ul.ie/fees/payment') < priority('https://www.ul.ie/news/old-article')


def test_queue_resume_dedupe_and_failure_reporting(tmp_path):
    db = connect(tmp_path)
    enqueue(db, ['https://www.ul.ie/fees', 'https://www.ul.ie/fees/', 'https://example.com/'])
    db.execute("UPDATE pages SET state='failed',error='HTTP 404'")
    db.commit(); db.close()
    db = connect(tmp_path)
    enqueue(db, ['https://www.ul.ie/fees'])
    assert db.execute('SELECT count(*) FROM pages').fetchone()[0] == 1
    out = report(db, tmp_path, 'crawl')
    assert out['counts'] == {'failed': 1}
    assert json.loads((tmp_path / 'crawl-status.json').read_text())['queued_urls'] == 1
    assert db.execute('SELECT error FROM pages').fetchone()[0] == 'HTTP 404'
    db.close()


def test_short_main_does_not_fall_back_to_navigation():
    from ul_ingest.extractors import extract_html
    html = '''<html><body><div>Navigation noise and unrelated footer text.</div>
    <main><h1>Fictional Office</h1><p>Contact the fictional student support team.</p>
    <a href="mailto:test@example.com">Email the office</a></main>
    <div>Unrelated copyright footer.</div></body></html>'''
    md = extract_html(html, 'https://fictional.example/contact').markdown
    assert 'test@example.com' in md
    assert 'Navigation noise' not in md
    assert 'copyright' not in md


def test_worker_lock_prevents_duplicate_processes(tmp_path):
    from ul_ingest.site_archive import worker_lock
    with worker_lock(tmp_path, 'crawl'):
        with pytest.raises(OSError):
            with worker_lock(tmp_path, 'crawl'):
                pytest.fail('a second worker acquired the same lock')
    with worker_lock(tmp_path, 'crawl'):
        pass  # released even after the nested failure


def test_redirect_scope_checked_before_fetch(tmp_path):
    from types import SimpleNamespace
    from ul_ingest.crawler import FetchResult
    from ul_ingest.site_archive import safe_fetch
    class Fetcher:
        client = SimpleNamespace(follow_redirects=True)
        redirect_location = 'https://outside.example/private'
        def __init__(self): self.calls = []
        def fetch(self, url):
            self.calls.append(url)
            return FetchResult(url=url, status=302)
        def _cache_paths(self, url): return (tmp_path/'x.bin', tmp_path/'x.json')
    fetcher = Fetcher()
    res = safe_fetch(fetcher, 'https://www.ul.ie/fees')
    assert 'outside public crawl scope' in res.error
    assert fetcher.calls == ['https://www.ul.ie/fees']
    assert not fetcher.client.follow_redirects


def test_official_inline_pdf_flag_is_allowed_without_opening_query_traps():
    assert canonical('https://www.ul.ie/', '/media/public-guide/download?inline') == 'https://www.ul.ie/media/public-guide/download?inline'
    assert canonical('https://www.ul.ie/', '/media/public-guide/download?inline=1') is None
    assert canonical('https://www.ul.ie/', '/media/public-guide/download?inline&auth=secret') is None
    assert priority('https://www.ul.ie/media/public-guide/download?inline') < priority('https://www.ul.ie/artsoc/news/old')

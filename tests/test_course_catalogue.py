"""Structured course extraction uses fictional content for deterministic checks."""
import importlib.util
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('course_builder',ROOT/'scripts/build_course_catalogue.py')
builder=importlib.util.module_from_spec(spec)
spec.loader.exec_module(builder)


def test_visible_fields_and_real_summary_exclude_hidden_fee_data():
    html='''<html><title>Fictional Data Practice | University of Limerick</title>
    <main><h1>Fictional Data Practice</h1><div class="course-summary-text">A fictional programme for testing extraction.</div>
    <p>YouTube cookie preferences should not become a programme description.</p>
    <div class="key-info__row"><span>Duration</span><span>One year</span></div>
    <div class="key-info__row"><span>NFQ Level</span><span>NFQ Level 9</span></div>
    <div class="key-info__row"><span>Non-EU fees per year</span><span>€10,000</span></div>
    <div style="display: none"><div class="key-info__row"><span>EU fees per year</span><span>€123,456</span></div></div>
    <a href="/study/postgraduate/fictional/entry-requirements#detail">Entry requirements</a>
    <a href="https://outside.example/fees">Fees and funding</a></main></html>'''
    result=builder.parse_course(html,'https://www.ul.ie/study/postgraduate/fictional')
    assert result['duration']=='One year'
    assert result['summary']=='A fictional programme for testing extraction.'
    assert result['euFee'] is None
    assert result['nonEuFee']=='€10,000'
    assert result['links']['entry requirements'].endswith('/fictional/entry-requirements')
    assert 'fees and funding' not in result['links']


def test_entry_extract_starts_after_key_facts_and_excludes_other_routes():
    md='''# Fictional programme
### Key information
Duration One year
## Minimum grades
Applicants must hold the fictional entry qualification with at least six subjects. This text exists only to test the extraction boundaries.
## Subject requirements
Applicants must have fictional mathematics.
## Non-EU entry requirements
Do not confuse a country chooser with complete international requirements.
'''
    result=builder.requirements(md)
    assert 'fictional mathematics' in result
    assert 'Duration' not in result
    assert 'country chooser' not in result


def test_live_catalogue_is_unique_cited_and_has_no_consent_descriptions():
    data=json.loads((ROOT/'frontend/src/data/courses.json').read_text(encoding='utf-8'))
    courses=data['courses']
    assert len(courses)>50
    assert len({course['id'] for course in courses})==len(courses)
    assert len({course['url'] for course in courses})==len(courses)
    for course in courses:
        assert urlsplit(course['url']).hostname in {'www.ul.ie','ul.ie'}
        assert 'youtube' not in course['summary'].lower()
        assert course['duration']
        if course['points']: assert course['pointsYear']
        for link in course['links'].values():
            assert urlsplit(link).hostname in {'www.ul.ie','ul.ie'}

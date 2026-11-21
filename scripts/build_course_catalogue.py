"""Publish a compact, cited course snapshot from official public UL sources.

Visible structured fields only. Hidden fee figures are deliberately not copied.
Entry links are discovered from actual course navigation, never guessed.
"""
from pathlib import Path
import argparse
import gzip
import hashlib
import json
import re
import sqlite3
import sys
import time
from datetime import datetime,timezone
from urllib.parse import urljoin,urlsplit,urldefrag

from bs4 import BeautifulSoup

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'ingestion')]
from ul_ingest.crawler import PoliteFetcher
from ul_ingest.extractors import extract_html
from ul_ingest.site_archive import safe_fetch

def clean(value): return re.sub(r'\s+',' ',value).strip()

def visible(node):
    return not any(n.has_attr('hidden') or n.get('aria-hidden')=='true' or
                   re.search(r'display\s*:\s*none',n.get('style',''),re.I)
                   for n in [node,*node.parents] if getattr(n,'attrs',None) is not None)

def official_link(base,href):
    url=urldefrag(urljoin(base,href))[0]
    p=urlsplit(url)
    return url if p.scheme=='https' and p.hostname in {'www.ul.ie','ul.ie'} and not p.query else None

def subjects(title):
    themes={'Computing & AI':r'comput|artificial|machine learning|data science|cyber|software|informatics',
            'Engineering':r'engineer|robot|aeronaut|mechatron|construction|manufactur',
            'Business':r'business|account|financ|econom|marketing|management|entrepreneur|supply chain',
            'Health & sport':r'nurs|health|medicine|medical|physio|occupational|psycholog|sport|midwif|paramedic|speech|exercise',
            'Arts & society':r'arts|music|language|history|politic|sociolog|journal|creative|dance|design|english|irish|international',
            'Science':r'science|biolog|chem|physic|math|environment|biotech|biomed|food|energy',
            'Education':r'education|teaching|learning|teacher',
            'Law':r'law|legal|justice|crimin'}
    return [k for k,rx in themes.items() if re.search(rx,title,re.I)] or ['Other subjects']

def parse_course(html,url,title='',checked=''):
    soup=BeautifulSoup(html,'lxml')
    fields={}
    for row in soup.select('.key-info__row'):
        spans=row.find_all('span',recursive=False)
        if len(spans)>=2 and visible(row):
            fields[clean(spans[0].get_text(' ',strip=True))]=clean(spans[1].get_text(' ',strip=True))
    if not fields.get('Duration') or not any('NFQ' in x for x in fields): return None
    title=title or (soup.title.get_text().split('| University')[0].strip() if soup.title else '')
    if not title or re.search(r'entry requirements|fees and funding|course content|how to apply',title,re.I): return None
    if not any(part in url for part in ('/study/undergraduate/','/study/postgraduate/','/study/short-courses/','/gps/')): return None
    links={}
    for a in soup.select('a[href]'):
        name=clean(a.get_text(' ',strip=True)).lower()
        if name in {'entry requirements','fees and funding','course content','how to apply','careers'}:
            link=official_link(url,a['href'])
            if link: links[name]=link
    h1=soup.select_one('main h1,h1')
    intro=soup.select_one('.course-summary-text')
    summary=clean(intro.get_text(' ',strip=True))[:310] if intro else ''
    point_label=next((k for k in fields if re.match(r'CAO points\s+20\d\d',k)),None)
    year=re.search(r'20\d\d',point_label)[0] if point_label else None
    level='Undergraduate' if '/study/undergraduate/' in url else 'Postgraduate / professional'
    return {'id':hashlib.sha1(url.encode()).hexdigest()[:12], 'title':title,'url':url,
            'checkedAt':checked,'level':level,'subjects':subjects(title),'summary':summary,
            'code':fields.get('Course code'),'duration':fields.get('Duration'),
            'attendance':fields.get('Attendance'),'delivery':fields.get('Delivery'),
            'nfq':fields.get('NFQ Level'),'award':fields.get('Award'),
            'euFee':fields.get('EU fees per year'),'nonEuFee':fields.get('Non-EU fees per year'),
            'start':fields.get('Start date'),'points':fields.get(point_label) if point_label else None,
            'pointsYear':year,'links':links,'requirements':None,'requirementsCheckedAt':None}

def requirements(markdown):
    # Course navigation/key facts precede the actual admissions content.
    match=re.search(r'^#{2,4}\s+(?:Minimum grades|Entry requirements|Requirements|Qualifications)[^\n]*$',markdown,re.M|re.I)
    if not match: return None
    body=markdown[match.start():]
    body=re.split(r'^#{2,4}\s+(?:Non-EU entry|Related courses|Area\(s\)|How to apply|Explore our campus)',body,flags=re.M|re.I)[0]
    body=re.sub(r'(?m)^#+\s*','',body)
    body=re.sub(r'(?m)^[-*_]{3,}\s*$','',body)
    body=clean(body)
    if len(body)<70: return None
    if len(body)>850: body=body[:850].rsplit(' ',1)[0]+'…'
    return body

def build(fetch=False,refresh_overviews=True):
    target=ROOT/'frontend/src/data'; target.mkdir(exist_ok=True)
    with sqlite3.connect(ROOT/'data/ul_navigator.db') as db:
        candidates={u:(t,date) for t,u,date in db.execute("SELECT title,url,collected_at FROM documents WHERE status='indexed' AND content_type='html' AND (category IN ('undergraduate','postgraduate'))")}
    programme_urls=set()
    with sqlite3.connect(ROOT/'data/site_archive/queue.sqlite3') as q:
        for u,t,date,payload in q.execute("SELECT url,title,fetched_at,payload FROM pages WHERE payload IS NOT NULL AND url LIKE '%/gps/%'"):
            with gzip.open(payload,'rt',encoding='utf-8') as f: archived=json.load(f)
            if 'Key information' in archived['markdown'] and 'Duration' in archived['markdown'] and 'NFQ' in archived['markdown']:
                candidates.setdefault(u,(t,date)); programme_urls.add(u)
    overview_fetcher=PoliteFetcher('ULNavigatorAI/1.2 (+https://ul-navigator-ai.vercel.app; official course comparison)',ROOT/'data/raw',delay_s=3,max_retries=2,timeout_s=25,cache_ttl_s=12*3600)
    overview_fetcher.client.event_hooks['response'].append(lambda response:setattr(overview_fetcher,'redirect_location',response.headers.get('location','')))
    if fetch and refresh_overviews:
        time.sleep(3)
        for u in sorted(programme_urls):
            path=ROOT/'data/raw'/(hashlib.sha1(u.encode()).hexdigest()+'.bin')
            if not path.exists():
                result=safe_fetch(overview_fetcher,u)
                print(json.dumps({'overview_checked':u,'ok':result.ok}),flush=True)
    overview_fetcher.close()
    # Redirect targets are the authoritative URLs and may differ from sitemap aliases.
    for meta_path in (ROOT/'data/raw').glob('*.json'):
        try:
            meta=json.loads(meta_path.read_text(encoding='utf-8'))
            u=meta.get('final_url','')
            if any(part in u for part in ('/gps/','/study/postgraduate/','/study/short-courses/')) and official_link(u,u):
                date=datetime.fromtimestamp(meta.get('fetched_at',0),timezone.utc).isoformat()
                candidates.setdefault(u,('',date))
        except (ValueError,OSError): pass
    courses=[]
    for url,(title,date) in candidates.items():
        p=ROOT/'data/raw'/(hashlib.sha1(url.encode()).hexdigest()+'.bin')
        if not p.exists(): continue
        course=parse_course(p.read_bytes(),url,title,date)
        if course: courses.append(course)
    courses=list({course['url']:course for course in courses}.values())
    courses.sort(key=lambda c:(c['level']!='Undergraduate',c['title']))
    fetcher=PoliteFetcher('ULNavigatorAI/1.2 (+https://ul-navigator-ai.vercel.app; official course comparison)',ROOT/'data/raw',delay_s=3,max_retries=2,timeout_s=25,cache_ttl_s=12*3600)
    fetcher.client.event_hooks['response'].append(lambda response:setattr(fetcher,'redirect_location',response.headers.get('location','')))
    fetched=0; failed=[]
    def save():
        manifest={'generatedAt':datetime.now(timezone.utc).isoformat(),'courses':courses,
                  'coverage':{'courses':len(courses),'requirements':sum(bool(c['requirements']) for c in courses),
                              'courseCodes':sum(bool(c['code']) for c in courses)},
                  'collectionSnapshot':json.loads((ROOT/'data/site_archive/crawl-status.json').read_text())}
        temporary=target/'courses.tmp.json'
        temporary.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
        temporary.replace(target/'courses.json')
        (ROOT/'work/course-catalogue-report.json').write_text(json.dumps({'courses':len(courses),'requirements':manifest['coverage']['requirements'],'failed':failed},indent=2),encoding='utf-8')
    save()
    try:
        time.sleep(3)
        for course in courses:
            url=course['links'].get('entry requirements')
            if not url: continue
            if fetch:
                result=safe_fetch(fetcher,url)
                if not result.ok:
                    failed.append({'url':url,'error':result.error});continue
                body=result.content
            else:
                cached=fetcher._load_cache(url)
                if not cached: continue
                body=cached.content
            course['requirements']=requirements(extract_html(body,url).markdown)
            if course['requirements']:
                meta_path=fetcher._cache_paths(url)[1]
                meta=json.loads(meta_path.read_text()) if meta_path.exists() else {}
                course['requirementsCheckedAt']=datetime.fromtimestamp(meta.get('fetched_at',time.time()),timezone.utc).isoformat()
            fetched+=1
            if fetched%10==0:
                save(); print(json.dumps({'courses':len(courses),'entry_pages_checked':fetched}),flush=True)
        save()
        print(json.dumps({'courses':len(courses),'requirements':sum(bool(c['requirements']) for c in courses),'failures':len(failed)}),flush=True)
    finally: fetcher.close()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--fetch',action='store_true');p.add_argument('--entries-only',action='store_true');args=p.parse_args();build(args.fetch,not args.entries_only)

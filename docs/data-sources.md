# Data sources & collection policy

## Seed sources (official, public)
All seeds are defined in `ingestion/ul_ingest/sources.yaml`.

| Area | Sources |
|---|---|
| Academic | Academic Registry; Academic Calendar 2026/27; Policy Hub; Book of Modules; Undergraduate study; Orientation |
| International & finance | Incoming students FAQs; Visa & immigration; Undergraduate scholarships; Fees |
| Accommodation & campus | Accommodation; Accommodation fees & payment; Student supports & resources; Campus maps; Library; CECD |
| PDFs | Handbook of Academic Regulations and Procedures 2026/27; UL Undergraduate Prospectus 2026/27; Autumn 2026 module booklet; Spring 2027 module booklet; Budget Planner 2026/27; UL room-number map |

Discovery follows links from the seeds only within `allowed_hosts` and `allowed_path_prefixes`, skips excluded patterns (login, search, Irish-language duplicates, media files, news/events) and is limited by `CRAWL_MAX_DEPTH` / `CRAWL_MAX_PAGES`. The seed list includes the alphabetical undergraduate course directory and its individual course pages, plus direct student-service and scholarship resources. The actual count depends on what the site permits and what is reachable, and every ingestion report lists failures explicitly.

## Rules the crawler follows
- Obeys `robots.txt` and `Crawl-delay`. An unreachable robots.txt means the host is **not** crawled.
- Identifies itself with a descriptive User-Agent including a contact address (`CRAWL_USER_AGENT`).
- At most one request per 3 s per host by default (automatically slowed to up to 30 s if the site returns HTTP 429), with exponential backoff and `Retry-After` on 429/5xx.
- Never submits forms, follows login/authenticated links or accesses restricted systems.
- Does not collect personal student information.

## Manual uploads
Administrators can upload **authorised** PDF, CSV, RTF, TXT and MD files (e.g. Book of Modules exports). Uploads are validated and stored in `data/uploads/` (git-ignored).

## Copyright
UL content remains the property of the University of Limerick. It is stored only to retrieve and cite passages with links to the original pages. Generated indexes, raw downloads and uploads are excluded from the repository.


## Expanded sources (19 November 2026)

The expansion adds direct links from UL's alphabetical course directory and official
student-service directories. These are explicit seeds, so policy-link discovery cannot
consume the crawl limit before they are reached.

- Undergraduate course directory and individual programme/subject pages.
- Counselling, student health, disability support, Access Office, chaplaincy,
  student engagement officers, and the Support and Engagement Hub.
- Regional Writing Centre, Mathematics Learning Centre, Science Learning Centre,
  First Seven Weeks, and Educational Assistive Technology Centre.
- Academic, sports, international scholarships and the scholarships/funding directory.
- Student financial support advice and campus/buildings information.

No academic year is assigned to these pages unless detected in the source itself.
Course descriptions and entry requirements may change; answers should retain the
original source links and check the relevant year.

Repeat the configured seed collection without unbounded link discovery:

```powershell
$env:PYTHONPATH = "backend;ingestion"
.\.venv\Scripts\python -m ul_ingest crawl --seeds-only --max-pages 180
```

The ingestion report is the authority on what was fetched, indexed, skipped, or failed;
a configured source is not necessarily an indexed source. Restart the API after an
external ingestion run so its in-memory retrieval index reloads.


## Postgraduate and catalogue expansion

The second expansion includes UL's taught postgraduate A–Z, professional/flexible A–Z,
research programme directory, faculty programme listings, application and entry requirements,
fees/funding guidance, and selected detailed programme pages across subjects. Directory
coverage does not imply that every individual postgraduate detail page has been indexed.

Broad course-browsing questions now include representative passages from the official
course directories. The answer gives study levels and examples and directs students to
the cited full directories. Subject-specific questions (such as AI courses) retain normal
hybrid retrieval. Explicit category filters remain enforced.

Refresh the enlarged seed list with a limit above its current length:

```powershell
$env:PYTHONPATH = "backend;ingestion"
.\.venv\Scripts\python -m ul_ingest crawl --seeds-only --max-pages 250
```


Measured second-expansion outcome: 65 successful fetches, 62 new documents, one updated
document, and two duplicates. One extra malformed FAQ URL returned 404; the canonical
FAQ page was indexed successfully, the duplicate seed was removed, and the stored URL
was normalized without removing content. The original ingestion report retains this history.
Searchable coverage is now 323 documents / 6,651 chunks.


## Book of Modules detail pages

The public Book of Modules search homepage is not a module catalogue export. Verified
module details can be collected from its `Default.aspx?ModuleCodeParameter=...` links.
The extractor now selects the module detail container inside the ASP.NET form instead
of dropping its contents with generic search forms. The crawler preserves a validated
single-module query parameter on the official Book of Modules host.

BS6005 (Executive MBA Project B) and CS4012 (Representation and Modelling) were imported
from their official detail pages, adding 12 chunks. This does not establish full coverage
of every UL module. A missing result means the local index may lack that module; it does
not establish that the module does not exist.


BY4001 (Biology 1) was subsequently imported from its verified official detail page.
Exact-code module lookup now separates descriptions from incidental mentions in
prerequisite lists. Direct descriptions are identified from official module URLs,
module titles, and explicit module headings; repeated chunks from the same description
are collapsed. Incidental mentions remain available separately in the API's `references`
field and are not displayed as the module's own search result. Coverage remains partial.

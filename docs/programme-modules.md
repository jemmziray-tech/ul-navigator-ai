# Programme curricula and module content

Collected 21 November 2026 from the official content navigation of 176 course-directory records. The reviewed snapshot captures 1,085 sections across 163 programmes and 4,334 coded module listings, representing 2,141 unique module codes. Thirteen programme records have no structured semester map captured; this is not a complete audit of every UL course, pathway or elective.

Sources retain course URL, exact tab fragment, collection timestamp, year/pathway label, semester label, coded module titles, elective/core wording and placement notes. Tables and programme tabs are parsed together, including side-by-side semester columns. Uncoded subjects and unsupported layouts are not invented. Academic-year applicability is not inferred from CAO years or collection timestamps. Programme study year is separate from academic year. Book of Modules Year Last Offered remains a descriptor field rather than a programme-cohort guarantee.

The /curricula browser links from course details, tools and the footer. It filters source year/pathway labels and opens indexed official module descriptors. Missing descriptions link to the official Book of Modules. The module descriptor endpoint reads only indexed official Book of Modules documents, not prerequisite mentions or curriculum references.

RAG clarification asks for programme, study year or BSc/MSc pathway where ambiguous. A short follow-up can inherit one recently identified programme, but a programme example in a clarification prompt cannot establish a student's context. Exact curriculum passages are injected before reranking and preferred for programme-semester questions. Exact Book of Modules descriptions are preferred for module-code questions. Semester ordinals are parsed separately from adjacent year numbers. Combined-year labels are split only where earlier source years establish cumulative two-semester numbering.

Curriculum ingestion can preserve section boundaries so short placement/semester passages are not merged. Initial course structures and 119 full module descriptors are packaged in a public-source seed. Their vectors are computed locally. The protected /api/admin/curricula/import endpoint checks cache completeness and the 24,000-passage ceiling before updating sources, batches persistence, and skips unchanged hashes. It never replaces conversations. A disposable Linux-container test imported 282 documents / 1,902 passages with embedding calls disabled; repeat import changed zero documents and a synthetic chat survived.

## Ongoing collection

Limited Windows tasks ULNavigator-Modules-collect and ULNavigator-Modules-publish run independently, using OS-held locks and resumable files under data/curricula. No credentials appear in task arguments or progress files. Book of Modules requests use a minimum three-second rate, robots rules and scoped redirects. No private/authenticated university systems are accessed and no Gemini calls are used for collection/import.

UL_MODULES_RESUME.bat resumes after a reboot, UL_MODULES_PAUSE.bat pauses after the current request, and UL_MODULES_PROGRESS.bat shows collection and publication status. Keep the computer awake and online. Completion means the queue was attempted; check failure counts, not just the completion state.

The new curriculum-specific publisher is bounded at 2,500 imports per run and 24,000 total live passages, with a 200-passage per-document bound. This accommodates the identified 2,141-code collection without changing cloud resources or billing caps. It pauses after three consecutive API failures and leaves overflow collected locally. The broad website workers are temporarily paused while the module-specific pipeline has priority. Existing non-module knowledge remains available.

## Live verification

Released to the production website and backend on 21 November 2026. The initial 282-document seed is indexed. Live questions returned all five named LM174 Year 1 Semester 1 modules, preserved programme context in a short follow-up, and returned the correct four listed modules for Year 4 BSc Semester 8, each with the exact official curriculum citation. Book of Modules fields retain labels in chunk bodies so small fields such as Credits survive section merging. The local collector reparses cached pages without additional university requests when this formatting changes.

The frozen initial module manifest predates that field-label improvement. Incremental publication updates the live descriptors. Do not rerun the frozen seed import after these updates unless the manifest and embedding seed have also been refreshed.

## Public repository setup

The public repository includes course/semester metadata but intentionally replaces the full module-description seed with an empty list. Recollect descriptions and prepare matching vectors before using cached-seed import. Production runtime state is not included. Set `UL_PUBLISH_API` explicitly to your own backend when using publication workers; its default is localhost. These workers use locally generated maintainer credentials under the ignored data directory. Review their task names before registering them on a machine already running another copy.

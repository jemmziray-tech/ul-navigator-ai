# Course finder and knowledge health

Published 20 November 2026. Vercel deployment: `dpl_91YyAv7Jx1Sk5MZ4MpWDAbKGkjb6`.

## Student flows

- `/courses`: search by course name, subject, description or programme code; filter study level/attendance; bookmark a browser-local shortlist; compare up to three programmes.
- Comparisons have a differences-only view, official entry/fee/source links, source dates, historical CAO years, missing-field labels, a shareable `compare` query parameter and CSV export.
- Shared links contain programme IDs only. Shortlists use versioned local storage and do not create an account or upload a student profile. Unknown IDs and malformed saved data are ignored.
- `/knowledge-health`: one live stats request on entry or manual refresh, with timeout/error handling; topic-source counts; small-coverage review flags; an explicitly dated collection snapshot; programme-field gaps. Source counts are not a confidence or completeness score.

## Source contract

The current catalogue has 176 records: 97 undergraduate and 79 postgraduate/professional. It includes 132 entry-page extracts. It is a collected selection, not the entire UL directory. Summaries come from actual programme summaries, not cookie-consent paragraphs. Course facts come from structured official fields; explicitly hidden rows/ancestors are excluded. Fees are only displayed when present in accepted structured fields, with the lack of an academic year stated. Fees and applicant eligibility always link to the official guidance. Historical CAO points retain the published year and are not predictions.

`src/data/courses.json` is a generated snapshot bundled with the frontend. It does not call Gemini, add cloud resources or depend on the backend for course browsing/comparison. Live indexed-source counts remain separate from collected documents and the course snapshot.

To refresh: pause the site crawler with `UL_RESOURCE_PAUSE.bat`; run the repository Python on `scripts/build_course_catalogue.py --fetch` (minimum three seconds per UL request); inspect `work/course-catalogue-report.json`; run tests and build; deploy reviewed frontend sources; resume the collection with `UL_RESOURCE_RESUME.bat`. Use `--fetch --entries-only` to refresh discovered entry pages without re-fetching old overview aliases. Redirect targets from the public raw cache are included. Writes of the generated catalogue are atomic.

## Verification

108 Python regression checks and 4 Node helper checks pass. Production TypeScript/build succeeds. Browser checks covered multi-word search, CAO-code search, saved shortlist after reload, shared selections, differences-only comparison, source links, a real CSV download with provenance, details dialog/Escape, and phone-width containment (no page-wide overflow; comparison table scrolls within its region). Knowledge health retrieved real live counts and exposed sparse topics.

The React review checked effect cleanup, bounded DOM rendering (24 cards initially), local-storage guards/versioning, validated share IDs, labelled controls, toggle states, focus-managed Radix dialogs, reduced-motion handling, keyboard-scrollable comparison tables and real CSV quoting/formula protection.

The final navigation fix opens incoming `#comparison` links at the comparison table after the selected programmes hydrate. The published three-programme limit was also checked: adding a fourth shows a clear notice and retains the existing selection.

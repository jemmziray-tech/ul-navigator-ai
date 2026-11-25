# Production hardening — 25 November 2026

This release presents UL Navigator AI as an independent information service. Personal attribution and student-project labels are removed from the website footer, About/Privacy copy and page metadata. The independent/unofficial status remains explicit; UL endorsement is not implied.

## Changes

- Anonymous chat identities remain separate when browser storage is blocked. The previous shared `anonymous-session` fallback is no longer used. Existing valid browser identities are preserved; blocked storage uses an in-memory identity that may be lost on reload.
- Coverage now reports the curriculum snapshot separately: programme maps, year/semester/pathway sections, coded module listings and records without a structured map. These do not represent fully indexed module descriptions or cohort-confirmed registration requirements.
- Chat and administration pages emit `noindex, nofollow`. Robots exclusions and a public-page sitemap provide crawler guidance; these are not access controls.
- The mobile navigation supports Escape, restores focus to its toggle and marks the current page. The footer focuses on product navigation and privacy rather than personal attribution.
- Public metadata describes the product and supplies social-sharing titles. No new tracking, cookies or external analytics are added.

## Verification

All 13 frontend unit cases pass, including blocked-storage isolation, reload persistence and legacy shared-ID replacement. Type checking and the production build pass. The locked dependency install reported no known vulnerabilities at install time; this is not a comprehensive security audit.

## Operating limits

This work does not turn the existing single-instance backend into a multi-instance service. Keep the existing instance/concurrency limits, persistence design, generation rate limits and spend controls until shared storage and coordinated ingestion are implemented and tested. Source coverage and answer correctness remain partial. Provider-credit exhaustion, storage recovery, capacity/load testing and incident response need ongoing operational verification. No new paid resources are provisioned by this frontend release.

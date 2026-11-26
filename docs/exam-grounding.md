# Exam timing and unsupported figures

Module descriptors establish teaching content and offering semesters, not individual exam appointments. Exam timing queries are classified as calendar questions and do not force Book of Modules descriptors into the retrieval pool.

Exact module exam requests now use the official public UL Module Exam Timetable form directly. The lookup submits only the validated module code and public form state. It verifies the announced academic year/session, selected module, result-table columns, module identity, date, weekday and time before displaying an appointment. It never reads a student login or personal timetable. Multiple published venues are retained without assigning a seat or personal accommodations.

The `/exams` page and `GET /api/exams/{code}` expose published results, unlisted modules, session mismatch, source failure and explicitly labelled stale data. Successful lookups are reused for ten minutes; an old success can be retained for at most a day during an upstream failure, with its original check time and a stale warning. Chat does not present stale details as a confirmed appointment. Requests use a fixed HTTPS source, reject redirects, validate module codes, serialize upstream requests with a three-second interval and bound the process cache to 256 keys. The endpoint is limited to 12 requests/minute per client, with no-store HTTP responses. No Gemini call or vector ingestion is required, and these answers do not use the generated-answer allowance.

Explicit requests for a different year or exam session do not reuse the current session's dates. Source format changes, missing result tables and inconsistent rows fail closed. A module missing from the current selector is not evidence that the student has no exam. Source-check time is separate from publication time. The frontend always links to UL for final verification.

Generated answers with figures that cannot be matched to their cited text are replaced with relevant source excerpts. Dates include their stated year, and ISO dates are checked. This is a conservative string-based guard, not a complete claim-verification system; equivalent date/number formatting may cause a safe fallback. Model text is buffered until validation finishes, then the existing frontend reveals the verified response progressively. Unsupported model deltas are not exposed temporarily before a correction.

The existing backend regression suite passed after the behavioral change. Twelve targeted cases subsequently passed, covering calendar classification, non-timing questions, history leakage, date years/ISO dates, pre-token replacement and generation-budget accounting. The exact deployment image passed a Linux module-exam regression without a provider call.

Official reference: https://www.timetable.ul.ie/UA/ExamModuleTimetable.aspx (checked 26 November 2026).

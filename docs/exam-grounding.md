# Exam timing and unsupported figures

Module descriptors establish teaching content and offering semesters, not individual exam appointments. Exam timing queries are classified as calendar questions and do not force Book of Modules descriptors into the retrieval pool.

Until verified per-module examination timetable records are integrated, requests for an exact module exam date/time receive deterministic guidance linking to the official public UL Module Exam Timetable. They do not infer dates from a teaching semester, a university-wide examination period or previous assistant messages. This guidance makes no Gemini call and does not consume the generated-answer allowance.

Generated answers with figures that cannot be matched to their cited text are replaced with relevant source excerpts. Dates include their stated year, and ISO dates are checked. This is a conservative string-based guard, not a complete claim-verification system; equivalent date/number formatting may cause a safe fallback. Model text is buffered until validation finishes, then the existing frontend reveals the verified response progressively. Unsupported model deltas are not exposed temporarily before a correction.

The existing backend regression suite passed after the behavioral change. Twelve targeted cases subsequently passed, covering calendar classification, non-timing questions, history leakage, date years/ISO dates, pre-token replacement and generation-budget accounting. The exact deployment image passed a Linux module-exam regression without a provider call.

Official reference: https://www.timetable.ul.ie/UA/ExamModuleTimetable.aspx (checked 26 November 2026).

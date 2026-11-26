# Grade planner and guidance release — 21 November 2026

The public /grade-planner route performs all arithmetic in the browser. No grades are transmitted or persisted. Inputs are examples until edited. The scenario calculates a required remaining QPV, projected QCA, maximum possible QCA, and an example mix of adjacent passing grades. A subset-sum search in half-credit units handles unequal indivisible modules. This is a projection for the credits entered, not an official award decision. Users must account for programme weighting, eligible semesters and repeat restrictions.

Both calculators use matching copies of qca-rules.json from the official 2026/27 handbook: PDF page 13 for grades, pages 14–15 for honours bands and page 26 for the QCA formula. Current bands are 3.30 / 2.90 / 2.50 / 2.00. D2 is absent from the current handbook and removed from current grade options. Band comparisons use full precision; displayed values are rounded. Backend tests enforce agreement between the two rule files.

Tuition amount questions now ask for the programme, user-stated fee category and academic year. Entry requirement questions ask for programme and applicant route, with qualification system for international qualifications. Clarification state is stored in assistant message metadata and restored by conversation ID. General overviews and unknown fee category are exits; nationality is not converted into fee status. Payment, repeat-exam, accommodation and other non-tuition fee questions bypass the tuition flow.

Source-role weights survive reranking. News and personal profiles cannot establish student fees, entry requirements, immigration or academic regulations unless the question explicitly asks about editorial content. Older academic years receive a soft ranking penalty, not an assertion that the newer source is automatically applicable. Relevant hits sort before rejected hits.

Immigration registration takes precedence over student registration in topic routing and links to UL Global. Personal matchmaking questions receive a short friendly scope response and suggestions for societies/events, without retrieval. Wedding venue questions remain normal factual queries.

Gemini streaming checks terminal finish reasons and rejects non-STOP termination or empty output. Interrupted output is reset and replaced with cited source excerpts. Uncited generated output also falls back to excerpts. Short-answer prompting puts citations beside each claim. No additional model retry is introduced for a partially streamed answer.

Verification: backend regression suite, frontend unit tests, production Next build, desktop and 390px phone layout. Browser checks cover default projection, automatic grade mix, unreachable target and blank input. Live conversation checks should be recorded in deployment.md after release.

## Product and progressive replies

The landing page now describes student tasks rather than implementation details. New /about and /privacy pages explain the independent public beta, source limitations, server-stored conversations, operational logs, third-party AI processing and browser-local grade planning/shortlists. The official UL logo was extracted from the inline header SVG at https://www.ul.ie/ on 21 November 2026. Its original paths/viewBox are preserved; standalone display removes CSS classes and supplies the green fill. It links to the official university website and is visually separate from the independent product compass.

ProgressiveReply buffers incoming SSE text, reveals two words per 32ms tick, preserves verified final corrections and drains before enabling the next request. Reset replaces failed generated text with source excerpts, still progressively. Stop/unmount/navigation cancel pending updates. Reduced-motion users receive chunks without the extra reveal pacing. Browser checks observed the initial partial greeting and successful mid-reply stop. The scroll position follows new text only while near the bottom.

Live testing found the production output cap is 1000 tokens and the paid-answer limit is three per minute. Gemini 3.8 Flash now uses LOW thinking (3.1 Flash Lite fallback uses MINIMAL), leaving room for the concise cited answer without increasing the cap. A local real-provider immigration question at the production cap returned a complete generative answer with two citations and the UL Global contact. Clarification, greetings and scope responses have zero cost against the shared paid-answer allowance but remain protected by a 20-request/minute outer limit. Streaming and synchronous routes now share that answer allowance. Tests verify a complete four-turn fee flow at a one-answer/minute cap, then reject the next full answer while allowing a clarification.


## Separate module and cumulative QCA (26 November 2026)

The planner defaults to included modules only, with no previous credits or QCA assumed. All A1 modules yield 4.000 regardless of individual credit weights. Previous results are included only when the user enables a cumulative projection and enters their actual current QCA and counted credits. Both the module QCA and blended cumulative result are then labelled explicitly. For example, 30 credits at A1 have module QCA 4.000, while blending them with 60 earlier credits at QCA 3.100 gives cumulative QCA 3.400. These are separate calculations, not different A1 quality point values.

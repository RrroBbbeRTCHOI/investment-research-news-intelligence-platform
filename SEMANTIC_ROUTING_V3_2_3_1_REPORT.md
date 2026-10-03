# V3.2.3.1 — Semantic Routing / Display-Type Correction

Patched the current local V3.2.3 in place. No architecture rebuild or older baseline substitution. No real Perigon/Gemini requests and no paid live smoke were run.

## Files modified
- src/news/live_content.py: bounded regulatory/production-restriction contexts, modal/threat signals, completed regulatory actions, final display_type helper, Outlook display field.
- src/news/live_runner.py: stamp completed event-lane records with final display_type.
- src/news/ui_api.py: derive display_type from final gate for both old and new V3 snapshots; stale stored display values cannot override it.
- static/js/news_model.js: gate-authoritative display adaptation, confirmed-event filtering and research marker suppression.
- static/js/news_presentation.js: neutral research presentation.
- static/js/news_ui.js: RESEARCH badge/header, N/A severity, no primary event urgency/geography sections; retain ticker qualification, relevance, source, research status and full raw audit.

## Added
- tests/news/test_live_semantic_routing.py
- tests/news_semantic_display_test.mjs
- SEMANTIC_ROUTING_V3_2_3_1_REPORT.md
- reports/v3_2_3_1/ validation logs

## Frozen preservation
Compared against the accepted V3.2.3 ZIP after editing: only the six product files listed above changed. Existing tests, frozen replays/GT, research_policy.py, event_geography.py, v3_validation.py, research_v3.py, severity, qualification, exposure, PIT, product scoring and financial methods are unchanged. The original live_intake_allow function is unchanged. The older V3.2.3 reports/manifests remain historical artifacts, not current patch manifests.

## Routing
Frozen reject/noise checks remain first. Non-negated affirmative headline actions are checked before future language. Explicit US/regulator/ITC/FTC/EU imposed/ordered/blocked/banned/fined actions and opened probes/investigations are recognized, along with existing actual actions. Historical threat wording after a completed action does not turn it into Outlook.

Threat/threatens, could/may/might face, risks/risk of, possible/potential, could/may/might be, expected to face and under/faces threat of are Outlook signals only with existing bounded research contexts. Contexts now include import bans, export restrictions, regulatory probes and production restrictions. Bare company mentions or threat words alone do not establish Outlook. Existing fallback research eligibility remains unchanged.

All supplied threat and actual-action examples pass, including “US imposes import ban after Apple had faced months of legal threat” and “FTC opens probe after Meta faced possible investigation”.

## Final display rules
- content_type=outlook → display_type=outlook.
- Event lane + gate.is_event=true → display_type=event.
- Event lane + gate.is_event=false → display_type=research.
- Missing confirmation at the API boundary is conservatively research.
- Skip is not shown.

Processing content_type is retained; final gate is never changed. Older V3 snapshots obtain display_type at read time without rewriting the snapshot. JS also respects explicit gate evidence rather than trusting a stale display label. Gate-less legacy UI fixtures retain existing compatibility behavior.

Form 144 is not automatically rerouted to Outlook. A completed record with gate=false shows RESEARCH, relevance, “N/A — Not confirmed event”, and “Not confirmed as discrete event”. Qualification, sources, research status and backend score objects remain available. No normal Event Urgency or event globe marker is shown. Original raw scores remain in Audit for compatibility, not as primary event claims.

## Counter semantics
No counters were renamed, redefined or added. event_count/outlook_count/skip_count remain per-cycle routing counts, including attempted/deferred event processing. event_count is NOT a confirmed-event count. Snapshot summary counts remain lane counts. To count confirmed completed records, inspect gate.is_event=true / display_type=event in completed records; research records are separately identifiable via display_type. This avoids mixing per-cycle attempts with accumulated snapshot totals.

## Validation
Focused Python command:
`python3 -m unittest tests.news.test_live_outlook tests.news.test_live_semantic_routing -v`
Result: 15 passed.

Focused JS: `node tests/news_semantic_display_test.mjs` — passed. Covers Form 144, gate override of stale display label, retained AAPL review qualification, no research marker, event-only filter and confirmed-event marker retention.

Full Python, run once after focused checks:
`python3 -m unittest discover -s tests/news -t . -v`
Result: 455 passed in 25.773 seconds.

All 10 News JS suites were run once: 9 passed, 1 failed. Failure: tests/news_v316_integration_test.mjs:12 asserts that mapArticles(frozen replay) has 6 markers. New required gate=false suppression correctly returns 2. The old test was deliberately NOT rewritten, nor was frozen gate data regraded. This is an explicit contract conflict with the new map-safety requirement; it is not reported as a fully green JS regression. The new focused test independently verifies that research records cannot receive event markers while confirmed events still can. No further full runs were made to hide the conflict.

## Limitations
English deterministic action/context patterns are bounded, not a universal temporal parser. Cross-clause, quoted, historical and body-only action language can still require review. Threat routing does not establish the legal facts, exact scheduled date, qualified exposure or future outcome. All existing Outlook date/evidence safeguards remain in force. The unchanged legacy marker-count assertion needs explicit reconciliation with the approved new UI contract before the entire inherited JS suite can be green. No real-news live claim is made for this patch.

# News V2 presentation refinement

## Scope and files

Built in `STOCK_SCREENER_NEWS_RESEARCH_INTELLIGENCE_V2_UI_REFINEMENT`, a standalone copy of `STOCK_SCREENER_NEWS_RESEARCH_INTELLIGENCE_V2`. The original project was not edited.

| File | Purpose |
|---|---|
| static/js/news_ui.js | Human feed badges, analyst panel, all ticker sections, disclosures, safe source links and existing globe locate action |
| static/css/news.css | Appended panel-scoped compact metrics, evidence/checklists, audit and archive table styling; original CSS retained |
| static/js/news_presentation.js (new) | Pure deterministic labels, explanations, checklists, supported paths, existing scores and components |
| tests/news_model_test.mjs | Replace obsolete renderer string assertion; retain adapter/semantics tests |
| tests/news_presentation_test.mjs (new) | A–H and additional null/zero, immutability, supplied components, history and path contracts |
| docs/ui_refinement/* (new) | Screenshots, complete test logs and file-integrity result |
| docs/NEWS_UI_REFINEMENT_REPORT.md (new) | This report |

No API serialization changes were necessary. `news_model.js`, `templates/news.html`, `app.py`, all backend modules, all Research templates/JS, all financial data, all original fixtures and snapshots, and `news_globe.js` are unchanged. Integrity comparison found only the three modified pre-existing files above; 550 original files compare equal (excluding runtime bytecode).

## Audit and information hierarchy

Before: API snapshot → adapter → raw status/qualification → oversized relevance/severity cells → mixed research-context rows → generic evidence → JSON. Unmatched articles returned early.

After: human event/relationship header and source/time → per-ticker 2×2 Relevance, Severity, Evidence, Priority → Why It Matters → Key Evidence → Research Gaps → Economic Channel → optional collapsed Exposure Path → Financial Impact → collapsed Score Details → compact Historical Context → shared Event Location → collapsed Audit Details → Direction guardrail.

All ticker analyses remain rendered and accessible by scrolling; no first-ticker truncation. The header reports the number of relationships for multi-ticker articles. Missing scores read `Not assigned`; actual zero stays zero. A relationship score of 0.15 remains 0.15, never 15%.

## Newly surfaced existing fields and deterministic rules

- Evidence assessment is now a primary metric, separate from priority, severity and financial impact.
- Direct article snippets, severity-rule snippets, curated edge identity/source, evidence basis and qualified economic channels are explicit.
- Existing financial-materiality level/reason retain their exact values.
- Existing relationship paths and score components are inspectable without recomputation.
- Geography precision is called out as country-level approximation; unresolved geography stays Unknown.
- Why It Matters branches on the existing relationship type. No LLM, direction inference or financial estimate is used.
- Research checklists match event subtype/type, existing classification and supplied channels: workforce, exports, production, legal/regulatory or commentary. These are explicitly verification questions, not assertions that answers are absent. Unmapped cases have no invented checklist.
- The generic backend `low_severity_event` header can use the existing direct-event channel (e.g. workforce_reduction) as its display label; backend classification and severity remain unchanged and auditable.
- Exposure paths use only direct article/ticker links or supplied matching edge paths; no missing dependency nodes are invented.
- Historical context remains collapsed when available. Its archive status, case identifier, limitation and supplied model/threshold/training-row values are displayed. Training rows are explicitly not comparable-event counts. All raw archived values remain in Audit Details. No win rate or directional probability is generated.
- Audit Details preserves the complete adapted API article, including original event enums, qualifications, scores, snippets, IDs, geometry basis/precision and all ticker analyses. It uses textContent, as do evidence and headings; URLs are restricted to HTTP(S).

## Browser verification and screenshots

Screenshots captured in the actual Flask page at 1280×720:

- [Direct company match](ui_refinement/direct_match.jpg): real unchanged NVDA commentary snapshot; High / Low / Moderate / Low.
- [Direct workforce event](ui_refinement/direct_layoff_qa.jpg): clearly labelled Synthetic UI QA; High / Medium / Moderate / Medium, Workforce / Restructuring checklist.
- [Mention only](ui_refinement/mention_only.jpg): Synthetic UI QA; Mention Only and Review, no qualified path. Expanded Score Details separately verified priority `Not assigned`, relationship 0.15.
- [No watchlist match](ui_refinement/no_match.jpg): real India article selected by clicking its globe marker; No match, Unknown severity, Review remain honest.

Synthetic scenarios used a separate temporary snapshot/server and never replaced the default 21-article production snapshot. The existing globe file is byte-identical, 10 real snapshot markers remain, the unmatched marker selects its article, and unknown-geography commentary has no marker. Right column remains 330px at this viewport. Original navigation, world clocks, market strip, left feed geometry, globe mechanics, fonts, animation and Bloomberg panel remain intact. Deep panel sections use the existing scrollbar.

## Tests and limitations

| Verification | Result |
|---|---|
| Full `tests/news` suite | 322 passed |
| Financial regression + refactor suite | 39 passed, including frozen 42 ticker/tab combinations |
| Existing Node model/adapter suite | Passed |
| New Node presentation suite | Passed: A–H, null versus zero, input immutability, supported direct/indirect paths, archive/components, generic event channel label |
| Legacy `test_news_ui` | 7 functional methods passed; one integrity method reports 3 pre-existing cache hash subtest failures |

Legacy hash failures are `data/cache/historical_financials/AAPL_balance_sheet_statement_5y.json`, `AAPL_cash_flow_statement_5y.json`, `AAPL_income_statement_5y.json` versus the older `tests/news_legacy_hashes.json`. All three are byte-identical to this task's starting project. No hashes, golden snapshots or caches were regenerated. Full logs are supplied, including expected simulated provider-failure logs in regression tests.

A–H coverage: real NVDA company subject, synthetic Apple direct workforce subject, mention-only Review, unmatched located event, unknown geography/no coordinates, absent historical context, null score/Not assigned and multiple ticker analyses. Browser additionally verified the live marker callback and rendered null priority.

The default snapshot has no compatible archived historical context; available-history rendering is tested with explicitly supplied test data, not presented as live historical validation. Checklists do not extract answers or assess completeness. Long evidence and multiple tickers can require scrolling. Existing backend precision/recall, severity policy, priority table, qualification, matcher, materiality and historical ML limitations are unchanged. No live news fetching or newly calibrated mathematical model is introduced.

## Future component hook

The helper exposes backend-supplied `relevance.components` or existing `relevance_components`, and `severity.components`, only when present. Score Details renders these as secondary supplied-component disclosures. A future UI can format Directness/Economic linkage/etc. when the backend actually provides them. No placeholder factors, weights, totals or arithmetic have been added.

## Reproduce

Run from the extracted project root:

```sh
python3 -m unittest discover -s tests/news -t tests
node tests/news_model_test.mjs
node tests/news_presentation_test.mjs
PYTHONPATH=tests:. python3 -m unittest test_regression test_refactor
PYTHONPATH=tests:. python3 -m unittest test_news_ui
python3 -m flask --app app run
```

The last test command retains the documented pre-existing cache hash failures. Existing project dependency/setup instructions still apply. Open `/news` after starting Flask.

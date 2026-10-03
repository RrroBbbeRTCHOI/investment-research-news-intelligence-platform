# NEWS INTELLIGENCE RELEVANCE-FIRST ARCHITECTURE AUDIT

Date: 2026-09-21. This audit precedes implementation. Source: the user's current `ML version/STOCK_SCREENER_NEWS_ML_V1` folder, including the previously delivered diagnostic corrections (all four patched files match). Work proceeds only in a separate `STOCK_SCREENER_NEWS_RELEVANCE_FIRST_V1` copy.

## 1. Executive finding

The backend is already close to the requested relevance-first architecture. `pipeline.py` does not import or invoke ML. It extracts a supported event, generates candidate channels and matches temporally eligible exposure records. No redesign of Event Engine, matching or model training is justified.

The missing piece is an explicit research-facing assembly contract: relationship-only relevance, separately qualified evidence strength, unquantified materiality, transparent attention priority, optional archived ML context and analyst-owned direction. The existing News screen is a clearly marked JavaScript demonstration, not connected to either backend or ML. Do not mistake its sample urgency/impact numbers for production scores.

Implement a small additive adapter and offline CLI, not a new matching engine. Preserve all legacy outputs and historical work. UI integration remains a later task; HTML/CSS/JS and routes stay unchanged.

## 2. Current architecture map

| Stage | Input | Output | Source | Status / gap |
|---|---|---|---|---|
| Provider ingestion | Provider responses | Raw response + fetched_at | news/providers/* | Existing; not run by backend pipeline |
| Article normalization | Listing/details | normalized_article_v2 | normalizer.py | Existing; hardcoded input paths, no change needed here |
| Event Gate | Article text | Accepted/rejected + reason | event_gate.py | Frozen English action/context rules |
| Event extraction | Accepted article | event_v1 + evidence_fields | event_extractor.py, schemas.py | Frozen; unknowns remain null |
| Candidate channels | Event facts/evidence | Hypotheses with basis | channel_generator.py | Existing, not company-impact facts |
| Mention mapping | Affirmed article names/symbols | MAG7 tickers_mentioned | constants.py, event_extractor.py | Mention is not economic impact |
| Exposure eligibility | Edges + article availability | Temporal/provenance exclusions | exposure_matcher.py | Existing; metadata-based checks |
| Company matching | Countries + channels + edges | One pair per MAG7 ticker | exposure_matcher.py | Exact joins and operational-subject restrictions |
| Legacy relevance | Match/mention/quality/severity | Heuristic score/components | exposure_matcher.py, constants.py | Mixes relationship, evidence quality and severity |
| Evidence/materiality/priority | Event + pairs | No unified research contract | Missing | Add assembly only |
| Historical ML | Curated label CSV + prices | OOS probabilities/metrics | material_reaction_model.py, ml/* | Independent experiment, preserve |
| News UI | Static demonstration array | Demo globe/cards | news_model.js, news_ui.js, news.html | `/news` only renders template; no backend context |

## 3. What is already working

Frozen action/negation/operational-channel rules; fabrication versus packaging specificity; nullable facts with field-level snippets; explicit country/channel compatibility; MAG7 aliases and service owners; named upstream dependency checks; evidence and temporal exclusions; no severity bonus without a qualifying edge; deterministic event IDs; per-event/ticker pair uniqueness; independently executed ML with chronological folds and train-only transforms.

The source includes the prior diagnostic fixes. Historical experiment files, old backup modules and outputs are to be preserved verbatim. No new model run or metric optimization is required for this architectural task.

## 4. What is currently overemphasized

ML is prominent in recent research activity, but **is not central in production matching code**. Do not invent an architectural ML dependency to remove. The UI's `urgent_score`/`impact_score` and hardcoded non-MAG7 sample tickers are demo data, unrelated to backend relevance; replacing them requires future UI integration, outside this task.

The legacy field name `relevance_score` hides evidence quality and severity contributions. This semantic mixing, not an opaque ML relevance model, is the issue to address at the new contract boundary.

## 5. Relevance Engine audit

Exact current formula:

`legacy = .15 * direct_mention + qualified_edge * quality * (.30 + .15 + .15 + .20 + .05 * severity_or_zero)`

Quality is 1 for verified and .5 for partial. Max over matched edges, not sum, prevents multiple-edge inflation. Scores are clipped to [0,1]. Mention alone is .15 and does not set matched=true. Verified indirect match with unknown severity is .80; with a mention .95. Country and channel are prerequisites and correlated components, not independently estimated evidence.

No later returns, labels, ML probabilities, Research ratings or valuation enter this score. Temporal and source fields gate eligibility. Record correctness itself is trusted, not independently established by the code.

Proposal: keep this legacy score and code exactly unchanged. In the new research object expose `legacy_relevance_score` for traceability and a versioned **relationship-only relevance score** using just the existing relationship terms: `.15*mention + .30*edge + .15*country + .15*channel`. Thus mention-only=.15, qualified unmentioned=.60, qualified mentioned=.75. This is an uncalibrated policy score, deliberately not rescaled to look like probability. Evidence remains an eligibility requirement but its quality multiplier and severity do not enter this numeric relationship score. Display descriptive levels (“Mention only”, “Qualified exposure”), not new tuned numeric cutoffs. No claim that .75 is 75% likelihood or stronger economic materiality.

## 6. Evidence / Exposure audit

Workbook: 27 flat Exposure Edges rows. Roles: buyer 12, seller 6, operator 9. Status: verified 12, partial 14, blocked 1. All seven MAG7 companies represented. The code supports additional dependency roles buyer/customer/input_dependency/dependent/procurement, but only buyer/seller/operator occur in this workbook.

Edges retain IDs, ticker, country, channel family/subtype, role, product/business, counterparty, facility/route, commodity/input, stage, exposure value/unit/band, evidence_status, source_url, source_locator, valid_from/to, known_at_utc, confidence and notes. These are explicit records, not a multi-hop graph; do not claim transitive relationships that are not recorded.

`edge_ineligibility` blocks unknown/hypothesis/blocked evidence, missing source URL/locator, planned capacity, unverified facility stage, missing/invalid timestamps, future knowledge/validity and expired edges. Date-only known_at is treated at end of day. UI can display preserved records/snippets. A status of verified is **curator-assigned**, not independent source verification.

Provenance caveat: Edge 1 combines a 2024 known_at with a source locator also mentioning FY2026 10-K; Edge 2 combines 2024 known_at with Apr. 2025 teardown evidence. Earlier assertions may be supported separately, but a composite record does not prove every field was available at the earlier date. Several source URLs are broad pages. Do not change dates/workbook or claim these sources were fact-checked here. Surface metadata validity separately from independently verified historical provenance, with review notes.

## 7. Economic Channel audit

23 supported channel families, including distinct advanced semiconductor fabrication and advanced packaging, regulatory export/general, legal, infrastructure, demand and commodity channels. Candidates retain basis/confidence/status and remain hypotheses. Exact country/family/subtype and operational entity compatibility control edge joins. Generic country overlap must not create a customer/supplier link.

Some event families (pricing, workforce, acquisitions) lack a dedicated existing exposure-family route. Expose their existing event type/subtype and evidence as research context, without modifying frozen taxonomy or fabricating an exposure channel. A no-qualified-match result is valid. Do not present generic candidate channels as established company pathways.

## 8. Ticker Matching audit

Distinguish `direct_mention`, `direct_exposure_match` (named company with qualified edge), `indirect_exposure_match` (unmentioned company with qualified edge), and review-only candidate status. “Direct” here is record/mention classification, not causal impact or a confirmed financial loss. A mention without an edge remains low-scored review-only; a quoted observer may be mentioned and is not automatically an affected target.

Existing strengths: MAG7 whitelist, semantic subject checks for operational events, explicit upstream relation requirement, per-ticker aggregation, refusal of narrow unsupported channels. Limits: English rule-based mentions, strict country joins can under-match geographically unspecified legal news; semantic subject checks do not cover every non-operational family; generic same-country/family evidence may be broad. Preserve these limitations rather than tuning historical matches.

Deduplicate by event/ticker and edge ID, reject duplicate/conflicting article identities, preserve exclusions separately. Cross-provider reports of the same real event are not semantically deduplicated by existing event IDs; flag as a future curation task, not a new clustering model.

## 9. Research Priority audit

No production research-priority layer exists. Add a versioned **ordinal attention policy**, not a probability or disguised direction score:

- Qualified edge with curator-verified relationship evidence → High attention.
- Qualified partial evidence only → Medium attention.
- Mention without a qualified edge → Review (explicitly unqualified).
- No mention and no qualified edge → no ticker candidate.

Within priority tiers use relationship-only relevance, then observed publication recency and stable IDs; never return direction or sort by future price movement. Explain the exact tier reason. “High” means evidence-backed relationship worth checking, **not high financial impact**. Severity/exposure band/value are shown as separate factors for investigation, not silently converted to financial materiality. Missing scale and segment contribution → materiality Unknown/unquantified. Recency tie-breaking does not change qualification or manufacture urgency from a missing timestamp. Historical ML does not affect tier or eligibility in this first version.

## 10. Historical ML role

Preserve B0/B1/B2a/B2b/B2, 2/3/4% targets, label maturation, grouping, features and all archived outputs. No imports of sklearn/training inside relevance assembly. Default historical context says experiment available offline with probability null; no invented class-level similarity statistic.

Optional explicit article→historical-case mapping can attach the existing saved OOS probabilities after identity/type/subtype/date/maturity/source-hash checks. Show all existing models/thresholds and original model/run metadata rather than selecting the best result. Label **retrospective OOS diagnostic**, never a live forecast: run generation after the event and historical backfill cannot be hidden. No automatic inference of H identifiers or join by event_type alone. A missing or inconsistent binding stays unavailable. Historical context has no effect on relationship qualification, relevance, priority or direction.

## 11. Leakage / hindsight risks

Reuse existing article availability resolver: live article max(publication,fetched); missing fetched means no automatic historical eligibility; explicit prediction time cannot precede available text; curated historical snapshot flags permit a published-time replay as originally designed. Snapshot flags are curator attestations, not independent verification.

Composite workbook source dates, broad source URLs, current text revisions, manually curated ML fields, missing precise historical timestamps and selection of cases remain limitations. Do not rebrand model OOS outputs as live as-of-event predictions. Require explicit case mapping and record checks; no outcome fields in new scores. No experimental probability can repair an unsupported exposure.

## 12. Proposed final architecture

`Normalized article → frozen gate/extractor → frozen event → frozen candidate channels → frozen exposure matcher → additive research assembly → JSON research contract + ranked research queue → future News UI consumer`

`Preserved historical OOS artifacts → optional validated retrospective-context adapter → historical_reaction field only`

Direction is always `Analyst judgment required`. Research Mode is outside both paths. Reuse `_resolve_prediction_time` rather than introducing a second replay clock. No route/app edits or shared services are necessary, so no shared-code boundary needs to be crossed.

## 13. Proposed UI data schema

Version `news_research_v1`: articles with article_id/headline/source/article_url, gate result, nullable event, candidate_channels, ticker_analysis and explicit no-match status. Each ticker row has:

- ticker, relationship_type, qualification/status;
- relevance_score, relevance_level, relevance_components, legacy_relevance_score, score_method;
- economic_channels supported by matched edges (separate from candidate hypotheses), relationship paths and raw matched evidence;
- evidence_strength with relationship-curation level versus article verification separately; no inferred trusted-source label;
- temporal_status including as_of and metadata-only verification caveat;
- materiality `{level: Unknown, status: unquantified, factors, missing_evidence}`;
- historical_reaction `{status, probability: null, predictions: [], disclosure, provenance}` or explicitly bound archived diagnostic;
- research_priority `{level, reasons, method}`, direction, explanation, next_questions.

Also expose edge exclusions, knowledge-layer status and a deduplicated research queue. Preserve nulls and source provenance. Rejected articles have event=null and no ticker rows. This new object is not the frozen event schema and does not mutate it.

## 14. Files that need modification

Prefer additive files only:

- `src/news/research_intelligence.py`: research assembly and offline CLI, reusing frozen modules.
- `src/news/historical_context.py`: optional strict archived-ML binding, no training.
- `tests/news/test_research_intelligence.py`: new behavior/invariance checks.
- `tests/news/test_historical_context.py`: optional ML binding and invalid-data checks.
- News-specific documentation, example output and regression/integrity evidence.

No existing production file needs modification. If implementation uncovers a required shared-code change, flag it before touching it.

## 15. Files that must NOT be modified

Research Mode modules/templates, ratings/valuation/DCF/financials/Earnings Quality/SEC; app.py/routes; templates and static assets; Event Gate/extractor/schema/constants/channel generator/matcher/pipeline; exposure workbook; every existing ML module, dataset, price cache, result and historical validation artifact. New CLI writes a new filename and refuses overwrite of existing files by default.

## 16. Minimal implementation plan

1. Complete this audit and preserve input hashes.
2. Add the adapter/CLI and optional archival-context reader, with pure serializable output and no network calls.
3. Add targeted tests for all requested cases and field isolation.
4. Run existing news suite plus new tests; inspect existing project-level verification instructions without exploring unrelated Research code; run applicable existing checks.
5. Compare frozen historical gate/event/channel/matcher outputs before/after using fixed extraction time; hash-check all copied original files.
6. Deliver standalone copied project, audit, documentation, representative JSON and verification report. Existing UI remains demo until separately wired; do not claim otherwise.

## 17. Tests required

Direct mentions; qualified direct and indirect exposure; unsupported relationships; future-known/expired/missing-time edges; multiple tickers; duplicate identity rejection/edge aggregation; evidence verified versus partial versus mention-only; metadata temporal validity; score formula; severity/evidence separate from relationship score; priority rules/tie ordering; known missing materiality; ML probability extremes cannot change eligibility/priority/direction; rejected events cannot acquire relevance; no implicit archived case mapping; bad source hashes/identity/date/maturity/probability records unavailable; historical outputs and all original files unchanged.

## 18. Definition of Done

An offline article analysis can state what happened, qualified/review-only stocks, relationship/channel/evidence, evidence limitations, metadata timing, transparent attention priority, unanswered scale questions, optional correctly labelled archived reaction context, and analyst-owned direction. Unknown/no-qualified-match remain legitimate outcomes. Existing tests pass, frozen results remain unchanged, and no ML tuning or Research/UI changes occur. A new backend JSON contract is delivered; a live UI integration is explicitly not claimed.

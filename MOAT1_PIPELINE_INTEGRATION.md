# Moat 1 Pipeline Integration V1

Date: 2026-09-10. This is an evidence integration patch, not the final full Moat 1 implementation. Work took place only in the new standalone `STOCK_SCREENER_MOAT1_PIPELINE_V1` copy. The previous working copy remains unchanged. Earlier architecture/regression reports in this project describe prior releases; this is the authoritative report for this patch.

## Root cause and evidence flow

The existing classifier recognizes narrative topics, but the legacy financial-line extractor discards topics without FINANCIAL_LINE_PATTERNS. The separate EQ table validator never consumes broader classifier results. More keywords alone therefore do not surface those disclosures in EQ.

The new focused adapter reuses the memoized 10-K HTML and existing clean_filing_text / classify_filing_text functions. It excludes HTML tables, script and style text, and consumes confirmed classifier matches directly. The result is merged additively into the existing evidence sidecar:

- HTML tables → unchanged strict table validator → validated_events / rejected_events.
- Non-table SEC text → supplied research_keywords.json → existing classifier → conservative local disclosure checks → narrative_events / rejected_narrative_events.
- Existing FMP statement observations remain statement_items, separate from both SEC paths.

The service and research context adapter already pass additive fields, so neither requires modification. Diagnostic rules are unchanged; narrative evidence is exposed to analysts without changing interpretation, sustainability or any score.

## Vocabulary isolation

The supplied data/research_keywords.json is included byte-for-byte. To prevent a vocabulary update from changing legacy scoring inputs, the old vocabulary is retained as data/research_keywords_legacy.json. Existing classify_sec_filing callers default to this frozen vocabulary; explicit keyword_file selection is additive. classify_filing_text uses the new vocabulary by default and is used by the narrative adapter. No global path mutation, monkeypatching or concurrency-dependent switching is used in production. The table row patterns, materiality calculation, NON_CORE_WEIGHTS and scoring code remain unchanged.

## Acceptance and boundaries

Accepted evidence requires a 10-K, accession and URL, a classifier Level >=2 with its evidence gate passed, an exact source-position match and a second classifier check on the local sentence. The local sentence must contain actual-event or financial-result discussion. Hypothetical/risk wording, negation, policy-only text, mismatched source positions and overly long/ambiguous disclosure spans are rejected conservatively. Nearby unrelated sentences cannot donate actual-event support.

Deduplication uses accession, source sentence position and normalized sentence text. Multiple keyword/topic hits on that disclosure retain matched_keywords, topics, categories and classifier_matches. Distinct sentence occurrences remain distinct; events are never summed. Sentence boundaries are computed once per document, with binary lookup per match.

Accepted rows preserve source metadata, topic/category, classifier level and evidence score, event type, quote, raw keywords, candidate amounts, confidence and reasons. Report date is explicitly filing metadata. A fiscal year is supplied only for an explicit single fiscal-year phrase without conflicting years; event period is not inferred from filing metadata.

This patch deliberately does not implement reliable amount-to-event linkage. All narrative event_amount and materiality values remain null; detected amounts are candidates only. No narrative/table/statement aggregation, recurrence inference, core/non-core split, causal conclusion or score penalty is produced. The UI separates the four evidence classes and explains these limits. The structured validator's period, accession, denominator, scale, sign, duplicate and reconciliation checks remain untouched.

## Regression results

100 test methods passed in 40.047 seconds. All 83 prior tests remain unchanged, plus 17 new tests. All 42 MAG7 ticker/tab routes pass. All 14 existing report types × seven tickers (98 comparisons) remain golden-identical. Fixture hashes are unchanged. Non-EQ template prefix/suffix hashes and rendered contracts remain unchanged.

Before editing the classifier, the current seven-symbol report set and Overview contexts were captured. The complete after-capture is exactly equal, including EQ classification/components, non-core score, Fundamental/Research Scores, rating, valuation, DCF scenarios and supporting model outputs. No expected golden values were changed.

The following values are **offline regression fixtures**, not current investment assessments. Each before/after pair is identical:

| Ticker | EQ / classification | Fundamental | Research | Rating | Fair value | Before/after |
|---|---|---|---|---|---|---|
| AAPL | 94.7 / Very Strong | 76.3 | 81.0 | Buy | $40.59 | unchanged |
| MSFT | 94.7 / Very Strong | 79.8 | 79.9 | Buy | $57.60 | unchanged |
| GOOGL | 94.7 / Very Strong | 79.8 | 76.9 | Buy | $75.78 | unchanged |
| NVDA | 96.5 / Very Strong | 80.5 | 80.3 | Buy | $98.72 | unchanged |
| AMZN | 96.5 / Very Strong | 80.5 | 68.3 | Neutral | $97.48 | unchanged |
| META | 100.0 / Very Strong | 85.5 | 72.5 | Neutral | $109.23 | unchanged |
| TSLA | 100.0 / Very Strong | 85.5 | 77.0 | Neutral | $143.86 | unchanged |

## MAG7 evidence validation

All seven Earnings Quality tabs build successfully. The preserved synthetic SEC fixture in each symbol produces one accepted narrative disclosure, zero strictly validated table events and two existing FMP statement observations. Ten classifier matches per symbol are conservatively rejected by the narrative adapter. This proves routing with the existing recordings; it is not a claim to have verified the latest actual filings for all seven companies. No ticker-specific production logic is present.

Separate synthetic cases exercise regulatory-credit, inventory-provision, supplier-financing and receivable-sale topics without adding financial-line patterns. Tests cover hypothetical/risk/policy/negated text, cross-sentence leakage, duplicate keywords, distinct disclosures, ambiguous amounts, absent/conflicting years, missing metadata, table exclusion, unchanged structured validation, statement continuity, actual rendered narrative UI and all-symbol context/diagnostic isolation.

## Wrong-year event audit

Confirmed pre-existing issue: analyze_financial_line_materiality computes year_match=False but returns the event, and calculate_weighted_non_core_events still includes a positive known-weight amount. A synthetic 2024 equity-security gain of 200 with a 2025 pretax denominator of 1000 still yields a weighted positive amount of 200. The test records this existing behavior rather than changing it.

Across the captured seven-symbol legacy reports, there are no wrong-year events; filtering them changes none of those recorded scores. This does not establish that live filings are unaffected. The scoring behavior is unchanged and remains a separately approved follow-up.

## Deferred-tax audit

Both ordinary deferred-tax/valuation-allowance policy text and a synthetic explicit current-period valuation-allowance charge with amount and net-income wording are hard-capped at Level 1 by the legacy classifier. The second example confirms a false-negative limitation. This patch does not remove or bypass the deferred-tax safeguard, and the adapter cannot promote Level 1 into accepted evidence. A safe generalized distinction between balance-sheet DTA/DTL disclosures and actual tax expense/release belongs in a separate classifier/methodology review with representative filings.

## Performance

Within a request, existing memoized SEC readers prevent repeated network requests for HTML, submissions or company facts. Re-running narrative evidence inside the same data_scope adds zero provider calls. Each of the four observed SEC boundaries is called once in the MAG7 independent-EQ tests.

Three cold AAPL offline runs per mode: table-only median 0.0248s versus narrative-enabled median 0.0296s; both use 10 provider-boundary calls. This is a small replay benchmark, not a live full-size 10-K latency guarantee.

## Exact patch file inventory

Modified:
- data/research_keywords.json
- src/analysis/filing_classifier.py
- src/analysis/earnings_quality_evidence.py
- templates/research.html (EQ branch only)

Added:
- data/research_keywords_legacy.json
- src/analysis/earnings_quality_narrative_evidence.py
- tests/test_narrative_pipeline.py
- MOAT1_PIPELINE_INTEGRATION.md

No rating, valuation, DCF, quality, materiality, non-core scoring, service cache or financial formula file changed. The complete copied project retains existing source, templates, fixtures, configuration and dependencies. Obsolete tests/results generated logs/measurement outputs are excluded from delivery; existing recorded historical FMP JSON files are retained because EQ uses them as its available cached data. No environments, bytecode, transient cache files or local credentials are included.

## Known limitations and final-Moat follow-ups

- Existing classifier vocabulary levels, substring matching, context windows and per-keyword match limits can miss disclosures. Local sentence boundaries and conservative negation filters favor precision over recall. Level-1 infrastructure/working-capital topics remain context unless existing classifier rules already qualify them; this patch does not promote them.
- Tables and mixed/nested formatting may contain meaningful narratives that are intentionally excluded from this narrative path. The strict table path continues independently.
- No robust paragraph/event coreference, amount linkage, numeric materiality or annual event-date resolution is attempted. Overlap remains possible even after sentence deduplication; do not sum evidence.
- No live MAG7 filing coverage/precision/recall benchmark was performed. The requested company-specific real-world examples were not forced into accepted results.
- Final Moat work should separately address representative-filing validation, amount/period linkage, wrong-year legacy scoring, deferred-tax classification and broader evidence coverage. Core Revenue, recurring-versus-one-off classification and full SEC Filing Intelligence remain out of scope.

## Run and verify

From the extracted project folder:

```bash
python3 -m pip install -r tests/requirements.txt
PYTHONDONTWRITEBYTECODE=1 python3 tests/run.py
python3 -m flask --app app run --host 127.0.0.1 --port 5000
```

Open /research?ticker=AAPL&tab=earnings-quality on the local Flask server. Live provider refresh still requires the existing FINANCIAL_API_KEY and SEC_USER_AGENT configuration. Offline tests require no live keys. Valid bundled historical cache data can be used by the existing EQ cache adapter; expired/missing data remains subject to the provider's normal behavior.

Keyword SHA-256: `e8ecdf3401c21455365361c04ba344a7942e0733b2d3cb333c861edb38e360ff`.

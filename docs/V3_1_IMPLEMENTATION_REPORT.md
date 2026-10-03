# V3.1 implementation and validation report

## 1. Scope and source provenance

New standalone copy: `STOCK_SCREENER_NEWS_VALIDATED_ANALYST_V3_1`.
The prior delivered V3 was copied; the user's working `Documents/Stock Screener/V3/STOCK_SCREENER_NEWS_VALIDATED_ANALYST_V3` was then compared byte-for-byte. Its only differing application source was `src/news/llm/gemini_provider.py`. That working Interactions API adapter was carried over **unchanged**. The user's NVIDIA input and previous live output were also retained for validation. Neither original project was overwritten. No credentials are included.

This is a reliability/clarity refinement, not an architecture redesign. Financial models, ratings, scoring weights, workbook, routes, Research templates, globe, CSS and page layout were not changed. `integrity.json` records 84 protected-file checks with zero changes; the file manifest records every changed/created release file.

## 2. Product files modified and purpose

Relative to the previously delivered V3 copy:

| File | Change |
|---|---|
| `src/news/v3_validation.py` | Field-specific, exact-source sentence filtering with retained/rejected sentence audit; classification corroboration; context-filtered V3 presentation geography. |
| `src/news/v3_config.py` | Configurable normalized BBC source policy, explicit policy disclosure, optional Gemini fallback model. |
| `src/news/v3_scoring.py` | Normalized source lookup and evidence-index disclosure. Equations and weights unchanged. |
| `src/news/llm/base.py` | Explicit prompt version and instructions for extractive, individually cited summary sentences. HTTP transport unchanged. |
| `src/news/llm/analyzer.py` | Bounded transient retries, actual-model fallback/cache, per-attempt audit, truthful request counts and article budget, successful-response-only accounting. |
| `src/news/llm/gemini_provider.py` | Carried over user's already-working Interactions API adapter verbatim; not a new provider redesign. Unchanged relative to user's live V3 source. |
| `src/news/research_v3.py` | Candidate/accepted/final classification audit, geography presentation safeguard, run/cache/success/unavailable counters. Existing qualification and severity authority preserved. |
| `src/news/ui_api.py` | Exposes classification audit and V3 presentation policy. V1/V2 top-level serialization remains compatible. |
| `static/js/news_presentation.js` | V3 primary/expanded relevance both use quantitative relevance; legacy numeric relevance stays in raw Audit only. |
| `static/js/news_ui.js` | Relevance disclosure and confidence evidence/policy index explanation; existing layout remains. |
| `.env.v3.example` | Empty fallback setting and explicit BBC-only source policy example. |
| `README.md`, `docs/V3_GUIDE.md` | Current setup, behavior, limitations and links; historical V3 report remains archived. |

No new product module, schema, financial formula, ML model or abstraction layer was created.

## 3. Tests and other files

Updated `tests/news/test_v3.py` only to match the user's working Gemini Interactions request/response contract. Added `tests/news/test_v31.py` (24 tests) and `tests/news_v31_presentation_test.mjs`.

The exact complete modified/created lists, including inputs, generated output, live semantic cache, logs, screenshot and report files, are in `v3_1/file_manifest.json`. Inputs copied from the user's live project are provenance imports, not invented fixtures. Golden financial snapshots and hash manifests were not regenerated.

## 4. Validation results

| Validation | Result |
|---|---|
| Full News suite | **381 passed**, including 35 existing V3 tests + 24 new V3.1 tests. |
| V3/V3.1 coverage | Sentence 1/3 retained and sentence 2 rejected; all-unsupported null; citation field boundaries; negation/attribution/line-wrap clipping; quoted sentence splitting; source policy; classification/geography; relevance API; retry/non-retry/fallback/cache; deterministic authority and future-edge rejection. |
| JS | **5 scripts passed**, including new V3.1 display checks. |
| Financial regression/refactor | **39 passed**, including all **42 ticker/tab** frozen comparisons. |
| Legacy UI suite | **7 methods passed**; **1 existing hash method failed in 3 AAPL cache subtests**. |
| Original live-project hash method | Same **3** failures reproduced before any V3.1 modification to those files. |
| Browser | NVIDIA page rendered; High / 0.45 heuristic; confidence 0.5985; expanded Score Details has no legacy 0.15; no horizontal overflow. Existing globe/three columns/Bloomberg retained. Screenshot included. |
| Live Gemini | One successful NVIDIA request, actual model `gemini-3.5-flash-lite`, no retry/fallback needed. A subsequent separate run reused cache with **0 requests, 1 cache hit**. |

The 3 pre-existing mismatches are `data/cache/historical_financials/AAPL_balance_sheet_statement_5y.json`, `AAPL_cash_flow_statement_5y.json`, and `AAPL_income_statement_5y.json`. Their bytes match the starting project; the older `tests/news_legacy_hashes.json` expects different bytes. No baseline was rewritten to hide this. Therefore the entire combined suite is **not claimed all green**.

The first sandboxed live request could not reach the network; it recorded a transport failure without retry. The permitted external-network rerun succeeded. Transport errors are intentionally outside the HTTP transient retry allowlist. Logs also contain environment-specific Arrow CPU-detection warnings; they did not cause the passing test suites to fail.

## 5. NVIDIA before/after

| Field | Prior live V3 | V3.1 live run |
|---|---|---|
| Provider/model | Gemini / gemini-3.5-flash-lite | Same |
| AI article class | commentary | commentary |
| AI type/subtype | company_event / executive_commentary | corporate_commentary / executive_statements |
| Final classification | commentary | commentary |
| Qualified relationship | NVDA direct_company_subject | Same, deterministic |
| Final severity/source | Low / rule | Same |
| Final event country | null | null; United States AI candidate rejected |
| Financial materiality | Not yet quantified | Same |
| Impact | null | null (all future components also null) |
| Primary V3 relevance | 0.45 existed but legacy 0.15 competed in Score Details | High / 0.45 heuristic; legacy only in audit/compatibility JSON |
| Source weight | null | 0.9 internal BBC policy |
| LLM self-assessment | 0.95 | 0.95 |
| Relationship evidence weight | 0.7 | 0.7 |
| Confidence index | null | 0.5985 = 0.9 × 0.95 × 0.7 |
| Validated short/full summary | short null; full 696 characters | both null with sentence-level rejection audit |
| Indirect qualified relationships | none | none |

AI subtype wording changed on the fresh live generation; it remains a candidate and did not change the deterministic final classification. This is not a claim of deterministic LLM output.

The new model supplied a single extractive summary sentence. The normalized source has author/image metadata fused into the first sentence, and a malformed scraped summary boundary. Under the conservative complete-sentence check, that shorter sentence cannot establish its own full source boundary; it is rejected rather than displayed as validated. This is an intentional recall limitation, **not a claimed summary-quality success**. No source cleanup or fuzzy entailment was invented to make this article pass.

`nvidia_same_response_revalidation.json` also runs the **old** semantic response through the new validator, without a new API call, so the original one-quote/whole-summary problem can be inspected independently of model variation. `nvidia_before.json` and `nvidia_after.json` retain the actual outputs.

## 6. Frozen 21-article replay

This replay is explicitly **provider=none**, not a 21-article live LLM performance benchmark:

| Counter | Result |
|---|---:|
| Articles / usable | 21 / 21 |
| Discrete events | 4 |
| Surface / background / noise rejected | 7 / 9 / 5 |
| Actual LLM requests / cache hits | 0 / 0 |
| Enrichment success | 0 |
| Enrichment unavailable (`enrichment_failure` compatibility counter) | 16, all `provider_disabled` |
| Skipped by cheap noise filter | 5 |
| Provider/network failures during this replay | 0 |
| Qualified ticker pairs / review candidates | 1 / 0 |

The 16 unavailable records are not 16 failed API requests. Classification, severity, geography, feed, relationship qualification, evidence, channels, materiality, research priority and direction match the prior frozen replay. See `sample21_comparison.json`.

The 51-item benchmark still has **zero human-verified labels**. Metrics stay null; no accuracy, precision, recall or provider-superiority claim is made. AI candidates remain non-ground-truth. Human review with provenance is still required.

## 7. Retry, fallback and cache details

Only HTTP 429/500/502/503/504 qualify for retry. Maximum **3 total requests per article**, including fallback; waits are 2s then 5s. A configured distinct Gemini fallback receives the third attempt only after two transient primary failures. Without fallback, all three use the primary. HTTP 400/401/403/404, unsupported model, transport/JSON errors and deterministic schema failures do not retry or trigger model fallback.

Records include provider, requested model, actual model, attempts with outcomes, attempt count, retry count and fallback_used. Final 429/401/403 blocks further uncached requests in that run. `llm_calls` is actual requests; `LLM_MAX_ARTICLES_PER_RUN` remains an article budget. A full run can make at most three requests per budgeted article.

Cache identity includes article content/metadata, full prompt, explicit prompt version, schema version, provider and **actual** model. Fallback success is never written under the primary-model cache key. Later runs may reuse a fallback that previously succeeded after this configured primary failed; explicit reprocessing refreshes it. Cache-hit attempt records describe the original generation, not new calls. Success writes are atomic and locks remain per key. Failures are not persisted as successful results.

Accounting covers only returned successful-response token usage. Failed attempts may be billable but their usage is unavailable. Fallback cost remains null instead of applying a primary-model price to a different model.

## 8. Source policy, grounding, classification and geography

Shipped source map is deliberately small: `{"bbc":0.9}`. Keys are casefolded and whitespace-normalized. `NEWS_SOURCE_QUALITY_JSON` replaces the entire map; `{}` disables weights. Other outlets remain null unless explicitly configured. This is not a claim that BBC has 90% factual accuracy.

**Internal source-quality policy weight; not a calibrated probability, truth probability, statistical accuracy estimate, or model confidence.** Confidence is an evidence/policy product, null if a required factor is missing. Its model self-assessment factor remains uncalibrated.

Summary citations must be exact spans in the named source and belong to the correct short/full field. Each sentence is checked against a complete original sentence and covering citation; only whitespace/terminal punctuation normalization is used. Unsupported sentences are removed individually; all rejected means null with explicit audit. No semantic similarity, second LLM judgment or investment interpretation is used.

Classification output separates `candidates`, `source_grounded_candidates` and deterministic `final`. Provenance-authenticated boolean/channel fields are still candidates, not final factual conclusions. Classification labels require existing deterministic corroboration to enter the accepted set. This limits semantic recall deliberately; the LLM continues proposing useful classifications for review.

V3 presentation geography excludes publisher/HQ/interview/nationality/referenced-location contexts. A country quote is checked in its original source field, not promoted to a headline framing rule. Unsupported final geography is null. These presentation filters do not change the exposure matcher's inputs or point-in-time evidence.

## 9. UI/API behavior and authority confirmations

V3 display uses only `ticker_analysis[].quantitative.relevance` as primary numeric relevance. Expanded scores/components use the same record. Legacy relationship_score is preserved in raw JSON/Audit for compatibility. V1/V2 replay displays remain compatible. Summary and Why It Matters remain separate. Confidence and relevance carry policy disclosures; no layout/CSS/template redesign was made.

- LLM candidates alone cannot create qualified ticker relationships.
- Final severity remains rule/validated; a Critical AI candidate does not promote Low commentary.
- Exposure known_at_utc / valid_from / valid_to and article replay-time eligibility remain intact.
- Confidence is not probability; relevance is not P(relevant).
- Research priority remains analyst attention, not expected return, direction or an ML input.
- Financial materiality and impact remain unquantified/null without supporting evidence.
- Weights, decay equation/default configurability and future null impact components remain unchanged.

## 10. Known limitations and intentional deferrals

Extractive grounding can reject accurate paraphrases and malformed/abbreviated source sentences. Context filtering can reject valid geography in mixed-context sentences. Classification corroboration is intentionally conservative and not a general entailment engine. Quotes and curated edges are not independent truth verification. Source policy is subjective and currently only supplies BBC by default.

Retry/fallback faults were simulated; no artificial live 503/429 was induced. OpenAI live validation, additional model comparisons, source-cleanup changes, source-policy calibration, reviewed benchmark collection, richer classification validation, financial impact estimation and ML training remain deferred. The live NVIDIA summary remains unavailable for the stated grounding reason. Existing AAPL legacy hash discrepancies remain unresolved intentionally.

## 11. Reproduce

From the standalone project root:

```sh
python3 -m unittest discover -s tests/news -t tests
PYTHONPATH=tests:. python3 -m unittest news.test_v3 news.test_v31
PYTHONPATH=tests:. python3 -m unittest test_regression test_refactor test_news_ui
node tests/news_model_test.mjs
node tests/news_presentation_test.mjs
node tests/news_visual_semantics_test.mjs
node tests/news_v3_model_test.mjs
node tests/news_v31_presentation_test.mjs
LLM_PROVIDER=none python3 -m src.news.research_v3 --input data/news/normalized/mag7_live_sample21_20260921.json
```

The combined financial/UI command retains the three documented pre-existing hash failures. To inspect the included live snapshot without making an API call:

```sh
NEWS_INTELLIGENCE_OUTPUT_PATH=data/news/research/v3_gemini_nvidia_test_output.json python3 -m flask --app app run
```

To rerun Gemini, place the key only in local `.env`/environment (not in source). Cache is reused unless `LLM_REPROCESS_EXISTING=true` is explicitly set:

```sh
LLM_PROVIDER=gemini GEMINI_MODEL=gemini-3.5-flash-lite python3 -m src.news.research_v3 --input data/news/normalized/v3_gemini_nvidia_test.json --output data/news/research/v3_gemini_nvidia_test_output.json
```

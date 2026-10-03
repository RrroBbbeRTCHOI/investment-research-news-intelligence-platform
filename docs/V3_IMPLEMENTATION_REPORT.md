# V3 implementation report

## Delivery scope

Complete standalone no-key implementation, as selected by the user. Original V2 Visual Hierarchy project not overwritten. Live provider round-trip validation is deferred until Gemini credentials/model are configured. Do not interpret this release as satisfying live-provider acceptance A or as an empirically validated financial prediction model.

## Architecture

Existing ingestion/normalization → cheap surface/background/reject prefilter → optional provider-independent structured LLM enrichment/cache → schema/source-span constraints → preserved V2 rule and point-in-time knowledge matching → quantitative diagnostics → stored V3 records → existing Flask News page. Pipeline stages retain candidates separately; their conceptual ordering does not let candidate text create exposure. The implementation computes the existing deterministic baseline and then reconciles LLM candidates against it.

Small focused modules handle configuration, provider transport, schema/cache, validation, scoring, pipeline and evaluation. No database, chatbot, live refresh enrichment, new framework or replacement app.

## Executed results

- Full News suite: **357 passed** (322 prior + 35 V3 tests).
- Last V3-focused verification after cache-race hardening: **35 passed**.
- Four Node suites: **passed**.
- Financial regression/refactor: **39 passed**, including original 42 ticker/tab frozen comparisons.
- Legacy UI suite: seven functional methods pass; the old integrity method retains three known AAPL cache-hash subtest failures. Those caches are unchanged, and no golden baseline was regenerated.
- Real 21-article offline pipeline: 7 surface, 9 background, 5 noise rejected; 0 LLM calls. All 21 remain accessible in All wire; 10 location markers retained.
- TSMC controlled QA: wafer-fab → AAPL Edge 6 and NVDA Edge 1; packaging → NVDA Edge 2; training has no matches. Workbook matching remains authoritative.
- Browser: Surface/All wire verified as 7/21 cards; source links are independent sibling anchors with _blank/noopener/noreferrer. Clicking an Original link leaves internal selection unchanged; external publisher-page loading was not verified. Summary-unavailable state is honest. See no_key_ui.jpg.
- Benchmark evaluation executed: 51 pending articles, 0 human-verified articles, no accuracy denominators. No fabricated results.

## Examples

**Real direct commentary**: “Nvidia boss rejects AI extinction fears as 'doomsday narratives'” (BBC). NVDA direct company subject, High relationship relevance, Low event severity, Moderate evidence, Low research priority; financial impact Not yet quantified. Summary fields are null because provider=none. Quantitative relevance is explicitly a normalized heuristic; confidence and impact are null. Full output: direct_commentary_example.json.

**Indirect supply-chain QA**: TSMC wafer-fabrication interruption with CoWoS explicitly unaffected. Existing workbook validates NVDA Edge 1 and AAPL Edge 6, not packaging Edge 2. This is a controlled regression article, not a new real-world historical validation. Full output: indirect_qa_output.json. Exposure paths use only existing edge fields and article context.

## Migration/configuration

Default read-only News snapshot is now news_research_v3_current.json; environment override supports old snapshots. Normalizer preserves listing-only original URLs. No Research route or scoring changes. See ../V3_GUIDE.md for every environment variable, provider switch and exact pipeline/test/benchmark command, and ../../.env.v3.example for an empty configuration template.

The no-key path requires no additional LLM SDK. Existing dotenv and stdlib HTTP are used. Model IDs are explicit user configuration, not silently assumed.

## Boundaries and remaining work

No API keys present and no live call attempted, by request. Provider request/response, refusal/error, cache, quota cap and usage contracts are mocked/offline tested only. Gemini account/model compatibility must be verified after configuration. Free-form semantics remain candidates; final matching/geography/severity still require existing deterministic support. This means existing recall gaps are not magically solved.

Summary numeric-token and citation checks are not entailment proofs. Source-quality ratings are absent by default; confidence therefore remains null. Relevance is policy math, not P(Relevant), and no probability calibration or statistical predictive value is claimed. Magnitude/directional exposure/surprise stay null. Research priority remains the existing transparent V2 ordinal category.

The 51-row review queue includes 30 historical manual snapshots, explicitly marked as not original full text. Human source/provenance review and benchmark labels are still required. No AI candidate is ground truth. The evaluator reports per-metric denominators, not an aggregate accuracy score.

All source/input/protected-file comparisons are recorded in integrity.json. Live credentials and environment files are excluded from packaging.

## Modified files
- `src/news/normalizer.py`
- `src/news/ui_api.py`
- `static/css/news.css`
- `static/js/news_model.js`
- `static/js/news_ui.js`
- `templates/news.html`

## Created files
- `.env.v3.example`
- `README.md`
- `data/news/benchmark/review_queue_v3.json`
- `data/news/benchmark/schema_v3.json`
- `data/news/research/news_research_v3_current.json`
- `docs/V3_GUIDE.md`
- `docs/V3_IMPLEMENTATION_REPORT.md`
- `docs/v3/benchmark_pending_report.json`
- `docs/v3/benchmark_run.txt`
- `docs/v3/browser_qa.json`
- `docs/v3/direct_commentary_example.json`
- `docs/v3/file_manifest.json`
- `docs/v3/frontend_tests.txt`
- `docs/v3/indirect_qa_output.json`
- `docs/v3/integrity.json`
- `docs/v3/legacy_ui_tests.txt`
- `docs/v3/news_tests.txt`
- `docs/v3/no_key_ui.jpg`
- `docs/v3/pipeline_run.txt`
- `docs/v3/research_tests.txt`
- `docs/v3/semantic_schema.json`
- `docs/v3/v3_final_checks.txt`
- `src/news/benchmark.py`
- `src/news/llm/__init__.py`
- `src/news/llm/analyzer.py`
- `src/news/llm/base.py`
- `src/news/llm/gemini_provider.py`
- `src/news/llm/openai_provider.py`
- `src/news/llm/schemas.py`
- `src/news/research_v3.py`
- `src/news/v3_config.py`
- `src/news/v3_scoring.py`
- `src/news/v3_validation.py`
- `tests/news/test_v3.py`
- `tests/news_v3_model_test.mjs`

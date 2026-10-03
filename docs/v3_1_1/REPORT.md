# V3.1.1 — focused corrective patch

## Changes and exact files modified

Only the requested validation, source-quality/confidence configuration/scoring, confidence presentation and related tests were inspected/edited. Work was performed in the existing local working copy `STOCK_SCREENER_NEWS_VALIDATED_ANALYST_V3_1`. The previously delivered V3.1 ZIP and the original project under `Documents/Stock Screener/V3/` were not overwritten. This delivery is a small replacement-file patch, not a rebuilt project.

| Modified file | Purpose |
|---|---|
| `src/news/v3_validation.py` | Replace complete-source-sentence equality with exact-citation-backed, bounded claim checks. Allow controlled paraphrases, compression and independently supported conjunctions; preserve per-sentence audit. Geography/classification/relationship functions unchanged. |
| `src/news/v3_config.py` | BBC → High; unlisted source → Unknown. Normalized/case-insensitive configurable tier lookup. Reject numeric source-weight configuration rather than inventing numeric-to-tier thresholds. |
| `src/news/v3_scoring.py` | Replace the confidence product with independent source/extraction/relationship components. Keep confidence.value as null for field-shape compatibility. Relevance and decay equations unchanged. |
| `src/news/ui_api.py` | Adapt old snapshot confidence products to qualitative components in memory at the read-only API boundary. No snapshot or cache file is rewritten. |
| `static/js/news_presentation.js` | Add pure component formatting; old composite numbers and numeric source weights are never promoted to the main confidence display. |
| `static/js/news_ui.js` | Display Confidence evidence: Source quality / Extraction confidence (model self-assessment) / Relationship evidence. Existing position, layout and CSS unchanged. |
| `.env.v3.example` | Replace numeric source policy example with `{"bbc":"High"}`. |
| `tests/news/test_v3.py` | Update only confidence/source-quality assertions for the deliberately changed contract. |
| `tests/news/test_v31.py` | Update only confidence/source-quality assertions; prior sentence/authority tests retained. |
| `tests/news_v31_presentation_test.mjs` | Update source-policy disclosure assertion from numeric weight to qualitative tier. |

New test files: `tests/news/test_v311.py`, `tests/news_v311_confidence_test.mjs`.
New report artifacts: `docs/v3_1_1/REPORT.md`, `nvidia_replay.json`, `focused_tests.log`, `js_tests.log`, `manifest.json`.

## Grounding behavior and limits

Each candidate sentence still needs a substantive exact citation in its named source field. Claim checks preserve ordered actor/predicate content, numbers, comparison signs/currencies, quoted wording, attribution, negation and modality. Explicit lexical rewrites support examples such as chief executive → CEO, dismissed → rejected, halted → stopped and delayed → postponed. Related claims joined by `and` or a semicolon can use separate source spans; elided subjects are restored only for the bounded supported construction.

Unlike V3.1, a supported sentence no longer fails solely because scraper metadata precedes it in the source. Original context surrounding a clipped citation is checked so it cannot hide a denial, reporting source or conditional. Attribution checks are local to the corresponding source sentence, not unrelated preceding sentences in the same citation.

Audit retains sentence, accepted, supporting_quotes, source_fields and reason, plus old singular quote/field aliases for compatible readers. A rejected sentence is removed individually; all rejected still gives null. Investment interpretation remains excluded. No LLM, embedding, fuzzy similarity, new model, training or external validation call is used.

This remains a **bounded deterministic paraphrase validator**, not general natural-language entailment or fact verification. Arbitrary synonyms, complex reordered syntax and unresolved pronouns may still be rejected when these checks cannot establish support. The patch does not claim universal paraphrase coverage. Provider prompts/cache keys are unchanged as requested.

## Qualitative confidence contract

Default: `BBC → High`. Unknown/unlisted sources stay `Unknown`. `NEWS_SOURCE_QUALITY_JSON` replaces the map; explicit `{}` leaves every source Unknown. Accepted tier values are High, Medium, Low and Unknown. Source-name matching is case-insensitive and whitespace-normalized.

If an existing local `.env` contains `NEWS_SOURCE_QUALITY_JSON={"bbc":0.9}`, change it explicitly to `NEWS_SOURCE_QUALITY_JSON={"bbc":"High"}`. Numeric source policies now raise a configuration error; no hidden numeric-to-tier conversion is applied. Local secrets/config files were not edited.

For NVIDIA the new confidence record is:

```json
{
  "value": null,
  "kind": "qualitative_evidence_components",
  "source_quality": "High",
  "extraction_self_assessment": 0.95,
  "relationship_evidence_quality": "Moderate"
}
```

There is no source-quality product, percentage or composite confidence score. The extraction value remains explicitly uncalibrated model self-assessment; High is a qualitative policy judgment, not factual accuracy. The API also adapts historical stored V3 confidence records for presentation without rewriting them. Stored summaries are not silently reprocessed on API reads: regenerate an analytical snapshot through the existing offline pipeline when applying the validator to older saved outputs.

## Focused validation

**44 Python tests passed; 3 JS scripts passed.** These cover the new 15 V3.1.1 tests plus related existing grounding, confidence, replay and API tests. No broad repository suite, financial suite, provider retry suite or live API calls were run for this patch.

Coverage includes supported paraphrase; unsupported new fact; wrong actor; changed number; negation/modal/conditional reversal; clipped citation context; multiple supporting spans; quote fidelity; numeric level versus change; comparison/currency and non-Latin entity preservation; normalized BBC/Unknown policy; old API snapshot adaptation without writes; UI components without percentage/composite; NVIDIA replay invariants. Test logs include environment-specific Arrow CPU-detection warnings, but all selected tests passed.

Reproduce from the project root:

```sh
PYTHONPATH=tests:. python3 -m unittest news.test_v311 news.test_v31.GroundingTests news.test_v31.IntegrationTests news.test_v3.V3Tests.test_quantification news.test_v3.V3Tests.test_missing_confidence_and_future_date news.test_v3.V3Tests.test_summaries_and_url news.test_v3.V3Tests.test_fake_citation_rejected news.test_v3.V3Tests.test_fabricated_number_rejected news.test_ui_api
node tests/news_presentation_test.mjs
node tests/news_v31_presentation_test.mjs
node tests/news_v311_confidence_test.mjs
```

## NVIDIA before / after

This is an **offline replay of the existing recorded Gemini response**, not a fresh live generation. The original normalized input and recorded response were not modified. No provider/cache operation was performed; LLM calls = 0.

| Field | V3.1 | V3.1.1 replay |
|---|---|---|
| summary_short | null | Source-grounded sentence retained |
| summary_full | null | Source-grounded sentence retained |
| Source quality | 0.9 | High |
| Confidence main display | 0.5985 composite | High / 0.95 self-assessment / Moderate components |
| Qualified relationship | NVDA direct_company_subject | Unchanged |
| Final severity | Low | Unchanged |
| Final geography | null | Unchanged |
| Relevance | 0.45 heuristic | Unchanged |
| Financial impact | null | Unchanged |
| Additional indirect relationships | None | None |

Retained short and full summary:

> Nvidia CEO Jensen Huang has described warnings that AI could lead to humanity's extinction by the next decade as "doomsday narratives".

The supplied normalized article contains this exact cited span; the preceding fused author/image metadata no longer disqualifies it. Separate tests establish paraphrase acceptance and combined-span support. `nvidia_replay.json` contains the detailed per-sentence audit and before/after values.

## Scope confirmation and applying the patch

No provider, retry/fallback, cache/key, ticker qualification, Exposure Knowledge Layer, final severity, point-in-time, benchmark, financial model, relevance formula, time decay, research priority, globe, Research Mode, template, CSS or page-layout code was changed. No unrelated module scan or refactor was performed. Existing original snapshots and enrichment cache files were not rewritten.

The ZIP contains only the 10 modified files, 2 new focused test files and 5 report artifacts, at project-relative paths. Apply those paths to the existing V3.1 project; this is not a standalone application ZIP. `manifest.json` lists before/after hashes for the explicitly scoped files only; no unrelated files were scanned to construct it.

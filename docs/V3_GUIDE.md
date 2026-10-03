# V3 / V3.1 configuration, research methodology and validation

## Integration and migration

The source project remains untouched. The new standalone folder is `STOCK_SCREENER_NEWS_VALIDATED_ANALYST_V3_1`.

The new offline entry point is `python3 -m src.news.research_v3`. Existing V1/V2 entry points, their schemas and tests remain usable. The Flask News default now points to `data/news/research/news_research_v3_current.json`. Set `NEWS_INTELLIGENCE_OUTPUT_PATH` to a V1/V2 snapshot to replay it; frontend/API accept all three versions. No route, financial service, Research template or globe implementation was changed.

The normalizer now falls back from detail.original_url to listing.original_url/listing.url instead of losing a listing-only canonical source link.

## Settings

Configuration is centralized in `src/news/v3_config.py`. It loads local `.env` without overriding explicitly exported environment values. `.env.v3.example` contains no secrets. Do not package a populated `.env`.

| Variable | Default / meaning |
|---|---|
| LLM_PROVIDER | `none`; also `gemini`, `openai` |
| GEMINI_API_KEY | Empty; required only for live Gemini |
| GEMINI_MODEL | Empty; set to an enabled structured-output model ID from your account |
| GEMINI_FALLBACK_MODEL | Empty; optional Gemini fallback after two transient primary failures; three attempts TOTAL |
| OPENAI_API_KEY | Empty; required only for live OpenAI |
| OPENAI_MODEL | Empty; set to an enabled Responses structured-output model ID |
| LLM_MAX_ARTICLES_PER_RUN | 10 uncached articles; retries are bounded to three requests per article; 0 disables new calls |
| LLM_REPROCESS_EXISTING | false; true explicitly replaces compatible cached results |
| LLM_TIMEOUT_SECONDS | 30; bounded to 0–120 seconds, exclusive of zero |
| LLM_CACHE_DIR | data/news/llm_enriched |
| NEWS_DECAY_HALF_LIFE_HOURS | 72 hours; explicit research policy default, not a fitted constant |
| NEWS_CLASS_HALF_LIVES_JSON | `{}`; optional class→positive half-life-hours overrides |
| NEWS_SOURCE_QUALITY_JSON | `{"bbc":0.9}` when unset; case-insensitive/whitespace-normalized publisher→internal policy weight. Explicit JSON replaces the whole map; `{}` disables all weights. Unknown sources are null |
| LLM_INPUT_USD_PER_MILLION | Blank; optional manually maintained input-token price |
| LLM_OUTPUT_USD_PER_MILLION | Blank; optional manually maintained output-token price |
| NEWS_INTELLIGENCE_OUTPUT_PATH | data/news/research/news_research_v3_current.json |

No model is silently selected, no key is printed, and no quota is used in none mode. Missing key/model is a recorded fallback, not an application crash.

## Run and switch providers

Existing ingestion/normalization are retained, including their existing FreeNewsAPI configuration:

```sh
python3 -m src.news.providers.freenewsapi
python3 -m src.news.providers.freenewsapi_details
python3 -m src.news.normalizer
LLM_PROVIDER=none python3 -m src.news.research_v3 --input data/news/normalized/freenewsapi_articles_normalized.json
```

For the included frozen real sample, no ingestion network call is necessary:

```sh
LLM_PROVIDER=none python3 -m src.news.research_v3 --input data/news/normalized/mag7_live_sample21_20260921.json
python3 -m flask --app app run
```

Later, configure `GEMINI_API_KEY` and `GEMINI_MODEL` in your local `.env`, then run:

```sh
LLM_PROVIDER=gemini python3 -m src.news.research_v3 --input data/news/normalized/mag7_live_sample21_20260921.json
```

Alternatively configure `OPENAI_API_KEY` and `OPENAI_MODEL`, then run:

```sh
LLM_PROVIDER=openai python3 -m src.news.research_v3 --input data/news/normalized/mag7_live_sample21_20260921.json
```

The Gemini implementation uses the documented generateContent structured JSON response format; OpenAI uses Responses `text.format` JSON Schema. References: [Google structured output REST](https://ai.google.dev/gemini-api/docs/generate-content/structured-output?hl=en), [OpenAI structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs). Provider/model availability must be checked in your account; live calls were intentionally deferred.

Cache keys include input text/metadata, full prompt, explicit prompt version, schema version, provider and actual model. V3.1 changes the prompt/key identity, so older semantic caches remain on disk but do not satisfy a V3.1 request. Repeated identical content is reused, even across process instances. A changed model/content/schema gets a separate record. Atomic replacement and per-key creation locks prevent partial files and duplicate concurrent requests. If a process crashes leaving a `.lock`, confirm no worker is active before manually removing that specific stale lock. Only HTTP 429/500/502/503/504 retry, with 2s and 5s waits and at most three total attempts. With a distinct configured Gemini fallback, attempt 3 uses that model after two transient failures. Other HTTP/transport/schema errors stop immediately. Final 429/401/403 opens a run-level circuit breaker. The actual model has its own success cache; a recorded fallback result may be reused on later primary-configured runs until explicit reprocessing. Attempts on cached records describe their original generation, not new requests. `llm_calls` counts actual requests, never circuit-breaker sentinels. Failed results are not persistent successes and may be retried in a later explicit run.

Usage stores input/output/total token counts when valid; missing accounting remains null. Cost is null without explicit pricing. This is a simple token estimate, excluding provider-specific discounts, cache/reasoning billing and taxes. Accounting covers the successful response only; token usage/cost for failed attempts is unavailable. Fallback cost remains null because primary-model prices cannot price a different model. Errors and aggregate fallback reasons are recorded without raw HTTP bodies or keys.

## Evidence boundaries

The semantic schema is in `docs/v3/semantic_schema.json`. It requires JSON, bounded types, null support, enums and exact-source citations. Invalid schema, refusal, incomplete/empty response, rate limit, timeout or invalid JSON falls back to deterministic analysis.

V3.1 validates both summaries sentence by sentence. Each retained sentence must match a complete original source sentence (whitespace/terminal punctuation normalization only) and be covered by a valid citation for that same summary field. Unsupported sentences and investment-direction sentences are dropped individually; an entirely rejected summary is null with per-sentence audit and an explicit reason. Paraphrases, clipped attributions and clipped negations do not pass. Quotes authenticate provenance, not truth. Conservative splitting can reject good text with malformed scraping boundaries or abbreviations. AI summaries remain article reports, not independent verification.

The existing V2 engine remains authoritative for final accepted event, ticker relationship, exposure channel, event matching and severity. V3.1 additionally removes publisher/HQ/interview/referenced-location context from presentation geography; this filtered geography is not fed into the exposure matcher. LLM event/channel/country fields are separate candidates in diagnostics. Classification labels need citation provenance plus corroboration by the existing deterministic classification to enter the accepted candidate set; unsupported labels stay in `classification_assessment.candidates`. Boolean semantic flags remain provenance-backed candidates, not new final flags. `classification_assessment.final` names the existing deterministic outcome. Semantic economic-class evidence may surface a background article for review, but cannot create a qualified relationship. A candidate severity is stored alongside rule-final severity, confidence, reason, source and rule evidence; it never promotes commentary to High by itself. This deliberately limits recall until broader semantic promotion rules can be human-validated.

The only V3 direct-subject addition recognizes explicit current AWS/service outage and Tesla/other known-company production-halt headline subjects, and only for an already accepted operational event with valid article time. Negated, historical and hypothetical triggers remain excluded. It adds no indirect edges.

Indirect candidates are reconciled against existing eligible matches. No eligible matching edge means unverified (or rejected for an outside-universe ticker), never qualified. Workbook evidence status, source provenance, operating stage, valid_from/valid_to and known_at checks are retained. Historical enrichment generated today is explicitly retrospective; it is not claimed to have existed at event time.

## Quantitative interpretation

No output is a statistically calibrated P(relevant), expected return or price direction.

**Relevance** is a normalized heuristic sum of supported indicators:

`0.10 × mention + 0.35 × direct subject + 0.35 × eligible edge + 0.10 × economic channel + 0.05 × edge country + 0.05 × edge counterparty`.

Each indicator is binary and each contribution is recorded. Sum of weights is 1. It measures supported relationship features, not financial exposure. Existing human-readable V2 relevance/priority categories remain; this experimental heuristic does not silently replace them.

**Confidence index** = configured source rating × source-grounded model self-assessment × relationship-evidence policy. Evidence factor is 1 for a curator-verified edge, .5 for partial edge, .7 for direct article subject without edge, .2 for mention-only. These are explicit policy values, not empirically calibrated reliability. Source policy disclosure: "Internal source-quality policy weight; not a calibrated probability, truth probability, statistical accuracy estimate, or model confidence." Only BBC has a shipped default (.9); no reputation inference or silent score for other publishers is made. If source rating or extraction self-assessment is absent, the product is null. No-key runs therefore normally have null confidence.

**Time decay** = `exp(-ln(2) × age_hours / half_life_hours)`. The default research half-life is 72 hours, configurable globally/by classification. Age is calculated at the recorded run time. Future/invalid dates produce null. It is a recency factor, not a model of actual event persistence.

**Future impact** keeps value, magnitude, directional_exposure and surprise null. No product is computed while these inputs are unestablished. Workbook exposure quantities remain evidence, not inferred event loss. Financial impact remains Not yet quantified / Insufficient evidence independently of relevance/severity.

## UI

The default Research Output view contains surface records. All Global Wire retains all articles; globe markers still represent available geography independently of ticker qualification. Selecting a background marker switches the list to All wire to reveal that article. Compact cards omit unknown/no-match clutter; detailed analysis preserves Unknown.

Card buttons select internal analysis. Original links are sibling anchors with `_blank` and `noopener noreferrer`, avoiding nested interactive controls and selection propagation. Summary is separate from Why It Matters. V3.1 shows quantitative relevance as the primary numeric measure, e.g. `High / 0.45 heuristic`. Score Details uses the same quantitative value/components. Legacy relationship_score remains only in compatible raw JSON/Audit, not a competing V3 display. Confidence is shown as an evidence/policy index with disclosure. The API exposes a presentation_policy directing consumers to ticker_analysis[].quantitative.relevance. V1/V2 snapshots retain their historical presentation.

## Benchmark and provider comparison

`data/news/benchmark/review_queue_v3.json` contains 51 pending items: 21 ingested real articles plus 30 existing manual historical snapshots with real-source references. Historical snapshots are explicitly not original full text. None is automatically human-verified. Review the source, fill only labelled expected fields, then record reviewer, reviewed_at and human_verified. Null means unlabelled; [] means a reviewed empty set. Recheck historical snapshot provenance before using it for claims.

Initialize another review queue (refuses to overwrite existing labels):

```sh
python3 -m src.news.benchmark init --input data/news/normalized/mag7_live_sample21_20260921.json --output data/news/benchmark/new_review_queue.json
```

Generate separate AI candidate labels after setting a provider/key/model:

```sh
LLM_PROVIDER=gemini python3 -m src.news.benchmark candidates --input data/news/normalized/mag7_live_sample21_20260921.json --output data/news/benchmark/gemini_candidates.json
LLM_PROVIDER=openai python3 -m src.news.benchmark candidates --input data/news/normalized/mag7_live_sample21_20260921.json --output data/news/benchmark/openai_candidates.json
```

These have `ground_truth:false` and `ai_candidate_only`; the evaluator does not treat them as reviewed labels.

```sh
python3 -m src.news.benchmark evaluate --benchmark data/news/benchmark/review_queue_v3.json --predictions data/news/research/news_research_v3_current.json --output docs/v3/benchmark_pending_report.json
```

The shipped report has zero reviewed articles and null metric denominators, not zero accuracy. For a reviewed benchmark, predictions must cover every reviewed article ID or evaluation fails rather than silently dropping difficult articles.

Multiple stored research outputs can be compared via `--predictions rule.json gemini.json openai.json hybrid.json`; each needs the documented research-record shape. Raw provider candidate files are not interchangeable with validated research records. Generate distinct outputs with the pipeline `--output` argument. Results include file hashes and separate per-run denominators. Missing feed state is explicitly reported and not treated as a rejected article.

Metrics: noise precision/recall (noise = should not surface; background/reject both not surfaced), classification/country/event-type accuracy, micro direct/indirect ticker precision/recall, economic-channel precision/recall, severity accuracy and coverage on labelled rows, reviewed exposure-path edge identity precision. There is no aggregate score, invented comparison, calibration claim or empirical impact forecast.

## Tests

```sh
python3 -m unittest discover -s tests/news -t tests
node tests/news_model_test.mjs
node tests/news_presentation_test.mjs
node tests/news_visual_semantics_test.mjs
node tests/news_v3_model_test.mjs
PYTHONPATH=tests:. python3 -m unittest test_regression test_refactor
PYTHONPATH=tests:. python3 -m unittest test_news_ui
```

The final legacy UI command retains the previously documented 3 AAPL cache hash discrepancies against an older manifest. V3 does not modify those caches or regenerate the golden baseline.

## Known limitations

No live provider call yet, by request. No human-verified benchmark labels yet. Structured output/citation constraints cannot guarantee factual semantic entailment. English keyword prefilter may miss unusual wording and non-English articles; All wire remains available. Existing gate/qualifier/geography recall limits remain. The statistical layer is transparent policy math, not a trained/calibrated model. Confidence may be null; financial impact generally remains unquantified. Existing archive models remain optional retrospective context, not live predictions. The filter and mathematical policies require benchmark-driven revision before claims of production accuracy.

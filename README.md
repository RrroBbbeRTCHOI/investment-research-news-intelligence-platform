# Stock Screener — Validated Analyst Intelligence V3.1

An evidence-constrained event-to-equity research engine for the existing Flask equity-research application. It is an analyst research aid, not a stock prediction chatbot.

```
Existing news provider → raw JSON → existing normalizer
  → cheap relevance filter → optional structured Gemini / OpenAI extraction + cache
  → citation/schema validation → existing point-in-time exposure validation
  → heuristic relevance / evidence confidence / configurable time decay
  → stored research JSON → Flask read-only API → existing News UI
```

V2 rule/matcher outputs are reused, not replaced by LLM guesses. LLM summaries and candidate semantics retain provenance; candidate tickers never qualify themselves. The Research Mode and exposure workbook remain unchanged.

## Quick start (no API key)

From this folder, using Python 3.11+ and Node.js for frontend tests:

```sh
python3 -m pip install -r requirements.txt -r src/news/requirements.txt -r src/news/ml/requirements.txt
LLM_PROVIDER=none python3 -m src.news.research_v3 --input data/news/normalized/mag7_live_sample21_20260921.json
python3 -m flask --app app run
```

Open http://127.0.0.1:5000/news. The included snapshot runs offline. Refresh never calls an LLM. Without enrichment, AI summaries are explicitly unavailable.

See [V3.1 implementation report](docs/V3_1_IMPLEMENTATION_REPORT.md) for this release, exact changes and validation. The earlier V3 report is historical. See [V3 guide](docs/V3_GUIDE.md) for provider switching, all environment variables, tests, benchmark commands, equations, provenance and limitations. See [implementation report](docs/V3_IMPLEMENTATION_REPORT.md) for changed files, executed tests and examples.

## Status

V3.1 includes a verified live Gemini NVIDIA run using the user's existing Interactions API adapter and `gemini-3.5-flash-lite`. OpenAI, retry and fallback fault cases are covered with mocks; no live OpenAI validation was performed. The default included 21-article snapshot uses no-key mode; the separate live NVIDIA output and cache are included without credentials. The benchmark contains 51 pending review items and **zero human-verified labels**; no accuracy claim is made.

Rules remain precise but incomplete; LLMs improve summaries/semantic coverage but can hallucinate. Source grounding is not independent verification. Curated exposure edges constrain indirect company relationships. Quantitative values are transparent heuristics, not calibrated probabilities. Financial magnitude, directional exposure and surprise remain null.

# News UI backend integration V1

## Audit before implementation

The prior `news_model.js` exported nine hand-authored demo events, demo quotes and market prices. `createEvents()` assigned relative timestamps. `news_ui.js` synchronously consumed those objects for article buttons, globe markers and the analysis panel. It fabricated demo urgent/impact scores and watchlist severity labels. `/news` only rendered a template; there was no News JSON route or asynchronous intelligence loader. Existing financial services belong to Research Mode and are not used for this snapshot adapter.

Current flow:

`configured research_intelligence JSON → GET /api/news/intelligence → adaptIntelligence → article list / valid-coordinate globe markers / original analysis panel`

## Changed files

- `app.py`: add only the News API route and one News output-path setting. Existing Research routes and request hooks are unchanged.
- NEW `src/news/ui_api.py`: read-only snapshot reader, shape validation, sanitized errors and compact event field projection. It does not call providers or run analysis.
- `static/js/news_model.js`: remove demo event/quote values; adapt articles to the existing event identity/title/geography contract. Preserve ticker analyses and backend score/relationship/direction. Existing position input validation remains; absent quotes yield unavailable P&L.
- `static/js/news_ui.js`: async API fetch, list and right-panel mapping, source/evidence links, per-ticker sections, loading/empty/error handling and valid-coordinate-only globe input. Preserve existing interaction controls, globe import, broadcast and clocks. Existing score-cell styles now display relevance and materiality instead of invented urgent/impact scores. Raw evidence/context is available in a disclosure inside the existing panel.
- `templates/news.html`: data-source and unavailable-quote labels only; structural panels, stylesheets and layout are retained.
- NEW `tests/news/test_ui_api.py`: seven Flask/API integration tests.
- `tests/news_model_test.mjs`: replace obsolete demo assertions with real-output adapter checks; retain input-validation checks and test price calculations only with explicit test quotes.
- `tests/test_news_ui.py`: retain the original app hash guard after removing only the additive News API block; original Research routes still require exact bytes.
- New report, screenshots, logs and integrity manifest in `docs/ui_integration/`.

All CSS, `news_globe.js`, map data, vendor assets, Research templates/JS/CSS, `src/ui/`, `src/analysis/`, existing financial services, News analytical modules, relevance weights, exposure workbook/matching, materiality/priority/direction rules and historical ML are byte-identical to the starting copy. The independent folder does not overwrite the original project.

## API and configuration

`GET /api/news/intelligence` returns HTTP 200:

```json
{"schema_version":"news_ui_v1","generated_at":"...","summary":{},"queue":[],"articles":[]}
```

Article metadata, gate, status, direction, candidate channels and original ticker analyses are retained. Event geography/type/time is projected to the fields used by the UI. Detailed ticker evidence, provenance, questions and historical context remain accessible. No provider raw responses, secrets or local file paths are exposed. Missing/unreadable/malformed snapshots return HTTP 503 with the same top-level collection fields plus a generic error. Responses use `Cache-Control: no-store`.

One configuration: `NEWS_INTELLIGENCE_OUTPUT_PATH`. Relative paths resolve against the project root; absolute paths are supported. The default explicitly selects the supplied current real-news output:

`data/news/research/mag7_live_sample21_run2_legal_fix.json`

The route does not scan newest mtime or accidentally choose a historical QA run. A later current output must be deliberately configured, or written to the configured path. The page fetches on load/reload; it is a backend snapshot viewer, not an ingestion scheduler or auto-refresh feed.

Run from the extracted project:

```sh
python3 -m flask --app app run --host 127.0.0.1 --port 5000
```

Open `http://127.0.0.1:5000/news`. To choose another already-generated current output:

```sh
NEWS_INTELLIGENCE_OUTPUT_PATH=data/news/research/current.json python3 -m flask --app app run --host 127.0.0.1 --port 5000
```

No API keys are needed just to view an existing snapshot. Existing project dependencies must be installed.

## Frontend semantics

One list item per article; queue articles are ordered ahead of other articles. Rejected and accepted-unmatched articles remain inspectable. All ticker analyses for a selected article render individually, retaining direct_event_subject, indirect_exposure_match and candidate_requires_review. Rows show source, available time, ticker score/level and available priority. Missing publication times in rejected backend records stay Unavailable rather than being inferred from generation time.

The analysis panel displays original relevance, relationship, economic channels, evidence strength, materiality, priority, historical-reaction availability, direction, explanation and evidence. Scores are not percentages, probabilities or stock-return forecasts. Materiality Unknown stays Unknown. Unavailable historical reactions stay Unavailable; available raw retrospective details remain under the evidence disclosure. Direction is read from backend, never synthesized as bullish/bearish.

No automatic demo fallback remains. Missing market/position quotes display unavailable in their existing visual slots. Positions are local editable input fields, not imported brokerage holdings. No new quote provider was added.

Only accepted events with finite numeric latitude/longitude in legal ranges reach the unchanged globe module. No country centroid or coordinate is invented. Selecting an article without coordinates updates analysis without focusing the camera on a made-up point. The current 21-article snapshot has no coordinates and therefore no event markers.

## Validation results

- `python3 -m unittest discover -s tests/news -t tests`: **303 passed** (296 existing + 7 new).
- `node tests/news_model_test.mjs`: passed. Real 21-article snapshot, direct/indirect cases, multiple tickers (clearly synthetic adapter-only additional ticker), empty/malformed data, coordinate validation, Unknown materiality, unavailable historical context, unchanged direction, position input validation and no default fake quotes.
- `PYTHONPATH=tests:. python3 -m unittest test_regression test_refactor`: **39 passed**, including all seven tickers × six Research tabs against the frozen baseline.
- Existing News UI functional/asset/containment tests: **7 passed**.
- Full `PYTHONPATH=tests:. python3 -m unittest test_news_ui`: 8 methods, **3 pre-existing hash subtest failures** inside the old financial-cache integrity method. AAPL balance-sheet, income-statement and cash-flow cache hashes already differ from that old manifest in the supplied V1.2 copy. Each file is unchanged by this integration; `integrity.json` records starting hashes. The manifest and caches were not regenerated to force a green result. All seven other methods pass.

Thus the requested `tests/news` suite passes; the older root-level UI manifest check is not wholly green for the documented pre-existing reason. Full captured logs are included.

## Actual browser end-to-end verification

Used the running Flask route, actual `fetch`, adapter and DOM (not just API serialization):

- Default real snapshot: 21 real headlines, four accepted and seventeen rejected; zero ticker analyses/queue entries, no fabricated MAG7 matches.
- Selected CNBC yen article: accepted/no-match explanation and Analyst judgment required displayed.
- Rejected article: rejected state and backend reason displayed.
- Separate local test server explicitly configured with existing round2 synthetic QA output: NVDA indirect CoWoS relationship 0.6, Edge 2, Strong (curated), High, Unknown materiality, historical Unavailable; META direct subject 0.15, Medium, direct evidence, no required exposure edge. These test cases are not mixed into the default feed.
- Empty temporary output: “No articles in this research snapshot.” and zero count.
- Malformed temporary JSON: clean unavailable state and “no demo fallback”.
- Browser console for the live success page contained no errors/warnings. Globe rendered with no markers, list selection continued to work.

Screenshots: `docs/ui_integration/live.png`, `indirect.png`, `direct.png`. Same three-column shell, globe, bars, typography, colors and existing CSS. Labels/content differ as required for truthful backend values; there was no visual redesign. Long analyses scroll in the original panel.

## Limitations

No new ingestion, automatic polling, price provider or geography inference was added. The default current snapshot has no qualified MAG7 pairs; direct/indirect display was verified separately with existing labeled QA output. Rejected records omit publication time in the backend output, so that time stays unavailable. Bounded API validation catches malformed shapes; unsupported analytical meanings are not repaired by the UI. Original financial-cache manifest drift remains as documented above.

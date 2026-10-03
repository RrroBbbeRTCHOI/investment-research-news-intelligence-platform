# Frozen V3.1.6 UI integration

## Scope and data flow

This is a standalone copy of the supplied V3.1 ZIP. Normalized articles already produced the frozen `data/news/research/stress_test_v1_v316_final_replay.json`. The existing Flask `/api/news/intelligence` route reads that snapshot through `src/news/ui_api.py`; `news_model.js` adapts it, and `news_ui.js`, `news_presentation.js` and `news_globe.js` render it. Refreshing the UI does not run research or fetch providers.

## Changed product files

- `src/news/ui_api.py`: select the existing V3.1.6 replay by default and retain event evidence-field provenance.
- `.env.v3.example`: document the same snapshot selection. An existing environment override still takes precedence.
- `static/js/news_model.js`: deterministic surface/severity/backend priority/recency ordering; final geography nulls remain null; rejected articles excluded from map data; no gate-based fallback interpretation.
- `static/js/news_presentation.js`: render supplied reasons and questions only; separate Qualified and Review; use final event subtype rather than infer it from a ticker channel; display location basis and precision.
- `static/js/news_ui.js`: compact feed metadata, explicit event and ticker sections, backend-only research status, shared selection and empty-selection cleanup.
- `static/js/news_globe.js`: separate coincident marker click targets by small screen offsets without changing geographic coordinates; support clearing selection.
- `static/css/news.css`: restrained metadata, Review and Unknown styling within existing layout.

Tests updated: `tests/news_presentation_test.mjs`, `tests/news_visual_semantics_test.mjs`. Their former expectations of frontend-generated questions and conclusions are replaced by supplied-data contracts. Added `tests/news/test_ui_v316.py` and `tests/news_v316_integration_test.mjs`.

## Architectural findings

The previous default snapshot contained 21 older articles. Some frontend text inferred classification and research questions from keywords. The frozen AWS record also retains stale legacy prose saying no qualified relationship exists although its final AMZN qualification is qualified. The UI uses final structured fields and their reasons; legacy payload remains inspectable in Audit. No backend record was rewritten to resolve this inconsistency.

## Results

- Before changes: 408 Python News tests passed.
- After changes: 413 Python News tests passed, 29.179 seconds.
- All 8 `tests/news*_test.mjs` suites passed, including the new frozen integration contracts.
- Modified Python compilation and four JavaScript syntax checks passed.
- Browser checked all requested cases plus ST05, shared card/marker selection, coincident Hormuz marker selection, and All Global Wire mode.
- Frozen display: 12 total, 11 surface, 1 reject; 4 qualified pairs and 4 review candidates retained. Six coordinate-bearing non-rejected map markers.
- No live research/provider API calls were made. The backend was not rerun or regraded. The supplied 9 PASS / 3 REVIEW / 0 FAIL grading remains historical QA, not an accuracy estimate.

| Case | Browser result |
|---|---|
| ST01 | US, institutional event origin, country approximation, Unknown, no ticker |
| ST03 | Export Controls, Medium, NVDA Qualified, geography Unknown |
| ST05 | Kaohsiung, city approximation, no forced ticker |
| ST07 | Outage, Medium, AMZN Qualified, AAPL Review |
| ST08 | Outage, Medium, MSFT Qualified via existing exposure match |
| ST09/ST10 | High, Strait of Hormuz, no inferred country/ticker; separate clickable markers |
| ST11 | Commentary, Low, NVDA Qualified |
| ST12 | Excluded from normal feed and map; inspectable in existing All Global Wire |

## Exact verification commands

Run from this extracted project folder:

```sh
python3 -m unittest discover -s tests/news -t . -v
python3 -m py_compile src/news/ui_api.py
for f in static/js/news_model.js static/js/news_presentation.js static/js/news_ui.js static/js/news_globe.js; do node --check "$f" || exit 1; done
for f in tests/news*_test.mjs; do node "$f" || exit 1; done
python3 -m flask --app app run --port 5077
```

Open http://127.0.0.1:5077/news. If your environment already defines `NEWS_INTELLIGENCE_OUTPUT_PATH`, set it to `data/news/research/stress_test_v1_v316_final_replay.json` before starting Flask.

## Visual checklist and limitations

Confirm High Hormuz cards appear first without forced tickers; AWS shows distinct Qualified/Review groups; Fed remains Unknown; card and marker clicks select the same article; Carnival appears only in All Global Wire and never on the globe. The existing three-column layout, time strip, asset controls, market tape and Bloomberg panel placement remain intact.

This is frozen snapshot presentation, not a live news refresh. Market quotes remain unavailable where previously unavailable. Bloomberg player placement/link were inspected; external video playback was not exercised. Missing financial impact/direction/channels do not acquire invented conclusions. Geography remains approximate where the backend says so. Coincident marker click targets have screen-space offsets only.

## Frozen integrity

Original project and ZIP were not overwritten. SHA-256 comparison against the extracted pre-edit copy permits only the nine modified original files listed above (seven product files and two existing tests). All other original source, templates, research snapshots, exposure data, benchmark source/ground truth/manifest, classification, geography, validation, scoring, provider, Gemini, retry/cache, PIT and financial logic remain byte-identical. New tests and this report are additive. Secrets and Python bytecode are excluded from the delivery ZIP.

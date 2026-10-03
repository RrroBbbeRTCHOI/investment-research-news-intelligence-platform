# News visual hierarchy and interaction semantics

Standalone output: `STOCK_SCREENER_NEWS_RESEARCH_INTELLIGENCE_V2_VISUAL_HIERARCHY`.
Starting project: `STOCK_SCREENER_NEWS_RESEARCH_INTELLIGENCE_V2_UI_REFINEMENT` (not overwritten).

## Changed files

| File | Purpose |
|---|---|
| static/js/news_presentation.js | Independent severity/qualified-watchlist/selection presentation contract; human tooltip; WATCHLIST label for unmatched events; existing component hooks |
| static/js/news_globe.js | Use severity palette directly; hide the 3D center for Unknown; marker qualification attribute; compact human tooltip |
| static/js/news_ui.js | Ticker-first feed badges; primary research order; checklist rows; collapsed evidence and historical context |
| static/css/news.css | Scoped hierarchy styles; hollow Unknown, cool Low, independent selection ring and watchlist dot; no column-width change |
| templates/news.html | Separate Low / Unknown legend; watchlist and selected-state keys |
| tests/news_visual_semantics_test.mjs (new) | Marker dimension independence, mention distinction, null/zero, checklist and component tests |
| docs/visual_hierarchy/* (new) | Five screenshots, test logs, integrity/browser results, explicitly synthetic QA snapshot and reproducible generator |
| docs/VISUAL_HIERARCHY_REPORT.md (new) | This report |

All earlier tests are preserved. No backend file, API, adapter, Research template, financial analysis module, production snapshot, financial cache, exposure workbook or golden fixture changed.

## Before / after

Before: Low and Unknown shared gray filled markers. Selection reused severity color. Feed classifications, priority and relationships competed. Evidence expanded ahead of economic channel and financial impact.

After: metadata → headline → prominent ticker/relationship/relevance badges plus severity. Mention-only has a subdued dashed ticker badge and no high-relevance promotion. Unmatched events remain valid Global Wire entries with a normal severity badge. Priority and classification remain in the right panel rather than cluttering the row.

Right panel: compact header → 2×2 metrics → Why It Matters → Economic Channel chips → Financial Impact → Next Research Questions. Unmatched metrics say WATCHLIST / No match, independently of event severity. All ticker analyses remain available; the first relationship does not replace subsequent ones.

Default open: the four primary research sections above, plus compact Event Location and direction guardrail.
Default collapsed: Evidence Details, Score Details, supported Exposure Path, Historical Context, Audit Details. Unavailable history uses a small summary status. Closed content is retained in the DOM; expanding Evidence preserves body snippets and provenance. A duplicate headline is referenced rather than repeated. Full raw snippets remain in Audit Details.

Research questions retain the existing deterministic mappings and use visual checklist rows. They explicitly ask questions and do not assert missing answers. There is no task persistence or scoring.

## Exact marker grammar

| Dimension | Presentation |
|---|---|
| Critical / High | Red `#ff5964` center and border |
| Medium | Amber `#ffb020` center and border |
| Low | Cyan `#43d8ff` center and border |
| Unknown | Neutral `#8197a4` hollow outline; transparent background; 3D center hidden |
| Selected | Bright `#eaf6ff` outer ring, 2px with 4px offset; severity color unchanged |
| Qualified watchlist relationship | Small white secondary dot at lower right, independent of severity |
| Mention-only / review candidate | No qualified dot; accurately described in feed and tooltip |

The qualification indicator reads the backend's `qualified_…` status, explicitly excluding direct mentions / Mention only. It does not compute a new relationship. The severity palette never reads relevance or qualification. Selection never changes the severity category. Unknown stays hollow when selected. Existing selected mesh scale behavior is retained for filled markers.

Tooltip: location, headline, explicit Severity, explicit Watchlist (including Mention only / Review candidate where applicable). No backend enum appears in primary tooltip text.

## Screenshots and visual QA

All five screenshots use clearly labelled **Synthetic Visual QA** articles, processed through the unchanged V2 backend. The synthetic output is stored under docs, never configured as the default production snapshot. It provides known geography to test a Low company match; no geography was invented for the real NVDA commentary.

- [Unknown unmatched](visual_hierarchy/unknown_unmatched.jpg): Mexico; neutral hollow selected ring, Unknown, valid No match.
- [Medium unmatched](visual_hierarchy/medium_unmatched.jpg): Saudi Arabia; amber, no qualified dot, Review.
- [NVDA direct-company match](visual_hierarchy/nvda_direct_company.jpg): Taiwan; cyan plus independent dot, High relevance / Low severity / Low priority.
- [AAPL workforce](visual_hierarchy/aapl_workforce.jpg): Japan; amber plus independent dot, High / Medium / Medium, five existing workforce questions.
- [Mention only](visual_hierarchy/mention_only.jpg): India; AAPL dashed badge, Unknown hollow marker, no qualified dot or exposure path.

Additional browser checks: AAPL/NVDA multiple relationships both render; all secondary disclosures start closed; Evidence Details expands with original body evidence; Score Details retains 0.15 and null→Not assigned; unmatched marker click selects its article; tooltip shows human fields; raw enum tokens absent from primary panel text. Browser results are in `visual_hierarchy/browser_qa.json`.

At 1280×720, the right column remains 330px. The metrics and concise Why block fit above the existing Bloomberg panel for these headlines. Lower research sections remain scrollable. Globe remains visually dominant; no large overlay added. Existing font, navigation, clock, market tape, Bloomberg geometry and responsive column rules remain intact.

## Tests

- Full News suite: **322 passed**.
- Existing model/adapter Node suite: **passed**.
- Existing presentation Node suite: **passed**.
- New visual-semantics Node suite: **passed**.
- Financial regression/refactor: **39 passed**, including existing frozen 42 ticker/tab comparisons.
- Legacy UI suite: 7 functional methods pass; the integrity method has the same **3 pre-existing AAPL cache hash failures** (balance sheet, cash flow, income statement) versus the old manifest. These files are identical to the starting project. No baseline/hash/cache was regenerated to hide the failures.

Test logs and integrity results are included. The mechanical portion of `news_globe.js` from resize through rotation, animation, disposal and selectEvent is byte-identical to the starting project. Sphere projection, texture, countries, camera and controls are unchanged; only event marker appearance/tooltip were edited. All backend and Research files compare equal.

```sh
python3 -m unittest discover -s tests/news -t tests
node tests/news_model_test.mjs
node tests/news_presentation_test.mjs
node tests/news_visual_semantics_test.mjs
PYTHONPATH=tests:. python3 -m unittest test_regression test_refactor
PYTHONPATH=tests:. python3 -m unittest test_news_ui
```

The final test command retains the documented old manifest failures.

## Limitations and future hooks

No new analytical scoring, prediction, direction, qualification, geography extraction or historical ML. Direction stays Analyst judgment required. Actual zero remains 0; null remains Not assigned. Unknown remains unknown.

Markers with identical coordinates can overlap, as before; this pass does not add clustering or alter geography/interaction mechanics. All such articles remain selectable from the feed. Long headlines or multiple ticker analyses can require scrolling. Checklist rows are visual, not interactive task state. Real default data may lack event geography and therefore has no marker; synthetic QA does not change that.

Only supplied component objects render in Score Details: Relationship, Severity, Evidence, Materiality and Priority hooks. The existing relationship component object may later carry Directness/Economic linkage/Channel specificity/Evidence support. No placeholder numbers, bars, factors or weights are created.

To launch the normal production snapshot, use existing setup instructions then `python3 -m flask --app app run`. To reproduce the separate synthetic QA, run `PYTHONPATH=tests:. python3 docs/visual_hierarchy/build_qa_snapshot.py`, then launch with `NEWS_INTELLIGENCE_OUTPUT_PATH=docs/visual_hierarchy/synthetic_qa_snapshot.json python3 -m flask --app app run`.

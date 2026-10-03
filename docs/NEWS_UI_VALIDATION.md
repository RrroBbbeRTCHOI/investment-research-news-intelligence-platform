# News Intelligence V1 validation

## Automated verification

**Final full suite: 219 tests passed in 300.494 seconds (211 existing + 8 new).** Run from the project root:

```sh
python3 tests/run.py
```

Standalone JavaScript checks (Node.js):

```sh
node tests/news_model_test.mjs
```

The suite retains the 211 existing tests, including all 42 Research ticker/tab combinations, frozen numerical output contracts, legacy scores/ratings, Moat 1/2/3 outputs and cache behavior. Eight added News tests cover containment, route rendering without provider calls, local static/GeoJSON delivery, dependency checksums, model calculations, time zones/accessibility and the stream/fallback contract. Ninety-three source/data/fixture hashes additionally protect unchanged Research functionality.

One obsolete assertion comparing the old News template to its Phase 1 hash was removed because this task explicitly replaces that page. DESIGN and Research guards remain. No fixture recordings or golden results were regenerated.

## Browser checks

The real Flask app was started on `127.0.0.1:5057`, debug/reloader disabled, for testing. Browser checks used the in-app Chromium browser. Layouts were inspected at 1280×720, 1024×768 and 390×844; the viewport override was reset afterward.

| Requirement | Observed result |
|---|---|
| Flask starts | Passed; real local server started |
| `/research` and Research Mode | Existing offline route/regression suite, including all 42 combinations; protected source bytes unchanged |
| `/news` | Browser and Flask test-client load passed; no news provider call |
| Local geography | `/static/data/countries.geojson` returns 177 features; no runtime remote geometry fetch |
| Real globe | WebGL sphere rendered; local texture and markers ready |
| Console | No application warning/error entries observed in successful page checks |
| Triangle artifacts / disappearing land | None observed in initial Asia, rotated Africa/Asia, Americas, zoom and resize checks |
| Dark fallback | Initial loading background is dark; no blue sphere observed |
| Left collapse | Expanded list becomes a 48px rail; expands again |
| Globe expands | At 1280px, center canvas changes from 670 to 902px; right column stays 330px |
| News scrolling | Independent list scroll observed (687px scroll position in one check) |
| Marker click | Brazil marker selects Brazil analysis and corresponding list row |
| List click | Fed and other list items update analysis, selected marker and globe view |
| Filter/selection | NVDA filter yields one row; selecting a China globe event clears incompatible filter and reveals its matching row |
| Country hover | Hover over India displays its name and highlight |
| Country selection | India retains cyan selection after cursor movement/rotation |
| Drag / wheel / buttons | Orbit drag, wheel zoom, reset and zoom buttons exercised |
| New York / London / Hong Kong clocks | All use the requested Intl time zones and update each second; UTC also updates |
| Positive P&L | AAPL demo price 228.40, cost 215, qty 10: +134.00 / +6.23% |
| Negative P&L | Cost changed to 250, qty 10: −216.00 / −8.64% |
| Unknown price | UNKNOWN ticker: No quote / P&L unavailable / N/M; no fabricated quote |
| Arithmetic boundaries | JS tests cover zero cost, zero quantity, invalid/negative inputs and numeric overflow |
| Market tape | Eleven illustrative markets render, sign colors applied, pause/resume works |
| Analysis scrolling | Independently scrollable; event changes reset analysis to its heading |
| Bloomberg location | Only a child of right panel; correct 16:9 iframe src created after click |
| Stream failure alternative | Always-visible external Watch live link; Player help restores a WATCH LIVE placeholder. Load timeout/error also invokes the fallback |
| Center bar containment | Top 38px and bottom 32px strips remain within center; neither extends into right column |
| Resize | Canvas tracks column and viewport size; no page horizontal overflow observed |
| Small screens | Initial rail, center map, then stacked analysis/broadcast; clocks/monitor use horizontal strip scrolling |
| Research integrity | No Research template/module, scoring, valuation, SEC, Moat or route edits |

The external YouTube iframe was created with muted, non-autoplay parameters. Actual stream playback was not confirmed in this browser session (the embedded surface remained blank); the external fallback link was present. YouTube can impose embedding, regional or network restrictions. Parent-page code cannot inspect every cross-origin player error. This is not reported as a verified live-video playback test.

Visual checks describe the sampled browser views, not a guarantee across every GPU/browser. The sphere-texture approach eliminates the specific country-polygon cap and wall geometry that produced the reported prototype artifacts. WebGL/data failures show a readable message while keeping list/analysis usable.

## Data and packaging scope

The news events, scores, exposure labels, market tape and position quotes are labelled demo data. These tests do not validate live financial/geopolitical intelligence. Clocks are real; the requested external broadcast is separate.

The complete original Moat 3 project is included alongside the new News assets, with no original overwrite. Environment files, keys, virtual environments, generated bytecode/test output and repository internals are excluded. Dependency licenses and local country data are included. ZIP integrity and member bytes are checked at packaging.

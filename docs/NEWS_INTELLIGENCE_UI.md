# News Intelligence UI V1

## Run

This is a complete standalone copy of `STOCK_SCREENER_MOAT3_V1_VALUATION_EXPECTATIONS`. The source project was not edited. Use Python 3.13 and install the preserved dependencies:

```sh
python3 -m pip install -r requirements.txt
python3 app.py
```

Visit `http://127.0.0.1:5000/news`. Existing Research uses your own locally supplied `.env` and provider credentials as before. No credentials are included. News geography and JavaScript dependencies are local and do not require API keys or a Node build. Bloomberg playback requires an internet connection and permission from YouTube to embed the stream. Node is needed only for the standalone JavaScript test.

## Scope and files

Only `templates/news.html` changes in existing product code. `app.py`, every existing `src/` module, Research templates, financial methods, scores, ratings, SEC/Moat logic, cache architecture, research universe, and original fixture files are unchanged. The existing `/news` route serves the new template without any Python changes.

New files:

- `static/css/news.css`: isolated News styling, three-column desktop grid, thin 38px/32px center bars, 48px collapsed rail, independent scrolling and mobile fallback.
- `static/js/news_model.js`: shared illustrative event schema, quote/market fixtures, filtering, age labels and pure position arithmetic.
- `static/js/news_ui.js`: clocks, list/analysis synchronization, collapse, position editor, tape and click-to-load broadcast.
- `static/js/news_globe.js`: single-version Three.js sphere, geographic texture, spherical country picking, markers, rotation/zoom and resize lifecycle.
- `static/data/countries.geojson`: 177 Natural Earth 110m country features served from `/static/data/countries.geojson`.
- `static/vendor/three/`: Three.js 0.180.0 module/core, matching OrbitControls, MIT license.
- `static/vendor/d3.min.js`, `D3_LICENSE`: D3 7.9.0 geographic path/containment support, ISC license.
- `static/vendor/manifest.json`: source URLs, byte lengths and SHA-256 asset checksums.
- `tests/test_news_ui.py`, `tests/news_model_test.mjs`, `tests/news_legacy_hashes.json`: News integration/model tests and byte-level preservation checks.
- This document and `docs/NEWS_UI_VALIDATION.md`.

The only existing test change is `tests/test_regression.py`: the original News-template byte-hash assertion is no longer applicable to this explicitly authorized replacement. The DESIGN and Research assertions are retained. No golden snapshots or provider recordings were changed. New layout/asset tests replace the obsolete News hash contract, and new source hashes protect unchanged Research code/data.

## Data honesty and connection points

The page is a complete functional **UI**, not a connected news-intelligence backend. All nine headlines, relative timestamps, relevance/urgency/impact scores, exposure labels, eleven market quotes and seven demo equity prices are explicitly illustrative. Their timestamps are relative to page initialization. The LIVE workspace label does not claim a live feed. No scoring, recommendation, portfolio holdings or financial provider methods are changed.

`createEvents()` creates the single event list consumed by the news buttons, globe markers and analysis renderer. Replace that boundary with validated provider events in a future integration; do not separately fetch for each visual component. DOM output uses text nodes rather than inserting event HTML. Country selection highlights a geographic feature; it does not invent country-level news analysis.

`positionValue()` accepts a quote dictionary, so a future price adapter can supply observations without changing arithmetic. This V1 supports nonnegative long-position quantities and costs in USD. Unknown tickers have no quote/P&L; no fallback price is invented. Zero basis is N/M. Negative, nonnumeric or overflowing inputs are rejected. The position lasts only for the page session; there is no external persistence. The full cost basis appears in the editor and monitor tooltip, alongside per-share cost and quantity.

## Globe stability decisions

Inspection of the supplied Moat 3 folder found a static News prototype, no country file and no installed Globe.gl/Three.js prototype. Rather than introduce the polygon-material problems mentioned in the brief, this implementation uses one pinned Three.js dependency and matching OrbitControls. No Globe.gl instance or second Three.js build is loaded.

Country geometry is projected into a local equirectangular canvas texture and applied to a real 3D sphere. D3's spherical path clipping handles dateline crossings; exterior winding is normalized to its convention. This avoids country mesh triangulation, cap/side-wall conflicts, altitude jumps, overlapping polygon materials and depth flicker. The underlying sphere is dark from its first render; a MeshBasicMaterial deliberately avoids lighting-dependent country disappearance. Hover and selection repaint only the texture, with no altitude changes. This is a geometric stability choice rather than a flat map substituted for a globe.

Raycasting against the sphere gives geographic coordinates for country containment/selection. Event meshes sit close to the surface and have projected accessible button targets, hidden behind the horizon. The news list supplies an equivalent keyboard-accessible selection path. Rotation uses damped OrbitControls, zoom is bounded, and ResizeObserver tracks both column animation and browser resizing. Keyboard arrows and +/- are also supported. Context-loss and data-loading failures preserve the list/analysis workflow and show a reload message.

Future day/night rendering has a separate named scene group. Country fill is not responsible for sunlight, night shading or a terminator. No unfinished day/night shader is shipped.

Natural Earth 110m is a generalized map: small islands and fine borders are simplified. Its boundaries and names are a source cartographic convention, not a geopolitical assertion. Country texture resolution is 4096×2048, with limited antialiasing/anisotropy; very close zoom will not reveal street-level detail.

## Broadcast and responsive behavior

Desktop: left list / center map / fixed right analysis. Only the left collapses. The time/position strip and market tape are children of the center column. The broadcast is a child of the right column below a separately scrollable analysis area. No broadcast content spans below the globe.

Below 720px, the map/list occupy the first row and the analysis/broadcast stack beneath. On initial small-screen load the list starts as a rail. The compact time strip can scroll horizontally to expose the position editor without growing vertically. No page-level horizontal overflow was observed at the tested breakpoints.

The broadcast shows a compact 16:9 placeholder until **Load live player** is clicked, then creates the requested `https://www.youtube.com/embed/QB5BNdBFujE` iframe with `autoplay=0&mute=1`. An always-visible **Watch live** link opens the user-specified stream externally. Cross-origin iframe playback failures cannot reliably be detected from the parent page, so the link remains available regardless of the iframe load event. A 12-second load timeout or iframe error restores a WATCH LIVE placeholder; Player help provides the same fallback when a cross-origin error still emits a load event. We do not claim to control YouTube's regional/embedding availability.

## Sources and licenses

- [Three.js OrbitControls documentation](https://threejs.org/docs/pages/OrbitControls.html) and [Raycaster documentation](https://threejs.org/docs/pages/Raycaster.html).
- [Natural Earth source data](https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_110m_admin_0_countries.geojson). Runtime does not request GitHub; the exact downloaded asset is included and hashed.
- [Natural Earth public-domain terms](https://www.naturalearthdata.com/about/terms-of-use/).
- Three.js MIT and D3 ISC notices are retained in `static/vendor/`. This project does not claim affiliation with Bloomberg.

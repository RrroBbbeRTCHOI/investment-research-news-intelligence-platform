# Meridian Research dossier integration

## Architecture and scope

The active project is `Codex UI/Production/STOCK_SCREENER_NEWS_LIVE_PRODUCT_V3_2_3_1` from the supplied Codex UI 2 archive. Other production folders and previously delivered ZIPs were not overwritten.

Flask/Jinja remains the application architecture. `build_research_dossier_context(ticker)` orchestrates existing production company, rating, financial interpretation, valuation, historical, earnings-quality and SEC services. It contains display formatting and adaptation, not new analytical formulas.

All eight sections render in one response. Legacy `?tab=` selects the initial scroll/focus target. Sticky section links use browser history and scrolling without reloading. Company selection still makes a ticker-specific Research request. Relevant Events hydrates asynchronously through the unchanged News API.

The request reuse layer and bounded 300-second shared service cache are retained. Dossiers are cached by ticker. Historical and SEC metadata outputs now also use that existing cache, avoiding duplicate transport when legacy context is constructed for a different section URL. Their original loader bodies are hash-locked. Compatibility company/screener contexts remain available to integrations and strict baseline comparisons; they no longer determine visible sections.

Cold construction is synchronous to preserve the existing request-scoped reuse semantics. Warm page loads reuse the complete dossier; no new concurrency framework or architecture was introduced. Live-provider latency remains unmeasured.

Each aggregated section has an independent fallback. The route also tolerates failure of its compatibility context. Unknown values are not replaced with zero. Detailed financial interpretation, exact values, period-aligned earnings analysis, source evidence and model caveats remain in expandable audit panels.

## Figma → production mapping

| Figma component | Existing production sources | Supported runtime fields | Rejected or unavailable prototype content | Jinja partial |
|---|---|---|---|---|
| CompanyHero | company service; rating service | identity, quote/change, market cap, EV, growth, margins, ROIC, rating/component scores | SEDOL/ISIN, target horizon/price, invented standalone Profitability score | _company_hero.html |
| Financials | financial interpretation; historical financials | three statements, compact current/prior values, margins, EPS/growth when fiscal years match, annual trajectories, real interpretation | invented business narratives and segment mix | _financials.html |
| Valuation | rating report; valuation interpretation; existing peer median function | current and low/base/high fair values, P/E, forward P/E, historical and peer median P/E, production expectations/confidence | copied targets, fake peer multiples, unsupported multiple cards/consensus | _valuation.html |
| HistoricalTrends | historical trends and benchmark services; existing EQ ROIC history | real financial series, company/SPY/QQQ normalized price paths, return spread, ROIC history | fictional total-return/alpha figures; missing ROE history | _historical_trends.html |
| EarningsQuality | earnings quality service | all six model components, exact scores/weights, original model inputs, period-aligned diagnostics, evidence | fabricated Core Revenue score or new methodology | _earnings_quality.html |
| FinancialHealth | financial interpretation and company metrics | cash, debt, net cash, debt/equity, equity, ROE/ROIC, FCF margin and histories where available | fictional capital structure/buyback amounts or solvency narratives | _financial_health.html |
| SecFilings | existing EDGAR metadata and normalized earnings evidence | actual returned forms/dates/accessions/URLs; evidence matched by accession | invented filing history/counts/summaries | _sec_filings.html |
| CorrelatedEvents | existing News Intelligence API | headline, source, timestamp, relationship, severity, evidence, backend relevance explanation and ticker/event links | hard-coded event stories or changed severity/match semantics | _relevant_events.html + research_events.js |

## Presentation and interaction verification

Browser skill workflow used the actual, unchanged React Figma prototype and the Flask production templates. Production previews replayed the frozen provider fixtures through real services; fixture company names deliberately identify themselves as synthetic. No Figma mock data was inserted into production.

Compared rendered Hero, Financials, Valuation, Historical Trends and Earnings Quality side by side. Verified overall rhythm, 7/5 Hero, 4/8 Financials, 8/4 Valuation/History, six progressive EQ rows and 5/4/3 Financial Health composition. Also inspected Financial Health and SEC evidence, light/dark themes, all three statement modes, historical metric selection, AAPL/NVDA/MSFT switching, initial section focus and ticker-scoped News handoff.

The browser's native viewport override did not change its measured viewport. The test-only preview therefore provides isolated iframe viewports for the 1440×900 reference and 390px mobile checks. Measured widths matched their requested frame sizes; mobile content did not overflow horizontally outside its scrollable controls/tables. No production iframe architecture was added.

Remaining differences from Figma are intentional or explicit:
- Production-backed content, headings, line counts and missing-data states differ from the prototype.
- Financial tables use supported current/prior periods, not fabricated third-period observations.
- Valuation visualizes production fair-value prices, not mock forward-P/E positions.
- The historical financial selector drives an additional real chart; no fabricated alpha/total-return claim.
- Model scores are numeric, with unavailable Core Revenue/Profitability shown honestly.
- The SEC detail disclosure includes actual accession-linked evidence, not fictional filing summaries.
- The top bar uses production routes and a native ticker selector; unsupported Portfolio/Markets pages, avatar and prototype search are not copied.
- Local sans/monospace font equivalents and simple icons are used; this is not a pixel-identical typography/icon reproduction.
- Live event cards were exercised with isolated backend-shaped JavaScript tests. The offline browser preview intentionally reports News unavailable and does not start live ingestion.

## Performance

Measured using `PYTHONPATH=tests:. python3 tests/benchmark_dossier.py`, `perf_counter`, frozen offline provider replay. These measurements exclude real external network latency. Full-route cold timings include the retained compatibility/screener contexts and HTML rendering.

| Ticker | Cold dossier | Cached dossier | Cold full route | Cached section route | Cached provider calls |
|---|---:|---:|---:|---:|---:|
| AAPL | 782.68 ms | 13.83 ms | 1998.00 ms | 63.62 ms | 0 |
| NVDA | 999.85 ms | 14.06 ms | 1631.12 ms | 50.74 ms | 0 |
| MSFT | 594.40 ms | 14.93 ms | 1283.74 ms | 48.09 ms | 0 |

## Regression status

Final complete Python rerun: **741/741 passed**, 393.293 seconds (`PYTHONPATH=tests:. python3 -m unittest discover -s tests -p 'test_*.py'`).
Final focused dossier/UI retest after presentation refinements: **20/20 passed**.
JavaScript: 20/20 passed (`node --test tests/*.mjs`): ten existing News test files plus ten new dossier/event interaction tests.
New dossier contracts: 13/13 passed, including strict backend/golden comparisons, all sections and tickers, three modes, SEC, no prototype values, cache reuse, and individual section failure injection. Research continues using the original shared appearance-preference key, without editing News.

Frozen numerical fixtures and exact comparison functions were not changed. Existing numerical golden comparisons remain strict; there are no new tolerances, rounding allowances or skipped analytical comparisons. Updated legacy UI tests now follow included partials and the continuous layout. The request-scope exception test injects an unrecoverable render error rather than incorrectly requiring a recoverable provider failure to crash the dossier.

News templates/CSS/JS, Globe, Three.js, OrbitControls, GeoJSON, Bloomberg and News backend files are byte-identical to the supplied archive. A new archive-derived manifest also locks analytical model sources. The only changes to existing historical/SEC services are cache wrappers; their original loader bodies are independently hash-checked.

## Files changed

Existing files:
- app.py
- src/services/historical_trends_service.py
- src/services/sec_filing_service.py
- templates/research.html
- templates/financial_interpretation.html
- static/js/research_events.js
- tests/test_regression.py
- tests/test_refactor.py
- tests/test_research_level5_ui.py
- tests/test_moat3.py
- tests/test_moat15.py
- tests/test_news_ui.py

New files:
- src/ui/research_dossier.py
- static/css/research_dossier.css
- static/js/research_dossier.js
- templates/research/_research_nav.html
- templates/research/_company_hero.html
- templates/research/_financials.html
- templates/research/_valuation.html
- templates/research/_historical_trends.html
- templates/research/_earnings_quality.html
- templates/research/_quality_audit.html
- templates/research/_financial_health.html
- templates/research/_sec_filings.html
- templates/research/_relevant_events.html
- tests/test_research_dossier.py
- tests/research_dossier_test.mjs
- tests/research_dossier_locked_hashes.json
- tests/benchmark_dossier.py
- tests/preview_dossier.py
- RESEARCH_DOSSIER_INTEGRATION.md

The Figma application source was not modified. Its npm dependencies were installed solely to run the reference preview.

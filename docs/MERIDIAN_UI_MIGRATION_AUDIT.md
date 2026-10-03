# Meridian UI Migration Audit

## Decision

Codebase A remains the runtime and functional source of truth. Codebase B is used only for visual hierarchy, typography, spacing, state presentation, and navigation concepts. The React/Vite runtime and all prototype data are excluded.

## File-by-file mapping

| Production file | Figma reference | Production logic preserved | Design migrated |
|---|---|---|---|
| `app.py` | `App.tsx` | Flask routes, validation, caching, data contracts | Eight research destinations and connected Research/News mode model |
| `templates/research.html` | `TopNav.tsx`, `ResearchPage.tsx`, `CompanyHero.tsx` | Jinja fields, route links, screener, company selection, charts | Compact top navigation, premium surface hierarchy, company workspace styling |
| `templates/research.html` | `Financials.tsx` | Existing company fields and financial interpretation | Denser metric cards and table hierarchy; no Figma statement values |
| `templates/research.html` | `Valuation.tsx`, `HistoricalTrends.tsx` | DCF/expectations output and Chart.js datasets | Typography, section spacing, comparison-card treatment |
| `templates/research.html` | `EarningsQuality.tsx` | Cash Conversion, Accrual Quality, Margin Stability, ROIC Quality, Non-Core Earnings, Core Revenue Quality | Evidence-first hierarchy and restrained status color |
| `templates/research.html` | `FinancialHealth.tsx` | Existing debt/equity, FCF margin, ROE, ROIC, and financial interpretation liquidity output | New first-class Financial Health tab and compact resilience cards |
| `templates/research.html` | `SecFilings.tsx` | Existing EDGAR metadata provider | Filing cards with honest unavailable state; no prototype filings |
| `templates/research.html`, `static/js/research_events.js` | `CorrelatedEvents.tsx` | `/api/news/intelligence`, ticker relationship fields, real severity/evidence | Relevant Events cards and contextual News deep links |
| `templates/news.html` | `TopNav.tsx`, `NewsPage.tsx` | Left feed / center globe / right analysis geometry, clocks, portfolio, markets, Bloomberg position | Meridian brand, compact top bar, shared theme control |
| `static/css/news.css` | `NewsFeed.tsx`, `NewsPage.tsx`, `AnalysisPanel.tsx` | All existing layout and behavior selectors | Premium black/daylight tokens, typography, feed selection, analysis grouping |
| `static/js/news_ui.js` | `NewsFeed.tsx`, `AnalysisPanel.tsx` | Real API adaptation, filtering, portfolio, markets, Bloomberg player, live polling | Reading order, independent severity/match/evidence treatment, contextual transitions |
| `static/js/news_globe.js` | `GlobeView.tsx` (style reference only) | Three.js renderer, OrbitControls, GeoJSON sphere, markers, drag/zoom/camera/country interaction | Existing marker polish retained; SVG globe explicitly rejected |
| `static/js/news_model.js` | none (prototype uses local objects) | API normalization and current schema compatibility | None |
| `static/js/news_presentation.js` | `AnalysisPanel.tsx` labels | Existing semantic separation and product wording | Labels reused in revised hierarchy |
| `static/js/news_product.js` | portfolio fragment in `NewsPage.tsx` | Position persistence, totals, selection identity | None |
| `src/ui/research_context.py` | `ResearchPage.tsx` | Existing services and adapters | Routes new tabs to existing services only |
| `src/services/sec_filing_service.py` | `SecFilings.tsx` | Existing SEC provider | Exposes latest supported metadata with failure isolation |

## Mock and placeholder data found in Codebase B

- `NewsPage.tsx`: all five news events, lat/lon, severity, relationship interpretations, market tape values, and world times are hard-coded.
- `SearchOverlay.tsx`: company search universe and recent state are hard-coded.
- `CompanyHero.tsx`: score cards, KPIs, NVIDIA identity, price, sector, and descriptions are hard-coded.
- `Financials.tsx`: all three statements and year-over-year changes are static NVIDIA figures.
- `Valuation.tsx`: valuation metrics, fair-value levels, and peer multiples are static.
- `HistoricalTrends.tsx`: chart series, benchmark selection defaults, and return statistics are static.
- `EarningsQuality.tsx`: all six dimension scores, evidence, and interpretations are static.
- `FinancialHealth.tsx`: liquidity, debt, capital structure, and narrative are static.
- `SecFilings.tsx`: filing list and extracted highlights are static.
- `CorrelatedEvents.tsx`: three events and their relationships are static.
- `GlobeView.tsx`: SVG land paths, marker data, portfolio ticker values, and performance values are static.

None of these values were copied into production.

## Regressions avoided

- Replacing `news_globe.js` with `GlobeView.tsx` would remove the real WebGL sphere, country hit testing, OrbitControls, lat/lon placement, camera behavior, and shared-coordinate marker handling.
- Replacing `news.html` with `NewsPage.tsx` would move or remove Bloomberg Live, weaken independent analysis scrolling, and replace live clocks/markets/positions with constants.
- Mounting the React prototype would introduce a second routing/runtime layer and bypass Flask/Jinja contracts.
- Copying prototype section data would conflict with production providers, model definitions, and unavailable-state policy.
- Treating evidence, severity, and relationship as a single score would regress the production semantic contract.
- Using Figma SEC and financial values would create unsupported claims.

## Integration risks and controls

| Risk | Control |
|---|---|
| Provider calls fail or are slow | Existing service exception handling and explicit unavailable states remain visible |
| Old byte-hash test blocks intentional presentation edits | Hash protection now excludes only the four explicit integration boundaries; analytical models, providers, assumptions, and fixtures remain frozen |
| New Research tabs accidentally invoke new calculations | Tabs route only to existing `financials_service` or basic-company data; Relevant Events reads the existing API |
| Query-state context is lost | Research event links include ticker/event; News chooses that event/ticker on first valid snapshot; News-to-Research links retain ticker and event |
| Theme divergence | Both modes use the same `research-platform-theme` browser key |
| Responsive three-panel collapse | Existing breakpoints are preserved; only widths and visual tokens are refined |
| Bloomberg or globe replacement | DOM containment regression tests remain and implementation files are retained |

## Safe staged migration

1. Shared Meridian tokens and top navigation.
2. Research overview/company workspace treatment.
3. Financial presentation styling over current fields.
4. Valuation and historical styling over current data/charts.
5. Earnings Quality styling plus Financial Health backed by existing metrics.
6. SEC metadata and Relevant Events backed by existing services/APIs.
7. News Feed refinement without changing filtering or selection logic.
8. Analysis reading order with separate severity, match, and evidence.
9. Query-backed Research ↔ News context retention.
10. Globe visual polish only; no implementation replacement.
11. Shared daylight/premium-black preference.
12. Python, JavaScript, Flask/template, and browser regression checks.

The current implementation completes the bounded UI migration across these stages while intentionally leaving analytical formulas, event qualification, scoring, providers, and API schemas unchanged.

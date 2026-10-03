# Migration report: Phases 2–7

## Completed work

| Phase | Delivered |
|---|---|
| 2 | ContextVar request scopes and shared Yahoo/SEC reads with defensive copies; no reuse of exceptions |
| 3 | Raw company assembly moved to company_service; original dashboard calculations relocated intact to analysis/company_metrics |
| 4 | Research/recommendation orchestration moved to rating_service; existing analysis entry points and all scoring/report contracts retained |
| 5 | Explicit Financials, Valuation, Historical Trends, Earnings Quality, SEC Filing and Screener service entry points; exact existing tab policies |
| 6 | Bounded 300-second shared company/rating results, ordered-peer keys, same-key load coalescing, original-data timestamps, request-only DCF/history reuse and atomic FMP cache writes |
| 7 | research_context reduced from 1,381 to 104 lines; output adapters separated; all 42 route combinations and full backend snapshots validated |

## Methodology protection

No weights, score thresholds, recommendation names, tax/WACC assumptions, FCFF
formula, growth denominator, financial period selection, debt definition, DCF
scenario, price definition, or frontend field was intentionally changed.
All golden JSON and the Phase 1 manifest remain byte-identical.

A structural source comparison found 327 existing src-level function ASTs
unchanged after ignoring decorators. The exceptions are relocated UI helpers,
provider-access functions, orchestration delegates, historical P/E data access,
and the atomic cache writer. Pure dashboard helpers were moved rather than
merged. The unreachable duplicate component pipeline after the old rating return
was removed as part of extracting that function; it never executed.

## Compatibility and test changes

All original routes and template files remain intact. The two analysis report
entry points remain callable under their old names. Existing context helper
names are imported/re-exported where relocated. No placeholder was turned into a
new working UI feature and no rating output was replaced with N/A.

The Phase 1 test framework needed two structural updates: reset the new service
cache between test cases, and observe tab dependency calls in their new service
locations. Assertions and golden outputs were not relaxed. Additional tests
exercise the new boundaries and preserve provider constructor-error behavior.

## Changed existing files

- `app.py`
- `src/analysis/materiality.py`
- `src/analysis/quality.py`
- `src/analysis/rating.py`
- `src/analysis/recommendation.py`
- `src/analysis/valuation.py`
- `src/data/financial_data.py`
- `src/data/historical_financial_data.py`
- `src/data/market_data.py`
- `src/data/sec_data.py`
- `src/data/sec_filings.py`
- `src/models/dcf_model.py`
- `src/models/fcff_model.py`
- `src/models/valuation_engine.py`
- `src/ui/research_context.py`
- `tests/support.py`
- `tests/test_regression.py`

## New code/test files (reports and evidence are additional)

- `src/analysis/company_metrics.py`
- `src/data/reuse.py`
- `src/data/yahoo_provider.py`
- `src/services/__init__.py`
- `src/services/cache.py`
- `src/services/company_service.py`
- `src/services/earnings_quality_service.py`
- `src/services/financials_service.py`
- `src/services/historical_trends_service.py`
- `src/services/rating_service.py`
- `src/services/screener_service.py`
- `src/services/sec_filing_service.py`
- `src/services/valuation_service.py`
- `src/ui/adapters.py`
- `src/ui/formatters.py`
- `tests/measure_performance.py`
- `tests/test_refactor.py`

## Limits

Cross-process caching, background workers and new UI loading states are not part
of this migration. Current broad failure fallbacks, Neutral on unavailable
recommendation inputs, and the existing N/A states remain intentional compatibility
constraints. No live-provider or browser-rendering claim is made.

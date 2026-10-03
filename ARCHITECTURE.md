# Refactored architecture

This is the Phase 1 project copy, migrated without replacing the product or its
financial methodology. The original project and the Phase 1 golden fixtures are
untouched. Flask, both HTML templates, navigation, search, tickers and field names
remain the same.

## Request flow

```text
Flask before_request: data_scope(persistent=True)
  research route (unchanged)
    existing (ticker, tab) page cache
      research_context.build_company_context (compatibility adapter)
        selected service pipeline
          company_service -> data providers + company_metrics
          rating_service -> existing analysis/model calculations
          historical_trends_service -> existing historical calculations
        ui/adapters + ui/formatters -> exact original frontend dictionary
    existing screener row caches
      screener_service -> shared company_service (no ratings)
    unchanged research.html
Flask teardown_request: release request-local provider data, even on errors
```

## Services

| Module | Responsibility |
|---|---|
| company_service | Assemble raw company/financial metrics in the original order; shared 300-second result for web requests |
| financials_service | Financials tab policy: basic financial metrics only |
| rating_service | Research component and recommendation orchestration; calls unchanged scoring, recommendation and model functions; caches complete reports by ticker and ordered peers |
| valuation_service | Rated-company pipeline used by Overview and Valuation, because their current fields require full research |
| earnings_quality_service | Reuses the rated-company pipeline: current Research Score and explanation require valuation too |
| historical_trends_service | Independently loads financial trends and company/SPY/QQQ price performance; preserves each original fallback |
| sec_filing_service | Keeps the current viewer placeholder free of SEC/DCF work; also exposes existing filing evidence through a separate, non-UI service entry point |
| screener_service | Basic company data only; adapter preserves N/A rating and research score |
| cache | Bounded process-local result store, defensive copies, same-key load coalescing |

These small tab entry points intentionally encode current policies, rather than
inventing new calculations for tabs with limited or placeholder content.

## Tab dependency contracts

| Tab | Basic data | Full rating/quality/valuation/SEC chain | FMP history + SPY/QQQ |
|---|---|---|---|
| overview | yes | yes | no |
| financials | yes | no | no |
| valuation | yes | yes | no |
| historical-trends | yes | no | yes |
| earnings-quality | yes | yes | no |
| sec-filing | yes | no | no |

All research routes also render the same lightweight seven-company screener.
There is no new asynchronous UI, route, chart, or API endpoint. News is unchanged.

## Analysis, provider and compatibility boundaries

- `analysis/company_metrics.py` holds the original dashboard formula functions.
  It deliberately does not merge the dashboard growth denominator with the
  distinct formula in `analysis/fundamentals.py`.
- `ui/adapters.py` holds exact output mapping and empty structures;
  `ui/formatters.py` holds the original display formatting.
- `analysis/rating.py:get_research_components` and
  `analysis/recommendation.py:analyze_recommendation` retain their signatures as
  compatibility delegates. Their old orchestration lives in rating_service.
  Pure scoring/recommendation functions remain in the analysis modules.
- Compatibility delegates use local imports to avoid module-initialization
  cycles. Services invoke analysis functions; legacy public entry points delegate
  back to service orchestration. Do not call those legacy entry points recursively
  from their own replacement orchestration.
- `data/yahoo_provider.py` owns raw info, statement and exact-parameter history
  access. Successful results are reused in the active request; errors are not
  memoized. Existing callers keep their different exception semantics.
- Closing price still comes from 5d Close history. Valuation info price still
  comes from info.currentPrice. They share raw access where appropriate, never
  a unified computed price.
- SEC CIK, Facts, submissions, HTML and cleaned text reuse successful values in
  a scope. There is no new persistent SEC dataset cache.
- Historical P/E and prepared DCF inputs are reused within the scope. All
  calculations, parameters, units, dates and scenario ordering remain unchanged.

## Cache lifetime and concurrency

Request data uses ContextVar state, nesting and defensive copies. It is released
on teardown and is not shared across independent threads or standalone calls.
Standalone service/report entry points open ephemeral scopes; they do not enable
cross-call result caching by default.

Web service results use a process-local LRU-like OrderedDict capped at 128 entries,
with TTL 300 seconds and keys `('company', ticker)` and
`('rating', ticker, tuple(peers))`. Rating results without a Research Score are
not added to this new store. Existing page-cache fallback behavior remains.
32 lock stripes coalesce same-key service loads; a separate short-lived store lock
protects eviction. Hash collisions can serialize unrelated loads; separate server
processes do not share these caches.

The existing company, per-company screener and full-screener caches retain their
names and 300-second boundary. Page timestamps inherit the oldest reused service
result time, so a tab opened later does not extend that result's freshness.
This is conservative: unrelated older data in a request can cause earlier expiry.
The legacy outer caches themselves are not converted into a distributed cache.

FMP still has its existing seven-day file cache, key validation order, payload,
force-refresh and expiry boundary. Writes now replace complete files atomically.
No data-source switchover or TTL extension was introduced.

## Running

Use the recorded Python 3.13 test environment and dependencies in
`tests/requirements.txt`. Run `python3 tests/run.py` for offline regression checks.
Run `python3 app.py` for the existing local Flask application. Live FMP access
requires your own FINANCIAL_API_KEY; SEC uses SEC_USER_AGENT. No .env or credentials
are included in this package. The original configuration behavior remains.
